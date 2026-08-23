from pathlib import Path

import pytest

from content.loader import ContentValidationError, load_encounters

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ENCOUNTERS_PATH = DATA_DIR / "encounters.yaml"

KNOWN_DUNGEON_IDS = {"millhaven", "goblin_ambush"}
KNOWN_QUEST_IDS = {"spreading_the_warning"}


def write_encounters(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "encounters.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_load_encounters_loads_the_real_shipped_file():
    encounters = load_encounters(
        ENCOUNTERS_PATH, known_dungeon_ids={"millhaven", "goblin_ambush"},
        known_quest_ids={"spreading_the_warning"},
    )

    assert set(encounters) == {"warning_ambush"}
    warning_ambush = encounters["warning_ambush"]
    assert warning_ambush.trigger_dungeon_id == "millhaven"
    assert warning_ambush.gate_quest_id == "spreading_the_warning"
    assert warning_ambush.gate_quest_status == "in_progress"
    assert warning_ambush.encounter_dungeon_id == "goblin_ambush"
    assert warning_ambush.delay_hours == 3


def test_load_encounters_rejects_unknown_trigger_dungeon(tmp_path):
    path = write_encounters(
        tmp_path,
        "bad_encounter:\n"
        "  trigger_dungeon_id: nonexistent_dungeon\n"
        "  gate_quest_id: spreading_the_warning\n"
        "  encounter_dungeon_id: goblin_ambush\n",
    )

    with pytest.raises(ContentValidationError, match="trigger_dungeon_id references unknown dungeon"):
        load_encounters(path, KNOWN_DUNGEON_IDS, KNOWN_QUEST_IDS)


def test_load_encounters_rejects_unknown_encounter_dungeon(tmp_path):
    path = write_encounters(
        tmp_path,
        "bad_encounter:\n"
        "  trigger_dungeon_id: millhaven\n"
        "  gate_quest_id: spreading_the_warning\n"
        "  encounter_dungeon_id: nonexistent_dungeon\n",
    )

    with pytest.raises(ContentValidationError, match="encounter_dungeon_id references unknown dungeon"):
        load_encounters(path, KNOWN_DUNGEON_IDS, KNOWN_QUEST_IDS)


def test_load_encounters_rejects_unknown_gate_quest(tmp_path):
    path = write_encounters(
        tmp_path,
        "bad_encounter:\n"
        "  trigger_dungeon_id: millhaven\n"
        "  gate_quest_id: nonexistent_quest\n"
        "  encounter_dungeon_id: goblin_ambush\n",
    )

    with pytest.raises(ContentValidationError, match="gate_quest_id references unknown quest"):
        load_encounters(path, KNOWN_DUNGEON_IDS, KNOWN_QUEST_IDS)


def test_load_encounters_defaults_gate_quest_status_to_in_progress(tmp_path):
    path = write_encounters(
        tmp_path,
        "an_encounter:\n"
        "  trigger_dungeon_id: millhaven\n"
        "  gate_quest_id: spreading_the_warning\n"
        "  encounter_dungeon_id: goblin_ambush\n",
    )

    encounters = load_encounters(path, KNOWN_DUNGEON_IDS, KNOWN_QUEST_IDS)

    assert encounters["an_encounter"].gate_quest_status == "in_progress"


def test_load_encounters_allows_an_explicit_gate_quest_status(tmp_path):
    path = write_encounters(
        tmp_path,
        "an_encounter:\n"
        "  trigger_dungeon_id: millhaven\n"
        "  gate_quest_id: spreading_the_warning\n"
        "  gate_quest_status: completed\n"
        "  encounter_dungeon_id: goblin_ambush\n",
    )

    encounters = load_encounters(path, KNOWN_DUNGEON_IDS, KNOWN_QUEST_IDS)

    assert encounters["an_encounter"].gate_quest_status == "completed"


def test_load_encounters_defaults_delay_hours_to_3(tmp_path):
    path = write_encounters(
        tmp_path,
        "an_encounter:\n"
        "  trigger_dungeon_id: millhaven\n"
        "  gate_quest_id: spreading_the_warning\n"
        "  encounter_dungeon_id: goblin_ambush\n",
    )

    encounters = load_encounters(path, KNOWN_DUNGEON_IDS, KNOWN_QUEST_IDS)

    assert encounters["an_encounter"].delay_hours == 3


def test_load_encounters_allows_an_explicit_delay_hours(tmp_path):
    path = write_encounters(
        tmp_path,
        "an_encounter:\n"
        "  trigger_dungeon_id: millhaven\n"
        "  gate_quest_id: spreading_the_warning\n"
        "  encounter_dungeon_id: goblin_ambush\n"
        "  delay_hours: 10\n",
    )

    encounters = load_encounters(path, KNOWN_DUNGEON_IDS, KNOWN_QUEST_IDS)

    assert encounters["an_encounter"].delay_hours == 10
