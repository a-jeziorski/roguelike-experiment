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

    assert changed == [(quest, True)]
    assert quest.status == "failed"


def test_check_deadlines_fails_a_not_given_quest_too():
    """A quest the player never picked up still fails once its deadline
    passes - the world (and any on_fail consequences, e.g.
    destroy_dungeon_id) doesn't wait for the player to have taken the
    quest first. was_in_progress is False here so the caller
    (Engine._check_quest_deadlines) knows not to show a failure_message
    for a quest the player never received."""
    quest = make_quest(deadline_year=87, deadline_day=57, status="not_given")
    log = QuestLog(quests={quest.id: quest})
    clock = GameClock(year=87, day=58, hour=0)

    changed = log.check_deadlines(clock)

    assert changed == [(quest, False)]
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

    assert changed == [(overdue, True)]
    assert fine.status == "in_progress"


def test_check_deadlines_ignores_a_quest_with_no_deadline():
    quest = make_quest(deadline_year=None, deadline_day=None)
    log = QuestLog(quests={quest.id: quest})
    clock = GameClock(year=9999, day=365, hour=23)  # far past any conceivable deadline

    changed = log.check_deadlines(clock)

    assert changed == []
    assert quest.status == "in_progress"


# --- void_by_dungeon ---


def test_void_by_dungeon_fails_an_in_progress_quest_and_reports_it_was_in_progress():
    quest = make_quest(voided_by_dungeon_id="wayford", status="in_progress")
    log = QuestLog(quests={quest.id: quest})

    changed = log.void_by_dungeon("wayford")

    assert changed == [(quest, True)]
    assert quest.status == "failed"


def test_void_by_dungeon_fails_a_not_given_quest_and_reports_it_was_not_in_progress():
    quest = make_quest(voided_by_dungeon_id="wayford", status="not_given")
    log = QuestLog(quests={quest.id: quest})

    changed = log.void_by_dungeon("wayford")

    assert changed == [(quest, False)]
    assert quest.status == "failed"


def test_void_by_dungeon_ignores_a_quest_voided_by_a_different_dungeon():
    quest = make_quest(voided_by_dungeon_id="millhaven", status="in_progress")
    log = QuestLog(quests={quest.id: quest})

    changed = log.void_by_dungeon("wayford")

    assert changed == []
    assert quest.status == "in_progress"


def test_void_by_dungeon_leaves_a_completed_quest_untouched():
    quest = make_quest(voided_by_dungeon_id="wayford", status="completed")
    log = QuestLog(quests={quest.id: quest})

    changed = log.void_by_dungeon("wayford")

    assert changed == []
    assert quest.status == "completed"


def test_void_by_dungeon_leaves_an_already_failed_quest_untouched():
    quest = make_quest(voided_by_dungeon_id="wayford", status="failed")
    log = QuestLog(quests={quest.id: quest})

    changed = log.void_by_dungeon("wayford")

    assert changed == []


# --- fail_intimidate_by_death ---


def test_fail_intimidate_by_death_fails_an_in_progress_quest_and_reports_it_was_in_progress():
    quest = make_quest(
        target_dungeon_id=None, target_intimidate_entity_id="millhaven_debtor", status="in_progress",
    )
    log = QuestLog(quests={quest.id: quest})

    changed = log.fail_intimidate_by_death("millhaven_debtor")

    assert changed == [(quest, True)]
    assert quest.status == "failed"


def test_fail_intimidate_by_death_fails_a_not_given_quest_and_reports_it_was_not_in_progress():
    quest = make_quest(
        target_dungeon_id=None, target_intimidate_entity_id="millhaven_debtor", status="not_given",
    )
    log = QuestLog(quests={quest.id: quest})

    changed = log.fail_intimidate_by_death("millhaven_debtor")

    assert changed == [(quest, False)]
    assert quest.status == "failed"


def test_fail_intimidate_by_death_ignores_a_different_entitys_death():
    quest = make_quest(
        target_dungeon_id=None, target_intimidate_entity_id="millhaven_debtor", status="in_progress",
    )
    log = QuestLog(quests={quest.id: quest})

    changed = log.fail_intimidate_by_death("rat")

    assert changed == []
    assert quest.status == "in_progress"


def test_fail_intimidate_by_death_leaves_a_completed_quest_untouched():
    quest = make_quest(
        target_dungeon_id=None, target_intimidate_entity_id="millhaven_debtor", status="completed",
    )
    log = QuestLog(quests={quest.id: quest})

    changed = log.fail_intimidate_by_death("millhaven_debtor")

    assert changed == []
    assert quest.status == "completed"


def test_fail_intimidate_by_death_leaves_an_already_failed_quest_untouched():
    quest = make_quest(
        target_dungeon_id=None, target_intimidate_entity_id="millhaven_debtor", status="failed",
    )
    log = QuestLog(quests={quest.id: quest})

    changed = log.fail_intimidate_by_death("millhaven_debtor")

    assert changed == []


# --- reset ---


def test_reset_clears_destroyed_dungeon_ids():
    quest = make_quest(status="in_progress")
    log = QuestLog(quests={quest.id: quest}, destroyed_dungeon_ids={"wayford"})

    log.reset()

    assert log.destroyed_dungeon_ids == set()


