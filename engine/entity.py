"""World-object model: the player, monsters, and items as they exist in a running
game (as opposed to content.schema, which describes how they're *defined* in
content files)."""

from __future__ import annotations

from dataclasses import dataclass, field

from content.schema import (
    AI_AMBUSHER,
    AI_ENRAGE,
    AI_MIMIC,
    BUFF_HASTE,
    BUFF_IRONROOT,
    BUFF_SHADOWED,
    BUFF_SURE_FOOTED,
    BUFF_VIGOR,
    BuffKind,
    EffectKind,
    FlagDialogue,
    PerkDef,
    TrinketEffectKind,
)

Color = tuple[int, int, int]

# Draw order when multiple entities could occupy visual space: items under actors.
RENDER_PRIORITY_ITEM = 0
RENDER_PRIORITY_ACTOR = 1
RENDER_PRIORITY_PLAYER = 2

# AI_ENRAGE's engine-level fallbacks, used by Entity.is_enraged/
# effective_attack below when an EntityDef leaves the corresponding field
# unset - defined here rather than in engine/engine.py (where the other
# AI defaults like DEFAULT_FLEE_HP_PCT live) because effective_attack
# needs the resolved bonus value itself, not just a threshold, and
# engine/entity.py can't import engine/engine.py (the dependency runs the
# other way).
DEFAULT_ENRAGE_HP_PCT = 0.3
DEFAULT_ENRAGE_ATTACK_BONUS = 2
# AI_MIMIC's own fallback, same "can't import engine/engine.py" reasoning
# as above - engine/actions.py's PickupAction needs it too, and importing
# engine/engine.py from there would be circular (engine/engine.py already
# imports engine/actions.py).
DEFAULT_MIMIC_BONUS = 5


@dataclass
class ActiveEffect:
    """One status effect currently afflicting a Fighter - see
    Fighter.active_effects. `potency` is meaningful only for the effect
    kinds that have an intensity concept (poison's damage/turn, weaken's
    attack reduction); 0 for stun, which doesn't. `turns_remaining` ticks
    down once per turn (engine/engine.py's _tick_active_effects); the key
    is removed from active_effects entirely once it hits 0, rather than
    left inert at 0 - "currently affected" is membership in the dict, not
    a >0 comparison on a value inside it."""

    potency: int
    turns_remaining: int


@dataclass
class Fighter:
    max_hp: int
    hp: int
    attack: int
    defense: int
    # A learned perk's ranged_attack_bonus, permanently folded in (see
    # apply_perk_stat_bonus below) - unlike max_hp/attack/defense, ranged
    # attack has no base stat of its own to bump (effective_ranged_attack
    # derives entirely from `attack` plus the equipped weapon's bonus), so
    # a ranged-specific perk needs this separate field.
    perk_ranged_attack_bonus: int = 0
    # A learned perk's crit_chance_bonus/dodge_chance_bonus, permanently
    # folded in the same way - same reasoning as perk_ranged_attack_bonus
    # above (no base "crit chance" stat on Fighter to bump; combat.py adds
    # these directly onto the module-level CRIT_CHANCE/DODGE_CHANCE
    # constants, the same spot a trinket's own bonus is added).
    perk_crit_chance_bonus: float = 0.0
    perk_dodge_chance_bonus: float = 0.0
    # This fighter's own live status-effect afflictions, keyed by kind
    # ("poison"/"stun"/"weaken") - a repeat hit of the same kind refreshes
    # (overwrites) rather than stacks, but different kinds coexist
    # independently (poisoned AND weakened at once is fine). Distinct from
    # Entity.inflicts_effect/inflicts_potency/inflicts_duration below,
    # which is an attacker's static capability, never mutated. field(...)
    # not a bare {} default - dataclasses require a factory for a mutable
    # default so every Fighter instance gets its own dict, never a shared
    # one. See engine/engine.py's _tick_active_effects (poison damage,
    # duration countdown, expiry) and process_player_action/_perform_ai
    # (stun blocking an action) for where this is actually read/mutated.
    active_effects: dict[str, ActiveEffect] = field(default_factory=dict)
    # This fighter's own live self-buffs, keyed by BuffKind ("vigor"/
    # "haste"/"shadowed"/"sure_footed"/"ironroot" today) - same ActiveEffect
    # shape (potency/turns_remaining) and refresh-not-stack rule as
    # active_effects above, but a deliberately separate dict: these are
    # positive, self-applied (drunk, never inflicted by an attacker), and
    # BuffKind is a type distinct from EffectKind precisely so nothing can
    # accidentally wire a monster's inflicts_effect to a player buff.
    # `turns_remaining` means different things per kind, though: for vigor,
    # shadowed, sure_footed, and ironroot it's real turns, ticked once per
    # turn by engine/engine.py's _tick_active_buffs (Entity._vigor_bonus
    # reads vigor's potency while active; shadowed/sure_footed/ironroot
    # have no potency, engine/engine.py's _perform_ai/
    # _apply_environmental_hazard and engine/combat.py's _inflict_effect
    # just check for presence); for haste it's a count of free player
    # actions remaining, consumed one at a time by
    # Engine._consume_haste_action -
    # never by _tick_active_buffs, since that only runs as part of
    # process_enemy_phase, which a hasted action skips entirely.
    active_buffs: dict[str, ActiveEffect] = field(default_factory=dict)


