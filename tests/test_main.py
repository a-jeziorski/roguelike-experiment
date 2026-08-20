"""Tests for main.py's action-dispatch glue - the interface between raw input
Actions and Engine/game-loop control. Pulled out into dispatch_action() so this
logic is testable without a real SDL window/event loop.

Regression coverage for a real bug: Escape only worked while game_state was
"playing", because Engine.process_turn no-ops once the run has ended, silently
swallowing the SystemExit that EscapeAction.perform() would otherwise raise."""

from pathlib import Path

from content.loader import load_catalog, load_dungeon_registry, load_levels, load_overworld
from engine.actions import BumpAction, EscapeAction, RestartAction, WaitAction
from engine.clock import GameClock
from engine.engine import Engine
from engine.entity import RENDER_PRIORITY_ITEM, Entity, ItemEffect
from engine.game_map import build_game_map
from main import DUNGEONS_DIR, OVERWORLD_KEY, OVERWORLD_LEVEL_PATH, dispatch_action, fire_mode_gate, resolve_transition

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LEVELS_DIR = DATA_DIR / "dungeons" / "forgotten_ruins" / "levels"


def make_engine() -> Engine:
    catalog = load_catalog()
    levels = load_levels(LEVELS_DIR, catalog)
    level_01 = levels["level_01"]
    game_map, player = build_game_map(level_01, catalog)
    return Engine(
        game_map,
        player,
        level_01.name,
        catalog=catalog,
        levels=levels,
        starting_level=level_01,
    )


def test_escape_quits_while_playing():
    engine = make_engine()
    assert dispatch_action(engine, EscapeAction()) is True


def test_escape_quits_after_death():
    engine = make_engine()
    engine.game_state = "dead"
    assert dispatch_action(engine, EscapeAction()) is True


def test_escape_quits_regardless_of_game_state():
    engine = make_engine()
    engine.game_state = "some-future-state"  # dispatch_action must not special-case values
    assert dispatch_action(engine, EscapeAction()) is True


def test_restart_is_ignored_while_playing():
    engine = make_engine()
    original_map = engine.game_map
    assert dispatch_action(engine, RestartAction()) is False
    assert engine.game_map is original_map
    assert engine.game_state == "playing"


def test_restart_is_applied_after_death():
    engine = make_engine()
    engine.game_state = "dead"
    assert dispatch_action(engine, RestartAction()) is False
    assert engine.game_state == "playing"


def test_normal_action_is_processed_while_playing():
    engine = make_engine()
    message_count_before = len(engine.message_log.messages)
    assert dispatch_action(engine, WaitAction()) is False
    assert len(engine.message_log.messages) == message_count_before


def test_none_action_is_a_noop():
    engine = make_engine()
    assert dispatch_action(engine, None) is False


def test_fire_mode_gate_blocks_without_a_ranged_weapon():
    engine = make_engine()
    assert fire_mode_gate(engine) == "You have no ranged weapon equipped."


def test_fire_mode_gate_blocks_without_ammo():
    engine = make_engine()
    engine.player.equipped_ranged_weapon = Entity(
        0, 0, "}", (160, 120, 70), "Hunting Bow",
        render_priority=RENDER_PRIORITY_ITEM,
        item=ItemEffect(ranged_attack_bonus=3, range=5),
    )
    assert fire_mode_gate(engine) == "You have no ammo."


def test_fire_mode_gate_allows_when_armed_and_stocked():
    engine = make_engine()
    engine.player.equipped_ranged_weapon = Entity(
        0, 0, "}", (160, 120, 70), "Hunting Bow",
        render_priority=RENDER_PRIORITY_ITEM,
        item=ItemEffect(ranged_attack_bonus=3, range=5),
    )
    engine.player.inventory.append(
        Entity(
            0, 0, "|", (190, 170, 140), "Arrows",
            render_priority=RENDER_PRIORITY_ITEM,
            item=ItemEffect(is_ammo=True, quantity=5),
        )
    )
    assert fire_mode_gate(engine) is None


def _world():
    """Real shipped content: catalog, dungeon registry, and the overworld -
    what resolve_transition actually needs at runtime."""
    catalog = load_catalog()
    dungeon_registry = load_dungeon_registry(DUNGEONS_DIR, catalog)
    overworld_level = load_overworld(
        OVERWORLD_LEVEL_PATH, catalog, known_dungeon_ids=set(dungeon_registry)
    )
    return catalog, dungeon_registry, overworld_level


