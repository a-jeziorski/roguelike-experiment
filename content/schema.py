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
    "landmark",
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
# back at all; town_guard doesn't either, until the map-wide hostility flag
# flips (see GameMap.player_attacked_peaceful_npc / Engine._perform_ai's
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

    @field_validator("glyph")
    @classmethod
    def glyph_is_single_char(cls, v: str) -> str:
        if len(v) != 1:
            raise ValueError(f"glyph must be a single character, got {v!r}")
        return v


class ItemDef(BaseModel):
    """An item type, as defined once in data/items.yaml and referenced by id from
    level files."""

    id: str
    name: str
    glyph: str
    color: Color
    heal_amount: int | None = None
    # Gold collected straight into the player's gold stat on pickup (see
    # PickupAction._collect_gold) - never enters inventory. Note this is a
    # trap for Engine.complete_quest, which appends reward_item_id straight
    # into player.inventory: a quest that rewards a gold item would sit
    # there inert instead of incrementing player.gold, since that path never
    # goes through PickupAction's dispatch. No current quest does this.
    gold_amount: int | None = None
    attack_bonus: int | None = None
    defense_bonus: int | None = None
    ranged_attack_bonus: int | None = None
    range: int | None = Field(default=None, gt=0)
    is_key: bool = False
    # An ammo item stacks: one pickup can be worth several shots.
    is_ammo: bool = False
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


class QuestDef(BaseModel):
    """A quest, as defined once in data/quests.yaml. Field-for-field the raw
    authored shape of engine/quest.py's runtime Quest, minus Quest's mutable
    `status` (renamed `starting_status` here - authored intent, "does this
    quest start given or not," not live state that changes as the run
    progresses). engine/quest.py's quest_from_def converts one of these into
    a live Quest; engine/quest.py itself still owns what each trigger *does*
    (QuestLog.check_dungeon_arrival/check_talked_to/check_delivery/
    record_entity_killed) - this model only owns which quest targets what.

    A quest completes via exactly one of four trigger shapes - at most one
    of target_dungeon_id/target_entity_id/target_kill_entity_id/
    target_item_id may be set (enforced below); zero is valid for a quest
    with no completion trigger yet. A fetch quest (target_item_id) always
    needs questgiver_entity_id too, since QuestLog.check_delivery only ever
    completes it by talking to that NPC while holding the item - enforced in
    content/loader.py's load_quests, which also checks every id here
    (questgiver/target/reward) actually exists in the catalog, since that
    needs the catalog and can't be checked at the field level here."""

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
    deadline_year: int | None = None
    deadline_day: int | None = None
    questgiver_entity_id: str | None = None
    given_message: str = ""
    already_done_message: str = ""
    questgiver_done_dialogue: str = ""
    target_done_dialogue: str = ""
    reward_item_id: str | None = None
    reward_shop_discount_pct: float | None = Field(default=None, gt=0, le=1)
    starting_status: QuestStatus = "not_given"
    # Quest log pane override for a fetch quest (target_item_id) while
    # in_progress and the player is actually carrying the target item (not
    # yet delivered) - see Quest.current_description. "" means no override:
    # `description` keeps showing even while carrying the item. Only
    # meaningful alongside target_item_id.
    carrying_item_description: str = ""
    # Quest log pane override once this quest is "completed" - a summary of
    # what happened and what was earned, not just the original pitch. ""
    # falls back to `description`.
    completed_description: str = ""
    # Quest log pane override once this quest is "failed" - only meaningful
    # alongside a deadline (see the validator below), since that's the only
    # way a quest ever fails. "" falls back to `description`.
    failed_description: str = ""

    @model_validator(mode="after")
    def at_most_one_trigger(self) -> "QuestDef":
        triggers = [
            self.target_dungeon_id, self.target_entity_id,
            self.target_kill_entity_id, self.target_item_id,
        ]
        if sum(t is not None for t in triggers) > 1:
            raise ValueError(
                "a quest can set at most one of target_dungeon_id/"
                "target_entity_id/target_kill_entity_id/target_item_id "
                "(ambiguous which completion trigger applies)"
            )
        return self

    @model_validator(mode="after")
    def failed_description_requires_a_deadline(self) -> "QuestDef":
        if self.failed_description and self.deadline_year is None:
            raise ValueError(
                "failed_description is set but there's no deadline - "
                "QuestLog.check_deadlines is the only way a quest ever "
                "fails, so a quest with no deadline_year/deadline_day can "
                "never show it"
            )
        return self

    @model_validator(mode="after")
    def deadline_both_or_neither(self) -> "QuestDef":
        if (self.deadline_year is None) != (self.deadline_day is None):
            raise ValueError("deadline_year and deadline_day must be set together or not at all")
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


class LegendEntry(BaseModel):
    """A normalized legend entry: what tile a symbol represents, and optionally
    which entity/item spawns there, or which level a stairway leads to.

    Level files may write a legend value as a plain tile-type string (e.g. "wall"),
    or as a mapping. Shorthands:
      - {entity: rat} / {item: healing_potion}: a floor tile with that entity/item
        on it.
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

    An `{entity: ...}` mapping may also carry a `dialogue` - the line the
    Talk action shows for *this specific placement*, distinct from
    `description` (which, on an entity mapping, is still a *tile*-level
    look-mode override, not the entity's - see load_level). Don't confuse
    the two: {entity: villager, dialogue: "Well's held up better than most
    things built before the Sundering."} gives this one villager a unique
    line; `description` here would instead override what look-mode says
    about the ground they're standing on.
    """

    tile: TileType
    entity: str | None = None
    item: str | None = None
    next_level: str | None = None
    requires_key: str | None = None
    dungeon_id: str | None = None
    description: str | None = None
    dialogue: str | None = None

    @classmethod
    def from_raw(cls, raw: str | dict) -> "LegendEntry":
        if isinstance(raw, str):
            return cls(tile=raw)
        if isinstance(raw, dict):
            description = raw.get("description")
            if "entity" in raw:
                return cls(
                    tile="floor", entity=raw["entity"], description=description,
                    dialogue=raw.get("dialogue"),
                )
            if "item" in raw:
                return cls(tile="floor", item=raw["item"], description=description)
            if "stairs_down" in raw:
                return cls(tile="stairs_down", next_level=raw["stairs_down"], description=description)
            if "stairs_up" in raw:
                return cls(tile="stairs_up", next_level=raw["stairs_up"], description=description)
            if "door" in raw:
                return cls(tile="door", requires_key=raw["door"], description=description)
            if "dungeon_entrance" in raw:
                return cls(
                    tile="dungeon_entrance", dungeon_id=raw["dungeon_entrance"], description=description
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
            )
        raise ValueError(f"legend entry must be a string or mapping, got {raw!r}")


class LevelDef(BaseModel):
    """A hand-authored level file: an ASCII map plus a legend mapping symbols to
    tiles/entities/items. Stairway destinations live per-symbol in the legend
    (see LegendEntry), not as a single level-wide field, since a level can branch
    into multiple stairways."""

    id: str
    name: str
    map: str
    legend: dict[str, LegendEntry]

    @field_validator("legend", mode="before")
    @classmethod
    def normalize_legend(cls, v: dict) -> dict[str, LegendEntry]:
        return {symbol: LegendEntry.from_raw(raw) for symbol, raw in v.items()}


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
