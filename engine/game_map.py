"""Runtime map representation and the bridge from validated content
(content.loader.ParsedLevel) into engine world-objects (engine.entity.Entity)."""

from __future__ import annotations

import math

import numpy as np
import tcod.map

from content.loader import PLAYER_ENTITY_ID, Catalog, ItemDef, ParsedLevel
from content.schema import TILE_PASSABILITY
from engine.clock import GameClock
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
# Shrunk FOV for a level with LevelDef.dark: true (see build_game_map,
# GameMap.fov_radius) - low enough that something can be well within
# hostile_basic's always-chase-once-seen range before the player ever
# sees it coming, without being so low the map reads as unplayable.
DARK_FOV_RADIUS = 3

# How long a town's guards stay hostile after the player attacks a peaceful
# NPC there, absent a murder (see GameMap.mark_peaceful_npc_murdered) - see
# GameMap.trigger_guard_hostility/guards_hostile.
HOSTILITY_COOLDOWN_DAYS = 7

# LegendEntry.elite's scaling (see _apply_elite_scaling below) - a stronger,
# more rewarding version of an ordinary catalog monster for one specific
# placement, without a second near-duplicate EntityDef. hp/attack/xp_reward
# scale multiplicatively, rounded up (math.ceil, not round - same
# "must always be strictly stronger, never accidentally identical at a low
# stat value" reasoning as engine/combat.py's crit multiplier). Defense is
# a flat bonus instead of a multiplier: many monsters have single-digit or
# zero base defense, where multiplying would do nothing at all.
ELITE_STAT_MULTIPLIER = 2.0
ELITE_DEFENSE_BONUS = 1
ELITE_XP_MULTIPLIER = 2.0
ELITE_NAME_PREFIX = "Elite "


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
        # Subset of auto_announce_tiles' coordinates whose legend entry's
        # tile kind is specifically "landmark" - lets
        # newly_seen_tile_announcements report which newly-announced tiles
        # should also award discovery XP (see Engine._award_xp), without
        # rewarding every announce:true tile (a flavorful gate/stairs/item
        # keeps its message but grants no XP).
        self.landmark_announce_tiles: set[tuple[int, int]] = set()
        # Coordinates whose auto_announce_tiles text has already been logged
        # this map's lifetime - persisted across save/reload (see
        # engine/save.py's SavedLevelState.announced_tiles) so a reload never
        # re-announces a tile the player already saw announced.
        self.announced_tiles: set[tuple[int, int]] = set()
        self.entities: list[Entity] = []
        # Set by GameMap.trigger_guard_hostility (called from
        # engine/combat.py the moment the player attacks any
        # PEACEFUL_AI_TYPES entity on this map) - True for the rest of this
        # map's lifetime once tripped, even after the cooldown below
        # expires; it's the "has this map ever been provoked at all" gate,
        # not "are guards hostile right now" (see guards_hostile for that).
        # Lives on GameMap (not Engine) so it persists across leaving and
        # re-entering this same map, the same way explored/locked_doors
        # already do, and resets for free on Engine.restart() (which always
        # builds a fresh GameMap).
        self.player_attacked_peaceful_npc = False
        # (year, day, hour) - see engine/clock.py's GameClock - at which the
        # cooldown started by trigger_guard_hostility naturally lapses. None
        # before the first provocation. Each new provocation overwrites this
        # with a fresh HOSTILITY_COOLDOWN_DAYS-from-now value rather than
        # extending the existing one - "most recent provocation resets the
        # countdown," same convention as QuestLog.arm_encounter for a
        # re-armed encounter timer. Meaningless once
        # player_murdered_peaceful_npc is set - see guards_hostile.
        self.hostility_expires_at: tuple[int, int, int] | None = None
        # Set by GameMap.mark_peaceful_npc_murdered (called from
        # Engine.on_entity_death the moment a PEACEFUL_AI_TYPES entity dies
        # on this map) - permanently overrides hostility_expires_at once
        # True, per the design: intimidation is forgivable after a cooldown,
        # killing a villager or guard is not. Never reset except by
        # Engine.restart() rebuilding this GameMap fresh.
        self.player_murdered_peaceful_npc = False
        # True makes every edge of this map a valid way to leave (see
        # LevelDef.open_boundary, engine/actions.py's MovementAction,
        # Engine.on_player_reach_map_edge). Set by build_game_map from the
        # level, same as stairs/locked_doors above rather than a
        # constructor param.
        self.open_boundary = False
        self.open_boundary_message = ""
        # FOV radius used by update_fov below - shrunk to DARK_FOV_RADIUS by
        # build_game_map for a level with LevelDef.dark: true, otherwise
        # left at the normal FOV_RADIUS. Same "set by build_game_map from
        # the level, not a constructor param" shape as open_boundary above.
        self.fov_radius = FOV_RADIUS
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

    def trigger_guard_hostility(self, clock: GameClock) -> None:
        """Called from engine/combat.py the instant the player attacks any
        PEACEFUL_AI_TYPES entity on this map. Arms (or re-arms) the
        HOSTILITY_COOLDOWN_DAYS cooldown from `clock`'s current moment -
        see hostility_expires_at's own comment for why a repeat provocation
        overwrites rather than extends it."""
        self.player_attacked_peaceful_npc = True
        self.hostility_expires_at = clock.plus_hours(HOSTILITY_COOLDOWN_DAYS * 24)

    def mark_peaceful_npc_murdered(self) -> None:
        """Called from Engine.on_entity_death the instant a PEACEFUL_AI_TYPES
        entity actually dies on this map - makes guards_hostile permanent,
        see player_murdered_peaceful_npc's own comment."""
        self.player_murdered_peaceful_npc = True

    def guards_hostile(self, clock: GameClock) -> bool:
        """Whether town_guard AI on this map should currently treat the
        player as a hostile combatant - read by Engine._perform_ai's
        AI_TOWN_GUARD branch and Engine._is_currently_peaceful. False until
        this map's ever been provoked at all; once provoked, True forever
        if player_murdered_peaceful_npc is set, otherwise True only until
        hostility_expires_at passes (`clock`'s current (year, day, hour) -
        see engine/clock.py's GameClock - compared the same "< due, not yet;
        >= due, fired" way main.py's _due_encounter checks
        QuestLog.armed_encounters)."""
        if not self.player_attacked_peaceful_npc:
            return False
        if self.player_murdered_peaceful_npc:
            return True
        return self.hostility_expires_at is not None and (
            (clock.year, clock.day, clock.hour) < self.hostility_expires_at
        )

    def blocking_entity_at(self, x: int, y: int) -> Entity | None:
        for entity in self.entities:
            if entity.blocks_movement and entity.x == x and entity.y == y:
                return entity
        return None

    def update_fov(self, pov: tuple[int, int]) -> None:
        self.visible = tcod.map.compute_fov(
            self.transparent,
            pov,
            radius=self.fov_radius,
            algorithm=tcod.constants.FOV_SYMMETRIC_SHADOWCAST,
        )
        self.explored |= self.visible

    def newly_seen_tile_announcements(self) -> list[tuple[str, bool]]:
        """(text, is_landmark) for every auto_announce_tiles entry that just
        became visible and hasn't been announced before - call once, right
        after update_fov, from every site that calls it (see
        Engine._log_newly_seen_tile_announcements, which logs text always
        and awards discovery XP only when is_landmark is True). Mutates
        announced_tiles as a side effect, so calling this twice in a row
        without an intervening update_fov yields an empty list the second
        time. explored |= visible above means a coordinate only ever
        becomes newly explored in the same update_fov call where it's also
        currently visible, so "newly explored" and "currently visible" are
        simultaneous by construction - checking visible here is exactly
        "did this tile just enter FOV for the first time," not merely
        "is it visible right now" in some more general sense."""
        results = []
        for coord, text in self.auto_announce_tiles.items():
            if coord in self.announced_tiles:
                continue
            if self.visible[coord]:
                self.announced_tiles.add(coord)
                results.append((text, coord in self.landmark_announce_tiles))
        return results


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


