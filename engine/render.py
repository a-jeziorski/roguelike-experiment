"""Draws the game map, entities, HUD, and message log onto a tcod Console.

Text that might run longer than the console is wide (monster/item descriptions
especially - they're free-form authored content, length isn't controlled) must
never be handed to console.print() without an explicit width: tcod does not
wrap by default, it silently clips at the console's right edge. Every print in
this module that isn't a single map glyph goes through a width= bound (either
directly via console.print's own wrapping, which returns how many lines it
used, or via textwrap for the message log's "does this still fit" trimming
logic) and every multi-line region uses a running y cursor instead of
hardcoded offsets, so the layout still holds together when something wraps to
more than one line.

The map itself is drawn through a fixed-size camera viewport (VIEWPORT_WIDTH x
VIEWPORT_HEIGHT) rather than 1:1 onto the console: a level's dimensions are
authored content and can exceed the console's size in either direction, so map
coordinates always go through compute_camera() + a `- cam_x, - cam_y`
translation before hitting console.print()/console.rgb - never printed at raw
map coordinates. The HUD/log area is anchored at the fixed row VIEWPORT_HEIGHT
+ 1, independent of the map's actual height, for the same reason."""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

import tcod.los

from engine.targeting import is_valid_target

if TYPE_CHECKING:
    from tcod.console import Console

    from content.loader import Catalog
    from engine.engine import Engine, MessageLog
    from engine.game_map import GameMap
    from engine.quest import Quest

TILE_VISUALS = {
    "wall": {"glyph": "#", "dark": (35, 35, 55), "light": (100, 100, 130)},
    "floor": {"glyph": ".", "dark": (25, 25, 35), "light": (75, 75, 95)},
    "stairs_down": {"glyph": ">", "dark": (65, 45, 15), "light": (210, 160, 60)},
    "stairs_up": {"glyph": "<", "dark": (65, 45, 15), "light": (210, 160, 60)},
    "door": {"glyph": "+", "dark": (70, 45, 15), "light": (170, 110, 40)},
    # A walkable point of interest (furniture, a landmark) - distinct from
    # both plain floor and from entity/item glyphs so it reads as "look
    # closer here" without being mistaken for something to fight or pick up.
    "landmark": {"glyph": "'", "dark": (95, 80, 55), "light": (200, 175, 130)},
    # Overworld terrain.
    "mountain": {"glyph": "^", "dark": (70, 65, 60), "light": (150, 140, 130)},
    "sea": {"glyph": "~", "dark": (15, 40, 80), "light": (60, 110, 200)},
    "forest": {"glyph": "T", "dark": (20, 50, 25), "light": (60, 140, 60)},
    "road": {"glyph": ".", "dark": (60, 50, 30), "light": (150, 130, 80)},
    "plains": {"glyph": ",", "dark": (35, 45, 20), "light": (120, 150, 70)},
    "town": {"glyph": "n", "dark": (80, 60, 25), "light": (210, 170, 90)},
    "dungeon_entrance": {"glyph": "O", "dark": (90, 60, 10), "light": (255, 200, 60)},
}

TILE_DESCRIPTIONS = {
    "wall": "Wall.",
    "floor": "Bare floor.",
    "stairs_down": "Stairs leading down.",
    "stairs_up": "Stairs leading up.",
    "mountain": "Impassable mountains.",
    "sea": "Open water, too deep to cross.",
    "forest": "Dense woodland.",
    "road": "A worn dirt road.",
    "plains": "Open grassland.",
    "town": "A small settlement.",
    "dungeon_entrance": "An entrance leading underground.",
    "landmark": "Something here catches your eye.",
}

HUD_FG = (220, 220, 220)
# One color per MessageLog category (see engine/engine.py's Message) - keeps
# the log scannable now that combat/dialogue/quest features all write to it
# in the same run: combat in red, spoken NPC lines in blue, everything else
# (level transitions, item/door feedback, quest updates - "descriptive" text
# in the same spirit as look mode's) in yellow.
LOG_COLORS = {
    "combat": (210, 70, 70),
    "dialogue": (100, 150, 230),
    "info": (210, 190, 90),
}
DEAD_FG = (220, 50, 50)
CURSOR_BG = (90, 90, 20)
TARGET_VALID_BG = (40, 120, 40)
TARGET_INVALID_BG = (110, 40, 40)
PROJECTILE_FG = (255, 230, 120)
IMPACT_BG = (200, 60, 30)

