"""Exercises the render layer headlessly (a Console with no SDL window/context),
to catch rendering bugs like bad glyph/color lookups without opening a game window."""

from pathlib import Path

import tcod.console

from content.loader import load_catalog, load_level, load_quests
from engine.engine import Engine, MessageLog
from engine.entity import (
    RENDER_PRIORITY_ACTOR,
    RENDER_PRIORITY_ITEM,
    RENDER_PRIORITY_PLAYER,
    Entity,
    Fighter,
    ItemEffect,
)
from engine.game_map import GameMap, build_game_map
from engine.quest import Quest, QuestLog, create_quest_log
from engine.render import (
    LOG_COLORS,
    TILE_VISUALS,
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
    render_message_log,
    render_quest_log,
    render_shop,
    render_target_frame,
)
from engine.sprites import SpriteCodepoints

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LEVELS_DIR = DATA_DIR / "dungeons" / "forgotten_ruins" / "levels"
QUESTS_PATH = DATA_DIR / "quests.yaml"


def real_quest_log() -> QuestLog:
    """The real starting QuestLog, built from data/quests.yaml the same way
    main.py builds it - for tests that exercise real quest content."""
    catalog = load_catalog()
    return create_quest_log(load_quests(QUESTS_PATH, catalog))


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


def test_render_hud_does_not_show_control_hints():
    """The control scheme was removed from the HUD (it took up a lot of
    space) - regression coverage so it doesn't quietly come back."""
    catalog = load_catalog()
    level = load_level(LEVELS_DIR / "level_01.lvl", catalog)
    game_map, player = build_game_map(level, catalog)
    engine = Engine(game_map, player, level.name, is_overworld=False)

    console = tcod.console.Console(70, 40, order="F")
    render_all(console, engine)

    text = console_text(console)
    assert "pick up" not in text
    assert "[t] talk" not in text
    assert "[esc] quit" not in text


def test_render_message_log_colors_each_category():
    log = MessageLog()
    log.add("You enter Millhaven Green.")  # default "info" category
    log.add("Rat hits you for 2 damage.", category="combat")
    log.add('Villager: "Hello."', category="dialogue")

    console = tcod.console.Console(70, 10, order="F")
    render_message_log(console, log, 0, 0)

    assert console.rgb[0, 0]["fg"].tolist() == list(LOG_COLORS["info"])
    assert console.rgb[0, 1]["fg"].tolist() == list(LOG_COLORS["combat"])
    assert console.rgb[0, 2]["fg"].tolist() == list(LOG_COLORS["dialogue"])


def test_render_message_log_keeps_category_across_a_wrapped_message():
    log = MessageLog()
    log.add("Rat hits you for two damage in melee combat today, for sure.", category="combat")

    console = tcod.console.Console(20, 10, order="F")
    render_message_log(console, log, 0, 0)

    assert console.rgb[0, 0]["fg"].tolist() == list(LOG_COLORS["combat"])
    assert console.rgb[0, 1]["fg"].tolist() == list(LOG_COLORS["combat"])


def test_render_hud_shows_the_world_clock():
    catalog = load_catalog()
    level = load_level(LEVELS_DIR / "level_01.lvl", catalog)
    game_map, player = build_game_map(level, catalog)
    engine = Engine(game_map, player, level.name)  # default clock: a fresh GameClock()

    console = tcod.console.Console(70, 40, order="F")
    render_all(console, engine)

    text = console_text(console)
    assert engine.clock.format_for_hud() in text


def test_render_hud_shows_the_active_quest():
    catalog = load_catalog()
    level = load_level(LEVELS_DIR / "level_01.lvl", catalog)
    game_map, player = build_game_map(level, catalog)
    quest_log = real_quest_log()
    engine = Engine(game_map, player, level.name, quest_log=quest_log)

    console = tcod.console.Console(70, 40, order="F")
    render_all(console, engine)

    text = console_text(console)
    assert quest_log.quests["goblin_warning"].format_for_hud() in text


def test_render_hud_shows_gold():
    catalog = load_catalog()
    level = load_level(LEVELS_DIR / "level_01.lvl", catalog)
    game_map, player = build_game_map(level, catalog)
    player.gold = 42
    engine = Engine(game_map, player, level.name)

    console = tcod.console.Console(70, 40, order="F")
    render_all(console, engine)

    text = console_text(console)
    assert "Gold: 42" in text


def test_render_hud_never_shows_a_not_given_quest():
    catalog = load_catalog()
    level = load_level(LEVELS_DIR / "level_01.lvl", catalog)
    game_map, player = build_game_map(level, catalog)
    quest_log = real_quest_log()  # kill_the_warden starts "not_given"
    engine = Engine(game_map, player, level.name, quest_log=quest_log)

    console = tcod.console.Console(70, 40, order="F")
    render_all(console, engine)

    text = console_text(console)
    kill_quest = quest_log.quests["kill_the_warden"]
    assert kill_quest.name not in text


