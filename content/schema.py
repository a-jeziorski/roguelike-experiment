"""Pydantic models for hand-authored content: monster/item catalogs and level files.

These models describe the *raw* shape of the YAML files as a human would write them.
Cross-referential checks (does this entity id exist in the catalog, is there exactly
one player start, etc.) happen in loader.py, since they require the catalog and the
level to be considered together.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

TileType = Literal[
    "wall", "floor", "stairs_down", "stairs_up", "player_start", "door",
    "dungeon_entrance", "mountain", "sea", "forest", "road", "plains", "town",
    "landmark", "dunes",
]

# kind -> (walkable, transparent). Anything not listed defaults to (True, True) -
# ordinary open ground - which is why every walkable kind (floor, stairs,
# dungeon_entrance, road/plains/town/sea's line-of-sight, landmark...) needs no
# entry here unless it's actually impassable and/or opaque. Lives here (rather
# than in engine/game_map.py, which uses it for real walkability/rendering)
# so content/loader.py can also import it for design-time validation - e.g.
# checking a locked door actually encloses what it's meant to guard - without
# a circular import (engine.game_map itself imports content.loader).
TILE_PASSABILITY: dict[str, tuple[bool, bool]] = {
    "wall": (False, False),
    "door": (False, False),  # closed; unlock_door() overrides both to True at runtime
    "mountain": (False, False),
    "sea": (False, True),  # can't cross it, but can see across it
    "forest": (True, False),  # can walk through, can't see far through/across it
    # dunes deliberately has no entry here - it's a chip-damage hazard (see
    # Engine._apply_environmental_hazard), not a movement/sight obstruction,
    # so it falls through to the default (True, True), same as plains. The
    # danger is standing on it, not crossing it.
}

Color = tuple[int, int, int]

# Known monster AI behaviors. Defined once here (rather than a bare str on
# EntityDef) so an unrecognized value fails loudly at content-load time
# instead of silently producing a monster that never acts; engine/engine.py
# imports these same constants for its dispatch, so validation and dispatch
# can't drift out of sync.
AI_HOSTILE_BASIC = "hostile_basic"
AI_SLEEPING_GUARD = "sleeping_guard"
AI_SKITTISH = "skittish"
AI_RANGED_BASIC = "ranged_basic"
AI_VILLAGER = "villager"
AI_TOWN_GUARD = "town_guard"
AIType = Literal[
    AI_HOSTILE_BASIC, AI_SLEEPING_GUARD, AI_SKITTISH, AI_RANGED_BASIC, AI_VILLAGER, AI_TOWN_GUARD,
]
# AI types that never initiate violence on their own - villager never fights
# back at all; town_guard doesn't either, until the map-wide, time-limited
# hostility state flips (see GameMap.guards_hostile / Engine._perform_ai's
# AI_TOWN_GUARD branch). Shared here since both engine/combat.py (the
# trigger) and engine/engine.py (dispatch + adjacency filtering) need it.
PEACEFUL_AI_TYPES = (AI_VILLAGER, AI_TOWN_GUARD)

# A quest's lifecycle - lives here (rather than engine/quest.py) for the same
# reason AIType does: engine/quest.py's QuestDef.starting_status and its
# runtime Quest.status both need it, and content/schema.py must never depend
# on engine/*.
QuestStatus = Literal["not_given", "in_progress", "completed", "failed"]


class EntityDef(BaseModel):
    """A monster type, as defined once in data/entities.yaml and referenced by id
    from level files."""

    id: str
    name: str
    glyph: str
    color: Color
    hp: int = Field(gt=0)
    attack: int = Field(ge=0)
    defense: int = Field(ge=0)
    ai: AIType = AI_HOSTILE_BASIC
    # Only meaningful for the AI type that uses them (sleeping_guard /
    # skittish / ranged_basic respectively); engine-level defaults apply
    # when omitted.
    alert_radius: int | None = Field(default=None, gt=0)
    flee_hp_pct: float | None = Field(default=None, gt=0, le=1)
    ranged_range: int | None = Field(default=None, gt=0)
    # Only meaningful for AI_VILLAGER - holds position instead of wandering
    # while undamaged (still flees normally once hurt, unchanged). Plain
    # bool, not the nullable-with-engine-fallback shape above, since there's
    # no "default stationary radius" concept - it's just on or off.
    stationary: bool = False
    description: str = ""
    # Fallback line the Talk action shows for a spawn of this type with no
    # per-spawn dialogue override (see LegendEntry.dialogue below) - only
    # meaningful for AI_VILLAGER entities today, but not restricted to them.
    dialogue: str = ""
    # Catalog item ids this entity sells, if any - empty means "not a
    # shopkeeper." Any entity with a non-empty shop_inventory is reachable
    # via Engine.adjacent_shopkeeper regardless of its catalog id, so a new
    # town can define its own shopkeeper NPC (its own EntityDef, its own
    # stock) without any engine change. Only meaningful on a
    # PEACEFUL_AI_TYPES entity (villager/town_guard) - content/loader.py's
    # load_catalog rejects it otherwise, since such an entity can never
    # actually be traded with.
    shop_inventory: list[str] = Field(default_factory=list)
    # XP granted to the player when this entity dies (see
    # Engine.on_entity_death) - 0 means no reward. Only meaningful for a
    # hostile entity: content/loader.py's load_catalog rejects a nonzero
    # value on a PEACEFUL_AI_TYPES entity, since a player could otherwise
    # farm XP by killing villagers.
    xp_reward: int = Field(default=0, ge=0)
    # Catalog perk ids this entity teaches, if any - empty means "not a
    # trainer," same shape/reasoning as shop_inventory above (reachable via
    # Engine.adjacent_trainer regardless of catalog id; only meaningful on
    # a PEACEFUL_AI_TYPES entity, enforced the same way as shop_inventory).
    trainer_perks: list[str] = Field(default_factory=list)
    # A landed hit (damage > 0 after defense) from this entity afflicts the
    # defender with "poisoned": poison_potency damage per turn for
    # poison_duration turns, refreshing rather than stacking on a repeat
    # hit (see engine/combat.py's _apply_damage, engine/engine.py's
    # _apply_poison_damage). None (the default) means this entity's
    # attacks never poison anyone.
    poison_potency: int | None = Field(default=None, gt=0)
    poison_duration: int | None = Field(default=None, gt=0)

    @field_validator("glyph")
    @classmethod
    def glyph_is_single_char(cls, v: str) -> str:
        if len(v) != 1:
            raise ValueError(f"glyph must be a single character, got {v!r}")
        return v

    @model_validator(mode="after")
    def poison_potency_and_duration_both_or_neither(self) -> "EntityDef":
        if (self.poison_potency is None) != (self.poison_duration is None):
            raise ValueError("poison_potency and poison_duration must be set together or not at all")
        return self


class ItemDef(BaseModel):
    """An item type, as defined once in data/items.yaml and referenced by id from
    level files."""

    id: str
    name: str
    glyph: str
    color: Color
    heal_amount: int | None = None
    # Gold collected straight into the player's gold stat on pickup (see
    # PickupAction._collect_gold) - never enters inventory. Don't set
    # reward_item_id (QuestDef, engine/quest.py) to a gold-amount item as a
    # way to reward gold from a quest - that path appends straight into
    # player.inventory via Engine.complete_quest, bypassing
    # PickupAction._collect_gold entirely, so the "coin" would just sit
    # there inert instead of incrementing player.gold. Use
    # QuestDef.reward_gold_amount instead - the actual, correct mechanism
    # for a quest to reward gold.
    gold_amount: int | None = None
    attack_bonus: int | None = None
    defense_bonus: int | None = None
    ranged_attack_bonus: int | None = None
    range: int | None = Field(default=None, gt=0)
    is_key: bool = False
    # An ammo item stacks: one pickup can be worth several shots.
    is_ammo: bool = False
    # Drinking this exits the current dungeon to the overworld - see
    # engine/actions.py's UseItemAction and engine/entity.py's POTION_KINDS.
    is_teleport: bool = False
    quantity: int = Field(default=1, gt=0)
    # What a shopkeeper charges for this item, in gold - a fact about the
    # item, not about any one shopkeeper (see EntityDef.shop_inventory).
    # None for an item that's never sold, only found.
    cost: int | None = Field(default=None, gt=0)
    description: str = ""

    @field_validator("glyph")
    @classmethod
    def glyph_is_single_char(cls, v: str) -> str:
        if len(v) != 1:
            raise ValueError(f"glyph must be a single character, got {v!r}")
        return v

    @model_validator(mode="after")
    def not_multiple_equipment_slots(self) -> "ItemDef":
        slots_set = sum(
            bonus is not None
            for bonus in (self.attack_bonus, self.defense_bonus, self.ranged_attack_bonus)
        )
        if slots_set > 1:
            raise ValueError(
                "an item can only set one of attack_bonus/defense_bonus/"
                "ranged_attack_bonus (ambiguous which equipment slot it belongs in)"
            )
        return self


class PerkDef(BaseModel):
    """A permanent player upgrade, as defined once in data/perks.yaml and
    taught by Trainer NPCs (EntityDef.trainer_perks) in exchange for XP -
    see Engine.learn_perk. Unlike an ItemDef's equipment bonus (conditional
    on what's currently equipped, and re-derivable at any time), a perk's
    bonus is folded permanently into the player's own Fighter the moment
    it's learned (see engine/entity.py's apply_perk_stat_bonus) and never
    removed - a perk is bought once, ever, never repurchased or unequipped.

    Exactly one of the four bonus fields must be set (enforced below),
    mirroring ItemDef's own single-equipment-slot discipline
    (not_multiple_equipment_slots) - unambiguous which stat a perk
    improves. A perk needing a mechanic beyond a flat stat bonus (the
    "more complex ones" the project's XP/Perks feature anticipates) isn't
    representable yet - this model covers only the first, simplest wave."""

    id: str
    name: str
    description: str
    # The XP price, always required - a perk is never free (see
    # Engine.learn_perk's affordability check).
    xp_cost: int = Field(gt=0)
    # An optional additional gold price, on top of xp_cost - None means
    # XP-only. Lets a Trainer NPC charge gold as well as XP for a
    # particularly valuable perk, same "some shopkeepers ask more" spirit
    # as EntityDef.shop_inventory letting different NPCs stock differently.
    gold_cost: int | None = Field(default=None, gt=0)
    max_hp_bonus: int | None = None
    attack_bonus: int | None = None
    defense_bonus: int | None = None
    ranged_attack_bonus: int | None = None

    @model_validator(mode="after")
    def exactly_one_bonus(self) -> "PerkDef":
        bonuses = [self.max_hp_bonus, self.attack_bonus, self.defense_bonus, self.ranged_attack_bonus]
        if sum(b is not None for b in bonuses) != 1:
            raise ValueError(
                "a perk must set exactly one of max_hp_bonus/attack_bonus/"
                "defense_bonus/ranged_attack_bonus (ambiguous which stat it improves)"
            )
        return self


class TightenDeadline(BaseModel):
    """One WorldConsequence action's payload: shortens ANOTHER quest's own
    deadline_day the moment this WorldConsequence's owning quest's deadline
    lapses (see Engine._tighten_deadline). Nested, not two flat fields on
    WorldConsequence, since the two pieces of data only mean anything
    together - same shape as FlagDialogue. Never extends a deadline - see
    Engine._tighten_deadline's own guard. No year field: every quest with
    a deadline today shares deadline_year 87."""

    quest_id: str
    new_day: int


class WorldConsequence(BaseModel):
    """One thing that happens automatically when a quest's on_fail list
    fires (see QuestDef.on_fail, QuestLog.check_deadlines,
    Engine._apply_world_consequences). Exactly one of the three actions
    below - never more than one, never none - so a quest's on_fail is a
    *list* of these, letting one deadline trigger more than one
    consequence (e.g. raze a dungeon AND record a flag) without a
    one-consequence limit."""

    # Raze this dungeon's overworld entrance - see Engine.destroy_dungeon.
    # Only meaningful if the target dungeon has ruined_tile/
    # ruined_description authored (content/loader.py's load_quests and
    # main.py's _check_destroyable_dungeons_have_ruin_content cross-check
    # this at content-load time).
    destroy_dungeon_id: str | None = None
    # Records this name in QuestLog.world_flags, permanently for the rest
    # of the run - see FlagDialogue for the first (and so far only) thing
    # that reads world_flags back.
    set_flag: str | None = None
    # Shortens another quest's own deadline_day - see TightenDeadline,
    # Engine._tighten_deadline. The one action that reaches into a
    # DIFFERENT quest's own clock - requires_quest_id only gates granting,
    # voided_by_dungeon_id only force-fails on a dungeon's destruction,
    # and destroy_dungeon_id/set_flag above only ever affect the failing
    # quest's own target, not another quest's timing.
    tighten_deadline: TightenDeadline | None = None

    @model_validator(mode="after")
    def exactly_one_action(self) -> "WorldConsequence":
        actions = [self.destroy_dungeon_id, self.set_flag, self.tighten_deadline]
        if sum(a is not None for a in actions) != 1:
            raise ValueError(
                "a WorldConsequence must set exactly one of "
                "destroy_dungeon_id/set_flag/tighten_deadline"
            )
        return self


class QuestDef(BaseModel):
    """A quest, as defined once in data/quests.yaml. Field-for-field the raw
    authored shape of engine/quest.py's runtime Quest, minus Quest's mutable
    `status` (renamed `starting_status` here - authored intent, "does this
    quest start given or not," not live state that changes as the run
    progresses). engine/quest.py's quest_from_def converts one of these into
    a live Quest; engine/quest.py itself still owns what each trigger *does*
    (QuestLog.check_dungeon_report/check_talked_to/check_delivery/
    check_kill_report/record_entity_killed/record_dungeon_arrival) - this
    model only owns which quest targets what.

    A quest completes via exactly one of four trigger shapes - at most one
    of target_dungeon_id/target_entity_id/target_kill_entity_id/
    target_item_id may be set (enforced below); zero is valid for a quest
    with no completion trigger yet. A fetch quest (target_item_id), a kill
    quest (target_kill_entity_id), and a dungeon-arrival quest
    (target_dungeon_id) all always need questgiver_entity_id too, since
    QuestLog.check_delivery/check_kill_report/check_dungeon_report only
    ever complete them by talking to that NPC (while holding the item,
    after the kill-target's been recorded dead, or after the dungeon's
    been recorded visited) - enforced in content/loader.py's load_quests,
    which also checks every id here (questgiver/target/reward) actually
    exists in the catalog, since that needs the catalog and can't be
    checked at the field level here."""

    id: str
    name: str
    # The quest log screen's default pane text - what's shown before
    # anything's happened yet (not_given/in_progress with no more specific
    # override applicable). See Quest.current_description for how the
    # three overrides below take precedence over this at their own stage.
    description: str
    completion_message: str
    failure_message: str = ""
    target_dungeon_id: str | None = None
    target_entity_id: str | None = None
    target_kill_entity_id: str | None = None
    target_item_id: str | None = None
    # A fifth trigger shape: intimidate, don't kill. Same two-step
    # "record the deed, complete only on report" pattern as
    # target_kill_entity_id (see QuestLog.record_entity_intimidated/
    # check_intimidate_report), except the deed here is the player
    # attacking (not necessarily damaging) this catalog entity while it
    # survives - engine/combat.py's _apply_damage records it under the
    # same condition that already flips a settlement's guards hostile
    # (attacker is the player, defender.ai in PEACEFUL_AI_TYPES), so
    # content/loader.py's load_quests requires this to name a peaceful
    # entity. If the target dies instead, QuestLog.fail_intimidate_by_death
    # force-fails the quest immediately - the codebase's first
    # action-triggered failure; every other failure is deadline- or
    # dungeon-destruction-based (see failed_description's validator below).
    target_intimidate_entity_id: str | None = None
    # A sixth trigger shape: cull a whole species from a dungeon while
    # another species survives. Unlike every other trigger, "cleared" is a
    # population check (no living entity with this catalog id remains
    # anywhere in the questgiver's dungeon - see
    # Engine._entity_type_cleared_from_dungeon), not a hand-authored kill
    # count that could drift out of sync with the level files. Recorded
    # into QuestLog.cleared_species_ids the instant the last one dies
    # (Engine.on_entity_death), completed only on report to
    # questgiver_entity_id (QuestLog.check_cull_report) - same two-step
    # shape as every other trigger.
    target_cull_entity_id: str | None = None
    # The species this cull quest must not wipe out - only meaningful
    # alongside target_cull_entity_id (validated below). Tracked via
    # QuestLog.entity_kill_counts (every kill of any entity id, counted
    # unconditionally); exceeding target_preserve_tolerance force-fails
    # the quest immediately (QuestLog.fail_cull_by_preservation_loss),
    # same action-triggered-failure timing as target_intimidate_entity_id's
    # fail_intimidate_by_death, just with a threshold instead of zero
    # tolerance.
    target_preserve_entity_id: str | None = None
    # How many target_preserve_entity_id deaths are still forgivable - the
    # (tolerance + 1)th one fails the quest. 0 (the default) is
    # zero-tolerance, same bar as an intimidate quest's target dying.
    target_preserve_tolerance: int = Field(default=0, ge=0)
    deadline_year: int | None = None
    deadline_day: int | None = None
    # Both set together or not at all (validated below): the earliest the
    # clock can be for this quest to be grantable at all -
    # QuestLog.check_questgiver skips a not-yet-available quest silently,
    # the same "NPC just says their normal line" treatment
    # requires_quest_id already gets. Independent of any other quest's
    # outcome - unlike requires_quest_id (gated on completion status) or
    # on_fail (gated on a quest's own failure), this is a pure calendar
    # floor, for content whose availability follows the world clock
    # itself rather than another quest's fate (e.g. "3 days after the
    # goblin horde was due to reach Wayford, whether or not the warning
    # got there in time").
    available_after_year: int | None = None
    available_after_day: int | None = None
    questgiver_entity_id: str | None = None
    given_message: str = ""
    already_done_message: str = ""
    questgiver_done_dialogue: str = ""
    target_done_dialogue: str = ""
    reward_item_id: str | None = None
    reward_gold_amount: int | None = Field(default=None, gt=0)
    # XP granted on completion (see Engine.complete_quest), a sibling to
    # reward_gold_amount above - not mutually exclusive with any other
    # reward shape, though no shipped quest combines more than one today.
    reward_xp_amount: int | None = Field(default=None, gt=0)
    reward_shop_discount_pct: float | None = Field(default=None, gt=0, le=1)
    # Which shopkeeper's shop this discount applies to - a catalog entity id
    # with a non-empty shop_inventory (see EntityDef.shop_inventory), e.g.
    # "shopkeeper" for Millhaven's. Required alongside reward_shop_discount_pct
    # (enforced below): a discount with no named shop would otherwise apply
    # everywhere, which is exactly the bug this field exists to close - see
    # QuestLog.shop_discount_pct/Engine.shop_price.
    reward_shop_discount_entity_id: str | None = None
    # Another quest's id that must be `completed` before this one can ever
    # be granted via QuestLog.check_questgiver - the general form of a
    # quest chain (e.g. a follow-up quest from the same NPC, unlockable
    # only once an earlier quest is done). None means no prerequisite -
    # grantable as soon as the questgiver is talked to, same as every
    # quest today.
    requires_quest_id: str | None = None
    starting_status: QuestStatus = "not_given"
    # Quest log pane override for a fetch quest (target_item_id) while
    # in_progress and the player is actually carrying the target item (not
    # yet delivered) - see Quest.current_description. "" means no override:
    # `description` keeps showing even while carrying the item. Only
    # meaningful alongside target_item_id.
    carrying_item_description: str = ""
    # Quest log pane override for a kill quest (target_kill_entity_id) while
    # in_progress and its target has actually been recorded dead (not yet
    # reported to the questgiver) - see Quest.current_description. Same
    # shape as carrying_item_description, just for the kill-then-report
    # trigger instead of pickup-then-deliver. Only meaningful alongside
    # target_kill_entity_id.
    target_dead_description: str = ""
    # Quest log pane override for a dungeon-arrival quest (target_dungeon_id)
    # while in_progress and the target dungeon has actually been recorded
    # visited (not yet reported to the questgiver) - see
    # Quest.current_description. Same shape again, for the arrive-then-report
    # trigger. Only meaningful alongside target_dungeon_id.
    target_visited_description: str = ""
    # Quest log pane override for an intimidate quest (target_intimidate_entity_id)
    # while in_progress and its target has actually been recorded
    # intimidated (not yet reported to the questgiver) - see
    # Quest.current_description. Same shape again, for the
    # intimidate-then-report trigger. Only meaningful alongside
    # target_intimidate_entity_id.
    target_intimidated_description: str = ""
    # Quest log pane override for a cull quest (target_cull_entity_id)
    # while in_progress and the target species has actually been recorded
    # cleared (not yet reported to the questgiver) - see
    # Quest.current_description. Same shape again, for the
    # clear-then-report trigger. Only meaningful alongside
    # target_cull_entity_id.
    target_cleared_description: str = ""
    # Quest log pane override once this quest is "completed" - a summary of
    # what happened and what was earned, not just the original pitch. ""
    # falls back to `description`.
    completed_description: str = ""
    # Quest log pane override once this quest is "failed" - only meaningful
    # alongside a deadline, voided_by_dungeon_id, or target_intimidate_entity_id
    # (see the validator below) - the only three ways a quest ever fails.
    # "" falls back to `description`.
    failed_description: str = ""
    # Every consequence applied the moment this quest's deadline passes
    # while still in_progress (see QuestLog.check_deadlines,
    # Engine._apply_world_consequences) - a list so one lapsed deadline can
    # fire more than one consequence (e.g. raze a dungeon AND record a
    # flag), not just one. Empty (the default) means an ordinary deadline
    # failure with no further consequence. Only meaningful alongside a
    # real deadline - a quest that can never fail can never trigger these
    # either.
    on_fail: list["WorldConsequence"] = Field(default_factory=list)
    # This quest can never be completed once the named dungeon has been
    # destroyed (see on_fail_destroy_dungeon_id above) - its questgiver or
    # completion target lives there. QuestLog.void_by_dungeon force-fails
    # any not_given/in_progress quest with this set the moment that
    # dungeon is razed. None means this quest is unaffected by any
    # dungeon's destruction.
    voided_by_dungeon_id: str | None = None

    @model_validator(mode="after")
    def at_most_one_trigger(self) -> "QuestDef":
        triggers = [
            self.target_dungeon_id, self.target_entity_id,
            self.target_kill_entity_id, self.target_item_id,
            self.target_intimidate_entity_id, self.target_cull_entity_id,
        ]
        if sum(t is not None for t in triggers) > 1:
            raise ValueError(
                "a quest can set at most one of target_dungeon_id/"
                "target_entity_id/target_kill_entity_id/target_item_id/"
                "target_intimidate_entity_id/target_cull_entity_id "
                "(ambiguous which completion trigger applies)"
            )
        return self

    @model_validator(mode="after")
    def failed_description_requires_a_deadline_or_voiding_dungeon(self) -> "QuestDef":
        if (
            self.failed_description
            and self.deadline_year is None
            and self.voided_by_dungeon_id is None
            and self.target_intimidate_entity_id is None
            and self.target_cull_entity_id is None
        ):
            raise ValueError(
                "failed_description is set but there's no deadline, no "
                "voided_by_dungeon_id, no target_intimidate_entity_id, and "
                "no target_cull_entity_id - QuestLog.check_deadlines, "
                "QuestLog.void_by_dungeon, QuestLog.fail_intimidate_by_death, "
                "and QuestLog.fail_cull_by_preservation_loss are the only "
                "ways a quest ever fails, so a quest with none of these can "
                "never show it"
            )
        return self

    @model_validator(mode="after")
    def deadline_both_or_neither(self) -> "QuestDef":
        if (self.deadline_year is None) != (self.deadline_day is None):
            raise ValueError("deadline_year and deadline_day must be set together or not at all")
        return self

    @model_validator(mode="after")
    def available_after_both_or_neither(self) -> "QuestDef":
        if (self.available_after_year is None) != (self.available_after_day is None):
            raise ValueError(
                "available_after_year and available_after_day must be set together or not at all"
            )
        return self

    @model_validator(mode="after")
    def target_preserve_entity_id_requires_a_cull_target(self) -> "QuestDef":
        if self.target_preserve_entity_id is not None and self.target_cull_entity_id is None:
            raise ValueError(
                "target_preserve_entity_id is set but target_cull_entity_id "
                "isn't - a preserve clause makes no sense without a cull "
                "quest to attach to"
            )
        return self

    @model_validator(mode="after")
    def target_preserve_entity_id_differs_from_cull_target(self) -> "QuestDef":
        if (
            self.target_preserve_entity_id is not None
            and self.target_preserve_entity_id == self.target_cull_entity_id
        ):
            raise ValueError(
                "target_preserve_entity_id is the same as target_cull_entity_id - "
                "killing and preserving the same species is incoherent"
            )
        return self

    @model_validator(mode="after")
    def reward_shop_discount_pct_and_entity_id_together(self) -> "QuestDef":
        if (self.reward_shop_discount_pct is None) != (self.reward_shop_discount_entity_id is None):
            raise ValueError(
                "reward_shop_discount_pct and reward_shop_discount_entity_id "
                "must be set together or not at all - a discount needs to "
                "name which shop it applies to"
            )
        return self

    @model_validator(mode="after")
    def requires_quest_id_needs_a_questgiver(self) -> "QuestDef":
        if self.requires_quest_id is not None and self.questgiver_entity_id is None:
            raise ValueError(
                "requires_quest_id is set but questgiver_entity_id isn't - "
                "QuestLog.check_questgiver is the only place requires_quest_id "
                "is ever checked, so a quest with no questgiver could never use it"
            )
        return self

    @model_validator(mode="after")
    def carrying_item_description_requires_a_fetch_target(self) -> "QuestDef":
        if self.carrying_item_description and self.target_item_id is None:
            raise ValueError(
                "carrying_item_description is set but target_item_id isn't - "
                "this override only ever applies to a fetch quest, checked "
                "against the item the player is actually carrying"
            )
        return self

    @model_validator(mode="after")
    def target_dead_description_requires_a_kill_target(self) -> "QuestDef":
        if self.target_dead_description and self.target_kill_entity_id is None:
            raise ValueError(
                "target_dead_description is set but target_kill_entity_id "
                "isn't - this override only ever applies to a kill quest, "
                "checked against whether the target's been recorded dead"
            )
        return self

    @model_validator(mode="after")
    def target_visited_description_requires_a_dungeon_target(self) -> "QuestDef":
        if self.target_visited_description and self.target_dungeon_id is None:
            raise ValueError(
                "target_visited_description is set but target_dungeon_id "
                "isn't - this override only ever applies to a dungeon-arrival "
                "quest, checked against whether the dungeon's been recorded "
                "visited"
            )
        return self

    @model_validator(mode="after")
    def target_intimidated_description_requires_an_intimidate_target(self) -> "QuestDef":
        if self.target_intimidated_description and self.target_intimidate_entity_id is None:
            raise ValueError(
                "target_intimidated_description is set but "
                "target_intimidate_entity_id isn't - this override only "
                "ever applies to an intimidate quest, checked against "
                "whether the target's been recorded intimidated"
            )
        return self

    @model_validator(mode="after")
    def target_cleared_description_requires_a_cull_target(self) -> "QuestDef":
        if self.target_cleared_description and self.target_cull_entity_id is None:
            raise ValueError(
                "target_cleared_description is set but target_cull_entity_id "
                "isn't - this override only ever applies to a cull quest, "
                "checked against whether the species has been recorded cleared"
            )
        return self


class EncounterDef(BaseModel):
    """A scripted overworld encounter, authored in data/encounters.yaml:
    leaving `trigger_dungeon_id` for the overworld while `gate_quest_id`'s
    live status equals `gate_quest_status` arms a `delay_hours`-long timer;
    once that many *overworld* hours have actually elapsed (dungeons never
    advance the clock - see Engine.process_enemy_phase), the player is
    redirected into `encounter_dungeon_id` instead of continuing on the
    overworld - see main.py's resolve_transition/_armable_encounter/
    _due_encounter, and QuestLog.armed_encounters/triggered_encounter_ids
    for the arm-then-fire state.

    Deliberately not named requires_quest_id/requires_quest_status despite
    the similarity to QuestDef.requires_quest_id above - that field means
    "must be completed, checked once at grant time" (QuestLog.check_questgiver);
    this one means "must currently equal this status, checked on every
    departure from trigger_dungeon_id" - different enough that sharing the
    name would mislead a future reader into assuming the same semantics.

    encounter_dungeon_id names a real entry in the dungeon registry (loaded
    and validated the same way as any other dungeon) that's deliberately
    never pointed at by any overworld dungeon_entrance tile - it's only
    ever reachable through this trigger, not by walking there."""

    id: str
    trigger_dungeon_id: str
    gate_quest_id: str
    gate_quest_status: QuestStatus = "in_progress"
    encounter_dungeon_id: str
    # Overworld hours that must pass after arming (departing trigger_dungeon_id
    # with the gate quest at gate_quest_status) before the encounter actually
    # fires - see GameClock.plus_hours/QuestLog.armed_encounters. Re-departing
    # trigger_dungeon_id before the timer fires restarts it from that later
    # departure, rather than continuing the original countdown.
    delay_hours: int = Field(default=3, gt=0)
    # Logged to the message log the moment this encounter actually fires
    # (main.py's _redirect_into_encounter), right after the generic "You
    # enter <level_name>." line every dungeon arrival already gets - explains
    # *why* the player was just pulled off the overworld, since nothing else
    # about the transition itself makes that obvious. "" (the default) logs
    # nothing extra.
    encounter_message: str = ""


class FlagDialogue(BaseModel):
    """One line an `{entity: ...}` legend spawn says instead of its normal
    dialogue once a named world flag is set (see QuestLog.world_flags,
    WorldConsequence.set_flag, Engine.talk_to_adjacent). Both fields are
    required - unlike WorldConsequence there's no "exactly one of"
    ambiguity, a FlagDialogue only ever does one thing.

    LegendEntry.flag_dialogue is a *list* so a single spawn can react to
    more than one possible world outcome; checked in author list order,
    first match wins - same "list, order matters" shape as on_fail."""

    flag: str
    line: str


class LegendEntry(BaseModel):
    """A normalized legend entry: what tile a symbol represents, and optionally
    which entity/item spawns there, or which level a stairway leads to.

    Level files may write a legend value as a plain tile-type string (e.g. "wall"),
    or as a mapping. Shorthands:
      - {entity: rat} / {item: healing_potion}: a floor tile with that entity/item
        on it. Add `tile: <kind>` to stand it on something other than plain
        floor - {entity: villager, tile: plains} for a villager in an
        outdoor town square, say - the entity/item and everything else
        about the shorthand works identically; only the underlying ground
        tile (and its sprite - see engine/sprites.py's composite_sprite_over_terrain)
        changes. Bare {entity: rat} still defaults to floor.
      - {stairs_down: level_02a}: a stairway tile leading to that level id. A bare
        "stairs_down" string (no mapping) means a *terminal* stairway - reaching it
        leaves the dungeon and returns to the overworld. A level can have multiple
        differently-symboled stairway tiles leading to different destinations
        (branching).
      - {stairs_up: level_01}: a stairway tile leading back to that level id. A
        bare "stairs_up" string (no mapping) is also terminal - like stairs_down,
        it leaves the dungeon and returns to the overworld (used for a retreat
        point near a dungeon's entrance, as opposed to stairs_down's usual role
        completing the dungeon at its far end).
      - {door: rusty_key}: a locked door tile, impassable until the player holds
        an item whose id matches (i.e. a key with that id), which is consumed to
        open it permanently.
      - {dungeon_entrance: forgotten_ruins}: overworld-only - a tile leading into
        that dungeon's registry entry (not a level within the current dungeon;
        see content/loader.py's load_overworld).

    Any mapping form (not the bare-string shorthand) may also carry a
    `description`, shown in look mode instead of the kind's generic default
    text (e.g. "Stairs leading up.") - useful for a stairway/entrance that
    deserves its own flavor: {stairs_up: null, description: "The town gate
    leading out."}.

    For a walkable point of interest that isn't a stairway/door/entrance -
    a piece of furniture, a landmark, anything meant to be noticed and read
    rather than walked past - use `tile: landmark` with a `description`
    rather than `tile: floor` (or `road`/`plains`/etc.) with one: a floor-
    kind tile with a custom description still *renders* as plain floor,
    identical to every other floor tile, so a player has no visual reason
    to stop and look. `landmark` renders with its own distinct glyph (see
    `engine/render.py` TILE_VISUALS) specifically so points of interest
    don't blend into the terrain around them: {tile: landmark, description:
    "A chalk tally board, its hatch-marks stopping mid-quota."}.

    A mapping with a `description` may also set `announce: true` to have
    that text automatically logged to the message log the first time this
    exact tile enters the player's field of view, once ever per tile per
    map - an alternative to requiring the player to manually Look to read
    it (see GameMap.newly_seen_tile_announcements). Meaningless (and
    rejected) without `description` also set. The primary use case is
    `tile: landmark` (see above), but any description-bearing tile - a
    flavorful stairway, an item resting somewhere notable - can opt in.
    Never use it on a symbol painted across many map cells (a `sea`/
    `mountain` hazard, a `wall` segment forming a whole boundary) - each
    cell announces independently, so the same line repeats once per
    distinct coordinate as different parts of it enter FOV. `announce` is
    for a tile placed once, not a shared kind spanning an area.

    An `{entity: ...}` mapping may also carry a `dialogue` - the line the
    Talk action shows for *this specific placement*, distinct from
    `description` (which, on an entity mapping, is still a *tile*-level
    look-mode override, not the entity's - see load_level). Don't confuse
    the two: {entity: villager, dialogue: "Well's held up better than most
    things built before the Sundering."} gives this one villager a unique
    line; `description` here would instead override what look-mode says
    about the ground they're standing on.

    An `{entity: ...}` mapping may also carry `flag_dialogue` - a list of
    {flag: <name>, line: <text>} entries (see FlagDialogue). If <name> is
    in QuestLog.world_flags when the player talks to this spawn, <text> is
    shown instead of both this entry's own `dialogue` and any active
    QuestLog.followup_dialogue line (see Engine.talk_to_adjacent) - a
    world-state reaction takes priority over per-spawn or per-quest text,
    since it means something happened that supersedes whatever this NPC
    would otherwise be saying. Checked in list order, first matching flag
    wins: {entity: village_chief, flag_dialogue: [{flag: wayford_razed,
    line: "..."}]}.
    """

    tile: TileType
    entity: str | None = None
    item: str | None = None
    next_level: str | None = None
    requires_key: str | None = None
    dungeon_id: str | None = None
    description: str | None = None
    dialogue: str | None = None
    announce: bool = False
    flag_dialogue: list[FlagDialogue] = Field(default_factory=list)

    @model_validator(mode="after")
    def announce_requires_description(self) -> "LegendEntry":
        if self.announce and not self.description:
            raise ValueError("announce requires description to be set")
        return self

    @classmethod
    def from_raw(cls, raw: str | dict) -> "LegendEntry":
        if isinstance(raw, str):
            return cls(tile=raw)
        if isinstance(raw, dict):
            description = raw.get("description")
            announce = raw.get("announce", False)
            if "entity" in raw:
                return cls(
                    tile=raw.get("tile", "floor"), entity=raw["entity"], description=description,
                    dialogue=raw.get("dialogue"), announce=announce,
                    flag_dialogue=raw.get("flag_dialogue") or [],
                )
            if "item" in raw:
                return cls(
                    tile=raw.get("tile", "floor"), item=raw["item"], description=description, announce=announce,
                )
            if "stairs_down" in raw:
                return cls(
                    tile="stairs_down", next_level=raw["stairs_down"], description=description, announce=announce,
                )
            if "stairs_up" in raw:
                return cls(
                    tile="stairs_up", next_level=raw["stairs_up"], description=description, announce=announce,
                )
            if "door" in raw:
                return cls(tile="door", requires_key=raw["door"], description=description, announce=announce)
            if "dungeon_entrance" in raw:
                return cls(
                    tile="dungeon_entrance", dungeon_id=raw["dungeon_entrance"],
                    description=description, announce=announce,
                )
            tile = raw.get("tile", "floor")
            return cls(
                tile=tile,
                entity=raw.get("entity"),
                item=raw.get("item"),
                next_level=raw.get("next_level"),
                requires_key=raw.get("requires_key"),
                dungeon_id=raw.get("dungeon_id"),
                description=description,
                dialogue=raw.get("dialogue"),
                announce=announce,
                flag_dialogue=raw.get("flag_dialogue") or [],
            )
        raise ValueError(f"legend entry must be a string or mapping, got {raw!r}")


# player_start_tile kinds that would be nonsensical as "the ambient terrain
# under the player's starting square" - either not a real terrain kind
# (player_start itself), or a special-purpose kind whose meaning depends on
# being a distinct, singular thing (a stairway, a dungeon_entrance).
# Anything impassable (wall/mountain/sea/door, per TILE_PASSABILITY) is
# rejected too, checked separately below since that's already the single
# source of truth for walkability.
_INVALID_PLAYER_START_TILE_KINDS = {
    "player_start", "stairs_down", "stairs_up", "dungeon_entrance",
}


class LevelDef(BaseModel):
    """A hand-authored level file: an ASCII map plus a legend mapping symbols to
    tiles/entities/items. Stairway destinations live per-symbol in the legend
    (see LegendEntry), not as a single level-wide field, since a level can branch
    into multiple stairways."""

    id: str
    name: str
    map: str
    legend: dict[str, LegendEntry]
    # The tile kind rendered under the player's starting square once the map
    # is built (see engine/game_map.py's build_game_map, which never lets a
    # live "player_start" kind reach the GameMap - it's always substituted
    # for something walkable). Defaults to "floor" for backward compatibility;
    # override it when the starting square sits amid non-floor terrain (e.g.
    # "plains" for an outdoor clearing/town square, "road" for a gate) so it
    # doesn't render as a mismatched patch the instant the player steps off it.
    player_start_tile: TileType = "floor"
    # True makes every edge of this level's map a valid way to leave (see
    # engine/actions.py's MovementAction, engine/engine.py's
    # on_player_reach_map_edge) - always returns to the overworld, the
    # open-area equivalent of a terminal stairs_up, just triggered by
    # walking off the map instead of onto one specific tile. Only
    # meaningful alongside requires_stairs_down: false (content/loader.py's
    # load_level rejects a level with neither a stairway nor this set,
    # per the existing "there would be no way to leave" soft-lock check) -
    # a real progression dungeon should keep using stairs_down to go
    # deeper.
    open_boundary: bool = False
    # Custom message logged the moment the player actually leaves via the
    # edge (see DEFAULT_OPEN_BOUNDARY_MESSAGE in engine/engine.py for the
    # fallback used when this is left unset). Only meaningful alongside
    # open_boundary: true.
    open_boundary_message: str = ""
    # True shrinks this level's FOV radius to DARK_FOV_RADIUS (see
    # engine/game_map.py) instead of the normal FOV_RADIUS - a level where
    # sunlight genuinely doesn't reach (a hollow, a sealed cellar), not a
    # difficulty slider to sprinkle on ordinary rooms. Purely a rendering/
    # awareness effect - doesn't touch walkability, monster AI, or
    # anything else; a hostile_basic monster still only ever acts once its
    # own tile is inside that shrunken visible area, so a dark level's real
    # effect is less reaction time before something's already close.
    dark: bool = False

    @field_validator("legend", mode="before")
    @classmethod
    def normalize_legend(cls, v: dict) -> dict[str, LegendEntry]:
        return {symbol: LegendEntry.from_raw(raw) for symbol, raw in v.items()}

    @field_validator("player_start_tile")
    @classmethod
    def validate_player_start_tile(cls, v: str) -> str:
        walkable, _ = TILE_PASSABILITY.get(v, (True, True))
        if not walkable or v in _INVALID_PLAYER_START_TILE_KINDS:
            raise ValueError(
                f"player_start_tile '{v}' must be a walkable ambient-terrain kind "
                "(e.g. floor/forest/road/plains/town/landmark) - not a wall/door/"
                "stairway/dungeon_entrance/player_start kind"
            )
        return v


class DungeonDef(BaseModel):
    """A dungeon's manifest: identifies it and declares where a fresh run
    begins. Lives at data/dungeons/<dungeon_id>/dungeon.yaml, sitting
    alongside that dungeon's own levels/ directory. The catalog
    (entities.yaml/items.yaml) is global, not per-dungeon - a dungeon just
    references ids from it, the same way a level does."""

    id: str
    name: str
    starting_level: str
    description: str = ""
    # Shown when the player inspects this dungeon's entrance tile on the
    # overworld (look mode) - distinct from `description` above, which is a
    # longer dev-facing summary for tools/preview.py, not in-game text.
    # Falls back to a generic line (engine/render.py TILE_DESCRIPTIONS) when
    # left blank.
    inspect_text: str = ""
    # False for a peaceful, non-progression place (a settlement) that only
    # ever needs a terminal stairs_up to leave - every real dungeon keeps
    # the default, which requires at least one stairs_down somewhere so a
    # level always either goes deeper or is a deliberate ending.
    requires_stairs_down: bool = True
    # What this dungeon's overworld entrance becomes if some quest's
    # on_fail names it via a WorldConsequence(destroy_dungeon_id=...) (see
    # QuestDef, Engine.destroy_dungeon) - the entrance tile is replaced
    # with ruined_tile, and ruined_description
    # becomes its look-mode text (see GameMap.tile_descriptions), in place
    # of the entrance disappearing into the dungeon it used to lead to.
    # Both are optional and only meaningful together (validated below) -
    # most dungeons are never destroyable and leave both unset.
    ruined_tile: TileType | None = None
    ruined_description: str = ""
    # Which level id this dungeon's entrance leads into once destroyed,
    # instead of its usual starting_level - lets a razed settlement stay
    # walkable (a real "after" ruins interior) rather than being sealed
    # off forever (see Engine.destroy_dungeon,
    # engine/game_map.py's apply_dungeon_destruction, main.py's
    # resolve_transition). Independent of ruined_tile/ruined_description
    # above - a dungeon can still be sealed-only by leaving this unset;
    # only a dungeon that wants a real walkable aftermath sets it.
    ruined_starting_level: str | None = None
    # The level this dungeon's entrance leads into *before* the world clock
    # reaches (pre_arrival_until_year, pre_arrival_until_day) - the mirror
    # image of ruined_starting_level: instead of "normal, then a quest
    # ruins it," this is "reduced, then a scheduled date populates it,"
    # independent of any quest's pass/fail (same "pure calendar floor"
    # shape as QuestDef.available_after_year/day, see
    # docs/content_design_process.md §0n). starting_level itself never
    # changes meaning - it's always the dungeon's normal, eventual state;
    # pre_arrival_starting_level is the temporary substitute shown only
    # until that date (see main.py's resolve_transition). Reference use
    # case: Silversilk Caves' goblin tribe doesn't yet occupy the cave
    # before the same day (87/67) the_uninvited_tribe becomes available -
    # entering earlier shows level_01_undisturbed (cave spiders only, no
    # way down to the warren) instead of the goblin-infested level_01.
    pre_arrival_starting_level: str | None = None
    pre_arrival_until_year: int | None = None
    pre_arrival_until_day: int | None = None
    # A reference number, never enforced or auto-consumed: roughly how
    # much XP-equivalent investment (perks actually bought, plus gear's
    # own XP-equivalent - see tools/balance.py, §0s) a player is expected
    # to have by the time they reasonably reach this dungeon. Purely for
    # tools/play_llm.py's `testbuild` mode to report a hand-picked test
    # build's total against, so a dungeon can be balance-checked without
    # a full playthrough. None (the default, and every dungeon predating
    # this field) just means no reference value has been set yet.
    balance_reference_xp: int | None = None

    @model_validator(mode="after")
    def ruined_tile_and_description_together(self) -> "DungeonDef":
        if (self.ruined_tile is None) != (self.ruined_description == ""):
            raise ValueError("ruined_tile and ruined_description must be set together or not at all")
        return self

    @model_validator(mode="after")
    def ruined_starting_level_requires_ruined_tile(self) -> "DungeonDef":
        if self.ruined_starting_level is not None and self.ruined_tile is None:
            raise ValueError("ruined_starting_level requires ruined_tile/ruined_description to be set")
        return self

    @model_validator(mode="after")
    def pre_arrival_until_year_and_day_together(self) -> "DungeonDef":
        if (self.pre_arrival_until_year is None) != (self.pre_arrival_until_day is None):
            raise ValueError(
                "pre_arrival_until_year and pre_arrival_until_day must be set together or not at all"
            )
        return self

    @model_validator(mode="after")
    def pre_arrival_starting_level_requires_the_date_pair(self) -> "DungeonDef":
        if self.pre_arrival_starting_level is not None and self.pre_arrival_until_year is None:
            raise ValueError(
                "pre_arrival_starting_level requires pre_arrival_until_year/day to be set too"
            )
        if self.pre_arrival_until_year is not None and self.pre_arrival_starting_level is None:
            raise ValueError(
                "pre_arrival_until_year/day is set but pre_arrival_starting_level isn't - "
                "there would be nothing to show before that date"
            )
        return self


class SpriteSheetDef(BaseModel):
    """One source image referenced by data/sprites.yaml, addressed either by
    a name->index JSON (RLTiles-style - a sheet with a published tile-name
    list) or by raw grid position (a plain spritesheet with no such index,
    e.g. the Kenney packs - see SpriteRef). `columns`/`rows` are required
    for a grid-only sheet since that's the only way a col/row SpriteRef can
    be bounds-checked or converted to a pixel box (see engine/sprites.py)."""

    image: str
    tile_size: int = Field(gt=0)
    index: str | None = None
    spacing: int = 0
    columns: int | None = Field(default=None, gt=0)
    rows: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def grid_sheets_need_columns_and_rows(self) -> "SpriteSheetDef":
        if self.index is None and (self.columns is None or self.rows is None):
            raise ValueError(
                "a sheet with no 'index' must set both 'columns' and 'rows' - "
                "that's the only way its tiles can be addressed by col/row"
            )
        return self


class SpriteRef(BaseModel):
    """One catalog id's (or tile kind's) sprite: which sheet, and which tile
    within it - addressed by `name` (looked up in that sheet's own index) or
    by `col`+`row` (direct grid position), never both. `recolor`, when true,
    retints the sprite toward the matching EntityDef/ItemDef's own `color`
    at registration time (see engine/sprites.py's recolor_sprite) - only
    meaningful on an entities/items entry, since a tile kind has no `.color`
    field to tint toward (content/loader.py's load_sprite_manifest rejects
    it on a tile_kinds entry).

    `backdrop`, when set, names another key in sprites.yaml's tile_kinds
    section to composite this sprite over, once, at registration time (see
    engine/sprites.py's composite_sprite_over_terrain) - for an icon-style
    sprite (a single tree/peak/tower silhouette on an otherwise transparent
    square, unlike a full-bleed texture like plains/sea/wall) whose
    transparent background would otherwise render as the console's plain
    black clear-color. Only meaningful on a tile_kinds or dungeon_entrances
    entry - entities/items already get this dynamically, per the actual
    tile they're standing on (see engine/render.py's _resolved_entity_glyph),
    which content/loader.py's load_sprite_manifest enforces by rejecting
    `backdrop` on an entities/items entry."""

    sheet: str
    name: str | None = None
    col: int | None = Field(default=None, ge=0)
    row: int | None = Field(default=None, ge=0)
    recolor: bool = False
    backdrop: str | None = None

    @model_validator(mode="after")
    def exactly_one_addressing_mode(self) -> "SpriteRef":
        by_name = self.name is not None
        by_grid = self.col is not None or self.row is not None
        if by_name and by_grid:
            raise ValueError("set either 'name' or 'col'+'row', not both")
        if not by_name and not by_grid:
            raise ValueError("must set either 'name' or 'col'+'row'")
        if by_grid and (self.col is None or self.row is None):
            raise ValueError("'col' and 'row' must be set together")
        return self


class SpriteManifestDef(BaseModel):
    """The raw shape of data/sprites.yaml: named source sheets, plus four
    id-keyed sections mapping a catalog entity id / item id / tile-kind
    string / dungeon registry id to a SpriteRef within one of those sheets.
    Any catalog id, tile kind, or dungeon id with no entry here simply has
    no sprite - engine/render.py falls back to its authored ASCII glyph
    (or, for a dungeon_entrance cell whose dungeon id has no entry in
    dungeon_entrances, to tile_kinds' generic dungeon_entrance sprite
    first - see _resolved_tile_glyph), so leaving something out is always
    safe, never a broken reference.

    dungeon_entrances is keyed by dungeon registry id, not tile kind -
    every dungeon_entrance cell on the overworld shares the same
    TileType, but which dungeon it actually leads to (see
    GameMap.dungeon_entrances) is what a per-dungeon entrance icon (a
    house for a town, a tower for a keep) needs to key off instead."""

    sheets: dict[str, SpriteSheetDef] = Field(default_factory=dict)
    entities: dict[str, SpriteRef] = Field(default_factory=dict)
    items: dict[str, SpriteRef] = Field(default_factory=dict)
    tile_kinds: dict[str, SpriteRef] = Field(default_factory=dict)
    dungeon_entrances: dict[str, SpriteRef] = Field(default_factory=dict)