MESSAGE_LOG_HEIGHT = 5

# The map is drawn into this fixed-size window regardless of a level's actual
# size; VIEWPORT_HEIGHT leaves room below it for the HUD (up to ~7 lines) plus
# a blank separator plus MESSAGE_LOG_HEIGHT lines within main.py's CONSOLE_ROWS.
VIEWPORT_WIDTH = 70
VIEWPORT_HEIGHT = 26


def compute_camera(
    map_width: int, map_height: int, viewport_width: int, viewport_height: int, focus_x: int, focus_y: int
) -> tuple[int, int]:
    """Top-left map coordinate the viewport should render from, centered on
    (focus_x, focus_y) and clamped so the camera never scrolls past the map's
    edges - or, for a map no bigger than the viewport, never scrolls at all,
    reproducing the old fixed full-map render as the small-map special case."""
    cam_x = focus_x - viewport_width // 2
    cam_y = focus_y - viewport_height // 2
    cam_x = max(0, min(cam_x, max(0, map_width - viewport_width)))
    cam_y = max(0, min(cam_y, max(0, map_height - viewport_height)))
    return cam_x, cam_y


def render_map(console: "Console", game_map: "GameMap", cam_x: int, cam_y: int) -> None:
    visible_width = min(VIEWPORT_WIDTH, game_map.width - cam_x)
    visible_height = min(VIEWPORT_HEIGHT, game_map.height - cam_y)
    for sx in range(visible_width):
        x = cam_x + sx
        for sy in range(visible_height):
            y = cam_y + sy
            visual = TILE_VISUALS[game_map.kinds[x, y]]
            if game_map.visible[x, y]:
                console.print(sx, sy, visual["glyph"], fg=visual["light"])
            elif game_map.explored[x, y]:
                console.print(sx, sy, visual["glyph"], fg=visual["dark"])


def render_entities(console: "Console", game_map: "GameMap", cam_x: int, cam_y: int) -> None:
    for entity in sorted(game_map.entities, key=lambda e: e.render_priority):
        if not game_map.visible[entity.x, entity.y]:
            continue
        sx, sy = entity.x - cam_x, entity.y - cam_y
        if 0 <= sx < VIEWPORT_WIDTH and 0 <= sy < VIEWPORT_HEIGHT:
            console.print(sx, sy, entity.glyph, fg=entity.color)


def projectile_glyph(fx: int, fy: int, tx: int, ty: int) -> str:
    """Picks a glyph matching a shot's line of travel, so a flying arrow/bolt
    reads as a directional streak rather than a generic marker."""
    dx, dy = tx - fx, ty - fy
    if dx == 0:
        return "|"
    if dy == 0:
        return "-"
    return "\\" if (dx > 0) == (dy > 0) else "/"


def projectile_path(fx: int, fy: int, tx: int, ty: int) -> list[tuple[int, int]]:
    """Cells a projectile crosses, from just past the shooter through the
    target. The shooter's own tile is excluded so the glyph never draws on
    top of them."""
    return [(int(x), int(y)) for x, y in tcod.los.bresenham((fx, fy), (tx, ty)).tolist()[1:]]


def render_projectile(console: "Console", cam_x: int, cam_y: int, x: int, y: int, glyph: str) -> None:
    sx, sy = x - cam_x, y - cam_y
    if 0 <= sx < VIEWPORT_WIDTH and 0 <= sy < VIEWPORT_HEIGHT:
        console.print(sx, sy, glyph, fg=PROJECTILE_FG)


def flash_impact(console: "Console", cam_x: int, cam_y: int, x: int, y: int) -> None:
    sx, sy = x - cam_x, y - cam_y
    if 0 <= sx < VIEWPORT_WIDTH and 0 <= sy < VIEWPORT_HEIGHT:
        console.rgb[sx, sy]["bg"] = IMPACT_BG


