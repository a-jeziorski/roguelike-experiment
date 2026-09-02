"""Owns game state and the turn loop. Rendering/windowing is driven from main.py
so Engine itself stays testable without an SDL window."""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from content.schema import (
    AI_AMBUSHER,
    AI_CHARGER,
    AI_ENRAGE,
    AI_HOSTILE_BASIC,
    AI_MIMIC,
    AI_PACK_HUNTER,
    AI_RANGED_BASIC,
    AI_REGENERATOR,
    AI_SCAVENGER,
    AI_SKITTISH,
    AI_SLEEPING_GUARD,
    AI_SPLITTER,
    AI_SUMMONER,
    AI_TERRITORIAL,
    AI_TOWN_GUARD,
    AI_VILLAGER,
    EFFECT_POISON,
    EFFECT_STUN,
    PEACEFUL_AI_TYPES,
    SKILL_COOLDOWN_HOURS,
    SKILL_COOLDOWN_TURNS,
    SKILL_EFFECT_AOE_DAMAGE,
    SKILL_EFFECT_HEAL,
)
from engine.actions import Action, MovementAction
from engine.clock import GameClock
from engine.combat import resolve_attack, resolve_ranged_attack, resolve_skill_damage
from engine.entity import POTION_KINDS, Entity, apply_perk_stat_bonus
from engine.game_map import (
    GameMap,
    apply_dungeon_destruction,
    build_game_map,
    entity_from_def,
    item_entity_from_def,
    nearby_walkable_tiles,
)
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
# AI_PACK_HUNTER/AI_REGENERATOR's own fallbacks - same "omit-friendly"
# convention as above. AI_ENRAGE's equivalents (DEFAULT_ENRAGE_HP_PCT/
# DEFAULT_ENRAGE_ATTACK_BONUS) live in engine/entity.py instead, since
# Entity.effective_attack needs them and can't import this module.
DEFAULT_PACK_RADIUS = 3
DEFAULT_PACK_ATTACK_BONUS = 1
DEFAULT_REGEN_AMOUNT = 2
# AI_CHARGER's own fallbacks - resolved entirely inside Engine._charge, so
# unlike AI_ENRAGE's these can live here rather than in engine/entity.py.
DEFAULT_CHARGE_RANGE = 4
DEFAULT_CHARGE_ATTACK_BONUS = 3
# AI_TERRITORIAL's own fallback - same "omit-friendly" convention as above.
DEFAULT_TERRITORY_RADIUS = 6
# AI_AMBUSHER's own fallback - resolved entirely inside _perform_ai's own
# branch, so (like AI_CHARGER's) this can live here rather than in
# engine/entity.py.
DEFAULT_AMBUSH_BONUS = 5
# AI_SCAVENGER's own fallbacks - resolved entirely inside
# _scavenge_from_death, same "omit-friendly" convention as above.
DEFAULT_SCAVENGE_RADIUS = 5
DEFAULT_SCAVENGE_HEAL_FRACTION = 0.5

# Flat XP awarded for discovering a landmark (see
# Engine._log_newly_seen_tile_announcements) - deliberately small relative
# to a monster kill/quest reward, since a landmark costs the player no
# risk to find, only exploration.
LANDMARK_XP_REWARD = 5

# Flat damage per turn spent standing on any hazardous tile kind (see
# ENVIRONMENTAL_HAZARD_MESSAGES/Engine._apply_environmental_hazard) - set one
# above _advance_world_clock's +1/hour passive heal on purpose, so lingering
# in the open is a small but real net loss (-1 HP/turn) rather than a wash.
# Deliberately not set any higher: at player baseline (30 HP), a net -1/turn
# means even a fairly long, straight-line crossing costs real HP without
# being an automatic death sentence for a fresh, unprepared player. Shared by
# every hazardous kind rather than tuned per-kind - the Northern Steppe's
# corruption is meant to be the same underlying danger as the Scoured
# Reach's wind, just given a different name and story (see
# docs/content_design_process.md §0p).
ENVIRONMENTAL_HAZARD_DAMAGE = 2

# Tile kinds Engine._apply_environmental_hazard punishes for lingering, each
# mapped to the message logged when it fires - one hazard mechanic, several
# flavors. `dunes` is the original (the Scoured Reach); `ashen_plains`/
# `blighted_forest` are the Northern Steppe's corrupted ground, mechanically
# identical, per the user's explicit "reuse the harmful effect... just
# change the text" instruction - see docs/content_design_process.md §0p.
# `scoured_ground` (content/schema.py's TileType, engine/render.py's
# TILE_VISUALS) is the deliberate exception: same ashen-grey look as
# `ashen_plains`, intentionally left out of this dict so it deals no
# damage at all - a place that should read as Northern Steppe corruption
# without punishing the player for standing on it (see
# data/dungeons/visitor_band_ambush, where the encounter itself is
# already the danger).
ENVIRONMENTAL_HAZARD_MESSAGES: dict[str, str] = {
    "dunes": "Wind-driven sand tears at exposed skin and eyes.",
    "ashen_plains": "Ash-choked ground scrapes at exposed skin with every step.",
    "blighted_forest": "Something in the blighted air burns to breathe here.",
}

# Random-encounter chance (Engine._maybe_trigger_visitor_band_encounter)
# checked every turn spent on ashen_plains/blighted_forest - a second, more
# dramatic way the Northern Steppe's corruption stands out from an ordinary
# hazard tile like dunes (the user's own framing), on top of the shared
# chip damage above. Modeled on the same "pull the player off the
# overworld into a dedicated encounter dungeon" shape as goblin_ambush
# (data/encounters.yaml, docs/content_design_process.md §0g) rather than
# spawning monsters directly onto the overworld map - see main.py's
# VISITOR_BAND_AMBUSH_DUNGEON_ID/_redirect_into_visitor_band for the actual
# handoff, and roll_visitor_band below for the random band itself.
# Deliberately NOT extended to dunes: the Scoured Reach isn't the
# Visitor's territory, so nothing in this roster belongs there.
VISITOR_BAND_ENCOUNTER_CHANCE = 0.1
VISITOR_BAND_TILE_KINDS = frozenset({"ashen_plains", "blighted_forest"})

