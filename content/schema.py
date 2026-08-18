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
]

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
AIType = Literal[AI_HOSTILE_BASIC, AI_SLEEPING_GUARD, AI_SKITTISH, AI_RANGED_BASIC]


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
    description: str = ""

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
    attack_bonus: int | None = None
    defense_bonus: int | None = None
    ranged_attack_bonus: int | None = None
    range: int | None = Field(default=None, gt=0)
    is_key: bool = False
    # An ammo item stacks: one pickup can be worth several shots.
    is_ammo: bool = False
    quantity: int = Field(default=1, gt=0)
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
    """

    tile: TileType
    entity: str | None = None
    item: str | None = None
    next_level: str | None = None
    requires_key: str | None = None
    dungeon_id: str | None = None

    @classmethod
    def from_raw(cls, raw: str | dict) -> "LegendEntry":
        if isinstance(raw, str):
            return cls(tile=raw)
        if isinstance(raw, dict):
            if "entity" in raw:
                return cls(tile="floor", entity=raw["entity"])
            if "item" in raw:
                return cls(tile="floor", item=raw["item"])
            if "stairs_down" in raw:
                return cls(tile="stairs_down", next_level=raw["stairs_down"])
            if "stairs_up" in raw:
                return cls(tile="stairs_up", next_level=raw["stairs_up"])
            if "door" in raw:
                return cls(tile="door", requires_key=raw["door"])
            if "dungeon_entrance" in raw:
                return cls(tile="dungeon_entrance", dungeon_id=raw["dungeon_entrance"])
            tile = raw.get("tile", "floor")
            return cls(
                tile=tile,
                entity=raw.get("entity"),
                item=raw.get("item"),
                next_level=raw.get("next_level"),
                requires_key=raw.get("requires_key"),
                dungeon_id=raw.get("dungeon_id"),
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