def render_hud(console: "Console", engine: "Engine", y: int) -> int:
    """Prints the HUD starting at row y, wrapping any line too long for the
    console. Returns the row just past the last line printed, so callers can
    place whatever comes next without assuming a fixed HUD height."""
    width = console.width
    player = engine.player
    fighter = player.fighter
    inventory = player.inventory
    potions = sum(1 for it in inventory if it.item.heal_amount)
    keys = sum(1 for it in inventory if it.item.key_id)
    ammo = sum(it.item.quantity for it in inventory if it.item.is_ammo)
    weapon_name = player.equipped_weapon.name if player.equipped_weapon else "none"
    armor_name = player.equipped_armor.name if player.equipped_armor else "none"
    ranged_name = player.equipped_ranged_weapon.name if player.equipped_ranged_weapon else "none"

    y += console.print(0, y, engine.level_name, fg=HUD_FG, width=width)
    y += console.print(0, y, engine.clock.format_for_hud(), fg=HUD_FG, width=width)
    active_quest = engine.quest_log.active_quest()
    if active_quest is not None:
        y += console.print(0, y, active_quest.format_for_hud(), fg=HUD_FG, width=width)
    y += console.print(0, y, f"HP: {fighter.hp}/{fighter.max_hp}", fg=HUD_FG, width=width)
    y += console.print(
        0,
        y,
        f"ATK: {player.effective_attack}  DEF: {player.effective_defense}",
        fg=HUD_FG,
        width=width,
    )
    y += console.print(
        0,
        y,
        f"Weapon: {weapon_name}  Armor: {armor_name}  Ranged: {ranged_name}",
        fg=HUD_FG,
        width=width,
    )
    y += console.print(
        0, y, f"Potions: {potions}  Keys: {keys}  Ammo: {ammo}  Gold: {player.gold}",
        fg=HUD_FG, width=width,
    )
    if engine.game_state == "dead":
        y += console.print(
            0, y, "You have died. [r] play again  [esc] quit", fg=DEAD_FG, width=width
        )

    return y


def render_message_log(console: "Console", message_log: "MessageLog", x: int, y: int) -> None:
    """Fills whatever vertical space remains below y (up to MESSAGE_LOG_HEIGHT
    lines) with the most recent messages, wrapping each to fit and dropping
    older messages that no longer fit rather than clipping any single one.
    Each wrapped line keeps its source message's category (LOG_COLORS) so a
    message that wraps to two lines doesn't lose its color partway through."""
    width = max(console.width - x, 1)
    max_lines = min(MESSAGE_LOG_HEIGHT, max(console.height - y, 0))
    if max_lines == 0:
        return

    lines: list[tuple[str, str]] = []
    for message in reversed(message_log.messages):
        wrapped = textwrap.wrap(message, width) or [message]
        wrapped_with_category = [(line, message.category) for line in wrapped]
        if len(lines) + len(wrapped_with_category) > max_lines:
            break
        lines = wrapped_with_category + lines

    for i, (line, category) in enumerate(lines):
        console.print(x, y + i, line, fg=LOG_COLORS.get(category, LOG_COLORS["info"]), width=width)


def render_all(console: "Console", engine: "Engine") -> None:
    console.clear()
    cam_x, cam_y = compute_camera(
        engine.game_map.width, engine.game_map.height, VIEWPORT_WIDTH, VIEWPORT_HEIGHT,
        engine.player.x, engine.player.y,
    )
    render_map(console, engine.game_map, cam_x, cam_y)
    render_entities(console, engine.game_map, cam_x, cam_y)

    hud_y = VIEWPORT_HEIGHT + 1
    log_y = render_hud(console, engine, hud_y) + 1
    render_message_log(console, engine.message_log, 0, log_y)


