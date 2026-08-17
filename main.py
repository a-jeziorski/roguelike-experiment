"""Entry point: loads level_01 from content files and runs the game."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import tcod
import tcod.event

from content.loader import ContentValidationError, load_catalog, load_dungeon
from engine.actions import EscapeAction, LookAction, RestartAction
from engine.engine import Engine
from engine.game_map import build_game_map
from engine.input_handlers import handle_event, handle_look_event
from engine.render import render_all, render_look_frame

LEVELS_DIR = Path(__file__).resolve().parent / "data" / "levels"
STARTING_LEVEL_ID = "level_01"

TILE_SIZE = 14
CONSOLE_COLUMNS = 70
CONSOLE_ROWS = 40

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
    actions are ignored after death/win), which would otherwise silently
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


def main() -> int:
    try:
        catalog = load_catalog()
        levels = load_dungeon(LEVELS_DIR, catalog)
    except ContentValidationError as e:
        print(str(e), file=sys.stderr)
        return 1

    starting_level = levels[STARTING_LEVEL_ID]
    game_map, player = build_game_map(starting_level, catalog)
    engine = Engine(
        game_map,
        player,
        starting_level.name,
        catalog=catalog,
        levels=levels,
        starting_level=starting_level,
    )

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

                if dispatch_action(engine, action):
                    return 0


if __name__ == "__main__":
    raise SystemExit(main())
