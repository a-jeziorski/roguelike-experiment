import pytest
from pydantic import ValidationError

from content.schema import (
    DungeonDef,
    EntityDef,
    FlagDialogue,
    ItemDef,
    LegendEntry,
    LevelDef,
    PerkDef,
    QuestDef,
    SpriteRef,
    SpriteSheetDef,
    TightenDeadline,
    WorldConsequence,
)


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


def test_entity_def_inflicts_effect_fields_default_none():
    e = EntityDef(id="cave_spider", name="Cave Spider", glyph="x", color=(1, 2, 3), hp=7, attack=3, defense=0)
    assert e.inflicts_effect is None
    assert e.inflicts_potency is None
    assert e.inflicts_duration is None


def test_entity_def_accepts_poison_effect_with_potency_and_duration():
    e = EntityDef(
        id="cave_spider", name="Cave Spider", glyph="x", color=(1, 2, 3), hp=7, attack=3, defense=0,
        inflicts_effect="poison", inflicts_potency=1, inflicts_duration=3,
    )
    assert e.inflicts_effect == "poison"
    assert e.inflicts_potency == 1
    assert e.inflicts_duration == 3


def test_entity_def_accepts_weaken_effect_with_potency_and_duration():
    e = EntityDef(
        id="gray_ooze", name="Gray Ooze", glyph="j", color=(1, 2, 3), hp=16, attack=4, defense=1,
        inflicts_effect="weaken", inflicts_potency=2, inflicts_duration=3,
    )
    assert e.inflicts_effect == "weaken"
    assert e.inflicts_potency == 2


def test_entity_def_accepts_stun_effect_with_no_potency():
    e = EntityDef(
        id="wraith", name="Wraith", glyph="Y", color=(1, 2, 3), hp=20, attack=6, defense=2,
        inflicts_effect="stun", inflicts_duration=1,
    )
    assert e.inflicts_effect == "stun"
    assert e.inflicts_potency is None


def test_entity_def_rejects_inflicts_effect_without_duration():
    with pytest.raises(ValidationError, match="must be set together"):
        EntityDef(
            id="cave_spider", name="Cave Spider", glyph="x", color=(1, 2, 3), hp=7, attack=3, defense=0,
            inflicts_effect="poison", inflicts_potency=1,
        )


def test_entity_def_rejects_inflicts_duration_without_effect():
    with pytest.raises(ValidationError, match="must be set together"):
        EntityDef(
            id="cave_spider", name="Cave Spider", glyph="x", color=(1, 2, 3), hp=7, attack=3, defense=0,
            inflicts_duration=3,
        )


def test_entity_def_rejects_poison_without_potency():
    with pytest.raises(ValidationError, match="requires inflicts_potency"):
        EntityDef(
            id="cave_spider", name="Cave Spider", glyph="x", color=(1, 2, 3), hp=7, attack=3, defense=0,
            inflicts_effect="poison", inflicts_duration=3,
        )


def test_entity_def_rejects_stun_with_potency():
    with pytest.raises(ValidationError, match="no intensity concept"):
        EntityDef(
            id="wraith", name="Wraith", glyph="Y", color=(1, 2, 3), hp=20, attack=6, defense=2,
            inflicts_effect="stun", inflicts_potency=1, inflicts_duration=1,
        )


