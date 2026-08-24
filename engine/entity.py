"""World-object model: the player, monsters, and items as they exist in a running
game (as opposed to content.schema, which describes how they're *defined* in
content files)."""

from __future__ import annotations

from dataclasses import dataclass

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
        shop_inventory: list[str] | None = None,
        entity_id: str = "",
        equipped_weapon: "Entity | None" = None,
        equipped_armor: "Entity | None" = None,
        equipped_ranged_weapon: "Entity | None" = None,
        gold: int = 0,
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
        # Catalog item ids this entity sells, if any - empty means "not a
        # shopkeeper" (see Engine.adjacent_shopkeeper). Defensively copied so
        # every spawned Entity gets its own list, never aliasing the
        # catalog's EntityDef.shop_inventory.
        self.shop_inventory: list[str] = list(shop_inventory) if shop_inventory is not None else []
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
        bonus = (
            self.equipped_ranged_weapon.item.ranged_attack_bonus
            if self.equipped_ranged_weapon
            else None
        )
        return base + (bonus or 0)

    def __repr__(self) -> str:
        return f"Entity({self.name!r} at ({self.x},{self.y}))"
