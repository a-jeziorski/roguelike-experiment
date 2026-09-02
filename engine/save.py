"""Save/load: captures a running game's full state (every visited dungeon's
every visited level, not just the current one - matching what already
persists in memory for a single sitting) into a pydantic model, serialized
to JSON rather than pickle. Deliberate: this project's whole content
pipeline already goes through pydantic models for every other structured-
data need, JSON stays human-inspectable (matching that ethos), and it
degrades gracefully across future schema changes (new fields can default)
where pickle - which can also execute arbitrary code on load, an
unnecessary risk even for a single-player local file - does not.

Nothing here is authored content (that's content/schema.py's job
exclusively) - this is runtime state, captured from and restored back into
the same live objects main.py already builds at startup. capture_save/
restore_save mirror main.py's own startup-construction shape on purpose:
restore_save's return type is exactly the (active_key, active_engines,
clock, quest_log) tuple a fresh start builds, so loading a save is a
drop-in replacement for that construction, not a parallel system.

The one real design wrinkle: a level's static geometry/spawns never need
saving (rebuildable any time via build_game_map against the already-loaded
ParsedLevel) - only the *delta* does. Entities and ground items are
tracked by their stable index within ParsedLevel.entity_spawns/item_spawns
(see GameMap.entity_spawn_index/item_spawn_index) rather than reconstructed
from scratch, specifically so a level-authored per-spawn dialogue override
survives a reload even for a spawn that's wandered from its original tile -
reconstructing purely from a catalog entity_id would silently lose it.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from pydantic import BaseModel, Field

from content.loader import PLAYER_ENTITY_ID, Catalog, ParsedLevel
from content.schema import QuestStatus
from engine.clock import GameClock
from engine.engine import Engine
from engine.entity import RENDER_PRIORITY_PLAYER, ActiveEffect, Entity, Fighter, apply_perk_stat_bonus
from engine.game_map import (
    PLAYER_ATTACK,
    PLAYER_DEFENSE,
    PLAYER_MAX_HP,
    GameMap,
    apply_dungeon_destruction,
    build_game_map,
    item_entity_from_def,
)
from engine.quest import QuestLog, create_quest_log

# The one dict key used for the overworld's single level-state entry within
# SavedPlace.levels - the overworld has no multi-level structure (Engine.levels
# is None for it), so this is just an internal bookkeeping constant, not
# related to main.py's OVERWORLD_KEY (a different dict's key entirely).
_OVERWORLD_LEVEL_ID = "overworld"

CURRENT_SAVE_VERSION = 1


class SavedItemSlot(BaseModel):
    entity_id: str
    quantity: int = 1


class SavedActiveEffect(BaseModel):
    """Mirrors engine/entity.py's ActiveEffect exactly - a separate model
    rather than reusing that dataclass directly, same reasoning every
    other Saved* model in this file already follows (runtime state gets
    its own persistence shape, decoupled from the live class)."""

    potency: int
    turns_remaining: int


class SavedGroundItem(BaseModel):
    entity_id: str
    x: int
    y: int
    quantity: int = 1


class SavedLevelState(BaseModel):
    """The mutable delta versus a fresh build_game_map call against this
    level's already-loaded ParsedLevel - see module docstring."""

    explored: list[tuple[int, int]] = Field(default_factory=list)
    # Coordinates whose GameMap.auto_announce_tiles text has already been
    # logged (LegendEntry.announce) - without this, a reload would re-fire
    # an announcement the player already saw the first time that tile came
    # back into FOV, breaking the "once ever" promise.
    announced_tiles: list[tuple[int, int]] = Field(default_factory=list)
    unlocked_doors: list[tuple[int, int]] = Field(default_factory=list)
    player_attacked_peaceful_npc: bool = False
    # (year, day, hour) or None - see GameMap.hostility_expires_at/
    # trigger_guard_hostility. Without persisting this, a save made mid-
    # cooldown would reload with guards_hostile's expiry check comparing
    # against None (permanently un-hostile) instead of the real remaining
    # cooldown.
    hostility_expires_at: tuple[int, int, int] | None = None
    # See GameMap.player_murdered_peaceful_npc/mark_peaceful_npc_murdered -
    # without persisting this, a save made after killing a villager/guard
    # would reload with that map's guards eventually going peaceful again
    # once hostility_expires_at lapses, instead of staying hostile forever.
    player_murdered_peaceful_npc: bool = False
    # ParsedLevel.entity_spawns index -> current (x, y, hp) for a surviving
    # spawn; an index missing here is dead (removed from GameMap.entities).
    alive_entity_spawns: dict[int, tuple[int, int, int]] = Field(default_factory=dict)
    # ParsedLevel.item_spawns indices no longer on the ground (picked up).
    picked_up_item_spawns: list[int] = Field(default_factory=list)
    # Items on this level with no item_spawns origin at all (a quest reward
    # or shop purchase later dropped by equipping over it), or that
    # originated on a *different* level and were carried here - see
    # PickupAction._equip's drop-to-current-position behavior.
    ground_items: list[SavedGroundItem] = Field(default_factory=list)


