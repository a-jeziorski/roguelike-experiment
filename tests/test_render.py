"""Exercises the render layer headlessly (a Console with no SDL window/context),
to catch rendering bugs like bad glyph/color lookups without opening a game window."""

from pathlib import Path

import tcod.console

from content.loader import load_catalog, load_level
from engine.engine import Engine
from engine.entity import RENDER_PRIORITY_ACTOR, RENDER_PRIORITY_ITEM, Entity, Fighter, ItemEffect
from engine.game_map import GameMap, build_game_map
from engine.render import describe_tile, render_all, render_look_frame, render_target_frame

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LEVELS_DIR = DATA_DIR / "dungeons" / "forgotten_ruins" / "levels"


def make_game_map(width: int = 3, height: int = 3) -> GameMap:
    game_map = GameMap(width, height)
    for x in range(width):
        for y in range(height):
            game_map.kinds[x, y] = "floor"
            game_map.walkable[x, y] = True
            game_map.transparent[x, y] = True
    return game_map


def console_text(console: tcod.console.Console) -> str:
    """Reconstructs every row of a console as text, for asserting on what
    actually made it to screen."""
    rows = []
    for y in range(console.height):
        rows.append(
            "".join(
                chr(console.rgb[x, y]["ch"]) if console.rgb[x, y]["ch"] else " "
                for x in range(console.width)
            )
        )
    return "\n".join(rows)


def test_render_all_does_not_raise_for_level_01():
    catalog = load_catalog()
    level = load_level(LEVELS_DIR / "level_01.lvl", catalog)
    game_map, player = build_game_map(level, catalog)
    engine = Engine(game_map, player, level.name)

    console = tcod.console.Console(70, 40, order="F")
    render_all(console, engine)  # should not raise


def test_long_monster_description_wraps_instead_of_being_clipped():
    """Regression test: console.print() silently truncates text past the
    console's right edge unless given an explicit width. A long, free-form
    monster description used to have its tail silently dropped in look mode -
    every word of it must now show up somewhere on screen instead."""
    catalog = load_catalog()
    level = load_level(LEVELS_DIR / "level_01.lvl", catalog)
    game_map, player = build_game_map(level, catalog)
    engine = Engine(game_map, player, level.name, catalog=catalog)
    game_map.visible[:] = True
    game_map.explored[:] = True

    long_description = (
        "This creature has an unusually long and rambling description that is "
        "deliberately far too wide to fit on a single console row without wrapping."
    )
    boss = Entity(
        player.x, player.y, "B", (255, 0, 0), "Test Boss",
        render_priority=RENDER_PRIORITY_ACTOR,
        fighter=Fighter(max_hp=10, hp=10, attack=1, defense=1),
        description=long_description,
    )
    game_map.entities.append(boss)

    console = tcod.console.Console(70, 40, order="F")
    render_look_frame(console, engine, player.x, player.y)

    text = console_text(console)
    for word in long_description.split():
        assert word in text, f"{word!r} missing from rendered output - description got clipped"


def test_render_look_frame_does_not_raise_for_level_01():
    catalog = load_catalog()
    level = load_level(LEVELS_DIR / "level_01.lvl", catalog)
    game_map, player = build_game_map(level, catalog)
    engine = Engine(game_map, player, level.name, catalog=catalog)

    console = tcod.console.Console(70, 40, order="F")
    render_look_frame(console, engine, player.x, player.y)  # should not raise


def test_render_target_frame_does_not_raise_for_level_01():
    catalog = load_catalog()
    level = load_level(LEVELS_DIR / "level_01.lvl", catalog)
    game_map, player = build_game_map(level, catalog)
    engine = Engine(game_map, player, level.name, catalog=catalog)

    console = tcod.console.Console(70, 40, order="F")
    render_target_frame(console, engine, player.x, player.y, max_range=5)  # should not raise
    render_target_frame(console, engine, player.x + 3, player.y, max_range=5)  # empty cursor tile


def test_describe_tile_unexplored():
    game_map = make_game_map()
    catalog = load_catalog()

    assert describe_tile(game_map, catalog, 1, 1) == ["You haven't explored this area."]


def test_describe_tile_terrain():
    game_map = make_game_map()
    game_map.explored[1, 1] = True
    game_map.kinds[1, 1] = "stairs_down"
    catalog = load_catalog()

    assert describe_tile(game_map, catalog, 1, 1) == ["Stairs leading down."]


def test_describe_tile_explored_but_not_visible_hides_entities():
    game_map = make_game_map()
    game_map.explored[1, 1] = True
    game_map.visible[1, 1] = False
    rat = Entity(
        1, 1, "r", (140, 90, 60), "Rat",
        render_priority=RENDER_PRIORITY_ACTOR,
        fighter=Fighter(max_hp=5, hp=5, attack=2, defense=0),
        description="A mangy sewer rat.",
    )
    game_map.entities.append(rat)
    catalog = load_catalog()

    assert describe_tile(game_map, catalog, 1, 1) == ["Bare floor."]


def test_describe_tile_visible_monster_shows_name_description_and_hp():
    game_map = make_game_map()
    game_map.explored[1, 1] = True
    game_map.visible[1, 1] = True
    rat = Entity(
        1, 1, "r", (140, 90, 60), "Rat",
        render_priority=RENDER_PRIORITY_ACTOR,
        fighter=Fighter(max_hp=5, hp=3, attack=2, defense=0),
        description="A mangy sewer rat.",
    )
    game_map.entities.append(rat)
    catalog = load_catalog()

    lines = describe_tile(game_map, catalog, 1, 1)
    assert lines == ["Bare floor.", "Rat: A mangy sewer rat. (HP: 3/5)"]


def test_describe_tile_visible_item_shows_name_and_description_without_hp():
    game_map = make_game_map()
    game_map.explored[1, 1] = True
    game_map.visible[1, 1] = True
    potion = Entity(
        1, 1, "!", (220, 40, 100), "Healing Potion",
        render_priority=RENDER_PRIORITY_ITEM,
        item=ItemEffect(heal_amount=10),
        description="A vial of crimson liquid.",
    )
    game_map.entities.append(potion)
    catalog = load_catalog()

    lines = describe_tile(game_map, catalog, 1, 1)
    assert lines == ["Bare floor.", "Healing Potion: A vial of crimson liquid."]


def test_describe_tile_locked_door_resolves_key_name():
    game_map = make_game_map()
    game_map.explored[1, 1] = True
    game_map.kinds[1, 1] = "door"
    game_map.locked_doors[(1, 1)] = "rusty_key"
    catalog = load_catalog()

    assert describe_tile(game_map, catalog, 1, 1) == ["Locked door. Requires: Rusty Key."]
