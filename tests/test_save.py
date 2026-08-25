"""Round-trip tests for engine/save.py, built the same way as
tests/test_main.py's own multi-place tests: real content, real
Engine/GameMap objects, direct state mutation (killing/picking
up/unlocking) mirroring how combat/pickup actions actually mutate state
rather than hand-building synthetic ParsedLevel/GameMap fixtures."""

import json
from pathlib import Path

from content.loader import load_catalog, load_dungeon_registry, load_encounters, load_overworld, load_quests
from engine.clock import GameClock
from engine.engine import Engine
from engine.game_map import build_game_map, item_entity_from_def
from engine.quest import create_quest_log
from engine.save import capture_save, load_from_path, restore_save, save_to_path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DUNGEONS_DIR = DATA_DIR / "dungeons"
OVERWORLD_LEVEL_PATH = DATA_DIR / "overworld.lvl"
QUESTS_PATH = DATA_DIR / "quests.yaml"
ENCOUNTERS_PATH = DATA_DIR / "encounters.yaml"
OVERWORLD_KEY = "overworld"


def _world():
    catalog = load_catalog()
    dungeon_registry = load_dungeon_registry(DUNGEONS_DIR, catalog)
    overworld_level = load_overworld(
        OVERWORLD_LEVEL_PATH, catalog, known_dungeon_ids=set(dungeon_registry)
    )
    quest_defs = load_quests(QUESTS_PATH, catalog, known_dungeon_ids=set(dungeon_registry))
    encounter_registry = load_encounters(
        ENCOUNTERS_PATH, known_dungeon_ids=set(dungeon_registry), known_quest_ids=set(quest_defs),
    )
    return catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry


def _prison_tower_engine(dungeon_registry, catalog, clock, quest_log) -> Engine:
    dungeon = dungeon_registry["prison_tower"]
    starting_level = dungeon.levels[dungeon.starting_level]
    game_map, player = build_game_map(starting_level, catalog)
    return Engine(
        game_map, player, starting_level.name,
        catalog=catalog, levels=dungeon.levels, starting_level=starting_level,
        clock=clock, quest_log=quest_log,
    )


def _overworld_engine(dungeon_registry, catalog, overworld_level, clock, quest_log) -> Engine:
    game_map, player = build_game_map(overworld_level, catalog)
    dungeon_ruin_data = {
        d_id: (d.ruined_tile, d.ruined_description)
        for d_id, d in dungeon_registry.items() if d.ruined_tile
    }
    return Engine(
        game_map, player, overworld_level.name,
        catalog=catalog, is_overworld=True, dungeon_ruin_data=dungeon_ruin_data,
        clock=clock, quest_log=quest_log,
    )


def _round_trip(save, tmp_path, catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry):
    path = tmp_path / "save.json"
    save_to_path(save, path)
    loaded = load_from_path(path)
    assert loaded is not None
    return restore_save(
        loaded, catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry, None, OVERWORLD_KEY,
    )


def test_round_trip_preserves_death_pickup_unlock_exploration_and_quest_progress(tmp_path):
    catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry = _world()
    clock = GameClock()
    quest_log = create_quest_log(quest_defs)
    engine = _prison_tower_engine(dungeon_registry, catalog, clock, quest_log)
    active_engines = {"prison_tower": engine}

    guard = next(e for e in engine.game_map.entities if e.name == "Guard")
    dagger = next(e for e in engine.game_map.entities if e.name == "Rusty Dagger")

    engine.on_entity_death(guard)
    engine.game_map.entities.remove(dagger)
    engine.player.inventory.append(dagger)
    engine.game_map.update_fov((engine.player.x, engine.player.y))
    quest_log.quests["kill_the_warden"].status = "in_progress"
    quest_log.armed_encounters["warning_ambush"] = (87, 51, 3)
    clock.advance_hour()

    save = capture_save("prison_tower", active_engines, clock, quest_log, overworld_level)
    active_key, active_engines2, clock2, quest_log2 = _round_trip(
        save, tmp_path, catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry,
    )

    engine2 = active_engines2[active_key]
    assert active_key == "prison_tower"
    assert not any(e.name == "Guard" for e in engine2.game_map.entities)
    assert any(it.name == "Rusty Dagger" for it in engine2.player.inventory)
    assert not any(e.name == "Rusty Dagger" for e in engine2.game_map.entities)
    assert engine2.game_map.explored[engine.player.x, engine.player.y]
    assert quest_log2.quests["kill_the_warden"].status == "in_progress"
    assert quest_log2.armed_encounters["warning_ambush"] == (87, 51, 3)
    assert (clock2.year, clock2.day, clock2.hour) == (clock.year, clock.day, clock.hour)
    assert engine2.player.x == engine.player.x
    assert engine2.player.y == engine.player.y


