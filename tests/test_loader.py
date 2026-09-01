from pathlib import Path

import pytest

from content.loader import (
    ContentValidationError,
    _parse_overworld_cell,
    load_audio_manifest,
    load_catalog,
    load_dungeon,
    load_dungeon_registry,
    load_level,
    load_levels,
    load_overworld,
    load_sprite_manifest,
)
from content.schema import FlagDialogue
from engine.game_map import build_game_map

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DUNGEONS_DIR = DATA_DIR / "dungeons"
OVERWORLD_DIR = DATA_DIR / "overworld"
FORGOTTEN_RUINS_LEVELS_DIR = DUNGEONS_DIR / "forgotten_ruins" / "levels"
PRISON_TOWER_LEVELS_DIR = DUNGEONS_DIR / "prison_tower" / "levels"
SUNKEN_MINE_LEVELS_DIR = DUNGEONS_DIR / "sunken_mine" / "levels"
MILLHAVEN_LEVELS_DIR = DUNGEONS_DIR / "millhaven" / "levels"
BROKEN_WATCH_LEVELS_DIR = DUNGEONS_DIR / "broken_watch" / "levels"
SILVER_MOUNTAIN_CAVES_LEVELS_DIR = DUNGEONS_DIR / "silver_mountain_caves" / "levels"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_load_catalog_loads_real_data():
    catalog = load_catalog()
    assert "rat" in catalog.entities
    assert "goblin" in catalog.entities
    assert "healing_potion" in catalog.items
    assert "rusty_dagger" in catalog.items


def test_load_catalog_real_shopkeeper_has_shop_inventory():
    catalog = load_catalog()
    assert catalog.entities["shopkeeper"].shop_inventory == ["healing_potion", "teleportation_potion"]


def test_load_catalog_rejects_shop_inventory_referencing_unknown_item(tmp_path):
    entities_path = tmp_path / "entities.yaml"
    items_path = tmp_path / "items.yaml"
    entities_path.write_text(
        "merchant:\n"
        "  name: Merchant\n"
        "  glyph: m\n"
        "  color: [200, 160, 70]\n"
        "  hp: 10\n"
        "  attack: 0\n"
        "  defense: 0\n"
        "  ai: villager\n"
        "  shop_inventory: [nonexistent_item]\n",
        encoding="utf-8",
    )
    items_path.write_text("", encoding="utf-8")

    with pytest.raises(ContentValidationError, match="shop_inventory references unknown item"):
        load_catalog(entities_path, items_path)


def test_load_catalog_rejects_shop_inventory_item_with_no_cost(tmp_path):
    entities_path = tmp_path / "entities.yaml"
    items_path = tmp_path / "items.yaml"
    entities_path.write_text(
        "merchant:\n"
        "  name: Merchant\n"
        "  glyph: m\n"
        "  color: [200, 160, 70]\n"
        "  hp: 10\n"
        "  attack: 0\n"
        "  defense: 0\n"
        "  ai: villager\n"
        "  shop_inventory: [free_thing]\n",
        encoding="utf-8",
    )
    items_path.write_text(
        "free_thing:\n"
        "  name: Free Thing\n"
        "  glyph: '?'\n"
        "  color: [255, 255, 255]\n",  # no cost set
        encoding="utf-8",
    )

    with pytest.raises(ContentValidationError, match="has no cost set"):
        load_catalog(entities_path, items_path)


def test_load_catalog_rejects_shop_inventory_on_a_non_peaceful_entity(tmp_path):
    entities_path = tmp_path / "entities.yaml"
    items_path = tmp_path / "items.yaml"
    entities_path.write_text(
        "shady_rat:\n"
        "  name: Shady Rat\n"
        "  glyph: r\n"
        "  color: [140, 90, 60]\n"
        "  hp: 6\n"
        "  attack: 2\n"
        "  defense: 0\n"
        "  ai: hostile_basic\n"
        "  shop_inventory: [trinket]\n",
        encoding="utf-8",
    )
    items_path.write_text(
        "trinket:\n"
        "  name: Trinket\n"
        "  glyph: '?'\n"
        "  color: [255, 255, 255]\n"
        "  cost: 5\n",
        encoding="utf-8",
    )

    with pytest.raises(ContentValidationError, match="could never be sold"):
        load_catalog(entities_path, items_path)


def test_load_catalog_allows_shop_inventory_on_a_town_guard(tmp_path):
    """Confirms the peaceful-AI check accepts both PEACEFUL_AI_TYPES, not
    just villager - a real content file could reasonably want a guard who
    also sells something."""
    entities_path = tmp_path / "entities.yaml"
    items_path = tmp_path / "items.yaml"
    entities_path.write_text(
        "quartermaster:\n"
        "  name: Quartermaster\n"
        "  glyph: g\n"
        "  color: [120, 120, 140]\n"
        "  hp: 18\n"
        "  attack: 4\n"
        "  defense: 1\n"
        "  ai: town_guard\n"
        "  shop_inventory: [trinket]\n",
        encoding="utf-8",
    )
    items_path.write_text(
        "trinket:\n"
        "  name: Trinket\n"
        "  glyph: '?'\n"
        "  color: [255, 255, 255]\n"
        "  cost: 5\n",
        encoding="utf-8",
    )

    catalog = load_catalog(entities_path, items_path)

    assert catalog.entities["quartermaster"].shop_inventory == ["trinket"]


def test_load_catalog_real_trainer_has_trainer_perks():
    catalog = load_catalog()
    assert "toughness_1" in catalog.entities["wayford_trainer"].trainer_perks
    assert "toughness_1" in catalog.perks


def test_load_catalog_rejects_trainer_perks_referencing_unknown_perk(tmp_path):
    entities_path = tmp_path / "entities.yaml"
    items_path = tmp_path / "items.yaml"
    perks_path = tmp_path / "perks.yaml"
    entities_path.write_text(
        "trainer:\n"
        "  name: Trainer\n"
        "  glyph: y\n"
        "  color: [150, 130, 100]\n"
        "  hp: 10\n"
        "  attack: 0\n"
        "  defense: 0\n"
        "  ai: villager\n"
        "  trainer_perks: [nonexistent_perk]\n",
        encoding="utf-8",
    )
    items_path.write_text("", encoding="utf-8")
    perks_path.write_text("", encoding="utf-8")

    with pytest.raises(ContentValidationError, match="trainer_perks references unknown perk"):
        load_catalog(entities_path, items_path, perks_path)


def test_load_catalog_accepts_a_valid_perk_tier_chain(tmp_path):
    entities_path = tmp_path / "entities.yaml"
    items_path = tmp_path / "items.yaml"
    perks_path = tmp_path / "perks.yaml"
    entities_path.write_text("", encoding="utf-8")
    items_path.write_text("", encoding="utf-8")
    perks_path.write_text(
        "toughness_1:\n"
        "  name: Toughness\n"
        "  description: Raises max HP.\n"
        "  xp_cost: 40\n"
        "  max_hp_bonus: 5\n"
        "toughness_2:\n"
        "  name: Greater Toughness\n"
        "  description: Raises max HP further.\n"
        "  xp_cost: 80\n"
        "  max_hp_bonus: 8\n"
        "  requires_perk_id: toughness_1\n",
        encoding="utf-8",
    )

    catalog = load_catalog(entities_path, items_path, perks_path)

    assert catalog.perks["toughness_2"].requires_perk_id == "toughness_1"


def test_load_catalog_rejects_requires_perk_id_referencing_unknown_perk(tmp_path):
    entities_path = tmp_path / "entities.yaml"
    items_path = tmp_path / "items.yaml"
    perks_path = tmp_path / "perks.yaml"
    entities_path.write_text("", encoding="utf-8")
    items_path.write_text("", encoding="utf-8")
    perks_path.write_text(
        "toughness_2:\n"
        "  name: Greater Toughness\n"
        "  description: Raises max HP further.\n"
        "  xp_cost: 80\n"
        "  max_hp_bonus: 8\n"
        "  requires_perk_id: nonexistent_perk\n",
        encoding="utf-8",
    )

    with pytest.raises(ContentValidationError, match="requires_perk_id references unknown perk"):
        load_catalog(entities_path, items_path, perks_path)


def test_load_catalog_rejects_requires_perk_id_referencing_itself(tmp_path):
    entities_path = tmp_path / "entities.yaml"
    items_path = tmp_path / "items.yaml"
    perks_path = tmp_path / "perks.yaml"
    entities_path.write_text("", encoding="utf-8")
    items_path.write_text("", encoding="utf-8")
    perks_path.write_text(
        "toughness_1:\n"
        "  name: Toughness\n"
        "  description: Raises max HP.\n"
        "  xp_cost: 40\n"
        "  max_hp_bonus: 5\n"
        "  requires_perk_id: toughness_1\n",
        encoding="utf-8",
    )

    with pytest.raises(ContentValidationError, match="can't reference itself"):
        load_catalog(entities_path, items_path, perks_path)


def test_load_catalog_rejects_a_requires_perk_id_cycle(tmp_path):
    entities_path = tmp_path / "entities.yaml"
    items_path = tmp_path / "items.yaml"
    perks_path = tmp_path / "perks.yaml"
    entities_path.write_text("", encoding="utf-8")
    items_path.write_text("", encoding="utf-8")
    perks_path.write_text(
        "perk_a:\n"
        "  name: Perk A\n"
        "  description: The first half of a cycle.\n"
        "  xp_cost: 40\n"
        "  max_hp_bonus: 5\n"
        "  requires_perk_id: perk_b\n"
        "perk_b:\n"
        "  name: Perk B\n"
        "  description: The second half of a cycle.\n"
        "  xp_cost: 40\n"
        "  attack_bonus: 2\n"
        "  requires_perk_id: perk_a\n",
        encoding="utf-8",
    )

    with pytest.raises(ContentValidationError, match="requires_perk_id chain forms a cycle"):
        load_catalog(entities_path, items_path, perks_path)