class SavedPlace(BaseModel):
    """One active_engines entry - a dungeon or the overworld."""

    current_level_id: str | None
    last_position: tuple[int, int]
    overworld_return_position: tuple[int, int] | None = None
    levels: dict[str, SavedLevelState]


class SavedQuestLogState(BaseModel):
    quest_statuses: dict[str, QuestStatus]
    active_quest_id: str | None
    killed_entity_ids: list[str] = Field(default_factory=list)
    intimidated_entity_ids: list[str] = Field(default_factory=list)
    cleared_species_ids: list[str] = Field(default_factory=list)
    entity_kill_counts: dict[str, int] = Field(default_factory=dict)
    visited_dungeon_ids: list[str] = Field(default_factory=list)
    triggered_encounter_ids: list[str] = Field(default_factory=list)
    armed_encounters: dict[str, tuple[int, int, int]] = Field(default_factory=dict)
    destroyed_dungeon_ids: list[str] = Field(default_factory=list)
    world_flags: list[str] = Field(default_factory=list)
    # Every quest's current deadline_day, keyed by quest id - captured for
    # every quest with a deadline, not just ones Engine._tighten_deadline
    # has touched (simpler than tracking "did this change from the
    # authored default," and harmless for an untouched quest since
    # restoring its own unchanged value is a no-op). Needed because
    # deadline_day was a write-once field (set from QuestDef, never
    # mutated) until _tighten_deadline - a save made after a tighten
    # fires would otherwise silently revert to the authored default on
    # reload, since restore_save always rebuilds every Quest fresh via
    # create_quest_log. An old save missing this field just gets {} (the
    # default), which is exactly correct for a save made before this
    # field existed - nothing was ever tightened.
    deadline_days: dict[str, int] = Field(default_factory=dict)


class SavedPlayer(BaseModel):
    x: int
    y: int
    hp: int
    gold: int = 0
    xp: int = 0
    # Perk catalog ids permanently learned (see Engine.learn_perk) - the
    # single source of truth for the player's perk-derived stat bonuses;
    # _build_player re-derives fighter.max_hp/attack/defense/
    # perk_ranged_attack_bonus from this plus catalog.perks at restore
    # time, rather than saving those totals redundantly.
    learned_perk_ids: set[str] = Field(default_factory=set)
    # Remaining cooldown units for a learned active-skill perk (see
    # Entity.skill_cooldowns, Engine.use_skill) - genuine live state, not
    # derivable from learned_perk_ids alone (depends on *when* a skill was
    # last used), so unlike the stat-bonus totals above, this is saved
    # directly rather than re-derived.
    skill_cooldowns: dict[str, int] = Field(default_factory=dict)
    # Turns left in which the player can cross deep_water/sea (see
    # Entity.water_walking_turns_remaining, engine/actions.py's
    # UseItemAction/MovementAction) - genuine live state like
    # skill_cooldowns above, not derivable from anything else.
    water_walking_turns_remaining: int = 0
    inventory: list[SavedItemSlot] = Field(default_factory=list)
    equipped_weapon: SavedItemSlot | None = None
    equipped_armor: SavedItemSlot | None = None
    equipped_ranged_weapon: SavedItemSlot | None = None
    equipped_trinket: SavedItemSlot | None = None
    selected_potion_kind: str = "healing"
    # Hotbar assignments (see Entity.skill_slots/potion_slots,
    # Engine.assign_skill_slot/assign_potion_slot) - defaults match
    # Entity.__init__'s own, so an old save missing these fields round-trips
    # to exactly today's behavior (no skills slotted, healing/teleport in
    # their default order).
    skill_slots: list[str | None] = Field(default_factory=lambda: [None, None, None, None])
    potion_slots: list[str | None] = Field(default_factory=lambda: ["healing", "teleport", None])
    # The player's live status-effect afflictions, if any (see
    # Fighter.active_effects) - monster effect state is never saved,
    # consistent with monster Fighter state beyond (x, y, hp) never being
    # saved today (SavedLevelState's own alive_entity_spawns).
    active_effects: dict[str, SavedActiveEffect] = Field(default_factory=dict)


