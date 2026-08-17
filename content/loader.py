"""Loads and validates hand-authored content files.

This is the safety net for the whole "content is hand-edited" workflow: anything
a human (or Claude) can get wrong in a .lvl or catalog file should be caught here,
with a clear message, before the engine ever sees it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import ValidationError

from content.schema import EntityDef, ItemDef, LevelDef

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class ContentValidationError(Exception):
    """Raised when a content file fails validation. Collects every problem found
    rather than stopping at the first, since fixing hand-edited files one error
    at a time is tedious."""

    def __init__(self, source: str, errors: list[str]):
        self.source = source
        self.errors = errors
        message = f"Invalid content in {source}:\n" + "\n".join(
            f"  - {e}" for e in errors
        )
        super().__init__(message)


@dataclass
class Catalog:
    entities: dict[str, EntityDef]
    items: dict[str, ItemDef]


@dataclass
class EntitySpawn:
    x: int
    y: int
    entity: EntityDef


@dataclass
class ItemSpawn:
    x: int
    y: int
    item: ItemDef


@dataclass
class ParsedLevel:
    """A validated level, decoupled from any engine/rendering data structures.
    tiles[y][x] gives the TileType string for that cell."""

    id: str
    name: str
    next_level: str | None
    width: int
    height: int
    tiles: list[list[str]]
    player_start: tuple[int, int]
    entity_spawns: list[EntitySpawn]
    item_spawns: list[ItemSpawn]


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_catalog(
    entities_path: Path = DATA_DIR / "entities.yaml",
    items_path: Path = DATA_DIR / "items.yaml",
) -> Catalog:
    entities: dict[str, EntityDef] = {}
    errors: list[str] = []

    raw_entities = _load_yaml(entities_path) or {}
    for entity_id, raw in raw_entities.items():
        try:
            entities[entity_id] = EntityDef(id=entity_id, **raw)
        except ValidationError as e:
            errors.append(f"entity '{entity_id}': {e}")

    items: dict[str, ItemDef] = {}
    raw_items = _load_yaml(items_path) or {}
    for item_id, raw in raw_items.items():
        try:
            items[item_id] = ItemDef(id=item_id, **raw)
        except ValidationError as e:
            errors.append(f"item '{item_id}': {e}")

    if errors:
        raise ContentValidationError(
            f"{entities_path.name} / {items_path.name}", errors
        )

    return Catalog(entities=entities, items=items)


def load_level(path: Path, catalog: Catalog) -> ParsedLevel:
    raw = _load_yaml(path)
    errors: list[str] = []

    try:
        level = LevelDef(**raw)
    except ValidationError as e:
        raise ContentValidationError(str(path), [str(e)]) from e

    rows = level.map.split("\n")
    # Drop a leading/trailing blank line that YAML block scalars commonly introduce.
    if rows and rows[0] == "":
        rows = rows[1:]
    if rows and rows[-1] == "":
        rows = rows[:-1]
    width = len(rows[0]) if rows else 0
    height = len(rows)

    for y, row in enumerate(rows):
        if len(row) != width:
            errors.append(
                f"map row {y} has length {len(row)}, expected {width} "
                "(all rows must be the same length)"
            )

    used_symbols = {ch for row in rows for ch in row}
    undefined_symbols = used_symbols - set(level.legend.keys())
    for symbol in sorted(undefined_symbols):
        errors.append(f"symbol '{symbol}' used in map but not defined in legend")

    tiles: list[list[str]] = []
    entity_spawns: list[EntitySpawn] = []
    item_spawns: list[ItemSpawn] = []
    player_starts: list[tuple[int, int]] = []

    for y, row in enumerate(rows):
        tile_row: list[str] = []
        for x, symbol in enumerate(row):
            entry = level.legend.get(symbol)
            if entry is None:
                tile_row.append("floor")
                continue

            tile_row.append(entry.tile)

            if entry.tile == "player_start":
                player_starts.append((x, y))

            if entry.entity is not None:
                if entry.entity not in catalog.entities:
                    errors.append(
                        f"legend symbol '{symbol}' references unknown entity "
                        f"'{entry.entity}'"
                    )
                else:
                    entity_spawns.append(
                        EntitySpawn(x=x, y=y, entity=catalog.entities[entry.entity])
                    )

            if entry.item is not None:
                if entry.item not in catalog.items:
                    errors.append(
                        f"legend symbol '{symbol}' references unknown item "
                        f"'{entry.item}'"
                    )
                else:
                    item_spawns.append(
                        ItemSpawn(x=x, y=y, item=catalog.items[entry.item])
                    )
        tiles.append(tile_row)

    if len(player_starts) != 1:
        errors.append(
            f"map must contain exactly one player_start tile, found {len(player_starts)}"
        )

    if errors:
        raise ContentValidationError(str(path), errors)

    return ParsedLevel(
        id=level.id,
        name=level.name,
        next_level=level.next_level,
        width=width,
        height=height,
        tiles=tiles,
        player_start=player_starts[0],
        entity_spawns=entity_spawns,
        item_spawns=item_spawns,
    )
