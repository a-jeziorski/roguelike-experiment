"""Exercises the render layer headlessly (a Console with no SDL window/context),
to catch rendering bugs like bad glyph/color lookups without opening a game window."""

from pathlib import Path

import tcod.console

from content.loader import load_catalog, load_level
from engine.engine import Engine
from engine.game_map import build_game_map
from engine.render import render_all

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def test_render_all_does_not_raise_for_level_01():
    catalog = load_catalog()
    level = load_level(DATA_DIR / "levels" / "level_01.lvl", catalog)
    game_map, player = build_game_map(level, catalog)
    engine = Engine(game_map, player, level.name)

    console = tcod.console.Console(70, 40, order="F")
    render_all(console, engine)  # should not raise