def test_render_hud_only_shows_the_pinned_quest_even_with_two_in_progress():
    catalog = load_catalog()
    level = load_level(LEVELS_DIR / "level_01.lvl", catalog)
    game_map, player = build_game_map(level, catalog)
    quest_log = real_quest_log()
    quest_log.quests["kill_the_warden"].status = "in_progress"  # both now in progress
    engine = Engine(game_map, player, level.name, quest_log=quest_log)  # pinned: goblin_warning

    console = tcod.console.Console(70, 40, order="F")
    render_all(console, engine)

    text = console_text(console)
    assert quest_log.quests["goblin_warning"].name in text
    assert quest_log.quests["kill_the_warden"].name not in text


def test_render_quest_log_lists_quests_and_tags_the_active_one():
    goblin = Quest(
        id="goblin", name="The Goblin Warning", description="Warn the town.",
        completion_message="Done.", status="in_progress", deadline_year=87, deadline_day=57,
    )
    warden = Quest(
        id="warden", name="An Old Debt", description="Kill the Warden.",
        completion_message="Done.", status="in_progress",
    )
    console = tcod.console.Console(70, 20, order="F")

    render_quest_log(console, [goblin, warden], selected=0, active_quest_id="goblin", description=goblin.description)

    text = console_text(console)
    assert "The Goblin Warning" in text
    assert "An Old Debt" in text
    assert "[ACTIVE]" in text
    assert "Warn the town." in text  # the selected (index 0) quest's description


def test_render_quest_log_shows_the_caller_supplied_description():
    """render_quest_log never reads Quest.description itself (see
    Quest.current_description, which is what actually resolves it) - it
    just displays whatever description string the caller hands it."""
    goblin = Quest(
        id="goblin", name="The Goblin Warning", description="Warn the town.",
        completion_message="Done.", status="in_progress",
    )
    warden = Quest(
        id="warden", name="An Old Debt", description="Kill the Warden of Prison Tower.",
        completion_message="Done.", status="in_progress",
    )
    console = tcod.console.Console(70, 20, order="F")

    render_quest_log(
        console, [goblin, warden], selected=1, active_quest_id="goblin",
        description="A resolved description, not warden.description itself.",
    )

    text = console_text(console)
    assert "A resolved description, not warden.description itself." in text
    assert "Kill the Warden of Prison Tower." not in text
    assert "Warn the town." not in text


def test_render_shop_lists_items_with_cost_and_shows_gold():
    catalog = load_catalog()
    console = tcod.console.Console(70, 20, order="F")

    render_shop(
        console, catalog, ["healing_potion"], {"healing_potion": 25},
        selected=0, player_gold=100, status="",
    )

    text = console_text(console)
    assert "Healing Potion" in text
    assert "25 gold" in text
    assert "Your gold: 100" in text
    assert "A vial of crimson liquid that mends wounds." in text  # selected item's description


def test_render_shop_shows_the_caller_supplied_price_not_the_catalog_cost():
    """render_shop must never recompute a price itself - Engine.shop_price
    is the single source of truth, and this function just displays
    whatever it's handed."""
    catalog = load_catalog()
    console = tcod.console.Console(70, 20, order="F")

    render_shop(
        console, catalog, ["healing_potion"], {"healing_potion": 20},
        selected=0, player_gold=100, status="",
    )

    text = console_text(console)
    assert "20 gold" in text
    assert "25 gold" not in text


def test_render_shop_marks_unaffordable_items():
    catalog = load_catalog()
    console = tcod.console.Console(70, 20, order="F")

    render_shop(
        console, catalog, ["healing_potion"], {"healing_potion": 25},
        selected=0, player_gold=5, status="",
    )

    text = console_text(console)
    assert "can't afford" in text


def test_render_shop_does_not_mark_affordable_items():
    catalog = load_catalog()
    console = tcod.console.Console(70, 20, order="F")

    render_shop(
        console, catalog, ["healing_potion"], {"healing_potion": 25},
        selected=0, player_gold=100, status="",
    )

    text = console_text(console)
    assert "can't afford" not in text


def test_render_shop_shows_the_status_message():
    catalog = load_catalog()
    console = tcod.console.Console(70, 20, order="F")

    render_shop(
        console, catalog, ["healing_potion"], {"healing_potion": 25},
        selected=0, player_gold=100,
        status="You buy a Healing Potion for 25 gold.",
    )

    text = console_text(console)
    assert "You buy a Healing Potion for 25 gold." in text


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


