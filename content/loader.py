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
class StairsSpawn:
    x: int
    y: int
    next_level: str | None  # None = terminal stairway (reaching it wins the game)


@dataclass
class DoorSpawn:
    x: int
    y: int
    requires_key: str  # id of the key item that unlocks this door


@dataclass
class ParsedLevel:
    """A validated level, decoupled from any engine/rendering data structures.
    tiles[y][x] gives the TileType string for that cell. A level may have multiple
    stairways (branching), each with its own destination."""

    id: str
    name: str
    width: int
    height: int
    tiles: list[list[str]]
    player_start: tuple[int, int]
    entity_spawns: list[EntitySpawn]
    item_spawns: list[ItemSpawn]
    stairs: list[StairsSpawn]
    doors: list[DoorSpawn]


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


def load_level(
    path: Path, catalog: Catalog, known_level_ids: set[str] | None = None
) -> ParsedLevel:
    """Parses and validates a single level file.

    `known_level_ids`, when provided, is the full set of level ids that exist in
    the dungeon; any stairway's `next_level` not in that set is reported as an
    error. Pass None (the default) to skip that cross-file check, e.g. when
    previewing a single level file in isolation.
    """
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
    stairs: list[StairsSpawn] = []
    doors: list[DoorSpawn] = []

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

            if entry.tile == "stairs_down":
                if entry.next_level is not None and known_level_ids is not None:
                    if entry.next_level not in known_level_ids:
                        errors.append(
                            f"legend symbol '{symbol}' stairs_down references "
                            f"unknown level '{entry.next_level}'"
                        )
                stairs.append(StairsSpawn(x=x, y=y, next_level=entry.next_level))

            if entry.tile == "door":
                key_item = catalog.items.get(entry.requires_key)
                if key_item is None:
                    errors.append(
                        f"legend symbol '{symbol}' door references unknown item "
                        f"'{entry.requires_key}'"
                    )
                elif not key_item.is_key:
                    errors.append(
                        f"legend symbol '{symbol}' door requires '{entry.requires_key}', "
                        "which is not a key item (is_key: true)"
                    )
                else:
                    doors.append(DoorSpawn(x=x, y=y, requires_key=entry.requires_key))

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

    if not stairs:
        errors.append("map must contain at least one stairs_down tile, found 0")

    if errors:
        raise ContentValidationError(str(path), errors)

    return ParsedLevel(
        id=level.id,
        name=level.name,
        width=width,
        height=height,
        tiles=tiles,
        player_start=player_starts[0],
        entity_spawns=entity_spawns,
        item_spawns=item_spawns,
        stairs=stairs,
        doors=doors,
    )


def load_dungeon(levels_dir: Path, catalog: Catalog) -> dict[str, ParsedLevel]:
    """Loads and validates every `.lvl` file in a directory as one connected
    dungeon. Two passes: first collect every level's id (so stairway destinations
    can be checked), then fully validate each level against that known-id set."""
    paths = sorted(levels_dir.glob("*.lvl"))
    if not paths:
        raise ContentValidationError(str(levels_dir), ["no .lvl files found"])

    known_level_ids: set[str] = set()
    errors: list[str] = []
    for path in paths:
        raw = _load_yaml(path)
        level_id = raw.get("id") if isinstance(raw, dict) else None
        if not level_id:
            errors.append(f"{path}: missing required 'id' field")
            continue
        if level_id in known_level_ids:
            errors.append(f"{path}: duplicate level id '{level_id}'")
        known_level_ids.add(level_id)

    if errors:
        raise ContentValidationError(str(levels_dir), errors)

    levels: dict[str, ParsedLevel] = {}
    for path in paths:
        try:
            level = load_level(path, catalog, known_level_ids=known_level_ids)
        except ContentValidationError as e:
            errors.extend(f"{path}: {err}" for err in e.errors)
            continue
        levels[level.id] = level

    if errors:
        raise ContentValidationError(str(levels_dir), errors)

    return levels
