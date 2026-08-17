import pytest
from pydantic import ValidationError

from content.schema import EntityDef, ItemDef, LegendEntry, LevelDef


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


def test_legend_entry_from_door_mapping():
    entry = LegendEntry.from_raw({"door": "rusty_key"})
    assert entry.tile == "door"
    assert entry.requires_key == "rusty_key"


def test_item_def_is_key_defaults_false():
    item = ItemDef(id="healing_potion", name="Healing Potion", glyph="!", color=(1, 2, 3))
    assert item.is_key is False


def test_level_def_normalizes_legend():
    level = LevelDef(
        id="l1",
        name="Test",
        map="#@#\n",
        legend={"#": "wall", "@": "player_start"},
    )
    assert level.legend["#"].tile == "wall"
    assert level.legend["@"].tile == "player_start"
