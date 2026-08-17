"""Draws the game map, entities, HUD, and message log onto a tcod Console."""

from __future__ import annotations

from typing import TYPE_CHECKING

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


def render_hud(console: "Console", engine: "Engine", y: int) -> None:
    fighter = engine.player.fighter
    inventory = engine.player.inventory
    potions = sum(1 for it in inventory if it.item.heal_amount)
    keys = sum(1 for it in inventory if it.item.key_id)

    console.print(0, y, f"{engine.level_name}", fg=HUD_FG)
    console.print(0, y + 1, f"HP: {fighter.hp}/{fighter.max_hp}", fg=HUD_FG)
    console.print(0, y + 2, f"ATK: {fighter.attack}  DEF: {fighter.defense}", fg=HUD_FG)
    console.print(
        0,
        y + 3,
        f"Potions: {potions}  Keys: {keys}  "
        "[arrows] move  [g] pick up  [u] use potion  [esc] quit",
        fg=HUD_FG,
    )

    if engine.game_state == "dead":
        console.print(0, y + 4, "You have died. [r] play again  [esc] quit", fg=DEAD_FG)
    elif engine.game_state == "won":
        console.print(0, y + 4, "You escaped the dungeon! [r] play again  [esc] quit", fg=WIN_FG)


def render_message_log(console: "Console", message_log: "MessageLog", x: int, y: int) -> None:
    recent = message_log.messages[-MESSAGE_LOG_HEIGHT:]
    for i, message in enumerate(recent):
        console.print(x, y + i, message, fg=LOG_FG)


def render_all(console: "Console", engine: "Engine") -> None:
    console.clear()
    render_map(console, engine.game_map)
    render_entities(console, engine.game_map)

    hud_y = engine.game_map.height + 1
    render_hud(console, engine, hud_y)
    render_message_log(console, engine.message_log, 0, hud_y + 5)


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
) -> None:
    fighter = engine.player.fighter
    console.print(0, y, f"{engine.level_name}", fg=HUD_FG)
    console.print(0, y + 1, f"HP: {fighter.hp}/{fighter.max_hp}", fg=HUD_FG)
    console.print(0, y + 2, f"ATK: {fighter.attack}  DEF: {fighter.defense}", fg=HUD_FG)

    description = " | ".join(describe_tile(engine.game_map, engine.catalog, cursor_x, cursor_y))
    console.print(0, y + 3, description, fg=HUD_FG)
    console.print(0, y + 4, "[arrows] move cursor  [l/esc] exit look", fg=HUD_FG)


def render_look_frame(console: "Console", engine: "Engine", cursor_x: int, cursor_y: int) -> None:
    console.clear()
    render_map(console, engine.game_map)
    render_entities(console, engine.game_map)
    console.rgb[cursor_x, cursor_y]["bg"] = CURSOR_BG

    hud_y = engine.game_map.height + 1
    render_look_hud(console, engine, cursor_x, cursor_y, hud_y)
    render_message_log(console, engine.message_log, 0, hud_y + 5)
