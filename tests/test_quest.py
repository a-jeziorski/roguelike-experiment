from engine.clock import GameClock
from engine.quest import (
    SEALED_MESSAGE_DEADLINE_DAY,
    SEALED_MESSAGE_DEADLINE_YEAR,
    SEALED_MESSAGE_ID,
    SEALED_MESSAGE_TARGET_DUNGEON,
    Quest,
    QuestLog,
    create_starting_quest_log,
)


def make_quest(**overrides) -> Quest:
    defaults = dict(
        id="test_quest",
        name="Test Quest",
        description="A quest for testing.",
        completion_message="Completed!",
        failure_message="Failed!",
        deadline_year=87,
        deadline_day=57,
        target_dungeon_id="millhaven",
    )
    defaults.update(overrides)
    return Quest(**defaults)


# --- check_deadlines ---


def test_check_deadlines_not_yet_due():
    quest = make_quest(deadline_year=87, deadline_day=57)
    log = QuestLog(quests={quest.id: quest})
    clock = GameClock(year=87, day=57, hour=23)  # still within the deadline day

    changed = log.check_deadlines(clock)

    assert changed == []
    assert quest.status == "active"


def test_check_deadlines_exactly_at_boundary_day_still_active():
    quest = make_quest(deadline_year=87, deadline_day=57)
    log = QuestLog(quests={quest.id: quest})
    clock = GameClock(year=87, day=57, hour=0)  # the full deadline day is granted

    changed = log.check_deadlines(clock)

    assert changed == []
    assert quest.status == "active"


def test_check_deadlines_past_due_fails():
    quest = make_quest(deadline_year=87, deadline_day=57)
    log = QuestLog(quests={quest.id: quest})
    clock = GameClock(year=87, day=58, hour=0)  # day 57 has fully passed

    changed = log.check_deadlines(clock)

    assert changed == [quest]
    assert quest.status == "failed"


def test_check_deadlines_does_not_refire_on_already_failed_quest():
    quest = make_quest(deadline_year=87, deadline_day=57, status="failed")
    log = QuestLog(quests={quest.id: quest})
    clock = GameClock(year=87, day=58, hour=0)

    changed = log.check_deadlines(clock)

    assert changed == []


def test_check_deadlines_does_not_refire_on_already_completed_quest():
    quest = make_quest(deadline_year=87, deadline_day=57, status="completed")
    log = QuestLog(quests={quest.id: quest})
    clock = GameClock(year=87, day=58, hour=0)

    changed = log.check_deadlines(clock)

    assert changed == []


def test_check_deadlines_only_returns_quests_that_changed():
    overdue = make_quest(id="overdue", deadline_year=87, deadline_day=57)
    fine = make_quest(id="fine", deadline_year=87, deadline_day=100)
    log = QuestLog(quests={overdue.id: overdue, fine.id: fine})
    clock = GameClock(year=87, day=58, hour=0)

    changed = log.check_deadlines(clock)

    assert changed == [overdue]
    assert fine.status == "active"


# --- check_dungeon_arrival ---


def test_check_dungeon_arrival_matching_dungeon_completes_quest():
    quest = make_quest(target_dungeon_id="millhaven")
    log = QuestLog(quests={quest.id: quest})

    changed = log.check_dungeon_arrival("millhaven")

    assert changed == [quest]
    assert quest.status == "completed"


def test_check_dungeon_arrival_non_matching_dungeon_is_a_no_op():
    quest = make_quest(target_dungeon_id="millhaven")
    log = QuestLog(quests={quest.id: quest})

    changed = log.check_dungeon_arrival("forgotten_ruins")

    assert changed == []
    assert quest.status == "active"


def test_check_dungeon_arrival_does_not_refire_on_already_terminal_quest():
    quest = make_quest(target_dungeon_id="millhaven", status="completed")
    log = QuestLog(quests={quest.id: quest})

    changed = log.check_dungeon_arrival("millhaven")

    assert changed == []


# --- reset ---


def test_reset_returns_terminal_quests_to_active():
    failed = make_quest(id="failed_one", status="failed")
    completed = make_quest(id="completed_one", status="completed")
    still_active = make_quest(id="active_one", status="active")
    log = QuestLog(quests={q.id: q for q in (failed, completed, still_active)})

    log.reset()

    assert failed.status == "active"
    assert completed.status == "active"
    assert still_active.status == "active"


# --- create_starting_quest_log ---


def test_create_starting_quest_log_has_the_sealed_message_quest():
    log = create_starting_quest_log()

    assert set(log.quests) == {SEALED_MESSAGE_ID}
    quest = log.quests[SEALED_MESSAGE_ID]
    assert quest.status == "active"
    assert quest.deadline_year == SEALED_MESSAGE_DEADLINE_YEAR == 87
    assert quest.deadline_day == SEALED_MESSAGE_DEADLINE_DAY == 57
    assert quest.target_dungeon_id == SEALED_MESSAGE_TARGET_DUNGEON == "millhaven"


# --- Quest.format_for_hud ---


def test_format_for_hud_active_shows_deadline():
    quest = make_quest(name="The Sealed Message", deadline_day=57, status="active")
    assert quest.format_for_hud() == "Quest: The Sealed Message - active (by Day 57)"


def test_format_for_hud_completed_omits_deadline():
    quest = make_quest(name="The Sealed Message", status="completed")
    assert quest.format_for_hud() == "Quest: The Sealed Message - completed"


def test_format_for_hud_failed_omits_deadline():
    quest = make_quest(name="The Sealed Message", status="failed")
    assert quest.format_for_hud() == "Quest: The Sealed Message - failed"
