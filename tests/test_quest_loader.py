from pathlib import Path

import pytest

from content.loader import ContentValidationError, load_catalog, load_quests
from engine.quest import create_quest_log

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
QUESTS_PATH = DATA_DIR / "quests.yaml"


def write_quests(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "quests.yaml"
    path.write_text(text, encoding="utf-8")
    return path


ALL_SHIPPED_QUEST_IDS = {
    "goblin_warning", "kill_the_warden", "fetch_fungus",
    "clearing_the_watch_road", "a_record_worth_keeping", "word_down_the_road",
}


def test_load_quests_loads_the_real_shipped_file():
    catalog = load_catalog()
    quests = load_quests(QUESTS_PATH, catalog, known_dungeon_ids={"millhaven"})

    assert set(quests) == ALL_SHIPPED_QUEST_IDS
    assert quests["goblin_warning"].starting_status == "in_progress"
    assert quests["kill_the_warden"].starting_status == "not_given"
    assert quests["fetch_fungus"].reward_shop_discount_pct == 0.2


def test_load_quests_end_to_end_matches_pre_refactor_values():
    """Regression net for the move from hardcoded Quest instances to
    data/quests.yaml: pins the same field values the old
    create_starting_quest_log() hardcoded, now loaded through the full
    load_quests -> create_quest_log pipeline against the real file."""
    catalog = load_catalog()
    quests = load_quests(QUESTS_PATH, catalog, known_dungeon_ids={"millhaven"})
    log = create_quest_log(quests)

    assert set(log.quests) == ALL_SHIPPED_QUEST_IDS
    assert log.active_quest_id == "goblin_warning"

    goblin_warning = log.quests["goblin_warning"]
    assert goblin_warning.status == "in_progress"
    assert goblin_warning.deadline_year == 87
    assert goblin_warning.deadline_day == 57
    assert goblin_warning.target_entity_id == "village_chief"

    kill_the_warden = log.quests["kill_the_warden"]
    assert kill_the_warden.status == "not_given"
    assert kill_the_warden.questgiver_entity_id == "escaped_prisoner"
    assert kill_the_warden.target_kill_entity_id == "warden"
    assert kill_the_warden.reward_item_id == "healing_potion"

    fetch_fungus = log.quests["fetch_fungus"]
    assert fetch_fungus.status == "not_given"
    assert fetch_fungus.questgiver_entity_id == "shopkeeper"
    assert fetch_fungus.target_item_id == "pale_fungus"
    assert fetch_fungus.reward_shop_discount_pct == 0.2

    clearing_the_watch_road = log.quests["clearing_the_watch_road"]
    assert clearing_the_watch_road.status == "not_given"
    assert clearing_the_watch_road.questgiver_entity_id == "wayford_road_warden"
    assert clearing_the_watch_road.target_kill_entity_id == "bandit_captain"
    assert clearing_the_watch_road.reward_item_id == "bone_plate"

    a_record_worth_keeping = log.quests["a_record_worth_keeping"]
    assert a_record_worth_keeping.status == "not_given"
    assert a_record_worth_keeping.questgiver_entity_id == "wayford_clerk"
    assert a_record_worth_keeping.target_item_id == "road_ledger"
    assert a_record_worth_keeping.reward_gold_amount == 30

    word_down_the_road = log.quests["word_down_the_road"]
    assert word_down_the_road.status == "not_given"
    assert word_down_the_road.questgiver_entity_id == "wayford_caravan_master"
    assert word_down_the_road.target_dungeon_id == "millhaven"
    assert word_down_the_road.reward_item_id is None


def test_load_quests_rejects_unknown_questgiver_entity(tmp_path):
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  questgiver_entity_id: nonexistent_npc\n"
        "  starting_status: in_progress\n",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="questgiver_entity_id"):
        load_quests(path, catalog)


def test_load_quests_rejects_unknown_target_item(tmp_path):
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  questgiver_entity_id: shopkeeper\n"
        "  target_item_id: nonexistent_item\n",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="target_item_id"):
        load_quests(path, catalog)


def test_load_quests_rejects_unknown_reward_item(tmp_path):
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  questgiver_entity_id: shopkeeper\n"
        "  reward_item_id: nonexistent_item\n"
        "  starting_status: in_progress\n",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="reward_item_id"):
        load_quests(path, catalog)