def test_load_catalog_rejects_trainer_perks_on_a_non_peaceful_entity(tmp_path):
    entities_path = tmp_path / "entities.yaml"
    items_path = tmp_path / "items.yaml"
    perks_path = tmp_path / "perks.yaml"
    entities_path.write_text(
        "shady_rat:\n"
        "  name: Shady Rat\n"
        "  glyph: r\n"
        "  color: [140, 90, 60]\n"
        "  hp: 6\n"
        "  attack: 2\n"
        "  defense: 0\n"
        "  ai: hostile_basic\n"
        "  trainer_perks: [toughness_1]\n",
        encoding="utf-8",
    )
    items_path.write_text("", encoding="utf-8")
    perks_path.write_text(
        "toughness_1:\n"
        "  name: Toughness\n"
        "  description: Raises max HP.\n"
        "  xp_cost: 40\n"
        "  max_hp_bonus: 5\n",
        encoding="utf-8",
    )

    with pytest.raises(ContentValidationError, match="could never teach anything"):
        load_catalog(entities_path, items_path, perks_path)


def test_load_catalog_rejects_xp_reward_on_a_peaceful_entity(tmp_path):
    entities_path = tmp_path / "entities.yaml"
    items_path = tmp_path / "items.yaml"
    perks_path = tmp_path / "perks.yaml"
    entities_path.write_text(
        "farmable_villager:\n"
        "  name: Farmable Villager\n"
        "  glyph: v\n"
        "  color: [170, 140, 90]\n"
        "  hp: 10\n"
        "  attack: 0\n"
        "  defense: 0\n"
        "  ai: villager\n"
        "  xp_reward: 5\n",
        encoding="utf-8",
    )
    items_path.write_text("", encoding="utf-8")
    perks_path.write_text("", encoding="utf-8")

    with pytest.raises(ContentValidationError, match="farm XP by killing"):
        load_catalog(entities_path, items_path, perks_path)


def test_load_catalog_rejects_drop_item_id_referencing_unknown_item(tmp_path):
    entities_path = tmp_path / "entities.yaml"
    items_path = tmp_path / "items.yaml"
    perks_path = tmp_path / "perks.yaml"
    entities_path.write_text(
        "looter_rat:\n"
        "  name: Looter Rat\n"
        "  glyph: r\n"
        "  color: [140, 90, 60]\n"
        "  hp: 6\n"
        "  attack: 2\n"
        "  defense: 0\n"
        "  ai: hostile_basic\n"
        "  drop_item_id: nonexistent_item\n"
        "  drop_chance: 0.5\n",
        encoding="utf-8",
    )
    items_path.write_text("", encoding="utf-8")
    perks_path.write_text("", encoding="utf-8")

    with pytest.raises(ContentValidationError, match="drop_item_id references unknown item"):
        load_catalog(entities_path, items_path, perks_path)


def test_load_catalog_rejects_drop_item_id_on_a_peaceful_entity(tmp_path):
    entities_path = tmp_path / "entities.yaml"
    items_path = tmp_path / "items.yaml"
    perks_path = tmp_path / "perks.yaml"
    entities_path.write_text(
        "farmable_villager:\n"
        "  name: Farmable Villager\n"
        "  glyph: v\n"
        "  color: [170, 140, 90]\n"
        "  hp: 10\n"
        "  attack: 0\n"
        "  defense: 0\n"
        "  ai: villager\n"
        "  drop_item_id: trinket\n"
        "  drop_chance: 0.5\n",
        encoding="utf-8",
    )
    items_path.write_text(
        "trinket:\n"
        "  name: Trinket\n"
        "  glyph: '?'\n"
        "  color: [255, 255, 255]\n"
        "  cost: 5\n",
        encoding="utf-8",
    )
    perks_path.write_text("", encoding="utf-8")

    with pytest.raises(ContentValidationError, match="shouldn't reward the player for killing it"):
        load_catalog(entities_path, items_path, perks_path)


def test_load_catalog_rejects_summon_entity_id_referencing_unknown_entity(tmp_path):
    entities_path = tmp_path / "entities.yaml"
    items_path = tmp_path / "items.yaml"
    perks_path = tmp_path / "perks.yaml"
    entities_path.write_text(
        "bone_caller:\n"
        "  name: Bone Caller\n"
        "  glyph: U\n"
        "  color: [150, 140, 180]\n"
        "  hp: 14\n"
        "  attack: 2\n"
        "  defense: 0\n"
        "  ai: summoner\n"
        "  summon_entity_id: nonexistent_monster\n"
        "  summon_interval: 4\n",
        encoding="utf-8",
    )
    items_path.write_text("", encoding="utf-8")
    perks_path.write_text("", encoding="utf-8")

    with pytest.raises(ContentValidationError, match="summon_entity_id references unknown entity"):
        load_catalog(entities_path, items_path, perks_path)


def test_load_catalog_rejects_summon_entity_id_targeting_a_peaceful_entity(tmp_path):
    entities_path = tmp_path / "entities.yaml"
    items_path = tmp_path / "items.yaml"
    perks_path = tmp_path / "perks.yaml"
    entities_path.write_text(
        "bone_caller:\n"
        "  name: Bone Caller\n"
        "  glyph: U\n"
        "  color: [150, 140, 180]\n"
        "  hp: 14\n"
        "  attack: 2\n"
        "  defense: 0\n"
        "  ai: summoner\n"
        "  summon_entity_id: villager\n"
        "  summon_interval: 4\n"
        "villager:\n"
        "  name: Villager\n"
        "  glyph: v\n"
        "  color: [170, 140, 90]\n"
        "  hp: 10\n"
        "  attack: 0\n"
        "  defense: 0\n"
        "  ai: villager\n",
        encoding="utf-8",
    )
    items_path.write_text("", encoding="utf-8")
    perks_path.write_text("", encoding="utf-8")

    with pytest.raises(ContentValidationError, match="summoning one as reinforcement makes no sense"):
        load_catalog(entities_path, items_path, perks_path)


def test_load_catalog_accepts_a_valid_summoner(tmp_path):
    entities_path = tmp_path / "entities.yaml"
    items_path = tmp_path / "items.yaml"
    perks_path = tmp_path / "perks.yaml"
    entities_path.write_text(
        "bone_caller:\n"
        "  name: Bone Caller\n"
        "  glyph: U\n"
        "  color: [150, 140, 180]\n"
        "  hp: 14\n"
        "  attack: 2\n"
        "  defense: 0\n"
        "  ai: summoner\n"
        "  summon_entity_id: kobold\n"
        "  summon_interval: 4\n"
        "  summon_max_active: 2\n"
        "kobold:\n"
        "  name: Kobold\n"
        "  glyph: k\n"
        "  color: [150, 120, 60]\n"
        "  hp: 8\n"
        "  attack: 3\n"
        "  defense: 0\n"
        "  ai: hostile_basic\n",
        encoding="utf-8",
    )
    items_path.write_text("", encoding="utf-8")
    perks_path.write_text("", encoding="utf-8")

    catalog = load_catalog(entities_path, items_path, perks_path)

    assert catalog.entities["bone_caller"].summon_entity_id == "kobold"