class SaveGame(BaseModel):
    version: int = CURRENT_SAVE_VERSION
    year: int
    day: int
    hour: int
    active_key: str
    player: SavedPlayer
    quest_log: SavedQuestLogState
    places: dict[str, SavedPlace]


# --- capture ---


def _save_item_slot(entity: Entity | None) -> SavedItemSlot | None:
    if entity is None:
        return None
    return SavedItemSlot(entity_id=entity.entity_id, quantity=entity.item.quantity)


def _capture_level_state(game_map: GameMap, level: ParsedLevel) -> SavedLevelState:
    explored_coords = [(int(x), int(y)) for x, y in np.argwhere(game_map.explored)]

    original_door_coords = {(door.x, door.y) for door in level.doors}
    still_locked = set(game_map.locked_doors.keys())
    unlocked_doors = list(original_door_coords - still_locked)

    alive_entity_spawns: dict[int, tuple[int, int, int]] = {}
    for index, entity in game_map.entity_spawn_index.items():
        if entity in game_map.entities:
            alive_entity_spawns[index] = (entity.x, entity.y, entity.fighter.hp)

    picked_up_item_spawns = [
        index for index, entity in game_map.item_spawn_index.items()
        if entity not in game_map.entities
    ]

    item_spawn_ids = {id(entity) for entity in game_map.item_spawn_index.values()}
    ground_items = [
        SavedGroundItem(entity_id=entity.entity_id, x=entity.x, y=entity.y, quantity=entity.item.quantity)
        for entity in game_map.entities
        if entity.item is not None and id(entity) not in item_spawn_ids
    ]

    return SavedLevelState(
        explored=explored_coords,
        announced_tiles=sorted(game_map.announced_tiles),
        unlocked_doors=unlocked_doors,
        player_attacked_peaceful_npc=game_map.player_attacked_peaceful_npc,
        hostility_expires_at=game_map.hostility_expires_at,
        player_murdered_peaceful_npc=game_map.player_murdered_peaceful_npc,
        alive_entity_spawns=alive_entity_spawns,
        picked_up_item_spawns=picked_up_item_spawns,
        ground_items=ground_items,
    )


def _capture_place(engine: Engine, overworld_level: ParsedLevel) -> SavedPlace:
    if engine.levels is None:
        # The overworld: exactly one map, no multi-level structure at all.
        levels = {_OVERWORLD_LEVEL_ID: _capture_level_state(engine.game_map, overworld_level)}
        current_level_id = None
    else:
        all_level_ids = set(engine.visited_maps)
        if engine.current_level_id is not None:
            all_level_ids.add(engine.current_level_id)
        levels = {
            level_id: _capture_level_state(
                engine.game_map if level_id == engine.current_level_id else engine.visited_maps[level_id],
                engine.levels[level_id],
            )
            for level_id in all_level_ids
        }
        current_level_id = engine.current_level_id

    return SavedPlace(
        current_level_id=current_level_id,
        last_position=tuple(engine.last_position),
        overworld_return_position=(
            tuple(engine.overworld_return_position) if engine.overworld_return_position else None
        ),
        levels=levels,
    )