def test_load_quests_rejects_unknown_target_dungeon(tmp_path):
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  target_dungeon_id: nonexistent_dungeon\n"
        "  starting_status: in_progress\n",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="target_dungeon_id"):
        load_quests(path, catalog, known_dungeon_ids={"millhaven"})


def test_load_quests_skips_dungeon_check_when_known_dungeon_ids_is_none(tmp_path):
    path = write_quests(
        tmp_path,
        "quest_one:\n"
        "  name: Quest One\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  questgiver_entity_id: shopkeeper\n"
        "  target_dungeon_id: anything_at_all\n"
        "  starting_status: in_progress\n",
    )
    catalog = load_catalog()

    quests = load_quests(path, catalog)  # known_dungeon_ids defaults to None

    assert quests["quest_one"].target_dungeon_id == "anything_at_all"


def test_load_quests_rejects_two_trigger_fields_set_at_once(tmp_path):
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  target_entity_id: village_chief\n"
        "  target_kill_entity_id: warden\n"
        "  starting_status: in_progress\n",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="at most one"):
        load_quests(path, catalog)


def test_load_quests_rejects_one_deadline_field_without_the_other(tmp_path):
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  deadline_year: 87\n"
        "  target_entity_id: village_chief\n"
        "  starting_status: in_progress\n",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="deadline_year and deadline_day"):
        load_quests(path, catalog)


def test_load_quests_rejects_a_fetch_quest_with_no_questgiver(tmp_path):
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  target_item_id: pale_fungus\n"
        "  starting_status: in_progress\n",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="requires questgiver_entity_id"):
        load_quests(path, catalog)


def test_load_quests_rejects_a_kill_quest_with_no_questgiver(tmp_path):
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  target_kill_entity_id: warden\n"
        "  starting_status: in_progress\n",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="requires questgiver_entity_id"):
        load_quests(path, catalog)


def test_load_quests_rejects_a_dungeon_arrival_quest_with_no_questgiver(tmp_path):
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  target_dungeon_id: millhaven\n"
        "  starting_status: in_progress\n",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="requires questgiver_entity_id"):
        load_quests(path, catalog, known_dungeon_ids={"millhaven"})


def test_load_quests_rejects_a_not_given_quest_with_no_questgiver(tmp_path):
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  target_entity_id: village_chief\n",
        # starting_status defaults to "not_given", no questgiver_entity_id set
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="could never start"):
        load_quests(path, catalog)


def test_load_quests_allows_a_not_given_quest_with_a_questgiver(tmp_path):
    path = write_quests(
        tmp_path,
        "fine_quest:\n"
        "  name: Fine Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  questgiver_entity_id: shopkeeper\n"
        "  target_entity_id: village_chief\n",
    )
    catalog = load_catalog()

    quests = load_quests(path, catalog)

    assert quests["fine_quest"].starting_status == "not_given"


def test_load_quests_rejects_target_dead_description_without_a_kill_target(tmp_path):
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  target_entity_id: village_chief\n"
        "  target_dead_description: It's dead.\n"
        "  starting_status: in_progress\n",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="target_dead_description"):
        load_quests(path, catalog)


def test_load_quests_rejects_target_visited_description_without_a_dungeon_target(tmp_path):
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  target_entity_id: village_chief\n"
        "  target_visited_description: You've been.\n"
        "  starting_status: in_progress\n",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="target_visited_description"):
        load_quests(path, catalog)


def test_load_quests_rejects_carrying_item_description_without_a_fetch_target(tmp_path):
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  target_entity_id: village_chief\n"
        "  carrying_item_description: You have it.\n"
        "  starting_status: in_progress\n",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="carrying_item_description"):
        load_quests(path, catalog)


def test_load_quests_rejects_failed_description_without_a_deadline(tmp_path):
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  target_entity_id: village_chief\n"
        "  failed_description: Too late.\n"
        "  starting_status: in_progress\n",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="failed_description"):
        load_quests(path, catalog)