def _entrance_for(overworld_level, dungeon_id: str) -> tuple[int, int]:
    entrance = next(e for e in overworld_level.dungeon_entrances if e.dungeon_id == dungeon_id)
    return (entrance.x, entrance.y)


def _dungeon_engine(dungeon_registry, catalog, dungeon_id: str, clock=None) -> Engine:
    dungeon = dungeon_registry[dungeon_id]
    starting_level = dungeon.levels[dungeon.starting_level]
    game_map, player = build_game_map(starting_level, catalog)
    return Engine(
        game_map, player, starting_level.name,
        catalog=catalog, levels=dungeon.levels, starting_level=starting_level,
        clock=clock,
    )


def test_resolve_transition_first_overworld_visit_lands_at_matched_entrance():
    catalog, dungeon_registry, overworld_level = _world()
    engine = _dungeon_engine(dungeon_registry, catalog, "prison_tower")
    engine.on_player_reach_stairs(None, "stairs_up")  # the retreat stairs near player_start

    active_key, new_engine = resolve_transition(
        "prison_tower", engine, {"prison_tower": engine}, dungeon_registry, overworld_level, catalog,
    )

    assert active_key == OVERWORLD_KEY
    assert new_engine.is_overworld is True
    assert (new_engine.player.x, new_engine.player.y) == _entrance_for(overworld_level, "prison_tower")


def test_resolve_transition_passes_the_given_clock_to_the_overworld_engine():
    catalog, dungeon_registry, overworld_level = _world()
    clock = GameClock()
    engine = _dungeon_engine(dungeon_registry, catalog, "prison_tower", clock=clock)
    engine.on_player_reach_stairs(None, "stairs_up")

    _, new_engine = resolve_transition(
        "prison_tower", engine, {"prison_tower": engine}, dungeon_registry, overworld_level, catalog,
        clock=clock,
    )

    assert new_engine.clock is clock


def test_resolve_transition_without_a_clock_still_works():
    catalog, dungeon_registry, overworld_level = _world()
    engine = _dungeon_engine(dungeon_registry, catalog, "prison_tower")
    engine.on_player_reach_stairs(None, "stairs_up")

    active_key, new_engine = resolve_transition(
        "prison_tower", engine, {"prison_tower": engine}, dungeon_registry, overworld_level, catalog,
    )

    assert active_key == OVERWORLD_KEY
    assert new_engine.clock == GameClock()


def test_resolve_transition_builds_overworld_engine_with_dungeon_inspect_text():
    catalog, dungeon_registry, overworld_level = _world()
    engine = _dungeon_engine(dungeon_registry, catalog, "prison_tower")
    engine.on_player_reach_stairs(None, "stairs_up")

    _, overworld_engine = resolve_transition(
        "prison_tower", engine, {"prison_tower": engine}, dungeon_registry, overworld_level, catalog,
    )

    assert overworld_engine.dungeon_inspect_text["prison_tower"] == dungeon_registry["prison_tower"].inspect_text
    assert overworld_engine.dungeon_inspect_text["forgotten_ruins"] == dungeon_registry["forgotten_ruins"].inspect_text


def test_resolve_transition_each_dungeons_departure_lands_at_its_own_entrance():
    catalog, dungeon_registry, overworld_level = _world()
    active_engines: dict = {}

    prison_engine = _dungeon_engine(dungeon_registry, catalog, "prison_tower")
    prison_engine.on_player_reach_stairs(None, "stairs_up")
    active_engines["prison_tower"] = prison_engine
    _, overworld_engine = resolve_transition(
        "prison_tower", prison_engine, active_engines, dungeon_registry, overworld_level, catalog,
    )

    ruins_engine = _dungeon_engine(dungeon_registry, catalog, "forgotten_ruins")
    ruins_engine.on_player_reach_stairs(None, "stairs_up")
    active_engines["forgotten_ruins"] = ruins_engine
    active_key, same_overworld_engine = resolve_transition(
        "forgotten_ruins", ruins_engine, active_engines, dungeon_registry, overworld_level, catalog,
    )

    assert active_key == OVERWORLD_KEY
    assert same_overworld_engine is overworld_engine  # cached, not rebuilt
    assert (same_overworld_engine.player.x, same_overworld_engine.player.y) == _entrance_for(
        overworld_level, "forgotten_ruins"
    )