def describe_tile(
    game_map: "GameMap",
    catalog: "Catalog",
    x: int,
    y: int,
    dungeon_inspect_text: "dict[str, str] | None" = None,
) -> list[str]:
    """The lines of text look mode shows for a map coordinate. Pure data in,
    strings out - no console/rendering dependency, so it's unit-testable on
    its own."""
    if not game_map.explored[x, y]:
        return ["You haven't explored this area."]

    kind = game_map.kinds[x, y]
    tile_description = game_map.tile_descriptions.get((x, y))
    if tile_description:
        # An author-supplied override (a legend entry's `description`) wins
        # over every kind-specific default below - most specific wins.
        lines = [tile_description]
    elif kind == "door":
        key_id = game_map.locked_doors.get((x, y))
        key_name = catalog.items[key_id].name if key_id in catalog.items else key_id
        lines = [f"Locked door. Requires: {key_name}."]
    elif kind == "dungeon_entrance":
        dungeon_id = game_map.dungeon_entrances.get((x, y))
        custom_text = (dungeon_inspect_text or {}).get(dungeon_id) if dungeon_id else None
        lines = [custom_text or TILE_DESCRIPTIONS.get(kind, f"{kind.capitalize()}.")]
    else:
        lines = [TILE_DESCRIPTIONS.get(kind, f"{kind.capitalize()}.")]

    if not game_map.visible[x, y]:
        return lines

    for entity in game_map.entities:
        if entity.x != x or entity.y != y:
            continue
        line = entity.name
        if entity.description:
            line += f": {entity.description}"
        if entity.fighter is not None:
            line += f" (HP: {entity.fighter.hp}/{entity.fighter.max_hp})"
        lines.append(line)

    return lines


def render_look_hud(
    console: "Console", engine: "Engine", cursor_x: int, cursor_y: int, y: int
) -> int:
    """Mirrors render_hud's contract: prints starting at y, wraps long lines,
    and returns the row just past the last line printed."""
    width = console.width
    player = engine.player
    fighter = player.fighter
    weapon_name = player.equipped_weapon.name if player.equipped_weapon else "none"
    armor_name = player.equipped_armor.name if player.equipped_armor else "none"
    ranged_name = player.equipped_ranged_weapon.name if player.equipped_ranged_weapon else "none"

    y += console.print(0, y, engine.level_name, fg=HUD_FG, width=width)
    y += console.print(0, y, f"HP: {fighter.hp}/{fighter.max_hp}", fg=HUD_FG, width=width)
    y += console.print(
        0,
        y,
        f"ATK: {player.effective_attack}  DEF: {player.effective_defense}",
        fg=HUD_FG,
        width=width,
    )
    y += console.print(
        0,
        y,
        f"Weapon: {weapon_name}  Armor: {armor_name}  Ranged: {ranged_name}",
        fg=HUD_FG,
        width=width,
    )

    for line in describe_tile(
        engine.game_map, engine.catalog, cursor_x, cursor_y, engine.dungeon_inspect_text
    ):
        y += console.print(0, y, line, fg=HUD_FG, width=width)

    y += console.print(
        0, y, "[arrows/numpad] move cursor  [l/esc] exit look", fg=HUD_FG, width=width
    )
    return y


def render_look_frame(console: "Console", engine: "Engine", cursor_x: int, cursor_y: int) -> None:
    """Centers the camera on the cursor rather than the player: look mode's
    cursor can roam anywhere on the map, unlike targeting's range-limited one,
    so it - not the player - is what must stay in view here."""
    console.clear()
    cam_x, cam_y = compute_camera(
        engine.game_map.width, engine.game_map.height, VIEWPORT_WIDTH, VIEWPORT_HEIGHT,
        cursor_x, cursor_y,
    )
    render_map(console, engine.game_map, cam_x, cam_y)
    render_entities(console, engine.game_map, cam_x, cam_y)
    console.rgb[cursor_x - cam_x, cursor_y - cam_y]["bg"] = CURSOR_BG

    hud_y = VIEWPORT_HEIGHT + 1
    log_y = render_look_hud(console, engine, cursor_x, cursor_y, hud_y) + 1
    render_message_log(console, engine.message_log, 0, log_y)


def render_target_hud(
    console: "Console",
    engine: "Engine",
    cursor_x: int,
    cursor_y: int,
    max_range: int,
    y: int,
) -> int:
    """Mirrors render_hud's contract: prints starting at y, wraps long lines,
    and returns the row just past the last line printed."""
    width = console.width
    fighter = engine.player.fighter

    y += console.print(0, y, engine.level_name, fg=HUD_FG, width=width)
    y += console.print(0, y, f"HP: {fighter.hp}/{fighter.max_hp}", fg=HUD_FG, width=width)

    if is_valid_target(engine.game_map, engine.player, cursor_x, cursor_y, max_range):
        target = engine.game_map.blocking_entity_at(cursor_x, cursor_y)
        status = f"Target: {target.name} (HP: {target.fighter.hp}/{target.fighter.max_hp})"
    else:
        status = "No valid target there."
    y += console.print(0, y, status, fg=HUD_FG, width=width)

    y += console.print(
        0, y, "[arrows/numpad] aim  [f] fire  [esc] cancel", fg=HUD_FG, width=width
    )
    return y