def _apply_elite_scaling(entity: Entity) -> None:
    """Mutates an already-built monster Entity in place into its elite
    version - called right after construction, in build_game_map's
    entity-spawn loop, for any spawn whose LegendEntry set elite: true. A
    drop already configured on the base entity (drop_item_id set) becomes
    guaranteed; an entity with no drop at all still gets none - this
    amplifies the existing drop system (see content_design_process.md
    §0v/§0w), it doesn't invent a separate elite-only loot table."""
    entity.name = ELITE_NAME_PREFIX + entity.name
    entity.color = tuple(min(255, int(c * 1.4) + 20) for c in entity.color)
    entity.fighter.max_hp = math.ceil(entity.fighter.max_hp * ELITE_STAT_MULTIPLIER)
    entity.fighter.hp = entity.fighter.max_hp
    entity.fighter.attack = math.ceil(entity.fighter.attack * ELITE_STAT_MULTIPLIER)
    entity.fighter.defense += ELITE_DEFENSE_BONUS
    entity.xp_reward = math.ceil(entity.xp_reward * ELITE_XP_MULTIPLIER)
    if entity.drop_item_id is not None:
        entity.drop_chance = 1.0


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
    game_map.fov_radius = DARK_FOV_RADIUS if level.dark else FOV_RADIUS

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
            if desc_spawn.is_landmark:
                game_map.landmark_announce_tiles.add((desc_spawn.x, desc_spawn.y))

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
            inflicts_effect=edef.inflicts_effect,
            inflicts_potency=edef.inflicts_potency,
            inflicts_duration=edef.inflicts_duration,
            enrage_hp_pct=edef.enrage_hp_pct,
            enrage_attack_bonus=edef.enrage_attack_bonus,
            pack_radius=edef.pack_radius,
            pack_attack_bonus=edef.pack_attack_bonus,
            regen_amount=edef.regen_amount,
            drop_item_id=edef.drop_item_id,
            drop_chance=edef.drop_chance,
            stationary=edef.stationary,
            description=edef.description,
            dialogue=spawn.dialogue or edef.dialogue,
            # No "or edef.flag_dialogue" fallback (unlike dialogue above) -
            # deliberately spawn-only, since a world-flag reaction is about
            # this specific placement, not a generic trait of the monster/
            # NPC type (EntityDef has no flag_dialogue field at all).
            flag_dialogue=spawn.flag_dialogue,
            shop_inventory=edef.shop_inventory,
            xp_reward=edef.xp_reward,
            trainer_perks=edef.trainer_perks,
            entity_id=edef.id,
        )
        if spawn.elite:
            _apply_elite_scaling(entity)
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
    game_map: GameMap, dungeon_id: str, ruined_tile: str, ruined_description: str,
    ruined_starting_level: str | None = None,
) -> None:
    """Razes dungeon_id's overworld entrance on game_map: swaps the tile to
    ruined_tile (updating walkable/transparent in lockstep, same pattern as
    GameMap.unlock_door) and sets tile_descriptions to ruined_description so
    look mode shows the ruins text. If ruined_starting_level is None (most
    dungeons), also pops the entrance from dungeon_entrances - sealing it,
    since engine/actions.py's MovementAction only ever finds
    pending_dungeon_entry through that dict, so a missing entry is just an
    ordinary move onto whatever kinds[x,y] says next. If
    ruined_starting_level is set, the entrance is deliberately left in
    dungeon_entrances - it stays walkable, just now leading to a real
    "after" ruins interior instead of the dungeon's normal starting level
    (see main.py's resolve_transition, which picks that level once
    dungeon_id is in QuestLog.destroyed_dungeon_ids).

    Called from both Engine.destroy_dungeon (the moment the deadline that
    triggers it is crossed) and engine/save.py's restore_save (reapplying
    every already-destroyed dungeon to a freshly rebuilt overworld GameMap,
    since build_game_map always rebuilds from the static, unmodified level
    file). Knows nothing about QuestLog - a pure GameMap mutation, which is
    what lets both callers share it. Silently no-ops if dungeon_id isn't
    found in dungeon_entrances (already razed-and-sealed, or never had an
    entrance on this map) - restore_save calls this unconditionally for
    every entry in QuestLog.destroyed_dungeon_ids, so it must be safe to
    call more than once; when ruined_starting_level is set, the entrance is
    never popped, so a repeat call just re-applies the same tile swap
    idempotently rather than becoming a no-op on the second call."""
    coord = next((c for c, d_id in game_map.dungeon_entrances.items() if d_id == dungeon_id), None)
    if coord is None:
        return
    if ruined_starting_level is None:
        game_map.dungeon_entrances.pop(coord)
    x, y = coord
    game_map.kinds[x, y] = ruined_tile
    walkable, transparent = TILE_PASSABILITY.get(ruined_tile, (True, True))
    game_map.walkable[x, y] = walkable
    game_map.transparent[x, y] = transparent
    game_map.tile_descriptions[coord] = ruined_description