# --- record_dungeon_arrival ---


def test_record_dungeon_arrival_records_but_never_completes_an_in_progress_quest():
    """record_dungeon_arrival only remembers the visit now - a dungeon-arrival
    quest no longer completes on arrival itself, only when reported (see
    check_dungeon_report below)."""
    quest = make_quest(target_dungeon_id="millhaven")
    log = QuestLog(quests={quest.id: quest})

    result = log.record_dungeon_arrival("millhaven")

    assert result is None
    assert quest.status == "in_progress"
    assert "millhaven" in log.visited_dungeon_ids


def test_record_dungeon_arrival_records_a_not_given_quests_target_too():
    quest = make_quest(target_dungeon_id="millhaven", status="not_given")
    log = QuestLog(quests={quest.id: quest})

    log.record_dungeon_arrival("millhaven")

    assert quest.status == "not_given"
    assert "millhaven" in log.visited_dungeon_ids


def test_record_dungeon_arrival_ignores_non_matching_quests():
    quest = make_quest(target_dungeon_id="millhaven")
    log = QuestLog(quests={quest.id: quest})

    log.record_dungeon_arrival("forgotten_ruins")

    assert quest.status == "in_progress"
    assert "forgotten_ruins" in log.visited_dungeon_ids


# --- check_dungeon_report ---


def test_check_dungeon_report_completes_when_talking_to_questgiver_after_arrival():
    quest = make_quest(
        target_dungeon_id="millhaven",
        questgiver_entity_id="wayford_caravan_master",
    )
    log = QuestLog(quests={quest.id: quest}, visited_dungeon_ids={"millhaven"})

    changed = log.check_dungeon_report("wayford_caravan_master")

    assert changed == [quest]
    assert quest.status == "completed"


def test_check_dungeon_report_is_a_no_op_before_the_dungeon_is_visited():
    quest = make_quest(
        target_dungeon_id="millhaven",
        questgiver_entity_id="wayford_caravan_master",
    )
    log = QuestLog(quests={quest.id: quest})

    changed = log.check_dungeon_report("wayford_caravan_master")

    assert changed == []
    assert quest.status == "in_progress"


def test_check_dungeon_report_is_a_no_op_when_talking_to_a_different_npc():
    quest = make_quest(
        target_dungeon_id="millhaven",
        questgiver_entity_id="wayford_caravan_master",
    )
    log = QuestLog(quests={quest.id: quest}, visited_dungeon_ids={"millhaven"})

    changed = log.check_dungeon_report("village_chief")

    assert changed == []
    assert quest.status == "in_progress"


def test_check_dungeon_report_is_a_no_op_on_a_not_given_quest():
    """A dungeon visited before the quest is even granted is handled by
    check_questgiver jumping straight to 'completed' at grant time, not by
    check_dungeon_report - see already_done_message."""
    quest = make_quest(
        target_dungeon_id="millhaven",
        questgiver_entity_id="wayford_caravan_master",
        status="not_given",
    )
    log = QuestLog(quests={quest.id: quest}, visited_dungeon_ids={"millhaven"})

    changed = log.check_dungeon_report("wayford_caravan_master")

    assert changed == []
    assert quest.status == "not_given"


def test_check_dungeon_report_does_not_refire_on_an_already_terminal_quest():
    quest = make_quest(
        target_dungeon_id="millhaven",
        questgiver_entity_id="wayford_caravan_master",
        status="completed",
    )
    log = QuestLog(quests={quest.id: quest}, visited_dungeon_ids={"millhaven"})

    changed = log.check_dungeon_report("wayford_caravan_master")

    assert changed == []


def test_check_dungeon_report_ignores_a_different_visited_dungeon():
    quest = make_quest(
        target_dungeon_id="millhaven",
        questgiver_entity_id="wayford_caravan_master",
    )
    log = QuestLog(quests={quest.id: quest}, visited_dungeon_ids={"forgotten_ruins"})

    changed = log.check_dungeon_report("wayford_caravan_master")

    assert changed == []
    assert quest.status == "in_progress"


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

    changed = log.check_questgiver("escaped_prisoner", GameClock())

    assert changed == [quest]
    assert quest.status == "in_progress"


def test_check_questgiver_non_matching_entity_is_a_no_op():
    quest = make_quest(status="not_given", questgiver_entity_id="escaped_prisoner")
    log = QuestLog(quests={quest.id: quest})

    changed = log.check_questgiver("villager", GameClock())

    assert changed == []
    assert quest.status == "not_given"


def test_check_questgiver_does_not_refire_once_granted():
    quest = make_quest(status="in_progress", questgiver_entity_id="escaped_prisoner")
    log = QuestLog(quests={quest.id: quest})

    changed = log.check_questgiver("escaped_prisoner", GameClock())

    assert changed == []


def test_check_questgiver_jumps_straight_to_completed_if_kill_target_already_dead():
    quest = make_quest(
        status="not_given",
        questgiver_entity_id="escaped_prisoner",
        target_kill_entity_id="warden",
    )
    log = QuestLog(quests={quest.id: quest}, killed_entity_ids={"warden"})

    changed = log.check_questgiver("escaped_prisoner", GameClock())

    assert changed == [quest]
    assert quest.status == "completed"