def test_describe_tile_custom_description_overrides_the_generic_stairs_text():
    game_map = make_game_map()
    game_map.explored[1, 1] = True
    game_map.kinds[1, 1] = "stairs_up"
    game_map.tile_descriptions[(1, 1)] = "The town gate, leading back out onto the road."
    catalog = load_catalog()

    assert describe_tile(game_map, catalog, 1, 1) == [
        "The town gate, leading back out onto the road."
    ]


def test_describe_tile_landmark_generic_default():
    game_map = make_game_map()
    game_map.explored[1, 1] = True
    game_map.kinds[1, 1] = "landmark"
    catalog = load_catalog()

    assert describe_tile(game_map, catalog, 1, 1) == ["Something here catches your eye."]


def test_describe_tile_landmark_custom_description():
    game_map = make_game_map()
    game_map.explored[1, 1] = True
    game_map.kinds[1, 1] = "landmark"
    game_map.tile_descriptions[(1, 1)] = "A chalk tally board, its hatch-marks stopping mid-quota."
    catalog = load_catalog()

    assert describe_tile(game_map, catalog, 1, 1) == [
        "A chalk tally board, its hatch-marks stopping mid-quota."
    ]


def test_landmark_has_a_distinct_glyph_from_floor():
    assert TILE_VISUALS["landmark"]["glyph"] != TILE_VISUALS["floor"]["glyph"]
    assert TILE_VISUALS["landmark"]["glyph"] not in {"@", "#"}


def test_describe_tile_custom_description_overrides_locked_door_text():
    game_map = make_game_map()
    game_map.explored[1, 1] = True
    game_map.kinds[1, 1] = "door"
    game_map.locked_doors[(1, 1)] = "rusty_key"
    game_map.tile_descriptions[(1, 1)] = "A heavy iron-bound door."
    catalog = load_catalog()

    assert describe_tile(game_map, catalog, 1, 1) == ["A heavy iron-bound door."]


def test_describe_tile_dungeon_entrance_falls_back_to_generic_text_without_inspect_text():
    game_map = make_game_map()
    game_map.explored[1, 1] = True
    game_map.kinds[1, 1] = "dungeon_entrance"
    game_map.dungeon_entrances[(1, 1)] = "prison_tower"
    catalog = load_catalog()

    assert describe_tile(game_map, catalog, 1, 1) == ["An entrance leading underground."]


def test_describe_tile_dungeon_entrance_uses_dungeon_specific_inspect_text():
    game_map = make_game_map()
    game_map.explored[1, 1] = True
    game_map.kinds[1, 1] = "dungeon_entrance"
    game_map.dungeon_entrances[(1, 1)] = "prison_tower"
    catalog = load_catalog()

    lines = describe_tile(
        game_map, catalog, 1, 1,
        dungeon_inspect_text={"prison_tower": "A black stone tower.", "forgotten_ruins": "Ruins."},
    )

    assert lines == ["A black stone tower."]


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


def test_render_map_uses_a_sprite_codepoint_when_the_tile_kind_is_mapped():
    game_map = make_game_map(10, 10)
    game_map.kinds[5, 5] = "stairs_down"
    game_map.visible[5, 5] = True
    sprite_codepoints = SpriteCodepoints(tile_kinds={"stairs_down": 0xE000})

    console = tcod.console.Console(20, 20, order="F")
    render_map(console, game_map, cam_x=0, cam_y=0, sprite_codepoints=sprite_codepoints)

    assert console.rgb[5, 5]["ch"] == 0xE000


def test_render_map_falls_back_to_the_ascii_glyph_when_the_tile_kind_is_unmapped():
    game_map = make_game_map(10, 10)
    game_map.kinds[5, 5] = "stairs_down"
    game_map.visible[5, 5] = True
    # Mapped, but not for stairs_down - the "content added, sprite not made
    # yet" case this fallback exists for.
    sprite_codepoints = SpriteCodepoints(tile_kinds={"floor": 0xE000})

    console = tcod.console.Console(20, 20, order="F")
    render_map(console, game_map, cam_x=0, cam_y=0, sprite_codepoints=sprite_codepoints)

    assert chr(console.rgb[5, 5]["ch"]) == ">"


def test_render_map_with_no_sprite_codepoints_argument_is_ascii_identical():
    game_map = make_game_map(10, 10)
    game_map.kinds[5, 5] = "stairs_down"
    game_map.visible[5, 5] = True

    console = tcod.console.Console(20, 20, order="F")
    render_map(console, game_map, cam_x=0, cam_y=0)  # sprite_codepoints omitted

    assert chr(console.rgb[5, 5]["ch"]) == ">"


