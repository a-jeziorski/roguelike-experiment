from pathlib import Path

import pytest

from content.loader import (
    ContentValidationError,
    load_catalog,
    load_dungeon,
    load_dungeon_registry,
    load_level,
    load_levels,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DUNGEONS_DIR = DATA_DIR / "dungeons"
FORGOTTEN_RUINS_LEVELS_DIR = DUNGEONS_DIR / "forgotten_ruins" / "levels"
PRISON_TOWER_LEVELS_DIR = DUNGEONS_DIR / "prison_tower" / "levels"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_load_catalog_loads_real_data():
    catalog = load_catalog()
    assert "rat" in catalog.entities
    assert "goblin" in catalog.entities
    assert "healing_potion" in catalog.items
    assert "rusty_dagger" in catalog.items


@pytest.mark.parametrize(
    "level_file",
    sorted(FORGOTTEN_RUINS_LEVELS_DIR.glob("*.lvl")) + sorted(PRISON_TOWER_LEVELS_DIR.glob("*.lvl")),
)
def test_every_shipped_level_validates_cleanly(level_file):
    catalog = load_catalog()
    level = load_level(level_file, catalog)
    assert level.width > 0
    assert level.height > 0
    assert all(len(row) == level.width for row in level.tiles)


def test_level_01_content():
    catalog = load_catalog()
    level = load_level(FORGOTTEN_RUINS_LEVELS_DIR / "level_01.lvl", catalog)

    assert level.id == "level_01"

    destinations = sorted(s.next_level for s in level.stairs)
    assert destinations == ["level_02a", "level_02b"]

    entity_names = sorted(s.entity.name for s in level.entity_spawns)
    assert entity_names == ["Goblin", "Rat", "Rat"]

    item_names = sorted(s.item.name for s in level.item_spawns)
    assert item_names == [
        "Arrows", "Healing Potion", "Healing Potion", "Hunting Bow", "Rusty Dagger", "Rusty Key",
    ]

    door_keys = sorted(d.requires_key for d in level.doors)
    assert door_keys == ["rusty_key"]


def test_broken_level_reports_all_errors():
    catalog = load_catalog()
    with pytest.raises(ContentValidationError) as excinfo:
        load_level(FIXTURES_DIR / "broken_level.lvl", catalog)

    message = str(excinfo.value)
    assert "row" in message  # ragged map row
    assert "player_start" in message  # missing player start
    assert "nonexistent_monster" in message  # unknown entity reference
    assert "stairs_down" in message  # no stairs at all


def test_level_with_no_stairs_is_rejected():
    catalog = load_catalog()
    with pytest.raises(ContentValidationError, match="stairs_down"):
        load_level(FIXTURES_DIR / "no_stairs.lvl", catalog)


def test_dangling_stairs_reference_is_rejected_when_known_ids_given():
    catalog = load_catalog()
    with pytest.raises(ContentValidationError, match="level_nonexistent"):
        load_level(
            FIXTURES_DIR / "dangling_stairs.lvl",
            catalog,
            known_level_ids={"dangling_stairs"},
        )


def test_dangling_stairs_reference_ignored_without_known_ids():
    # No known_level_ids given (e.g. previewing a single file in isolation) ->
    # cross-level reference checking is skipped, so this should load cleanly.
    catalog = load_catalog()
    level = load_level(FIXTURES_DIR / "dangling_stairs.lvl", catalog)
    assert level.stairs[0].next_level == "level_nonexistent"


def test_load_levels_loads_and_links_all_six_forgotten_ruins_levels():
    catalog = load_catalog()
    levels = load_levels(FORGOTTEN_RUINS_LEVELS_DIR, catalog)

    assert set(levels) == {
        "level_01", "level_02a", "level_02b", "level_03", "level_04", "level_05",
    }

    level_01_destinations = sorted(s.next_level for s in levels["level_01"].stairs)
    assert level_01_destinations == ["level_02a", "level_02b"]

    assert [s.next_level for s in levels["level_02a"].stairs] == ["level_03"]
    assert [s.next_level for s in levels["level_02b"].stairs] == ["level_03"]
    assert [s.next_level for s in levels["level_03"].stairs] == ["level_04"]
    assert [s.next_level for s in levels["level_04"].stairs] == ["level_05"]
    assert [s.next_level for s in levels["level_05"].stairs] == [None]


def test_level_04_content():
    catalog = load_catalog()
    level = load_level(FORGOTTEN_RUINS_LEVELS_DIR / "level_04.lvl", catalog)

    entity_names = sorted(s.entity.name for s in level.entity_spawns)
    assert entity_names == ["Rat", "Skeleton", "Skeleton", "Skeleton Archer"]

    item_names = sorted(s.item.name for s in level.item_spawns)
    assert item_names == ["Arrows", "Bone Plate", "Healing Potion", "Iron Sword", "Rusty Key"]

    door_keys = sorted(d.requires_key for d in level.doors)
    assert door_keys == ["rusty_key"]


def test_level_05_content():
    catalog = load_catalog()
    level = load_level(FORGOTTEN_RUINS_LEVELS_DIR / "level_05.lvl", catalog)

    entity_names = sorted(s.entity.name for s in level.entity_spawns)
    assert entity_names == ["Ogre", "Skeleton"]

    item_names = sorted(s.item.name for s in level.item_spawns)
    assert item_names == ["Healing Potion", "Healing Potion"]

    assert [s.next_level for s in level.stairs] == [None]  # terminal - wins the game


def test_door_referencing_unknown_item_is_rejected():
    catalog = load_catalog()
    with pytest.raises(ContentValidationError, match="no_such_item"):
        load_level(FIXTURES_DIR / "door_unknown_key.lvl", catalog)


def test_door_referencing_non_key_item_is_rejected():
    catalog = load_catalog()
    with pytest.raises(ContentValidationError, match="not a key item"):
        load_level(FIXTURES_DIR / "door_non_key_item.lvl", catalog)


def test_load_dungeon_loads_manifest_and_levels():
    catalog = load_catalog()
    dungeon = load_dungeon(DUNGEONS_DIR / "forgotten_ruins", catalog)

    assert dungeon.id == "forgotten_ruins"
    assert dungeon.name == "The Forgotten Ruins"
    assert dungeon.starting_level == "level_01"
    assert set(dungeon.levels) == {
        "level_01", "level_02a", "level_02b", "level_03", "level_04", "level_05",
    }


def test_load_dungeon_rejects_unknown_starting_level(tmp_path):
    dungeon_dir = tmp_path / "broken_dungeon"
    levels_dir = dungeon_dir / "levels"
    levels_dir.mkdir(parents=True)
    (dungeon_dir / "dungeon.yaml").write_text(
        "id: broken_dungeon\nname: Broken\nstarting_level: nope\n", encoding="utf-8"
    )
    (levels_dir / "level_01.lvl").write_text(
        "id: level_01\n"
        "name: Test Level\n"
        "map: |\n"
        "  ###\n"
        "  #@#\n"
        "  #>#\n"
        "  ###\n"
        "legend:\n"
        '  "#": wall\n'
        '  ".": floor\n'
        '  "@": player_start\n'
        '  ">": stairs_down\n',
        encoding="utf-8",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="starting_level"):
        load_dungeon(dungeon_dir, catalog)


def test_load_dungeon_registry_finds_both_shipped_dungeons():
    catalog = load_catalog()
    registry = load_dungeon_registry(DUNGEONS_DIR, catalog)

    assert set(registry) == {"forgotten_ruins", "prison_tower"}
    assert registry["forgotten_ruins"].starting_level == "level_01"
    assert registry["prison_tower"].starting_level == "level_01"


def test_prison_tower_level_01_content():
    catalog = load_catalog()
    level = load_level(PRISON_TOWER_LEVELS_DIR / "level_01.lvl", catalog)

    entity_names = sorted(s.entity.name for s in level.entity_spawns)
    assert entity_names == ["Crossbow Guard", "Guard"]

    item_names = sorted(s.item.name for s in level.item_spawns)
    assert item_names == ["Hunting Bow", "Rusty Dagger"]


def test_prison_tower_chain_links_all_levels():
    catalog = load_catalog()
    levels = load_levels(PRISON_TOWER_LEVELS_DIR, catalog)

    # level_01 branches: the normal path to level_02, plus a side path into
    # level_01_large (an oversized version of the same cell, used to exercise
    # the camera/viewport system on a map far bigger than the console) which
    # rejoins the main chain at level_02.
    assert set(levels) == {"level_01", "level_01_large", "level_02", "level_03", "level_04"}
    assert [s.next_level for s in levels["level_01"].stairs] == ["level_01_large", "level_02"]
    assert [s.next_level for s in levels["level_01_large"].stairs] == ["level_02"]
    assert [s.next_level for s in levels["level_02"].stairs] == ["level_03"]
    assert [s.next_level for s in levels["level_03"].stairs] == ["level_04"]
    assert [s.next_level for s in levels["level_04"].stairs] == [None]