def test_resolve_transition_reentering_a_dungeon_resumes_the_exact_retreat_spot():
    catalog, dungeon_registry, overworld_level = _world()
    active_engines: dict = {}

    prison_engine = _dungeon_engine(dungeon_registry, catalog, "prison_tower")
    original_map = prison_engine.game_map
    retreat_spot = (prison_engine.player.x, prison_engine.player.y)
    prison_engine.on_player_reach_stairs(None, "stairs_up")
    active_engines["prison_tower"] = prison_engine

    active_key, overworld_engine = resolve_transition(
        "prison_tower", prison_engine, active_engines, dungeon_registry, overworld_level, catalog,
    )
    assert active_key == OVERWORLD_KEY

    # Walk onto the prison_tower entrance tile on the overworld to trigger re-entry.
    overworld_engine.pending_dungeon_entry = "prison_tower"
    active_key, back_engine = resolve_transition(
        OVERWORLD_KEY, overworld_engine, active_engines, dungeon_registry, overworld_level, catalog,
    )

    assert active_key == "prison_tower"
    assert back_engine.game_map is original_map  # same cached map, not rebuilt
    assert (back_engine.player.x, back_engine.player.y) == retreat_spot


def test_resolve_transition_does_nothing_when_not_playing():
    catalog, dungeon_registry, overworld_level = _world()
    engine = _dungeon_engine(dungeon_registry, catalog, "prison_tower")
    engine.wants_overworld = True
    engine.game_state = "dead"  # e.g. killed the same turn a leave-tile was reached

    active_key, same_engine = resolve_transition(
        "prison_tower", engine, {"prison_tower": engine}, dungeon_registry, overworld_level, catalog,
    )

    assert active_key == "prison_tower"
    assert same_engine is engine
    assert engine.wants_overworld is True  # untouched - the death screen takes priority


def test_resolve_transition_round_trip_preserves_dungeon_state():
    catalog, dungeon_registry, overworld_level = _world()
    active_engines: dict = {}

    prison_engine = _dungeon_engine(dungeon_registry, catalog, "prison_tower")
    guard = next(e for e in prison_engine.game_map.entities if e.name == "Guard")
    prison_engine.on_entity_death(guard)
    assert guard not in prison_engine.game_map.entities

    prison_engine.on_player_reach_stairs(None, "stairs_up")
    active_engines["prison_tower"] = prison_engine
    active_key, overworld_engine = resolve_transition(
        "prison_tower", prison_engine, active_engines, dungeon_registry, overworld_level, catalog,
    )

    # Detour: overworld -> forgotten_ruins -> overworld -> back to prison_tower.
    overworld_engine.pending_dungeon_entry = "forgotten_ruins"
    active_key, ruins_engine = resolve_transition(
        active_key, overworld_engine, active_engines, dungeon_registry, overworld_level, catalog,
    )
    ruins_engine.on_player_reach_stairs(None, "stairs_up")
    active_key, overworld_engine_2 = resolve_transition(
        active_key, ruins_engine, active_engines, dungeon_registry, overworld_level, catalog,
    )
    assert overworld_engine_2 is overworld_engine  # still the one cached overworld Engine

    overworld_engine_2.pending_dungeon_entry = "prison_tower"
    active_key, prison_engine_2 = resolve_transition(
        active_key, overworld_engine_2, active_engines, dungeon_registry, overworld_level, catalog,
    )

    assert active_key == "prison_tower"
    assert prison_engine_2 is prison_engine
    assert guard not in prison_engine_2.game_map.entities  # still dead after the detour


def test_overworld_has_all_ten_shipped_entrances_mutually_reachable():
    """Every dungeon_entrance on the real overworld map must be reachable from
    player_start via ordinary 8-directional movement, and vice versa - a
    location an entrance leads to that nothing can walk to would be shippable
    content nobody could ever reach."""
    catalog, dungeon_registry, overworld_level = _world()

    assert {e.dungeon_id for e in overworld_level.dungeon_entrances} == set(dungeon_registry)
    assert len(overworld_level.dungeon_entrances) == 10

    game_map, _ = build_game_map(overworld_level, catalog)

    from collections import deque

    start = overworld_level.player_start
    seen = {start}
    queue = deque([start])
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

    for entrance in overworld_level.dungeon_entrances:
        assert (entrance.x, entrance.y) in seen, (
            f"{entrance.dungeon_id} entrance at ({entrance.x}, {entrance.y}) "
            "is unreachable from player_start"
        )
