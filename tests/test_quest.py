from content.schema import QuestDef
from engine.clock import GameClock
from engine.quest import (
    Quest,
    QuestLog,
    create_quest_log,
    quest_from_def,
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


def make_quest_def(**overrides) -> QuestDef:
    defaults = dict(
        id="test_quest",
        name="Test Quest",
        description="A quest for testing.",
        completion_message="Completed!",
    )
    defaults.update(overrides)
    return QuestDef(**defaults)


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


def test_record_entity_killed_records_but_never_completes_an_in_progress_quest():
    """record_entity_killed only remembers the death now - a kill quest no
    longer completes on the kill itself, only when reported (see
    check_kill_report below)."""
    quest = make_quest(status="in_progress", target_kill_entity_id="warden")
    log = QuestLog(quests={quest.id: quest})

    result = log.record_entity_killed("warden")

    assert result is None
    assert quest.status == "in_progress"
    assert "warden" in log.killed_entity_ids


def test_record_entity_killed_records_a_not_given_quests_target_too():
    quest = make_quest(status="not_given", target_kill_entity_id="warden")
    log = QuestLog(quests={quest.id: quest})

    log.record_entity_killed("warden")

    assert quest.status == "not_given"
    assert "warden" in log.killed_entity_ids


def test_record_entity_killed_ignores_non_matching_quests():
    quest = make_quest(status="in_progress", target_kill_entity_id="warden")
    log = QuestLog(quests={quest.id: quest})

    log.record_entity_killed("rat")

    assert quest.status == "in_progress"
    assert "rat" in log.killed_entity_ids


# --- check_kill_report ---


def test_check_kill_report_completes_when_talking_to_questgiver_after_the_kill():
    quest = make_quest(
        status="in_progress",
        questgiver_entity_id="escaped_prisoner",
        target_kill_entity_id="warden",
    )
    log = QuestLog(quests={quest.id: quest}, killed_entity_ids={"warden"})

    changed = log.check_kill_report("escaped_prisoner")

    assert changed == [quest]
    assert quest.status == "completed"


def test_check_kill_report_is_a_no_op_before_the_target_is_dead():
    quest = make_quest(
        status="in_progress",
        questgiver_entity_id="escaped_prisoner",
        target_kill_entity_id="warden",
    )
    log = QuestLog(quests={quest.id: quest})

    changed = log.check_kill_report("escaped_prisoner")

    assert changed == []
    assert quest.status == "in_progress"


def test_check_kill_report_is_a_no_op_when_talking_to_a_different_npc():
    quest = make_quest(
        status="in_progress",
        questgiver_entity_id="escaped_prisoner",
        target_kill_entity_id="warden",
    )
    log = QuestLog(quests={quest.id: quest}, killed_entity_ids={"warden"})

    changed = log.check_kill_report("village_chief")

    assert changed == []
    assert quest.status == "in_progress"


def test_check_kill_report_is_a_no_op_on_a_not_given_quest():
    """A target dying before the quest is even granted is handled by
    check_questgiver jumping straight to 'completed' at grant time, not by
    check_kill_report - see already_done_message."""
    quest = make_quest(
        status="not_given",
        questgiver_entity_id="escaped_prisoner",
        target_kill_entity_id="warden",
    )
    log = QuestLog(quests={quest.id: quest}, killed_entity_ids={"warden"})

    changed = log.check_kill_report("escaped_prisoner")

    assert changed == []
    assert quest.status == "not_given"


def test_check_kill_report_does_not_refire_on_an_already_terminal_quest():
    quest = make_quest(
        status="completed",
        questgiver_entity_id="escaped_prisoner",
        target_kill_entity_id="warden",
    )
    log = QuestLog(quests={quest.id: quest}, killed_entity_ids={"warden"})

    changed = log.check_kill_report("escaped_prisoner")

    assert changed == []


def test_check_kill_report_ignores_a_different_recorded_death():
    quest = make_quest(
        status="in_progress",
        questgiver_entity_id="escaped_prisoner",
        target_kill_entity_id="warden",
    )
    log = QuestLog(quests={quest.id: quest}, killed_entity_ids={"rat"})

    changed = log.check_kill_report("escaped_prisoner")

    assert changed == []
    assert quest.status == "in_progress"


# --- check_delivery ---


class _FakeInventoryItem:
    """Minimal stand-in for engine.entity.Entity, carrying only what
    check_delivery reads (entity_id) - keeps test_quest.py decoupled from
    engine.entity, matching how this file otherwise tests quest.py's logic
    in isolation."""

    def __init__(self, entity_id: str):
        self.entity_id = entity_id


def test_check_delivery_completes_when_talking_to_questgiver_while_carrying_the_item():
    quest = make_quest(
        status="in_progress",
        questgiver_entity_id="shopkeeper",
        target_item_id="pale_fungus",
    )
    log = QuestLog(quests={quest.id: quest})
    inventory = [_FakeInventoryItem("pale_fungus")]

    changed = log.check_delivery("shopkeeper", inventory)

    assert changed == [quest]
    assert quest.status == "completed"


def test_check_delivery_is_a_no_op_without_the_item_in_inventory():
    quest = make_quest(
        status="in_progress",
        questgiver_entity_id="shopkeeper",
        target_item_id="pale_fungus",
    )
    log = QuestLog(quests={quest.id: quest})

    changed = log.check_delivery("shopkeeper", [])

    assert changed == []
    assert quest.status == "in_progress"


def test_check_delivery_is_a_no_op_when_talking_to_a_different_npc():
    quest = make_quest(
        status="in_progress",
        questgiver_entity_id="shopkeeper",
        target_item_id="pale_fungus",
    )
    log = QuestLog(quests={quest.id: quest})
    inventory = [_FakeInventoryItem("pale_fungus")]

    changed = log.check_delivery("village_chief", inventory)

    assert changed == []
    assert quest.status == "in_progress"


def test_check_delivery_is_a_no_op_on_a_not_given_quest():
    """Confirms the deliberate scope decision: no retroactive "already had
    it" detection for fetch quests, unlike kill quests."""
    quest = make_quest(
        status="not_given",
        questgiver_entity_id="shopkeeper",
        target_item_id="pale_fungus",
    )
    log = QuestLog(quests={quest.id: quest})
    inventory = [_FakeInventoryItem("pale_fungus")]

    changed = log.check_delivery("shopkeeper", inventory)

    assert changed == []
    assert quest.status == "not_given"


def test_check_delivery_does_not_refire_on_an_already_terminal_quest():
    quest = make_quest(
        status="completed",
        questgiver_entity_id="shopkeeper",
        target_item_id="pale_fungus",
    )
    log = QuestLog(quests={quest.id: quest})
    inventory = [_FakeInventoryItem("pale_fungus")]

    changed = log.check_delivery("shopkeeper", inventory)

    assert changed == []


def test_check_delivery_ignores_non_matching_inventory_items():
    quest = make_quest(
        status="in_progress",
        questgiver_entity_id="shopkeeper",
        target_item_id="pale_fungus",
    )
    log = QuestLog(quests={quest.id: quest})
    inventory = [_FakeInventoryItem("healing_potion")]

    changed = log.check_delivery("shopkeeper", inventory)

    assert changed == []
    assert quest.status == "in_progress"


# --- shop_discount_pct ---


def test_shop_discount_pct_is_zero_with_nothing_completed():
    log = QuestLog()
    assert log.shop_discount_pct() == 0.0


def test_shop_discount_pct_returns_the_completed_quests_discount():
    quest = make_quest(status="completed", reward_shop_discount_pct=0.2)
    log = QuestLog(quests={quest.id: quest})

    assert log.shop_discount_pct() == 0.2


def test_shop_discount_pct_ignores_an_in_progress_discount_quest():
    quest = make_quest(status="in_progress", reward_shop_discount_pct=0.2)
    log = QuestLog(quests={quest.id: quest})

    assert log.shop_discount_pct() == 0.0


def test_shop_discount_pct_takes_the_largest_of_multiple_completed_discounts():
    small = make_quest(id="small", status="completed", reward_shop_discount_pct=0.1)
    big = make_quest(id="big", status="completed", reward_shop_discount_pct=0.2)
    log = QuestLog(quests={small.id: small, big.id: big})

    assert log.shop_discount_pct() == 0.2


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


# --- quest_from_def ---


def test_quest_from_def_copies_every_field():
    qdef = make_quest_def(
        id="fetch_test", name="Fetch Test", description="Bring it back.",
        completion_message="Got it.", failure_message="Too late.",
        target_item_id="pale_fungus", questgiver_entity_id="shopkeeper",
        deadline_year=87, deadline_day=60,
        given_message="Go get it.", already_done_message="Already done.",
        questgiver_done_dialogue="Thanks.",
        reward_shop_discount_pct=0.2,
        starting_status="in_progress",
    )

    quest = quest_from_def(qdef)

    assert quest.id == "fetch_test"
    assert quest.name == "Fetch Test"
    assert quest.description == "Bring it back."
    assert quest.completion_message == "Got it."
    assert quest.failure_message == "Too late."
    assert quest.target_item_id == "pale_fungus"
    assert quest.questgiver_entity_id == "shopkeeper"
    assert quest.deadline_year == 87
    assert quest.deadline_day == 60
    assert quest.given_message == "Go get it."
    assert quest.already_done_message == "Already done."
    assert quest.questgiver_done_dialogue == "Thanks."
    assert quest.reward_shop_discount_pct == 0.2
    assert quest.status == "in_progress"
    assert quest.initial_status == "in_progress"  # __post_init__ snapshots starting_status


# --- create_quest_log ---


def test_create_quest_log_builds_a_quest_per_def():
    defs = {
        "a": make_quest_def(id="a", starting_status="in_progress"),
        "b": make_quest_def(id="b", starting_status="not_given"),
    }

    log = create_quest_log(defs)

    assert set(log.quests) == {"a", "b"}
    assert log.quests["a"].status == "in_progress"
    assert log.quests["b"].status == "not_given"


def test_create_quest_log_pins_the_first_in_progress_quest_in_def_order():
    defs = {
        "not_given_one": make_quest_def(id="not_given_one", starting_status="not_given"),
        "first_in_progress": make_quest_def(id="first_in_progress", starting_status="in_progress"),
        "second_in_progress": make_quest_def(id="second_in_progress", starting_status="in_progress"),
    }

    log = create_quest_log(defs)

    assert log.active_quest_id == "first_in_progress"


def test_create_quest_log_pin_is_none_when_nothing_starts_in_progress():
    defs = {"a": make_quest_def(id="a", starting_status="not_given")}

    log = create_quest_log(defs)

    assert log.active_quest_id is None


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


# --- Quest.current_description ---


def test_current_description_defaults_to_description_when_in_progress():
    quest = make_quest(status="in_progress", description="The starting pitch.")
    assert quest.current_description([], set()) == "The starting pitch."


def test_current_description_uses_completed_description_when_set():
    quest = make_quest(
        status="completed", description="The starting pitch.",
        completed_description="All done, here's what you got.",
    )
    assert quest.current_description([], set()) == "All done, here's what you got."


def test_current_description_completed_falls_back_to_description_when_unset():
    quest = make_quest(status="completed", description="The starting pitch.")
    assert quest.current_description([], set()) == "The starting pitch."


def test_current_description_uses_failed_description_when_set():
    quest = make_quest(
        status="failed", description="The starting pitch.",
        failed_description="Too late - here's what that cost you.",
    )
    assert quest.current_description([], set()) == "Too late - here's what that cost you."


def test_current_description_failed_falls_back_to_description_when_unset():
    quest = make_quest(status="failed", description="The starting pitch.")
    assert quest.current_description([], set()) == "The starting pitch."


def test_current_description_uses_carrying_item_description_when_holding_the_item():
    quest = make_quest(
        status="in_progress", description="The starting pitch.",
        target_item_id="pale_fungus", questgiver_entity_id="shopkeeper",
        carrying_item_description="You've got it - bring it back.",
    )
    inventory = [_FakeInventoryItem("pale_fungus")]

    assert quest.current_description(inventory, set()) == "You've got it - bring it back."


def test_current_description_ignores_carrying_item_description_without_the_item():
    quest = make_quest(
        status="in_progress", description="The starting pitch.",
        target_item_id="pale_fungus", questgiver_entity_id="shopkeeper",
        carrying_item_description="You've got it - bring it back.",
    )
    assert quest.current_description([], set()) == "The starting pitch."


def test_current_description_ignores_carrying_item_description_for_a_non_fetch_quest():
    """A Talk/kill/dungeon quest has no target_item_id, so
    carrying_item_description (even if somehow set) never applies -
    matches content/schema.py's own validator rejecting that combination
    at content-load time; this just confirms the runtime side agrees."""
    quest = make_quest(
        status="in_progress", description="The starting pitch.",
        target_entity_id="village_chief", target_item_id=None,
        carrying_item_description="Should never show.",
    )
    inventory = [_FakeInventoryItem("pale_fungus")]

    assert quest.current_description(inventory, set()) == "The starting pitch."


def test_current_description_completed_takes_priority_over_carrying_item_description():
    quest = make_quest(
        status="completed", description="The starting pitch.",
        target_item_id="pale_fungus", questgiver_entity_id="shopkeeper",
        carrying_item_description="You've got it - bring it back.",
        completed_description="All done.",
    )
    inventory = [_FakeInventoryItem("pale_fungus")]

    assert quest.current_description(inventory, set()) == "All done."


def test_current_description_uses_target_dead_description_when_recorded_dead():
    quest = make_quest(
        status="in_progress", description="The starting pitch.",
        target_kill_entity_id="warden", questgiver_entity_id="escaped_prisoner",
        target_dead_description="It's done - go tell them.",
    )
    assert quest.current_description([], {"warden"}) == "It's done - go tell them."


def test_current_description_ignores_target_dead_description_before_the_kill():
    quest = make_quest(
        status="in_progress", description="The starting pitch.",
        target_kill_entity_id="warden", questgiver_entity_id="escaped_prisoner",
        target_dead_description="It's done - go tell them.",
    )
    assert quest.current_description([], set()) == "The starting pitch."


def test_current_description_ignores_target_dead_description_for_a_different_death():
    quest = make_quest(
        status="in_progress", description="The starting pitch.",
        target_kill_entity_id="warden", questgiver_entity_id="escaped_prisoner",
        target_dead_description="It's done - go tell them.",
    )
    assert quest.current_description([], {"rat"}) == "The starting pitch."


def test_current_description_ignores_target_dead_description_for_a_non_kill_quest():
    """A Talk/fetch/dungeon quest has no target_kill_entity_id, so
    target_dead_description (even if somehow set) never applies - matches
    content/schema.py's own validator rejecting that combination at
    content-load time; this just confirms the runtime side agrees."""
    quest = make_quest(
        status="in_progress", description="The starting pitch.",
        target_entity_id="village_chief", target_kill_entity_id=None,
        target_dead_description="Should never show.",
    )
    assert quest.current_description([], {"warden"}) == "The starting pitch."


def test_current_description_completed_takes_priority_over_target_dead_description():
    quest = make_quest(
        status="completed", description="The starting pitch.",
        target_kill_entity_id="warden", questgiver_entity_id="escaped_prisoner",
        target_dead_description="It's done - go tell them.",
        completed_description="All done.",
    )
    assert quest.current_description([], {"warden"}) == "All done."
