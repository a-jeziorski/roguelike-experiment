"""Owns game state and the turn loop. Rendering/windowing is driven from main.py
so Engine itself stays testable without an SDL window."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from content.schema import (
    AI_HOSTILE_BASIC,
    AI_RANGED_BASIC,
    AI_SKITTISH,
    AI_SLEEPING_GUARD,
    AI_TOWN_GUARD,
    AI_VILLAGER,
    PEACEFUL_AI_TYPES,
)
from engine.actions import Action, MovementAction
from engine.clock import GameClock
from engine.combat import resolve_attack, resolve_ranged_attack
from engine.entity import POTION_KINDS, Entity, apply_perk_stat_bonus
from engine.game_map import GameMap, apply_dungeon_destruction, build_game_map, item_entity_from_def
from engine.quest import Quest, QuestLog

if TYPE_CHECKING:
    from content.loader import Catalog, ParsedLevel
    from content.schema import TightenDeadline
    from engine.sprites import SpriteCodepoints

# Fallbacks when a monster doesn't specify its own alert_radius/flee_hp_pct/
# ranged_range.
DEFAULT_ALERT_RADIUS = 4
DEFAULT_FLEE_HP_PCT = 0.3
DEFAULT_MONSTER_RANGED_RANGE = 4

# Flat XP awarded for discovering a landmark (see
# Engine._log_newly_seen_tile_announcements) - deliberately small relative
# to a monster kill/quest reward, since a landmark costs the player no
# risk to find, only exploration.
LANDMARK_XP_REWARD = 5

# Candidate steps for AI_VILLAGER's idle wander: the 8 directions plus
# "stay put" repeated 8 times, so a wandering villager holds position about
# as often as it moves - reads as puttering around rather than skittering.
_WANDER_MOVES = [(0, 0)] * 8 + [
    (dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx, dy) != (0, 0)
]

# Last-resort fallback if a talkable entity somehow has no dialogue at all
# (no per-spawn override, no catalog-level default either) - should never
# actually fire for a properly-authored villager, kept only for safety.
_DEFAULT_TALK_LINE = "They don't seem to have anything to say."

# Fallback logged when the player leaves an open_boundary level (see
# GameMap.open_boundary) with no LevelDef.open_boundary_message authored -
# same "sensible generic default, content can override" shape as
# _DEFAULT_TALK_LINE above.
_DEFAULT_OPEN_BOUNDARY_MESSAGE = "You walk past the edge of the map, back onto open ground."


class Message(str):
    """A logged line plus which color category the message log renders it
    in (see engine/render.py's render_message_log). A str subclass rather
    than a separate wrapper type on purpose: every existing `"text" in
    message_log.messages` / `messages == [...]` / `.count(text)` comparison
    keeps working unchanged against a plain string - only render_message_log
    needs to know about .category."""

    category: str

    def __new__(cls, text: str, category: str = "info") -> "Message":
        obj = str.__new__(cls, text)
        obj.category = category
        return obj


class MessageLog:
    def __init__(self) -> None:
        self.messages: list[Message] = []

    def add(self, text: str, category: str = "info") -> None:
        self.messages.append(Message(text, category))


class Engine:
    def __init__(
        self,
        game_map: GameMap,
        player: Entity,
        level_name: str,
        *,
        catalog: "Catalog | None" = None,
        levels: "dict[str, ParsedLevel] | None" = None,
        starting_level: "ParsedLevel | None" = None,
        is_overworld: bool = False,
        dungeon_inspect_text: dict[str, str] | None = None,
        dungeon_ruin_data: dict[str, tuple[str, str]] | None = None,
        clock: GameClock | None = None,
        quest_log: QuestLog | None = None,
        sprite_codepoints: "SpriteCodepoints | None" = None,
        overworld_return_position: tuple[int, int] | None = None,
    ):
        self.game_map = game_map
        self.player = player
        self.level_name = level_name
        self.message_log = MessageLog()
        self.game_state = "playing"  # "playing" | "dead"
        # An explicit flag (not inferred from `levels is None`) so render.py's
        # HUD can hide dungeon-only control hints (pickup/potion/fire) without
        # coupling that to an unrelated invariant that could change later.
        self.is_overworld = is_overworld
        # Shared world-clock object: main.py hands the *same* GameClock
        # instance to every Engine it constructs, so advancing it from the
        # overworld Engine is instantly visible from every dungeon Engine's
        # .clock reference too - same "one object, referenced everywhere"
        # pattern as self.player across depart_player/arrive_player. Defaults
        # to a fresh GameClock() so bare Engine(...) construction in tests
        # doesn't need to know or care about it.
        self.clock = clock if clock is not None else GameClock()
        # Shared quest log, same pattern as self.clock above - main.py hands
        # every Engine the same QuestLog instance (built by
        # engine.quest.create_quest_log from data/quests.yaml), so completing
        # or failing the one active quest is visible everywhere at once.
        # Defaults to a fresh *empty* QuestLog() (no quests inside) so bare
        # Engine(...) construction in tests stays inert.
        self.quest_log = quest_log if quest_log is not None else QuestLog()
        # dungeon_id -> flavor text shown when a dungeon_entrance tile is
        # inspected in look mode (see engine/render.py describe_tile). Only
        # ever populated for the overworld Engine - every other Engine has no
        # dungeon_entrance tiles to describe, so an empty dict is correct.
        self.dungeon_inspect_text = dungeon_inspect_text or {}
        # dungeon_id -> (ruined_tile, ruined_description), for Engine.destroy_dungeon
        # to apply once a quest's on_fail fires a destroy_dungeon_id
        # consequence (see content.schema.DungeonDef, WorldConsequence).
        # Same "only ever populated for the
        # overworld Engine" restriction as dungeon_inspect_text above -
        # destroy_dungeon is only ever called while is_overworld is True.
        self.dungeon_ruin_data = dungeon_ruin_data or {}
        # Needed to resolve a stairway's destination id into content when
        # descending; only required if the dungeon actually branches/continues.
        self.catalog = catalog
        # Shared across every Engine main.py constructs, same "one object,
        # referenced everywhere" pattern as self.clock/self.quest_log - see
        # engine/sprites.py. None (the default) means "no sprite manifest
        # loaded," which engine/render.py treats identically to an empty
        # one: every glyph falls back to its authored ASCII character.
        self.sprite_codepoints = sprite_codepoints
        self.levels = levels
        # The level a fresh run begins at, kept so restart() can rebuild from
        # scratch; only required if restarting is supported for this Engine.
        self.starting_level = starting_level
        # Which key of self.levels self.game_map currently is, so a stairway
        # can look up "what level did the player just come from" (for
        # arrival matching) and so on_player_reach_stairs knows where to
        # file the outgoing map in the cache below.
        self.current_level_id = starting_level.id if starting_level is not None else None
        # GameMaps for every level the player has already visited, keyed by
        # level id. Reusing the *same* GameMap object on a return visit -
        # instead of rebuilding one from the static ParsedLevel - is what
        # makes dead monsters stay dead, picked-up items stay gone, unlocked
        # doors stay unlocked, and explored tiles stay explored.
        self.visited_maps: dict[str, GameMap] = {}
        # (from_x, from_y, to_x, to_y) for every ranged attack, and (x, y) for
        # every melee hit, resolved during the last process_turn() call -
        # combat.py appends to these, main.py drains them to drive impact
        # animations. Engine itself never reads them back; they're purely a
        # mailbox to the SDL-dependent render layer, which is why they live
        # here instead of forcing Engine to know about rendering.
        self.ranged_attack_events: list[tuple[int, int, int, int]] = []
        self.melee_attack_events: list[tuple[int, int]] = []
        # Mailbox flags for main.py: Engine only ever sets these to signal "the
        # player wants to leave this dungeon/enter that dungeon" - it never acts
        # on them itself, since it has no access to the dungeon registry or the
        # overworld (only main.py, which owns both, can perform the actual
        # cross-Engine handoff). Same pattern as ranged_attack_events above.
        self.wants_overworld = False
        self.pending_dungeon_entry: str | None = None
        # The overworld coordinate this Engine should hand the player back
        # to whenever it next leaves for the overworld, overriding
        # main.py's normal _match_entrance lookup - None (the default, every
        # normal dungeon/the overworld itself) means "use _match_entrance/
        # player_start as usual." Only ever set on an overworld-encounter
        # Engine (see EncounterDef/main.py's resolve_transition), since an
        # encounter dungeon has no overworld dungeon_entrance tile for
        # _match_entrance to find - without this, leaving one would
        # incorrectly land the player at the world's default player_start
        # instead of back on the road where the encounter interrupted them.
        self.overworld_return_position = overworld_return_position
        # Where depart_player last saw the player, for arrive_player's
        # "resume exactly where they left" path. Set for real the first time
        # depart_player runs; the initial value just avoids the attribute
        # not existing yet.
        self.last_position = (player.x, player.y)
        if self.current_level_id is not None:
            self.visited_maps[self.current_level_id] = self.game_map

        self.game_map.update_fov((player.x, player.y))
        self.message_log.add(f"You enter {level_name}.")
        self._log_newly_seen_tile_announcements()

    def on_entity_death(self, entity: Entity) -> None:
        if entity is self.player:
            self.message_log.add("You have died...", category="combat")
            self.game_state = "dead"
        else:
            self.message_log.add(f"The {entity.name} dies.", category="combat")
            if entity in self.game_map.entities:
                self.game_map.entities.remove(entity)
            # Records the death only - a kill quest doesn't complete here
            # anymore, only when reported to its questgiver (see
            # talk_to_adjacent's check_kill_report loop).
            self.quest_log.record_entity_killed(entity.entity_id)
            # Unlike every other trigger shape, an intimidate quest can
            # fail right here, immediately - a dead target can never be
            # "intimidated" per the quest's own premise, so this can't wait
            # for the player's next report the way check_kill_report does.
            for quest, was_in_progress in self.quest_log.fail_intimidate_by_death(entity.entity_id):
                if was_in_progress and quest.failure_message:
                    self.message_log.add(quest.failure_message)
            if entity.xp_reward:
                self._award_xp(entity.xp_reward, "kill")

    def _award_xp(self, amount: int, reason: str) -> None:
        """The single funnel every XP source routes through (kills, quest
        completion, landmark discovery) - same reasoning as complete_quest
        being the one funnel for item/gold/discount rewards."""
        self.player.xp += amount
        self.message_log.add(f"You gain {amount} XP ({reason}).")

    def _log_newly_seen_tile_announcements(self) -> None:
        """Logs the flavor text for any auto-announce tile that just entered
        the player's FOV for the first time (GameMap.newly_seen_tile_announcements)
        - called after every update_fov, so a landmark's description reaches
        the player automatically instead of requiring a manual Look. Placed
        after any "You enter X."-style message at each call site, so an
        announcement never appears to precede the arrival it's describing.
        Awards LANDMARK_XP_REWARD only for a tile:landmark entry - a
        flavorful gate/stairs/item announcement still logs its text but
        grants no XP (see GameMap.landmark_announce_tiles)."""
        for text, is_landmark in self.game_map.newly_seen_tile_announcements():
            self.message_log.add(text, category="flavor")
            if is_landmark:
                self._award_xp(LANDMARK_XP_REWARD, "discovery")

    def _arrival_position(self, level: "ParsedLevel", from_level_id: str | None) -> tuple[int, int]:
        """Where the player lands on `level`: the stairway leading back to
        from_level_id if one exists, else the level's player_start - also
        the fallback used unconditionally today, since no level yet defines
        a stairs_up (so every existing dungeon keeps behaving exactly as
        before this method existed)."""
        if from_level_id is not None:
            for stairs in level.stairs:
                if stairs.next_level == from_level_id:
                    return (stairs.x, stairs.y)
        return level.player_start

    def depart_player(self) -> Entity:
        """Removes the player from the current map and caches that map under
        its level id, so a later return visit resumes it exactly as left
        (dead monsters, picked-up items, unlocked doors, explored tiles).
        Records last_position *before* the caller repositions the player
        elsewhere - the player Entity's x/y is shared and mutable, and will
        get overwritten by whatever map becomes active next (typically the
        overworld), so this Engine needs its own memory of where it left the
        player, independent of where that Entity physically ends up in the
        meantime. Clears both transition mailbox flags - their lifetime is
        tied to "the player is currently on this map," so a cached Engine can
        never re-fire a stale transition the next time it becomes active.
        Used both for intra-dungeon stairs and for leaving to/entering from
        the overworld (main.py calls this directly for the latter)."""
        self.last_position = (self.player.x, self.player.y)
        self.game_map.entities.remove(self.player)
        if self.current_level_id is not None:
            self.visited_maps[self.current_level_id] = self.game_map
        self.wants_overworld = False
        self.pending_dungeon_entry = None
        return self.player

    def arrive_player(self, player: Entity, position: tuple[int, int] | None = None) -> None:
        """Counterpart to depart_player, for resuming a *cached* Engine (this
        dungeon/the overworld was already visited). `position` is given when
        arrival must be matched to a specific tile (the overworld, always);
        left None to resume exactly where *this* Engine's player last
        departed from (re-entering an already-visited dungeon) - using
        self.last_position rather than the player's current x/y, since that
        may since have been overwritten by whatever map was active in
        between. First-time creation of a target Engine doesn't use this -
        the constructor + build_game_map already do the equivalent
        bootstrapping.

        Resets message_log first - a cached Engine's log otherwise keeps
        every message from every earlier visit, so returning to a
        dungeon/the overworld later in the same run would surface stale
        dialogue and combat lines from the last time the player was here,
        alongside (and easily confused with) whatever's happening now."""
        self.player = player
        player.x, player.y = position if position is not None else self.last_position
        self.game_map.entities.append(player)
        self.message_log = MessageLog()
        self.message_log.add(f"You enter {self.level_name}.")
        self.game_map.update_fov((player.x, player.y))
        self._log_newly_seen_tile_announcements()

    def on_player_reach_stairs(self, next_level_id: str | None, kind: str = "stairs_down") -> None:
        if next_level_id is None:
            verb = "retreat back to the surface" if kind == "stairs_up" else "leave the dungeon behind"
            self.message_log.add(f"You {verb}.")
            self.wants_overworld = True
            return

        if self.current_level_id is not None:
            self.game_map.entities.remove(self.player)
            self.visited_maps[self.current_level_id] = self.game_map

        next_level = self.levels[next_level_id]
        cached_map = self.visited_maps.get(next_level_id)
        arrival = self._arrival_position(next_level, self.current_level_id)

        if cached_map is not None:
            self.game_map = cached_map
            self.player.x, self.player.y = arrival
            self.game_map.entities.append(self.player)
        else:
            self.game_map, self.player = build_game_map(next_level, self.catalog, player=self.player)
            self.player.x, self.player.y = arrival

        self.current_level_id = next_level_id
        self.level_name = next_level.name
        verb = "ascend to" if kind == "stairs_up" else "descend into"
        # Reset here too, same reasoning as arrive_player - this Engine
        # persists across the whole run, so without a reset a level revisited
        # later would still be carrying every message from earlier visits to
        # *other* levels in this same dungeon, not just this one.
        self.message_log = MessageLog()
        self.message_log.add(f"You {verb} {next_level.name}.")
        self.game_map.update_fov((self.player.x, self.player.y))
        self._log_newly_seen_tile_announcements()

    def on_player_reach_map_edge(self) -> None:
        """Called by MovementAction when the player steps off the edge of
        an open_boundary level (see GameMap.open_boundary) - the open-area
        equivalent of on_player_reach_stairs(None, ...), just triggered by
        geography instead of a specific tile. Always leaves to the
        overworld, same wants_overworld mailbox main.py's resolve_transition
        already consumes - overworld_return_position (if this Engine has
        one set, e.g. an overworld-encounter Engine) still applies exactly
        as it does for a stairway exit, no special-casing needed here."""
        self.message_log.add(self.game_map.open_boundary_message or _DEFAULT_OPEN_BOUNDARY_MESSAGE)
        self.wants_overworld = True

    def restart(self) -> None:
        """Begins a fresh run from the starting level: a brand-new player (full
        hp, no inventory or picked-up attack bonus), a freshly built map (killed
        monsters and taken items restored), a cleared message log, the world
        clock reset to its starting date, and every quest reset to its own
        starting status (see QuestLog.reset) - since self.clock/self.quest_log
        are shared by every cached Engine, this is visible everywhere
        immediately, which is the intended "clean do-over" behavior for a
        restart."""
        self.clock.reset()
        self.quest_log.reset()
        self.game_map, self.player = build_game_map(self.starting_level, self.catalog)
        self.level_name = self.starting_level.name
        self.game_state = "playing"
        self.message_log = MessageLog()
        self.ranged_attack_events = []
        self.melee_attack_events = []
        self.wants_overworld = False
        self.pending_dungeon_entry = None
        self.last_position = (self.player.x, self.player.y)
        # A fresh run discards all progress on every level, not just the one
        # currently live - every previously cached GameMap goes with it.
        self.visited_maps = {}
        self.current_level_id = self.starting_level.id
        self.visited_maps[self.current_level_id] = self.game_map
        self.game_map.update_fov((self.player.x, self.player.y))
        self.message_log.add(f"You enter {self.level_name}.")
        self._log_newly_seen_tile_announcements()

    def _perform_ai(self, entity: Entity) -> None:
        if not self.game_map.visible[entity.x, entity.y]:
            return

        dx = self.player.x - entity.x
        dy = self.player.y - entity.y
        distance = max(abs(dx), abs(dy))

        if entity.ai == AI_HOSTILE_BASIC:
            self._chase_and_attack(entity, dx, dy, distance)

        elif entity.ai == AI_SLEEPING_GUARD:
            alert_radius = entity.alert_radius or DEFAULT_ALERT_RADIUS
            if distance <= alert_radius:
                self._chase_and_attack(entity, dx, dy, distance)

        elif entity.ai == AI_SKITTISH:
            flee_hp_pct = entity.flee_hp_pct or DEFAULT_FLEE_HP_PCT
            if entity.fighter.hp / entity.fighter.max_hp <= flee_hp_pct:
                self._flee(entity, dx, dy)
            else:
                self._chase_and_attack(entity, dx, dy, distance)

        elif entity.ai == AI_RANGED_BASIC:
            ranged_range = entity.ranged_range or DEFAULT_MONSTER_RANGED_RANGE
            if distance <= 1:
                resolve_attack(self, attacker=entity, defender=self.player)
            elif distance <= ranged_range:
                resolve_ranged_attack(self, attacker=entity, defender=self.player)
            else:
                step_x = (dx > 0) - (dx < 0)
                step_y = (dy > 0) - (dy < 0)
                MovementAction(step_x, step_y).perform(self, entity)

        elif entity.ai == AI_VILLAGER:
            # Never fights back - there's no branch here that ever calls
            # resolve_attack. hp < max_hp is a reliable "has been attacked"
            # proxy since nothing ever heals a non-player entity, so this
            # can't falsely reset once triggered.
            if entity.fighter.hp < entity.fighter.max_hp:
                self._flee(entity, dx, dy)
            elif not entity.stationary:
                self._wander(entity)

        elif entity.ai == AI_TOWN_GUARD:
            # Deliberately no per-entity hp check here, unlike AI_VILLAGER -
            # a guard's hostility is purely the shared map-wide flag, not
            # personal injury, since an untouched guard elsewhere on the map
            # still needs to turn hostile the instant anyone provokes the
            # town (see engine/combat.py's _apply_damage).
            if self.game_map.player_attacked_peaceful_npc:
                self._chase_and_attack(entity, dx, dy, distance)
            else:
                self._wander(entity)

    def _chase_and_attack(self, entity: Entity, dx: int, dy: int, distance: int) -> None:
        if distance <= 1:
            resolve_attack(self, attacker=entity, defender=self.player)
        else:
            step_x = (dx > 0) - (dx < 0)
            step_y = (dy > 0) - (dy < 0)
            MovementAction(step_x, step_y).perform(self, entity)

    def _flee(self, entity: Entity, dx: int, dy: int) -> None:
        """Steps directly away from the player. If that's blocked (wall,
        another entity, a corner), MovementAction's own checks just no-op -
        the entity holds position rather than being forced to fight."""
        step_x = -((dx > 0) - (dx < 0))
        step_y = -((dy > 0) - (dy < 0))
        MovementAction(step_x, step_y).perform(self, entity)

    def _wander(self, entity: Entity) -> None:
        """Idle movement untargeted at the player - "going about their
        business." Picks a random adjacent tile or holds position;
        MovementAction already no-ops safely if the destination is blocked
        or occupied, the same free behavior _flee relies on."""
        step_x, step_y = random.choice(_WANDER_MOVES)
        MovementAction(step_x, step_y).perform(self, entity)

    def _handle_enemy_turns(self) -> None:
        for entity in list(self.game_map.entities):
            if entity is self.player or not entity.is_alive or entity.ai is None:
                continue
            self._perform_ai(entity)

    def _advance_world_clock(self) -> None:
        """The only source of in-game time passing: one hour per turn taken
        on the overworld (dungeons/settlements never call this - is_overworld
        is False for all of them, including Millhaven/Wayford). Passive
        healing is the sole current effect of time passing; future effects
        can hang off self.clock without changing this method's shape."""
        self.clock.advance_hour()
        fighter = self.player.fighter
        fighter.hp = min(fighter.max_hp, fighter.hp + 1)

    def _check_quest_deadlines(self) -> None:
        """Sibling to _advance_world_clock, called the same turn: any in-progress
        quest whose deadline the clock just crossed gets its failure message
        logged here. A separate method (not folded into _advance_world_clock)
        so deadline logic is testable independent of clock/healing mechanics.
        Only ever called while self.is_overworld (see the one call site in
        process_turn) - a newly-failed quest's on_fail entries are safe to
        act on immediately, since self.game_map is guaranteed to be the
        overworld's own map here."""
        for quest in self.quest_log.check_deadlines(self.clock):
            self.message_log.add(quest.failure_message)
            self._apply_world_consequences(quest)

    def _apply_world_consequences(self, quest: Quest) -> None:
        """Applies every WorldConsequence in quest.on_fail, in list order -
        the sole call site is _check_quest_deadlines, on_fail's only
        trigger. destroy_dungeon_id defers to destroy_dungeon (already
        idempotent, so two quests naming the same dungeon in one tick is
        safe); set_flag just records a name in quest_log.world_flags, read
        back by Entity.flag_dialogue/talk_to_adjacent (see
        content.schema.FlagDialogue); tighten_deadline defers to
        _tighten_deadline. The three kinds don't interact, so list order
        has no observable effect today - kept anyway for a future consumer
        that might care."""
        for consequence in quest.on_fail:
            if consequence.destroy_dungeon_id is not None:
                self.destroy_dungeon(consequence.destroy_dungeon_id)
            elif consequence.set_flag is not None:
                self.quest_log.world_flags.add(consequence.set_flag)
            elif consequence.tighten_deadline is not None:
                self._tighten_deadline(consequence.tighten_deadline)

    def _tighten_deadline(self, tighten: "TightenDeadline") -> None:
        """Shortens another quest's own deadline_day - the sole call site
        is _apply_world_consequences, tighten_deadline's only trigger.
        No-ops on a target that doesn't exist (shouldn't happen once
        content is validated by content/loader.py's load_quests, but
        defensive rather than crashing on a misconfigured quest, same
        posture as destroy_dungeon's ruin_data guard below), one that's
        already terminal (completed/failed - nothing left to tighten,
        same re-fire guard QuestLog.check_deadlines/void_by_dungeon use),
        or one with no deadline_day at all (also validated away at load
        time, checked again here for the same defensive reason).
        Deliberately works on a not_given quest too (not just
        in_progress) - the world got more dangerous whether or not the
        player has personally picked up that quest yet, so the tighter
        deadline is already waiting the moment they do. Only ever
        SHORTENS: a new_day later than the current deadline_day is a
        silent no-op, never an accidental extension."""
        quest = self.quest_log.quests.get(tighten.quest_id)
        if quest is None or quest.status in ("completed", "failed") or quest.deadline_day is None:
            return
        if tighten.new_day < quest.deadline_day:
            quest.deadline_day = tighten.new_day

    def destroy_dungeon(self, dungeon_id: str) -> None:
        """Razes dungeon_id's overworld entrance (see
        engine.game_map.apply_dungeon_destruction) and force-fails every
        quest voided by its destruction (QuestLog.void_by_dungeon) -
        their questgiver or completion target lived there and is gone now.
        A voided quest the player never received (not_given) fails
        silently; one they'd already started (in_progress) gets its
        failure_message logged, same as an ordinary deadline failure.
        No-ops if dungeon_id has no ruin content registered (shouldn't
        happen once content is validated, see main.py's
        _check_destroyable_dungeons_have_ruin_content, but defensive
        rather than crashing on a misconfigured quest)."""
        ruin_data = self.dungeon_ruin_data.get(dungeon_id)
        if ruin_data is None:
            return
        ruined_tile, ruined_description = ruin_data
        apply_dungeon_destruction(self.game_map, dungeon_id, ruined_tile, ruined_description)
        self.quest_log.destroyed_dungeon_ids.add(dungeon_id)
        for quest, was_in_progress in self.quest_log.void_by_dungeon(dungeon_id):
            if was_in_progress and quest.failure_message:
                self.message_log.add(quest.failure_message)

    def _is_currently_peaceful(self, entity: Entity) -> bool:
        """Whether `entity` is still meaningfully peaceful right now - a
        villager already hurt (fleeing) or a town guard after the map's
        hostility flag has tripped are no longer peaceful in any real
        sense, even though their catalog ai type is still one of
        PEACEFUL_AI_TYPES. Shared by _find_adjacent_peaceful_npc (is this
        NPC currently talkable/tradeable) and would_attack_peaceful_npc
        (does bumping this NPC need a deliberate confirmation instead of
        attacking outright).

        A villager that's been hurt is excluded - per _perform_ai's own
        AI_VILLAGER branch, any damage at all makes a villager flee
        permanently (nothing ever heals a non-player entity, so hp <
        max_hp is a stable "currently fleeing" flag, not a fleeting one).
        A town guard's hostility is map-wide rather than personal, so it's
        excluded once game_map.player_attacked_peaceful_npc trips even if
        this specific guard is undamaged - villagers are NOT affected by
        that flag (only their own hp matters to them); that asymmetry is
        intentional, not a leak."""
        if entity.ai not in PEACEFUL_AI_TYPES:
            return False
        if entity.ai == AI_TOWN_GUARD and self.game_map.player_attacked_peaceful_npc:
            return False
        if entity.fighter is not None and entity.fighter.hp < entity.fighter.max_hp:
            return False
        return True

    def _find_adjacent_peaceful_npc(
        self, entity_id: str | None = None, requires_shop: bool = False,
        requires_trainer: bool = False,
    ) -> Entity | None:
        """The first currently-peaceful entity (see _is_currently_peaceful)
        within 8-directional adjacency of the player - matches the
        project's diagonal-movement model. Hostile monsters are never
        talkable (filtered by AI type, not a new flag); bumping them still
        attacks, unchanged. `entity_id`, if given, additionally restricts
        the match to that specific catalog id. `requires_shop`, if True,
        additionally restricts the match to an entity with a non-empty
        shop_inventory (see EntityDef.shop_inventory) - i.e. any
        shopkeeper, not one hardcoded catalog id - see adjacent_shopkeeper.
        `requires_trainer` is the same idea for trainer_perks - see
        adjacent_trainer. Leaving all three at their defaults reproduces
        the original unfiltered scan exactly. A fleeing/hostile NPC won't
        stop to talk or trade, so both talk_to_adjacent and
        adjacent_shopkeeper get this for free from the one shared scan."""
        px, py = self.player.x, self.player.y
        for entity in self.game_map.entities:
            if not self._is_currently_peaceful(entity):
                continue
            if entity_id is not None and entity.entity_id != entity_id:
                continue
            if requires_shop and not entity.shop_inventory:
                continue
            if requires_trainer and not entity.trainer_perks:
                continue
            if entity.x == px and entity.y == py:
                continue
            if abs(entity.x - px) <= 1 and abs(entity.y - py) <= 1:
                return entity
        return None

    def would_attack_peaceful_npc(self, dx: int, dy: int) -> Entity | None:
        """Whether bumping (dx, dy) from the player's current position
        would resolve to a melee attack against a still-peaceful NPC (see
        _is_currently_peaceful) rather than an ordinary move or a fight
        with something already hostile. main.py checks this before
        dispatching a BumpAction and shows a confirmation prompt instead
        of attacking outright when it returns an entity - so a moment of
        misjudged pathing near a villager/guard never turns into an
        unintended fight (and, for a town guard, unintended map-wide
        hostility) the way a plain bump-to-attack otherwise would. Mirrors
        BumpAction's own "is something blocking the destination" check
        (engine/actions.py) without performing anything - purely a peek."""
        dest_x, dest_y = self.player.x + dx, self.player.y + dy
        blocker = self.game_map.blocking_entity_at(dest_x, dest_y)
        if blocker is not None and self._is_currently_peaceful(blocker):
            return blocker
        return None

    def adjacent_shopkeeper(self) -> Entity | None:
        """The first adjacent peaceful NPC with a non-empty shop_inventory
        (see EntityDef.shop_inventory) - any shopkeeper, not one hardcoded
        catalog id, so a new town's own shopkeeper NPC works with no engine
        change. Used by main.py's shop_gate to decide whether shop mode can
        be entered, and by run_shop_mode/buy_from_shop to know which items
        are actually for sale here."""
        return self._find_adjacent_peaceful_npc(requires_shop=True)

    def complete_quest(self, quest: Quest, message: str | None = None) -> None:
        """Logs completion and grants whichever reward(s) are set - the
        single funnel every completion trigger (kill, Talk, dungeon
        arrival, fetch, a retroactive questgiver grant) routes through, so
        reward-granting only has to be written once. Never mutates
        quest.status - that already happened inside whichever QuestLog.check_*
        call produced this quest; this is purely "log + reward". Never
        called for a quest that failed - failing a quest never grants a
        reward. The reward shapes (reward_item_id, reward_gold_amount,
        reward_xp_amount, reward_shop_discount_pct) aren't mutually
        exclusive - a quest can set any combination, though no shipped
        quest currently combines more than one of the non-XP shapes."""
        self.message_log.add(message or quest.completion_message)
        if quest.reward_item_id is not None and self.catalog is not None:
            idef = self.catalog.items[quest.reward_item_id]
            reward = item_entity_from_def(idef)
            self.player.inventory.append(reward)
            self.message_log.add(f"You receive a {reward.name}.")
        if quest.reward_gold_amount:
            self.player.gold += quest.reward_gold_amount
            self.message_log.add(f"You receive {quest.reward_gold_amount} gold.")
        if quest.reward_xp_amount:
            self._award_xp(quest.reward_xp_amount, "quest")
        if quest.reward_shop_discount_pct and quest.reward_shop_discount_entity_id:
            pct = int(quest.reward_shop_discount_pct * 100)
            shop_name = "shop"
            if self.catalog is not None and quest.reward_shop_discount_entity_id in self.catalog.entities:
                shop_name = self.catalog.entities[quest.reward_shop_discount_entity_id].name
            self.message_log.add(f"The {shop_name} now gives you a permanent {pct}% discount.")

    def shop_price(self, item_id: str, shopkeeper: Entity) -> int:
        """The gold cost to buy item_id right now from shopkeeper
        specifically, after any permanent discount unlocked at *that*
        shopkeeper's shop by a completed quest (see
        QuestLog.shop_discount_pct, keyed by shopkeeper.entity_id) - a
        discount quest scoped to a different shopkeeper never affects this
        price. Reused by buy_from_shop (to charge correctly) and main.py's
        shop screen (to display the same number)."""
        if self.catalog is None or item_id not in self.catalog.items:
            return 0
        idef = self.catalog.items[item_id]
        discount = self.quest_log.shop_discount_pct(shopkeeper.entity_id)
        return round((idef.cost or 0) * (1 - discount))

    def buy_from_shop(self, item_id: str) -> str:
        """Attempts to buy one item from the shop for the player, from the
        inventory of whichever shopkeeper is currently adjacent (see
        adjacent_shopkeeper/EntityDef.shop_inventory) - not just any catalog
        item, since two shopkeepers can now stock different things. Returns
        the status message (also logged to message_log, so it's still
        visible after leaving the shop screen - see main.py's run_shop_mode,
        which doesn't render the message log itself). Never touches
        game_state/clock/enemy turns - buying costs no turn, same reasoning
        as talk_to_adjacent."""
        shopkeeper = self.adjacent_shopkeeper()
        if (
            self.catalog is None
            or item_id not in self.catalog.items
            or shopkeeper is None
            or item_id not in shopkeeper.shop_inventory
        ):
            message = "The shop is unavailable."
            self.message_log.add(message)
            return message
        idef = self.catalog.items[item_id]
        cost = self.shop_price(item_id, shopkeeper)
        if self.player.gold < cost:
            message = "You can't afford that."
            self.message_log.add(message)
            return message
        self.player.gold -= cost
        reward = item_entity_from_def(idef)
        self.player.inventory.append(reward)
        message = f"You buy a {reward.name} for {cost} gold."
        self.message_log.add(message)
        return message

    def adjacent_trainer(self) -> Entity | None:
        """The first adjacent peaceful NPC with a non-empty trainer_perks
        (see EntityDef.trainer_perks) - any Trainer, not one hardcoded
        catalog id, so a new town's own Trainer NPC works with no engine
        change. Used by main.py's trainer_gate to decide whether trainer
        mode can be entered, and by run_trainer_mode/learn_perk to know
        which perks are actually teachable here."""
        return self._find_adjacent_peaceful_npc(requires_trainer=True)

    def learn_perk(self, perk_id: str) -> str:
        """Attempts to permanently learn one perk for the player, taught by
        whichever Trainer is currently adjacent (see adjacent_trainer/
        EntityDef.trainer_perks) - not just any catalog perk, since two
        Trainers can teach different things. Returns the status message
        (also logged, so it's still visible after leaving the trainer
        screen - see main.py's run_trainer_mode). Never touches
        game_state/clock/enemy turns - learning costs no turn, same
        reasoning as buy_from_shop. A perk is one-time-only: already
        knowing it is rejected the same way as being unable to afford it,
        never silently re-sold."""
        trainer = self.adjacent_trainer()
        if (
            self.catalog is None
            or perk_id not in self.catalog.perks
            or trainer is None
            or perk_id not in trainer.trainer_perks
        ):
            message = "The trainer is unavailable."
            self.message_log.add(message)
            return message
        if perk_id in self.player.learned_perk_ids:
            message = "You already know that."
            self.message_log.add(message)
            return message
        perk = self.catalog.perks[perk_id]
        if self.player.xp < perk.xp_cost or self.player.gold < (perk.gold_cost or 0):
            message = "You can't afford that."
            self.message_log.add(message)
            return message
        self.player.xp -= perk.xp_cost
        self.player.gold -= perk.gold_cost or 0
        self.player.learned_perk_ids.add(perk_id)
        apply_perk_stat_bonus(self.player.fighter, perk)
        # Only here, only once, only for a live purchase - the "instant
        # full benefit" a newly bought perk should give. Never done at
        # save-restore time (see engine/save.py's _build_player), since
        # saved.hp already reflects every historical bump.
        if perk.max_hp_bonus:
            self.player.fighter.hp += perk.max_hp_bonus
        message = f"You learn {perk.name}."
        self.message_log.add(message)
        return message

    def cycle_selected_potion_kind(self) -> None:
        """Free, non-turn action (see main.py's CyclePotionKindAction branch):
        advances player.selected_potion_kind to the next POTION_KINDS entry,
        wrapping around - this is what UseItemAction drinks."""
        i = POTION_KINDS.index(self.player.selected_potion_kind)
        self.player.selected_potion_kind = POTION_KINDS[(i + 1) % len(POTION_KINDS)]
        self.message_log.add(f"Selected potion: {self.player.selected_potion_kind}.")

    def talk_to_adjacent(self) -> None:
        """Free, non-turn action (see main.py's TalkAction branch): shows an
        adjacent villager's dialogue line, then checks whether talking to
        them grants a questgiver's quest (see QuestLog.check_questgiver),
        completes one that targets them (see QuestLog.check_talked_to),
        completes a fetch quest they're the questgiver for because the
        player is holding the delivered item (see QuestLog.check_delivery),
        completes a kill quest they're the questgiver for because its
        target's already been recorded dead (see QuestLog.check_kill_report),
        or completes a dungeon-arrival quest they're the questgiver for
        because its target dungeon's already been recorded visited (see
        QuestLog.check_dungeon_report), or completes an intimidate quest
        they're the questgiver for because its target's already been
        recorded intimidated (see QuestLog.check_intimidate_report). Never
        touches self.clock or calls _handle_enemy_turns - talking costs
        nothing."""
        target = self._find_adjacent_peaceful_npc()
        if target is None:
            self.message_log.add("There's no one here to talk to.", category="dialogue")
            return
        # A world-flag reaction takes priority over followup_dialogue: it
        # means something happened in the world that supersedes whatever
        # per-quest thank-you line would otherwise show (see
        # content.schema.FlagDialogue, docs/content_design_process.md §0k).
        flag_line = next(
            (fd.line for fd in target.flag_dialogue if fd.flag in self.quest_log.world_flags),
            None,
        )
        line = (
            flag_line
            or self.quest_log.followup_dialogue(target.entity_id)
            or target.dialogue
            or _DEFAULT_TALK_LINE
        )
        self.message_log.add(f'{target.name}: "{line}"', category="dialogue")

        for quest in self.quest_log.check_questgiver(target.entity_id):
            if quest.status == "completed":
                self.complete_quest(quest, message=quest.already_done_message or quest.completion_message)
            else:
                self.message_log.add(quest.given_message)
                if self.quest_log.active_quest_id is None:
                    self.quest_log.active_quest_id = quest.id

        for quest in self.quest_log.check_talked_to(target.entity_id):
            self.complete_quest(quest)

        for quest in self.quest_log.check_delivery(target.entity_id, self.player.inventory):
            delivered = next(it for it in self.player.inventory if it.entity_id == quest.target_item_id)
            self.player.inventory.remove(delivered)
            self.complete_quest(quest)

        for quest in self.quest_log.check_kill_report(target.entity_id):
            self.complete_quest(quest)

        for quest in self.quest_log.check_dungeon_report(target.entity_id):
            self.complete_quest(quest)

        for quest in self.quest_log.check_intimidate_report(target.entity_id):
            self.complete_quest(quest)

    def process_player_action(self, action: Action) -> bool:
        """The first half of a turn: just the player's own action. Returns
        False (and does nothing else) if the game had already ended before
        this call, matching process_turn's original all-or-nothing no-op in
        that case. Split out from process_turn so main.py's dispatch path can
        animate the player's own attack (see ranged_attack_events/
        melee_attack_events) before calling process_enemy_phase - otherwise a
        monster that survives a hit and then closes distance on its own turn
        has already moved by the time the impact flash renders, so the flash
        appears on the tile it left rather than on the monster. Player
        position never changes as a side effect of an attack action, so
        skipping the FOV update until process_enemy_phase causes no visible
        staleness during that in-between animation."""
        if self.game_state != "playing":
            return False
        action.perform(self, self.player)
        return True

    def process_enemy_phase(self) -> None:
        """The second half of a turn: enemy AI turns, player-death
        bookkeeping, world clock/quest deadlines, and the FOV update - see
        process_player_action's docstring for why this is split out.
        Guarded the same way process_turn's tail always was: each step only
        runs if the game is still "playing" going into it."""
        if self.game_state == "playing":
            self._handle_enemy_turns()

        if self.game_state == "playing" and not self.player.is_alive:
            self.on_entity_death(self.player)

        if self.game_state == "playing" and self.is_overworld:
            self._advance_world_clock()
            self._check_quest_deadlines()

        self.game_map.update_fov((self.player.x, self.player.y))
        self._log_newly_seen_tile_announcements()

    def process_turn(self, action: Action) -> None:
        """Resolves a full turn (both phases back to back, no animation gap)
        - what every caller that doesn't care about mid-turn animation
        timing should use (all existing tests, AI-only callers, etc.). See
        main.py's dispatch_action for the animated, two-phase version."""
        if not self.process_player_action(action):
            return
        self.process_enemy_phase()