def test_check_questgiver_jumps_straight_to_completed_if_dungeon_already_visited():
    quest = make_quest(
        status="not_given",
        questgiver_entity_id="wayford_caravan_master",
        target_dungeon_id="millhaven",
    )
    log = QuestLog(quests={quest.id: quest}, visited_dungeon_ids={"millhaven"})

    changed = log.check_questgiver("wayford_caravan_master", GameClock())

    assert changed == [quest]
    assert quest.status == "completed"


def test_check_questgiver_jumps_straight_to_completed_if_intimidate_target_already_intimidated():
    quest = make_quest(
        status="not_given",
        questgiver_entity_id="wayford_provisioner",
        target_dungeon_id=None,
        target_intimidate_entity_id="millhaven_debtor",
    )
    log = QuestLog(quests={quest.id: quest}, intimidated_entity_ids={"millhaven_debtor"})

    changed = log.check_questgiver("wayford_provisioner", GameClock())

    assert changed == [quest]
    assert quest.status == "completed"


def test_check_questgiver_withholds_a_quest_whose_prerequisite_is_not_yet_completed():
    prereq = make_quest(id="prereq", status="in_progress", target_entity_id="village_chief")
    chained = make_quest(
        id="chained", status="not_given",
        questgiver_entity_id="village_chief", requires_quest_id="prereq",
    )
    log = QuestLog(quests={prereq.id: prereq, chained.id: chained})

    changed = log.check_questgiver("village_chief", GameClock())

    assert changed == []
    assert chained.status == "not_given"


def test_check_questgiver_grants_a_quest_once_its_prerequisite_is_completed():
    prereq = make_quest(id="prereq", status="completed", target_entity_id="village_chief")
    chained = make_quest(
        id="chained", status="not_given",
        questgiver_entity_id="village_chief", requires_quest_id="prereq",
    )
    log = QuestLog(quests={prereq.id: prereq, chained.id: chained})

    changed = log.check_questgiver("village_chief", GameClock())

    assert changed == [chained]
    assert chained.status == "in_progress"


def test_check_questgiver_withholds_a_quest_whose_prerequisite_failed():
    prereq = make_quest(id="prereq", status="failed", target_entity_id="village_chief")
    chained = make_quest(
        id="chained", status="not_given",
        questgiver_entity_id="village_chief", requires_quest_id="prereq",
    )
    log = QuestLog(quests={prereq.id: prereq, chained.id: chained})

    changed = log.check_questgiver("village_chief", GameClock())

    assert changed == []
    assert chained.status == "not_given"  # permanently ungrantable - correct, not a bug


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


def test_followup_dialogue_prefers_the_later_defined_quest_for_a_chained_npc():
    """The Village Chief's real-world case: target_entity_id for goblin_warning
    (defined first) and questgiver_entity_id for its requires_quest_id-gated
    follow-up (defined after it). Once both are completed, the later quest's
    line should win, not get stuck on the earlier one forever."""
    earlier = make_quest(
        id="earlier", status="completed",
        target_entity_id="village_chief", target_done_dialogue="The warning's out now.",
    )
    later = make_quest(
        id="later", status="completed",
        questgiver_entity_id="village_chief", questgiver_done_dialogue="Word's on its way to Wayford now.",
    )
    log = QuestLog(quests={earlier.id: earlier, later.id: later})

    assert log.followup_dialogue("village_chief") == "Word's on its way to Wayford now."


# --- record_encounter_triggered ---


def test_record_encounter_triggered_records_unconditionally():
    log = QuestLog()

    log.record_encounter_triggered("warning_ambush")

    assert "warning_ambush" in log.triggered_encounter_ids


def test_arm_encounter_sets_the_due_time():
    log = QuestLog()

    log.arm_encounter("warning_ambush", (87, 50, 3))

    assert log.armed_encounters["warning_ambush"] == (87, 50, 3)


def test_arm_encounter_overwrites_an_existing_due_time():
    log = QuestLog(armed_encounters={"warning_ambush": (87, 50, 3)})

    log.arm_encounter("warning_ambush", (87, 50, 10))

    assert log.armed_encounters["warning_ambush"] == (87, 50, 10)


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


# --- record_entity_intimidated ---


def test_record_entity_intimidated_records_unconditionally():
    log = QuestLog()

    log.record_entity_intimidated("millhaven_debtor")

    assert "millhaven_debtor" in log.intimidated_entity_ids


def test_record_entity_intimidated_records_but_never_completes_an_in_progress_quest():
    """record_entity_intimidated only remembers the hit now - an intimidate
    quest doesn't complete on the hit itself, only when reported (see
    check_intimidate_report below)."""
    quest = make_quest(
        status="in_progress", target_dungeon_id=None, target_intimidate_entity_id="millhaven_debtor",
    )
    log = QuestLog(quests={quest.id: quest})

    result = log.record_entity_intimidated("millhaven_debtor")

    assert result is None
    assert quest.status == "in_progress"
    assert "millhaven_debtor" in log.intimidated_entity_ids


def test_record_entity_intimidated_records_a_not_given_quests_target_too():
    quest = make_quest(
        status="not_given", target_dungeon_id=None, target_intimidate_entity_id="millhaven_debtor",
    )
    log = QuestLog(quests={quest.id: quest})

    log.record_entity_intimidated("millhaven_debtor")

    assert quest.status == "not_given"
    assert "millhaven_debtor" in log.intimidated_entity_ids


