"""Exercises the render layer headlessly (a Console with no SDL window/context),
to catch rendering bugs like bad glyph/color lookups without opening a game window."""

from pathlib import Path

import tcod.console

from content.loader import load_catalog, load_level
from engine.engine import Engine
from engine.entity import (
    RENDER_PRIORITY_ACTOR,
    RENDER_PRIORITY_ITEM,
    RENDER_PRIORITY_PLAYER,
    Entity,
    Fighter,
    ItemEffect,
)
from engine.game_map import GameMap, build_game_map
from engine.render import (
    VIEWPORT_HEIGHT,
    VIEWPORT_WIDTH,
    compute_camera,
    describe_tile,
    projectile_glyph,
    projectile_path,
    render_all,
    render_entities,
    render_look_frame,
    render_map,
    render_target_frame,
)

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


def test_render_hud_shows_reduced_controls_on_the_overworld():
    catalog = load_catalog()
    level = load_level(LEVELS_DIR / "level_01.lvl", catalog)
    game_map, player = build_game_map(level, catalog)
    engine = Engine(game_map, player, level.name, is_overworld=True)

    console = tcod.console.Console(70, 40, order="F")
    render_all(console, engine)

    text = console_text(console)
    assert "[l] look  [esc] quit" in text
    assert "pick up" not in text
    assert "fire" not in text


def test_render_hud_shows_full_controls_in_a_dungeon():
    catalog = load_catalog()
    level = load_level(LEVELS_DIR / "level_01.lvl", catalog)
    game_map, player = build_game_map(level, catalog)
    engine = Engine(game_map, player, level.name, is_overworld=False)

    console = tcod.console.Console(70, 40, order="F")
    render_all(console, engine)

    text = console_text(console)
    assert "pick up" in text
    assert "fire" in text


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


def test_compute_camera_small_map_never_scrolls():
    """A map no bigger than the viewport must render exactly like the old
    fixed full-map behavior: camera pinned at the origin no matter where the
    focus point is."""
    assert compute_camera(20, 15, VIEWPORT_WIDTH, VIEWPORT_HEIGHT, 5, 5) == (0, 0)
    assert compute_camera(20, 15, VIEWPORT_WIDTH, VIEWPORT_HEIGHT, 19, 14) == (0, 0)


def test_compute_camera_centers_on_focus_within_a_large_map():
    cam_x, cam_y = compute_camera(200, 100, VIEWPORT_WIDTH, VIEWPORT_HEIGHT, 100, 50)
    assert cam_x == 100 - VIEWPORT_WIDTH // 2
    assert cam_y == 50 - VIEWPORT_HEIGHT // 2


def test_compute_camera_clamps_at_map_edges():
    assert compute_camera(200, 100, VIEWPORT_WIDTH, VIEWPORT_HEIGHT, 0, 0) == (0, 0)
    cam_x, cam_y = compute_camera(200, 100, VIEWPORT_WIDTH, VIEWPORT_HEIGHT, 199, 99)
    assert (cam_x, cam_y) == (200 - VIEWPORT_WIDTH, 100 - VIEWPORT_HEIGHT)


def test_render_map_translates_by_camera_offset():
    game_map = make_game_map(10, 10)
    game_map.kinds[5, 5] = "stairs_down"
    game_map.visible[5, 5] = True

    console = tcod.console.Console(20, 20, order="F")
    render_map(console, game_map, cam_x=2, cam_y=3)

    assert chr(console.rgb[3, 2]["ch"]) == ">"  # (5,5) minus camera (2,3)


def test_render_entities_translates_by_camera_offset():
    game_map = make_game_map(10, 10)
    game_map.visible[5, 5] = True
    player = Entity(
        5, 5, "@", (255, 255, 255), "Player",
        render_priority=RENDER_PRIORITY_PLAYER,
        fighter=Fighter(max_hp=10, hp=10, attack=1, defense=0),
    )
    game_map.entities.append(player)

    console = tcod.console.Console(20, 20, order="F")
    render_entities(console, game_map, cam_x=2, cam_y=3)

    assert chr(console.rgb[3, 2]["ch"]) == "@"


def test_render_entities_hides_entities_scrolled_outside_the_viewport():
    game_map = make_game_map(10, 10)
    game_map.visible[9, 9] = True
    player = Entity(
        9, 9, "@", (255, 255, 255), "Player",
        render_priority=RENDER_PRIORITY_PLAYER,
        fighter=Fighter(max_hp=10, hp=10, attack=1, defense=0),
    )
    game_map.entities.append(player)

    console = tcod.console.Console(20, 20, order="F")
    render_entities(console, game_map, cam_x=50, cam_y=50)  # camera far from (9,9)

    text = console_text(console)
    assert "@" not in text


def test_render_all_places_hud_at_a_fixed_row_regardless_of_map_height():
    """Regression test: the HUD used to be anchored at game_map.height + 1,
    which pushed it below the console (and off screen) for any map taller
    than the console. A map far larger than the console in both directions
    must still render its HUD/HP line somewhere on screen."""
    game_map = GameMap(200, 120)
    for x in range(200):
        for y in range(120):
            game_map.kinds[x, y] = "floor"
            game_map.walkable[x, y] = True
            game_map.transparent[x, y] = True
    player = Entity(
        100, 110, "@", (255, 255, 255), "Player",
        blocks_movement=True,
        render_priority=RENDER_PRIORITY_PLAYER,
        fighter=Fighter(max_hp=30, hp=30, attack=5, defense=1),
    )
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Huge Level")

    console = tcod.console.Console(70, 40, order="F")
    render_all(console, engine)

    text = console_text(console)
    assert "HP: 30/30" in text
    assert "@" in text  # player stays visible - the camera followed them


def test_projectile_glyph_picks_direction():
    assert projectile_glyph(1, 1, 1, 5) == "|"  # straight down
    assert projectile_glyph(1, 1, 5, 1) == "-"  # straight right
    assert projectile_glyph(1, 1, 5, 5) == "\\"  # down-right
    assert projectile_glyph(5, 1, 1, 5) == "/"  # down-left


def test_projectile_path_excludes_shooter_and_includes_target():
    path = projectile_path(1, 1, 4, 1)
    assert path[0] != (1, 1)
    assert path[-1] == (4, 1)
    assert path == [(2, 1), (3, 1), (4, 1)]


def test_projectile_path_adjacent_shot_is_just_the_target():
    assert projectile_path(1, 1, 2, 1) == [(2, 1)]


def test_describe_tile_locked_door_resolves_key_name():
    game_map = make_game_map()
    game_map.explored[1, 1] = True
    game_map.kinds[1, 1] = "door"
    game_map.locked_doors[(1, 1)] = "rusty_key"
    catalog = load_catalog()

    assert describe_tile(game_map, catalog, 1, 1) == ["Locked door. Requires: Rusty Key."]
