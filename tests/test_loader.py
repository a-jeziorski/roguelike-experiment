from pathlib import Path

import pytest

from content.loader import (
    ContentValidationError,
    load_catalog,
    load_dungeon,
    load_dungeon_registry,
    load_level,
    load_levels,
    load_overworld,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DUNGEONS_DIR = DATA_DIR / "dungeons"
FORGOTTEN_RUINS_LEVELS_DIR = DUNGEONS_DIR / "forgotten_ruins" / "levels"
PRISON_TOWER_LEVELS_DIR = DUNGEONS_DIR / "prison_tower" / "levels"
MILLHAVEN_LEVELS_DIR = DUNGEONS_DIR / "millhaven" / "levels"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_load_catalog_loads_real_data():
    catalog = load_catalog()
    assert "rat" in catalog.entities
    assert "goblin" in catalog.entities
    assert "healing_potion" in catalog.items
    assert "rusty_dagger" in catalog.items


@pytest.mark.parametrize(
    "entity_id,hp,attack,defense,ai",
    [
        ("bandit", 13, 5, 1, "hostile_basic"),
        ("bandit_captain", 20, 7, 2, "hostile_basic"),
        ("drowned_wretch", 11, 4, 0, "hostile_basic"),
        ("stone_sentinel", 30, 5, 3, "hostile_basic"),
    ],
)
def test_new_monster_catalog_entries(entity_id, hp, attack, defense, ai):
    catalog = load_catalog()
    entity = catalog.entities[entity_id]

    assert entity.hp == hp
    assert entity.attack == attack
    assert entity.defense == defense
    assert entity.ai == ai
    assert entity.description


@pytest.mark.parametrize(
    "level_file,require_stairs_down",
    [(p, True) for p in sorted(FORGOTTEN_RUINS_LEVELS_DIR.glob("*.lvl"))]
    + [(p, True) for p in sorted(PRISON_TOWER_LEVELS_DIR.glob("*.lvl"))]
    + [(p, False) for p in sorted(MILLHAVEN_LEVELS_DIR.glob("*.lvl"))],
)
def test_every_shipped_level_validates_cleanly(level_file, require_stairs_down):
    catalog = load_catalog()
    level = load_level(level_file, catalog, require_stairs_down=require_stairs_down)
    assert level.width > 0
    assert level.height > 0
    assert all(len(row) == level.width for row in level.tiles)


def test_level_01_content():
    catalog = load_catalog()
    level = load_level(FORGOTTEN_RUINS_LEVELS_DIR / "level_01.lvl", catalog)

    assert level.id == "level_01"

    # None is the terminal retreat stairs_up (leaves to the overworld).
    destinations = sorted(s.next_level for s in level.stairs if s.next_level is not None)
    assert destinations == ["level_02a", "level_02b"]
    assert sum(1 for s in level.stairs if s.kind == "stairs_up" and s.next_level is None) == 1

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


def test_stairs_down_not_required_when_flag_is_false():
    # only_stairs_up.lvl has no stairs_down at all - rejected by default,
    # accepted once a level opts out via require_stairs_down=False.
    catalog = load_catalog()
    level = load_level(FIXTURES_DIR / "only_stairs_up.lvl", catalog, require_stairs_down=False)
    assert [s.kind for s in level.stairs] == ["stairs_up"]


def test_level_with_no_stairs_at_all_still_rejected_when_not_required():
    catalog = load_catalog()
    with pytest.raises(ContentValidationError, match="there would be no way to leave"):
        load_level(FIXTURES_DIR / "no_stairs.lvl", catalog, require_stairs_down=False)


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


def test_terminal_stairs_up_is_valid_and_means_leave_to_overworld():
    catalog = load_catalog()
    level = load_level(FIXTURES_DIR / "terminal_stairs_both_kinds.lvl", catalog)

    stairs_up = next(s for s in level.stairs if s.kind == "stairs_up")
    assert stairs_up.next_level is None


def test_level_with_only_stairs_up_still_requires_stairs_down():
    catalog = load_catalog()
    with pytest.raises(ContentValidationError, match="at least one stairs_down"):
        load_level(FIXTURES_DIR / "only_stairs_up.lvl", catalog)


def test_two_stairways_to_the_same_level_is_rejected_as_ambiguous():
    catalog = load_catalog()
    with pytest.raises(ContentValidationError, match="ambiguous which one is the return path"):
        load_level(FIXTURES_DIR / "ambiguous_return_stairs.lvl", catalog)


def test_load_levels_loads_and_links_all_six_forgotten_ruins_levels():
    catalog = load_catalog()
    levels = load_levels(FORGOTTEN_RUINS_LEVELS_DIR, catalog)

    assert set(levels) == {
        "level_01", "level_02a", "level_02b", "level_03", "level_04", "level_05",
    }

    level_01_destinations = sorted(
        s.next_level for s in levels["level_01"].stairs if s.next_level is not None
    )
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
    assert dungeon.inspect_text != ""  # shown when its overworld entrance is inspected
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


def test_load_dungeon_threads_requires_stairs_down_false_into_levels(tmp_path):
    dungeon_dir = tmp_path / "peaceful_dungeon"
    levels_dir = dungeon_dir / "levels"
    levels_dir.mkdir(parents=True)
    (dungeon_dir / "dungeon.yaml").write_text(
        "id: peaceful_dungeon\nname: Peaceful\nstarting_level: level_01\n"
        "requires_stairs_down: false\n",
        encoding="utf-8",
    )
    (levels_dir / "level_01.lvl").write_text(
        "id: level_01\n"
        "name: Test Level\n"
        "map: |\n"
        "  ###\n"
        "  #@#\n"
        "  #x#\n"
        "  ###\n"
        "legend:\n"
        '  "#": wall\n'
        '  ".": floor\n'
        '  "@": player_start\n'
        '  "x": stairs_up\n',
        encoding="utf-8",
    )
    catalog = load_catalog()

    dungeon = load_dungeon(dungeon_dir, catalog)

    assert dungeon.requires_stairs_down is False
    assert [s.kind for s in dungeon.levels["level_01"].stairs] == ["stairs_up"]


def test_millhaven_level_01_content():
    catalog = load_catalog()
    level = load_level(
        MILLHAVEN_LEVELS_DIR / "level_01.lvl", catalog, require_stairs_down=False
    )

    entity_names = sorted(s.entity.name for s in level.entity_spawns)
    assert entity_names == ["Village Chief"] + ["Villager"] * 5

    # every entity spawn carries its own per-spawn dialogue - no un-authored
    # villagers left in Millhaven now that this pass gave each one a line
    assert all(s.dialogue for s in level.entity_spawns)

    assert [s.kind for s in level.stairs] == ["stairs_up"]
    assert level.stairs[0].next_level is None  # terminal - leaves to the overworld
    assert not any(s.kind == "stairs_down" for s in level.stairs)

    # the gate + the well and mending-yard landmarks
    assert len(level.tile_descriptions) == 3
    exit_stairs_x, exit_stairs_y = level.stairs[0].x, level.stairs[0].y
    desc = next(
        d for d in level.tile_descriptions if (d.x, d.y) == (exit_stairs_x, exit_stairs_y)
    )
    assert desc.text == "The town gate, leading back out onto the road."


def test_load_level_collects_custom_tile_descriptions():
    catalog = load_catalog()
    level = load_level(FIXTURES_DIR / "only_stairs_up.lvl", catalog, require_stairs_down=False)
    assert level.tile_descriptions == []  # no legend entry sets description there


def test_load_level_collects_per_spawn_entity_dialogue(tmp_path):
    level_path = tmp_path / "with_dialogue.lvl"
    level_path.write_text(
        "id: with_dialogue\n"
        "name: Test Level\n"
        "map: |\n"
        "  ###\n"
        "  #@#\n"
        "  #v#\n"
        "  #>#\n"
        "  ###\n"
        "legend:\n"
        '  "#": wall\n'
        '  ".": floor\n'
        '  "@": player_start\n'
        '  ">": stairs_down\n'
        '  "v": { entity: villager, dialogue: "Well held up better than most things." }\n',
        encoding="utf-8",
    )
    catalog = load_catalog()

    level = load_level(level_path, catalog)

    assert len(level.entity_spawns) == 1
    assert level.entity_spawns[0].dialogue == "Well held up better than most things."
    # a per-spawn dialogue is not a tile description - the two are independent
    assert level.tile_descriptions == []


def test_load_level_entity_spawn_without_dialogue_leaves_it_none(tmp_path):
    level_path = tmp_path / "no_dialogue.lvl"
    level_path.write_text(
        "id: no_dialogue\n"
        "name: Test Level\n"
        "map: |\n"
        "  ###\n"
        "  #@#\n"
        "  #v#\n"
        "  #>#\n"
        "  ###\n"
        "legend:\n"
        '  "#": wall\n'
        '  ".": floor\n'
        '  "@": player_start\n'
        '  ">": stairs_down\n'
        '  "v": { entity: villager }\n',
        encoding="utf-8",
    )
    catalog = load_catalog()

    level = load_level(level_path, catalog)

    assert level.entity_spawns[0].dialogue is None


def test_load_level_rejects_a_door_with_a_second_route_around_it(tmp_path):
    # Two parallel corridors both connect the same open top row to the same
    # open bottom row - one is locked, one isn't - so the door guards nothing.
    level_path = tmp_path / "bypassable.lvl"
    level_path.write_text(
        "id: bypassable\n"
        "name: Bypassable\n"
        "map: |\n"
        "  #####\n"
        "  #@..#\n"
        "  #.#.#\n"
        "  #.D.#\n"
        "  #.#.#\n"
        "  #..>#\n"
        "  #####\n"
        "legend:\n"
        '  "#": wall\n'
        '  ".": floor\n'
        '  "@": player_start\n'
        '  "D": { door: rusty_key }\n'
        '  ">": stairs_down\n',
        encoding="utf-8",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="does not enclose anything"):
        load_level(level_path, catalog)


def test_load_level_rejects_a_door_bypassed_diagonally(tmp_path):
    # The tile directly behind the door has no *orthogonal* neighbor except
    # the door itself, but it's diagonally adjacent to tiles on both sides -
    # MovementAction never blocks a diagonal step for cutting a wall's
    # corner, so this is a real bypass in actual play, not a theoretical one
    # a 4-directional-only reachability check would miss (mirrors the actual
    # bug found in the Sunken Mine's Weighhouse Shaft).
    level_path = tmp_path / "diagonal_bypass.lvl"
    level_path.write_text(
        "id: diagonal_bypass\n"
        "name: Diagonal Bypass\n"
        "map: |\n"
        "  #######\n"
        "  #@>.D.#\n"
        "  ####.##\n"
        "  #######\n"
        "legend:\n"
        '  "#": wall\n'
        '  ".": floor\n'
        '  "@": player_start\n'
        '  "D": { door: rusty_key }\n'
        '  ">": stairs_down\n',
        encoding="utf-8",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="does not enclose anything"):
        load_level(level_path, catalog)


def test_load_level_accepts_a_door_that_truly_encloses_its_reward():
    catalog = load_catalog()
    level = load_level(FIXTURES_DIR / "enclosed_door.lvl", catalog)

    assert [(d.x, d.y) for d in level.doors] == [(6, 1)]
    assert [i.item.id for i in level.item_spawns] == ["leather_armor"]


SHIPPED_DUNGEON_IDS = {
    "forgotten_ruins",
    "prison_tower",
    "millhaven",
    "broken_watch",
    "drowned_waystation",
    "elder_cairn",
    "sunken_mine",
    "wayford",
    "stonebridge",
    "saltmarsh",
}

COMBAT_DUNGEON_IDS = ["broken_watch", "drowned_waystation", "elder_cairn", "sunken_mine"]
SETTLEMENT_DUNGEON_IDS = ["wayford", "stonebridge", "saltmarsh"]


def test_load_dungeon_registry_finds_all_shipped_dungeons():
    catalog = load_catalog()
    registry = load_dungeon_registry(DUNGEONS_DIR, catalog)

    assert set(registry) == SHIPPED_DUNGEON_IDS
    for dungeon_id in SHIPPED_DUNGEON_IDS:
        assert registry[dungeon_id].starting_level == "level_01"


@pytest.mark.parametrize("dungeon_id", COMBAT_DUNGEON_IDS)
def test_new_combat_dungeon_content(dungeon_id):
    catalog = load_catalog()
    dungeon = load_dungeon(DUNGEONS_DIR / dungeon_id, catalog)

    assert dungeon.requires_stairs_down is True
    assert dungeon.id == dungeon_id
    assert dungeon.description
    assert dungeon.inspect_text

    all_stairs = [s for level in dungeon.levels.values() for s in level.stairs]
    assert any(s.kind == "stairs_down" and s.next_level is None for s in all_stairs)

    all_entities = [s.entity.name for level in dungeon.levels.values() for s in level.entity_spawns]
    assert len(all_entities) > 0


@pytest.mark.parametrize("dungeon_id", SETTLEMENT_DUNGEON_IDS)
def test_new_settlement_dungeon_content(dungeon_id):
    catalog = load_catalog()
    dungeon = load_dungeon(DUNGEONS_DIR / dungeon_id, catalog)

    assert dungeon.requires_stairs_down is False
    assert dungeon.id == dungeon_id
    assert dungeon.description
    assert dungeon.inspect_text

    all_entities = [s.entity for level in dungeon.levels.values() for s in level.entity_spawns]
    assert len(all_entities) > 0
    assert all(e.ai == "villager" for e in all_entities)


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
    # level_01's first stairway is now its retreat stairs_up (terminal, leaves
    # to the overworld), scanned before the two stairs_down branches below it.
    assert [s.next_level for s in levels["level_01"].stairs] == [None, "level_01_large", "level_02"]
    assert [s.next_level for s in levels["level_01_large"].stairs] == ["level_02"]
    # level_02 also has a stairs_up back to level_01 (the return-trip example).
    assert [s.next_level for s in levels["level_02"].stairs] == ["level_01", "level_03"]
    assert [s.next_level for s in levels["level_03"].stairs] == ["level_04"]
    assert [s.next_level for s in levels["level_04"].stairs] == [None]


def test_load_overworld_happy_path():
    catalog = load_catalog()
    level = load_overworld(
        FIXTURES_DIR / "overworld_valid.lvl", catalog, known_dungeon_ids={"prison_tower"}
    )

    assert level.id == "overworld_valid"
    assert level.player_start == (1, 1)
    assert [e.dungeon_id for e in level.dungeon_entrances] == ["prison_tower"]
    assert level.stairs == []
    assert level.entity_spawns == []
    assert level.item_spawns == []


def test_load_overworld_rejects_unknown_dungeon_id():
    catalog = load_catalog()
    with pytest.raises(ContentValidationError, match="unknown dungeon 'no_such_dungeon'"):
        load_overworld(
            FIXTURES_DIR / "overworld_unknown_dungeon.lvl", catalog,
            known_dungeon_ids={"prison_tower"},
        )


def test_load_overworld_rejects_ambiguous_entrances_to_the_same_dungeon():
    catalog = load_catalog()
    with pytest.raises(ContentValidationError, match="ambiguous which one is the return path"):
        load_overworld(
            FIXTURES_DIR / "overworld_ambiguous_entrances.lvl", catalog,
            known_dungeon_ids={"prison_tower"},
        )


def test_load_overworld_requires_at_least_one_dungeon_entrance():
    catalog = load_catalog()
    with pytest.raises(ContentValidationError, match="at least one dungeon_entrance"):
        load_overworld(
            FIXTURES_DIR / "overworld_no_entrance.lvl", catalog, known_dungeon_ids={"prison_tower"}
        )


def test_load_overworld_rejects_stairs_tiles():
    catalog = load_catalog()
    with pytest.raises(ContentValidationError, match="stairs_down.*has no meaning on the overworld"):
        load_overworld(
            FIXTURES_DIR / "overworld_with_stairs.lvl", catalog, known_dungeon_ids={"prison_tower"}
        )


def test_load_level_rejects_dungeon_entrance_tiles():
    catalog = load_catalog()
    with pytest.raises(ContentValidationError, match="dungeon_entrance.*has no meaning inside a dungeon"):
        load_level(FIXTURES_DIR / "level_with_dungeon_entrance.lvl", catalog)