def test_record_entity_intimidated_ignores_non_matching_quests():
    quest = make_quest(
        status="in_progress", target_dungeon_id=None, target_intimidate_entity_id="millhaven_debtor",
    )
    log = QuestLog(quests={quest.id: quest})

    log.record_entity_intimidated("villager")

    assert quest.status == "in_progress"
    assert "villager" in log.intimidated_entity_ids


# --- check_intimidate_report ---


def test_check_intimidate_report_completes_when_talking_to_questgiver_after_the_hit():
    quest = make_quest(
        status="in_progress",
        target_dungeon_id=None,
        questgiver_entity_id="wayford_provisioner",
        target_intimidate_entity_id="millhaven_debtor",
    )
    log = QuestLog(quests={quest.id: quest}, intimidated_entity_ids={"millhaven_debtor"})

    changed = log.check_intimidate_report("wayford_provisioner")

    assert changed == [quest]
    assert quest.status == "completed"


def test_check_intimidate_report_is_a_no_op_before_the_target_is_hit():
    quest = make_quest(
        status="in_progress",
        target_dungeon_id=None,
        questgiver_entity_id="wayford_provisioner",
        target_intimidate_entity_id="millhaven_debtor",
    )
    log = QuestLog(quests={quest.id: quest})

    changed = log.check_intimidate_report("wayford_provisioner")

    assert changed == []
    assert quest.status == "in_progress"


def test_check_intimidate_report_is_a_no_op_when_talking_to_a_different_npc():
    quest = make_quest(
        status="in_progress",
        target_dungeon_id=None,
        questgiver_entity_id="wayford_provisioner",
        target_intimidate_entity_id="millhaven_debtor",
    )
    log = QuestLog(quests={quest.id: quest}, intimidated_entity_ids={"millhaven_debtor"})

    changed = log.check_intimidate_report("village_chief")

    assert changed == []
    assert quest.status == "in_progress"


def test_check_intimidate_report_is_a_no_op_on_a_not_given_quest():
    """A target hit before the quest is even granted is handled by
    check_questgiver jumping straight to 'completed' at grant time, not by
    check_intimidate_report - see already_done_message."""
    quest = make_quest(
        status="not_given",
        target_dungeon_id=None,
        questgiver_entity_id="wayford_provisioner",
        target_intimidate_entity_id="millhaven_debtor",
    )
    log = QuestLog(quests={quest.id: quest}, intimidated_entity_ids={"millhaven_debtor"})

    changed = log.check_intimidate_report("wayford_provisioner")

    assert changed == []
    assert quest.status == "not_given"


def test_check_intimidate_report_does_not_refire_on_an_already_terminal_quest():
    quest = make_quest(
        status="completed",
        target_dungeon_id=None,
        questgiver_entity_id="wayford_provisioner",
        target_intimidate_entity_id="millhaven_debtor",
    )
    log = QuestLog(quests={quest.id: quest}, intimidated_entity_ids={"millhaven_debtor"})

    changed = log.check_intimidate_report("wayford_provisioner")

    assert changed == []


def test_check_intimidate_report_is_a_no_op_on_a_quest_already_failed_by_the_targets_death():
    """A lethal hit results in 'failed', never 'completed' - check_intimidate_report's
    status != "in_progress" guard means a dead target's quest is simply
    skipped here, never wrongly completed even though the hit also got
    recorded in intimidated_entity_ids (see engine/combat.py's _apply_damage)."""
    quest = make_quest(
        status="failed",
        target_dungeon_id=None,
        questgiver_entity_id="wayford_provisioner",
        target_intimidate_entity_id="millhaven_debtor",
    )
    log = QuestLog(quests={quest.id: quest}, intimidated_entity_ids={"millhaven_debtor"})

    changed = log.check_intimidate_report("wayford_provisioner")

    assert changed == []
    assert quest.status == "failed"


def test_check_intimidate_report_ignores_a_different_recorded_hit():
    quest = make_quest(
        status="in_progress",
        target_dungeon_id=None,
        questgiver_entity_id="wayford_provisioner",
        target_intimidate_entity_id="millhaven_debtor",
    )
    log = QuestLog(quests={quest.id: quest}, intimidated_entity_ids={"villager"})

    changed = log.check_intimidate_report("wayford_provisioner")

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
    assert log.shop_discount_pct("shopkeeper") == 0.0


def test_shop_discount_pct_returns_the_completed_quests_discount():
    quest = make_quest(
        status="completed", reward_shop_discount_pct=0.2,
        reward_shop_discount_entity_id="shopkeeper",
    )
    log = QuestLog(quests={quest.id: quest})

    assert log.shop_discount_pct("shopkeeper") == 0.2


def test_shop_discount_pct_ignores_an_in_progress_discount_quest():
    quest = make_quest(
        status="in_progress", reward_shop_discount_pct=0.2,
        reward_shop_discount_entity_id="shopkeeper",
    )
    log = QuestLog(quests={quest.id: quest})

    assert log.shop_discount_pct("shopkeeper") == 0.0


