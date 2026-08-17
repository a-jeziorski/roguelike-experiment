"""Entry point: loads level_01 from content files and runs the game."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import tcod
import tcod.event

from content.loader import ContentValidationError, load_catalog, load_dungeon
from engine.actions import RestartAction
from engine.engine import Engine
from engine.game_map import build_game_map
from engine.input_handlers import handle_event
from engine.render import render_all

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

                if isinstance(action, RestartAction):
                    if engine.game_state != "playing":
                        engine.restart()
                elif action is not None:
                    engine.process_turn(action)


if __name__ == "__main__":
    raise SystemExit(main())
