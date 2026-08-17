"""Pydantic models for hand-authored content: monster/item catalogs and level files.

These models describe the *raw* shape of the YAML files as a human would write them.
Cross-referential checks (does this entity id exist in the catalog, is there exactly
one player start, etc.) happen in loader.py, since they require the catalog and the
level to be considered together.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

TileType = Literal["wall", "floor", "stairs_down", "player_start"]

Color = tuple[int, int, int]


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
    ai: str = "hostile_basic"
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
    description: str = ""

    @field_validator("glyph")
    @classmethod
    def glyph_is_single_char(cls, v: str) -> str:
        if len(v) != 1:
            raise ValueError(f"glyph must be a single character, got {v!r}")
        return v


class LegendEntry(BaseModel):
    """A normalized legend entry: what tile a symbol represents, and optionally
    which entity/item spawns there.

    Level files may write a legend value as a plain tile-type string (e.g. "wall"),
    or as a mapping referencing an entity/item by id (e.g. {entity: rat}), which
    implicitly means "floor tile with this entity standing on it".
    """

    tile: TileType
    entity: str | None = None
    item: str | None = None

    @classmethod
    def from_raw(cls, raw: str | dict) -> "LegendEntry":
        if isinstance(raw, str):
            return cls(tile=raw)
        if isinstance(raw, dict):
            tile = raw.get("tile", "floor")
            return cls(tile=tile, entity=raw.get("entity"), item=raw.get("item"))
        raise ValueError(f"legend entry must be a string or mapping, got {raw!r}")


class LevelDef(BaseModel):
    """A hand-authored level file: an ASCII map plus a legend mapping symbols to
    tiles/entities/items."""

    id: str
    name: str
    next_level: str | None = None
    map: str
    legend: dict[str, LegendEntry]

    @field_validator("legend", mode="before")
    @classmethod
    def normalize_legend(cls, v: dict) -> dict[str, LegendEntry]:
        return {symbol: LegendEntry.from_raw(raw) for symbol, raw in v.items()}