def test_shop_discount_pct_ignores_a_completed_discount_scoped_to_a_different_shopkeeper():
    quest = make_quest(
        status="completed", reward_shop_discount_pct=0.2,
        reward_shop_discount_entity_id="wayford_provisioner",
    )
    log = QuestLog(quests={quest.id: quest})

    assert log.shop_discount_pct("shopkeeper") == 0.0
    assert log.shop_discount_pct("wayford_provisioner") == 0.2


def test_shop_discount_pct_takes_the_largest_of_multiple_completed_discounts_for_the_same_shop():
    small = make_quest(
        id="small", status="completed", reward_shop_discount_pct=0.1,
        reward_shop_discount_entity_id="shopkeeper",
    )
    big = make_quest(
        id="big", status="completed", reward_shop_discount_pct=0.2,
        reward_shop_discount_entity_id="shopkeeper",
    )
    log = QuestLog(quests={small.id: small, big.id: big})

    assert log.shop_discount_pct("shopkeeper") == 0.2


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


def test_reset_clears_intimidated_entity_ids():
    log = QuestLog(intimidated_entity_ids={"millhaven_debtor"})
    log.reset()
    assert log.intimidated_entity_ids == set()


def test_reset_clears_triggered_encounter_ids():
    log = QuestLog(triggered_encounter_ids={"warning_ambush"})
    log.reset()
    assert log.triggered_encounter_ids == set()


def test_reset_clears_armed_encounters():
    log = QuestLog(armed_encounters={"warning_ambush": (87, 50, 3)})
    log.reset()
    assert log.armed_encounters == {}


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
        reward_shop_discount_entity_id="shopkeeper",
        requires_quest_id="some_other_quest",
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
    assert quest.reward_shop_discount_entity_id == "shopkeeper"
    assert quest.requires_quest_id == "some_other_quest"
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
    assert quest.current_description([], set(), set(), set()) == "The starting pitch."


def test_current_description_uses_completed_description_when_set():
    quest = make_quest(
        status="completed", description="The starting pitch.",
        completed_description="All done, here's what you got.",
    )
    assert quest.current_description([], set(), set(), set()) == "All done, here's what you got."


def test_current_description_completed_falls_back_to_description_when_unset():
    quest = make_quest(status="completed", description="The starting pitch.")
    assert quest.current_description([], set(), set(), set()) == "The starting pitch."


def test_current_description_uses_failed_description_when_set():
    quest = make_quest(
        status="failed", description="The starting pitch.",
        failed_description="Too late - here's what that cost you.",
    )
    assert quest.current_description([], set(), set(), set()) == "Too late - here's what that cost you."


def test_current_description_failed_falls_back_to_description_when_unset():
    quest = make_quest(status="failed", description="The starting pitch.")
    assert quest.current_description([], set(), set(), set()) == "The starting pitch."


def test_current_description_uses_carrying_item_description_when_holding_the_item():
    quest = make_quest(
        status="in_progress", description="The starting pitch.",
        target_item_id="pale_fungus", questgiver_entity_id="shopkeeper",
        carrying_item_description="You've got it - bring it back.",
    )
    inventory = [_FakeInventoryItem("pale_fungus")]

    assert quest.current_description(inventory, set(), set(), set()) == "You've got it - bring it back."


def test_current_description_ignores_carrying_item_description_without_the_item():
    quest = make_quest(
        status="in_progress", description="The starting pitch.",
        target_item_id="pale_fungus", questgiver_entity_id="shopkeeper",
        carrying_item_description="You've got it - bring it back.",
    )
    assert quest.current_description([], set(), set(), set()) == "The starting pitch."


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

    assert quest.current_description(inventory, set(), set(), set()) == "The starting pitch."


def test_current_description_completed_takes_priority_over_carrying_item_description():
    quest = make_quest(
        status="completed", description="The starting pitch.",
        target_item_id="pale_fungus", questgiver_entity_id="shopkeeper",
        carrying_item_description="You've got it - bring it back.",
        completed_description="All done.",
    )
    inventory = [_FakeInventoryItem("pale_fungus")]

    assert quest.current_description(inventory, set(), set(), set()) == "All done."


def test_current_description_uses_target_dead_description_when_recorded_dead():
    quest = make_quest(
        status="in_progress", description="The starting pitch.",
        target_kill_entity_id="warden", questgiver_entity_id="escaped_prisoner",
        target_dead_description="It's done - go tell them.",
    )
    assert quest.current_description([], {"warden"}, set(), set()) == "It's done - go tell them."


def test_current_description_ignores_target_dead_description_before_the_kill():
    quest = make_quest(
        status="in_progress", description="The starting pitch.",
        target_kill_entity_id="warden", questgiver_entity_id="escaped_prisoner",
        target_dead_description="It's done - go tell them.",
    )
    assert quest.current_description([], set(), set(), set()) == "The starting pitch."


def test_current_description_ignores_target_dead_description_for_a_different_death():
    quest = make_quest(
        status="in_progress", description="The starting pitch.",
        target_kill_entity_id="warden", questgiver_entity_id="escaped_prisoner",
        target_dead_description="It's done - go tell them.",
    )
    assert quest.current_description([], {"rat"}, set(), set()) == "The starting pitch."


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
    assert quest.current_description([], {"warden"}, set(), set()) == "The starting pitch."


