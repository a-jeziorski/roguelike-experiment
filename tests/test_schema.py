import pytest
from pydantic import ValidationError

from content.schema import DungeonDef, EntityDef, ItemDef, LegendEntry, LevelDef


def test_entity_def_valid():
    e = EntityDef(id="rat", name="Rat", glyph="r", color=(1, 2, 3), hp=5, attack=2, defense=0)
    assert e.hp == 5
    assert e.ai == "hostile_basic"


def test_entity_def_rejects_multi_char_glyph():
    with pytest.raises(ValidationError):
        EntityDef(id="rat", name="Rat", glyph="rat", color=(1, 2, 3), hp=5, attack=2, defense=0)


def test_entity_def_rejects_nonpositive_hp():
    with pytest.raises(ValidationError):
        EntityDef(id="rat", name="Rat", glyph="r", color=(1, 2, 3), hp=0, attack=2, defense=0)


def test_entity_def_rejects_unknown_ai():
    with pytest.raises(ValidationError):
        EntityDef(
            id="rat", name="Rat", glyph="r", color=(1, 2, 3), hp=5, attack=2, defense=0,
            ai="berserker",
        )


def test_entity_def_accepts_known_ai_types_with_optional_tuning():
    guard = EntityDef(
        id="skeleton", name="Skeleton", glyph="s", color=(1, 2, 3), hp=16, attack=5, defense=2,
        ai="sleeping_guard", alert_radius=6,
    )
    assert guard.alert_radius == 6

    skittish = EntityDef(
        id="rat", name="Rat", glyph="r", color=(1, 2, 3), hp=5, attack=2, defense=0,
        ai="skittish", flee_hp_pct=0.5,
    )
    assert skittish.flee_hp_pct == 0.5

    archer = EntityDef(
        id="skeleton_archer", name="Skeleton Archer", glyph="S", color=(1, 2, 3),
        hp=12, attack=4, defense=1, ai="ranged_basic", ranged_range=5,
    )
    assert archer.ranged_range == 5

    villager = EntityDef(
        id="villager", name="Villager", glyph="v", color=(1, 2, 3),
        hp=4, attack=0, defense=0, ai="villager",
    )
    assert villager.ai == "villager"

    town_guard = EntityDef(
        id="town_guard", name="Town Guard", glyph="T", color=(1, 2, 3),
        hp=14, attack=5, defense=2, ai="town_guard",
    )
    assert town_guard.ai == "town_guard"


def test_entity_def_rejects_out_of_range_flee_hp_pct():
    with pytest.raises(ValidationError):
        EntityDef(
            id="rat", name="Rat", glyph="r", color=(1, 2, 3), hp=5, attack=2, defense=0,
            ai="skittish", flee_hp_pct=1.5,
        )


def test_legend_entry_from_plain_string():
    entry = LegendEntry.from_raw("wall")
    assert entry.tile == "wall"
    assert entry.entity is None
    assert entry.item is None


def test_legend_entry_from_entity_mapping():
    entry = LegendEntry.from_raw({"entity": "rat"})
    assert entry.tile == "floor"
    assert entry.entity == "rat"


def test_legend_entry_from_item_mapping():
    entry = LegendEntry.from_raw({"item": "healing_potion"})
    assert entry.tile == "floor"
    assert entry.item == "healing_potion"


def test_legend_entry_from_stairs_up_mapping():
    entry = LegendEntry.from_raw({"stairs_up": "level_01"})
    assert entry.tile == "stairs_up"
    assert entry.next_level == "level_01"


def test_legend_entry_from_door_mapping():
    entry = LegendEntry.from_raw({"door": "rusty_key"})
    assert entry.tile == "door"
    assert entry.requires_key == "rusty_key"


def test_legend_entry_from_dungeon_entrance_mapping():
    entry = LegendEntry.from_raw({"dungeon_entrance": "forgotten_ruins"})
    assert entry.tile == "dungeon_entrance"
    assert entry.dungeon_id == "forgotten_ruins"


def test_legend_entry_description_defaults_none():
    entry = LegendEntry.from_raw({"stairs_up": "level_01"})
    assert entry.description is None


def test_legend_entry_stairs_up_accepts_custom_description():
    entry = LegendEntry.from_raw(
        {"stairs_up": None, "description": "The town gate, leading back out onto the road."}
    )
    assert entry.tile == "stairs_up"
    assert entry.next_level is None  # still terminal
    assert entry.description == "The town gate, leading back out onto the road."


def test_legend_entry_dungeon_entrance_accepts_custom_description():
    entry = LegendEntry.from_raw(
        {"dungeon_entrance": "millhaven", "description": "A cluster of thatched roofs."}
    )
    assert entry.dungeon_id == "millhaven"
    assert entry.description == "A cluster of thatched roofs."


def test_item_def_is_key_defaults_false():
    item = ItemDef(id="healing_potion", name="Healing Potion", glyph="!", color=(1, 2, 3))
    assert item.is_key is False


