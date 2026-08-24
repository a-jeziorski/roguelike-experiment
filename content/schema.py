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
    deadline_year: int | None = None
    deadline_day: int | None = None
    questgiver_entity_id: str | None = None
    given_message: str = ""
    already_done_message: str = ""
    questgiver_done_dialogue: str = ""
    target_done_dialogue: str = ""
    reward_item_id: str | None = None
    reward_gold_amount: int | None = Field(default=None, gt=0)
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
                    tile=raw.get("tile", "floor"), entity=raw["entity"], description=description,
                    dialogue=raw.get("dialogue"),
                )
            if "item" in raw:
                return cls(tile=raw.get("tile", "floor"), item=raw["item"], description=description)
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
    it on a tile_kinds entry)."""

    sheet: str
    name: str | None = None
    col: int | None = Field(default=None, ge=0)
    row: int | None = Field(default=None, ge=0)
    recolor: bool = False

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
