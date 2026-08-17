"""Draws the game map, entities, HUD, and message log onto a tcod Console."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tcod.console import Console

    from engine.engine import Engine, MessageLog
    from engine.game_map import GameMap

TILE_VISUALS = {
    "wall": {"glyph": "#", "dark": (35, 35, 55), "light": (100, 100, 130)},
    "floor": {"glyph": ".", "dark": (25, 25, 35), "light": (75, 75, 95)},
    "stairs_down": {"glyph": ">", "dark": (65, 45, 15), "light": (210, 160, 60)},
}

HUD_FG = (220, 220, 220)
LOG_FG = (190, 190, 190)
DEAD_FG = (220, 50, 50)
WIN_FG = (60, 220, 90)

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
    console.print(0, y, f"{engine.level_name}", fg=HUD_FG)
    console.print(0, y + 1, f"HP: {fighter.hp}/{fighter.max_hp}", fg=HUD_FG)
    console.print(0, y + 2, f"ATK: {fighter.attack}  DEF: {fighter.defense}", fg=HUD_FG)
    console.print(
        0,
        y + 3,
        f"Potions: {len(engine.player.inventory)}  "
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