def capture_save(
    active_key: str,
    active_engines: dict[str, Engine],
    clock: GameClock,
    quest_log: QuestLog,
    overworld_level: ParsedLevel,
) -> SaveGame:
    """Snapshots the entire live game - every visited place's every visited
    level, not just the current one, so a loaded save feels exactly like
    the player never quit (matching what already persists in memory for a
    single sitting via active_engines/Engine.visited_maps)."""
    player = active_engines[active_key].player
    saved_player = SavedPlayer(
        x=player.x, y=player.y, hp=player.fighter.hp, gold=player.gold,
        xp=player.xp, learned_perk_ids=set(player.learned_perk_ids),
        skill_cooldowns=dict(player.skill_cooldowns),
        water_walking_turns_remaining=player.water_walking_turns_remaining,
        inventory=[
            SavedItemSlot(entity_id=item.entity_id, quantity=item.item.quantity)
            for item in player.inventory
        ],
        equipped_weapon=_save_item_slot(player.equipped_weapon),
        equipped_armor=_save_item_slot(player.equipped_armor),
        equipped_ranged_weapon=_save_item_slot(player.equipped_ranged_weapon),
        equipped_trinket=_save_item_slot(player.equipped_trinket),
        selected_potion_kind=player.selected_potion_kind,
        skill_slots=list(player.skill_slots),
        potion_slots=list(player.potion_slots),
        active_effects={
            kind: SavedActiveEffect(potency=effect.potency, turns_remaining=effect.turns_remaining)
            for kind, effect in player.fighter.active_effects.items()
        },
    )

    places = {
        key: _capture_place(place_engine, overworld_level)
        for key, place_engine in active_engines.items()
    }

    quest_log_state = SavedQuestLogState(
        quest_statuses={qid: quest.status for qid, quest in quest_log.quests.items()},
        active_quest_id=quest_log.active_quest_id,
        killed_entity_ids=sorted(quest_log.killed_entity_ids),
        intimidated_entity_ids=sorted(quest_log.intimidated_entity_ids),
        cleared_species_ids=sorted(quest_log.cleared_species_ids),
        entity_kill_counts=dict(quest_log.entity_kill_counts),
        visited_dungeon_ids=sorted(quest_log.visited_dungeon_ids),
        triggered_encounter_ids=sorted(quest_log.triggered_encounter_ids),
        armed_encounters=dict(quest_log.armed_encounters),
        destroyed_dungeon_ids=sorted(quest_log.destroyed_dungeon_ids),
        world_flags=sorted(quest_log.world_flags),
        deadline_days={
            qid: quest.deadline_day for qid, quest in quest_log.quests.items()
            if quest.deadline_day is not None
        },
    )

    return SaveGame(
        year=clock.year, day=clock.day, hour=clock.hour,
        active_key=active_key, player=saved_player,
        quest_log=quest_log_state, places=places,
    )


# --- restore ---


def _build_item_entity(slot: SavedItemSlot, catalog: Catalog) -> Entity:
    item_entity = item_entity_from_def(catalog.items[slot.entity_id])
    item_entity.item.quantity = slot.quantity
    return item_entity


def _build_player(saved: SavedPlayer, catalog: Catalog) -> Entity:
    fighter = Fighter(max_hp=PLAYER_MAX_HP, hp=saved.hp, attack=PLAYER_ATTACK, defense=PLAYER_DEFENSE)
    fighter.active_effects = {
        kind: ActiveEffect(potency=effect.potency, turns_remaining=effect.turns_remaining)
        for kind, effect in saved.active_effects.items()
    }
    # Perk-derived stat totals are *derived* from learned_perk_ids at
    # restore time, never stored redundantly (see SavedPlayer.learned_perk_ids) -
    # deliberately never touches fighter.hp here (see apply_perk_stat_bonus's
    # docstring): saved.hp already reflects every historical max-hp bump.
    for perk_id in saved.learned_perk_ids:
        perk = catalog.perks.get(perk_id)
        if perk is not None:
            apply_perk_stat_bonus(fighter, perk)
    player = Entity(
        saved.x, saved.y, "@", (255, 255, 255), "Player",
        blocks_movement=True, render_priority=RENDER_PRIORITY_PLAYER,
        fighter=fighter,
        entity_id=PLAYER_ENTITY_ID, gold=saved.gold,
        xp=saved.xp, learned_perk_ids=set(saved.learned_perk_ids),
        skill_cooldowns=dict(saved.skill_cooldowns),
    )
    player.inventory = [_build_item_entity(slot, catalog) for slot in saved.inventory]
    player.selected_potion_kind = saved.selected_potion_kind
    player.skill_slots = list(saved.skill_slots)
    player.potion_slots = list(saved.potion_slots)
    player.water_walking_turns_remaining = saved.water_walking_turns_remaining
    player.equipped_weapon = _build_item_entity(saved.equipped_weapon, catalog) if saved.equipped_weapon else None
    player.equipped_armor = _build_item_entity(saved.equipped_armor, catalog) if saved.equipped_armor else None
    player.equipped_ranged_weapon = (
        _build_item_entity(saved.equipped_ranged_weapon, catalog) if saved.equipped_ranged_weapon else None
    )
    player.equipped_trinket = (
        _build_item_entity(saved.equipped_trinket, catalog) if saved.equipped_trinket else None
    )
    return player


