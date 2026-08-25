"""World-object model: the player, monsters, and items as they exist in a running
game (as opposed to content.schema, which describes how they're *defined* in
content files)."""

from __future__ import annotations

from dataclasses import dataclass

from content.schema import FlagDialogue, PerkDef

Color = tuple[int, int, int]

# Draw order when multiple entities could occupy visual space: items under actors.
RENDER_PRIORITY_ITEM = 0
RENDER_PRIORITY_ACTOR = 1
RENDER_PRIORITY_PLAYER = 2


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


# Cycle order for UseItemAction's potion-kind selection (see
# Entity.selected_potion_kind and Engine.cycle_selected_potion_kind).
POTION_KINDS: tuple[str, ...] = ("healing", "teleport")


def potion_kind(item: ItemEffect) -> str | None:
    """Which POTION_KINDS entry this item is, or None if it's not a potion."""
    if item.heal_amount:
        return "healing"
    if item.is_teleport:
        return "teleport"
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
        gold: int = 0,
        xp: int = 0,
        learned_perk_ids: set[str] | None = None,
    ):
        self.x = x
        self.y = y
        self.glyph = glyph
        self.color = color
        self.name = name
        self.blocks_movement = blocks_movement
        self.render_priority = render_priority
        self.fighter = fighter
        self.item = item
        self.ai = ai
        self.alert_radius = alert_radius
        self.flee_hp_pct = flee_hp_pct
        self.ranged_range = ranged_range
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
        # Which potion kind UseItemAction drinks (see POTION_KINDS/potion_kind) -
        # lives here rather than on Engine because the player Entity instance
        # itself is what survives every dungeon-to-dungeon hand-off unchanged
        # (depart_player/arrive_player pass the same instance).
        self.selected_potion_kind = POTION_KINDS[0]

    @property
    def is_alive(self) -> bool:
        return self.fighter is not None and self.fighter.hp > 0

    @property
    def effective_attack(self) -> int:
        base = self.fighter.attack if self.fighter else 0
        bonus = self.equipped_weapon.item.attack_bonus if self.equipped_weapon else None
        return base + (bonus or 0)

    @property
    def effective_defense(self) -> int:
        base = self.fighter.defense if self.fighter else 0
        bonus = self.equipped_armor.item.defense_bonus if self.equipped_armor else None
        return base + (bonus or 0)

    @property
    def effective_ranged_attack(self) -> int:
        base = self.fighter.attack if self.fighter else 0
        perk_bonus = self.fighter.perk_ranged_attack_bonus if self.fighter else 0
        weapon_bonus = (
            self.equipped_ranged_weapon.item.ranged_attack_bonus
            if self.equipped_ranged_weapon
            else None
        )
        return base + perk_bonus + (weapon_bonus or 0)

    def __repr__(self) -> str:
        return f"Entity({self.name!r} at ({self.x},{self.y}))"