# Row bands within the Northern Steppe cell
# (data/overworld/cells/northern_steppe.lvl) that a rolled band's
# composition escalates across - the same three corruption bands that
# cell's own terrain generation used (docs/region_bibles/northern_steppe.md).
# The Northern Steppe is the assembled overworld's row-0 cell (see
# data/overworld/cells.lvl), so its local y already equals the assembled
# map's global y with no offset - a content-shape assumption, accepted the
# same way ENVIRONMENTAL_HAZARD_MESSAGES already assumes these tile kinds
# only appear on the overworld at all.
HOLLOW_REACH_MAX_Y = 29
CINDER_MARCHES_MAX_Y = 59

# (candidate entity ids, (min band size, max band size)) per corruption
# band, escalating tier to tier - see data/entities.yaml's "The Visitor's
# creations" block for the stats behind each id. excavation_warden is
# deliberately excluded from every band: it's reserved to guard the
# Northern Steppe's Elder Age excavation sites specifically, not a roaming
# random encounter (see that same entities.yaml comment).
FRAYED_EDGE_BAND: tuple[tuple[str, ...], tuple[int, int]] = (("ash_bound_husk", "bound_eye"), (2, 3))
CINDER_MARCHES_BAND: tuple[tuple[str, ...], tuple[int, int]] = (("stitched_vanguard", "hollow_chanter", "bound_crawler"), (2, 3))
HOLLOW_REACH_BAND: tuple[tuple[str, ...], tuple[int, int]] = (("charnel_colossus",), (1, 2))