def _apply_level_state(game_map: GameMap, state: SavedLevelState, catalog: Catalog) -> None:
    for x, y in state.explored:
        game_map.explored[x, y] = True
    game_map.announced_tiles = set(state.announced_tiles)
    for x, y in state.unlocked_doors:
        game_map.unlock_door(x, y)
    game_map.player_attacked_peaceful_npc = state.player_attacked_peaceful_npc
    game_map.hostility_expires_at = state.hostility_expires_at
    game_map.player_murdered_peaceful_npc = state.player_murdered_peaceful_npc

    for index, entity in list(game_map.entity_spawn_index.items()):
        if index not in state.alive_entity_spawns:
            if entity in game_map.entities:
                game_map.entities.remove(entity)
            continue
        x, y, hp = state.alive_entity_spawns[index]
        entity.x, entity.y = x, y
        entity.fighter.hp = hp

    for index, entity in list(game_map.item_spawn_index.items()):
        if index in state.picked_up_item_spawns and entity in game_map.entities:
            game_map.entities.remove(entity)

    for ground_item in state.ground_items:
        idef = catalog.items[ground_item.entity_id]
        item_entity = item_entity_from_def(idef, ground_item.x, ground_item.y)
        item_entity.item.quantity = ground_item.quantity
        game_map.entities.append(item_entity)


def _build_map_for_load(level: ParsedLevel, catalog: Catalog, state: SavedLevelState) -> GameMap:
    """A fresh build_game_map call - correct static geometry, correct
    per-spawn dialogue/name/glyph for every entity, automatically - with the
    throwaway default player it always creates immediately discarded (the
    one real player is placed separately, only on the current place's live
    map - see restore_save), then patched to match the saved delta."""
    game_map, throwaway_player = build_game_map(level, catalog)
    game_map.entities.remove(throwaway_player)
    _apply_level_state(game_map, state, catalog)
    return game_map