def test_round_trip_preserves_an_already_announced_tile(tmp_path):
    """The regression test for the feature's "once ever" promise: without
    persisting announced_tiles, a reload would re-fire an announcement the
    player already saw the first time that tile came back into FOV."""
    catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry = _world()
    clock = GameClock()
    quest_log = create_quest_log(quest_defs)
    engine = _prison_tower_engine(dungeon_registry, catalog, clock, quest_log)
    active_engines = {"prison_tower": engine}
    coord = (engine.player.x, engine.player.y)
    engine.game_map.auto_announce_tiles[coord] = "A flavorful landmark."
    engine.game_map.announced_tiles.add(coord)

    save = capture_save("prison_tower", active_engines, clock, quest_log, overworld_level)
    active_key, active_engines2, clock2, quest_log2 = _round_trip(
        save, tmp_path, catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry,
    )

    engine2 = active_engines2[active_key]
    engine2.game_map.auto_announce_tiles[coord] = "A flavorful landmark."  # static content, reapplied fresh
    assert coord in engine2.game_map.announced_tiles
    assert engine2.game_map.newly_seen_tile_announcements() == []


def test_round_trip_preserves_a_not_yet_seen_announce_tile(tmp_path):
    """A flagged tile the player hasn't reached yet must still announce
    normally after a restore - an empty announced_tiles shouldn't suppress
    a legitimate future announcement."""
    catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry = _world()
    clock = GameClock()
    quest_log = create_quest_log(quest_defs)
    engine = _prison_tower_engine(dungeon_registry, catalog, clock, quest_log)
    active_engines = {"prison_tower": engine}

    save = capture_save("prison_tower", active_engines, clock, quest_log, overworld_level)
    active_key, active_engines2, clock2, quest_log2 = _round_trip(
        save, tmp_path, catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry,
    )

    engine2 = active_engines2[active_key]
    coord = (engine2.player.x, engine2.player.y)
    engine2.game_map.auto_announce_tiles[coord] = "A flavorful landmark."
    engine2.game_map.update_fov(coord)

    assert engine2.game_map.newly_seen_tile_announcements() == [("A flavorful landmark.", False)]


def test_round_trip_preserves_selected_potion_kind(tmp_path):
    catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry = _world()
    clock = GameClock()
    quest_log = create_quest_log(quest_defs)
    engine = _prison_tower_engine(dungeon_registry, catalog, clock, quest_log)
    active_engines = {"prison_tower": engine}
    engine.player.selected_potion_kind = "teleport"

    save = capture_save("prison_tower", active_engines, clock, quest_log, overworld_level)
    active_key, active_engines2, _clock2, _quest_log2 = _round_trip(
        save, tmp_path, catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry,
    )

    assert active_engines2[active_key].player.selected_potion_kind == "teleport"


