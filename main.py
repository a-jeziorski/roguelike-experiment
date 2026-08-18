"""Entry point: loads the dungeon registry and starts a run in the default dungeon."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import tcod
import tcod.event

from content.loader import (
    ContentValidationError,
    load_catalog,
    load_dungeon_registry,
    load_overworld,
)
from engine.actions import (
    DEFAULT_RANGED_RANGE,
    EscapeAction,
    FireAction,
    FireModeAction,
    LookAction,
    RestartAction,
)
from engine.engine import Engine
from engine.game_map import build_game_map
from engine.input_handlers import handle_event, handle_look_event, handle_target_event
from engine.render import (
    VIEWPORT_HEIGHT,
    VIEWPORT_WIDTH,
    compute_camera,
    flash_impact,
    projectile_glyph,
    projectile_path,
    render_all,
    render_look_frame,
    render_projectile,
    render_target_frame,
)
from engine.targeting import find_nearest_target

DUNGEONS_DIR = Path(__file__).resolve().parent / "data" / "dungeons"
OVERWORLD_LEVEL_PATH = Path(__file__).resolve().parent / "data" / "overworld.lvl"
STARTING_DUNGEON_ID = "prison_tower"
OVERWORLD_KEY = "overworld"

TILE_SIZE = 14
# The console must be at least as wide as the map viewport (no horizontal HUD
# sidebar); its extra rows below VIEWPORT_HEIGHT are the HUD/message log area,
# sized independently of any level's actual height - see engine/render.py.
CONSOLE_COLUMNS = VIEWPORT_WIDTH
CONSOLE_ROWS = 40

PROJECTILE_FRAME_SECONDS = 0.035
IMPACT_FLASH_SECONDS = 0.09

FONT_CANDIDATES = [
    Path(os.environ.get("SystemRoot", r"C:\Windows")) / "Fonts" / "consola.ttf",
    Path(os.environ.get("SystemRoot", r"C:\Windows")) / "Fonts" / "cour.ttf",
]


def load_tileset() -> tcod.tileset.Tileset:
    for candidate in FONT_CANDIDATES:
        if candidate.exists():
            return tcod.tileset.load_truetype_font(str(candidate), TILE_SIZE, TILE_SIZE)
    raise RuntimeError(
        "No usable monospace TTF font found. Tried: "
        + ", ".join(str(c) for c in FONT_CANDIDATES)
    )


def dispatch_action(engine: Engine, action) -> bool:
    """Routes a raw input Action to the engine. Returns True if the caller
    should quit.

    Escape and Restart are handled outside Engine.process_turn on purpose:
    process_turn no-ops once the game is no longer "playing" (so normal
    actions are ignored after death), which would otherwise silently
    swallow both quitting and restarting once the run has ended.
    """
    if isinstance(action, EscapeAction):
        return True
    if isinstance(action, RestartAction):
        if engine.game_state != "playing":
            engine.restart()
        return False
    if action is not None:
        engine.process_turn(action)
    return False


def fire_mode_gate(engine: Engine) -> str | None:
    """Whether targeting mode can currently be entered. Returns an error
    message to log if not, or None if run_target_mode should run - pulled
    out for testability without SDL, same reasoning as dispatch_action."""
    if engine.player.equipped_ranged_weapon is None:
        return "You have no ranged weapon equipped."
    if not any(it.item.is_ammo for it in engine.player.inventory):
        return "You have no ammo."
    return None


def run_target_mode(console: tcod.console.Console, context: tcod.context.Context, engine: Engine) -> tuple[int, int] | None:
    """Nested event loop for targeting: aims a cursor (starting on the
    nearest valid target) and re-renders until the player fires or cancels.
    Never touches Engine.process_turn - aiming costs no turn, only a
    confirmed shot does. Returns the chosen (x, y) to fire at, or None if
    cancelled."""
    weapon = engine.player.equipped_ranged_weapon
    max_range = weapon.item.range or DEFAULT_RANGED_RANGE
    nearest = find_nearest_target(engine.game_map, engine.player, max_range)
    cursor_x, cursor_y = (nearest.x, nearest.y) if nearest else (engine.player.x, engine.player.y)

    while True:
        render_target_frame(console, engine, cursor_x, cursor_y, max_range)
        context.present(console)

        for event in tcod.event.wait():
            context.convert_event(event)
            result = handle_target_event(event)

            if result == "cancel":
                return None
            if result == "fire":
                return (cursor_x, cursor_y)
            if isinstance(result, tuple):
                dx, dy = result
                cursor_x = max(0, min(engine.game_map.width - 1, cursor_x + dx))
                cursor_y = max(0, min(engine.game_map.height - 1, cursor_y + dy))


def run_look_mode(console: tcod.console.Console, context: tcod.context.Context, engine: Engine) -> None:
    """Nested event loop for look mode: moves a cursor and re-renders until the
    player exits. Never touches Engine.process_turn, so it costs no game turn."""
    cursor_x, cursor_y = engine.player.x, engine.player.y

    while True:
        render_look_frame(console, engine, cursor_x, cursor_y)
        context.present(console)

        for event in tcod.event.wait():
            context.convert_event(event)
            result = handle_look_event(event)

            if result == "exit":
                return
            if isinstance(result, tuple):
                dx, dy = result
                cursor_x = max(0, min(engine.game_map.width - 1, cursor_x + dx))
                cursor_y = max(0, min(engine.game_map.height - 1, cursor_y + dy))


def animate_ranged_attacks(
    console: tcod.console.Console, context: tcod.context.Context, engine: Engine
) -> None:
    """Plays a brief flying-projectile-then-impact-flash animation for every
    ranged attack Engine resolved during the last dispatched turn (player-
    fired via FireAction, or monster-fired via a ranged_basic AI's shot) and
    discards the events. Damage is already fully applied by the time this
    runs - Engine resolves combat synchronously and has no concept of
    animation frames - so this is pure visual flavor layered on top of
    already-final game state, not a step in Engine.process_turn."""
    events = engine.ranged_attack_events
    engine.ranged_attack_events = []
    cam_x, cam_y = compute_camera(
        engine.game_map.width, engine.game_map.height, VIEWPORT_WIDTH, VIEWPORT_HEIGHT,
        engine.player.x, engine.player.y,
    )

    for fx, fy, tx, ty in events:
        glyph = projectile_glyph(fx, fy, tx, ty)
        for x, y in projectile_path(fx, fy, tx, ty):
            render_all(console, engine)
            render_projectile(console, cam_x, cam_y, x, y, glyph)
            context.present(console)
            time.sleep(PROJECTILE_FRAME_SECONDS)

        render_all(console, engine)
        flash_impact(console, cam_x, cam_y, tx, ty)
        context.present(console)
        time.sleep(IMPACT_FLASH_SECONDS)


def animate_melee_attacks(
    console: tcod.console.Console, context: tcod.context.Context, engine: Engine
) -> None:
    """Same idea as animate_ranged_attacks but for melee hits: no travel to
    show, just the same impact flash on the struck tile, so a sword hit
    reads as an event on the map instead of only a message-log line."""
    events = engine.melee_attack_events
    engine.melee_attack_events = []
    cam_x, cam_y = compute_camera(
        engine.game_map.width, engine.game_map.height, VIEWPORT_WIDTH, VIEWPORT_HEIGHT,
        engine.player.x, engine.player.y,
    )

    for x, y in events:
        render_all(console, engine)
        flash_impact(console, cam_x, cam_y, x, y)
        context.present(console)
        time.sleep(IMPACT_FLASH_SECONDS)


def animate_combat_feedback(
    console: tcod.console.Console, context: tcod.context.Context, engine: Engine
) -> None:
    animate_melee_attacks(console, context, engine)
    animate_ranged_attacks(console, context, engine)


def _match_entrance(overworld_map, from_dungeon_id: str) -> tuple[int, int] | None:
    """The overworld tile whose dungeon_entrance targets from_dungeon_id, if
    one exists - where the player should land after leaving that dungeon.
    Re-derived on every arrival (never cached) since the player can return
    via a different dungeon than the one they last left through."""
    for coord, dungeon_id in overworld_map.dungeon_entrances.items():
        if dungeon_id == from_dungeon_id:
            return coord
    return None


def resolve_transition(
    active_key: str,
    engine: Engine,
    active_engines: dict[str, Engine],
    dungeon_registry: dict,
    overworld_level,
    catalog,
) -> tuple[str, Engine]:
    """After a dispatch, checks the active engine's transition mailbox
    (Engine.wants_overworld / Engine.pending_dungeon_entry) and performs the
    cross-Engine player handoff if one is pending, returning whichever
    (key, Engine) should be active next - unchanged if nothing is pending.

    Gated on game_state == "playing": if the player also died on the same
    turn they reached a leave-tile (a monster's retaliation after the move
    that triggered the transition), the death screen for that dungeon takes
    priority - the transition simply doesn't fire this turn.

    Each dungeon (and the overworld) gets at most one Engine, lazily created
    on first visit and cached in active_engines thereafter, so leaving and
    later returning resumes exactly the state that dungeon was left in.
    """
    if engine.game_state != "playing":
        return active_key, engine

    if engine.wants_overworld:
        player = engine.depart_player()
        target = active_engines.get(OVERWORLD_KEY)
        if target is None:
            game_map, _ = build_game_map(overworld_level, catalog, player=player)
            player.x, player.y = _match_entrance(game_map, active_key) or overworld_level.player_start
            dungeon_inspect_text = {d_id: d.inspect_text for d_id, d in dungeon_registry.items()}
            target = Engine(
                game_map, player, overworld_level.name,
                catalog=catalog, is_overworld=True, dungeon_inspect_text=dungeon_inspect_text,
            )
            active_engines[OVERWORLD_KEY] = target
        else:
            position = _match_entrance(target.game_map, active_key) or overworld_level.player_start
            target.arrive_player(player, position)
        return OVERWORLD_KEY, target

    if engine.pending_dungeon_entry is not None:
        dungeon_id = engine.pending_dungeon_entry
        player = engine.depart_player()
        target = active_engines.get(dungeon_id)
        if target is None:
            dungeon = dungeon_registry[dungeon_id]
            starting_level = dungeon.levels[dungeon.starting_level]
            game_map, _ = build_game_map(starting_level, catalog, player=player)
            target = Engine(
                game_map, player, starting_level.name,
                catalog=catalog, levels=dungeon.levels, starting_level=starting_level,
            )
            active_engines[dungeon_id] = target
        else:
            target.arrive_player(player)  # position=None: resume exactly where they left
        return dungeon_id, target

    return active_key, engine


def main() -> int:
    try:
        catalog = load_catalog()
        dungeon_registry = load_dungeon_registry(DUNGEONS_DIR, catalog)
        overworld_level = load_overworld(
            OVERWORLD_LEVEL_PATH, catalog, known_dungeon_ids=set(dungeon_registry)
        )
    except ContentValidationError as e:
        print(str(e), file=sys.stderr)
        return 1

    dungeon = dungeon_registry[STARTING_DUNGEON_ID]
    levels = dungeon.levels
    starting_level = levels[dungeon.starting_level]
    game_map, player = build_game_map(starting_level, catalog)
    engine = Engine(
        game_map,
        player,
        starting_level.name,
        catalog=catalog,
        levels=levels,
        starting_level=starting_level,
    )
    active_key = STARTING_DUNGEON_ID
    active_engines: dict[str, Engine] = {active_key: engine}

    tileset = load_tileset()

    with tcod.context.new(
        columns=CONSOLE_COLUMNS,
        rows=CONSOLE_ROWS,
        tileset=tileset,
        title="Claude-Authored Roguelike",
    ) as context:
        console = tcod.console.Console(CONSOLE_COLUMNS, CONSOLE_ROWS, order="F")

        while True:
            render_all(console, engine)
            context.present(console)

            for event in tcod.event.wait():
                context.convert_event(event)
                try:
                    action = handle_event(event)
                except SystemExit:
                    return 0

                if isinstance(action, LookAction):
                    if engine.game_state == "playing":
                        run_look_mode(console, context, engine)
                    continue

                if isinstance(action, FireModeAction):
                    if engine.game_state == "playing":
                        error = fire_mode_gate(engine)
                        if error:
                            engine.message_log.add(error)
                        else:
                            target = run_target_mode(console, context, engine)
                            if target is not None:
                                dispatch_action(engine, FireAction(*target))
                                animate_combat_feedback(console, context, engine)
                                active_key, engine = resolve_transition(
                                    active_key, engine, active_engines,
                                    dungeon_registry, overworld_level, catalog,
                                )
                    continue

                if dispatch_action(engine, action):
                    return 0
                animate_combat_feedback(console, context, engine)
                active_key, engine = resolve_transition(
                    active_key, engine, active_engines, dungeon_registry, overworld_level, catalog,
                )


if __name__ == "__main__":
    raise SystemExit(main())
