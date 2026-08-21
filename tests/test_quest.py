from engine.clock import GameClock
from engine.quest import (
    GOBLIN_WARNING_DEADLINE_DAY,
    GOBLIN_WARNING_DEADLINE_YEAR,
    GOBLIN_WARNING_ID,
    GOBLIN_WARNING_TARGET_ENTITY,
    KILL_THE_WARDEN_ID,
    KILL_THE_WARDEN_QUESTGIVER,
    KILL_THE_WARDEN_REWARD,
    KILL_THE_WARDEN_TARGET,
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
        status="in_progress",
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
    assert quest.status == "in_progress"


def test_check_deadlines_exactly_at_boundary_day_still_active():
    quest = make_quest(deadline_year=87, deadline_day=57)
    log = QuestLog(quests={quest.id: quest})
    clock = GameClock(year=87, day=57, hour=0)  # the full deadline day is granted

    changed = log.check_deadlines(clock)

    assert changed == []
    assert quest.status == "in_progress"


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
    assert fine.status == "in_progress"


def test_check_deadlines_ignores_a_quest_with_no_deadline():
    quest = make_quest(deadline_year=None, deadline_day=None)
    log = QuestLog(quests={quest.id: quest})
    clock = GameClock(year=9999, day=365, hour=23)  # far past any conceivable deadline

    changed = log.check_deadlines(clock)

    assert changed == []
    assert quest.status == "in_progress"


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
    assert quest.status == "in_progress"


def test_check_dungeon_arrival_does_not_refire_on_already_terminal_quest():
    quest = make_quest(target_dungeon_id="millhaven", status="completed")
    log = QuestLog(quests={quest.id: quest})

    changed = log.check_dungeon_arrival("millhaven")

    assert changed == []


# --- check_talked_to ---


def test_check_talked_to_matching_entity_completes_quest():
    quest = make_quest(target_entity_id="village_chief")
    log = QuestLog(quests={quest.id: quest})

    changed = log.check_talked_to("village_chief")

    assert changed == [quest]
    assert quest.status == "completed"


def test_check_talked_to_non_matching_entity_is_a_no_op():
    quest = make_quest(target_entity_id="village_chief")
    log = QuestLog(quests={quest.id: quest})

    changed = log.check_talked_to("villager")

    assert changed == []
    assert quest.status == "in_progress"


def test_check_talked_to_does_not_refire_on_already_terminal_quest():
    quest = make_quest(target_entity_id="village_chief", status="completed")
    log = QuestLog(quests={quest.id: quest})

    changed = log.check_talked_to("village_chief")

    assert changed == []


# --- check_questgiver ---


def test_check_questgiver_grants_a_not_given_quest():
    quest = make_quest(status="not_given", questgiver_entity_id="escaped_prisoner")
    log = QuestLog(quests={quest.id: quest})

    changed = log.check_questgiver("escaped_prisoner")

    assert changed == [quest]
    assert quest.status == "in_progress"


def test_check_questgiver_non_matching_entity_is_a_no_op():
    quest = make_quest(status="not_given", questgiver_entity_id="escaped_prisoner")
    log = QuestLog(quests={quest.id: quest})

    changed = log.check_questgiver("villager")

    assert changed == []
    assert quest.status == "not_given"


def test_check_questgiver_does_not_refire_once_granted():
    quest = make_quest(status="in_progress", questgiver_entity_id="escaped_prisoner")
    log = QuestLog(quests={quest.id: quest})

    changed = log.check_questgiver("escaped_prisoner")

    assert changed == []


def test_check_questgiver_jumps_straight_to_completed_if_kill_target_already_dead():
    quest = make_quest(
        status="not_given",
        questgiver_entity_id="escaped_prisoner",
        target_kill_entity_id="warden",
    )
    log = QuestLog(quests={quest.id: quest}, killed_entity_ids={"warden"})

    changed = log.check_questgiver("escaped_prisoner")

    assert changed == [quest]
    assert quest.status == "completed"


# --- followup_dialogue ---


def test_followup_dialogue_none_before_completion():
    quest = make_quest(
        status="in_progress",
        questgiver_entity_id="escaped_prisoner",
        questgiver_done_dialogue="It's done.",
    )
    log = QuestLog(quests={quest.id: quest})

    assert log.followup_dialogue("escaped_prisoner") is None


def test_followup_dialogue_after_completion_for_questgiver():
    quest = make_quest(
        status="completed",
        questgiver_entity_id="escaped_prisoner",
        questgiver_done_dialogue="It's done.",
    )
    log = QuestLog(quests={quest.id: quest})

    assert log.followup_dialogue("escaped_prisoner") == "It's done."


def test_followup_dialogue_after_completion_for_target_entity():
    quest = make_quest(
        status="completed",
        target_entity_id="village_chief",
        target_done_dialogue="Thanks for that.",
    )
    log = QuestLog(quests={quest.id: quest})

    assert log.followup_dialogue("village_chief") == "Thanks for that."


def test_followup_dialogue_none_when_not_set():
    quest = make_quest(status="completed", questgiver_entity_id="escaped_prisoner")
    log = QuestLog(quests={quest.id: quest})

    assert log.followup_dialogue("escaped_prisoner") is None


def test_followup_dialogue_none_for_non_matching_entity():
    quest = make_quest(
        status="completed",
        questgiver_entity_id="escaped_prisoner",
        questgiver_done_dialogue="It's done.",
    )
    log = QuestLog(quests={quest.id: quest})

    assert log.followup_dialogue("villager") is None


# --- record_entity_killed ---


def test_record_entity_killed_records_unconditionally():
    log = QuestLog()

    log.record_entity_killed("warden")

    assert "warden" in log.killed_entity_ids


def test_record_entity_killed_completes_a_matching_in_progress_quest():
    quest = make_quest(status="in_progress", target_kill_entity_id="warden")
    log = QuestLog(quests={quest.id: quest})

    changed = log.record_entity_killed("warden")

    assert changed == [quest]
    assert quest.status == "completed"


def test_record_entity_killed_does_not_complete_a_not_given_quest_but_still_records_it():
    quest = make_quest(status="not_given", target_kill_entity_id="warden")
    log = QuestLog(quests={quest.id: quest})

    changed = log.record_entity_killed("warden")

    assert changed == []
    assert quest.status == "not_given"
    assert "warden" in log.killed_entity_ids


def test_record_entity_killed_does_not_refire_on_a_terminal_quest():
    quest = make_quest(status="completed", target_kill_entity_id="warden")
    log = QuestLog(quests={quest.id: quest})

    changed = log.record_entity_killed("warden")

    assert changed == []


def test_record_entity_killed_ignores_non_matching_quests():
    quest = make_quest(status="in_progress", target_kill_entity_id="warden")
    log = QuestLog(quests={quest.id: quest})

    changed = log.record_entity_killed("rat")

    assert changed == []
    assert quest.status == "in_progress"
    assert "rat" in log.killed_entity_ids


# --- active_quest / set_active_quest ---


def test_active_quest_returns_none_when_nothing_pinned():
    log = QuestLog()
    assert log.active_quest() is None


def test_active_quest_returns_the_pinned_quest():
    quest = make_quest()
    log = QuestLog(quests={quest.id: quest}, active_quest_id=quest.id)

    assert log.active_quest() is quest


def test_set_active_quest_changes_the_pin():
    log = QuestLog()
    log.set_active_quest("test_quest")
    assert log.active_quest_id == "test_quest"


# --- reset ---


def test_reset_returns_terminal_quests_to_their_own_starting_status():
    failed = make_quest(id="failed_one", status="in_progress")
    failed.status = "failed"  # simulate having failed after starting in_progress
    completed = make_quest(id="completed_one", status="in_progress")
    completed.status = "completed"
    still_active = make_quest(id="active_one", status="in_progress")
    not_given = make_quest(id="not_given_one", status="not_given")
    log = QuestLog(quests={q.id: q for q in (failed, completed, still_active, not_given)})

    log.reset()

    assert failed.status == "in_progress"
    assert completed.status == "in_progress"
    assert still_active.status == "in_progress"
    assert not_given.status == "not_given"  # stays not-given, not reset to in_progress


def test_reset_clears_killed_entity_ids():
    log = QuestLog(killed_entity_ids={"warden"})
    log.reset()
    assert log.killed_entity_ids == set()


def test_reset_recomputes_the_active_pin_from_initially_in_progress_quests():
    given = make_quest(id="given_one", status="in_progress")
    not_given = make_quest(id="not_given_one", status="not_given")
    log = QuestLog(
        quests={given.id: given, not_given.id: not_given}, active_quest_id="not_given_one"
    )
    given.status = "completed"  # simulate progress since the log was built

    log.reset()

    assert log.active_quest_id == "given_one"


def test_reset_active_pin_is_none_when_nothing_started_in_progress():
    quest = make_quest(status="not_given")
    log = QuestLog(quests={quest.id: quest}, active_quest_id=None)

    log.reset()

    assert log.active_quest_id is None


# --- no-deadline quests ---


def test_format_for_hud_no_deadline_omits_the_day_suffix():
    quest = make_quest(name="An Old Debt", deadline_year=None, deadline_day=None, status="in_progress")
    assert quest.format_for_hud() == "Quest: An Old Debt - active"


# --- create_starting_quest_log ---


def test_create_starting_quest_log_has_both_quests():
    log = create_starting_quest_log()

    assert set(log.quests) == {GOBLIN_WARNING_ID, KILL_THE_WARDEN_ID}


def test_create_starting_quest_log_goblin_warning_is_given_from_the_start():
    log = create_starting_quest_log()
    quest = log.quests[GOBLIN_WARNING_ID]

    assert quest.status == "in_progress"
    assert quest.deadline_year == GOBLIN_WARNING_DEADLINE_YEAR == 87
    assert quest.deadline_day == GOBLIN_WARNING_DEADLINE_DAY == 57
    assert quest.target_entity_id == GOBLIN_WARNING_TARGET_ENTITY == "village_chief"
    assert quest.target_dungeon_id is None


def test_create_starting_quest_log_kill_the_warden_starts_not_given():
    log = create_starting_quest_log()
    quest = log.quests[KILL_THE_WARDEN_ID]

    assert quest.status == "not_given"
    assert quest.deadline_year is None
    assert quest.deadline_day is None
    assert quest.questgiver_entity_id == KILL_THE_WARDEN_QUESTGIVER == "escaped_prisoner"
    assert quest.target_kill_entity_id == KILL_THE_WARDEN_TARGET == "warden"
    assert quest.reward_item_id == KILL_THE_WARDEN_REWARD == "healing_potion"


def test_create_starting_quest_log_pins_the_goblin_warning_as_active():
    log = create_starting_quest_log()
    assert log.active_quest_id == GOBLIN_WARNING_ID


# --- Quest.format_for_hud ---


def test_format_for_hud_active_shows_deadline():
    quest = make_quest(name="The Goblin Warning", deadline_day=57, status="in_progress")
    assert quest.format_for_hud() == "Quest: The Goblin Warning - active (by Day 57)"


def test_format_for_hud_completed_omits_deadline():
    quest = make_quest(name="The Goblin Warning", status="completed")
    assert quest.format_for_hud() == "Quest: The Goblin Warning - completed"


def test_format_for_hud_failed_omits_deadline():
    quest = make_quest(name="The Goblin Warning", status="failed")
    assert quest.format_for_hud() == "Quest: The Goblin Warning - failed"


def test_format_for_hud_not_given():
    quest = make_quest(name="An Old Debt", status="not_given")
    assert quest.format_for_hud() == "Quest: An Old Debt - not_given"