def apply_perk_stat_bonus(fighter: Fighter, perk: PerkDef) -> None:
    """Permanently folds one learned perk's bonus into fighter's base
    stats - never hp. Engine.learn_perk bumps current hp separately, once,
    only for a live max-hp purchase (the "instant full benefit" a newly
    bought perk should give); engine/save.py's restore path calls this in
    a loop over every learned perk and must NOT re-bump hp per perk, since
    saved.hp already reflects every historical bump."""
    if perk.max_hp_bonus:
        fighter.max_hp += perk.max_hp_bonus
    elif perk.attack_bonus:
        fighter.attack += perk.attack_bonus
    elif perk.defense_bonus:
        fighter.defense += perk.defense_bonus
    elif perk.ranged_attack_bonus:
        fighter.perk_ranged_attack_bonus += perk.ranged_attack_bonus
    elif perk.crit_chance_bonus:
        fighter.perk_crit_chance_bonus += perk.crit_chance_bonus
    elif perk.dodge_chance_bonus:
        fighter.perk_dodge_chance_bonus += perk.dodge_chance_bonus
    # An active-skill perk (skill_effect set) folds nothing into Fighter at
    # all - it has no passive bonus, only a manually-triggered effect (see
    # engine/actions.py's UseSkillAction, Engine.use_skill). Nothing to do
    # here for one; learn_perk still adds it to learned_perk_ids, which is
    # what actually makes it usable.


@dataclass
class ItemEffect:
    heal_amount: int | None = None
    gold_amount: int | None = None
    attack_bonus: int | None = None
    defense_bonus: int | None = None
    ranged_attack_bonus: int | None = None
    range: int | None = None
    key_id: str | None = None
    is_ammo: bool = False
    is_teleport: bool = False
    quantity: int = 1
    # A trinket's passive rate bonus - see Entity.equipped_trinket below,
    # engine/combat.py's _trinket_bonus, Engine._award_xp.
    trinket_effect: "TrinketEffectKind | None" = None
    trinket_bonus: float | None = None
    # A weapon/armor affix's secondary status-effect proc - see
    # engine/combat.py's _maybe_apply_weapon_affix/_maybe_apply_armor_affix.
    affix_effect: "EffectKind | None" = None
    affix_potency: int | None = None
    affix_duration: int | None = None
    affix_chance: float | None = None
    # How many turns UseItemAction grants passage over deep_water/sea for -
    # see potion_kind below, engine/game_map.py's is_walkable.
    water_walking_duration: int | None = None
    # Whether drinking this clears every entry in Fighter.active_effects at
    # once - see potion_kind below.
    cures_effects: bool = False
    # Which Fighter.active_buffs entry drinking this grants, and its
    # potency/duration - see potion_kind below, Entity._vigor_bonus,
    # engine/engine.py's _tick_active_buffs/_consume_haste_action.
    # grants_buff+buff_duration are set together or not at all; buff_potency
    # is set only for the buff kinds that need it (content/schema.py's
    # grants_buff_and_duration_together/buff_potency_matches_buff_kind).
    grants_buff: "BuffKind | None" = None
    buff_potency: int | None = None
    buff_duration: int | None = None
    # Whether drinking this instantly explores the whole current level and
    # logs a one-time creature summary - see potion_kind below,
    # engine/actions.py's UseItemAction. A plain flag, not a buff - the map
    # stays explored permanently, there's nothing to tick down.
    reveals_map: bool = False
    # Whether using this relocates the player to a random nearby tile on
    # the same level and grants a short shadowed window - see potion_kind
    # below (checked before grants_buff, so this classifies as its own
    # "smoke_bomb" kind rather than colliding with plain "shadowed"),
    # engine/actions.py's UseItemAction.
    local_teleport: bool = False
    # Whether drinking this clears every entry in Entity.skill_cooldowns at
    # once - see potion_kind below. Same plain-flag shape as cures_effects.
    resets_skill_cooldowns: bool = False


