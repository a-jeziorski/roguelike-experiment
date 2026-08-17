"""Runtime map representation and the bridge from validated content
(content.loader.ParsedLevel) into engine world-objects (engine.entity.Entity)."""

from __future__ import annotations

import numpy as np
import tcod.map

from content.loader import Catalog, ParsedLevel
from engine.entity import (
    RENDER_PRIORITY_ACTOR,
    RENDER_PRIORITY_ITEM,
    RENDER_PRIORITY_PLAYER,
    Entity,
    Fighter,
    ItemEffect,
)

PLAYER_MAX_HP = 30
PLAYER_ATTACK = 5
PLAYER_DEFENSE = 1

FOV_RADIUS = 8


class GameMap:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.walkable = np.zeros((width, height), dtype=bool, order="F")
        self.transparent = np.zeros((width, height), dtype=bool, order="F")
        # Tile type per cell ("wall" / "floor" / "stairs_down"), used for rendering.
        self.kinds = np.full((width, height), "floor", dtype=object, order="F")
        self.explored = np.zeros((width, height), dtype=bool, order="F")
        self.visible = np.zeros((width, height), dtype=bool, order="F")
        self.stairs_down: tuple[int, int] | None = None
        self.entities: list[Entity] = []

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def is_walkable(self, x: int, y: int) -> bool:
        return self.in_bounds(x, y) and bool(self.walkable[x, y])

    def blocking_entity_at(self, x: int, y: int) -> Entity | None:
        for entity in self.entities:
            if entity.blocks_movement and entity.x == x and entity.y == y:
                return entity
        return None

    def update_fov(self, pov: tuple[int, int]) -> None:
        self.visible = tcod.map.compute_fov(
            self.transparent,
            pov,
            radius=FOV_RADIUS,
            algorithm=tcod.constants.FOV_SYMMETRIC_SHADOWCAST,
        )
        self.explored |= self.visible


def build_game_map(level: ParsedLevel, catalog: Catalog) -> tuple[GameMap, Entity]:
    """Builds a runtime GameMap and spawns entities from a validated level.
    Returns (game_map, player_entity)."""
    game_map = GameMap(level.width, level.height)

    for y, row in enumerate(level.tiles):
        for x, tile in enumerate(row):
            kind = "floor" if tile == "player_start" else tile
            game_map.kinds[x, y] = kind
            game_map.walkable[x, y] = kind != "wall"
            game_map.transparent[x, y] = kind != "wall"
            if kind == "stairs_down":
                game_map.stairs_down = (x, y)

    for spawn in level.entity_spawns:
        edef = spawn.entity
        entity = Entity(
            spawn.x,
            spawn.y,
            edef.glyph,
            edef.color,
            edef.name,
            blocks_movement=True,
            render_priority=RENDER_PRIORITY_ACTOR,
            fighter=Fighter(
                max_hp=edef.hp, hp=edef.hp, attack=edef.attack, defense=edef.defense
            ),
            ai=edef.ai,
        )
        game_map.entities.append(entity)

    for spawn in level.item_spawns:
        idef = spawn.item
        entity = Entity(
            spawn.x,
            spawn.y,
            idef.glyph,
            idef.color,
            idef.name,
            blocks_movement=False,
            render_priority=RENDER_PRIORITY_ITEM,
            item=ItemEffect(heal_amount=idef.heal_amount, attack_bonus=idef.attack_bonus),
        )
        game_map.entities.append(entity)

    px, py = level.player_start
    player = Entity(
        px,
        py,
        "@",
        (255, 255, 255),
        "Player",
        blocks_movement=True,
        render_priority=RENDER_PRIORITY_PLAYER,
        fighter=Fighter(
            max_hp=PLAYER_MAX_HP, hp=PLAYER_MAX_HP, attack=PLAYER_ATTACK, defense=PLAYER_DEFENSE
        ),
    )
    game_map.entities.append(player)

    return game_map, player