def test_entity_def_rejects_unknown_inflicts_effect():
    with pytest.raises(ValidationError):
        EntityDef(
            id="cave_spider", name="Cave Spider", glyph="x", color=(1, 2, 3), hp=7, attack=3, defense=0,
            inflicts_effect="fire", inflicts_potency=1, inflicts_duration=3,
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

    berserker = EntityDef(
        id="berserker", name="Berserker", glyph="b", color=(1, 2, 3),
        hp=18, attack=5, defense=1, ai="enrage", enrage_hp_pct=0.4, enrage_attack_bonus=3,
    )
    assert berserker.enrage_hp_pct == 0.4
    assert berserker.enrage_attack_bonus == 3

    wolf = EntityDef(
        id="wolf", name="Wolf", glyph="w", color=(1, 2, 3),
        hp=10, attack=3, defense=0, ai="pack_hunter", pack_radius=4, pack_attack_bonus=2,
    )
    assert wolf.pack_radius == 4
    assert wolf.pack_attack_bonus == 2

    troll = EntityDef(
        id="troll", name="Troll", glyph="T", color=(1, 2, 3),
        hp=30, attack=6, defense=2, ai="regenerator", regen_amount=4,
    )
    assert troll.regen_amount == 4


def test_entity_def_drop_fields_default_none():
    e = EntityDef(id="rat", name="Rat", glyph="r", color=(1, 2, 3), hp=5, attack=2, defense=0)
    assert e.drop_item_id is None
    assert e.drop_chance is None


def test_entity_def_accepts_drop_item_id_with_chance():
    e = EntityDef(
        id="rat", name="Rat", glyph="r", color=(1, 2, 3), hp=5, attack=2, defense=0,
        drop_item_id="rusty_dagger", drop_chance=0.25,
    )
    assert e.drop_item_id == "rusty_dagger"
    assert e.drop_chance == 0.25


def test_entity_def_rejects_drop_item_id_without_chance():
    with pytest.raises(ValidationError, match="must be set together"):
        EntityDef(
            id="rat", name="Rat", glyph="r", color=(1, 2, 3), hp=5, attack=2, defense=0,
            drop_item_id="rusty_dagger",
        )


def test_entity_def_rejects_drop_chance_without_item_id():
    with pytest.raises(ValidationError, match="must be set together"):
        EntityDef(
            id="rat", name="Rat", glyph="r", color=(1, 2, 3), hp=5, attack=2, defense=0,
            drop_chance=0.25,
        )


def test_entity_def_rejects_out_of_range_drop_chance():
    with pytest.raises(ValidationError):
        EntityDef(
            id="rat", name="Rat", glyph="r", color=(1, 2, 3), hp=5, attack=2, defense=0,
            drop_item_id="rusty_dagger", drop_chance=1.5,
        )


def test_entity_def_split_fields_default_none():
    e = EntityDef(id="slime", name="Slime", glyph="J", color=(1, 2, 3), hp=16, attack=3, defense=0)
    assert e.split_count is None
    assert e.split_hp_fraction is None


def test_entity_def_accepts_split_count_with_fraction():
    e = EntityDef(
        id="slime", name="Slime", glyph="J", color=(1, 2, 3), hp=16, attack=3, defense=0,
        ai="splitter", split_count=2, split_hp_fraction=0.4,
    )
    assert e.split_count == 2
    assert e.split_hp_fraction == 0.4


def test_entity_def_rejects_split_count_without_fraction():
    with pytest.raises(ValidationError, match="must be set together"):
        EntityDef(
            id="slime", name="Slime", glyph="J", color=(1, 2, 3), hp=16, attack=3, defense=0,
            ai="splitter", split_count=2,
        )


def test_entity_def_rejects_split_fraction_without_count():
    with pytest.raises(ValidationError, match="must be set together"):
        EntityDef(
            id="slime", name="Slime", glyph="J", color=(1, 2, 3), hp=16, attack=3, defense=0,
            ai="splitter", split_hp_fraction=0.4,
        )


def test_entity_def_rejects_out_of_range_split_hp_fraction():
    with pytest.raises(ValidationError):
        EntityDef(
            id="slime", name="Slime", glyph="J", color=(1, 2, 3), hp=16, attack=3, defense=0,
            ai="splitter", split_count=2, split_hp_fraction=1.5,
        )


def test_entity_def_rejects_nonpositive_split_count():
    with pytest.raises(ValidationError):
        EntityDef(
            id="slime", name="Slime", glyph="J", color=(1, 2, 3), hp=16, attack=3, defense=0,
            ai="splitter", split_count=0, split_hp_fraction=0.4,
        )


def test_entity_def_summon_fields_default_none():
    e = EntityDef(id="bone_caller", name="Bone Caller", glyph="U", color=(1, 2, 3), hp=14, attack=2, defense=0)
    assert e.summon_entity_id is None
    assert e.summon_interval is None
    assert e.summon_max_active is None


def test_entity_def_accepts_summon_entity_id_with_interval():
    e = EntityDef(
        id="bone_caller", name="Bone Caller", glyph="U", color=(1, 2, 3), hp=14, attack=2, defense=0,
        ai="summoner", summon_entity_id="skeleton", summon_interval=4,
    )
    assert e.summon_entity_id == "skeleton"
    assert e.summon_interval == 4


def test_entity_def_accepts_summon_max_active():
    e = EntityDef(
        id="bone_caller", name="Bone Caller", glyph="U", color=(1, 2, 3), hp=14, attack=2, defense=0,
        ai="summoner", summon_entity_id="skeleton", summon_interval=4, summon_max_active=2,
    )
    assert e.summon_max_active == 2


def test_entity_def_rejects_summon_entity_id_without_interval():
    with pytest.raises(ValidationError, match="must be set together"):
        EntityDef(
            id="bone_caller", name="Bone Caller", glyph="U", color=(1, 2, 3), hp=14, attack=2, defense=0,
            ai="summoner", summon_entity_id="skeleton",
        )


def test_entity_def_rejects_summon_interval_without_entity_id():
    with pytest.raises(ValidationError, match="must be set together"):
        EntityDef(
            id="bone_caller", name="Bone Caller", glyph="U", color=(1, 2, 3), hp=14, attack=2, defense=0,
            ai="summoner", summon_interval=4,
        )


def test_entity_def_rejects_summon_max_active_without_entity_id():
    with pytest.raises(ValidationError, match="only meaningful when summon_entity_id"):
        EntityDef(
            id="bone_caller", name="Bone Caller", glyph="U", color=(1, 2, 3), hp=14, attack=2, defense=0,
            summon_max_active=2,
        )


def test_entity_def_rejects_nonpositive_summon_interval():
    with pytest.raises(ValidationError):
        EntityDef(
            id="bone_caller", name="Bone Caller", glyph="U", color=(1, 2, 3), hp=14, attack=2, defense=0,
            ai="summoner", summon_entity_id="skeleton", summon_interval=0,
        )


def test_entity_def_charge_fields_default_none():
    e = EntityDef(id="boar", name="Boar", glyph="a", color=(1, 2, 3), hp=12, attack=4, defense=0)
    assert e.charge_range is None
    assert e.charge_attack_bonus is None


def test_entity_def_accepts_charge_range_and_bonus():
    e = EntityDef(
        id="boar", name="Boar", glyph="a", color=(1, 2, 3), hp=12, attack=4, defense=0,
        ai="charger", charge_range=4, charge_attack_bonus=4,
    )
    assert e.charge_range == 4
    assert e.charge_attack_bonus == 4


def test_entity_def_accepts_charge_range_without_bonus():
    e = EntityDef(
        id="boar", name="Boar", glyph="a", color=(1, 2, 3), hp=12, attack=4, defense=0,
        ai="charger", charge_range=4,
    )
    assert e.charge_range == 4
    assert e.charge_attack_bonus is None


def test_entity_def_rejects_nonpositive_charge_range():
    with pytest.raises(ValidationError):
        EntityDef(
            id="boar", name="Boar", glyph="a", color=(1, 2, 3), hp=12, attack=4, defense=0,
            ai="charger", charge_range=0,
        )


def test_entity_def_rejects_nonpositive_charge_attack_bonus():
    with pytest.raises(ValidationError):
        EntityDef(
            id="boar", name="Boar", glyph="a", color=(1, 2, 3), hp=12, attack=4, defense=0,
            ai="charger", charge_attack_bonus=0,
        )


def test_entity_def_territory_radius_defaults_none():
    e = EntityDef(id="cave_bear", name="Cave Bear", glyph="Z", color=(1, 2, 3), hp=22, attack=6, defense=1)
    assert e.territory_radius is None


def test_entity_def_accepts_territory_radius():
    e = EntityDef(
        id="cave_bear", name="Cave Bear", glyph="Z", color=(1, 2, 3), hp=22, attack=6, defense=1,
        ai="territorial", territory_radius=5,
    )
    assert e.territory_radius == 5


def test_entity_def_rejects_nonpositive_territory_radius():
    with pytest.raises(ValidationError):
        EntityDef(
            id="cave_bear", name="Cave Bear", glyph="Z", color=(1, 2, 3), hp=22, attack=6, defense=1,
            ai="territorial", territory_radius=0,
        )


def test_entity_def_ambush_bonus_defaults_none():
    e = EntityDef(id="lurker", name="Lurker", glyph="t", color=(1, 2, 3), hp=14, attack=5, defense=1)
    assert e.ambush_bonus is None


def test_entity_def_accepts_ambush_bonus():
    e = EntityDef(
        id="lurker", name="Lurker", glyph="t", color=(1, 2, 3), hp=14, attack=5, defense=1,
        ai="ambusher", ambush_bonus=6,
    )
    assert e.ambush_bonus == 6


def test_entity_def_rejects_nonpositive_ambush_bonus():
    with pytest.raises(ValidationError):
        EntityDef(
            id="lurker", name="Lurker", glyph="t", color=(1, 2, 3), hp=14, attack=5, defense=1,
            ai="ambusher", ambush_bonus=0,
        )


def test_entity_def_scavenge_fields_default_none():
    e = EntityDef(id="vulture", name="Vulture", glyph="v", color=(1, 2, 3), hp=12, attack=3, defense=0)
    assert e.scavenge_radius is None
    assert e.scavenge_heal_fraction is None


def test_entity_def_accepts_scavenge_fields():
    e = EntityDef(
        id="vulture", name="Vulture", glyph="v", color=(1, 2, 3), hp=12, attack=3, defense=0,
        ai="scavenger", scavenge_radius=6, scavenge_heal_fraction=0.5,
    )
    assert e.scavenge_radius == 6
    assert e.scavenge_heal_fraction == 0.5


def test_entity_def_scavenge_fields_are_independently_optional():
    e = EntityDef(
        id="vulture", name="Vulture", glyph="v", color=(1, 2, 3), hp=12, attack=3, defense=0,
        ai="scavenger", scavenge_radius=6,
    )
    assert e.scavenge_radius == 6
    assert e.scavenge_heal_fraction is None


def test_entity_def_rejects_nonpositive_scavenge_radius():
    with pytest.raises(ValidationError):
        EntityDef(
            id="vulture", name="Vulture", glyph="v", color=(1, 2, 3), hp=12, attack=3, defense=0,
            ai="scavenger", scavenge_radius=0,
        )


def test_entity_def_rejects_out_of_range_scavenge_heal_fraction():
    with pytest.raises(ValidationError):
        EntityDef(
            id="vulture", name="Vulture", glyph="v", color=(1, 2, 3), hp=12, attack=3, defense=0,
            ai="scavenger", scavenge_heal_fraction=1.5,
        )


def test_entity_def_mimic_bonus_defaults_none():
    e = EntityDef(id="mimic_flask", name="Gleaming Vial", glyph="!", color=(1, 2, 3), hp=14, attack=4, defense=1)
    assert e.mimic_bonus is None


def test_entity_def_accepts_mimic_bonus():
    e = EntityDef(
        id="mimic_flask", name="Gleaming Vial", glyph="!", color=(1, 2, 3), hp=14, attack=4, defense=1,
        ai="mimic", mimic_bonus=6,
    )
    assert e.mimic_bonus == 6


def test_entity_def_rejects_nonpositive_mimic_bonus():
    with pytest.raises(ValidationError):
        EntityDef(
            id="mimic_flask", name="Gleaming Vial", glyph="!", color=(1, 2, 3), hp=14, attack=4, defense=1,
            ai="mimic", mimic_bonus=0,
        )


def test_entity_def_rejects_out_of_range_flee_hp_pct():
    with pytest.raises(ValidationError):
        EntityDef(
            id="rat", name="Rat", glyph="r", color=(1, 2, 3), hp=5, attack=2, defense=0,
            ai="skittish", flee_hp_pct=1.5,
        )


def test_entity_def_rejects_out_of_range_enrage_hp_pct():
    with pytest.raises(ValidationError):
        EntityDef(
            id="berserker", name="Berserker", glyph="b", color=(1, 2, 3), hp=18, attack=5, defense=1,
            ai="enrage", enrage_hp_pct=1.5,
        )


def test_entity_def_rejects_nonpositive_pack_attack_bonus():
    with pytest.raises(ValidationError):
        EntityDef(
            id="wolf", name="Wolf", glyph="w", color=(1, 2, 3), hp=10, attack=3, defense=0,
            ai="pack_hunter", pack_attack_bonus=0,
        )


def test_entity_def_rejects_nonpositive_regen_amount():
    with pytest.raises(ValidationError):
        EntityDef(
            id="troll", name="Troll", glyph="T", color=(1, 2, 3), hp=30, attack=6, defense=2,
            ai="regenerator", regen_amount=0,
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


def test_legend_entry_flag_dialogue_defaults_to_empty_list():
    entry = LegendEntry.from_raw({"entity": "rat"})
    assert entry.flag_dialogue == []


def test_legend_entry_from_entity_mapping_parses_flag_dialogue():
    entry = LegendEntry.from_raw(
        {"entity": "village_chief", "flag_dialogue": [{"flag": "wayford_razed", "line": "It's gone."}]}
    )
    assert entry.flag_dialogue == [FlagDialogue(flag="wayford_razed", line="It's gone.")]


def test_legend_entry_elite_defaults_false():
    entry = LegendEntry.from_raw({"entity": "rat"})
    assert entry.elite is False


def test_legend_entry_from_entity_mapping_with_elite():
    entry = LegendEntry.from_raw({"entity": "orc", "elite": True})
    assert entry.elite is True


def test_legend_entry_elite_requires_entity():
    with pytest.raises(ValidationError, match="elite requires entity"):
        LegendEntry.from_raw({"tile": "floor", "elite": True})


def test_legend_entry_from_item_mapping():
    entry = LegendEntry.from_raw({"item": "healing_potion"})
    assert entry.tile == "floor"
    assert entry.item == "healing_potion"


def test_legend_entry_from_entity_mapping_with_a_tile_override():
    entry = LegendEntry.from_raw({"entity": "villager", "tile": "plains"})
    assert entry.tile == "plains"
    assert entry.entity == "villager"


def test_legend_entry_from_item_mapping_with_a_tile_override():
    entry = LegendEntry.from_raw({"item": "healing_potion", "tile": "road"})
    assert entry.tile == "road"


def test_legend_entry_decoration_defaults_none():
    entry = LegendEntry.from_raw({"tile": "floor"})
    assert entry.decoration is None


def test_legend_entry_accepts_a_valid_decoration_kind():
    entry = LegendEntry.from_raw({"tile": "floor", "decoration": "table"})
    assert entry.decoration == "table"


def test_legend_entry_rejects_an_unknown_decoration_kind():
    with pytest.raises(ValidationError):
        LegendEntry.from_raw({"tile": "floor", "decoration": "hot_tub"})


@pytest.mark.parametrize(
    "kind", ["tombstone", "tilled_soil", "archery_target", "barrel", "crate"],
)
def test_legend_entry_accepts_each_of_millhavens_third_pass_decoration_kinds(kind):
    entry = LegendEntry.from_raw({"tile": "plains", "decoration": kind})
    assert entry.decoration == kind


def test_legend_entry_decoration_coexists_with_entity():
    entry = LegendEntry.from_raw({"entity": "villager", "tile": "plains", "decoration": "bush"})
    assert entry.entity == "villager"
    assert entry.decoration == "bush"


def test_legend_entry_decoration_coexists_with_item():
    entry = LegendEntry.from_raw({"item": "healing_potion", "decoration": "table"})
    assert entry.item == "healing_potion"
    assert entry.decoration == "table"


def test_legend_entry_tile_sprite_defaults_none():
    entry = LegendEntry.from_raw({"tile": "floor"})
    assert entry.tile_sprite is None


def test_legend_entry_accepts_a_tile_sprite_via_the_general_mapping_form():
    entry = LegendEntry.from_raw(
        {"tile": "stairs_up", "next_level": None, "tile_sprite": "town_gate"}
    )
    assert entry.tile == "stairs_up"
    assert entry.tile_sprite == "town_gate"


def test_legend_entry_announce_defaults_false():
    entry = LegendEntry.from_raw({"tile": "landmark", "description": "A chalk board."})
    assert entry.announce is False


def test_legend_entry_from_entity_mapping_with_announce():
    entry = LegendEntry.from_raw({"entity": "rat", "description": "A mangy rat.", "announce": True})
    assert entry.announce is True


def test_legend_entry_from_general_mapping_with_announce():
    entry = LegendEntry.from_raw(
        {"tile": "landmark", "description": "A chalk board.", "announce": True}
    )
    assert entry.announce is True


def test_legend_entry_announce_requires_description():
    with pytest.raises(ValidationError, match="announce requires description"):
        LegendEntry.from_raw({"tile": "landmark", "announce": True})


def test_legend_entry_announce_true_with_description_is_valid():
    entry = LegendEntry.from_raw(
        {"tile": "landmark", "description": "A chalk board.", "announce": True}
    )
    assert entry.description == "A chalk board."
    assert entry.announce is True


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


def test_item_def_trinket_fields_default_none():
    item = ItemDef(id="rusty_key", name="Rusty Key", glyph="-", color=(1, 2, 3))
    assert item.trinket_effect is None
    assert item.trinket_bonus is None


def test_item_def_accepts_trinket_effect_and_bonus():
    charm = ItemDef(
        id="lucky_charm", name="Lucky Charm", glyph="'", color=(1, 2, 3),
        trinket_effect="crit_chance", trinket_bonus=0.1,
    )
    assert charm.trinket_effect == "crit_chance"
    assert charm.trinket_bonus == 0.1


def test_item_def_rejects_trinket_effect_without_bonus():
    with pytest.raises(ValidationError, match="must be set together"):
        ItemDef(
            id="lucky_charm", name="Lucky Charm", glyph="'", color=(1, 2, 3),
            trinket_effect="crit_chance",
        )


def test_item_def_rejects_trinket_bonus_without_effect():
    with pytest.raises(ValidationError, match="must be set together"):
        ItemDef(
            id="lucky_charm", name="Lucky Charm", glyph="'", color=(1, 2, 3),
            trinket_bonus=0.1,
        )


def test_item_def_rejects_out_of_range_trinket_bonus():
    with pytest.raises(ValidationError):
        ItemDef(
            id="lucky_charm", name="Lucky Charm", glyph="'", color=(1, 2, 3),
            trinket_effect="crit_chance", trinket_bonus=1.5,
        )


def test_item_def_rejects_unknown_trinket_effect():
    with pytest.raises(ValidationError):
        ItemDef(
            id="lucky_charm", name="Lucky Charm", glyph="'", color=(1, 2, 3),
            trinket_effect="luck", trinket_bonus=0.1,
        )


def test_item_def_rejects_trinket_effect_combined_with_attack_bonus():
    with pytest.raises(ValidationError):
        ItemDef(
            id="weird_item", name="Weird Item", glyph="?", color=(1, 2, 3),
            attack_bonus=2, trinket_effect="crit_chance", trinket_bonus=0.1,
        )


def test_item_def_affix_fields_default_none():
    item = ItemDef(id="rusty_dagger", name="Rusty Dagger", glyph="/", color=(1, 2, 3), attack_bonus=2)
    assert item.affix_effect is None
    assert item.affix_potency is None
    assert item.affix_duration is None
    assert item.affix_chance is None


def test_item_def_accepts_a_weapon_affix():
    dagger = ItemDef(
        id="venomous_dagger", name="Venomous Dagger", glyph="`", color=(1, 2, 3), attack_bonus=2,
        affix_effect="poison", affix_potency=1, affix_duration=3, affix_chance=0.3,
    )
    assert dagger.affix_effect == "poison"
    assert dagger.affix_chance == 0.3


def test_item_def_accepts_an_armor_affix():
    plate = ItemDef(
        id="thorned_plate", name="Thorned Plate", glyph="_", color=(1, 2, 3), defense_bonus=2,
        affix_effect="weaken", affix_potency=2, affix_duration=2, affix_chance=0.3,
    )
    assert plate.affix_effect == "weaken"


def test_item_def_accepts_a_stun_affix_with_no_potency():
    item = ItemDef(
        id="stunning_mace", name="Stunning Mace", glyph="!", color=(1, 2, 3), attack_bonus=3,
        affix_effect="stun", affix_duration=1, affix_chance=0.2,
    )
    assert item.affix_effect == "stun"
    assert item.affix_potency is None


def test_item_def_rejects_affix_effect_without_duration_or_chance():
    with pytest.raises(ValidationError, match="must all be set together"):
        ItemDef(
            id="venomous_dagger", name="Venomous Dagger", glyph="`", color=(1, 2, 3), attack_bonus=2,
            affix_effect="poison", affix_potency=1,
        )


def test_item_def_rejects_affix_chance_without_effect():
    with pytest.raises(ValidationError, match="must all be set together"):
        ItemDef(
            id="rusty_dagger", name="Rusty Dagger", glyph="/", color=(1, 2, 3), attack_bonus=2,
            affix_chance=0.3,
        )


def test_item_def_rejects_affix_poison_without_potency():
    with pytest.raises(ValidationError, match="requires affix_potency"):
        ItemDef(
            id="venomous_dagger", name="Venomous Dagger", glyph="`", color=(1, 2, 3), attack_bonus=2,
            affix_effect="poison", affix_duration=3, affix_chance=0.3,
        )


def test_item_def_rejects_affix_stun_with_potency():
    with pytest.raises(ValidationError, match="no intensity concept"):
        ItemDef(
            id="stunning_mace", name="Stunning Mace", glyph="!", color=(1, 2, 3), attack_bonus=3,
            affix_effect="stun", affix_potency=1, affix_duration=1, affix_chance=0.2,
        )


def test_item_def_rejects_affix_with_neither_attack_nor_defense_bonus():
    with pytest.raises(ValidationError, match="exactly one of attack_bonus"):
        ItemDef(
            id="weird_item", name="Weird Item", glyph="?", color=(1, 2, 3),
            affix_effect="poison", affix_potency=1, affix_duration=3, affix_chance=0.3,
        )


def test_item_def_rejects_affix_with_both_attack_and_defense_bonus():
    # not_multiple_equipment_slots already rejects attack_bonus + defense_bonus
    # together on its own, before affix_requires_weapon_or_armor is ever reached.
    with pytest.raises(ValidationError):
        ItemDef(
            id="weird_item", name="Weird Item", glyph="?", color=(1, 2, 3),
            attack_bonus=2, defense_bonus=1,
            affix_effect="poison", affix_potency=1, affix_duration=3, affix_chance=0.3,
        )


def test_item_def_rejects_out_of_range_affix_chance():
    with pytest.raises(ValidationError):
        ItemDef(
            id="venomous_dagger", name="Venomous Dagger", glyph="`", color=(1, 2, 3), attack_bonus=2,
            affix_effect="poison", affix_potency=1, affix_duration=3, affix_chance=1.5,
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


def test_item_def_is_teleport_defaults_false():
    item = ItemDef(id="healing_potion", name="Healing Potion", glyph="!", color=(1, 2, 3))
    assert item.is_teleport is False


def test_item_def_accepts_is_teleport():
    potion = ItemDef(
        id="teleportation_potion", name="Teleportation Potion", glyph="?",
        color=(1, 2, 3), is_teleport=True,
    )
    assert potion.is_teleport is True


def test_item_def_water_walking_duration_defaults_none():
    item = ItemDef(id="healing_potion", name="Healing Potion", glyph="!", color=(1, 2, 3))
    assert item.water_walking_duration is None


def test_item_def_accepts_water_walking_duration():
    potion = ItemDef(
        id="water_walking_potion", name="Water Walking Potion", glyph="~",
        color=(1, 2, 3), water_walking_duration=20,
    )
    assert potion.water_walking_duration == 20


def test_item_def_rejects_non_positive_water_walking_duration():
    with pytest.raises(ValidationError):
        ItemDef(
            id="water_walking_potion", name="Water Walking Potion", glyph="~",
            color=(1, 2, 3), water_walking_duration=0,
        )


def test_item_def_cures_effects_defaults_false():
    item = ItemDef(id="healing_potion", name="Healing Potion", glyph="!", color=(1, 2, 3))
    assert item.cures_effects is False


def test_item_def_accepts_cures_effects():
    potion = ItemDef(
        id="antidote_potion", name="Antidote", glyph="!", color=(1, 2, 3), cures_effects=True,
    )
    assert potion.cures_effects is True


def test_item_def_grants_buff_defaults_none():
    item = ItemDef(id="healing_potion", name="Healing Potion", glyph="!", color=(1, 2, 3))
    assert item.grants_buff is None
    assert item.buff_potency is None
    assert item.buff_duration is None


def test_item_def_accepts_grants_buff_with_potency_and_duration():
    potion = ItemDef(
        id="vigor_elixir", name="Elixir of Vigor", glyph="!", color=(1, 2, 3),
        grants_buff="vigor", buff_potency=3, buff_duration=10,
    )
    assert potion.grants_buff == "vigor"
    assert potion.buff_potency == 3
    assert potion.buff_duration == 10


def test_item_def_rejects_non_positive_buff_potency_or_duration():
    with pytest.raises(ValidationError):
        ItemDef(
            id="vigor_elixir", name="Elixir of Vigor", glyph="!", color=(1, 2, 3),
            grants_buff="vigor", buff_potency=0, buff_duration=10,
        )
    with pytest.raises(ValidationError):
        ItemDef(
            id="vigor_elixir", name="Elixir of Vigor", glyph="!", color=(1, 2, 3),
            grants_buff="vigor", buff_potency=3, buff_duration=0,
        )


def test_item_def_rejects_grants_buff_without_potency_and_duration():
    with pytest.raises(ValidationError):
        ItemDef(
            id="vigor_elixir", name="Elixir of Vigor", glyph="!", color=(1, 2, 3),
            grants_buff="vigor",
        )


def test_item_def_rejects_buff_potency_and_duration_without_grants_buff():
    with pytest.raises(ValidationError):
        ItemDef(
            id="vigor_elixir", name="Elixir of Vigor", glyph="!", color=(1, 2, 3),
            buff_potency=3, buff_duration=10,
        )


def test_item_def_accepts_grants_buff_haste_without_potency():
    potion = ItemDef(
        id="swiftness_draught", name="Draught of Swiftness", glyph="!", color=(1, 2, 3),
        grants_buff="haste", buff_duration=3,
    )
    assert potion.grants_buff == "haste"
    assert potion.buff_potency is None
    assert potion.buff_duration == 3


def test_item_def_rejects_haste_with_potency():
    with pytest.raises(ValidationError):
        ItemDef(
            id="swiftness_draught", name="Draught of Swiftness", glyph="!", color=(1, 2, 3),
            grants_buff="haste", buff_potency=1, buff_duration=3,
        )


def test_item_def_rejects_grants_buff_without_duration():
    with pytest.raises(ValidationError):
        ItemDef(
            id="swiftness_draught", name="Draught of Swiftness", glyph="!", color=(1, 2, 3),
            grants_buff="haste",
        )


def test_item_def_accepts_grants_buff_shadowed_without_potency():
    potion = ItemDef(
        id="shadow_vial", name="Vial of Shadows", glyph="!", color=(1, 2, 3),
        grants_buff="shadowed", buff_duration=8,
    )
    assert potion.grants_buff == "shadowed"
    assert potion.buff_potency is None
    assert potion.buff_duration == 8


def test_item_def_rejects_shadowed_with_potency():
    with pytest.raises(ValidationError):
        ItemDef(
            id="shadow_vial", name="Vial of Shadows", glyph="!", color=(1, 2, 3),
            grants_buff="shadowed", buff_potency=1, buff_duration=8,
        )


def test_item_def_accepts_grants_buff_sure_footed_without_potency():
    potion = ItemDef(
        id="sure_footing_draught", name="Sure-Footing Draught", glyph="!", color=(1, 2, 3),
        grants_buff="sure_footed", buff_duration=15,
    )
    assert potion.grants_buff == "sure_footed"
    assert potion.buff_potency is None
    assert potion.buff_duration == 15


def test_item_def_rejects_sure_footed_with_potency():
    with pytest.raises(ValidationError):
        ItemDef(
            id="sure_footing_draught", name="Sure-Footing Draught", glyph="!", color=(1, 2, 3),
            grants_buff="sure_footed", buff_potency=1, buff_duration=15,
        )


def test_item_def_reveals_map_defaults_false():
    item = ItemDef(id="healing_potion", name="Healing Potion", glyph="!", color=(1, 2, 3))
    assert item.reveals_map is False


def test_item_def_accepts_reveals_map():
    potion = ItemDef(
        id="bottled_second_sight", name="Bottled Second Sight", glyph="!", color=(1, 2, 3),
        reveals_map=True,
    )
    assert potion.reveals_map is True


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


def test_dungeon_def_ruin_fields_default_to_unset():
    dungeon = DungeonDef(id="wayford", name="Wayford", starting_level="level_01")
    assert dungeon.ruined_tile is None
    assert dungeon.ruined_description == ""


def test_dungeon_def_accepts_ruin_fields_set_together():
    dungeon = DungeonDef(
        id="wayford", name="Wayford", starting_level="level_01",
        ruined_tile="road", ruined_description="Ash and quiet.",
    )
    assert dungeon.ruined_tile == "road"
    assert dungeon.ruined_description == "Ash and quiet."


@pytest.mark.parametrize(
    "kwargs", [{"ruined_tile": "road"}, {"ruined_description": "Ash and quiet."}]
)
def test_dungeon_def_rejects_ruin_fields_set_alone(kwargs):
    with pytest.raises(ValidationError):
        DungeonDef(id="wayford", name="Wayford", starting_level="level_01", **kwargs)


def test_dungeon_def_ruined_starting_level_defaults_none():
    dungeon = DungeonDef(id="wayford", name="Wayford", starting_level="level_01")
    assert dungeon.ruined_starting_level is None


def test_dungeon_def_accepts_ruined_starting_level_with_ruined_tile():
    dungeon = DungeonDef(
        id="wayford", name="Wayford", starting_level="level_01",
        ruined_tile="floor", ruined_description="Ash and quiet.",
        ruined_starting_level="level_01_ruins",
    )
    assert dungeon.ruined_starting_level == "level_01_ruins"


def test_dungeon_def_rejects_ruined_starting_level_without_ruined_tile():
    with pytest.raises(ValidationError, match="ruined_starting_level requires"):
        DungeonDef(
            id="wayford", name="Wayford", starting_level="level_01",
            ruined_starting_level="level_01_ruins",
        )


def test_dungeon_def_pre_arrival_fields_default_none():
    dungeon = DungeonDef(id="silver_mountain_caves", name="Silversilk Caves", starting_level="level_01")
    assert dungeon.pre_arrival_starting_level is None
    assert dungeon.pre_arrival_until_year is None
    assert dungeon.pre_arrival_until_day is None


def test_dungeon_def_accepts_pre_arrival_fields_together():
    dungeon = DungeonDef(
        id="silver_mountain_caves", name="Silversilk Caves", starting_level="level_01",
        pre_arrival_starting_level="level_01_undisturbed",
        pre_arrival_until_year=87, pre_arrival_until_day=67,
    )
    assert dungeon.pre_arrival_starting_level == "level_01_undisturbed"
    assert dungeon.pre_arrival_until_year == 87
    assert dungeon.pre_arrival_until_day == 67


def test_dungeon_def_rejects_pre_arrival_until_year_without_day():
    with pytest.raises(ValidationError, match="must be set together"):
        DungeonDef(
            id="silver_mountain_caves", name="Silversilk Caves", starting_level="level_01",
            pre_arrival_until_year=87,
        )


def test_dungeon_def_rejects_pre_arrival_starting_level_without_the_date_pair():
    with pytest.raises(ValidationError, match="pre_arrival_starting_level requires"):
        DungeonDef(
            id="silver_mountain_caves", name="Silversilk Caves", starting_level="level_01",
            pre_arrival_starting_level="level_01_undisturbed",
        )


def test_dungeon_def_rejects_pre_arrival_date_pair_without_starting_level():
    with pytest.raises(ValidationError, match="nothing to show before that date"):
        DungeonDef(
            id="silver_mountain_caves", name="Silversilk Caves", starting_level="level_01",
            pre_arrival_until_year=87, pre_arrival_until_day=67,
        )


def test_dungeon_def_balance_reference_xp_defaults_none():
    dungeon = DungeonDef(id="the_windrest", name="The Windrest", starting_level="level_01")
    assert dungeon.balance_reference_xp is None


def test_dungeon_def_accepts_balance_reference_xp():
    dungeon = DungeonDef(
        id="the_windrest", name="The Windrest", starting_level="level_01",
        balance_reference_xp=68,
    )
    assert dungeon.balance_reference_xp == 68


def test_level_def_normalizes_legend():
    level = LevelDef(
        id="l1",
        name="Test",
        map="#@#\n",
        legend={"#": "wall", "@": "player_start"},
    )
    assert level.legend["#"].tile == "wall"
    assert level.legend["@"].tile == "player_start"


def test_level_def_open_boundary_defaults_to_false():
    level = LevelDef(id="l1", name="Test", map="#@#\n", legend={"#": "wall", "@": "player_start"})
    assert level.open_boundary is False
    assert level.open_boundary_message == ""


def test_level_def_accepts_an_explicit_open_boundary():
    level = LevelDef(
        id="l1", name="Test", map="#@#\n", legend={"#": "wall", "@": "player_start"},
        open_boundary=True, open_boundary_message="You break off into the trees.",
    )
    assert level.open_boundary is True
    assert level.open_boundary_message == "You break off into the trees."


def test_level_def_player_start_tile_defaults_to_floor():
    level = LevelDef(id="l1", name="Test", map="#@#\n", legend={"#": "wall", "@": "player_start"})
    assert level.player_start_tile == "floor"


def test_level_def_accepts_a_walkable_player_start_tile_override():
    level = LevelDef(
        id="l1", name="Test", map="#@#\n", legend={"#": "wall", "@": "player_start"},
        player_start_tile="plains",
    )
    assert level.player_start_tile == "plains"


@pytest.mark.parametrize(
    "kind", ["wall", "door", "mountain", "sea", "deep_water", "stairs_down", "stairs_up", "dungeon_entrance", "player_start"]
)
def test_level_def_rejects_an_unwalkable_or_special_purpose_player_start_tile(kind):
    with pytest.raises(ValidationError):
        LevelDef(
            id="l1", name="Test", map="#@#\n", legend={"#": "wall", "@": "player_start"},
            player_start_tile=kind,
        )


def test_sprite_sheet_def_grid_sheet_requires_columns_and_rows():
    with pytest.raises(ValidationError, match="must set both 'columns' and 'rows'"):
        SpriteSheetDef(image="sheet.png", tile_size=16)


def test_sprite_sheet_def_indexed_sheet_does_not_require_columns_and_rows():
    sheet = SpriteSheetDef(image="rltiles-2d.png", tile_size=32, index="rltiles-2d.json")
    assert sheet.columns is None
    assert sheet.rows is None


def test_sprite_sheet_def_grid_sheet_with_columns_and_rows_is_valid():
    sheet = SpriteSheetDef(image="sheet.png", tile_size=16, columns=10, rows=5)
    assert sheet.columns == 10
    assert sheet.rows == 5


def test_sprite_ref_rejects_both_name_and_col_row():
    with pytest.raises(ValidationError, match="not both"):
        SpriteRef(sheet="rltiles", name="rat", col=0, row=0)


def test_sprite_ref_rejects_neither_name_nor_col_row():
    with pytest.raises(ValidationError, match="must set either"):
        SpriteRef(sheet="rltiles")


def test_sprite_ref_accepts_name_addressing():
    ref = SpriteRef(sheet="rltiles", name="rat")
    assert ref.name == "rat"
    assert ref.col is None


def test_sprite_ref_accepts_grid_addressing():
    ref = SpriteRef(sheet="kenney", col=6, row=0)
    assert ref.col == 6
    assert ref.row == 0


def test_sprite_ref_recolor_defaults_false():
    ref = SpriteRef(sheet="rltiles", name="human")
    assert ref.recolor is False


def test_world_consequence_accepts_destroy_dungeon_id_alone():
    consequence = WorldConsequence(destroy_dungeon_id="wayford")
    assert consequence.destroy_dungeon_id == "wayford"
    assert consequence.set_flag is None


def test_world_consequence_accepts_set_flag_alone():
    consequence = WorldConsequence(set_flag="wayford_population_thinned")
    assert consequence.set_flag == "wayford_population_thinned"
    assert consequence.destroy_dungeon_id is None


def test_world_consequence_rejects_both_destroy_dungeon_id_and_set_flag():
    with pytest.raises(ValidationError, match="exactly one"):
        WorldConsequence(destroy_dungeon_id="wayford", set_flag="wayford_razed")


def test_world_consequence_rejects_neither_destroy_dungeon_id_nor_set_flag():
    with pytest.raises(ValidationError, match="exactly one"):
        WorldConsequence()


def test_tighten_deadline_construction():
    tighten = TightenDeadline(quest_id="a_wall_worth_holding", new_day=66)
    assert tighten.quest_id == "a_wall_worth_holding"
    assert tighten.new_day == 66


def test_world_consequence_accepts_tighten_deadline_alone():
    consequence = WorldConsequence(
        tighten_deadline=TightenDeadline(quest_id="a_wall_worth_holding", new_day=66)
    )
    assert consequence.tighten_deadline.quest_id == "a_wall_worth_holding"
    assert consequence.destroy_dungeon_id is None
    assert consequence.set_flag is None


def test_world_consequence_rejects_tighten_deadline_with_destroy_dungeon_id():
    with pytest.raises(ValidationError, match="exactly one"):
        WorldConsequence(
            destroy_dungeon_id="wayford",
            tighten_deadline=TightenDeadline(quest_id="a_wall_worth_holding", new_day=66),
        )


def test_world_consequence_rejects_tighten_deadline_with_set_flag():
    with pytest.raises(ValidationError, match="exactly one"):
        WorldConsequence(
            set_flag="wayford_razed",
            tighten_deadline=TightenDeadline(quest_id="a_wall_worth_holding", new_day=66),
        )


def test_quest_def_on_fail_defaults_to_empty_list():
    quest = QuestDef(
        id="q1", name="Test Quest", description="A test.", completion_message="Done.",
    )
    assert quest.on_fail == []


def test_flag_dialogue_requires_flag():
    with pytest.raises(ValidationError):
        FlagDialogue(line="It's gone.")


def test_flag_dialogue_requires_line():
    with pytest.raises(ValidationError):
        FlagDialogue(flag="wayford_razed")


def test_flag_dialogue_accepts_both_fields():
    fd = FlagDialogue(flag="wayford_razed", line="It's gone.")
    assert fd.flag == "wayford_razed"
    assert fd.line == "It's gone."


def test_entity_def_xp_reward_and_trainer_perks_default():
    e = EntityDef(id="rat", name="Rat", glyph="r", color=(1, 2, 3), hp=5, attack=2, defense=0)
    assert e.xp_reward == 0
    assert e.trainer_perks == []


def test_entity_def_accepts_xp_reward_and_trainer_perks():
    e = EntityDef(
        id="wayford_trainer", name="Trainer", glyph="y", color=(1, 2, 3), hp=10, attack=0,
        defense=0, ai="villager", trainer_perks=["toughness_1", "weapon_training_1"],
    )
    assert e.trainer_perks == ["toughness_1", "weapon_training_1"]

    ogre = EntityDef(
        id="ogre", name="Ogre", glyph="O", color=(1, 2, 3), hp=28, attack=8, defense=3,
        xp_reward=14,
    )
    assert ogre.xp_reward == 14


def test_entity_def_rejects_negative_xp_reward():
    with pytest.raises(ValidationError):
        EntityDef(id="rat", name="Rat", glyph="r", color=(1, 2, 3), hp=5, attack=2, defense=0, xp_reward=-1)


def test_quest_def_accepts_reward_xp_amount():
    quest = QuestDef(
        id="q1", name="Test Quest", description="A test.", completion_message="Done.",
        reward_xp_amount=15,
    )
    assert quest.reward_xp_amount == 15


def test_quest_def_reward_xp_amount_defaults_none():
    quest = QuestDef(
        id="q1", name="Test Quest", description="A test.", completion_message="Done.",
    )
    assert quest.reward_xp_amount is None


def test_quest_def_rejects_nonpositive_reward_xp_amount():
    with pytest.raises(ValidationError):
        QuestDef(
            id="q1", name="Test Quest", description="A test.", completion_message="Done.",
            reward_xp_amount=0,
        )


def _perk_kwargs(**overrides):
    kwargs = dict(
        id="toughness_1", name="Toughness", description="Raises max HP.", xp_cost=40,
        max_hp_bonus=5,
    )
    kwargs.update(overrides)
    return kwargs


def test_perk_def_accepts_exactly_one_bonus():
    perk = PerkDef(**_perk_kwargs())
    assert perk.max_hp_bonus == 5
    assert perk.attack_bonus is None
    assert perk.defense_bonus is None
    assert perk.ranged_attack_bonus is None


def test_perk_def_accepts_attack_bonus_alone():
    perk = PerkDef(**_perk_kwargs(max_hp_bonus=None, attack_bonus=2))
    assert perk.attack_bonus == 2


def test_perk_def_accepts_defense_bonus_alone():
    perk = PerkDef(**_perk_kwargs(max_hp_bonus=None, defense_bonus=2))
    assert perk.defense_bonus == 2


def test_perk_def_accepts_ranged_attack_bonus_alone():
    perk = PerkDef(**_perk_kwargs(max_hp_bonus=None, ranged_attack_bonus=2))
    assert perk.ranged_attack_bonus == 2


def test_perk_def_rejects_zero_bonuses_set():
    with pytest.raises(ValidationError, match="exactly one"):
        PerkDef(**_perk_kwargs(max_hp_bonus=None))


def test_perk_def_rejects_more_than_one_bonus_set():
    with pytest.raises(ValidationError, match="exactly one"):
        PerkDef(**_perk_kwargs(attack_bonus=2))


def test_perk_def_rejects_nonpositive_xp_cost():
    with pytest.raises(ValidationError):
        PerkDef(**_perk_kwargs(xp_cost=0))


def test_perk_def_gold_cost_defaults_none():
    perk = PerkDef(**_perk_kwargs())
    assert perk.gold_cost is None


def test_perk_def_accepts_gold_cost():
    perk = PerkDef(**_perk_kwargs(gold_cost=10))
    assert perk.gold_cost == 10


def test_perk_def_rejects_nonpositive_gold_cost():
    with pytest.raises(ValidationError):
        PerkDef(**_perk_kwargs(gold_cost=0))


# --- passive rate bonuses (crit_chance_bonus/dodge_chance_bonus) ---


def test_perk_def_accepts_crit_chance_bonus_alone():
    perk = PerkDef(**_perk_kwargs(max_hp_bonus=None, crit_chance_bonus=0.05))
    assert perk.crit_chance_bonus == 0.05


def test_perk_def_accepts_dodge_chance_bonus_alone():
    perk = PerkDef(**_perk_kwargs(max_hp_bonus=None, dodge_chance_bonus=0.05))
    assert perk.dodge_chance_bonus == 0.05


def test_perk_def_rejects_crit_and_dodge_chance_bonus_together():
    with pytest.raises(ValidationError, match="exactly one"):
        PerkDef(**_perk_kwargs(max_hp_bonus=None, crit_chance_bonus=0.05, dodge_chance_bonus=0.05))


def test_perk_def_rejects_crit_chance_bonus_combined_with_attack_bonus():
    with pytest.raises(ValidationError, match="exactly one"):
        PerkDef(**_perk_kwargs(crit_chance_bonus=0.05))  # max_hp_bonus=5 already set by _perk_kwargs


def test_perk_def_rejects_out_of_range_crit_chance_bonus():
    with pytest.raises(ValidationError):
        PerkDef(**_perk_kwargs(max_hp_bonus=None, crit_chance_bonus=1.5))


# --- active skills (skill_effect/skill_cooldown_kind/skill_cooldown_amount) ---


def test_perk_def_accepts_a_heal_skill():
    perk = PerkDef(**_perk_kwargs(
        max_hp_bonus=None, skill_effect="heal", skill_heal_pct=0.5,
        skill_cooldown_kind="hours", skill_cooldown_amount=24,
    ))
    assert perk.skill_effect == "heal"
    assert perk.skill_heal_pct == 0.5
    assert perk.skill_cooldown_kind == "hours"
    assert perk.skill_cooldown_amount == 24


def test_perk_def_accepts_an_aoe_damage_skill():
    perk = PerkDef(**_perk_kwargs(
        max_hp_bonus=None, skill_effect="aoe_damage", skill_aoe_damage=4,
        skill_cooldown_kind="turns", skill_cooldown_amount=5,
    ))
    assert perk.skill_effect == "aoe_damage"
    assert perk.skill_aoe_damage == 4
    assert perk.skill_cooldown_kind == "turns"


def test_perk_def_rejects_skill_effect_combined_with_a_stat_bonus():
    with pytest.raises(ValidationError, match="either a passive"):
        PerkDef(**_perk_kwargs(
            skill_effect="heal", skill_heal_pct=0.5,
            skill_cooldown_kind="hours", skill_cooldown_amount=24,
        ))  # max_hp_bonus=5 still set by _perk_kwargs


def test_perk_def_rejects_skill_effect_without_cooldown_kind_or_amount():
    with pytest.raises(ValidationError, match="must all be set together"):
        PerkDef(**_perk_kwargs(max_hp_bonus=None, skill_effect="heal", skill_heal_pct=0.5))


def test_perk_def_rejects_skill_effect_without_cooldown_amount():
    with pytest.raises(ValidationError, match="must all be set together"):
        PerkDef(**_perk_kwargs(
            max_hp_bonus=None, skill_effect="heal", skill_heal_pct=0.5, skill_cooldown_kind="hours",
        ))


def test_perk_def_rejects_heal_skill_without_heal_pct():
    with pytest.raises(ValidationError, match="requires skill_heal_pct"):
        PerkDef(**_perk_kwargs(
            max_hp_bonus=None, skill_effect="heal",
            skill_cooldown_kind="hours", skill_cooldown_amount=24,
        ))


def test_perk_def_rejects_heal_skill_with_aoe_damage_set():
    with pytest.raises(ValidationError, match="only meaningful when skill_effect is 'aoe_damage'"):
        PerkDef(**_perk_kwargs(
            max_hp_bonus=None, skill_effect="heal", skill_heal_pct=0.5, skill_aoe_damage=4,
            skill_cooldown_kind="hours", skill_cooldown_amount=24,
        ))


def test_perk_def_rejects_aoe_damage_skill_without_aoe_damage():
    with pytest.raises(ValidationError, match="requires skill_aoe_damage"):
        PerkDef(**_perk_kwargs(
            max_hp_bonus=None, skill_effect="aoe_damage",
            skill_cooldown_kind="turns", skill_cooldown_amount=5,
        ))


def test_perk_def_rejects_aoe_damage_skill_with_heal_pct_set():
    with pytest.raises(ValidationError, match="only meaningful when skill_effect is 'heal'"):
        PerkDef(**_perk_kwargs(
            max_hp_bonus=None, skill_effect="aoe_damage", skill_aoe_damage=4, skill_heal_pct=0.5,
            skill_cooldown_kind="turns", skill_cooldown_amount=5,
        ))


def test_perk_def_rejects_out_of_range_skill_heal_pct():
    with pytest.raises(ValidationError):
        PerkDef(**_perk_kwargs(
            max_hp_bonus=None, skill_effect="heal", skill_heal_pct=1.5,
            skill_cooldown_kind="hours", skill_cooldown_amount=24,
        ))


# --- perk tiers (requires_perk_id) ---


def test_perk_def_requires_perk_id_defaults_none():
    perk = PerkDef(**_perk_kwargs())
    assert perk.requires_perk_id is None


def test_perk_def_accepts_requires_perk_id():
    perk = PerkDef(**_perk_kwargs(id="toughness_2", requires_perk_id="toughness_1"))
    assert perk.requires_perk_id == "toughness_1"