def roll_visitor_band(y: int) -> list[str]:
    """A random list of Visitor-creation entity ids (data/entities.yaml)
    for a Visitor-band-ambush encounter, tiered by the Northern Steppe row
    `y` falls in (HOLLOW_REACH_MAX_Y/CINDER_MARCHES_MAX_Y above) - always
    at least one id. Called by main.py's _redirect_into_visitor_band at
    the moment the encounter actually fires (using the overworld position
    the player was standing on, not wherever the ambush arena later places
    them), so the composition is freshly randomized every time, never
    reused from a previous fire the way a cached dungeon Engine normally
    would be."""
    if y <= HOLLOW_REACH_MAX_Y:
        candidate_ids, (min_size, max_size) = HOLLOW_REACH_BAND
    elif y <= CINDER_MARCHES_MAX_Y:
        candidate_ids, (min_size, max_size) = CINDER_MARCHES_BAND
    else:
        candidate_ids, (min_size, max_size) = FRAYED_EDGE_BAND
    return [random.choice(candidate_ids) for _ in range(random.randint(min_size, max_size))]

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
    needs to know about .category/.speaker.

    speaker, when set, names who's talking - only ever set on a dialogue
    message (see talk_to_adjacent, the one call site that constructs one),
    whose text already starts with `f"{speaker}: "` by convention. It's a
    separate field rather than something render_message_log parses back out
    of the text, so a display change (highlighting the speaker's name, so
    consecutive lines from different NPCs don't blend together) never
    depends on guessing where a name ends inside free-form dialogue text."""

    category: str
    speaker: str | None

    def __new__(cls, text: str, category: str = "info", speaker: str | None = None) -> "Message":
        obj = str.__new__(cls, text)
        obj.category = category
        obj.speaker = speaker
        return obj


class MessageLog:
    def __init__(self) -> None:
        self.messages: list[Message] = []

    def add(self, text: str, category: str = "info", speaker: str | None = None) -> None:
        self.messages.append(Message(text, category, speaker))


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
        dungeon_ruin_data: dict[str, tuple[str, str, str | None]] | None = None,
        clock: GameClock | None = None,
        quest_log: QuestLog | None = None,
        sprite_codepoints: "SpriteCodepoints | None" = None,
        overworld_return_position: tuple[int, int] | None = None,
        current_level_id: str | None = None,
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
        # dungeon_id -> (ruined_tile, ruined_description, ruined_starting_level),
        # for Engine.destroy_dungeon to apply once a quest's on_fail fires a
        # destroy_dungeon_id consequence (see content.schema.DungeonDef,
        # WorldConsequence). Same "only ever populated for the
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
        # file the outgoing map in the cache below. Defaults to
        # starting_level's own id (true for every ordinary fresh dungeon
        # visit), but callers landing the player somewhere other than the
        # dungeon's nominal starting level - e.g. main.py's
        # resolve_transition entering a razed dungeon's ruins interior
        # instead of its normal starting_level, or engine/save.py's
        # restore_save resuming mid-dungeon - must pass the real one
        # explicitly, since starting_level here is deliberately kept
        # pristine (for Engine.restart() to rebuild from) and would
        # otherwise silently mismatch what game_map actually is.
        self.current_level_id = (
            current_level_id if current_level_id is not None
            else (starting_level.id if starting_level is not None else None)
        )
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
        # Semantic sound-effect keys (e.g. "melee_hit", "pickup_gold" - see
        # data/audio.yaml) queued during the last process_turn()/free-action
        # call - same mailbox pattern as the two event lists above: Engine
        # never reads these back, main.py's play_queued_sounds drains them
        # and hands each key to engine/audio.py's SoundManager. Kept as
        # plain strings, not an enum, so Engine never has to import
        # anything audio-related.
        self.sound_events: list[str] = []
        # Mailbox flags for main.py: Engine only ever sets these to signal "the
        # player wants to leave this dungeon/enter that dungeon" - it never acts
        # on them itself, since it has no access to the dungeon registry or the
        # overworld (only main.py, which owns both, can perform the actual
        # cross-Engine handoff). Same pattern as ranged_attack_events above.
        self.wants_overworld = False
        self.pending_dungeon_entry: str | None = None
        # Same mailbox shape as the two above, set by
        # _maybe_trigger_visitor_band_encounter below - main.py's
        # resolve_transition is the only thing that ever reads or clears it.
        self.wants_visitor_band_encounter = False
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
            self.sound_events.append("player_death")
        else:
            self.message_log.add(f"The {entity.name} dies.", category="combat")
            self.sound_events.append("entity_death")
            if entity in self.game_map.entities:
                self.game_map.entities.remove(entity)
            # A killed villager/guard makes this map's guard hostility
            # permanent (GameMap.guards_hostile never expires it again) -
            # per the design, intimidation earns a cooldown, murder doesn't.
            # Only the player ever attacks a PEACEFUL_AI_TYPES entity today
            # (see engine/combat.py's _apply_damage), so this needs no
            # separate "who killed it" check.
            if entity.ai in PEACEFUL_AI_TYPES:
                self.game_map.mark_peaceful_npc_murdered()
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
            # A cull quest's target species is "cleared" the moment none
            # remain anywhere in this dungeon - checked here (not at
            # report time) since the questgiver is typically reported to
            # from a *different* Engine than the one the kill happened on,
            # which has no visibility into this dungeon's levels. Gated on
            # a live quest actually caring, since the whole-dungeon scan
            # isn't free and every other kill in the game would otherwise
            # trigger it for nothing.
            if any(
                q.target_cull_entity_id == entity.entity_id and q.status in ("not_given", "in_progress")
                for q in self.quest_log.quests.values()
            ):
                if self._entity_type_cleared_from_dungeon(entity.entity_id):
                    self.quest_log.cleared_species_ids.add(entity.entity_id)
            # Same action-triggered-failure timing as the intimidate case
            # above, just with a threshold instead of zero tolerance - see
            # QuestLog.fail_cull_by_preservation_loss.
            for quest, was_in_progress in self.quest_log.fail_cull_by_preservation_loss(entity.entity_id):
                if was_in_progress and quest.failure_message:
                    self.message_log.add(quest.failure_message)
            if entity.xp_reward:
                self._award_xp(entity.xp_reward, "kill")
            self._maybe_drop_loot(entity)
            self._maybe_split(entity)
            self._scavenge_from_death(entity)

    def _scavenge_from_death(self, dead_entity: Entity) -> None:
        """AI_SCAVENGER's whole hook, called once per (non-player) death
        from on_entity_death, after dead_entity has already been removed
        from game_map.entities. Every living scavenger within its own
        scavenge_radius of wherever dead_entity fell heals by its own
        scavenge_heal_fraction of its own max_hp, capped at max_hp - a
        battlefield feeding opportunity that happens to it, not something
        a scavenger goes hunting for on its own (see the AI_SCAVENGER
        branch in _perform_ai, which just chases and attacks normally).
        A peaceful death (a villager/guard) doesn't feed one - same
        PEACEFUL_AI_TYPES exclusion _has_nearby_ally already uses to
        define "ally."
        """
        if dead_entity.ai in PEACEFUL_AI_TYPES:
            return
        for other in self.game_map.entities:
            if other.ai != AI_SCAVENGER or not other.is_alive or other.fighter is None:
                continue
            if other.fighter.hp >= other.fighter.max_hp:
                continue
            radius = other.scavenge_radius or DEFAULT_SCAVENGE_RADIUS
            if max(abs(other.x - dead_entity.x), abs(other.y - dead_entity.y)) > radius:
                continue
            fraction = other.scavenge_heal_fraction or DEFAULT_SCAVENGE_HEAL_FRACTION
            healed = min(math.ceil(other.fighter.max_hp * fraction), other.fighter.max_hp - other.fighter.hp)
            other.fighter.hp += healed
            self.message_log.add(
                f"{other.name} feeds on the fallen {dead_entity.name}, healing {healed} HP.",
                category="combat",
            )

    def _maybe_split(self, entity: Entity) -> None:
        """AI_SPLITTER's whole hook - on death, spawns entity.split_count
        copies of itself at free adjacent tiles (nearby_walkable_tiles,
        radius=1), built fresh from the same EntityDef via entity_from_def
        so a copy carries every field a real spawn would, not a
        hand-maintained duplicate field list. Each copy's max_hp is
        ceil(this entity's own *current* max_hp * split_hp_fraction) -
        this entity's own max_hp, not the catalog base, so an
        elite-scaled splitter (§0w) splits into elite-sized-fraction
        copies too. Spawned copies carry can_split=False so a chain can't
        cascade forever. No-ops if this entity isn't a splitter, can't
        split (a copy of a copy), has nowhere to put a copy (surrounded),
        or self.catalog/its own catalog entry is missing."""
        if (
            entity.split_count is None
            or entity.split_hp_fraction is None
            or not entity.can_split
            or self.catalog is None
            or entity.entity_id not in self.catalog.entities
        ):
            return
        edef = self.catalog.entities[entity.entity_id]
        child_max_hp = max(1, math.ceil(entity.fighter.max_hp * entity.split_hp_fraction))
        spawn_tiles = nearby_walkable_tiles(self.game_map, entity.x, entity.y, entity.split_count, radius=1)
        for x, y in spawn_tiles:
            child = entity_from_def(edef, x, y)
            child.fighter.max_hp = child_max_hp
            child.fighter.hp = child_max_hp
            child.can_split = False
            self.game_map.entities.append(child)
        if spawn_tiles:
            self.message_log.add(f"The {entity.name} splits into {len(spawn_tiles)} more!", category="combat")

    def _maybe_drop_loot(self, entity: Entity) -> None:
        """Rolls entity's own drop_chance (if any) and, on success, places
        one fresh drop_item_id on the ground at entity's last (x, y) - same
        "item_entity_from_def + append to game_map.entities" shape
        build_game_map's own item-spawn loop already uses, so the drop is
        just an ordinary ground item afterward (PickupAction, no special
        handling). No-ops entirely if this entity has no drop configured,
        or self.catalog is None (a synthetic Engine built without a
        catalog, same guard complete_quest's reward_item_id branch uses)."""
        if entity.drop_item_id is None or entity.drop_chance is None or self.catalog is None:
            return
        if random.random() >= entity.drop_chance:
            return
        idef = self.catalog.items[entity.drop_item_id]
        drop = item_entity_from_def(idef, entity.x, entity.y)
        self.game_map.entities.append(drop)
        self.message_log.add(f"The {entity.name} drops a {drop.name}.")

    def _entity_type_cleared_from_dungeon(self, entity_id: str) -> bool:
        """True if no living entity with this catalog id remains anywhere
        in this Engine's dungeon - every level, visited or not. An
        unvisited level's spawns are assumed still alive (they can't have
        been killed without being visited), read from the static
        ParsedLevel content (self.levels), which is always fully known
        regardless of visitation - unlike a live GameMap scan, this never
        needs a hand-authored total that could drift out of sync with the
        level files. False (never cleared) if self.levels is None - this
        Engine isn't a real multi-level dungeon (e.g. the overworld), so
        the check is meaningless there."""
        if self.levels is None:
            return False
        for level_id, level in self.levels.items():
            game_map = self.visited_maps.get(level_id)
            if game_map is not None:
                if any(e.entity_id == entity_id for e in game_map.entities):
                    return False
            elif any(spawn.entity.id == entity_id for spawn in level.entity_spawns):
                return False
        return True

    def _award_xp(self, amount: int, reason: str) -> None:
        """The single funnel every XP source routes through (kills, quest
        completion, landmark discovery) - same reasoning as complete_quest
        being the one funnel for item/gold/discount rewards. An equipped
        xp_gain trinket (see engine/entity.py's Entity.equipped_trinket)
        boosts every source that passes through here alike, not just
        kills - math.ceil so a trinket always grants strictly more, never
        accidentally the same amount at a low xp value (same reasoning as
        combat.py's crit multiplier)."""
        trinket = self.player.equipped_trinket
        if trinket is not None and trinket.item.trinket_effect == "xp_gain":
            amount = math.ceil(amount * (1 + trinket.item.trinket_bonus))
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
        self.wants_visitor_band_encounter = False
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
        # Cache the level we just arrived on immediately, not only once we
        # later leave it (line 376's pre-departure caching) - without this,
        # a cull quest's _entity_type_cleared_from_dungeon would see no
        # cached GameMap for the level the player is *currently standing
        # on* (unless it happens to be the dungeon's original entry level,
        # cached in __init__) and would fall back to this level's static,
        # never-updated entity_spawns - meaning a kill that clears a
        # species entirely on the current level, without ever backing out
        # of it first, wouldn't register as cleared. Harmless to repeat
        # every subsequent visit: it's the same GameMap reference already
        # sitting under this key once cached_map was used above.
        self.visited_maps[self.current_level_id] = self.game_map
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
        self.sound_events = []
        self.wants_overworld = False
        self.pending_dungeon_entry = None
        self.wants_visitor_band_encounter = False
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

        if entity.fighter is not None and EFFECT_STUN in entity.fighter.active_effects:
            self.message_log.add(f"{entity.name} is stunned and can't act.", category="combat")
            self._consume_stun_turn(entity.fighter)
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
            # a guard's hostility is purely the shared map-wide state, not
            # personal injury, since an untouched guard elsewhere on the map
            # still needs to turn hostile the instant anyone provokes the
            # town (see engine/combat.py's _apply_damage). guards_hostile
            # itself is time-limited (GameMap.HOSTILITY_COOLDOWN_DAYS)
            # unless a villager/guard was actually killed here.
            if self.game_map.guards_hostile(self.clock):
                self._chase_and_attack(entity, dx, dy, distance)
            else:
                self._wander(entity)

        elif entity.ai == AI_ENRAGE:
            # Chases and attacks exactly like hostile_basic - the enrage
            # bonus itself is entirely handled by Entity.is_enraged/
            # effective_attack (computed live off current hp), nothing
            # extra to do here beyond the ordinary chase-and-attack.
            self._chase_and_attack(entity, dx, dy, distance)

        elif entity.ai == AI_PACK_HUNTER:
            pack_radius = entity.pack_radius or DEFAULT_PACK_RADIUS
            entity.pack_bonus_active = (
                (entity.pack_attack_bonus or DEFAULT_PACK_ATTACK_BONUS)
                if self._has_nearby_ally(entity, pack_radius)
                else 0
            )
            self._chase_and_attack(entity, dx, dy, distance)

        elif entity.ai == AI_REGENERATOR:
            self._regenerate(entity)
            self._chase_and_attack(entity, dx, dy, distance)

        elif entity.ai == AI_SPLITTER:
            # Chases and attacks exactly like hostile_basic - splitting
            # itself is a death trigger (_maybe_split, on_entity_death),
            # not a turn-by-turn behavior, so there's nothing extra to do
            # on an ordinary turn.
            self._chase_and_attack(entity, dx, dy, distance)

        elif entity.ai == AI_MIMIC:
            if entity.just_revealed:
                # Already landed its one attack this turn via PickupAction's
                # reveal (see engine/actions.py) - skip the ordinary chase/
                # attack so it doesn't also get an unrelated second hit in
                # the very same turn it was revealed.
                entity.just_revealed = False
            elif entity.mimicking:
                pass  # stays disguised and motionless until picked at
            else:
                self._chase_and_attack(entity, dx, dy, distance)

        elif entity.ai == AI_SCAVENGER:
            # Chases and attacks exactly like hostile_basic - feeding off a
            # nearby ally's death is a death-triggered event
            # (_scavenge_from_death, on_entity_death), not a turn-by-turn
            # behavior, so there's nothing extra to do on an ordinary turn.
            self._chase_and_attack(entity, dx, dy, distance)

        elif entity.ai == AI_SUMMONER:
            # A summon attempt spends the whole turn - channeling a
            # reinforcement instead of also swinging a weapon - so
            # chase_and_attack only runs when this turn wasn't spent
            # summoning (_maybe_summon returns False while its own
            # cooldown hasn't reached 0 yet).
            if not self._maybe_summon(entity):
                self._chase_and_attack(entity, dx, dy, distance)

        elif entity.ai == AI_CHARGER:
            if entity.charge_recovering:
                # Skips its action entirely for exactly one turn, the
                # same "block, don't chase/attack" shape a stunned
                # entity's own turn already takes (§0t) - the cost for
                # a charge that actually landed last turn.
                entity.charge_recovering = False
                self.message_log.add(f"{entity.name} is recovering from the charge.", category="combat")
            elif (
                distance > 1
                and distance <= (entity.charge_range or DEFAULT_CHARGE_RANGE)
                and (dx == 0 or dy == 0 or abs(dx) == abs(dy))
            ):
                self._charge(entity, dx, dy, distance)
            else:
                self._chase_and_attack(entity, dx, dy, distance)

        elif entity.ai == AI_TERRITORIAL:
            radius = entity.territory_radius or DEFAULT_TERRITORY_RADIUS
            home_distance = max(abs(entity.x - entity.home_x), abs(entity.y - entity.home_y))
            # Already adjacent always fights back, regardless of how far
            # from home that is - a territorial creature doesn't refuse an
            # attack already landing on it. Otherwise, once it's reached
            # the edge of its own territory, it breaks off and heads back
            # instead of taking one more step outward, even if the player
            # is still visible and still running.
            if distance <= 1 or home_distance < radius:
                self._chase_and_attack(entity, dx, dy, distance)
            else:
                self._return_home(entity)

        elif entity.ai == AI_AMBUSHER:
            if not entity.hidden:
                self._chase_and_attack(entity, dx, dy, distance)
            elif distance <= 1:
                # The reveal moment - cleared for good, never re-hides.
                # entity.hidden being checked by render.py/targeting.py is
                # the entire "invisible until now" illusion; from here on
                # it's an ordinary visible monster.
                entity.hidden = False
                bonus = entity.ambush_bonus or DEFAULT_AMBUSH_BONUS
                self.message_log.add(f"{entity.name} bursts from hiding!", category="combat")
                resolve_skill_damage(self, entity, self.player, entity.effective_attack + bonus, "ambushes")
            # else: stays hidden and motionless - an ambusher that hasn't
            # been reached yet takes no action at all, not even a single
            # step toward the player, which would defeat "lying in wait."

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

    def _return_home(self, entity: Entity) -> None:
        """AI_TERRITORIAL's disengage step - walks one tile back toward
        (home_x, home_y), the same direct step_x/step_y shape _flee/
        _chase_and_attack already use. A no-op once actually home (holds
        position rather than jittering in place) - there's no "resume
        guarding" behavior beyond that; it simply waits there until the
        player comes back within territory_radius."""
        if (entity.x, entity.y) == (entity.home_x, entity.home_y):
            return
        dx = entity.home_x - entity.x
        dy = entity.home_y - entity.y
        step_x = (dx > 0) - (dx < 0)
        step_y = (dy > 0) - (dy < 0)
        MovementAction(step_x, step_y).perform(self, entity)

    def _wander(self, entity: Entity) -> None:
        """Idle movement untargeted at the player - "going about their
        business." Picks a random adjacent tile or holds position;
        MovementAction already no-ops safely if the destination is blocked
        or occupied, the same free behavior _flee relies on."""
        step_x, step_y = random.choice(_WANDER_MOVES)
        MovementAction(step_x, step_y).perform(self, entity)

    def _has_nearby_ally(self, entity: Entity, radius: int) -> bool:
        """True if another living, hostile (non-peaceful) monster is
        within radius tiles of entity - AI_PACK_HUNTER's trigger
        condition (see _perform_ai's AI_PACK_HUNTER branch). A peaceful
        entity (villager/town_guard) never counts as a pack hunter's ally,
        same PEACEFUL_AI_TYPES exclusion combat.py already uses elsewhere."""
        for other in self.game_map.entities:
            if other is entity or other is self.player or not other.is_alive:
                continue
            if other.ai is None or other.ai in PEACEFUL_AI_TYPES:
                continue
            if max(abs(other.x - entity.x), abs(other.y - entity.y)) <= radius:
                return True
        return False

    def _regenerate(self, entity: Entity) -> None:
        """Heals entity by its regen_amount (DEFAULT_REGEN_AMOUNT if
        unset), capped at max_hp - AI_REGENERATOR's whole hook. Runs every
        turn this entity acts, combat or not, by design: the player has to
        out-damage the regen to make progress, not just eventually finish
        it off given enough turns."""
        if entity.fighter is None or entity.fighter.hp >= entity.fighter.max_hp:
            return
        amount = entity.regen_amount or DEFAULT_REGEN_AMOUNT
        healed = min(amount, entity.fighter.max_hp - entity.fighter.hp)
        entity.fighter.hp += healed
        self.message_log.add(f"{entity.name} regenerates {healed} HP.", category="combat")

    def _maybe_summon(self, entity: Entity) -> bool:
        """AI_SUMMONER's whole hook, called from _perform_ai's own branch.
        Returns True if this turn was spent summoning (the caller skips
        its own chase_and_attack that turn), False if it wasn't time yet
        or nothing could be summoned (caller falls through to an ordinary
        chase_and_attack instead). entity.summon_cooldown counts down to
        the next attempt; reaching 0 triggers one and resets it to
        summon_interval, whether or not that attempt actually succeeds -
        a summoner blocked by its own summon_max_active cap, or with
        nowhere free to put a summon, tries again after another full
        interval, not on the very next turn.

        entity.summoned_children tracks this specific summoner's own
        still-living summons (pruned of dead ones here) - the cap is per
        summoner, not a global count of every copy of summon_entity_id
        anywhere on the map, so two summoners of the same kind don't
        starve each other's caps."""
        if (
            entity.summon_entity_id is None
            or self.catalog is None
            or entity.summon_entity_id not in self.catalog.entities
        ):
            return False
        if entity.summon_cooldown > 0:
            entity.summon_cooldown -= 1
            return False
        entity.summon_cooldown = entity.summon_interval
        entity.summoned_children = [c for c in entity.summoned_children if c.is_alive]
        if entity.summon_max_active is not None and len(entity.summoned_children) >= entity.summon_max_active:
            return False
        spawn_tiles = nearby_walkable_tiles(self.game_map, entity.x, entity.y, 1, radius=1)
        if not spawn_tiles:
            return False
        edef = self.catalog.entities[entity.summon_entity_id]
        x, y = spawn_tiles[0]
        child = entity_from_def(edef, x, y)
        self.game_map.entities.append(child)
        entity.summoned_children.append(child)
        self.message_log.add(f"{entity.name} summons a {child.name}!", category="combat")
        return True

    def _charge(self, entity: Entity, dx: int, dy: int, distance: int) -> None:
        """AI_CHARGER's whole hook, called from _perform_ai's own branch
        only when the player is aligned in a straight line (orthogonal or
        exact diagonal) within charge_range and farther than one tile
        away. Covers up to charge_range tiles toward the player in this
        one turn - one MovementAction step at a time, stopping early (no
        attack, no recovery) the moment a step doesn't actually move it,
        the same way an ordinary blocked step already no-ops safely.

        Reaching adjacent resolves one attack immediately, with
        charge_attack_bonus added on top of effective_attack via
        resolve_skill_damage (the same flat-damage-value pipeline
        Ground Pound uses, §0z) rather than temporarily mutating
        fighter.attack - then sets charge_recovering so next turn is
        spent winded instead of acting at all. A charge that gets blocked
        partway and never reaches adjacent costs nothing extra: it simply
        closed some distance, the same as a failed lunge would in
        practice, not a punishable mistake."""
        step_x = (dx > 0) - (dx < 0)
        step_y = (dy > 0) - (dy < 0)
        steps = min(distance - 1, entity.charge_range or DEFAULT_CHARGE_RANGE)
        for _ in range(steps):
            before = (entity.x, entity.y)
            MovementAction(step_x, step_y).perform(self, entity)
            if (entity.x, entity.y) == before:
                return
        if max(abs(self.player.x - entity.x), abs(self.player.y - entity.y)) > 1:
            return
        bonus = entity.charge_attack_bonus or DEFAULT_CHARGE_ATTACK_BONUS
        resolve_skill_damage(self, entity, self.player, entity.effective_attack + bonus, "charges into")
        entity.charge_recovering = True

    def _handle_enemy_turns(self) -> None:
        for entity in list(self.game_map.entities):
            if entity is self.player or not entity.is_alive or entity.ai is None:
                continue
            self._perform_ai(entity)

    def _apply_environmental_hazard(self) -> None:
        """Chip damage for ending a turn standing on a hazardous tile kind
        (see ENVIRONMENTAL_HAZARD_MESSAGES above, content/schema.py's
        TileType, docs/content_design_process.md §0p) - the Scoured Reach's
        and the Northern Steppe's whole reason nobody's settled them. Player
        only: whatever wildlife lives out there is already adapted to it,
        the same reasoning skittish/hostile monsters never flee a terrain
        hazard the player would. ENVIRONMENTAL_HAZARD_DAMAGE deliberately
        outpaces _advance_world_clock's +1/hour passive heal (this runs
        first, same turn) - standing still in the open is meant to be a
        losing trade, not a wash. Runs regardless of is_overworld's
        dungeon/settlement gate on the clock/heal below: these kinds only
        ever appear on the overworld map today, but the check is by tile
        kind, not location, so it needs no special-casing if that ever
        changes."""
        message = ENVIRONMENTAL_HAZARD_MESSAGES.get(self.game_map.kinds[self.player.x, self.player.y])
        if message is None:
            return
        self.player.fighter.hp -= ENVIRONMENTAL_HAZARD_DAMAGE
        self.message_log.add(message, category="combat")

    def _maybe_trigger_visitor_band_encounter(self) -> None:
        """A chance, each turn spent on Northern Steppe corruption
        (VISITOR_BAND_TILE_KINDS above), to pull the player off the
        overworld into a Visitor-band ambush - modeled on goblin_ambush
        (data/encounters.yaml, docs/content_design_process.md §0g), not a
        monster-spawn effect this Engine can perform itself. Only sets the
        wants_visitor_band_encounter mailbox flag (same pattern as
        wants_overworld/pending_dungeon_entry above) for main.py's
        resolve_transition to act on - this Engine has no access to the
        dungeon registry needed to actually build the ambush. Checked only
        on the overworld, mirroring _due_encounter's own is_overworld gate
        in main.py, since this drives the same kind of cross-Engine
        handoff."""
        if not self.is_overworld:
            return
        if self.game_map.kinds[self.player.x, self.player.y] not in VISITOR_BAND_TILE_KINDS:
            return
        if random.random() >= VISITOR_BAND_ENCOUNTER_CHANCE:
            return
        self.wants_visitor_band_encounter = True

    def _tick_active_effects(self) -> None:
        """Ticks every active poison/weaken affliction on every entity
        (player or monster) once - refresh semantics, no stacking, and
        different kinds on the same entity tick independently of each
        other (see Fighter.active_effects, engine/combat.py's
        _apply_damage). Runs once per process_enemy_phase call, strictly
        after both process_player_action (earlier this turn) and
        _handle_enemy_turns (just above) have resolved - so an entity
        afflicted for the first time this turn, by either side, still
        takes its first tick immediately: inflicts_duration=N means N
        total ticks, the first landing the same turn as the hit, not the
        turn after.

        Only poison does anything ON the tick itself (damage); weaken is
        purely passive while active (reducing effective_attack -
        Entity._weaken_penalty) - this method's only job for it is
        counting turns_remaining down and removing it once it expires
        (see ActiveEffect's own docstring on why expiry means key
        removal, not a value left at 0).

        Deliberately excludes EFFECT_STUN entirely - see
        _consume_stun_turn's own docstring for why stun is decremented at
        the moment process_player_action/_perform_ai actually block that
        entity's turn, not here. Ticking it here too would double-decrement
        it (once here, once at the block site) and, worse, could expire a
        duration=1 stun in the very turn it was inflicted - before the
        afflicted entity ever gets a turn to actually be blocked on.

        Snapshots game_map.entities fresh each call, same reasoning the
        poison-only version of this method already established: anything
        that died earlier this same turn via combat.py's own direct
        on_entity_death call is already gone (monster: already removed
        from game_map.entities; player: already caught by
        process_enemy_phase's own "if game_state == playing" guard around
        this call), so on_entity_death can never double-fire for the same
        death in one turn - don't hoist this snapshot earlier without
        re-checking that invariant."""
        for entity in list(self.game_map.entities):
            if entity.fighter is None or not entity.fighter.active_effects:
                continue
            expired_kinds = []
            for kind, effect in entity.fighter.active_effects.items():
                if kind == EFFECT_STUN:
                    continue
                if kind == EFFECT_POISON:
                    entity.fighter.hp -= effect.potency
                    self.message_log.add(
                        f"{entity.name} writhes from poison, taking {effect.potency} damage.",
                        category="combat",
                    )
                effect.turns_remaining -= 1
                if effect.turns_remaining <= 0:
                    expired_kinds.append(kind)
            for kind in expired_kinds:
                del entity.fighter.active_effects[kind]
            if entity.fighter.hp <= 0:
                self.on_entity_death(entity)

    def _tick_skill_cooldowns(self, kind: str) -> None:
        """Decrements every active-skill cooldown of the given kind
        ("turns" or "hours", see PerkDef.skill_cooldown_kind) on the
        player by 1. "turns" is called once per turn from
        process_enemy_phase, any turn anywhere (dungeon or overworld);
        "hours" is called only from _advance_world_clock (overworld turns
        only) - a skill on an hour-based cooldown is meant to genuinely
        require leaving to rest, not just taking more turns wherever the
        player already is. Entries reaching 0 are deleted outright, not
        left inert at 0 - same "membership is the state" convention
        Fighter.active_effects/_tick_active_effects already established."""
        if self.catalog is None:
            return
        expired_ids = []
        for perk_id, remaining in self.player.skill_cooldowns.items():
            perk = self.catalog.perks.get(perk_id)
            if perk is None or perk.skill_cooldown_kind != kind:
                continue
            remaining -= 1
            if remaining <= 0:
                expired_ids.append(perk_id)
            else:
                self.player.skill_cooldowns[perk_id] = remaining
        for perk_id in expired_ids:
            del self.player.skill_cooldowns[perk_id]

    def _tick_water_walking(self) -> None:
        """Counts down Entity.water_walking_turns_remaining by 1, same
        "any turn anywhere" cadence as _tick_skill_cooldowns(SKILL_COOLDOWN_TURNS) -
        called alongside it from process_enemy_phase, not gated to
        is_overworld, so a buff spent crossing dungeon water also burns
        down if the player then leaves to the surface."""
        if self.player.water_walking_turns_remaining > 0:
            self.player.water_walking_turns_remaining -= 1

    def _advance_world_clock(self) -> None:
        """The only source of in-game time passing: one hour per turn taken
        on the overworld (dungeons/settlements never call this - is_overworld
        is False for all of them, including Millhaven/Wayford). Passive
        healing is the sole current effect of time passing; future effects
        can hang off self.clock without changing this method's shape."""
        self.clock.advance_hour()
        self._tick_skill_cooldowns(SKILL_COOLDOWN_HOURS)
        fighter = self.player.fighter
        fighter.hp = min(fighter.max_hp, fighter.hp + 1)

    def _check_quest_deadlines(self) -> None:
        """Sibling to _advance_world_clock, called the same turn: any
        not_given/in_progress quest whose deadline the clock just crossed
        gets failed here. A separate method (not folded into
        _advance_world_clock) so deadline logic is testable independent of
        clock/healing mechanics. Only ever called while self.is_overworld
        (see the one call site in process_turn) - a newly-failed quest's
        on_fail entries are safe to act on immediately, since self.game_map
        is guaranteed to be the overworld's own map here.

        on_fail consequences (e.g. spreading_the_warning razing Wayford)
        always apply, regardless of was_in_progress - the world doesn't
        wait for the player to have taken the quest. failure_message is
        only logged when was_in_progress, same "never announce the failure
        of a quest the player never received" rule destroy_dungeon (below)
        already follows via QuestLog.void_by_dungeon."""
        for quest, was_in_progress in self.quest_log.check_deadlines(self.clock):
            if was_in_progress:
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
        ruined_tile, ruined_description, ruined_starting_level = ruin_data
        apply_dungeon_destruction(
            self.game_map, dungeon_id, ruined_tile, ruined_description, ruined_starting_level,
        )
        self.quest_log.destroyed_dungeon_ids.add(dungeon_id)
        for quest, was_in_progress in self.quest_log.void_by_dungeon(dungeon_id):
            if was_in_progress and quest.failure_message:
                self.message_log.add(quest.failure_message)

    def _is_currently_peaceful(self, entity: Entity) -> bool:
        """Whether `entity` is still meaningfully peaceful right now - a
        villager already hurt (fleeing) or a town guard while
        GameMap.guards_hostile is True are no longer peaceful in any real
        sense, even though their catalog ai type is still one of
        PEACEFUL_AI_TYPES. Shared by _find_adjacent_peaceful_npc (is this
        NPC currently talkable/tradeable) and would_attack_peaceful_npc
        (does bumping this NPC need a deliberate confirmation instead of
        attacking outright).

        A villager that's been hurt is excluded - per _perform_ai's own
        AI_VILLAGER branch, any damage at all makes a villager flee
        permanently (nothing ever heals a non-player entity, so hp <
        max_hp is a stable "currently fleeing" flag, not a fleeting one).
        A town guard's hostility is map-wide and time-limited rather than
        personal, so it's excluded exactly while guards_hostile(self.clock)
        is True even if this specific guard is undamaged - villagers are
        NOT affected by that state (only their own hp matters to them);
        that asymmetry is intentional, not a leak. Once
        guards_hostile's cooldown lapses (no murder on this map), a town
        guard reverts to peaceful/talkable here too, same as any other
        settlement NPC."""
        if entity.ai not in PEACEFUL_AI_TYPES:
            return False
        if entity.ai == AI_TOWN_GUARD and self.game_map.guards_hostile(self.clock):
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
        self.sound_events.append("shop_buy")
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
        if perk.requires_perk_id is not None and perk.requires_perk_id not in self.player.learned_perk_ids:
            prereq_name = self.catalog.perks[perk.requires_perk_id].name
            message = f"You need to learn {prereq_name} first."
            self.message_log.add(message)
            return message
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
        # A freshly learned active-skill perk auto-slots into the first
        # empty hotbar slot, same "learn it, it just works" experience the
        # old hardcoded W/K bindings gave for free - still reassignable
        # afterward via assign_skill_slot (see run_character_mode). No-ops
        # if every slot is already full (nothing to do until the player
        # frees one themselves).
        if perk.skill_effect is not None and perk_id not in self.player.skill_slots:
            if None in self.player.skill_slots:
                self.assign_skill_slot(self.player.skill_slots.index(None), perk_id)
        message = f"You learn {perk.name}."
        self.message_log.add(message)
        self.sound_events.append("perk_learn")
        return message

    def use_skill(self, entity: Entity, perk_id: str) -> str:
        """Manually triggers a learned active-skill perk (see
        engine/actions.py's UseSkillAction, which reaches this exactly the
        way UseItemAction reaches its own inline logic - through the
        normal process_player_action path, so this costs a turn like any
        other real action, unlike learn_perk/buy_from_shop above). Returns
        the status message (also logged), matching those two methods' own
        "return + log" convention."""
        if self.catalog is None or perk_id not in self.catalog.perks:
            message = "That skill doesn't exist."
            self.message_log.add(message)
            return message
        perk = self.catalog.perks[perk_id]
        if perk.skill_effect is None or perk_id not in entity.learned_perk_ids:
            message = "You don't know that skill."
            self.message_log.add(message)
            return message
        if entity.skill_cooldowns.get(perk_id, 0) > 0:
            message = f"{perk.name} is still on cooldown."
            self.message_log.add(message)
            return message

        entity.skill_cooldowns[perk_id] = perk.skill_cooldown_amount

        if perk.skill_effect == SKILL_EFFECT_HEAL:
            fighter = entity.fighter
            healed = min(fighter.max_hp - fighter.hp, math.ceil(fighter.max_hp * perk.skill_heal_pct))
            fighter.hp += healed
            message = f"You use {perk.name} and recover {healed} HP."
            self.message_log.add(message)
            return message

        # SKILL_EFFECT_AOE_DAMAGE - strikes every hostile entity adjacent
        # to entity (8-directional), reusing the full combat resolution
        # pipeline per target (resolve_skill_damage -> _apply_damage), so
        # dodge/crit/weapon-affix procs and on_entity_death all apply
        # exactly as they would for an ordinary attack - not a special
        # case to avoid, a nice emergent synergy with whatever's equipped.
        message = f"You use {perk.name}!"
        self.message_log.add(message)
        # fighter is not None already excludes every item entity (no item
        # ever has a Fighter) - an extra "ai is not None" check would be
        # redundant for that and wrong besides, since a real monster's own
        # ai is never actually None in shipped content.
        targets = [
            e for e in list(self.game_map.entities)
            if e is not entity and e.fighter is not None and e.is_alive
            and e.ai not in PEACEFUL_AI_TYPES
            and max(abs(e.x - entity.x), abs(e.y - entity.y)) <= 1
        ]
        for target in targets:
            resolve_skill_damage(self, entity, target, perk.skill_aoe_damage, "pounds")
        return message

    def assign_skill_slot(self, slot_index: int, perk_id: str | None) -> str:
        """Free, non-turn mutation (see main.py's CharacterAction/
        run_character_mode, tools/play_llm.py's bind_skill command) - the
        single validated path either front end uses to change
        player.skill_slots. perk_id must be a known, learned,
        skill_effect-bearing perk, or None to clear the slot. If perk_id is
        already sitting in a *different* slot, that slot is cleared first
        (moved, not duplicated) - the one rule that keeps a hotbar with
        more slots than skills unambiguous. Also called once, automatically,
        by learn_perk the moment a new skill perk is learned (auto-slotting
        into the first empty slot) - this is the same method either path
        uses, so validation/move-not-duplicate behavior can't drift between
        them. Returns the status message (also logged), matching
        learn_perk's own "return + log" convention."""
        if not (0 <= slot_index < len(self.player.skill_slots)):
            message = "Invalid skill slot."
            self.message_log.add(message)
            return message
        if perk_id is not None:
            perk = self.catalog.perks.get(perk_id) if self.catalog else None
            if (
                perk is None
                or perk.skill_effect is None
                or perk_id not in self.player.learned_perk_ids
            ):
                message = "That's not a skill you've learned."
                self.message_log.add(message)
                return message
            for i, existing in enumerate(self.player.skill_slots):
                if existing == perk_id:
                    self.player.skill_slots[i] = None
        self.player.skill_slots[slot_index] = perk_id
        name = self.catalog.perks[perk_id].name if perk_id and self.catalog else "(empty)"
        message = f"Skill slot {slot_index + 1}: {name}."
        self.message_log.add(message)
        return message

    def assign_potion_slot(self, slot_index: int, kind: str | None) -> str:
        """assign_skill_slot's exact shape, for player.potion_slots/
        POTION_KINDS instead of skill_slots/learned perks - see main.py's
        CharacterAction/run_character_mode, tools/play_llm.py's
        bind_potion command."""
        if not (0 <= slot_index < len(self.player.potion_slots)):
            message = "Invalid potion slot."
            self.message_log.add(message)
            return message
        if kind is not None and kind not in POTION_KINDS:
            message = "That's not a potion kind."
            self.message_log.add(message)
            return message
        if kind is not None:
            for i, existing in enumerate(self.player.potion_slots):
                if existing == kind:
                    self.player.potion_slots[i] = None
        self.player.potion_slots[slot_index] = kind
        message = f"Potion slot {slot_index + 1}: {kind or '(empty)'}."
        self.message_log.add(message)
        return message

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
        recorded intimidated (see QuestLog.check_intimidate_report), or
        completes a cull quest they're the questgiver for because its
        target species has already been recorded cleared (see
        QuestLog.check_cull_report). Reads self.clock (only to gate a
        not-yet-available quest in check_questgiver) but never advances
        it, and never calls _handle_enemy_turns - talking costs nothing."""
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
        self.message_log.add(f'{target.name}: "{line}"', category="dialogue", speaker=target.name)

        for quest in self.quest_log.check_questgiver(target.entity_id, self.clock):
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

        for quest in self.quest_log.check_cull_report(target.entity_id):
            self.complete_quest(quest)

    def _consume_stun_turn(self, fighter: "Fighter") -> None:
        """Decrements a blocked turn off an active stun and removes it once
        exhausted - called from process_player_action/_perform_ai exactly
        when the block actually takes effect, deliberately NOT from
        _tick_active_effects. Poison/weaken tick in that shared end-of-turn
        sweep because their own effect (damage / a passive stat penalty)
        *is* the tick; stun's effect (blocking an action) happens earlier
        in the turn sequence, at the moment process_player_action/_perform_ai
        are about to run this same entity's turn - decrementing it there
        instead is what makes duration=1 block exactly the entity's next
        turn, rather than expiring in the same tick sweep that runs on the
        very turn it was inflicted, before that entity ever got a turn to
        actually be blocked on."""
        effect = fighter.active_effects[EFFECT_STUN]
        effect.turns_remaining -= 1
        if effect.turns_remaining <= 0:
            del fighter.active_effects[EFFECT_STUN]

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
        staleness during that in-between animation. A stunned player still
        "acts" in the sense that a turn passes (returns True, so
        process_enemy_phase still runs - the world doesn't pause just
        because the player can't) - only action.perform() itself is
        skipped, matching _perform_ai's own stun check for a monster's
        turn. Free/non-turn actions (Look, Talk, the shop/quest-log
        screens, ...) never reach this method at all - main.py's dispatch
        intercepts them before dispatch_action, so stun correctly never
        blocks any of those, only real turn-costing actions."""
        if self.game_state != "playing":
            return False
        if EFFECT_STUN in self.player.fighter.active_effects:
            self.message_log.add("You are stunned and can't act!", category="combat")
            self._consume_stun_turn(self.player.fighter)
            return True
        action.perform(self, self.player)
        return True

    def process_enemy_phase(self) -> None:
        """The second half of a turn: enemy AI turns, environmental hazard
        damage, a chance to arm a Visitor band ambush, player-death
        bookkeeping, world clock/quest deadlines, and the FOV update - see
        process_player_action's docstring for why this is split out.
        Guarded the same way process_turn's tail always was: each step
        only runs if the game is still "playing" going into it."""
        if self.game_state == "playing":
            self._handle_enemy_turns()

        if self.game_state == "playing":
            self._apply_environmental_hazard()

        if self.game_state == "playing" and self.player.is_alive:
            self._maybe_trigger_visitor_band_encounter()

        if self.game_state == "playing":
            self._tick_active_effects()

        if self.game_state == "playing":
            self._tick_skill_cooldowns(SKILL_COOLDOWN_TURNS)

        if self.game_state == "playing":
            self._tick_water_walking()

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
