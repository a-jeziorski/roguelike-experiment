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
    "spreading_the_warning", "a_wall_worth_holding", "what_the_tide_kept",
    "a_debt_worth_collecting", "the_uninvited_tribe", "reclaiming_the_windrest",
    "clearing_the_sunless_hollow",
}


def test_load_quests_loads_the_real_shipped_file():
    catalog = load_catalog()
    quests = load_quests(QUESTS_PATH, catalog, known_dungeon_ids={"millhaven", "wayford"})

    assert set(quests) == ALL_SHIPPED_QUEST_IDS
    assert quests["goblin_warning"].starting_status == "in_progress"
    assert quests["kill_the_warden"].starting_status == "not_given"
    assert quests["fetch_fungus"].reward_shop_discount_pct == 0.2
    assert quests["fetch_fungus"].reward_shop_discount_entity_id == "shopkeeper"
    assert quests["a_debt_worth_collecting"].questgiver_entity_id == "wayford_provisioner"
    assert quests["a_debt_worth_collecting"].target_intimidate_entity_id == "millhaven_debtor"


def test_real_shipped_content_spreading_the_warning_tightens_a_wall_worth_holding():
    catalog = load_catalog()
    quests = load_quests(QUESTS_PATH, catalog, known_dungeon_ids={"millhaven", "wayford"})

    tighten = next(
        c.tighten_deadline for c in quests["spreading_the_warning"].on_fail
        if c.tighten_deadline is not None
    )
    assert tighten.quest_id == "a_wall_worth_holding"
    assert tighten.new_day == 66


def test_load_quests_end_to_end_matches_pre_refactor_values():
    """Regression net for the move from hardcoded Quest instances to
    data/quests.yaml: pins the same field values the old
    create_starting_quest_log() hardcoded, now loaded through the full
    load_quests -> create_quest_log pipeline against the real file."""
    catalog = load_catalog()
    quests = load_quests(QUESTS_PATH, catalog, known_dungeon_ids={"millhaven", "wayford"})
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
    assert fetch_fungus.reward_shop_discount_entity_id == "shopkeeper"

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

    spreading_the_warning = log.quests["spreading_the_warning"]
    assert spreading_the_warning.status == "not_given"
    assert spreading_the_warning.questgiver_entity_id == "village_chief"
    assert spreading_the_warning.requires_quest_id == "goblin_warning"
    assert spreading_the_warning.target_entity_id == "wayford_road_warden"


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


def test_load_quests_rejects_a_shop_discount_pct_without_an_entity_id(tmp_path):
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  questgiver_entity_id: shopkeeper\n"
        "  target_item_id: pale_fungus\n"
        "  reward_shop_discount_pct: 0.2\n",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="reward_shop_discount_pct and reward_shop_discount_entity_id"):
        load_quests(path, catalog)


def test_load_quests_rejects_a_shop_discount_entity_id_without_a_pct(tmp_path):
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  questgiver_entity_id: shopkeeper\n"
        "  target_item_id: pale_fungus\n"
        "  reward_shop_discount_entity_id: shopkeeper\n",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="reward_shop_discount_pct and reward_shop_discount_entity_id"):
        load_quests(path, catalog)


def test_load_quests_rejects_an_unknown_shop_discount_entity(tmp_path):
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  questgiver_entity_id: shopkeeper\n"
        "  target_item_id: pale_fungus\n"
        "  reward_shop_discount_pct: 0.2\n"
        "  reward_shop_discount_entity_id: nonexistent_npc\n",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="reward_shop_discount_entity_id"):
        load_quests(path, catalog)


def test_load_quests_rejects_a_shop_discount_entity_with_no_shop_inventory(tmp_path):
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  questgiver_entity_id: shopkeeper\n"
        "  target_item_id: pale_fungus\n"
        "  reward_shop_discount_pct: 0.2\n"
        "  reward_shop_discount_entity_id: village_chief\n",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="no shop_inventory"):
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


def test_load_quests_rejects_unknown_target_intimidate_entity(tmp_path):
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  questgiver_entity_id: shopkeeper\n"
        "  target_intimidate_entity_id: nonexistent_npc\n"
        "  starting_status: in_progress\n",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="target_intimidate_entity_id"):
        load_quests(path, catalog)


def test_load_quests_rejects_a_hostile_target_intimidate_entity(tmp_path):
    """engine/combat.py's _apply_damage only ever records an intimidation
    against a peaceful defender - a quest targeting a hostile catalog
    entity (e.g. the warden, ai: hostile_basic) could never complete, so
    load_quests catches it at content-load time instead."""
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  questgiver_entity_id: shopkeeper\n"
        "  target_intimidate_entity_id: warden\n"
        "  starting_status: in_progress\n",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="isn't a peaceful entity"):
        load_quests(path, catalog)


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