# Every potion kind UseItemAction can drink (see Entity.selected_potion_kind,
# Entity.potion_slots, Engine.assign_potion_slot).
POTION_KINDS: tuple[str, ...] = (
    "healing", "teleport", "water_walking", "antidote", "vigor", "haste", "shadowed", "second_sight",
    "sure_footed", "smoke_bomb", "clarity", "ironroot",
)


def potion_kind(item: ItemEffect) -> str | None:
    """Which POTION_KINDS entry this item is, or None if it's not a potion."""
    if item.heal_amount:
        return "healing"
    if item.is_teleport:
        return "teleport"
    if item.water_walking_duration:
        return "water_walking"
    if item.cures_effects:
        return "antidote"
    if item.resets_skill_cooldowns:
        return "clarity"
    if item.local_teleport:
        # Checked before grants_buff below: a smoke bomb also sets
        # grants_buff=BUFF_SHADOWED on itself (see ItemDef.local_teleport's
        # own docstring), and would otherwise misclassify as plain
        # "shadowed" - local_teleport is what makes this its own kind.
        return "smoke_bomb"
    if item.grants_buff == BUFF_VIGOR:
        return "vigor"
    if item.grants_buff == BUFF_HASTE:
        return "haste"
    if item.grants_buff == BUFF_SHADOWED:
        return "shadowed"
    if item.grants_buff == BUFF_SURE_FOOTED:
        return "sure_footed"
    if item.grants_buff == BUFF_IRONROOT:
        return "ironroot"
    if item.reveals_map:
        return "second_sight"
    return None


