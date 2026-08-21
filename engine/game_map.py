"""Runtime map representation and the bridge from validated content
(content.loader.ParsedLevel) into engine world-objects (engine.entity.Entity)."""

from __future__ import annotations

import numpy as np
import tcod.map

from content.loader import Catalog, ItemDef, ParsedLevel
from content.schema import TILE_PASSABILITY
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
        # Coordinate -> destination level id, or None for a terminal stairway
        # (leaves the dungeon, returns to the overworld).
        self.stairs: dict[tuple[int, int], str | None] = {}
        # Coordinate -> required key item id, for tiles not yet unlocked.
        self.locked_doors: dict[tuple[int, int], str] = {}
        # Overworld-only: coordinate -> dungeon registry id to enter.
        self.dungeon_entrances: dict[tuple[int, int], str] = {}
        # Coordinate -> author-supplied look-mode text overriding the tile
        # kind's generic default (e.g. "Stairs leading up.") - optional, only
        # present where a legend entry set `description`.
        self.tile_descriptions: dict[tuple[int, int], str] = {}
        self.entities: list[Entity] = []
        # Set by engine/combat.py the moment the player attacks any
        # PEACEFUL_AI_TYPES entity on this map - read by Engine._perform_ai's
        # AI_TOWN_GUARD branch, which turns every town_guard on this map
        # hostile once it's True. Lives on GameMap (not Engine) so it
        # persists across leaving and re-entering this same map, the same
        # way explored/locked_doors already do, and resets for free on
        # Engine.restart() (which always builds a fresh GameMap).
        self.player_attacked_peaceful_npc = False

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def is_walkable(self, x: int, y: int) -> bool:
        return self.in_bounds(x, y) and bool(self.walkable[x, y])

    def unlock_door(self, x: int, y: int) -> None:
        self.walkable[x, y] = True
        self.transparent[x, y] = True
        self.kinds[x, y] = "floor"
        self.locked_doors.pop((x, y), None)

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


def item_entity_from_def(idef: ItemDef, x: int = 0, y: int = 0) -> Entity:
    """Builds a standalone item Entity from a catalog ItemDef - the piece of
    build_game_map's item-spawn loop that's reusable outside a map spawn
    (e.g. a quest reward going straight into player.inventory, which never
    needs real map coordinates - x/y default to 0, 0 and are never read for
    an inventory-held item)."""
    return Entity(
        x,
        y,
        idef.glyph,
        idef.color,
        idef.name,
        blocks_movement=False,
        render_priority=RENDER_PRIORITY_ITEM,
        item=ItemEffect(
            heal_amount=idef.heal_amount,
            gold_amount=idef.gold_amount,
            attack_bonus=idef.attack_bonus,
            defense_bonus=idef.defense_bonus,
            ranged_attack_bonus=idef.ranged_attack_bonus,
            range=idef.range,
            key_id=idef.id if idef.is_key else None,
            is_ammo=idef.is_ammo,
            quantity=idef.quantity,
        ),
        description=idef.description,
    )


def build_game_map(
    level: ParsedLevel, catalog: Catalog, player: Entity | None = None
) -> tuple[GameMap, Entity]:
    """Builds a runtime GameMap and spawns entities from a validated level.

    `player`, when given, is an existing player Entity to reuse (repositioned to
    this level's player_start, hp/inventory/attack carried over) instead of
    creating a fresh one - used when descending from one level to the next.
    Returns (game_map, player_entity).
    """
    game_map = GameMap(level.width, level.height)

    for y, row in enumerate(level.tiles):
        for x, tile in enumerate(row):
            kind = "floor" if tile == "player_start" else tile
            game_map.kinds[x, y] = kind
            walkable, transparent = TILE_PASSABILITY.get(kind, (True, True))
            game_map.walkable[x, y] = walkable
            game_map.transparent[x, y] = transparent

    for stairs_spawn in level.stairs:
        game_map.stairs[(stairs_spawn.x, stairs_spawn.y)] = stairs_spawn.next_level

    for door_spawn in level.doors:
        game_map.locked_doors[(door_spawn.x, door_spawn.y)] = door_spawn.requires_key

    for entrance_spawn in level.dungeon_entrances:
        game_map.dungeon_entrances[(entrance_spawn.x, entrance_spawn.y)] = entrance_spawn.dungeon_id

    for desc_spawn in level.tile_descriptions:
        game_map.tile_descriptions[(desc_spawn.x, desc_spawn.y)] = desc_spawn.text

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
            alert_radius=edef.alert_radius,
            flee_hp_pct=edef.flee_hp_pct,
            ranged_range=edef.ranged_range,
            description=edef.description,
            dialogue=spawn.dialogue or edef.dialogue,
            entity_id=edef.id,
        )
        game_map.entities.append(entity)

    for spawn in level.item_spawns:
        entity = item_entity_from_def(spawn.item, spawn.x, spawn.y)
        game_map.entities.append(entity)

    px, py = level.player_start
    if player is None:
        player = Entity(
            px,
            py,
            "@",
            (255, 255, 255),
            "Player",
            blocks_movement=True,
            render_priority=RENDER_PRIORITY_PLAYER,
            fighter=Fighter(
                max_hp=PLAYER_MAX_HP,
                hp=PLAYER_MAX_HP,
                attack=PLAYER_ATTACK,
                defense=PLAYER_DEFENSE,
            ),
        )
    else:
        player.x, player.y = px, py
    game_map.entities.append(player)

    return game_map, player