def test_load_quests_rejects_unknown_on_fail_destroy_dungeon_id(tmp_path):
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  starting_status: in_progress\n"
        "  deadline_year: 87\n"
        "  deadline_day: 60\n"
        "  on_fail:\n"
        "    - destroy_dungeon_id: nonexistent_dungeon\n",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="on_fail destroy_dungeon_id"):
        load_quests(path, catalog, known_dungeon_ids={"millhaven"})


def test_load_quests_rejects_unknown_voided_by_dungeon_id(tmp_path):
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  starting_status: in_progress\n"
        "  voided_by_dungeon_id: nonexistent_dungeon\n",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="voided_by_dungeon_id"):
        load_quests(path, catalog, known_dungeon_ids={"millhaven"})


def test_load_quests_rejects_on_fail_with_no_deadline(tmp_path):
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  starting_status: in_progress\n"
        "  on_fail:\n"
        "    - destroy_dungeon_id: millhaven\n",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="there's no deadline"):
        load_quests(path, catalog, known_dungeon_ids={"millhaven"})


def test_load_quests_rejects_on_fail_set_flag_with_no_deadline(tmp_path):
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  starting_status: in_progress\n"
        "  on_fail:\n"
        "    - set_flag: some_flag\n",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="there's no deadline"):
        load_quests(path, catalog, known_dungeon_ids={"millhaven"})


def test_load_quests_rejects_an_on_fail_tighten_deadline_referencing_itself(tmp_path):
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  starting_status: in_progress\n"
        "  deadline_year: 87\n"
        "  deadline_day: 60\n"
        "  on_fail:\n"
        "    - tighten_deadline: { quest_id: bad_quest, new_day: 55 }\n",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="on_fail tighten_deadline can't target itself"):
        load_quests(path, catalog)


def test_load_quests_rejects_an_unknown_on_fail_tighten_deadline_quest_id(tmp_path):
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  starting_status: in_progress\n"
        "  deadline_year: 87\n"
        "  deadline_day: 60\n"
        "  on_fail:\n"
        "    - tighten_deadline: { quest_id: nonexistent_quest, new_day: 55 }\n",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="on_fail tighten_deadline references unknown quest"):
        load_quests(path, catalog)


def test_load_quests_rejects_an_on_fail_tighten_deadline_targeting_a_quest_with_no_deadline(tmp_path):
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  starting_status: in_progress\n"
        "  deadline_year: 87\n"
        "  deadline_day: 60\n"
        "  on_fail:\n"
        "    - tighten_deadline: { quest_id: no_deadline_quest, new_day: 55 }\n"
        "no_deadline_quest:\n"
        "  name: No Deadline Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  target_entity_id: village_chief\n"
        "  starting_status: in_progress\n",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="has no deadline_year set"):
        load_quests(path, catalog)


def test_load_quests_allows_an_on_fail_tighten_deadline_referencing_a_quest_defined_later(tmp_path):
    """Mirrors requires_quest_id's own forward-reference test - tighten_deadline
    is checked against the whole raw YAML dict too, so file order between the
    two quests doesn't matter."""
    path = write_quests(
        tmp_path,
        "first_quest:\n"
        "  name: First Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  starting_status: in_progress\n"
        "  deadline_year: 87\n"
        "  deadline_day: 60\n"
        "  on_fail:\n"
        "    - tighten_deadline: { quest_id: second_quest, new_day: 66 }\n"
        "second_quest:\n"
        "  name: Second Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  target_entity_id: village_chief\n"
        "  starting_status: in_progress\n"
        "  deadline_year: 87\n"
        "  deadline_day: 70\n",
    )
    catalog = load_catalog()

    quests = load_quests(path, catalog)

    assert quests["first_quest"].on_fail[0].tighten_deadline.quest_id == "second_quest"
    assert quests["first_quest"].on_fail[0].tighten_deadline.new_day == 66