def test_current_description_completed_takes_priority_over_target_dead_description():
    quest = make_quest(
        status="completed", description="The starting pitch.",
        target_kill_entity_id="warden", questgiver_entity_id="escaped_prisoner",
        target_dead_description="It's done - go tell them.",
        completed_description="All done.",
    )
    assert quest.current_description([], {"warden"}, set(), set()) == "All done."


def test_current_description_uses_target_visited_description_when_recorded_visited():
    quest = make_quest(
        status="in_progress", description="The starting pitch.",
        target_dungeon_id="millhaven", questgiver_entity_id="wayford_caravan_master",
        target_visited_description="You've been - go tell them.",
    )
    assert quest.current_description([], set(), {"millhaven"}, set()) == "You've been - go tell them."


def test_current_description_ignores_target_visited_description_before_the_visit():
    quest = make_quest(
        status="in_progress", description="The starting pitch.",
        target_dungeon_id="millhaven", questgiver_entity_id="wayford_caravan_master",
        target_visited_description="You've been - go tell them.",
    )
    assert quest.current_description([], set(), set(), set()) == "The starting pitch."


def test_current_description_ignores_target_visited_description_for_a_different_dungeon():
    quest = make_quest(
        status="in_progress", description="The starting pitch.",
        target_dungeon_id="millhaven", questgiver_entity_id="wayford_caravan_master",
        target_visited_description="You've been - go tell them.",
    )
    assert quest.current_description([], set(), {"forgotten_ruins"}, set()) == "The starting pitch."


def test_current_description_ignores_target_visited_description_for_a_non_dungeon_quest():
    """A Talk/fetch/kill quest has no target_dungeon_id, so
    target_visited_description (even if somehow set) never applies - matches
    content/schema.py's own validator rejecting that combination at
    content-load time; this just confirms the runtime side agrees."""
    quest = make_quest(
        status="in_progress", description="The starting pitch.",
        target_entity_id="village_chief", target_dungeon_id=None,
        target_visited_description="Should never show.",
    )
    assert quest.current_description([], set(), {"millhaven"}, set()) == "The starting pitch."


def test_current_description_completed_takes_priority_over_target_visited_description():
    quest = make_quest(
        status="completed", description="The starting pitch.",
        target_dungeon_id="millhaven", questgiver_entity_id="wayford_caravan_master",
        target_visited_description="You've been - go tell them.",
        completed_description="All done.",
    )
    assert quest.current_description([], set(), {"millhaven"}, set()) == "All done."


def test_current_description_uses_target_intimidated_description_when_recorded_intimidated():
    quest = make_quest(
        status="in_progress", description="The starting pitch.",
        target_dungeon_id=None,
        target_intimidate_entity_id="millhaven_debtor", questgiver_entity_id="wayford_provisioner",
        target_intimidated_description="Done, not yet reported - go tell them.",
    )
    assert (
        quest.current_description([], set(), set(), {"millhaven_debtor"})
        == "Done, not yet reported - go tell them."
    )


def test_current_description_ignores_target_intimidated_description_before_the_hit():
    quest = make_quest(
        status="in_progress", description="The starting pitch.",
        target_dungeon_id=None,
        target_intimidate_entity_id="millhaven_debtor", questgiver_entity_id="wayford_provisioner",
        target_intimidated_description="Done, not yet reported - go tell them.",
    )
    assert quest.current_description([], set(), set(), set()) == "The starting pitch."


def test_current_description_ignores_target_intimidated_description_for_a_different_target():
    quest = make_quest(
        status="in_progress", description="The starting pitch.",
        target_dungeon_id=None,
        target_intimidate_entity_id="millhaven_debtor", questgiver_entity_id="wayford_provisioner",
        target_intimidated_description="Done, not yet reported - go tell them.",
    )
    assert quest.current_description([], set(), set(), {"villager"}) == "The starting pitch."


def test_current_description_ignores_target_intimidated_description_for_a_non_intimidate_quest():
    """A Talk/fetch/kill/dungeon quest has no target_intimidate_entity_id, so
    target_intimidated_description (even if somehow set) never applies -
    matches content/schema.py's own validator rejecting that combination at
    content-load time; this just confirms the runtime side agrees."""
    quest = make_quest(
        status="in_progress", description="The starting pitch.",
        target_entity_id="village_chief", target_dungeon_id=None, target_intimidate_entity_id=None,
        target_intimidated_description="Should never show.",
    )
    assert quest.current_description([], set(), set(), {"millhaven_debtor"}) == "The starting pitch."


def test_current_description_completed_takes_priority_over_target_intimidated_description():
    quest = make_quest(
        status="completed", description="The starting pitch.",
        target_dungeon_id=None,
        target_intimidate_entity_id="millhaven_debtor", questgiver_entity_id="wayford_provisioner",
        target_intimidated_description="Done, not yet reported - go tell them.",
        completed_description="All done.",
    )
    assert quest.current_description([], set(), set(), {"millhaven_debtor"}) == "All done."


# --- check_questgiver: available_after_year/day ---


