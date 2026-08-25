"""Runtime map representation and the bridge from validated content
(content.loader.ParsedLevel) into engine world-objects (engine.entity.Entity)."""

from __future__ import annotations

import numpy as np
import tcod.map

from content.loader import PLAYER_ENTITY_ID, Catalog, ItemDef, ParsedLevel
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
        # Coordinate -> description text for a legend entry that opted into
        # auto-announcing (LegendEntry.announce) - a filtered view of
        # tile_descriptions above, populated in lockstep by build_game_map.
        self.auto_announce_tiles: dict[tuple[int, int], str] = {}
        # Coordinates whose auto_announce_tiles text has already been logged
        # this map's lifetime - persisted across save/reload (see
        # engine/save.py's SavedLevelState.announced_tiles) so a reload never
        # re-announces a tile the player already saw announced.
        self.announced_tiles: set[tuple[int, int]] = set()
        self.entities: list[Entity] = []
        # Set by engine/combat.py the moment the player attacks any
        # PEACEFUL_AI_TYPES entity on this map - read by Engine._perform_ai's
        # AI_TOWN_GUARD branch, which turns every town_guard on this map
        # hostile once it's True. Lives on GameMap (not Engine) so it
        # persists across leaving and re-entering this same map, the same
        # way explored/locked_doors already do, and resets for free on
        # Engine.restart() (which always builds a fresh GameMap).
        self.player_attacked_peaceful_npc = False
        # True makes every edge of this map a valid way to leave (see
        # LevelDef.open_boundary, engine/actions.py's MovementAction,
        # Engine.on_player_reach_map_edge). Set by build_game_map from the
        # level, same as stairs/locked_doors above rather than a
        # constructor param.
        self.open_boundary = False
        self.open_boundary_message = ""
        # spawn-list-index -> the Entity build_game_map produced for it, for
        # ParsedLevel.entity_spawns/item_spawns respectively - populated by
        # build_game_map as it spawns each one. Purely additive bookkeeping
        # read only by engine/save.py's save/load reconciliation (matching a
        # possibly-moved/possibly-damaged live entity back to the specific
        # spawn it originated from, since that's the only way to preserve a
        # level-authored per-spawn dialogue override on reload without
        # reconstructing entities from scratch) - nothing else in the engine
        # reads these two dicts.
        self.entity_spawn_index: dict[int, Entity] = {}
        self.item_spawn_index: dict[int, Entity] = {}

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

    def newly_seen_tile_announcements(self) -> list[str]:
        """Text for every auto_announce_tiles entry that just became visible
        and hasn't been announced before - call once, right after
        update_fov, from every site that calls it (see
        Engine._log_newly_seen_tile_announcements). Mutates announced_tiles
        as a side effect, so calling this twice in a row without an
        intervening update_fov yields an empty list the second time.
        explored |= visible above means a coordinate only ever becomes
        newly explored in the same update_fov call where it's also
        currently visible, so "newly explored" and "currently visible" are
        simultaneous by construction - checking visible here is exactly
        "did this tile just enter FOV for the first time," not merely
        "is it visible right now" in some more general sense."""
        texts = []
        for coord, text in self.auto_announce_tiles.items():
            if coord in self.announced_tiles:
                continue
            if self.visible[coord]:
                self.announced_tiles.add(coord)
                texts.append(text)
        return texts


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
            is_teleport=idef.is_teleport,
            quantity=idef.quantity,
        ),
        description=idef.description,
        # The catalog id this item was spawned from - mirrors how creature
        # spawns already carry entity_id, and is what lets a fetch quest
        # (QuestLog.check_delivery) match a carried item by stable id.
        entity_id=idef.id,
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
    game_map.open_boundary = level.open_boundary
    game_map.open_boundary_message = level.open_boundary_message

    for y, row in enumerate(level.tiles):
        for x, tile in enumerate(row):
            kind = level.player_start_tile if tile == "player_start" else tile
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
        if desc_spawn.announce:
            game_map.auto_announce_tiles[(desc_spawn.x, desc_spawn.y)] = desc_spawn.text

    for index, spawn in enumerate(level.entity_spawns):
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
            stationary=edef.stationary,
            description=edef.description,
            dialogue=spawn.dialogue or edef.dialogue,
            # No "or edef.flag_dialogue" fallback (unlike dialogue above) -
            # deliberately spawn-only, since a world-flag reaction is about
            # this specific placement, not a generic trait of the monster/
            # NPC type (EntityDef has no flag_dialogue field at all).
            flag_dialogue=spawn.flag_dialogue,
            shop_inventory=edef.shop_inventory,
            entity_id=edef.id,
        )
        game_map.entities.append(entity)
        game_map.entity_spawn_index[index] = entity

    for index, spawn in enumerate(level.item_spawns):
        entity = item_entity_from_def(spawn.item, spawn.x, spawn.y)
        game_map.entities.append(entity)
        game_map.item_spawn_index[index] = entity

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
            entity_id=PLAYER_ENTITY_ID,
        )
    else:
        player.x, player.y = px, py
    game_map.entities.append(player)

    return game_map, player


def apply_dungeon_destruction(
    game_map: GameMap, dungeon_id: str, ruined_tile: str, ruined_description: str
) -> None:
    """Razes dungeon_id's overworld entrance on game_map: pops it from
    dungeon_entrances (sealing it - engine/actions.py's MovementAction only
    ever finds pending_dungeon_entry through that dict, so a missing entry
    is just an ordinary move onto whatever kinds[x,y] says next), swaps the
    tile to ruined_tile (updating walkable/transparent in lockstep, same
    pattern as GameMap.unlock_door), and sets tile_descriptions to
    ruined_description so look mode shows the ruins text.

    Called from both Engine.destroy_dungeon (the moment the deadline that
    triggers it is crossed) and engine/save.py's restore_save (reapplying
    every already-destroyed dungeon to a freshly rebuilt overworld GameMap,
    since build_game_map always rebuilds from the static, unmodified level
    file). Knows nothing about QuestLog - a pure GameMap mutation, which is
    what lets both callers share it. Silently no-ops if dungeon_id isn't
    found in dungeon_entrances (already razed, or never had an entrance on
    this map) - restore_save calls this unconditionally for every entry in
    QuestLog.destroyed_dungeon_ids, so it must be safe to call more than
    once."""
    coord = next((c for c, d_id in game_map.dungeon_entrances.items() if d_id == dungeon_id), None)
    if coord is None:
        return
    game_map.dungeon_entrances.pop(coord)
    x, y = coord
    game_map.kinds[x, y] = ruined_tile
    walkable, transparent = TILE_PASSABILITY.get(ruined_tile, (True, True))
    game_map.walkable[x, y] = walkable
    game_map.transparent[x, y] = transparent
    game_map.tile_descriptions[coord] = ruined_description