def test_render_entities_uses_a_sprite_codepoint_for_a_mapped_entity_id():
    game_map = make_game_map(10, 10)
    game_map.visible[5, 5] = True
    rat = Entity(
        5, 5, "r", (140, 90, 60), "Rat",
        render_priority=RENDER_PRIORITY_ACTOR,
        fighter=Fighter(max_hp=5, hp=5, attack=1, defense=0),
        entity_id="rat",
    )
    game_map.entities.append(rat)
    sprite_codepoints = SpriteCodepoints(entities={"rat": 0xE001})

    console = tcod.console.Console(20, 20, order="F")
    render_entities(console, game_map, cam_x=0, cam_y=0, sprite_codepoints=sprite_codepoints)

    assert console.rgb[5, 5]["ch"] == 0xE001


def test_render_entities_uses_a_sprite_codepoint_for_a_mapped_item_id():
    game_map = make_game_map(10, 10)
    game_map.visible[5, 5] = True
    potion = Entity(
        5, 5, "!", (220, 40, 100), "Healing Potion",
        item=ItemEffect(heal_amount=10),
        entity_id="healing_potion",
    )
    game_map.entities.append(potion)
    sprite_codepoints = SpriteCodepoints(items={"healing_potion": 0xE002})

    console = tcod.console.Console(20, 20, order="F")
    render_entities(console, game_map, cam_x=0, cam_y=0, sprite_codepoints=sprite_codepoints)

    assert console.rgb[5, 5]["ch"] == 0xE002


def test_render_entities_falls_back_to_the_ascii_glyph_for_an_unmapped_entity_id():
    game_map = make_game_map(10, 10)
    game_map.visible[5, 5] = True
    rat = Entity(
        5, 5, "r", (140, 90, 60), "Rat",
        render_priority=RENDER_PRIORITY_ACTOR,
        fighter=Fighter(max_hp=5, hp=5, attack=1, defense=0),
        entity_id="rat",
    )
    game_map.entities.append(rat)
    # Mapped, but not for "rat".
    sprite_codepoints = SpriteCodepoints(entities={"goblin": 0xE000})

    console = tcod.console.Console(20, 20, order="F")
    render_entities(console, game_map, cam_x=0, cam_y=0, sprite_codepoints=sprite_codepoints)

    assert chr(console.rgb[5, 5]["ch"]) == "r"


def test_render_entities_falls_back_for_an_entity_with_no_entity_id():
    """An entity_id of "" (never a real catalog id, and never what
    build_game_map gives the real player - see PLAYER_ENTITY_ID) always
    falls back, even if a sprite entry happens to share that empty key -
    defensive coverage for _resolved_glyph's own guard, not a real spawn
    shape."""
    game_map = make_game_map(10, 10)
    game_map.visible[5, 5] = True
    entity = Entity(
        5, 5, "@", (255, 255, 255), "Player",
        render_priority=RENDER_PRIORITY_PLAYER,
        fighter=Fighter(max_hp=10, hp=10, attack=1, defense=0),
    )
    game_map.entities.append(entity)
    sprite_codepoints = SpriteCodepoints(entities={"": 0xE000})

    console = tcod.console.Console(20, 20, order="F")
    render_entities(console, game_map, cam_x=0, cam_y=0, sprite_codepoints=sprite_codepoints)

    assert chr(console.rgb[5, 5]["ch"]) == "@"


def test_render_entities_uses_a_sprite_codepoint_for_the_mapped_player():
    """build_game_map gives the real player entity_id="player" (see
    content.loader.PLAYER_ENTITY_ID) - it resolves a sprite exactly like
    any other mapped entity once one is registered for that id."""
    game_map = make_game_map(10, 10)
    game_map.visible[5, 5] = True
    player = Entity(
        5, 5, "@", (255, 255, 255), "Player",
        render_priority=RENDER_PRIORITY_PLAYER,
        fighter=Fighter(max_hp=10, hp=10, attack=1, defense=0),
        entity_id="player",
    )
    game_map.entities.append(player)
    sprite_codepoints = SpriteCodepoints(entities={"player": 0xE003})

    console = tcod.console.Console(20, 20, order="F")
    render_entities(console, game_map, cam_x=0, cam_y=0, sprite_codepoints=sprite_codepoints)

    assert console.rgb[5, 5]["ch"] == 0xE003


def test_render_all_threads_engines_sprite_codepoints_through():
    game_map = make_game_map(10, 10)
    game_map.kinds[5, 5] = "floor"
    game_map.visible[5, 5] = True
    player = Entity(
        5, 5, "@", (255, 255, 255), "Player",
        render_priority=RENDER_PRIORITY_PLAYER,
        fighter=Fighter(max_hp=10, hp=10, attack=1, defense=0),
    )
    game_map.entities.append(player)
    sprite_codepoints = SpriteCodepoints(tile_kinds={"floor": 0xE010})
    engine = Engine(game_map, player, "Test Level", sprite_codepoints=sprite_codepoints)

    console = tcod.console.Console(70, 40, order="F")
    render_all(console, engine)

    assert 0xE010 in console.rgb["ch"]


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