def test_check_questgiver_withholds_a_quest_not_yet_available():
    quest = make_quest(
        status="not_given", target_dungeon_id=None, target_entity_id="village_chief",
        questgiver_entity_id="village_chief",
        available_after_year=87, available_after_day=67,
    )
    log = QuestLog(quests={quest.id: quest})
    clock = GameClock(year=87, day=66)  # one day short

    changed = log.check_questgiver("village_chief", clock)

    assert changed == []
    assert quest.status == "not_given"


def test_check_questgiver_grants_a_quest_exactly_on_its_available_after_day():
    quest = make_quest(
        status="not_given", target_dungeon_id=None, target_entity_id="village_chief",
        questgiver_entity_id="village_chief",
        available_after_year=87, available_after_day=67,
    )
    log = QuestLog(quests={quest.id: quest})
    clock = GameClock(year=87, day=67)

    changed = log.check_questgiver("village_chief", clock)

    assert changed == [quest]
    assert quest.status == "in_progress"


def test_check_questgiver_grants_a_quest_well_past_its_available_after_day():
    quest = make_quest(
        status="not_given", target_dungeon_id=None, target_entity_id="village_chief",
        questgiver_entity_id="village_chief",
        available_after_year=87, available_after_day=67,
    )
    log = QuestLog(quests={quest.id: quest})
    clock = GameClock(year=87, day=200)

    changed = log.check_questgiver("village_chief", clock)

    assert changed == [quest]
    assert quest.status == "in_progress"


def test_check_questgiver_ignores_available_after_when_unset():
    """No available_after_year set at all - grantable immediately, same as
    every quest before this feature existed."""
    quest = make_quest(
        status="not_given", target_dungeon_id=None, target_entity_id="village_chief",
        questgiver_entity_id="village_chief",
    )
    log = QuestLog(quests={quest.id: quest})
    clock = GameClock(year=1, day=1)  # long before the game even starts

    changed = log.check_questgiver("village_chief", clock)

    assert changed == [quest]


def test_check_questgiver_jumps_straight_to_completed_if_cull_target_already_cleared():
    quest = make_quest(
        status="not_given", target_dungeon_id=None,
        questgiver_entity_id="grey_valley_elder", target_cull_entity_id="goblin",
    )
    log = QuestLog(quests={quest.id: quest}, cleared_species_ids={"goblin"})

    changed = log.check_questgiver("grey_valley_elder", GameClock())

    assert changed == [quest]
    assert quest.status == "completed"


# --- fail_cull_by_preservation_loss ---


def test_fail_cull_by_preservation_loss_does_not_fail_under_tolerance():
    quest = make_quest(
        target_dungeon_id=None, target_cull_entity_id="goblin",
        target_preserve_entity_id="cave_spider", target_preserve_tolerance=5,
        status="in_progress",
    )
    log = QuestLog(quests={quest.id: quest}, entity_kill_counts={"cave_spider": 5})

    changed = log.fail_cull_by_preservation_loss("cave_spider")

    assert changed == []
    assert quest.status == "in_progress"


def test_fail_cull_by_preservation_loss_fails_the_instant_tolerance_is_exceeded():
    quest = make_quest(
        target_dungeon_id=None, target_cull_entity_id="goblin",
        target_preserve_entity_id="cave_spider", target_preserve_tolerance=5,
        status="in_progress",
    )
    log = QuestLog(quests={quest.id: quest}, entity_kill_counts={"cave_spider": 6})

    changed = log.fail_cull_by_preservation_loss("cave_spider")

    assert changed == [(quest, True)]
    assert quest.status == "failed"


def test_fail_cull_by_preservation_loss_zero_tolerance_fails_on_the_first_death():
    quest = make_quest(
        target_dungeon_id=None, target_cull_entity_id="goblin",
        target_preserve_entity_id="cave_spider", status="in_progress",  # tolerance defaults 0
    )
    log = QuestLog(quests={quest.id: quest}, entity_kill_counts={"cave_spider": 1})

    changed = log.fail_cull_by_preservation_loss("cave_spider")

    assert changed == [(quest, True)]
    assert quest.status == "failed"


def test_fail_cull_by_preservation_loss_ignores_a_different_entitys_death():
    quest = make_quest(
        target_dungeon_id=None, target_cull_entity_id="goblin",
        target_preserve_entity_id="cave_spider", target_preserve_tolerance=0,
        status="in_progress",
    )
    log = QuestLog(quests={quest.id: quest}, entity_kill_counts={"rat": 10})

    changed = log.fail_cull_by_preservation_loss("rat")

    assert changed == []
    assert quest.status == "in_progress"


def test_fail_cull_by_preservation_loss_reports_not_given_quests_as_not_in_progress():
    quest = make_quest(
        target_dungeon_id=None, target_cull_entity_id="goblin",
        target_preserve_entity_id="cave_spider", target_preserve_tolerance=0,
        status="not_given",
    )
    log = QuestLog(quests={quest.id: quest}, entity_kill_counts={"cave_spider": 1})

    changed = log.fail_cull_by_preservation_loss("cave_spider")

    assert changed == [(quest, False)]
    assert quest.status == "failed"


def test_fail_cull_by_preservation_loss_leaves_a_completed_quest_untouched():
    quest = make_quest(
        target_dungeon_id=None, target_cull_entity_id="goblin",
        target_preserve_entity_id="cave_spider", target_preserve_tolerance=0,
        status="completed",
    )
    log = QuestLog(quests={quest.id: quest}, entity_kill_counts={"cave_spider": 1})

    changed = log.fail_cull_by_preservation_loss("cave_spider")

    assert changed == []
    assert quest.status == "completed"