def restore_save(
    save: SaveGame,
    catalog: Catalog,
    dungeon_registry: dict,
    overworld_level: ParsedLevel,
    quest_defs: dict,
    encounter_registry,
    sprite_codepoints,
    overworld_key: str,
) -> tuple[str, dict[str, Engine], GameClock, QuestLog]:
    """The load-time counterpart to capture_save - rebuilds exactly the
    (active_key, active_engines, clock, quest_log) tuple a fresh start
    would build, but reflecting the saved run instead. Deliberately mirrors
    main.py's own startup-construction shape so loading is a drop-in
    replacement for it, not a parallel system."""
    clock = GameClock(year=save.year, day=save.day, hour=save.hour)

    quest_log = create_quest_log(quest_defs)
    for quest_id, status in save.quest_log.quest_statuses.items():
        if quest_id in quest_log.quests:
            quest_log.quests[quest_id].status = status
    quest_log.active_quest_id = save.quest_log.active_quest_id
    quest_log.killed_entity_ids = set(save.quest_log.killed_entity_ids)
    quest_log.intimidated_entity_ids = set(save.quest_log.intimidated_entity_ids)
    quest_log.cleared_species_ids = set(save.quest_log.cleared_species_ids)
    quest_log.entity_kill_counts = dict(save.quest_log.entity_kill_counts)
    quest_log.visited_dungeon_ids = set(save.quest_log.visited_dungeon_ids)
    quest_log.triggered_encounter_ids = set(save.quest_log.triggered_encounter_ids)
    quest_log.armed_encounters = dict(save.quest_log.armed_encounters)
    quest_log.destroyed_dungeon_ids = set(save.quest_log.destroyed_dungeon_ids)
    quest_log.world_flags = set(save.quest_log.world_flags)
    for quest_id, day in save.quest_log.deadline_days.items():
        if quest_id in quest_log.quests:
            quest_log.quests[quest_id].deadline_day = day

    player = _build_player(save.player, catalog)
    dungeon_inspect_text = {d_id: d.inspect_text for d_id, d in dungeon_registry.items()}
    dungeon_ruin_data = {
        d_id: (d.ruined_tile, d.ruined_description, d.ruined_starting_level)
        for d_id, d in dungeon_registry.items() if d.ruined_tile
    }

    active_engines: dict[str, Engine] = {}
    for key, place in save.places.items():
        is_overworld = key == overworld_key
        is_current = key == save.active_key

        if is_overworld:
            level = overworld_level
            levels_dict = None
            starting_level = None
            current_state_key = _OVERWORLD_LEVEL_ID
        else:
            dungeon = dungeon_registry[key]
            levels_dict = dungeon.levels
            starting_level = levels_dict[dungeon.starting_level]
            current_state_key = place.current_level_id or dungeon.starting_level
            level = levels_dict[current_state_key]

        game_map = _build_map_for_load(level, catalog, place.levels[current_state_key])
        # Engine.__init__ unconditionally computes initial FOV around the
        # player Entity's *current* x/y - explicitly set it correctly for
        # THIS place before constructing, regardless of what any earlier
        # loop iteration (dict order isn't guaranteed to put the active
        # place first) may have left it at. For the active place that's
        # save.player.x/y (set once, before this loop, by _build_player);
        # for any other cached place, the shared player Entity's position
        # reflects wherever it currently is, not wherever it was last on
        # THIS map, so passing it through as-is can put the FOV
        # computation out of this game_map's bounds entirely -
        # place.last_position was saved for exactly this "resume where I
        # left off" purpose (see Engine.depart_player/arrive_player), so
        # borrow it here instead.
        if is_current:
            player.x, player.y = save.player.x, save.player.y
            game_map.entities.append(player)
        else:
            player.x, player.y = place.last_position

        if is_overworld:
            for dungeon_id in quest_log.destroyed_dungeon_ids:
                ruin_data = dungeon_ruin_data.get(dungeon_id)
                if ruin_data is not None:
                    apply_dungeon_destruction(game_map, dungeon_id, *ruin_data)

        engine = Engine(
            game_map, player, level.name,
            catalog=catalog, levels=levels_dict, starting_level=starting_level,
            current_level_id=current_state_key if not is_overworld else None,
            is_overworld=is_overworld,
            dungeon_inspect_text=dungeon_inspect_text if is_overworld else None,
            dungeon_ruin_data=dungeon_ruin_data if is_overworld else None,
            clock=clock, quest_log=quest_log, sprite_codepoints=sprite_codepoints,
            overworld_return_position=(
                tuple(place.overworld_return_position) if place.overworld_return_position else None
            ),
        )
        engine.current_level_id = place.current_level_id
        engine.last_position = tuple(place.last_position)

        if not is_overworld:
            for level_id, level_state in place.levels.items():
                if level_id == current_state_key:
                    continue  # already the live game_map above
                engine.visited_maps[level_id] = _build_map_for_load(levels_dict[level_id], catalog, level_state)

        active_engines[key] = engine

    # Undo every temporary player.x/y borrow above (the last iteration may
    # have been a non-active place) - the player's real position is always
    # save.player.x/y, already correct for the active place specifically.
    player.x, player.y = save.player.x, save.player.y

    # game_state isn't part of the saved schema - it's fully derivable from
    # the player's own hp (Engine.on_entity_death sets "dead" exactly when
    # hp drops to 0), so it's re-derived here rather than duplicated. Only
    # the active engine matters: a cached-but-inactive place's game_state
    # is never touched by on_entity_death in the first place (the player
    # can only die wherever they currently are), so every other engine
    # correctly keeps Engine.__init__'s "playing" default. Without this,
    # a save captured while dead (main.py's own SaveGameAction blocks this,
    # but nothing stops a script/tool from persisting one anyway) would
    # restore with game_state defaulting back to "playing" despite
    # negative/zero hp, silently breaking RestartAction's own
    # `if engine.game_state != "playing"` gate.
    active_engines[save.active_key].game_state = "dead" if player.fighter.hp <= 0 else "playing"

    return save.active_key, active_engines, clock, quest_log


# --- file I/O ---


def save_to_path(save: SaveGame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(save.model_dump_json(indent=2), encoding="utf-8")


def load_from_path(path: Path) -> SaveGame | None:
    """None for a missing or corrupt/unreadable file - the caller falls
    back to a fresh start rather than crashing, the same spirit as a
    ContentValidationError being reported rather than propagated raw."""
    if not path.exists():
        return None
    try:
        return SaveGame.model_validate_json(path.read_text(encoding="utf-8"))
    except (ValueError, TypeError):
        return None