def test_load_quests_allows_a_valid_on_fail_tighten_deadline(tmp_path):
    path = write_quests(
        tmp_path,
        "second_quest:\n"
        "  name: Second Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  target_entity_id: village_chief\n"
        "  starting_status: in_progress\n"
        "  deadline_year: 87\n"
        "  deadline_day: 70\n"
        "first_quest:\n"
        "  name: First Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  starting_status: in_progress\n"
        "  deadline_year: 87\n"
        "  deadline_day: 60\n"
        "  on_fail:\n"
        "    - tighten_deadline: { quest_id: second_quest, new_day: 66 }\n",
    )
    catalog = load_catalog()

    quests = load_quests(path, catalog)

    tighten = quests["first_quest"].on_fail[0].tighten_deadline
    assert tighten.quest_id == "second_quest"
    assert tighten.new_day == 66


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


def test_load_quests_rejects_intimidate_and_another_trigger_set_at_once(tmp_path):
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  questgiver_entity_id: shopkeeper\n"
        "  target_intimidate_entity_id: millhaven_debtor\n"
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


def test_load_quests_rejects_an_intimidate_quest_with_no_questgiver(tmp_path):
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  target_intimidate_entity_id: millhaven_debtor\n"
        "  starting_status: in_progress\n",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="requires questgiver_entity_id"):
        load_quests(path, catalog)


def test_load_quests_rejects_requires_quest_id_without_a_questgiver(tmp_path):
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  target_entity_id: village_chief\n"
        "  requires_quest_id: goblin_warning\n"
        "  starting_status: in_progress\n",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="requires_quest_id is set but questgiver_entity_id isn't"):
        load_quests(path, catalog)


def test_load_quests_rejects_an_unknown_requires_quest_id(tmp_path):
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  questgiver_entity_id: shopkeeper\n"
        "  target_entity_id: village_chief\n"
        "  requires_quest_id: nonexistent_quest\n"
        "  starting_status: in_progress\n",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="requires_quest_id references unknown quest"):
        load_quests(path, catalog)


def test_load_quests_rejects_a_requires_quest_id_referencing_itself(tmp_path):
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  questgiver_entity_id: shopkeeper\n"
        "  target_entity_id: village_chief\n"
        "  requires_quest_id: bad_quest\n"
        "  starting_status: in_progress\n",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="requires_quest_id can't reference itself"):
        load_quests(path, catalog)


def test_load_quests_allows_a_requires_quest_id_referencing_a_quest_defined_later(tmp_path):
    """requires_quest_id is checked against the whole raw YAML dict, already
    fully parsed before the per-quest loop starts - so, unlike a two-pass
    cross-file check, file order between the two quests doesn't matter."""
    path = write_quests(
        tmp_path,
        "second_quest:\n"
        "  name: Second Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  questgiver_entity_id: shopkeeper\n"
        "  target_entity_id: escaped_prisoner\n"
        "  requires_quest_id: first_quest\n"
        "first_quest:\n"
        "  name: First Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  target_entity_id: village_chief\n"
        "  starting_status: in_progress\n",
    )
    catalog = load_catalog()

    quests = load_quests(path, catalog)

    assert quests["second_quest"].requires_quest_id == "first_quest"


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


def test_load_quests_rejects_target_intimidated_description_without_an_intimidate_target(tmp_path):
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  target_entity_id: village_chief\n"
        "  target_intimidated_description: They're rattled.\n"
        "  starting_status: in_progress\n",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="target_intimidated_description"):
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


def test_load_quests_accepts_failed_description_with_voided_by_dungeon_id_and_no_deadline(tmp_path):
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  target_entity_id: village_chief\n"
        "  failed_description: The town is gone.\n"
        "  voided_by_dungeon_id: millhaven\n"
        "  starting_status: in_progress\n",
    )
    catalog = load_catalog()

    quests = load_quests(path, catalog, known_dungeon_ids={"millhaven"})

    assert quests["bad_quest"].failed_description == "The town is gone."
    assert quests["bad_quest"].voided_by_dungeon_id == "millhaven"


def test_load_quests_accepts_failed_description_with_target_intimidate_entity_id_and_no_deadline(tmp_path):
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  questgiver_entity_id: shopkeeper\n"
        "  target_intimidate_entity_id: millhaven_debtor\n"
        "  failed_description: They're dead - so much for collecting.\n"
        "  starting_status: in_progress\n",
    )
    catalog = load_catalog()

    quests = load_quests(path, catalog)

    assert quests["bad_quest"].failed_description == "They're dead - so much for collecting."


# --- cull-while-preserving (target_cull_entity_id/target_preserve_entity_id) ---