# --- check_cull_report ---


def test_check_cull_report_completes_when_talking_to_questgiver_after_cleared():
    quest = make_quest(
        status="in_progress", target_dungeon_id=None,
        questgiver_entity_id="grey_valley_elder", target_cull_entity_id="goblin",
    )
    log = QuestLog(quests={quest.id: quest}, cleared_species_ids={"goblin"})

    changed = log.check_cull_report("grey_valley_elder")

    assert changed == [quest]
    assert quest.status == "completed"


def test_check_cull_report_is_a_no_op_before_cleared():
    quest = make_quest(
        status="in_progress", target_dungeon_id=None,
        questgiver_entity_id="grey_valley_elder", target_cull_entity_id="goblin",
    )
    log = QuestLog(quests={quest.id: quest})

    changed = log.check_cull_report("grey_valley_elder")

    assert changed == []
    assert quest.status == "in_progress"


def test_check_cull_report_is_a_no_op_when_talking_to_a_different_npc():
    quest = make_quest(
        status="in_progress", target_dungeon_id=None,
        questgiver_entity_id="grey_valley_elder", target_cull_entity_id="goblin",
    )
    log = QuestLog(quests={quest.id: quest}, cleared_species_ids={"goblin"})

    changed = log.check_cull_report("village_chief")

    assert changed == []
    assert quest.status == "in_progress"


def test_check_cull_report_does_not_refire_on_an_already_terminal_quest():
    quest = make_quest(
        status="completed", target_dungeon_id=None,
        questgiver_entity_id="grey_valley_elder", target_cull_entity_id="goblin",
    )
    log = QuestLog(quests={quest.id: quest}, cleared_species_ids={"goblin"})

    changed = log.check_cull_report("grey_valley_elder")

    assert changed == []


def test_check_cull_report_ignores_a_different_cleared_species():
    quest = make_quest(
        status="in_progress", target_dungeon_id=None,
        questgiver_entity_id="grey_valley_elder", target_cull_entity_id="goblin",
    )
    log = QuestLog(quests={quest.id: quest}, cleared_species_ids={"rat"})

    changed = log.check_cull_report("grey_valley_elder")

    assert changed == []
    assert quest.status == "in_progress"


# --- record_entity_killed: entity_kill_counts ---


def test_record_entity_killed_increments_entity_kill_counts():
    log = QuestLog()

    log.record_entity_killed("goblin")
    log.record_entity_killed("goblin")
    log.record_entity_killed("rat")

    assert log.entity_kill_counts == {"goblin": 2, "rat": 1}
    assert log.killed_entity_ids == {"goblin", "rat"}


# --- reset: cleared_species_ids/entity_kill_counts ---


def test_reset_clears_cleared_species_ids_and_entity_kill_counts():
    quest = make_quest(status="in_progress", target_dungeon_id=None)
    log = QuestLog(
        quests={quest.id: quest},
        cleared_species_ids={"goblin"},
        entity_kill_counts={"goblin": 12, "cave_spider": 2},
    )

    log.reset()

    assert log.cleared_species_ids == set()
    assert log.entity_kill_counts == {}


# --- current_description: target_cleared_description ---


def test_current_description_uses_target_cleared_description_when_recorded_cleared():
    quest = make_quest(
        status="in_progress", description="The starting pitch.",
        target_dungeon_id=None,
        target_cull_entity_id="goblin", questgiver_entity_id="grey_valley_elder",
        target_cleared_description="The goblins are gone - go tell them.",
    )
    assert (
        quest.current_description([], set(), set(), set(), {"goblin"})
        == "The goblins are gone - go tell them."
    )


def test_current_description_ignores_target_cleared_description_before_cleared():
    quest = make_quest(
        status="in_progress", description="The starting pitch.",
        target_dungeon_id=None,
        target_cull_entity_id="goblin", questgiver_entity_id="grey_valley_elder",
        target_cleared_description="The goblins are gone - go tell them.",
    )
    assert quest.current_description([], set(), set(), set()) == "The starting pitch."


def test_current_description_ignores_target_cleared_description_with_no_cleared_species_arg():
    """cleared_species_ids defaults to None (treated as empty) when the
    caller doesn't pass it - confirms that default doesn't crash and
    correctly falls back to the starting pitch."""
    quest = make_quest(
        status="in_progress", description="The starting pitch.",
        target_dungeon_id=None,
        target_cull_entity_id="goblin", questgiver_entity_id="grey_valley_elder",
        target_cleared_description="The goblins are gone - go tell them.",
    )
    assert quest.current_description([], set(), set(), set()) == "The starting pitch."


def test_current_description_completed_takes_priority_over_target_cleared_description():
    quest = make_quest(
        status="completed", description="The starting pitch.",
        target_dungeon_id=None,
        target_cull_entity_id="goblin", questgiver_entity_id="grey_valley_elder",
        target_cleared_description="The goblins are gone - go tell them.",
        completed_description="All done.",
    )
    assert quest.current_description([], set(), set(), set(), {"goblin"}) == "All done."
