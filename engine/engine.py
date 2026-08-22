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
from engine.entity import Entity
from engine.game_map import GameMap, build_game_map, item_entity_from_def
from engine.quest import Quest, QuestLog
from engine.shop import SHOPKEEPER_ENTITY_ID

if TYPE_CHECKING:
    from content.loader import Catalog, ParsedLevel

# Fallbacks when a monster doesn't specify its own alert_radius/flee_hp_pct/
# ranged_range.
DEFAULT_ALERT_RADIUS = 4
DEFAULT_FLEE_HP_PCT = 0.3
DEFAULT_MONSTER_RANGED_RANGE = 4

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
        clock: GameClock | None = None,
        quest_log: QuestLog | None = None,
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
        # engine.quest.create_starting_quest_log), so completing or failing
        # the one active quest is visible everywhere at once. Defaults to a
        # fresh *empty* QuestLog() (no quests inside) so bare Engine(...)
        # construction in tests stays inert.
        self.quest_log = quest_log if quest_log is not None else QuestLog()
        # dungeon_id -> flavor text shown when a dungeon_entrance tile is
        # inspected in look mode (see engine/render.py describe_tile). Only
        # ever populated for the overworld Engine - every other Engine has no
        # dungeon_entrance tiles to describe, so an empty dict is correct.
        self.dungeon_inspect_text = dungeon_inspect_text or {}
        # Needed to resolve a stairway's destination id into content when
        # descending; only required if the dungeon actually branches/continues.
        self.catalog = catalog
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
        # Where depart_player last saw the player, for arrive_player's
        # "resume exactly where they left" path. Set for real the first time
        # depart_player runs; the initial value just avoids the attribute
        # not existing yet.
        self.last_position = (player.x, player.y)
        if self.current_level_id is not None:
            self.visited_maps[self.current_level_id] = self.game_map

        self.game_map.update_fov((player.x, player.y))
        self.message_log.add(f"You enter {level_name}.")

    def on_entity_death(self, entity: Entity) -> None:
        if entity is self.player:
            self.message_log.add("You have died...", category="combat")
            self.game_state = "dead"
        else:
            self.message_log.add(f"The {entity.name} dies.", category="combat")
            if entity in self.game_map.entities:
                self.game_map.entities.remove(entity)
            for quest in self.quest_log.record_entity_killed(entity.entity_id):
                self.complete_quest(quest)

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
        bootstrapping."""
        self.player = player
        player.x, player.y = position if position is not None else self.last_position
        self.game_map.entities.append(player)
        self.message_log.add(f"You enter {self.level_name}.")
        self.game_map.update_fov((player.x, player.y))

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
        self.message_log.add(f"You {verb} {next_level.name}.")
        self.game_map.update_fov((self.player.x, self.player.y))

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
        so deadline logic is testable independent of clock/healing mechanics."""
        for quest in self.quest_log.check_deadlines(self.clock):
            self.message_log.add(quest.failure_message)

    def _find_adjacent_peaceful_npc(self, entity_id: str | None = None) -> Entity | None:
        """The first PEACEFUL_AI_TYPES entity (villager or town_guard) within
        8-directional adjacency of the player - matches the project's
        diagonal-movement model. Hostile monsters are never talkable
        (filtered by AI type, not a new flag); bumping them still attacks,
        unchanged. `entity_id`, if given, additionally restricts the match
        to that specific catalog id (e.g. the shopkeeper) rather than any
        peaceful NPC - see adjacent_shopkeeper. Leaving it None reproduces
        the original unfiltered scan exactly.

        A villager that's been hurt is excluded - per _perform_ai's own
        AI_VILLAGER branch, any damage at all makes a villager flee
        permanently (nothing ever heals a non-player entity, so hp <
        max_hp is a stable "currently fleeing" flag, not a fleeting one).
        A town guard's hostility is map-wide rather than personal, so it's
        excluded once game_map.player_attacked_peaceful_npc trips even if
        this specific guard is undamaged - villagers are NOT affected by
        that flag (only their own hp matters to them); that asymmetry is
        intentional, not a leak. A fleeing/hostile NPC won't stop to talk or
        trade, so both talk_to_adjacent and adjacent_shopkeeper get this for
        free from the one shared scan."""
        px, py = self.player.x, self.player.y
        for entity in self.game_map.entities:
            if entity.ai not in PEACEFUL_AI_TYPES:
                continue
            if entity_id is not None and entity.entity_id != entity_id:
                continue
            if entity.ai == AI_TOWN_GUARD and self.game_map.player_attacked_peaceful_npc:
                continue
            if entity.fighter is not None and entity.fighter.hp < entity.fighter.max_hp:
                continue
            if entity.x == px and entity.y == py:
                continue
            if abs(entity.x - px) <= 1 and abs(entity.y - py) <= 1:
                return entity
        return None

    def adjacent_shopkeeper(self) -> Entity | None:
        """The shopkeeper NPC, if one is adjacent to the player - used by
        main.py's shop_gate to decide whether shop mode can be entered."""
        return self._find_adjacent_peaceful_npc(entity_id=SHOPKEEPER_ENTITY_ID)

    def complete_quest(self, quest: Quest, message: str | None = None) -> None:
        """Logs completion and grants quest.reward_item_id if set - the single
        funnel every completion trigger (kill, Talk, dungeon arrival, a
        retroactive questgiver grant) routes through, so reward-granting only
        has to be written once. Never mutates quest.status - that already
        happened inside whichever QuestLog.check_* call produced this quest;
        this is purely "log + reward". Never called for a quest that failed -
        failing a quest never grants a reward."""
        self.message_log.add(message or quest.completion_message)
        if quest.reward_item_id is not None and self.catalog is not None:
            idef = self.catalog.items[quest.reward_item_id]
            reward = item_entity_from_def(idef)
            self.player.inventory.append(reward)
            self.message_log.add(f"You receive a {reward.name}.")
        if quest.reward_shop_discount_pct:
            pct = int(quest.reward_shop_discount_pct * 100)
            self.message_log.add(f"The Millhaven shop now gives you a permanent {pct}% discount.")

    def shop_price(self, item_id: str) -> int:
        """The gold cost to buy item_id right now, after any permanent shop
        discount unlocked by a completed quest (see
        QuestLog.shop_discount_pct). Reused by buy_from_shop (to charge
        correctly) and main.py's shop screen (to display the same
        number)."""
        if self.catalog is None or item_id not in self.catalog.items:
            return 0
        idef = self.catalog.items[item_id]
        discount = self.quest_log.shop_discount_pct()
        return round((idef.cost or 0) * (1 - discount))

    def buy_from_shop(self, item_id: str) -> str:
        """Attempts to buy one item from the shop for the player. Returns
        the status message (also logged to message_log, so it's still
        visible after leaving the shop screen - see main.py's run_shop_mode,
        which doesn't render the message log itself). Never touches
        game_state/clock/enemy turns - buying costs no turn, same reasoning
        as talk_to_adjacent."""
        if self.catalog is None or item_id not in self.catalog.items:
            message = "The shop is unavailable."
            self.message_log.add(message)
            return message
        idef = self.catalog.items[item_id]
        cost = self.shop_price(item_id)
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

    def talk_to_adjacent(self) -> None:
        """Free, non-turn action (see main.py's TalkAction branch): shows an
        adjacent villager's dialogue line, then checks whether talking to
        them grants a questgiver's quest (see QuestLog.check_questgiver),
        completes one that targets them (see QuestLog.check_talked_to), or
        completes a fetch quest they're the questgiver for because the
        player is holding the delivered item (see QuestLog.check_delivery).
        Never touches self.clock or calls _handle_enemy_turns - talking costs
        nothing."""
        target = self._find_adjacent_peaceful_npc()
        if target is None:
            self.message_log.add("There's no one here to talk to.", category="dialogue")
            return
        line = (
            self.quest_log.followup_dialogue(target.entity_id)
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

    def process_turn(self, action: Action) -> None:
        """Resolves a full turn (both phases back to back, no animation gap)
        - what every caller that doesn't care about mid-turn animation
        timing should use (all existing tests, AI-only callers, etc.). See
        main.py's dispatch_action for the animated, two-phase version."""
        if not self.process_player_action(action):
            return
        self.process_enemy_phase()