@pytest.mark.parametrize(
    "entity_id,hp,attack,defense,ai",
    [
        ("bandit", 13, 5, 1, "hostile_basic"),
        ("bandit_captain", 20, 7, 2, "hostile_basic"),
        ("drowned_wretch", 11, 4, 0, "hostile_basic"),
        ("stone_sentinel", 30, 5, 3, "hostile_basic"),
        ("slime", 16, 3, 0, "splitter"),
        ("bone_caller", 14, 2, 0, "summoner"),
        ("boar", 12, 4, 0, "charger"),
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
        "Arrows", "Healing Potion", "Healing Potion", "Hunting Bow", "Lucky Charm", "Rusty Dagger", "Rusty Key",
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


def test_open_boundary_satisfies_the_no_stairs_soft_lock_check(tmp_path):
    level_path = tmp_path / "open.lvl"
    level_path.write_text(
        "id: open\n"
        "name: Test Level\n"
        "open_boundary: true\n"
        "map: |\n"
        "  ###\n"
        "  #@,\n"
        "  ###\n"
        "legend:\n"
        '  "#": wall\n'
        '  ",": plains\n'
        '  "@": player_start\n',
        encoding="utf-8",
    )
    catalog = load_catalog()

    level = load_level(level_path, catalog, require_stairs_down=False)

    assert level.open_boundary is True
    assert level.stairs == []


def test_open_boundary_with_a_fully_walled_perimeter_is_rejected(tmp_path):
    level_path = tmp_path / "sealed.lvl"
    level_path.write_text(
        "id: sealed\n"
        "name: Test Level\n"
        "open_boundary: true\n"
        "map: |\n"
        "  ###\n"
        "  #@#\n"
        "  ###\n"
        "legend:\n"
        '  "#": wall\n'
        '  "@": player_start\n',
        encoding="utf-8",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="no perimeter tile is walkable"):
        load_level(level_path, catalog, require_stairs_down=False)


def test_load_level_player_start_tile_defaults_to_floor():
    catalog = load_catalog()
    level = load_level(FIXTURES_DIR / "only_stairs_up.lvl", catalog, require_stairs_down=False)
    assert level.player_start_tile == "floor"


def test_load_level_carries_through_an_explicit_player_start_tile(tmp_path):
    level_path = tmp_path / "custom_start.lvl"
    level_path.write_text(
        "id: custom_start\n"
        "name: Test Level\n"
        "player_start_tile: plains\n"
        "open_boundary: true\n"
        "map: |\n"
        "  ###\n"
        "  #@,\n"
        "  ###\n"
        "legend:\n"
        '  "#": wall\n'
        '  ",": plains\n'
        '  "@": player_start\n',
        encoding="utf-8",
    )
    catalog = load_catalog()

    level = load_level(level_path, catalog, require_stairs_down=False)

    assert level.player_start_tile == "plains"


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
    assert dungeon.ruined_tile is None  # not a destroyable dungeon
    assert dungeon.ruined_description == ""
    assert set(dungeon.levels) == {
        "level_01", "level_02a", "level_02b", "level_03", "level_04", "level_05",
    }


def test_load_dungeon_carries_through_ruin_content():
    catalog = load_catalog()
    dungeon = load_dungeon(DUNGEONS_DIR / "wayford", catalog)

    assert dungeon.ruined_tile == "floor"
    assert dungeon.ruined_description != ""
    assert dungeon.ruined_starting_level == "level_01_ruins"
    assert "level_01_ruins" in dungeon.levels  # a real, walkable ruins interior


def test_load_dungeon_rejects_unknown_ruined_starting_level(tmp_path):
    dungeon_dir = tmp_path / "broken_dungeon"
    levels_dir = dungeon_dir / "levels"
    levels_dir.mkdir(parents=True)
    (dungeon_dir / "dungeon.yaml").write_text(
        "id: broken_dungeon\nname: Broken\nstarting_level: level_01\n"
        "ruined_tile: floor\nruined_description: Ash.\n"
        "ruined_starting_level: nope\n",
        encoding="utf-8",
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

    with pytest.raises(ContentValidationError, match="ruined_starting_level"):
        load_dungeon(dungeon_dir, catalog)


def test_load_dungeon_rejects_ruined_starting_level_equal_to_starting_level(tmp_path):
    dungeon_dir = tmp_path / "broken_dungeon"
    levels_dir = dungeon_dir / "levels"
    levels_dir.mkdir(parents=True)
    (dungeon_dir / "dungeon.yaml").write_text(
        "id: broken_dungeon\nname: Broken\nstarting_level: level_01\n"
        "ruined_tile: floor\nruined_description: Ash.\n"
        "ruined_starting_level: level_01\n",
        encoding="utf-8",
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

    with pytest.raises(ContentValidationError, match="same as starting_level"):
        load_dungeon(dungeon_dir, catalog)


def test_load_dungeon_carries_through_pre_arrival_content():
    catalog = load_catalog()
    dungeon = load_dungeon(DUNGEONS_DIR / "silver_mountain_caves", catalog)

    assert dungeon.pre_arrival_starting_level == "level_01_undisturbed"
    assert dungeon.pre_arrival_until_year == 87
    assert dungeon.pre_arrival_until_day == 67
    assert "level_01_undisturbed" in dungeon.levels  # a real, walkable pre-arrival interior

    undisturbed = dungeon.levels["level_01_undisturbed"]
    assert all(spawn.entity.id != "goblin" for spawn in undisturbed.entity_spawns)


def test_load_dungeon_carries_through_balance_reference_xp():
    catalog = load_catalog()
    dungeon = load_dungeon(DUNGEONS_DIR / "the_windrest", catalog)

    assert dungeon.balance_reference_xp == 120


def test_load_dungeon_rejects_unknown_pre_arrival_starting_level(tmp_path):
    dungeon_dir = tmp_path / "broken_dungeon"
    levels_dir = dungeon_dir / "levels"
    levels_dir.mkdir(parents=True)
    (dungeon_dir / "dungeon.yaml").write_text(
        "id: broken_dungeon\nname: Broken\nstarting_level: level_01\n"
        "pre_arrival_starting_level: nope\n"
        "pre_arrival_until_year: 87\npre_arrival_until_day: 67\n",
        encoding="utf-8",
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

    with pytest.raises(ContentValidationError, match="pre_arrival_starting_level"):
        load_dungeon(dungeon_dir, catalog)


def test_load_dungeon_rejects_pre_arrival_starting_level_equal_to_starting_level(tmp_path):
    dungeon_dir = tmp_path / "broken_dungeon"
    levels_dir = dungeon_dir / "levels"
    levels_dir.mkdir(parents=True)
    (dungeon_dir / "dungeon.yaml").write_text(
        "id: broken_dungeon\nname: Broken\nstarting_level: level_01\n"
        "pre_arrival_starting_level: level_01\n"
        "pre_arrival_until_year: 87\npre_arrival_until_day: 67\n",
        encoding="utf-8",
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

    with pytest.raises(ContentValidationError, match="same as starting_level"):
        load_dungeon(dungeon_dir, catalog)


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
    assert entity_names == (
        ["Debtor", "Escaped Prisoner", "Old Drillmaster", "Shopkeeper", "Town Guard", "Village Chief"]
        + ["Villager"] * 8
    )

    # every entity spawn carries its own per-spawn dialogue - no un-authored
    # villagers left in Millhaven now that this pass gave each one a line
    assert all(s.dialogue for s in level.entity_spawns)

    # regression guard: the town was regenerated at a much larger scale
    # (from 22x15) specifically so it wouldn't feel crowded again - keep it
    # from silently shrinking back down. Fourth pass deliberately walked
    # the footprint back down from an oversized 60x60 (see
    # content_design_process.md §0af - population-scaled footprint, not a
    # round generous number) to 50x40, still comfortably above this floor.
    assert level.width >= 30 and level.height >= 44 or level.width >= 44 and level.height >= 30

    assert [s.kind for s in level.stairs] == ["stairs_up"]
    assert level.stairs[0].next_level is None  # terminal - leaves to the overworld
    assert not any(s.kind == "stairs_down" for s in level.stairs)

    # the gate + the well, mending-yard, and chief's-doorstep landmarks
    assert len(level.tile_descriptions) == 4
    exit_stairs_x, exit_stairs_y = level.stairs[0].x, level.stairs[0].y
    desc = next(
        d for d in level.tile_descriptions if (d.x, d.y) == (exit_stairs_x, exit_stairs_y)
    )
    assert desc.text == "The town gate, leading back out onto the road."

    # third pass: the well, notice board, and mending yard each get their
    # own icon alongside the gate - four tile_sprite overrides total.
    assert len(level.tile_sprite_spawns) == 4
    assert {s.sprite_id for s in level.tile_sprite_spawns} == {
        "town_gate", "well", "notice_board", "mending_yard",
    }

    # regression guard: coverage, not just placement - a burying ground, a
    # tilled plot, and a practice range were added specifically because the
    # town felt mostly empty at this scale. Fourth pass walled off the
    # large empty NE quadrant and two other dead corners with an irregular
    # (non-rectangular) boundary rather than decorating space the road
    # network never reached - a handful of treeline cells inside the new
    # notch went with it, dropping the count from the third pass's 65 to
    # 58; the floor below reflects that as the new baseline, not a
    # loosening of the guard itself.
    decoration_kinds = {s.kind for s in level.decoration_spawns}
    assert {"tombstone", "tilled_soil", "archery_target"} <= decoration_kinds
    assert len(level.decoration_spawns) > 55


def test_load_level_collects_custom_tile_descriptions():
    catalog = load_catalog()
    level = load_level(FIXTURES_DIR / "only_stairs_up.lvl", catalog, require_stairs_down=False)
    assert level.tile_descriptions == []  # no legend entry sets description there


def test_load_level_collects_announce_flag_on_tile_descriptions(tmp_path):
    level_path = tmp_path / "with_announce.lvl"
    level_path.write_text(
        "id: with_announce\n"
        "name: Test Level\n"
        "map: |\n"
        "  ####\n"
        "  #@.#\n"
        "  #o.#\n"
        "  #>.#\n"
        "  ####\n"
        "legend:\n"
        '  "#": wall\n'
        '  ".": floor\n'
        '  "@": player_start\n'
        '  ">": stairs_down\n'
        '  "o": { tile: landmark, description: "A chalk board.", announce: true }\n',
        encoding="utf-8",
    )
    catalog = load_catalog()

    level = load_level(level_path, catalog)

    assert len(level.tile_descriptions) == 1
    assert level.tile_descriptions[0].text == "A chalk board."
    assert level.tile_descriptions[0].announce is True
    assert level.tile_descriptions[0].is_landmark is True


def test_load_level_stairs_up_description_is_not_a_landmark(tmp_path):
    """A flavorful tile that isn't `tile: landmark` (a gate/stairs) should
    never award discovery XP - see GameMap.landmark_announce_tiles."""
    level_path = tmp_path / "gate.lvl"
    level_path.write_text(
        "id: gate\n"
        "name: Test Level\n"
        "map: |\n"
        "  ####\n"
        "  #@.#\n"
        "  #x.#\n"
        "  #>.#\n"
        "  ####\n"
        "legend:\n"
        '  "#": wall\n'
        '  ".": floor\n'
        '  "@": player_start\n'
        '  ">": stairs_down\n'
        '  "x": { stairs_up: null, description: "The gate.", announce: true }\n',
        encoding="utf-8",
    )
    catalog = load_catalog()

    level = load_level(level_path, catalog)

    assert len(level.tile_descriptions) == 1
    assert level.tile_descriptions[0].is_landmark is False


def test_load_level_tile_description_without_announce_defaults_false(tmp_path):
    level_path = tmp_path / "no_announce.lvl"
    level_path.write_text(
        "id: no_announce\n"
        "name: Test Level\n"
        "map: |\n"
        "  ####\n"
        "  #@.#\n"
        "  #o.#\n"
        "  #>.#\n"
        "  ####\n"
        "legend:\n"
        '  "#": wall\n'
        '  ".": floor\n'
        '  "@": player_start\n'
        '  ">": stairs_down\n'
        '  "o": { tile: landmark, description: "A chalk board." }\n',
        encoding="utf-8",
    )
    catalog = load_catalog()

    level = load_level(level_path, catalog)

    assert level.tile_descriptions[0].announce is False


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


def test_load_level_collects_decoration_spawns(tmp_path):
    level_path = tmp_path / "with_decoration.lvl"
    level_path.write_text(
        "id: with_decoration\n"
        "name: Test Level\n"
        "map: |\n"
        "  ###\n"
        "  #@#\n"
        "  #t#\n"
        "  #>#\n"
        "  ###\n"
        "legend:\n"
        '  "#": wall\n'
        '  ".": floor\n'
        '  "@": player_start\n'
        '  ">": stairs_down\n'
        '  "t": { tile: floor, decoration: table }\n',
        encoding="utf-8",
    )
    catalog = load_catalog()

    level = load_level(level_path, catalog)

    assert len(level.decoration_spawns) == 1
    assert level.decoration_spawns[0].kind == "table"
    assert (level.decoration_spawns[0].x, level.decoration_spawns[0].y) == (1, 2)
    # a decoration spawn is not an entity/item spawn - the three are independent
    assert level.entity_spawns == []
    assert level.item_spawns == []


def test_load_level_decoration_coexists_with_entity_spawn(tmp_path):
    level_path = tmp_path / "with_both.lvl"
    level_path.write_text(
        "id: with_both\n"
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
        '  "v": { entity: villager, tile: plains, decoration: bush }\n',
        encoding="utf-8",
    )
    catalog = load_catalog()

    level = load_level(level_path, catalog)

    assert len(level.entity_spawns) == 1
    assert len(level.decoration_spawns) == 1
    assert level.decoration_spawns[0].kind == "bush"


def test_load_level_collects_tile_sprite_spawns(tmp_path):
    level_path = tmp_path / "with_tile_sprite.lvl"
    level_path.write_text(
        "id: with_tile_sprite\n"
        "name: Test Level\n"
        "map: |\n"
        "  ####\n"
        "  #@.#\n"
        "  #g>#\n"
        "  ####\n"
        "legend:\n"
        '  "#": wall\n'
        '  ".": floor\n'
        '  "@": player_start\n'
        '  ">": stairs_down\n'
        '  "g": { tile: stairs_up, next_level: null, tile_sprite: town_gate }\n',
        encoding="utf-8",
    )
    catalog = load_catalog()

    level = load_level(level_path, catalog)

    assert len(level.tile_sprite_spawns) == 1
    assert level.tile_sprite_spawns[0].sprite_id == "town_gate"
    assert (level.tile_sprite_spawns[0].x, level.tile_sprite_spawns[0].y) == (1, 2)


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


def test_load_level_collects_per_spawn_flag_dialogue(tmp_path):
    level_path = tmp_path / "with_flag_dialogue.lvl"
    level_path.write_text(
        "id: with_flag_dialogue\n"
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
        '  "v": { entity: villager, flag_dialogue: [{ flag: wayford_razed, line: "It is gone." }] }\n',
        encoding="utf-8",
    )
    catalog = load_catalog()

    level = load_level(level_path, catalog)

    assert len(level.entity_spawns) == 1
    assert level.entity_spawns[0].flag_dialogue == [FlagDialogue(flag="wayford_razed", line="It is gone.")]


def test_load_level_collects_elite_entity_spawn(tmp_path):
    level_path = tmp_path / "with_elite.lvl"
    level_path.write_text(
        "id: with_elite\n"
        "name: Test Level\n"
        "map: |\n"
        "  ###\n"
        "  #@#\n"
        "  #g#\n"
        "  #>#\n"
        "  ###\n"
        "legend:\n"
        '  "#": wall\n'
        '  ".": floor\n'
        '  "@": player_start\n'
        '  ">": stairs_down\n'
        '  "g": { entity: goblin, elite: true }\n',
        encoding="utf-8",
    )
    catalog = load_catalog()

    level = load_level(level_path, catalog)

    assert len(level.entity_spawns) == 1
    assert level.entity_spawns[0].elite is True


def test_load_level_entity_spawn_without_elite_defaults_false(tmp_path):
    level_path = tmp_path / "no_elite.lvl"
    level_path.write_text(
        "id: no_elite\n"
        "name: Test Level\n"
        "map: |\n"
        "  ###\n"
        "  #@#\n"
        "  #g#\n"
        "  #>#\n"
        "  ###\n"
        "legend:\n"
        '  "#": wall\n'
        '  ".": floor\n'
        '  "@": player_start\n'
        '  ">": stairs_down\n'
        '  "g": { entity: goblin }\n',
        encoding="utf-8",
    )
    catalog = load_catalog()

    level = load_level(level_path, catalog)

    assert level.entity_spawns[0].elite is False


def test_load_level_rejects_elite_on_a_peaceful_entity(tmp_path):
    level_path = tmp_path / "elite_villager.lvl"
    level_path.write_text(
        "id: elite_villager\n"
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
        '  "v": { entity: villager, elite: true }\n',
        encoding="utf-8",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="elite only makes sense for a real hostile encounter"):
        load_level(level_path, catalog)


def test_load_level_entity_spawn_without_flag_dialogue_defaults_to_empty_list(tmp_path):
    level_path = tmp_path / "no_flag_dialogue.lvl"
    level_path.write_text(
        "id: no_flag_dialogue\n"
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

    assert level.entity_spawns[0].flag_dialogue == []


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
    "goblin_ambush",
    "grey_valley_monastery",
    "silver_mountain_caves",
    "the_windrest",
    "farrows_stake",
    "sunless_hollow",
    "visitor_band_ambush",
    "northern_watch_post",
}

COMBAT_DUNGEON_IDS = ["broken_watch", "drowned_waystation", "elder_cairn", "sunken_mine", "the_windrest", "sunless_hollow"]
SETTLEMENT_DUNGEON_IDS = ["wayford", "stonebridge", "saltmarsh", "grey_valley_monastery", "farrows_stake", "northern_watch_post"]


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
    assert all(e.ai in ("villager", "town_guard") for e in all_entities)


def test_goblin_ambush_uses_open_boundary_instead_of_a_stairway():
    catalog = load_catalog()
    dungeon = load_dungeon(DUNGEONS_DIR / "goblin_ambush", catalog)

    assert dungeon.requires_stairs_down is False
    level = dungeon.levels["level_01"]
    assert level.open_boundary is True
    assert level.open_boundary_message != ""
    assert level.stairs == []

    goblin_names = [s.entity.name for s in level.entity_spawns]
    assert goblin_names == ["Goblin", "Goblin", "Goblin"]


def test_visitor_band_ambush_ground_looks_corrupted_but_is_not_hazardous():
    """The arena's ground is scoured_ground, not ashen_plains - visually
    identical (same TILE_VISUALS/sprite), but deliberately not one of the
    kinds Engine._apply_environmental_hazard punishes for lingering. A
    monster band is already the danger here; the ground doesn't need to be
    too (see docs/dungeon_bibles/visitor_band_ambush.md)."""
    catalog = load_catalog()
    dungeon = load_dungeon(DUNGEONS_DIR / "visitor_band_ambush", catalog)
    level = dungeon.levels["level_01"]

    kinds = {tile for row in level.tiles for tile in row}
    assert "scoured_ground" in kinds
    assert "ashen_plains" not in kinds
    assert level.player_start_tile == "scoured_ground"


def test_prison_tower_level_01_content():
    catalog = load_catalog()
    level = load_level(PRISON_TOWER_LEVELS_DIR / "level_01.lvl", catalog)

    entity_names = sorted(s.entity.name for s in level.entity_spawns)
    assert entity_names == ["Crossbow Guard", "Guard"]

    item_names = sorted(s.item.name for s in level.item_spawns)
    assert item_names == ["Gold Pile", "Healing Potion", "Hunting Bow", "Rusty Dagger", "Thorned Plate"]


def test_prison_tower_level_02_content():
    catalog = load_catalog()
    level = load_level(PRISON_TOWER_LEVELS_DIR / "level_02.lvl", catalog)

    item_names = sorted(s.item.name for s in level.item_spawns)
    assert item_names == ["Gold Pile", "Iron Sword", "Rusty Key"]


def test_prison_tower_level_04_content():
    catalog = load_catalog()
    level = load_level(PRISON_TOWER_LEVELS_DIR / "level_04.lvl", catalog)

    item_names = sorted(s.item.name for s in level.item_spawns)
    assert item_names == ["Gold Stash"]


def test_sunken_mine_gold_placements():
    catalog = load_catalog()
    levels = load_levels(SUNKEN_MINE_LEVELS_DIR, catalog)

    item_names_by_level = {
        level_id: sorted(s.item.name for s in level.item_spawns)
        for level_id, level in levels.items()
    }
    assert "Gold Pile" in item_names_by_level["level_01"]
    assert "Gold Stash" in item_names_by_level["level_02"]
    assert "Gold Pile" in item_names_by_level["level_03"]


def test_sunken_mine_level_02_has_the_pale_fungus():
    catalog = load_catalog()
    level = load_level(SUNKEN_MINE_LEVELS_DIR / "level_02.lvl", catalog)

    item_names = [s.item.name for s in level.item_spawns]
    assert "Pale Fungus" in item_names


def test_sunken_mine_level_01_has_the_kobold_warren():
    catalog = load_catalog()
    level = load_level(SUNKEN_MINE_LEVELS_DIR / "level_01.lvl", catalog)

    entity_names = sorted(s.entity.name for s in level.entity_spawns)
    assert entity_names.count("Kobold") == 2
    assert "Kobold Shaman" in entity_names


def test_sunken_mine_level_03_has_the_orc_guarding_the_last_vein():
    catalog = load_catalog()
    level = load_level(SUNKEN_MINE_LEVELS_DIR / "level_03.lvl", catalog)

    entity_names = [s.entity.name for s in level.entity_spawns]
    assert "Orc" in entity_names


def test_broken_watch_level_01_has_a_giant_rat():
    catalog = load_catalog()
    level = load_level(BROKEN_WATCH_LEVELS_DIR / "level_01.lvl", catalog)

    entity_names = [s.entity.name for s in level.entity_spawns]
    assert "Giant Rat" in entity_names


def test_silver_mountain_caves_level_02_has_a_giant_spider():
    catalog = load_catalog()
    level = load_level(SILVER_MOUNTAIN_CAVES_LEVELS_DIR / "level_02.lvl", catalog)

    entity_names = [s.entity.name for s in level.entity_spawns]
    assert "Giant Spider" in entity_names


def test_silver_mountain_caves_level_02_rockfall_now_leads_deeper():
    """The Sealed Passage (docs/dungeon_bibles/silver_mountain_caves.md) is
    a real stairs_down now, not a landmark - the long-flagged hook this
    pass finally builds."""
    catalog = load_catalog()
    level = load_level(SILVER_MOUNTAIN_CAVES_LEVELS_DIR / "level_02.lvl", catalog)

    assert any(s.kind == "stairs_down" and s.next_level == "level_03" for s in level.stairs)


@pytest.mark.parametrize(
    "level_id, up_target, down_target, roster",
    [
        ("level_03", "level_02", "level_04", {"Deep Spider", "Blind Stalker"}),
        ("level_04", "level_03", "level_05", {"Deep Spider", "Cave Lurker", "Broodmother"}),
        ("level_05", "level_04", None, {"Deep Spider", "Blind Stalker", "Cave Lurker", "Elder Widow"}),
    ],
)
def test_silver_mountain_caves_depths_are_linked_and_populated(level_id, up_target, down_target, roster):
    catalog = load_catalog()
    level = load_level(SILVER_MOUNTAIN_CAVES_LEVELS_DIR / f"{level_id}.lvl", catalog)

    assert any(s.kind == "stairs_up" and s.next_level == up_target for s in level.stairs)
    assert any(s.kind == "stairs_down" and s.next_level == down_target for s in level.stairs)

    entity_names = {s.entity.name for s in level.entity_spawns}
    assert roster <= entity_names


def test_silver_mountain_caves_depths_are_fully_reachable_from_player_start():
    """Every monster/item/stairs tile on each new level must be reachable
    from that level's own player_start via ordinary 8-directional
    movement - the same discipline the overworld's own entrance-reachability
    test holds every dungeon_entrance to, applied here since these levels
    were generated (cellular-automata cave carving, see
    docs/content_design_process.md §0ae) rather than hand-drawn."""
    from collections import deque

    catalog = load_catalog()
    for level_id in ("level_03", "level_04", "level_05"):
        level = load_level(SILVER_MOUNTAIN_CAVES_LEVELS_DIR / f"{level_id}.lvl", catalog)
        game_map, _ = build_game_map(level, catalog)

        seen = {level.player_start}
        queue = deque([level.player_start])
        while queue:
            x, y = queue.popleft()
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = x + dx, y + dy
                    if (nx, ny) not in seen and game_map.is_walkable(nx, ny):
                        seen.add((nx, ny))
                        queue.append((nx, ny))

        for spawn in level.entity_spawns:
            assert (spawn.x, spawn.y) in seen, f"{level_id}: {spawn.entity.name} at ({spawn.x},{spawn.y}) is unreachable"
        for spawn in level.item_spawns:
            assert (spawn.x, spawn.y) in seen, f"{level_id}: item at ({spawn.x},{spawn.y}) is unreachable"
        for stairs in level.stairs:
            assert (stairs.x, stairs.y) in seen, f"{level_id}: stairs at ({stairs.x},{stairs.y}) is unreachable"


def test_forgotten_ruins_level_02b_has_a_hobgoblin_leading_the_warren():
    catalog = load_catalog()
    level = load_level(FORGOTTEN_RUINS_LEVELS_DIR / "level_02b.lvl", catalog)

    entity_names = [s.entity.name for s in level.entity_spawns]
    assert "Hobgoblin" in entity_names


def test_prison_tower_chain_links_all_levels():
    catalog = load_catalog()
    levels = load_levels(PRISON_TOWER_LEVELS_DIR, catalog)

    assert set(levels) == {"level_01", "level_02", "level_03", "level_04"}
    # level_01's first stairway is its retreat stairs_up (terminal, leaves to
    # the overworld), scanned before the stairs_down branch below it.
    assert [s.next_level for s in levels["level_01"].stairs] == [None, "level_02"]
    # level_02 also has a stairs_up back to level_01 (the return-trip example).
    assert [s.next_level for s in levels["level_02"].stairs] == ["level_01", "level_03"]
    assert [s.next_level for s in levels["level_03"].stairs] == ["level_04"]
    assert [s.next_level for s in levels["level_04"].stairs] == [None]


def test_load_overworld_happy_path():
    catalog = load_catalog()
    level = load_overworld(
        FIXTURES_DIR / "overworld_valid", catalog, known_dungeon_ids={"prison_tower"}
    )

    assert level.id == "overworld_valid"
    assert level.player_start == (1, 1)
    assert [e.dungeon_id for e in level.dungeon_entrances] == ["prison_tower"]
    assert level.stairs == []
    assert level.entity_spawns == []
    assert level.item_spawns == []


def test_load_overworld_collects_announce_flag_on_tile_descriptions(tmp_path):
    overworld_dir = tmp_path / "overworld_announce"
    (overworld_dir / "cells").mkdir(parents=True)
    (overworld_dir / "cells.lvl").write_text(
        "id: overworld_announce\n"
        "name: Test Overworld\n"
        "map: |\n"
        "  A\n"
        "legend:\n"
        '  "A": main\n',
        encoding="utf-8",
    )
    (overworld_dir / "cells" / "main.lvl").write_text(
        "id: main\n"
        "name: Main Cell\n"
        "map: |\n"
        "  #####\n"
        "  #@.P#\n"
        "  #####\n"
        "legend:\n"
        '  "#": mountain\n'
        '  ".": plains\n'
        '  "@": player_start\n'
        '  "P": { dungeon_entrance: prison_tower, description: "A black stone tower.", announce: true }\n',
        encoding="utf-8",
    )
    catalog = load_catalog()

    level = load_overworld(overworld_dir, catalog, known_dungeon_ids={"prison_tower"})

    assert len(level.tile_descriptions) == 1
    assert level.tile_descriptions[0].announce is True


def test_load_overworld_rejects_unknown_dungeon_id():
    catalog = load_catalog()
    with pytest.raises(ContentValidationError, match="unknown dungeon 'no_such_dungeon'"):
        load_overworld(
            FIXTURES_DIR / "overworld_unknown_dungeon", catalog,
            known_dungeon_ids={"prison_tower"},
        )


def test_load_overworld_rejects_ambiguous_entrances_to_the_same_dungeon():
    catalog = load_catalog()
    with pytest.raises(ContentValidationError, match="ambiguous which one is the return path"):
        load_overworld(
            FIXTURES_DIR / "overworld_ambiguous_entrances", catalog,
            known_dungeon_ids={"prison_tower"},
        )


def test_load_overworld_requires_at_least_one_dungeon_entrance():
    catalog = load_catalog()
    with pytest.raises(ContentValidationError, match="at least one dungeon_entrance"):
        load_overworld(
            FIXTURES_DIR / "overworld_no_entrance", catalog, known_dungeon_ids={"prison_tower"}
        )


def test_load_overworld_rejects_stairs_tiles():
    catalog = load_catalog()
    with pytest.raises(ContentValidationError, match="stairs_down.*has no meaning on the overworld"):
        load_overworld(
            FIXTURES_DIR / "overworld_with_stairs", catalog, known_dungeon_ids={"prison_tower"}
        )


def test_load_overworld_rejects_unknown_cell_id(tmp_path):
    overworld_dir = tmp_path / "overworld_bad_cell"
    (overworld_dir / "cells").mkdir(parents=True)
    (overworld_dir / "cells.lvl").write_text(
        "id: overworld_bad_cell\n"
        "name: Test Overworld\n"
        "map: |\n"
        "  A\n"
        "legend:\n"
        '  "A": nonexistent\n',
        encoding="utf-8",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match="references cell 'nonexistent'"):
        load_overworld(overworld_dir, catalog, known_dungeon_ids={"prison_tower"})


def test_load_overworld_rejects_a_bad_cells_own_content_naming_that_cell(tmp_path):
    """A per-cell content error (not a cells.lvl-level problem) must name
    the actual offending cell file, not the umbrella cells.lvl."""
    overworld_dir = tmp_path / "overworld_bad_cell_content"
    (overworld_dir / "cells").mkdir(parents=True)
    (overworld_dir / "cells.lvl").write_text(
        "id: overworld_bad_cell_content\n"
        "name: Test Overworld\n"
        "map: |\n"
        "  A\n"
        "legend:\n"
        '  "A": main\n',
        encoding="utf-8",
    )
    (overworld_dir / "cells" / "main.lvl").write_text(
        "id: main\n"
        "name: Main Cell\n"
        "map: |\n"
        "  #####\n"
        "  #@xP#\n"
        "  #####\n"
        "legend:\n"
        '  "#": mountain\n'
        '  ".": plains\n'
        '  "@": player_start\n'
        '  "x": stairs_down\n'
        '  "P": { dungeon_entrance: prison_tower }\n',
        encoding="utf-8",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match=r"main\.lvl.*stairs_down.*has no meaning"):
        load_overworld(overworld_dir, catalog, known_dungeon_ids={"prison_tower"})


def test_load_overworld_rejects_a_cell_with_mismatched_dimensions(tmp_path):
    overworld_dir = tmp_path / "overworld_mismatched_cells"
    (overworld_dir / "cells").mkdir(parents=True)
    (overworld_dir / "cells.lvl").write_text(
        "id: overworld_mismatched_cells\n"
        "name: Test Overworld\n"
        "map: |\n"
        "  AB\n"
        "legend:\n"
        '  "A": first\n'
        '  "B": second\n',
        encoding="utf-8",
    )
    (overworld_dir / "cells" / "first.lvl").write_text(
        "id: first\n"
        "name: First Cell\n"
        "map: |\n"
        "  ###\n"
        "  #@#\n"
        "  #P#\n"
        "  ###\n"
        "legend:\n"
        '  "#": mountain\n'
        '  "@": player_start\n'
        '  "P": { dungeon_entrance: prison_tower }\n',
        encoding="utf-8",
    )
    (overworld_dir / "cells" / "second.lvl").write_text(
        "id: second\n"
        "name: Second Cell\n"
        "map: |\n"
        "  ##\n"
        "  ##\n"
        "legend:\n"
        '  "#": mountain\n',
        encoding="utf-8",
    )
    catalog = load_catalog()

    with pytest.raises(ContentValidationError, match=r"second.*expected 3x4.*got 2x2"):
        load_overworld(overworld_dir, catalog, known_dungeon_ids={"prison_tower"})


def test_load_overworld_stitches_a_multi_cell_grid():
    """2x1 grid of small, visually-distinguishable synthetic cells -
    proves tile-array concatenation order and coordinate offsetting are
    both correct, not just that a single cell still works."""
    catalog = load_catalog()
    fixtures_dir = FIXTURES_DIR / "overworld_multi_cell"

    level = load_overworld(fixtures_dir, catalog, known_dungeon_ids={"prison_tower", "wayford"})

    assert (level.width, level.height) == (6, 3)
    # left cell (mountain) occupies columns 0-2, right cell (forest)
    # occupies columns 3-5 - row 0/2 have no special tiles in either
    # cell, proving horizontal concatenation didn't interleave or
    # reorder the two cells' rows.
    assert level.tiles[0] == ["mountain", "mountain", "mountain", "forest", "forest", "forest"]
    assert level.tiles[2] == ["mountain", "mountain", "mountain", "forest", "forest", "forest"]
    # player_start lives in the left cell at local (0, 1) -> global (0, 1) (first cell, no offset).
    assert level.player_start == (0, 1)
    entrances = {(e.x, e.y): e.dungeon_id for e in level.dungeon_entrances}
    # prison_tower's entrance is local (2,1) in the left cell -> global (2,1).
    assert entrances[(2, 1)] == "prison_tower"
    # wayford's entrance is local (1,1) in the right cell -> global (4,1),
    # i.e. offset by the left cell's own width (3).
    assert entrances[(4, 1)] == "wayford"


def test_load_overworld_rejects_two_cells_targeting_the_same_dungeon():
    """A cross-cell duplicate dungeon_entrance target is impossible to
    detect per-cell (each cell's own entrance is perfectly valid in
    isolation) - only a whole-grid, post-assembly check catches it."""
    catalog = load_catalog()
    fixtures_dir = FIXTURES_DIR / "overworld_duplicate_entrance_across_cells"

    with pytest.raises(ContentValidationError, match="ambiguous which one is the return path"):
        load_overworld(fixtures_dir, catalog, known_dungeon_ids={"prison_tower"})


def test_load_overworld_real_shipped_content_is_a_pure_stitch_of_its_two_cells():
    """Regression test for the overworld cell-grid: today's real content is
    a 1x2 grid, Northern Steppe (row 0, north) stacked on Heartlands (row 1,
    south) - the assembled overworld's Heartlands half must be byte-for-byte
    identical to that cell's own raw parse (offset by Northern Steppe's
    height), proving the stitcher didn't disturb already-shipped content
    when a second cell was added above it. Scalar facts below were captured
    directly from the real assembled output when this pass landed."""
    catalog = load_catalog()
    dungeon_registry = load_dungeon_registry(DUNGEONS_DIR, catalog)
    known_dungeon_ids = set(dungeon_registry)

    overworld = load_overworld(OVERWORLD_DIR, catalog, known_dungeon_ids=known_dungeon_ids)

    assert overworld.id == "overworld"
    assert overworld.name == "The Sundered Realm"
    assert overworld.width == 150
    assert overworld.height == 180
    assert overworld.player_start == (29, 136)
    assert overworld.player_start_tile == "plains"
    assert len(overworld.dungeon_entrances) == 16  # heartlands' 15 (windbreak_hold retired, folded into farrows_stake) + Northern Steppe's first, the Watch Post
    assert len(overworld.tile_descriptions) == 6  # heartlands' 3 signposts + Northern Steppe's 3 remaining landmarks

    heartlands, cell_errors = _parse_overworld_cell(
        OVERWORLD_DIR / "cells" / "heartlands.lvl", catalog, known_dungeon_ids=known_dungeon_ids,
    )
    assert cell_errors == []
    y_offset = overworld.height - heartlands.height  # Northern Steppe's own height (row 0 of the grid)
    assert overworld.width == heartlands.width
    assert overworld.tiles[y_offset:] == heartlands.tiles
    hx, hy = heartlands.player_starts[0]
    assert overworld.player_start == (hx, hy + y_offset)
    # Only the entrances actually inside the Heartlands portion (y >= y_offset) -
    # the Northern Steppe now has its own first entrance (the Watch Post),
    # which has no counterpart in heartlands.lvl and would otherwise show up
    # as a spurious mismatch here.
    assert {(e.x, e.y - y_offset, e.dungeon_id) for e in overworld.dungeon_entrances if e.y >= y_offset} == {
        (e.x, e.y, e.dungeon_id) for e in heartlands.dungeon_entrances
    }
    heartlands_descriptions = {(d.x, d.y, d.text) for d in heartlands.tile_descriptions}
    assert {(d.x, d.y - y_offset, d.text) for d in overworld.tile_descriptions} >= heartlands_descriptions


def test_load_overworld_northern_steppe_cell_has_its_first_dungeon():
    """The Northern Steppe's first real dungeon - the Watch Post
    (see docs/region_bibles/northern_steppe.md, docs/dungeon_bibles/
    northern_watch_post.md) - replaces what was originally a `landmark`-only
    placeholder; the region's other three reserved locations (the goblin
    homeland, two Elder Age sites) are still landmarks, no dungeons yet."""
    catalog = load_catalog()
    dungeon_registry = load_dungeon_registry(DUNGEONS_DIR, catalog)
    known_dungeon_ids = set(dungeon_registry)

    steppe, cell_errors = _parse_overworld_cell(
        OVERWORLD_DIR / "cells" / "northern_steppe.lvl", catalog, known_dungeon_ids=known_dungeon_ids,
    )

    assert cell_errors == []
    assert steppe.width == 150
    assert steppe.height == 90
    assert steppe.player_starts == []
    assert len(steppe.dungeon_entrances) == 1
    assert steppe.dungeon_entrances[0].dungeon_id == "northern_watch_post"
    assert len(steppe.tile_descriptions) == 3
    kinds = {tile for row in steppe.tiles for tile in row}
    assert "ashen_plains" in kinds
    assert "blighted_forest" in kinds


def test_load_level_rejects_dungeon_entrance_tiles():
    catalog = load_catalog()
    with pytest.raises(ContentValidationError, match="dungeon_entrance.*has no meaning inside a dungeon"):
        load_level(FIXTURES_DIR / "level_with_dungeon_entrance.lvl", catalog)


def test_load_sprite_manifest_loads_a_valid_minimal_manifest(tmp_path):
    catalog = load_catalog()
    path = tmp_path / "sprites.yaml"
    path.write_text(
        "sheets:\n"
        "  rltiles:\n"
        "    image: rltiles-2d.png\n"
        "    index: rltiles-2d.json\n"
        "    tile_size: 32\n"
        "  kenney:\n"
        "    image: roguelikeSheet_transparent.png\n"
        "    tile_size: 16\n"
        "    columns: 57\n"
        "    rows: 31\n"
        "entities:\n"
        "  rat: {sheet: rltiles, name: rat}\n"
        "items:\n"
        "  road_ledger: {sheet: kenney, col: 44, row: 15}\n"
        "tile_kinds:\n"
        "  sea: {sheet: kenney, col: 0, row: 2}\n",
        encoding="utf-8",
    )

    manifest = load_sprite_manifest(path, catalog)

    assert manifest.entities["rat"].name == "rat"
    assert manifest.items["road_ledger"].col == 44
    assert manifest.tile_kinds["sea"].row == 2


def test_load_sprite_manifest_accepts_the_reserved_player_id(tmp_path):
    """"player" isn't a real catalog entity (it's hardcoded in
    engine/game_map.py) - load_sprite_manifest allows it anyway, see
    content.loader.PLAYER_ENTITY_ID."""
    catalog = load_catalog()
    path = tmp_path / "sprites.yaml"
    path.write_text(
        "sheets:\n"
        "  rltiles:\n"
        "    image: rltiles-2d.png\n"
        "    index: rltiles-2d.json\n"
        "    tile_size: 32\n"
        "entities:\n"
        "  player: {sheet: rltiles, name: warrior}\n",
        encoding="utf-8",
    )

    manifest = load_sprite_manifest(path, catalog)

    assert manifest.entities["player"].name == "warrior"


def test_load_sprite_manifest_rejects_recolor_on_the_player_entry(tmp_path):
    catalog = load_catalog()
    path = tmp_path / "sprites.yaml"
    path.write_text(
        "sheets:\n"
        "  rltiles:\n"
        "    image: rltiles-2d.png\n"
        "    index: rltiles-2d.json\n"
        "    tile_size: 32\n"
        "entities:\n"
        "  player: {sheet: rltiles, name: warrior, recolor: true}\n",
        encoding="utf-8",
    )

    with pytest.raises(ContentValidationError, match="the player has no EntityDef/.color field"):
        load_sprite_manifest(path, catalog)


def test_load_sprite_manifest_rejects_unknown_entity_id(tmp_path):
    catalog = load_catalog()
    path = tmp_path / "sprites.yaml"
    path.write_text(
        "sheets:\n"
        "  rltiles:\n"
        "    image: rltiles-2d.png\n"
        "    index: rltiles-2d.json\n"
        "    tile_size: 32\n"
        "entities:\n"
        "  nonexistent_creature: {sheet: rltiles, name: rat}\n",
        encoding="utf-8",
    )

    with pytest.raises(ContentValidationError, match="unknown entity id"):
        load_sprite_manifest(path, catalog)


def test_load_sprite_manifest_rejects_unrecognized_tile_kind(tmp_path):
    catalog = load_catalog()
    path = tmp_path / "sprites.yaml"
    path.write_text(
        "sheets:\n"
        "  kenney:\n"
        "    image: roguelikeSheet_transparent.png\n"
        "    tile_size: 16\n"
        "    columns: 57\n"
        "    rows: 31\n"
        "tile_kinds:\n"
        "  player_start: {sheet: kenney, col: 0, row: 0}\n",
        encoding="utf-8",
    )

    with pytest.raises(ContentValidationError, match="not a recognized tile kind"):
        load_sprite_manifest(path, catalog)


def test_load_sprite_manifest_accepts_a_valid_decoration(tmp_path):
    catalog = load_catalog()
    path = tmp_path / "sprites.yaml"
    path.write_text(
        "sheets:\n"
        "  kenney:\n"
        "    image: roguelikeSheet_transparent.png\n"
        "    tile_size: 16\n"
        "    columns: 57\n"
        "    rows: 31\n"
        "decorations:\n"
        "  table: {sheet: kenney, col: 18, row: 5}\n",
        encoding="utf-8",
    )

    manifest = load_sprite_manifest(path, catalog)

    assert manifest.decorations["table"].col == 18


def test_load_sprite_manifest_rejects_unrecognized_decoration_kind(tmp_path):
    catalog = load_catalog()
    path = tmp_path / "sprites.yaml"
    path.write_text(
        "sheets:\n"
        "  kenney:\n"
        "    image: roguelikeSheet_transparent.png\n"
        "    tile_size: 16\n"
        "    columns: 57\n"
        "    rows: 31\n"
        "decorations:\n"
        "  hot_tub: {sheet: kenney, col: 0, row: 0}\n",
        encoding="utf-8",
    )

    with pytest.raises(ContentValidationError, match="not a recognized decoration kind"):
        load_sprite_manifest(path, catalog)


def test_load_sprite_manifest_rejects_backdrop_on_a_decoration(tmp_path):
    catalog = load_catalog()
    path = tmp_path / "sprites.yaml"
    path.write_text(
        "sheets:\n"
        "  kenney:\n"
        "    image: roguelikeSheet_transparent.png\n"
        "    tile_size: 16\n"
        "    columns: 57\n"
        "    rows: 31\n"
        "tile_kinds:\n"
        "  plains: {sheet: kenney, col: 5, row: 0}\n"
        "decorations:\n"
        "  table: {sheet: kenney, col: 18, row: 5, backdrop: plains}\n",
        encoding="utf-8",
    )

    with pytest.raises(ContentValidationError, match="backdrop is only meaningful"):
        load_sprite_manifest(path, catalog)


def test_load_sprite_manifest_rejects_recolor_on_a_decoration(tmp_path):
    catalog = load_catalog()
    path = tmp_path / "sprites.yaml"
    path.write_text(
        "sheets:\n"
        "  kenney:\n"
        "    image: roguelikeSheet_transparent.png\n"
        "    tile_size: 16\n"
        "    columns: 57\n"
        "    rows: 31\n"
        "decorations:\n"
        "  table: {sheet: kenney, col: 18, row: 5, recolor: true}\n",
        encoding="utf-8",
    )

    with pytest.raises(ContentValidationError, match="recolor is only meaningful"):
        load_sprite_manifest(path, catalog)


def test_load_sprite_manifest_accepts_a_valid_tile_sprite_override(tmp_path):
    catalog = load_catalog()
    path = tmp_path / "sprites.yaml"
    path.write_text(
        "sheets:\n"
        "  rltiles:\n"
        "    image: rltiles-2d.png\n"
        "    index: rltiles-2d.json\n"
        "    tile_size: 32\n"
        "tile_sprite_overrides:\n"
        "  town_gate: {sheet: rltiles, name: dngn_stone_arch}\n",
        encoding="utf-8",
    )

    manifest = load_sprite_manifest(path, catalog)

    assert manifest.tile_sprite_overrides["town_gate"].name == "dngn_stone_arch"


def test_load_sprite_manifest_accepts_multiple_col_row_tile_sprite_overrides(tmp_path):
    """Millhaven's third pass gives the well/notice board/mending yard each
    their own icon alongside the gate - a col/row-addressed sheet (Kenney's
    tiny_town), not the name-addressed rltiles the gate itself uses."""
    catalog = load_catalog()
    path = tmp_path / "sprites.yaml"
    path.write_text(
        "sheets:\n"
        "  kenney_tiny_town:\n"
        "    image: tiny_town_tilemap.png\n"
        "    tile_size: 16\n"
        "    columns: 12\n"
        "    rows: 11\n"
        "tile_sprite_overrides:\n"
        "  well:         {sheet: kenney_tiny_town, col: 8,  row: 8}\n"
        "  notice_board: {sheet: kenney_tiny_town, col: 11, row: 6}\n"
        "  mending_yard: {sheet: kenney_tiny_town, col: 8,  row: 9}\n",
        encoding="utf-8",
    )

    manifest = load_sprite_manifest(path, catalog)

    assert manifest.tile_sprite_overrides["well"].col == 8
    assert manifest.tile_sprite_overrides["notice_board"].row == 6
    assert manifest.tile_sprite_overrides["mending_yard"].col == 8


def test_load_sprite_manifest_rejects_an_unknown_sheet_on_a_tile_sprite_override(tmp_path):
    catalog = load_catalog()
    path = tmp_path / "sprites.yaml"
    path.write_text(
        "sheets: {}\n"
        "tile_sprite_overrides:\n"
        "  town_gate: {sheet: nonexistent, name: dngn_stone_arch}\n",
        encoding="utf-8",
    )

    with pytest.raises(ContentValidationError, match="unknown sheet"):
        load_sprite_manifest(path, catalog)


def test_load_sprite_manifest_rejects_a_tile_sprite_override_backdrop_not_in_tile_kinds(tmp_path):
    catalog = load_catalog()
    path = tmp_path / "sprites.yaml"
    path.write_text(
        "sheets:\n"
        "  rltiles:\n"
        "    image: rltiles-2d.png\n"
        "    index: rltiles-2d.json\n"
        "    tile_size: 32\n"
        "tile_sprite_overrides:\n"
        "  town_gate: {sheet: rltiles, name: dngn_stone_arch, backdrop: nonexistent_kind}\n",
        encoding="utf-8",
    )

    with pytest.raises(ContentValidationError, match="not a tile_kinds entry"):
        load_sprite_manifest(path, catalog)


def test_load_sprite_manifest_rejects_recolor_on_a_tile_sprite_override(tmp_path):
    catalog = load_catalog()
    path = tmp_path / "sprites.yaml"
    path.write_text(
        "sheets:\n"
        "  rltiles:\n"
        "    image: rltiles-2d.png\n"
        "    index: rltiles-2d.json\n"
        "    tile_size: 32\n"
        "tile_sprite_overrides:\n"
        "  town_gate: {sheet: rltiles, name: dngn_stone_arch, recolor: true}\n",
        encoding="utf-8",
    )

    with pytest.raises(ContentValidationError, match="recolor is only meaningful"):
        load_sprite_manifest(path, catalog)


def test_load_sprite_manifest_rejects_both_name_and_col_row_set(tmp_path):
    catalog = load_catalog()
    path = tmp_path / "sprites.yaml"
    path.write_text(
        "sheets:\n"
        "  rltiles:\n"
        "    image: rltiles-2d.png\n"
        "    index: rltiles-2d.json\n"
        "    tile_size: 32\n"
        "entities:\n"
        "  rat: {sheet: rltiles, name: rat, col: 0, row: 0}\n",
        encoding="utf-8",
    )

    with pytest.raises(ContentValidationError, match=r"set either 'name' or 'col'\+'row', not both"):
        load_sprite_manifest(path, catalog)


def test_load_sprite_manifest_rejects_neither_name_nor_col_row_set(tmp_path):
    catalog = load_catalog()
    path = tmp_path / "sprites.yaml"
    path.write_text(
        "sheets:\n"
        "  rltiles:\n"
        "    image: rltiles-2d.png\n"
        "    index: rltiles-2d.json\n"
        "    tile_size: 32\n"
        "entities:\n"
        "  rat: {sheet: rltiles}\n",
        encoding="utf-8",
    )

    with pytest.raises(ContentValidationError, match=r"must set either 'name' or 'col'\+'row'"):
        load_sprite_manifest(path, catalog)


def test_load_sprite_manifest_rejects_an_unknown_sheet(tmp_path):
    catalog = load_catalog()
    path = tmp_path / "sprites.yaml"
    path.write_text(
        "sheets: {}\n"
        "entities:\n"
        "  rat: {sheet: nonexistent_sheet, name: rat}\n",
        encoding="utf-8",
    )

    with pytest.raises(ContentValidationError, match="unknown sheet 'nonexistent_sheet'"):
        load_sprite_manifest(path, catalog)


def test_load_sprite_manifest_rejects_name_addressing_against_an_index_less_sheet(tmp_path):
    catalog = load_catalog()
    path = tmp_path / "sprites.yaml"
    path.write_text(
        "sheets:\n"
        "  kenney:\n"
        "    image: roguelikeSheet_transparent.png\n"
        "    tile_size: 16\n"
        "    columns: 57\n"
        "    rows: 31\n"
        "entities:\n"
        "  rat: {sheet: kenney, name: rat}\n",
        encoding="utf-8",
    )

    with pytest.raises(ContentValidationError, match="has no 'index'"):
        load_sprite_manifest(path, catalog)


def test_load_sprite_manifest_rejects_recolor_on_a_tile_kind(tmp_path):
    catalog = load_catalog()
    path = tmp_path / "sprites.yaml"
    path.write_text(
        "sheets:\n"
        "  kenney:\n"
        "    image: roguelikeSheet_transparent.png\n"
        "    tile_size: 16\n"
        "    columns: 57\n"
        "    rows: 31\n"
        "tile_kinds:\n"
        "  sea: {sheet: kenney, col: 0, row: 2, recolor: true}\n",
        encoding="utf-8",
    )

    with pytest.raises(ContentValidationError, match="recolor is only meaningful for entities/items"):
        load_sprite_manifest(path, catalog)


def test_load_sprite_manifest_accepts_a_valid_dungeon_entrances_entry(tmp_path):
    catalog = load_catalog()
    path = tmp_path / "sprites.yaml"
    path.write_text(
        "sheets:\n"
        "  kenney:\n"
        "    image: roguelikeSheet_transparent.png\n"
        "    tile_size: 16\n"
        "    columns: 57\n"
        "    rows: 31\n"
        "dungeon_entrances:\n"
        "  prison_tower: {sheet: kenney, col: 50, row: 10}\n",
        encoding="utf-8",
    )

    manifest = load_sprite_manifest(path, catalog, known_dungeon_ids={"prison_tower"})

    assert manifest.dungeon_entrances["prison_tower"].col == 50


def test_load_sprite_manifest_rejects_an_unknown_dungeon_id(tmp_path):
    catalog = load_catalog()
    path = tmp_path / "sprites.yaml"
    path.write_text(
        "sheets:\n"
        "  kenney:\n"
        "    image: roguelikeSheet_transparent.png\n"
        "    tile_size: 16\n"
        "    columns: 57\n"
        "    rows: 31\n"
        "dungeon_entrances:\n"
        "  nonexistent_dungeon: {sheet: kenney, col: 50, row: 10}\n",
        encoding="utf-8",
    )

    with pytest.raises(ContentValidationError, match="unknown dungeon 'nonexistent_dungeon'"):
        load_sprite_manifest(path, catalog, known_dungeon_ids={"prison_tower"})


def test_load_sprite_manifest_skips_dungeon_id_check_when_known_dungeon_ids_is_none(tmp_path):
    catalog = load_catalog()
    path = tmp_path / "sprites.yaml"
    path.write_text(
        "sheets:\n"
        "  kenney:\n"
        "    image: roguelikeSheet_transparent.png\n"
        "    tile_size: 16\n"
        "    columns: 57\n"
        "    rows: 31\n"
        "dungeon_entrances:\n"
        "  nonexistent_dungeon: {sheet: kenney, col: 50, row: 10}\n",
        encoding="utf-8",
    )

    manifest = load_sprite_manifest(path, catalog)  # known_dungeon_ids defaults to None

    assert "nonexistent_dungeon" in manifest.dungeon_entrances


def test_load_sprite_manifest_rejects_recolor_on_a_dungeon_entrance(tmp_path):
    catalog = load_catalog()
    path = tmp_path / "sprites.yaml"
    path.write_text(
        "sheets:\n"
        "  kenney:\n"
        "    image: roguelikeSheet_transparent.png\n"
        "    tile_size: 16\n"
        "    columns: 57\n"
        "    rows: 31\n"
        "dungeon_entrances:\n"
        "  prison_tower: {sheet: kenney, col: 50, row: 10, recolor: true}\n",
        encoding="utf-8",
    )

    with pytest.raises(ContentValidationError, match="recolor is only meaningful for entities/items"):
        load_sprite_manifest(path, catalog, known_dungeon_ids={"prison_tower"})


def test_load_sprite_manifest_accepts_a_valid_backdrop(tmp_path):
    catalog = load_catalog()
    path = tmp_path / "sprites.yaml"
    path.write_text(
        "sheets:\n"
        "  kenney:\n"
        "    image: roguelikeSheet_transparent.png\n"
        "    tile_size: 16\n"
        "    columns: 57\n"
        "    rows: 31\n"
        "tile_kinds:\n"
        "  plains: {sheet: kenney, col: 5, row: 0}\n"
        "  forest: {sheet: kenney, col: 23, row: 9, backdrop: plains}\n"
        "dungeon_entrances:\n"
        "  prison_tower: {sheet: kenney, col: 50, row: 10, backdrop: plains}\n",
        encoding="utf-8",
    )

    manifest = load_sprite_manifest(path, catalog, known_dungeon_ids={"prison_tower"})

    assert manifest.tile_kinds["forest"].backdrop == "plains"
    assert manifest.dungeon_entrances["prison_tower"].backdrop == "plains"


def test_load_sprite_manifest_rejects_backdrop_on_an_entity(tmp_path):
    catalog = load_catalog()
    path = tmp_path / "sprites.yaml"
    path.write_text(
        "sheets:\n"
        "  kenney:\n"
        "    image: roguelikeSheet_transparent.png\n"
        "    tile_size: 16\n"
        "    columns: 57\n"
        "    rows: 31\n"
        "tile_kinds:\n"
        "  plains: {sheet: kenney, col: 5, row: 0}\n"
        "entities:\n"
        "  rat: {sheet: kenney, col: 0, row: 0, backdrop: plains}\n",
        encoding="utf-8",
    )

    with pytest.raises(ContentValidationError, match="backdrop is only meaningful for tile_kinds"):
        load_sprite_manifest(path, catalog)


def test_load_sprite_manifest_rejects_backdrop_on_an_item(tmp_path):
    catalog = load_catalog()
    path = tmp_path / "sprites.yaml"
    path.write_text(
        "sheets:\n"
        "  kenney:\n"
        "    image: roguelikeSheet_transparent.png\n"
        "    tile_size: 16\n"
        "    columns: 57\n"
        "    rows: 31\n"
        "tile_kinds:\n"
        "  plains: {sheet: kenney, col: 5, row: 0}\n"
        "items:\n"
        "  healing_potion: {sheet: kenney, col: 0, row: 0, backdrop: plains}\n",
        encoding="utf-8",
    )

    with pytest.raises(ContentValidationError, match="backdrop is only meaningful for tile_kinds"):
        load_sprite_manifest(path, catalog)


def test_load_sprite_manifest_rejects_a_backdrop_that_is_not_a_tile_kind(tmp_path):
    catalog = load_catalog()
    path = tmp_path / "sprites.yaml"
    path.write_text(
        "sheets:\n"
        "  kenney:\n"
        "    image: roguelikeSheet_transparent.png\n"
        "    tile_size: 16\n"
        "    columns: 57\n"
        "    rows: 31\n"
        "tile_kinds:\n"
        "  forest: {sheet: kenney, col: 23, row: 9, backdrop: nonexistent}\n",
        encoding="utf-8",
    )

    with pytest.raises(ContentValidationError, match="is not a tile_kinds entry"):
        load_sprite_manifest(path, catalog)


def test_load_sprite_manifest_rejects_a_tile_kind_backdropping_itself(tmp_path):
    catalog = load_catalog()
    path = tmp_path / "sprites.yaml"
    path.write_text(
        "sheets:\n"
        "  kenney:\n"
        "    image: roguelikeSheet_transparent.png\n"
        "    tile_size: 16\n"
        "    columns: 57\n"
        "    rows: 31\n"
        "tile_kinds:\n"
        "  forest: {sheet: kenney, col: 23, row: 9, backdrop: forest}\n",
        encoding="utf-8",
    )

    with pytest.raises(ContentValidationError, match="backdrop can't reference itself"):
        load_sprite_manifest(path, catalog)


def test_load_sprite_manifest_rejects_chained_backdrops(tmp_path):
    catalog = load_catalog()
    path = tmp_path / "sprites.yaml"
    path.write_text(
        "sheets:\n"
        "  kenney:\n"
        "    image: roguelikeSheet_transparent.png\n"
        "    tile_size: 16\n"
        "    columns: 57\n"
        "    rows: 31\n"
        "tile_kinds:\n"
        "  plains: {sheet: kenney, col: 5, row: 0}\n"
        "  forest: {sheet: kenney, col: 23, row: 9, backdrop: plains}\n"
        "  landmark: {sheet: kenney, col: 51, row: 11, backdrop: forest}\n",
        encoding="utf-8",
    )

    with pytest.raises(ContentValidationError, match="chaining isn't supported"):
        load_sprite_manifest(path, catalog)


def test_load_sprite_manifest_collects_multiple_errors_at_once(tmp_path):
    catalog = load_catalog()
    path = tmp_path / "sprites.yaml"
    path.write_text(
        "sheets: {}\n"
        "entities:\n"
        "  nonexistent_creature: {sheet: nonexistent_sheet, name: rat}\n"
        "items:\n"
        "  nonexistent_item: {sheet: nonexistent_sheet, col: 0, row: 0}\n",
        encoding="utf-8",
    )

    with pytest.raises(ContentValidationError) as exc_info:
        load_sprite_manifest(path, catalog)
    assert len(exc_info.value.errors) == 4  # 2 unknown ids + 2 unknown sheets


def test_load_audio_manifest_loads_a_valid_manifest(tmp_path):
    path = tmp_path / "audio.yaml"
    path.write_text(
        "sfx:\n"
        "  melee_hit: assets/audio/sfx/melee_hit.ogg\n"
        "music:\n"
        "  dungeon: assets/audio/music/dungeon.ogg\n",
        encoding="utf-8",
    )

    manifest = load_audio_manifest(path)

    assert manifest.sfx == {"melee_hit": "assets/audio/sfx/melee_hit.ogg"}
    assert manifest.music == {"dungeon": "assets/audio/music/dungeon.ogg"}


def test_load_audio_manifest_does_not_require_real_files_to_exist(tmp_path):
    """SoundManager (engine/audio.py) resolves and opens these paths lazily
    at play time, no-op-ing on anything missing - the loader itself never
    touches the filesystem beyond the manifest YAML, so this is valid even
    though assets/audio/sfx/nonexistent.ogg was never created."""
    path = tmp_path / "audio.yaml"
    path.write_text("sfx:\n  melee_hit: assets/audio/sfx/nonexistent.ogg\n", encoding="utf-8")

    manifest = load_audio_manifest(path)

    assert manifest.sfx["melee_hit"] == "assets/audio/sfx/nonexistent.ogg"


def test_load_audio_manifest_defaults_to_empty_when_a_section_is_missing(tmp_path):
    path = tmp_path / "audio.yaml"
    path.write_text("sfx:\n  melee_hit: assets/audio/sfx/melee_hit.ogg\n", encoding="utf-8")

    manifest = load_audio_manifest(path)

    assert manifest.music == {}


def test_load_audio_manifest_rejects_a_non_string_value(tmp_path):
    path = tmp_path / "audio.yaml"
    path.write_text("sfx:\n  melee_hit: [not, a, string]\n", encoding="utf-8")

    with pytest.raises(ContentValidationError):
        load_audio_manifest(path)
