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
more than one line."""

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

TILE_VISUALS = {
    "wall": {"glyph": "#", "dark": (35, 35, 55), "light": (100, 100, 130)},
    "floor": {"glyph": ".", "dark": (25, 25, 35), "light": (75, 75, 95)},
    "stairs_down": {"glyph": ">", "dark": (65, 45, 15), "light": (210, 160, 60)},
    "door": {"glyph": "+", "dark": (70, 45, 15), "light": (170, 110, 40)},
}

TILE_DESCRIPTIONS = {
    "wall": "Wall.",
    "floor": "Bare floor.",
    "stairs_down": "Stairs leading down.",
}

HUD_FG = (220, 220, 220)
LOG_FG = (190, 190, 190)
DEAD_FG = (220, 50, 50)
WIN_FG = (60, 220, 90)
CURSOR_BG = (90, 90, 20)
TARGET_VALID_BG = (40, 120, 40)
TARGET_INVALID_BG = (110, 40, 40)
PROJECTILE_FG = (255, 230, 120)
IMPACT_BG = (200, 60, 30)

MESSAGE_LOG_HEIGHT = 5


def render_map(console: "Console", game_map: "GameMap") -> None:
    for x in range(game_map.width):
        for y in range(game_map.height):
            visual = TILE_VISUALS[game_map.kinds[x, y]]
            if game_map.visible[x, y]:
                console.print(x, y, visual["glyph"], fg=visual["light"])
            elif game_map.explored[x, y]:
                console.print(x, y, visual["glyph"], fg=visual["dark"])


def render_entities(console: "Console", game_map: "GameMap") -> None:
    for entity in sorted(game_map.entities, key=lambda e: e.render_priority):
        if game_map.visible[entity.x, entity.y]:
            console.print(entity.x, entity.y, entity.glyph, fg=entity.color)


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


def render_projectile(console: "Console", x: int, y: int, glyph: str) -> None:
    console.print(x, y, glyph, fg=PROJECTILE_FG)


def flash_impact(console: "Console", x: int, y: int) -> None:
    console.rgb[x, y]["bg"] = IMPACT_BG


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
        0, y, f"Potions: {potions}  Keys: {keys}  Ammo: {ammo}", fg=HUD_FG, width=width
    )
    y += console.print(
        0,
        y,
        "[arrows/numpad] move  [g] pick up  [u] use potion  [l] look  [f] fire  [esc] quit",
        fg=HUD_FG,
        width=width,
    )

    if engine.game_state == "dead":
        y += console.print(
            0, y, "You have died. [r] play again  [esc] quit", fg=DEAD_FG, width=width
        )
    elif engine.game_state == "won":
        y += console.print(
            0, y, "You escaped the dungeon! [r] play again  [esc] quit", fg=WIN_FG, width=width
        )

    return y


def render_message_log(console: "Console", message_log: "MessageLog", x: int, y: int) -> None:
    """Fills whatever vertical space remains below y (up to MESSAGE_LOG_HEIGHT
    lines) with the most recent messages, wrapping each to fit and dropping
    older messages that no longer fit rather than clipping any single one."""
    width = max(console.width - x, 1)
    max_lines = min(MESSAGE_LOG_HEIGHT, max(console.height - y, 0))
    if max_lines == 0:
        return

    lines: list[str] = []
    for message in reversed(message_log.messages):
        wrapped = textwrap.wrap(message, width) or [message]
        if len(lines) + len(wrapped) > max_lines:
            break
        lines = wrapped + lines

    for i, line in enumerate(lines):
        console.print(x, y + i, line, fg=LOG_FG, width=width)


def render_all(console: "Console", engine: "Engine") -> None:
    console.clear()
    render_map(console, engine.game_map)
    render_entities(console, engine.game_map)

    hud_y = engine.game_map.height + 1
    log_y = render_hud(console, engine, hud_y) + 1
    render_message_log(console, engine.message_log, 0, log_y)


def describe_tile(game_map: "GameMap", catalog: "Catalog", x: int, y: int) -> list[str]:
    """The lines of text look mode shows for a map coordinate. Pure data in,
    strings out - no console/rendering dependency, so it's unit-testable on
    its own."""
    if not game_map.explored[x, y]:
        return ["You haven't explored this area."]

    kind = game_map.kinds[x, y]
    if kind == "door":
        key_id = game_map.locked_doors.get((x, y))
        key_name = catalog.items[key_id].name if key_id in catalog.items else key_id
        lines = [f"Locked door. Requires: {key_name}."]
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

    for line in describe_tile(engine.game_map, engine.catalog, cursor_x, cursor_y):
        y += console.print(0, y, line, fg=HUD_FG, width=width)

    y += console.print(
        0, y, "[arrows/numpad] move cursor  [l/esc] exit look", fg=HUD_FG, width=width
    )
    return y


def render_look_frame(console: "Console", engine: "Engine", cursor_x: int, cursor_y: int) -> None:
    console.clear()
    render_map(console, engine.game_map)
    render_entities(console, engine.game_map)
    console.rgb[cursor_x, cursor_y]["bg"] = CURSOR_BG

    hud_y = engine.game_map.height + 1
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
    render_map(console, engine.game_map)
    render_entities(console, engine.game_map)

    valid = is_valid_target(engine.game_map, engine.player, cursor_x, cursor_y, max_range)
    console.rgb[cursor_x, cursor_y]["bg"] = TARGET_VALID_BG if valid else TARGET_INVALID_BG

    hud_y = engine.game_map.height + 1
    log_y = render_target_hud(console, engine, cursor_x, cursor_y, max_range, hud_y) + 1
    render_message_log(console, engine.message_log, 0, log_y)