def test_restore_save_defaults_selected_potion_kind_for_an_old_format_save(tmp_path):
    """A save file written before selected_potion_kind existed has no such
    field - pydantic should fill in the default rather than erroring, so
    old saves keep loading."""
    catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry = _world()
    clock = GameClock()
    quest_log = create_quest_log(quest_defs)
    engine = _prison_tower_engine(dungeon_registry, catalog, clock, quest_log)
    active_engines = {"prison_tower": engine}

    save = capture_save("prison_tower", active_engines, clock, quest_log, overworld_level)
    path = tmp_path / "old_save.json"
    save_to_path(save, path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    del raw["player"]["selected_potion_kind"]
    path.write_text(json.dumps(raw), encoding="utf-8")

    loaded = load_from_path(path)
    active_key, active_engines2, _clock2, _quest_log2 = restore_save(
        loaded, catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry, None, OVERWORLD_KEY,
    )

    assert active_engines2[active_key].player.selected_potion_kind == "healing"


def test_round_trip_preserves_xp_and_re_derives_learned_perk_bonuses(tmp_path):
    """learned_perk_ids is the single source of truth for perk-derived stat
    totals - _build_player must re-derive fighter.max_hp/attack/defense/
    perk_ranged_attack_bonus from it plus catalog.perks at restore time,
    not double-apply anything already baked into saved.hp."""
    catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry = _world()
    clock = GameClock()
    quest_log = create_quest_log(quest_defs)
    engine = _prison_tower_engine(dungeon_registry, catalog, clock, quest_log)
    active_engines = {"prison_tower": engine}
    engine.player.xp = 25
    engine.player.learned_perk_ids.add("toughness_1")
    engine.player.fighter.max_hp += 5
    engine.player.fighter.hp += 5

    save = capture_save("prison_tower", active_engines, clock, quest_log, overworld_level)
    active_key, active_engines2, _clock2, _quest_log2 = _round_trip(
        save, tmp_path, catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry,
    )

    player2 = active_engines2[active_key].player
    assert player2.xp == 25
    assert player2.learned_perk_ids == {"toughness_1"}
    assert player2.fighter.max_hp == 35  # base 30 + the learned perk's bonus
    assert player2.fighter.hp == 35  # saved.hp already reflected the bump - not re-applied


def test_restore_save_defaults_xp_and_learned_perk_ids_for_an_old_format_save(tmp_path):
    """A save file written before xp/learned_perk_ids existed has neither
    field - pydantic should default to 0/empty rather than erroring, so old
    saves keep loading with unaffected base stats."""
    catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry = _world()
    clock = GameClock()
    quest_log = create_quest_log(quest_defs)
    engine = _prison_tower_engine(dungeon_registry, catalog, clock, quest_log)
    active_engines = {"prison_tower": engine}

    save = capture_save("prison_tower", active_engines, clock, quest_log, overworld_level)
    path = tmp_path / "old_save.json"
    save_to_path(save, path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    del raw["player"]["xp"]
    del raw["player"]["learned_perk_ids"]
    path.write_text(json.dumps(raw), encoding="utf-8")

    loaded = load_from_path(path)
    active_key, active_engines2, _clock2, _quest_log2 = restore_save(
        loaded, catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry, None, OVERWORLD_KEY,
    )

    player2 = active_engines2[active_key].player
    assert player2.xp == 0
    assert player2.learned_perk_ids == set()
    assert player2.fighter.max_hp == 30


def test_round_trip_of_a_dead_player_restores_dead_game_state(tmp_path):
    """game_state isn't part of the saved schema - it's re-derived from
    hp at restore time (see restore_save). Without this, a save captured
    while dead would restore with game_state defaulting back to
    "playing" despite non-positive hp, silently breaking RestartAction's
    own gate."""
    catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry = _world()
    clock = GameClock()
    quest_log = create_quest_log(quest_defs)
    engine = _prison_tower_engine(dungeon_registry, catalog, clock, quest_log)
    active_engines = {"prison_tower": engine}
    engine.player.fighter.hp = 0
    engine.game_state = "dead"

    save = capture_save("prison_tower", active_engines, clock, quest_log, overworld_level)
    active_key, active_engines2, _clock2, _quest_log2 = _round_trip(
        save, tmp_path, catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry,
    )

    assert active_engines2[active_key].game_state == "dead"


def test_round_trip_of_a_living_player_restores_playing_game_state(tmp_path):
    catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry = _world()
    clock = GameClock()
    quest_log = create_quest_log(quest_defs)
    engine = _prison_tower_engine(dungeon_registry, catalog, clock, quest_log)
    active_engines = {"prison_tower": engine}

    save = capture_save("prison_tower", active_engines, clock, quest_log, overworld_level)
    active_key, active_engines2, _clock2, _quest_log2 = _round_trip(
        save, tmp_path, catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry,
    )

    assert active_engines2[active_key].game_state == "playing"


def test_round_trip_preserves_a_cleared_non_current_level(tmp_path):
    """The multi-level gotcha: Engine.__init__ only ever seeds visited_maps
    with the *current* level - restore_save must separately re-insert every
    other visited level, or a previously-cleared one silently reverts to
    fresh the next time the player descends into it again."""
    catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry = _world()
    clock = GameClock()
    quest_log = create_quest_log(quest_defs)
    engine = _prison_tower_engine(dungeon_registry, catalog, clock, quest_log)
    active_engines = {"prison_tower": engine}

    for monster_name in ("Guard", "Crossbow Guard"):
        monster = next(e for e in engine.game_map.entities if e.name == monster_name)
        engine.on_entity_death(monster)

    engine.on_player_reach_stairs("level_02", "stairs_down")
    assert engine.current_level_id == "level_02"
    door_coord = next(iter(engine.game_map.locked_doors))
    engine.game_map.unlock_door(*door_coord)

    save = capture_save("prison_tower", active_engines, clock, quest_log, overworld_level)
    assert set(save.places["prison_tower"].levels) == {"level_01", "level_02"}

    active_key, active_engines2, clock2, quest_log2 = _round_trip(
        save, tmp_path, catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry,
    )
    engine2 = active_engines2[active_key]

    assert engine2.current_level_id == "level_02"
    assert door_coord not in engine2.game_map.locked_doors  # the CURRENT level's own delta
    assert "level_01" in engine2.visited_maps
    level_01_map = engine2.visited_maps["level_01"]
    assert not any(e.name in ("Guard", "Crossbow Guard") for e in level_01_map.entities)


def test_round_trip_with_two_places_of_different_sizes_does_not_crash_fov(tmp_path):
    """Real bug found via manual play: restore_save's loop used to pass the
    player Entity's CURRENT (active-place) x/y into every cached place's
    Engine constructor, including inactive ones - Engine.__init__
    unconditionally computes FOV around that position, which is nonsense
    (and can be out of bounds) for any place other than the active one,
    since prison_tower's Solitary Cell and the overworld are wildly
    different sizes."""
    catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry = _world()
    clock = GameClock()
    quest_log = create_quest_log(quest_defs)
    prison_engine = _prison_tower_engine(dungeon_registry, catalog, clock, quest_log)
    active_engines = {"prison_tower": prison_engine}

    player = prison_engine.depart_player()
    overworld_game_map, _ = build_game_map(overworld_level, catalog, player=player)
    player.x, player.y = 28, 46  # a real position, far outside prison_tower's tiny map
    overworld_engine = Engine(
        overworld_game_map, player, overworld_level.name,
        catalog=catalog, is_overworld=True, clock=clock, quest_log=quest_log,
    )
    active_engines["overworld"] = overworld_engine

    save = capture_save("overworld", active_engines, clock, quest_log, overworld_level)

    # Must not raise - previously an out-of-bounds tcod FOV computation
    # when reconstructing the inactive prison_tower place.
    active_key, active_engines2, _clock2, _quest_log2 = _round_trip(
        save, tmp_path, catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry,
    )

    assert active_key == "overworld"
    restored_engine = active_engines2["overworld"]
    assert (restored_engine.player.x, restored_engine.player.y) == (28, 46)
    # Catches a second, related bug: restore_save's loop only fixed up the
    # player's *final* position, not the position FOV was actually computed
    # around during this place's own Engine construction - if the active
    # place isn't first in save.places' iteration order (prison_tower is
    # inserted before overworld above), the previous non-active iteration's
    # temporary position leaked into the active place's own FOV computation,
    # leaving the player's real, current tile wrongly marked not-visible.
    assert bool(restored_engine.game_map.visible[28, 46]) is True


def test_round_trip_preserves_a_destroyed_dungeon(tmp_path):
    """The gap this closes: build_game_map always rebuilds the overworld
    from the static, unmodified level file - without restore_save
    re-applying every entry in destroyed_dungeon_ids, a save made after
    Wayford's destruction would silently un-raze it on reload."""
    catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry = _world()
    clock = GameClock()
    quest_log = create_quest_log(quest_defs)
    engine = _overworld_engine(dungeon_registry, catalog, overworld_level, clock, quest_log)
    active_engines = {"overworld": engine}
    entrance_coord = next(
        c for c, d_id in engine.game_map.dungeon_entrances.items() if d_id == "wayford"
    )

    engine.destroy_dungeon("wayford")
    assert entrance_coord not in engine.game_map.dungeon_entrances

    save = capture_save("overworld", active_engines, clock, quest_log, overworld_level)
    active_key, active_engines2, clock2, quest_log2 = _round_trip(
        save, tmp_path, catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry,
    )
    engine2 = active_engines2[active_key]

    assert quest_log2.destroyed_dungeon_ids == {"wayford"}
    assert entrance_coord not in engine2.game_map.dungeon_entrances
    assert engine2.game_map.kinds[entrance_coord] == "floor"
    assert engine2.game_map.tile_descriptions[entrance_coord] != ""


def test_round_trip_preserves_world_flags(tmp_path):
    """world_flags is plain bookkeeping with no map-mutation side effect
    (unlike destroyed_dungeon_ids above) - unlike that test, there's no
    real trigger to simulate here, just the save/restore plumbing, so this
    sets the flag directly rather than driving it through a real deadline
    (Engine._apply_world_consequences is covered separately in
    tests/test_engine.py)."""
    catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry = _world()
    clock = GameClock()
    quest_log = create_quest_log(quest_defs)
    engine = _overworld_engine(dungeon_registry, catalog, overworld_level, clock, quest_log)
    active_engines = {"overworld": engine}
    quest_log.world_flags.add("wayford_population_thinned")

    save = capture_save("overworld", active_engines, clock, quest_log, overworld_level)
    active_key, active_engines2, clock2, quest_log2 = _round_trip(
        save, tmp_path, catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry,
    )

    assert quest_log2.world_flags == {"wayford_population_thinned"}


def test_round_trip_preserves_intimidated_entity_ids(tmp_path):
    """Same shape and reasoning as killed_entity_ids/visited_dungeon_ids -
    without persisting this, a save made after intimidating an
    intimidate-quest target (but before reporting it) would silently lose
    that progress on reload."""
    catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry = _world()
    clock = GameClock()
    quest_log = create_quest_log(quest_defs)
    engine = _overworld_engine(dungeon_registry, catalog, overworld_level, clock, quest_log)
    active_engines = {"overworld": engine}
    quest_log.record_entity_intimidated("millhaven_debtor")

    save = capture_save("overworld", active_engines, clock, quest_log, overworld_level)
    active_key, active_engines2, clock2, quest_log2 = _round_trip(
        save, tmp_path, catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry,
    )

    assert quest_log2.intimidated_entity_ids == {"millhaven_debtor"}


def test_round_trip_preserves_guard_hostility_cooldown(tmp_path):
    """Without persisting GameMap.hostility_expires_at, a save made mid-
    cooldown would reload with guards_hostile comparing against None
    (permanently peaceful again) instead of the real remaining cooldown."""
    catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry = _world()
    clock = GameClock()
    quest_log = create_quest_log(quest_defs)
    engine = _prison_tower_engine(dungeon_registry, catalog, clock, quest_log)
    active_engines = {"prison_tower": engine}
    engine.game_map.trigger_guard_hostility(clock)

    save = capture_save("prison_tower", active_engines, clock, quest_log, overworld_level)
    active_key, active_engines2, clock2, _quest_log2 = _round_trip(
        save, tmp_path, catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry,
    )

    engine2 = active_engines2[active_key]
    assert engine2.game_map.hostility_expires_at == clock.plus_hours(7 * 24)
    assert engine2.game_map.guards_hostile(clock2) is True
    assert engine2.game_map.player_murdered_peaceful_npc is False


def test_round_trip_preserves_a_permanent_guard_hostility_murder(tmp_path):
    """Without persisting GameMap.player_murdered_peaceful_npc, a save made
    after killing a villager/guard would reload with that map's guards
    eventually going peaceful again once hostility_expires_at lapses."""
    catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry = _world()
    clock = GameClock()
    quest_log = create_quest_log(quest_defs)
    engine = _prison_tower_engine(dungeon_registry, catalog, clock, quest_log)
    active_engines = {"prison_tower": engine}
    engine.game_map.trigger_guard_hostility(clock)
    engine.game_map.mark_peaceful_npc_murdered()

    save = capture_save("prison_tower", active_engines, clock, quest_log, overworld_level)
    active_key, active_engines2, _clock2, _quest_log2 = _round_trip(
        save, tmp_path, catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry,
    )

    engine2 = active_engines2[active_key]
    assert engine2.game_map.player_murdered_peaceful_npc is True
    far_future = GameClock(*clock.plus_hours(365 * 24))
    assert engine2.game_map.guards_hostile(far_future) is True


def test_capture_save_records_a_tightened_deadline(tmp_path):
    catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry = _world()
    clock = GameClock()
    quest_log = create_quest_log(quest_defs)
    engine = _overworld_engine(dungeon_registry, catalog, overworld_level, clock, quest_log)
    active_engines = {"overworld": engine}
    quest_log.quests["a_wall_worth_holding"].deadline_day = 66

    save = capture_save("overworld", active_engines, clock, quest_log, overworld_level)

    assert save.quest_log.deadline_days["a_wall_worth_holding"] == 66


def test_restore_save_reapplies_a_tightened_deadline(tmp_path):
    """The regression test for the bug this field fixes: deadline_day was a
    write-once field until Engine._tighten_deadline - without persisting it,
    a save made after a tighten fires would silently revert to the
    authored QuestDef default (70) on reload."""
    catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry = _world()
    clock = GameClock()
    quest_log = create_quest_log(quest_defs)
    engine = _overworld_engine(dungeon_registry, catalog, overworld_level, clock, quest_log)
    active_engines = {"overworld": engine}
    quest_log.quests["a_wall_worth_holding"].deadline_day = 66
    assert quest_defs["a_wall_worth_holding"].deadline_day == 70  # the un-tightened authored default

    save = capture_save("overworld", active_engines, clock, quest_log, overworld_level)
    active_key, active_engines2, clock2, quest_log2 = _round_trip(
        save, tmp_path, catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry,
    )

    assert quest_log2.quests["a_wall_worth_holding"].deadline_day == 66


def test_restore_save_with_no_deadline_days_falls_back_to_authored_defaults(tmp_path):
    """Simulates a save made before this field existed - deadline_days
    defaults to {} (Field(default_factory=dict)), so every quest just
    keeps its own QuestDef-authored deadline, exactly as it did before
    tighten_deadline was ever a possibility."""
    catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry = _world()
    clock = GameClock()
    quest_log = create_quest_log(quest_defs)
    engine = _overworld_engine(dungeon_registry, catalog, overworld_level, clock, quest_log)
    active_engines = {"overworld": engine}

    save = capture_save("overworld", active_engines, clock, quest_log, overworld_level)
    save.quest_log.deadline_days = {}
    active_key, active_engines2, clock2, quest_log2 = _round_trip(
        save, tmp_path, catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry,
    )

    assert quest_log2.quests["a_wall_worth_holding"].deadline_day == 70


def test_round_trip_preserves_an_item_dropped_by_equipping_over_it(tmp_path):
    catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry = _world()
    clock = GameClock()
    quest_log = create_quest_log(quest_defs)
    engine = _prison_tower_engine(dungeon_registry, catalog, clock, quest_log)
    active_engines = {"prison_tower": engine}
    # Remove the level's own real Rusty Dagger spawn first, so it can't be
    # confused with the synthetic dropped one this test creates below.
    real_dagger = next(e for e in engine.game_map.entities if e.name == "Rusty Dagger")
    engine.game_map.entities.remove(real_dagger)

    old_weapon = item_entity_from_def(catalog.items["rusty_dagger"])
    engine.player.equipped_weapon = old_weapon
    new_weapon = item_entity_from_def(catalog.items["iron_sword"])

    # Mirror PickupAction._equip's drop-to-current-position behavior: the
    # replaced item lands on the ground where the player is standing, with
    # no item_spawns origin of its own.
    engine.player.equipped_weapon = new_weapon
    old_weapon.x, old_weapon.y = engine.player.x, engine.player.y
    engine.game_map.entities.append(old_weapon)

    save = capture_save("prison_tower", active_engines, clock, quest_log, overworld_level)
    active_key, active_engines2, clock2, quest_log2 = _round_trip(
        save, tmp_path, catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry,
    )
    engine2 = active_engines2[active_key]

    assert engine2.player.equipped_weapon is not None
    assert engine2.player.equipped_weapon.entity_id == "iron_sword"
    dropped = [
        e for e in engine2.game_map.entities
        if e.entity_id == "rusty_dagger" and e.item is not None
    ]
    assert len(dropped) == 1
    assert (dropped[0].x, dropped[0].y) == (engine.player.x, engine.player.y)


def test_round_trip_preserves_a_ground_item_carried_to_and_dropped_on_a_different_level(tmp_path):
    catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry = _world()
    clock = GameClock()
    quest_log = create_quest_log(quest_defs)
    engine = _prison_tower_engine(dungeon_registry, catalog, clock, quest_log)
    active_engines = {"prison_tower": engine}

    # Pick up the starting dagger from level_01 (a real item_spawns-indexed item).
    dagger = next(e for e in engine.game_map.entities if e.name == "Rusty Dagger")
    engine.game_map.entities.remove(dagger)
    engine.player.inventory.append(dagger)

    engine.on_player_reach_stairs("level_02", "stairs_down")
    assert engine.current_level_id == "level_02"

    # Now drop it on level_02 by equipping something else over it.
    engine.player.inventory.remove(dagger)
    dagger.x, dagger.y = engine.player.x, engine.player.y
    engine.game_map.entities.append(dagger)

    save = capture_save("prison_tower", active_engines, clock, quest_log, overworld_level)
    level_01_state = save.places["prison_tower"].levels["level_01"]
    level_02_state = save.places["prison_tower"].levels["level_02"]
    assert level_01_state.picked_up_item_spawns  # the dagger's original spawn index
    assert len(level_02_state.ground_items) == 1
    assert level_02_state.ground_items[0].entity_id == "rusty_dagger"

    active_key, active_engines2, clock2, quest_log2 = _round_trip(
        save, tmp_path, catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry,
    )
    engine2 = active_engines2[active_key]
    level_01_map = engine2.visited_maps["level_01"]

    assert not any(e.entity_id == "rusty_dagger" for e in level_01_map.entities)
    on_level_02 = [e for e in engine2.game_map.entities if e.entity_id == "rusty_dagger"]
    assert len(on_level_02) == 1
    assert (on_level_02[0].x, on_level_02[0].y) == (engine.player.x, engine.player.y)


def test_load_from_path_missing_file_returns_none(tmp_path):
    assert load_from_path(tmp_path / "does_not_exist.json") is None


def test_load_from_path_corrupt_file_returns_none(tmp_path):
    path = tmp_path / "corrupt.json"
    path.write_text("not valid json at all {{{", encoding="utf-8")
    assert load_from_path(path) is None