def test_entity_def_stationary_defaults_false():
    villager = EntityDef(
        id="villager", name="Villager", glyph="v", color=(1, 2, 3),
        hp=10, attack=0, defense=0, ai="villager",
    )
    assert villager.stationary is False


def test_entity_def_accepts_stationary():
    shopkeeper = EntityDef(
        id="shopkeeper", name="Shopkeeper", glyph="m", color=(1, 2, 3),
        hp=10, attack=0, defense=0, ai="villager", stationary=True,
    )
    assert shopkeeper.stationary is True


def test_item_def_accepts_defense_bonus():
    armor = ItemDef(
        id="leather_armor", name="Leather Armor", glyph="[", color=(1, 2, 3), defense_bonus=1
    )
    assert armor.defense_bonus == 1


def test_item_def_rejects_both_attack_and_defense_bonus():
    with pytest.raises(ValidationError):
        ItemDef(
            id="weird_item", name="Weird Item", glyph="?", color=(1, 2, 3),
            attack_bonus=2, defense_bonus=1,
        )


def test_item_def_accepts_ranged_attack_bonus_and_range():
    bow = ItemDef(
        id="hunting_bow", name="Hunting Bow", glyph="}", color=(1, 2, 3),
        ranged_attack_bonus=3, range=5,
    )
    assert bow.ranged_attack_bonus == 3
    assert bow.range == 5


def test_item_def_rejects_ranged_attack_bonus_combined_with_attack_bonus():
    with pytest.raises(ValidationError):
        ItemDef(
            id="weird_item", name="Weird Item", glyph="?", color=(1, 2, 3),
            attack_bonus=2, ranged_attack_bonus=3,
        )


def test_item_def_rejects_ranged_attack_bonus_combined_with_defense_bonus():
    with pytest.raises(ValidationError):
        ItemDef(
            id="weird_item", name="Weird Item", glyph="?", color=(1, 2, 3),
            defense_bonus=1, ranged_attack_bonus=3,
        )


def test_item_def_ammo_defaults():
    item = ItemDef(id="healing_potion", name="Healing Potion", glyph="!", color=(1, 2, 3))
    assert item.is_ammo is False
    assert item.quantity == 1


def test_item_def_accepts_ammo_with_quantity():
    arrows = ItemDef(
        id="arrows", name="Arrows", glyph="|", color=(1, 2, 3), is_ammo=True, quantity=5
    )
    assert arrows.is_ammo is True
    assert arrows.quantity == 5


def test_item_def_gold_amount_defaults_none():
    item = ItemDef(id="healing_potion", name="Healing Potion", glyph="!", color=(1, 2, 3))
    assert item.gold_amount is None


def test_item_def_accepts_gold_amount():
    gold = ItemDef(
        id="gold_pile", name="Gold Pile", glyph="$", color=(1, 2, 3), gold_amount=10
    )
    assert gold.gold_amount == 10


def test_item_def_cost_defaults_none():
    item = ItemDef(id="healing_potion", name="Healing Potion", glyph="!", color=(1, 2, 3))
    assert item.cost is None


def test_item_def_accepts_cost():
    potion = ItemDef(
        id="healing_potion", name="Healing Potion", glyph="!", color=(1, 2, 3), cost=25
    )
    assert potion.cost == 25


def test_item_def_rejects_zero_cost():
    with pytest.raises(ValidationError):
        ItemDef(id="healing_potion", name="Healing Potion", glyph="!", color=(1, 2, 3), cost=0)


def test_dungeon_def_valid():
    dungeon = DungeonDef(id="prison_tower", name="The Prison Tower", starting_level="level_01")
    assert dungeon.starting_level == "level_01"
    assert dungeon.description == ""
    assert dungeon.inspect_text == ""


def test_dungeon_def_accepts_inspect_text():
    dungeon = DungeonDef(
        id="prison_tower", name="The Prison Tower", starting_level="level_01",
        inspect_text="A black stone tower.",
    )
    assert dungeon.inspect_text == "A black stone tower."


def test_dungeon_def_requires_starting_level():
    with pytest.raises(ValidationError):
        DungeonDef(id="prison_tower", name="The Prison Tower")


def test_dungeon_def_requires_stairs_down_defaults_true():
    dungeon = DungeonDef(id="prison_tower", name="The Prison Tower", starting_level="level_01")
    assert dungeon.requires_stairs_down is True


def test_dungeon_def_accepts_requires_stairs_down_false():
    dungeon = DungeonDef(
        id="millhaven", name="Millhaven", starting_level="level_01",
        requires_stairs_down=False,
    )
    assert dungeon.requires_stairs_down is False


def test_level_def_normalizes_legend():
    level = LevelDef(
        id="l1",
        name="Test",
        map="#@#\n",
        legend={"#": "wall", "@": "player_start"},
    )
    assert level.legend["#"].tile == "wall"
    assert level.legend["@"].tile == "player_start"