class Entity:
    def __init__(
        self,
        x: int,
        y: int,
        glyph: str,
        color: Color,
        name: str,
        *,
        blocks_movement: bool = False,
        render_priority: int = RENDER_PRIORITY_ITEM,
        fighter: Fighter | None = None,
        item: ItemEffect | None = None,
        ai: str | None = None,
        alert_radius: int | None = None,
        flee_hp_pct: float | None = None,
        ranged_range: int | None = None,
        inflicts_effect: "EffectKind | None" = None,
        inflicts_potency: int | None = None,
        inflicts_duration: int | None = None,
        enrage_hp_pct: float | None = None,
        enrage_attack_bonus: int | None = None,
        pack_radius: int | None = None,
        pack_attack_bonus: int | None = None,
        regen_amount: int | None = None,
        drop_item_id: str | None = None,
        drop_chance: float | None = None,
        split_count: int | None = None,
        split_hp_fraction: float | None = None,
        can_split: bool = True,
        summon_entity_id: str | None = None,
        summon_interval: int | None = None,
        summon_max_active: int | None = None,
        charge_range: int | None = None,
        charge_attack_bonus: int | None = None,
        territory_radius: int | None = None,
        ambush_bonus: int | None = None,
        scavenge_radius: int | None = None,
        scavenge_heal_fraction: float | None = None,
        mimic_bonus: int | None = None,
        stationary: bool = False,
        description: str = "",
        dialogue: str = "",
        flag_dialogue: list[FlagDialogue] | None = None,
        shop_inventory: list[str] | None = None,
        xp_reward: int = 0,
        trainer_perks: list[str] | None = None,
        entity_id: str = "",
        equipped_weapon: "Entity | None" = None,
        equipped_armor: "Entity | None" = None,
        equipped_ranged_weapon: "Entity | None" = None,
        equipped_trinket: "Entity | None" = None,
        gold: int = 0,
        xp: int = 0,
        learned_perk_ids: set[str] | None = None,
        skill_cooldowns: dict[str, int] | None = None,
    ):
        self.x = x
        self.y = y
        # AI_TERRITORIAL's anchor point - wherever this entity actually
        # started existing, captured once here rather than a separate
        # settable field, since "home" is exactly "where it was placed"
        # for every entity, not a concept needing its own configuration.
        # Harmless and unread for anything that isn't territorial.
        self.home_x = x
        self.home_y = y
        self.glyph = glyph
        self.color = color
        self.name = name
        self.blocks_movement = blocks_movement
        self.render_priority = render_priority
        self.fighter = fighter
        self.item = item
        self.ai = ai
        # AI_AMBUSHER's whole "invisible until adjacent" mechanic - derived
        # purely from ai, not a separate EntityDef field, since "starts
        # hidden" is exactly what being an ambusher already means. Checked
        # by engine/render.py's render_entities/describe_tile and
        # engine/targeting.py's is_valid_target/find_nearest_target (never
        # drawn, listed, or targetable while True); cleared for good by
        # Engine._perform_ai's own AI_AMBUSHER branch the instant the
        # player gets adjacent. Always False for anything else.
        self.hidden = ai == AI_AMBUSHER
        # AI_MIMIC's whole "disguised as an item" mechanic - derived purely
        # from ai, not a separate EntityDef field, same shape as hidden
        # above. Checked by engine/game_map.py's entity_from_def (which
        # keeps a mimic non-blocking and item-render-priority while this is
        # True) and engine/actions.py's PickupAction (which reveals it
        # instead of collecting it). Cleared for good, like hidden, the
        # instant the player tries to pick it up - never re-disguises.
        # Unlike an ambusher, a mimic is never actually hidden (render.py/
        # targeting.py don't check this) - it's fully visible the whole
        # time, just mislabeled by its own glyph/color/name/description.
        self.mimicking = ai == AI_MIMIC
        self.alert_radius = alert_radius
        self.flee_hp_pct = flee_hp_pct
        self.ranged_range = ranged_range
        # This entity's innate on-hit status-effect capability, if any - set
        # once at spawn from EntityDef.inflicts_effect/inflicts_potency/
        # inflicts_duration, never mutated. See Fighter.active_effects
        # above for the victim-side live state this inflicts on a landed
        # hit (engine/combat.py's _apply_damage).
        self.inflicts_effect = inflicts_effect
        self.inflicts_potency = inflicts_potency
        self.inflicts_duration = inflicts_duration
        # AI_ENRAGE's threshold/bonus and AI_PACK_HUNTER's radius/bonus -
        # static per-entity-type config, set once at spawn like the
        # inflicts_* fields above, never mutated. AI_REGENERATOR's
        # regen_amount alongside them for the same reason.
        self.enrage_hp_pct = enrage_hp_pct
        self.enrage_attack_bonus = enrage_attack_bonus
        self.pack_radius = pack_radius
        self.pack_attack_bonus = pack_attack_bonus
        self.regen_amount = regen_amount
        # This entity's on-death drop capability - drop_chance probability
        # of leaving drop_item_id on the ground where it died (see
        # Engine._maybe_drop_loot). Static, set once at spawn, never
        # mutated - same shape as inflicts_effect above.
        self.drop_item_id = drop_item_id
        self.drop_chance = drop_chance
        # AI_SPLITTER's static config, same shape as drop_item_id/drop_chance
        # above - split_count/split_hp_fraction set once at spawn, never
        # mutated. can_split is different: still set once at spawn, but
        # explicitly False on a spawned copy (see Engine._maybe_split) so a
        # split chain can't cascade forever - true for everything else,
        # harmless for a non-splitter, which never reads it.
        self.split_count = split_count
        self.split_hp_fraction = split_hp_fraction
        self.can_split = can_split
        # AI_SUMMONER's static config - same "set once at spawn" shape as
        # split_count/split_hp_fraction above.
        self.summon_entity_id = summon_entity_id
        self.summon_interval = summon_interval
        self.summon_max_active = summon_max_active
        # AI_SUMMONER's *live* state - summon_cooldown counts down to the
        # next summon attempt (0 means ready now; see
        # Engine._maybe_summon), summoned_children tracks this specific
        # entity's own still-living summons for summon_max_active's cap.
        # Harmless and unused for anything that isn't a summoner.
        self.summon_cooldown = 0
        self.summoned_children: list[Entity] = []
        # AI_CHARGER's static config, same "omit-friendly, engine-level
        # default" shape as alert_radius/flee_hp_pct above.
        self.charge_range = charge_range
        self.charge_attack_bonus = charge_attack_bonus
        # AI_CHARGER's *live* state - True for exactly one turn right after
        # a charge lands a hit (see Engine._charge/_perform_ai), during
        # which this entity skips its action entirely instead of acting.
        # Harmless and unused for anything that isn't a charger.
        self.charge_recovering = False
        # A player-only live counter (see engine/actions.py's UseItemAction
        # "water_walking" branch, Engine._tick_water_walking): turns left in
        # which MovementAction will let this entity cross deep_water/sea.
        # Harmless and unread on anything but the player, same "set
        # unconditionally, only ever matters for one entity" shape as
        # selected_potion_kind below.
        self.water_walking_turns_remaining = 0
        # AI_TERRITORIAL's static config, same "omit-friendly, engine-level
        # default" shape as alert_radius/flee_hp_pct above.
        self.territory_radius = territory_radius
        # AI_AMBUSHER's static config, same "omit-friendly, engine-level
        # default" shape as charge_attack_bonus above.
        self.ambush_bonus = ambush_bonus
        # AI_SCAVENGER's static config, same "omit-friendly, engine-level
        # default" shape as charge_range/charge_attack_bonus above - see
        # Engine._scavenge_from_death.
        self.scavenge_radius = scavenge_radius
        self.scavenge_heal_fraction = scavenge_heal_fraction
        # AI_MIMIC's static config, same "omit-friendly, engine-level
        # default" shape as ambush_bonus above.
        self.mimic_bonus = mimic_bonus
        # AI_MIMIC's *live* state - True for exactly one turn right after
        # PickupAction's reveal (see engine/actions.py), during which
        # Engine._perform_ai's own AI_MIMIC branch skips the ordinary
        # chase/attack so a mimic doesn't land two hits in the same turn
        # it's revealed - the reveal-strike already spent it, the same
        # "special action replaces the normal one" principle
        # AI_SUMMONER/AI_AMBUSHER already established. Harmless and unused
        # for anything that isn't a mimic.
        self.just_revealed = False
        # AI_PACK_HUNTER's *live* bonus - unlike the static config above,
        # this is recomputed by Engine._perform_ai every time this entity
        # acts (see Engine._has_nearby_ally), immediately before it
        # attacks, since "is an ally nearby right now" depends on the
        # whole map's current entity positions, not anything Entity itself
        # can compute. Defaults to 0 and is harmless for every entity that
        # isn't AI_PACK_HUNTER, which never touches it.
        self.pack_bonus_active = 0
        self.stationary = stationary
        self.description = description
        # The line the Talk action shows for this specific entity (see
        # Engine.talk_to_adjacent), and the catalog id it was spawned from
        # (e.g. "village_chief") - the latter is how the quest system
        # identifies *which* NPC was talked to, since display names aren't
        # guaranteed unique/stable the way catalog ids are.
        self.dialogue = dialogue
        # World-state-reactive dialogue overrides, checked in list order
        # against QuestLog.world_flags (see Engine.talk_to_adjacent) -
        # takes priority over both self.dialogue and any active
        # QuestLog.followup_dialogue line. Defensively copied, same
        # reasoning as shop_inventory below.
        self.flag_dialogue: list[FlagDialogue] = list(flag_dialogue) if flag_dialogue is not None else []
        # Catalog item ids this entity sells, if any - empty means "not a
        # shopkeeper" (see Engine.adjacent_shopkeeper). Defensively copied so
        # every spawned Entity gets its own list, never aliasing the
        # catalog's EntityDef.shop_inventory.
        self.shop_inventory: list[str] = list(shop_inventory) if shop_inventory is not None else []
        # XP granted to the player when this entity dies (see
        # Engine.on_entity_death) - 0 means no reward. Only ever nonzero on
        # a hostile monster (content/loader.py's load_catalog enforces
        # this at content-load time).
        self.xp_reward = xp_reward
        # Catalog perk ids this entity teaches, if any - empty means "not a
        # trainer" (see Engine.adjacent_trainer). Defensively copied, same
        # reasoning as shop_inventory above.
        self.trainer_perks: list[str] = list(trainer_perks) if trainer_perks is not None else []
        self.entity_id = entity_id
        self.inventory: list[Entity] = []
        # The Entity currently equipped in each slot (so its name/bonus stay
        # available), not just a bare number - see effective_attack/defense.
        self.equipped_weapon = equipped_weapon
        self.equipped_armor = equipped_armor
        self.equipped_ranged_weapon = equipped_ranged_weapon
        # The fourth equipment slot - a passive, non-flat-stat rate bonus
        # (see ItemEffect.trinket_effect/trinket_bonus, engine/combat.py's
        # _trinket_bonus, Engine._award_xp). Never touches
        # effective_attack/defense/ranged_attack - that's the whole point
        # of a trinket versus a weapon/armor/ranged item.
        self.equipped_trinket = equipped_trinket
        # A scalar player stat, not a held item - collected gold never enters
        # inventory (see PickupAction._collect_gold). Named asymmetrically
        # from ItemEffect.gold_amount on purpose, matching how is_key/key_id
        # already don't mirror 1:1 between the two classes.
        self.gold = gold
        # A spendable currency separate from gold, earned from kills/quests/
        # landmark discoveries and spent on perks (see Engine._award_xp,
        # Engine.learn_perk) - a player stat only, always 0 on a monster/NPC.
        self.xp = xp
        # Perk catalog ids already learned, permanently - never repurchased
        # (see Engine.learn_perk). Defensively copied, same reasoning as
        # shop_inventory/trainer_perks above.
        self.learned_perk_ids: set[str] = set(learned_perk_ids) if learned_perk_ids is not None else set()
        # Remaining cooldown units (hours or turns, per that skill's own
        # PerkDef.skill_cooldown_kind) for a learned active-skill perk,
        # keyed by perk_id - absent or <= 0 means ready to use (see
        # Engine.use_skill, Engine._tick_skill_cooldowns/
        # _advance_world_clock). Defensively copied, same reasoning as
        # learned_perk_ids above.
        self.skill_cooldowns: dict[str, int] = dict(skill_cooldowns) if skill_cooldowns is not None else {}
        # Which potion kind UseItemAction drinks (see POTION_KINDS/potion_kind) -
        # lives here rather than on Engine because the player Entity instance
        # itself is what survives every dungeon-to-dungeon hand-off unchanged
        # (depart_player/arrive_player pass the same instance).
        self.selected_potion_kind = POTION_KINDS[0]
        # Hotbar assignment for a learned active-skill perk (see
        # Engine.assign_skill_slot, engine/actions.py's UseSkillSlotAction)
        # - key "1".."4" in the graphical client. None means unassigned.
        # Same "lives on the surviving player Entity, not Engine" reasoning
        # as selected_potion_kind above; harmless and unread on a monster.
        self.skill_slots: list[str | None] = [None, None, None, None]
        # Hotbar assignment for a potion kind (see Engine.assign_potion_slot,
        # engine/actions.py's UsePotionSlotAction) - key "5".."7". One more
        # slot than POTION_KINDS has entries today, same "room to grow"
        # reasoning as the 4 skill slots above having only 2 skills to fill
        # them so far. Defaults to today's only two kinds, in POTION_KINDS
        # order, so a fresh player's quick-slots work with no setup.
        self.potion_slots: list[str | None] = [POTION_KINDS[0], POTION_KINDS[1], None]

    @property
    def is_alive(self) -> bool:
        return self.fighter is not None and self.fighter.hp > 0

    @property
    def _weaken_penalty(self) -> int:
        """The live attack reduction from an active "weaken" affliction, if
        any - shared by effective_attack/effective_ranged_attack below,
        since both derive from the same fighter.attack base (see
        effective_ranged_attack's own docstring precedent) and a weaker
        swing should weaken the aim just as much as the blow."""
        if self.fighter is None:
            return 0
        weaken = self.fighter.active_effects.get("weaken")
        return weaken.potency if weaken else 0

    @property
    def _exposed_penalty(self) -> int:
        """The live defense reduction from an active "exposed" affliction,
        if any - weaken's exact shape (_weaken_penalty above), just read
        from a separate active_effects key and subtracted from
        effective_defense instead of effective_attack/
        effective_ranged_attack. See EFFECT_EXPOSED (content/schema.py),
        Guard Break's own active-skill mechanic (engine/engine.py's
        use_skill)."""
        if self.fighter is None:
            return 0
        exposed = self.fighter.active_effects.get("exposed")
        return exposed.potency if exposed else 0

    @property
    def _vigor_bonus(self) -> int:
        """The live attack/defense bonus from an active "vigor" buff, if
        any - see Fighter.active_buffs, Elixir of Vigor. Added to both
        effective_attack and effective_defense below, mirroring
        _weaken_penalty's shape but as a bonus, not a subtraction."""
        if self.fighter is None:
            return 0
        vigor = self.fighter.active_buffs.get(BUFF_VIGOR)
        return vigor.potency if vigor else 0

    @property
    def is_enraged(self) -> bool:
        """True once this entity's own hp fraction has dropped to/below
        its enrage threshold - AI_ENRAGE's whole hook (see
        engine/engine.py's _perform_ai AI_ENRAGE branch, engine/combat.py's
        berserk-hit message). Computed live off current hp rather than a
        sticky flag, so effective_attack (and the message) stay correct
        even if this entity is ever healed back above the threshold."""
        if self.ai != AI_ENRAGE or self.fighter is None or self.fighter.max_hp <= 0:
            return False
        threshold = self.enrage_hp_pct or DEFAULT_ENRAGE_HP_PCT
        return self.fighter.hp / self.fighter.max_hp <= threshold

    @property
    def effective_attack(self) -> int:
        base = self.fighter.attack if self.fighter else 0
        bonus = self.equipped_weapon.item.attack_bonus if self.equipped_weapon else None
        enrage_bonus = (self.enrage_attack_bonus or DEFAULT_ENRAGE_ATTACK_BONUS) if self.is_enraged else 0
        return max(
            0, base + (bonus or 0) + enrage_bonus + self.pack_bonus_active + self._vigor_bonus - self._weaken_penalty
        )

    @property
    def effective_defense(self) -> int:
        base = self.fighter.defense if self.fighter else 0
        bonus = self.equipped_armor.item.defense_bonus if self.equipped_armor else None
        return max(0, base + (bonus or 0) + self._vigor_bonus - self._exposed_penalty)

    @property
    def effective_ranged_attack(self) -> int:
        base = self.fighter.attack if self.fighter else 0
        perk_bonus = self.fighter.perk_ranged_attack_bonus if self.fighter else 0
        weapon_bonus = (
            self.equipped_ranged_weapon.item.ranged_attack_bonus
            if self.equipped_ranged_weapon
            else None
        )
        return max(0, base + perk_bonus + (weapon_bonus or 0) - self._weaken_penalty)

    def __repr__(self) -> str:
        return f"Entity({self.name!r} at ({self.x},{self.y}))"