def test_load_quests_accepts_a_valid_cull_and_preserve_quest(tmp_path):
    path = write_quests(
        tmp_path,
        "clear_the_goblins:\n"
        "  name: Clear the Goblins\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  questgiver_entity_id: shopkeeper\n"
        "  target_cull_entity_id: goblin\n"
        "  target_preserve_entity_id: cave_spider\n"
        "  target_preserve_tolerance: 5\n"
        "  target_cleared_description: The goblins are gone.\n"
        "  starting_status: in_progress\n",
    )
    catalog = load_catalog()

    quests = load_quests(path, catalog)

    assert quests["clear_the_goblins"].target_cull_entity_id == "goblin"
    assert quests["clear_the_goblins"].target_preserve_entity_id == "cave_spider"
    assert quests["clear_the_goblins"].target_preserve_tolerance == 5


def test_load_quests_rejects_unknown_target_cull_entity(tmp_path):
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  questgiver_entity_id: shopkeeper\n"
        "  target_cull_entity_id: nonexistent_monster\n"
        "  starting_status: in_progress\n",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="target_cull_entity_id"):
        load_quests(path, catalog)


def test_load_quests_rejects_unknown_target_preserve_entity(tmp_path):
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  questgiver_entity_id: shopkeeper\n"
        "  target_cull_entity_id: goblin\n"
        "  target_preserve_entity_id: nonexistent_critter\n"
        "  starting_status: in_progress\n",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="target_preserve_entity_id"):
        load_quests(path, catalog)


def test_load_quests_rejects_cull_and_another_trigger_set_at_once(tmp_path):
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  questgiver_entity_id: shopkeeper\n"
        "  target_cull_entity_id: goblin\n"
        "  target_kill_entity_id: warden\n"
        "  starting_status: in_progress\n",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="at most one"):
        load_quests(path, catalog)


def test_load_quests_rejects_a_cull_quest_with_no_questgiver(tmp_path):
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  target_cull_entity_id: goblin\n"
        "  starting_status: in_progress\n",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="requires questgiver_entity_id"):
        load_quests(path, catalog)


def test_load_quests_rejects_preserve_target_without_a_cull_target(tmp_path):
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  questgiver_entity_id: shopkeeper\n"
        "  target_preserve_entity_id: cave_spider\n"
        "  starting_status: in_progress\n",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="target_preserve_entity_id is set but target_cull_entity_id"):
        load_quests(path, catalog)


def test_load_quests_rejects_preserve_target_equal_to_cull_target(tmp_path):
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  questgiver_entity_id: shopkeeper\n"
        "  target_cull_entity_id: goblin\n"
        "  target_preserve_entity_id: goblin\n"
        "  starting_status: in_progress\n",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="same as target_cull_entity_id"):
        load_quests(path, catalog)


def test_load_quests_rejects_target_cleared_description_without_a_cull_target(tmp_path):
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  target_entity_id: village_chief\n"
        "  target_cleared_description: They're gone.\n"
        "  starting_status: in_progress\n",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="target_cleared_description"):
        load_quests(path, catalog)


def test_load_quests_accepts_failed_description_with_target_cull_entity_id_and_no_deadline(tmp_path):
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  questgiver_entity_id: shopkeeper\n"
        "  target_cull_entity_id: goblin\n"
        "  target_preserve_entity_id: cave_spider\n"
        "  failed_description: Too many spiders died.\n"
        "  starting_status: in_progress\n",
    )
    catalog = load_catalog()

    quests = load_quests(path, catalog)

    assert quests["bad_quest"].failed_description == "Too many spiders died."


# --- time-gated availability (available_after_year/day) ---


def test_load_quests_accepts_available_after_year_and_day_together(tmp_path):
    path = write_quests(
        tmp_path,
        "delayed_quest:\n"
        "  name: Delayed Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  questgiver_entity_id: shopkeeper\n"
        "  target_entity_id: village_chief\n"
        "  available_after_year: 87\n"
        "  available_after_day: 67\n"
        "  starting_status: not_given\n",
    )
    catalog = load_catalog()

    quests = load_quests(path, catalog)

    assert quests["delayed_quest"].available_after_year == 87
    assert quests["delayed_quest"].available_after_day == 67


def test_load_quests_rejects_available_after_year_without_day(tmp_path):
    path = write_quests(
        tmp_path,
        "bad_quest:\n"
        "  name: Bad Quest\n"
        "  description: x\n"
        "  completion_message: x\n"
        "  target_entity_id: village_chief\n"
        "  available_after_year: 87\n"
        "  starting_status: not_given\n",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="available_after_year and available_after_day"):
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
    quests = load_quests(QUESTS_PATH, catalog, known_dungeon_ids={"millhaven", "wayford"})

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
    assert quests["a_debt_worth_collecting"].target_intimidated_description
    assert quests["a_debt_worth_collecting"].completed_description
    assert quests["a_debt_worth_collecting"].failed_description