def render_target_frame(
    console: "Console", engine: "Engine", cursor_x: int, cursor_y: int, max_range: int
) -> None:
    console.clear()
    cam_x, cam_y = compute_camera(
        engine.game_map.width, engine.game_map.height, VIEWPORT_WIDTH, VIEWPORT_HEIGHT,
        cursor_x, cursor_y,
    )
    render_map(console, engine.game_map, cam_x, cam_y)
    render_entities(console, engine.game_map, cam_x, cam_y)

    valid = is_valid_target(engine.game_map, engine.player, cursor_x, cursor_y, max_range)
    console.rgb[cursor_x - cam_x, cursor_y - cam_y]["bg"] = (
        TARGET_VALID_BG if valid else TARGET_INVALID_BG
    )

    hud_y = VIEWPORT_HEIGHT + 1
    log_y = render_target_hud(console, engine, cursor_x, cursor_y, max_range, hud_y) + 1
    render_message_log(console, engine.message_log, 0, log_y)


def render_quest_log(
    console: "Console",
    quests: "list[Quest]",
    selected: int,
    active_quest_id: str | None,
    description: str,
) -> None:
    """The quest log screen: unlike every other render_* function above, this
    one draws no map - just a list of known quests (already filtered by the
    caller to exclude not-given ones), the selected quest's description, and
    a footer control hint. `quests` and `selected` together identify the
    highlighted row; `active_quest_id` marks which one is currently pinned to
    the HUD. `description` is the selected quest's already-resolved current
    text (see Quest.current_description) - this function never computes it
    itself, same "engine computes, render just displays" split as
    Engine.shop_price/render_shop's `prices`."""
    console.clear()
    width = console.width
    y = 0
    y += console.print(0, y, "Quest Log", fg=HUD_FG, width=width)
    y += 1

    for i, quest in enumerate(quests):
        marker = ">" if i == selected else " "
        tag = " [ACTIVE]" if quest.id == active_quest_id else ""
        y += console.print(0, y, f"{marker} {quest.format_for_hud()}{tag}", fg=HUD_FG, width=width)

    y += 1
    if quests:
        y += console.print(0, y, description, fg=HUD_FG, width=width)

    y = console.height - 1
    console.print(
        0, y, "[up/down] select  [enter] set active  [q/esc] exit", fg=HUD_FG, width=width
    )


def render_shop(
    console: "Console",
    catalog: "Catalog",
    item_ids: "list[str]",
    prices: "dict[str, int]",
    selected: int,
    player_gold: int,
    status: str,
) -> None:
    """The shop screen: mirrors render_quest_log's shape - no map drawn,
    just a list of what's for sale (item_ids, resolved against the catalog
    for name/description; `prices` gives each one's current effective cost -
    already discount-adjusted by Engine.shop_price, so this function never
    computes a price itself), the selected item's description, a status
    line for the last purchase attempt (this screen never renders the
    message log, so this is the only way to show immediate feedback), and a
    footer control hint."""
    console.clear()
    width = console.width
    y = 0
    y += console.print(0, y, "Shop", fg=HUD_FG, width=width)
    y += console.print(0, y, f"Your gold: {player_gold}", fg=HUD_FG, width=width)
    y += 1

    for i, item_id in enumerate(item_ids):
        idef = catalog.items[item_id]
        cost = prices[item_id]
        marker = ">" if i == selected else " "
        afford_tag = "" if player_gold >= cost else " (can't afford)"
        y += console.print(
            0, y, f"{marker} {idef.name} - {cost} gold{afford_tag}", fg=HUD_FG, width=width
        )

    y += 1
    if item_ids:
        y += console.print(0, y, catalog.items[item_ids[selected]].description, fg=HUD_FG, width=width)

    if status:
        y += 1
        y += console.print(0, y, status, fg=HUD_FG, width=width)

    y = console.height - 1
    console.print(
        0, y, "[up/down] select  [enter] buy  [b/esc] exit", fg=HUD_FG, width=width
    )