def test_load_quests_allows_the_full_set_of_description_overrides(tmp_path):
    path = write_quests(
        tmp_path,
        "fetch_quest:\n"
        "  name: Fetch Quest\n"
        "  description: The pitch.\n"
        "  completion_message: Got it.\n"
        "  questgiver_entity_id: shopkeeper\n"
        "  target_item_id: pale_fungus\n"
        "  carrying_item_description: You have it now.\n"
        "  completed_description: All done.\n"
        "deadline_quest:\n"
        "  name: Deadline Quest\n"
        "  description: The pitch.\n"
        "  completion_message: Got it.\n"
        "  target_entity_id: village_chief\n"
        "  deadline_year: 87\n"
        "  deadline_day: 60\n"
        "  completed_description: All done.\n"
        "  failed_description: Too late.\n"
        "  starting_status: in_progress\n",
    )
    catalog = load_catalog()

    quests = load_quests(path, catalog)

    assert quests["fetch_quest"].carrying_item_description == "You have it now."
    assert quests["fetch_quest"].completed_description == "All done."
    assert quests["deadline_quest"].failed_description == "Too late."


def test_load_quests_real_shipped_quests_have_the_new_description_overrides():
    catalog = load_catalog()
    quests = load_quests(QUESTS_PATH, catalog, known_dungeon_ids={"millhaven"})

    assert quests["goblin_warning"].completed_description
    assert quests["goblin_warning"].failed_description
    assert quests["kill_the_warden"].target_dead_description
    assert quests["kill_the_warden"].completed_description
    assert quests["fetch_fungus"].carrying_item_description
    assert quests["fetch_fungus"].completed_description
    assert "20%" in quests["fetch_fungus"].completed_description
    assert quests["clearing_the_watch_road"].target_dead_description
    assert quests["clearing_the_watch_road"].completed_description
    assert quests["word_down_the_road"].target_visited_description
    assert quests["word_down_the_road"].completed_description


class _FakeInventoryItem:
    def __init__(self, entity_id: str):
        self.entity_id = entity_id


def test_fetch_fungus_current_description_progresses_through_every_real_stage():
    """End-to-end regression net for the quest log description feature,
    against the real shipped fetch_fungus quest: starting pitch -> carrying
    the item -> completed, each stage a genuinely different string."""
    catalog = load_catalog()
    quests = load_quests(QUESTS_PATH, catalog, known_dungeon_ids={"millhaven"})
    log = create_quest_log(quests)
    quest = log.quests["fetch_fungus"]

    starting = quest.current_description([], set(), set())
    assert starting == quest.description

    quest.status = "in_progress"
    carrying = quest.current_description([_FakeInventoryItem("pale_fungus")], set(), set())
    assert carrying == quest.carrying_item_description
    assert carrying != starting

    quest.status = "completed"
    completed = quest.current_description([], set(), set())
    assert completed == quest.completed_description
    assert completed not in (starting, carrying)


def test_kill_the_warden_current_description_progresses_through_every_real_stage():
    """Same end-to-end regression net as the fetch_fungus test above, for
    the kill-then-report shape: starting pitch -> target recorded dead ->
    completed, each stage a genuinely different string."""
    catalog = load_catalog()
    quests = load_quests(QUESTS_PATH, catalog, known_dungeon_ids={"millhaven"})
    log = create_quest_log(quests)
    quest = log.quests["kill_the_warden"]

    starting = quest.current_description([], set(), set())
    assert starting == quest.description

    quest.status = "in_progress"
    dead = quest.current_description([], {"warden"}, set())
    assert dead == quest.target_dead_description
    assert dead != starting

    quest.status = "completed"
    completed = quest.current_description([], {"warden"}, set())
    assert completed == quest.completed_description
    assert completed not in (starting, dead)


def test_word_down_the_road_current_description_progresses_through_every_real_stage():
    """Same end-to-end regression net again, for the dungeon-arrival ->
    report shape: starting pitch -> Millhaven recorded visited -> completed,
    each stage a genuinely different string."""
    catalog = load_catalog()
    quests = load_quests(QUESTS_PATH, catalog, known_dungeon_ids={"millhaven"})
    log = create_quest_log(quests)
    quest = log.quests["word_down_the_road"]

    starting = quest.current_description([], set(), set())
    assert starting == quest.description

    quest.status = "in_progress"
    visited = quest.current_description([], set(), {"millhaven"})
    assert visited == quest.target_visited_description
    assert visited != starting

    quest.status = "completed"
    completed = quest.current_description([], set(), {"millhaven"})
    assert completed == quest.completed_description
    assert completed not in (starting, visited)