class _FakeInventoryItem:
    def __init__(self, entity_id: str):
        self.entity_id = entity_id


def test_fetch_fungus_current_description_progresses_through_every_real_stage():
    """End-to-end regression net for the quest log description feature,
    against the real shipped fetch_fungus quest: starting pitch -> carrying
    the item -> completed, each stage a genuinely different string."""
    catalog = load_catalog()
    quests = load_quests(QUESTS_PATH, catalog, known_dungeon_ids={"millhaven", "wayford"})
    log = create_quest_log(quests)
    quest = log.quests["fetch_fungus"]

    starting = quest.current_description([], set(), set(), set())
    assert starting == quest.description

    quest.status = "in_progress"
    carrying = quest.current_description([_FakeInventoryItem("pale_fungus")], set(), set(), set())
    assert carrying == quest.carrying_item_description
    assert carrying != starting

    quest.status = "completed"
    completed = quest.current_description([], set(), set(), set())
    assert completed == quest.completed_description
    assert completed not in (starting, carrying)


def test_kill_the_warden_current_description_progresses_through_every_real_stage():
    """Same end-to-end regression net as the fetch_fungus test above, for
    the kill-then-report shape: starting pitch -> target recorded dead ->
    completed, each stage a genuinely different string."""
    catalog = load_catalog()
    quests = load_quests(QUESTS_PATH, catalog, known_dungeon_ids={"millhaven", "wayford"})
    log = create_quest_log(quests)
    quest = log.quests["kill_the_warden"]

    starting = quest.current_description([], set(), set(), set())
    assert starting == quest.description

    quest.status = "in_progress"
    dead = quest.current_description([], {"warden"}, set(), set())
    assert dead == quest.target_dead_description
    assert dead != starting

    quest.status = "completed"
    completed = quest.current_description([], {"warden"}, set(), set())
    assert completed == quest.completed_description
    assert completed not in (starting, dead)


def test_word_down_the_road_current_description_progresses_through_every_real_stage():
    """Same end-to-end regression net again, for the dungeon-arrival ->
    report shape: starting pitch -> Millhaven recorded visited -> completed,
    each stage a genuinely different string."""
    catalog = load_catalog()
    quests = load_quests(QUESTS_PATH, catalog, known_dungeon_ids={"millhaven", "wayford"})
    log = create_quest_log(quests)
    quest = log.quests["word_down_the_road"]

    starting = quest.current_description([], set(), set(), set())
    assert starting == quest.description

    quest.status = "in_progress"
    visited = quest.current_description([], set(), {"millhaven"}, set())
    assert visited == quest.target_visited_description
    assert visited != starting

    quest.status = "completed"
    completed = quest.current_description([], set(), {"millhaven"}, set())
    assert completed == quest.completed_description
    assert completed not in (starting, visited)


def test_a_debt_worth_collecting_current_description_progresses_through_every_real_stage():
    """Same end-to-end regression net again, for the intimidate-then-report
    shape: starting pitch -> debtor recorded intimidated -> completed, each
    stage a genuinely different string."""
    catalog = load_catalog()
    quests = load_quests(QUESTS_PATH, catalog, known_dungeon_ids={"millhaven", "wayford"})
    log = create_quest_log(quests)
    quest = log.quests["a_debt_worth_collecting"]

    starting = quest.current_description([], set(), set(), set())
    assert starting == quest.description

    quest.status = "in_progress"
    intimidated = quest.current_description([], set(), set(), {"millhaven_debtor"})
    assert intimidated == quest.target_intimidated_description
    assert intimidated != starting

    quest.status = "completed"
    completed = quest.current_description([], set(), set(), {"millhaven_debtor"})
    assert completed == quest.completed_description
    assert completed not in (starting, intimidated)


def test_a_debt_worth_collecting_fails_immediately_if_the_debtor_is_killed_instead():
    """The intimidate shape's unique failure path: killing the target force-
    fails the quest right away (fail_intimidate_by_death), not on the next
    report - unlike every other trigger shape's fail conditions."""
    catalog = load_catalog()
    quests = load_quests(QUESTS_PATH, catalog, known_dungeon_ids={"millhaven", "wayford"})
    log = create_quest_log(quests)
    quest = log.quests["a_debt_worth_collecting"]
    quest.status = "in_progress"

    changed = log.fail_intimidate_by_death("millhaven_debtor")

    assert changed == [(quest, True)]
    assert quest.status == "failed"
