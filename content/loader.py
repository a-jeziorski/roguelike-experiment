"""Loads and validates hand-authored content files.

This is the safety net for the whole "content is hand-edited" workflow: anything
a human (or Claude) can get wrong in a .lvl or catalog file should be caught here,
with a clear message, before the engine ever sees it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml
from pydantic import ValidationError

from content.schema import DungeonDef, EntityDef, ItemDef, LevelDef

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
    # None = terminal stairway - reaching it leaves the dungeon and returns to
    # the overworld (either kind can now be terminal: a stairs_down terminal
    # is a dungeon's usual "completed it" exit, a stairs_up terminal is a
    # retreat point near the entrance).
    next_level: str | None
    kind: Literal["stairs_down", "stairs_up"]


@dataclass
class DoorSpawn:
    x: int
    y: int
    requires_key: str  # id of the key item that unlocks this door


@dataclass
class DungeonEntranceSpawn:
    x: int
    y: int
    dungeon_id: str  # overworld-only: a dungeon registry id, not a level id


@dataclass
class ParsedLevel:
    """A validated level, decoupled from any engine/rendering data structures.
    tiles[y][x] gives the TileType string for that cell. A level may have multiple
    stairways (branching), each with its own destination. dungeon_entrances is
    only ever populated for the overworld (see load_overworld) - every dungeon
    level leaves it empty."""

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
    dungeon_entrances: list[DungeonEntranceSpawn]


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


def _parse_map_rows(raw_map: str, legend: dict) -> tuple[list[str], list[str]]:
    """Splits a level/overworld file's raw `map` block into rows and validates
    the purely textual concerns shared by every kind of ASCII map, regardless
    of what the tiles mean: trimming the leading/trailing blank line a YAML
    block scalar commonly introduces, every row being the same width, and
    every symbol used actually being defined in the legend. Returns
    (rows, errors) - what each symbol's tile *means* is caller-specific
    (dungeon vs. overworld), so that dispatch stays in load_level/
    load_overworld rather than here."""
    rows = raw_map.split("\n")
    if rows and rows[0] == "":
        rows = rows[1:]
    if rows and rows[-1] == "":
        rows = rows[:-1]
    width = len(rows[0]) if rows else 0

    errors: list[str] = []
    for y, row in enumerate(rows):
        if len(row) != width:
            errors.append(
                f"map row {y} has length {len(row)}, expected {width} "
                "(all rows must be the same length)"
            )

    used_symbols = {ch for row in rows for ch in row}
    undefined_symbols = used_symbols - set(legend.keys())
    for symbol in sorted(undefined_symbols):
        errors.append(f"symbol '{symbol}' used in map but not defined in legend")

    return rows, errors


def load_level(
    path: Path,
    catalog: Catalog,
    known_level_ids: set[str] | None = None,
    require_stairs_down: bool = True,
) -> ParsedLevel:
    """Parses and validates a single level file.

    `known_level_ids`, when provided, is the full set of level ids that exist in
    the dungeon; any stairway's `next_level` not in that set is reported as an
    error. Pass None (the default) to skip that cross-file check, e.g. when
    previewing a single level file in isolation.

    `require_stairs_down` is False for a peaceful, non-progression dungeon
    (a settlement) - see DungeonDef.requires_stairs_down; every real dungeon
    keeps the default.
    """
    raw = _load_yaml(path)
    errors: list[str] = []

    try:
        level = LevelDef(**raw)
    except ValidationError as e:
        raise ContentValidationError(str(path), [str(e)]) from e

    rows, row_errors = _parse_map_rows(level.map, level.legend)
    errors.extend(row_errors)
    width = len(rows[0]) if rows else 0
    height = len(rows)

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
                stairs.append(
                    StairsSpawn(x=x, y=y, next_level=entry.next_level, kind="stairs_down")
                )

            if entry.tile == "stairs_up":
                if entry.next_level is not None and known_level_ids is not None:
                    if entry.next_level not in known_level_ids:
                        errors.append(
                            f"legend symbol '{symbol}' stairs_up references "
                            f"unknown level '{entry.next_level}'"
                        )
                stairs.append(
                    StairsSpawn(x=x, y=y, next_level=entry.next_level, kind="stairs_up")
                )

            if entry.tile == "dungeon_entrance":
                errors.append(
                    f"legend symbol '{symbol}' is a dungeon_entrance tile, which has no "
                    "meaning inside a dungeon - use a terminal stairs_up to leave instead"
                )

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

    if require_stairs_down:
        if not any(s.kind == "stairs_down" for s in stairs):
            errors.append("map must contain at least one stairs_down tile, found 0")
    elif not stairs:
        errors.append(
            "map has requires_stairs_down: false but contains no stairway "
            "(stairs_up or stairs_down) - there would be no way to leave"
        )

    next_level_targets: dict[str, list[tuple[int, int]]] = {}
    for s in stairs:
        if s.next_level is not None:
            next_level_targets.setdefault(s.next_level, []).append((s.x, s.y))
    for target_id, coords in next_level_targets.items():
        if len(coords) > 1:
            coords_str = " and ".join(f"({x}, {y})" for x, y in coords)
            errors.append(
                f"multiple stairways target level '{target_id}' at {coords_str} - "
                "ambiguous which one is the return path when arriving from that level"
            )

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
        dungeon_entrances=[],
    )


def load_overworld(path: Path, catalog: Catalog, known_dungeon_ids: set[str]) -> ParsedLevel:
    """Parses and validates the overworld file - a single, standalone map (no
    directory of levels, no manifest; there is exactly one overworld). Reuses
    the same ParsedLevel shape as a dungeon level so build_game_map/Engine can
    treat it identically, but its own tile vocabulary is deliberately smaller:
    no entities, items, doors, or stairs (this is not a dungeon), only
    terrain and dungeon_entrance tiles leading into a dungeon registry id
    (not a level id - that's why this doesn't reuse known_level_ids)."""
    raw = _load_yaml(path)
    errors: list[str] = []

    try:
        level = LevelDef(**raw)
    except ValidationError as e:
        raise ContentValidationError(str(path), [str(e)]) from e

    rows, row_errors = _parse_map_rows(level.map, level.legend)
    errors.extend(row_errors)
    width = len(rows[0]) if rows else 0
    height = len(rows)

    tiles: list[list[str]] = []
    player_starts: list[tuple[int, int]] = []
    dungeon_entrances: list[DungeonEntranceSpawn] = []

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

            if entry.tile == "dungeon_entrance":
                if entry.dungeon_id not in known_dungeon_ids:
                    errors.append(
                        f"legend symbol '{symbol}' dungeon_entrance references "
                        f"unknown dungeon '{entry.dungeon_id}'"
                    )
                dungeon_entrances.append(
                    DungeonEntranceSpawn(x=x, y=y, dungeon_id=entry.dungeon_id)
                )

            if entry.tile in ("stairs_down", "stairs_up", "door"):
                errors.append(
                    f"legend symbol '{symbol}' is a {entry.tile} tile, which has no "
                    "meaning on the overworld - use dungeon_entrance instead"
                )

            if entry.entity is not None or entry.item is not None:
                errors.append(
                    f"legend symbol '{symbol}' spawns an entity/item, which has no "
                    "meaning on the overworld - there is no combat or itemization here"
                )
        tiles.append(tile_row)

    if len(player_starts) != 1:
        errors.append(
            f"map must contain exactly one player_start tile, found {len(player_starts)}"
        )

    if not dungeon_entrances:
        errors.append("map must contain at least one dungeon_entrance tile, found 0")

    dungeon_targets: dict[str, list[tuple[int, int]]] = {}
    for entrance in dungeon_entrances:
        dungeon_targets.setdefault(entrance.dungeon_id, []).append((entrance.x, entrance.y))
    for dungeon_id, coords in dungeon_targets.items():
        if len(coords) > 1:
            coords_str = " and ".join(f"({x}, {y})" for x, y in coords)
            errors.append(
                f"multiple dungeon_entrance tiles target dungeon '{dungeon_id}' at "
                f"{coords_str} - ambiguous which one is the return path when leaving it"
            )

    if errors:
        raise ContentValidationError(str(path), errors)

    return ParsedLevel(
        id=level.id,
        name=level.name,
        width=width,
        height=height,
        tiles=tiles,
        player_start=player_starts[0],
        entity_spawns=[],
        item_spawns=[],
        stairs=[],
        doors=[],
        dungeon_entrances=dungeon_entrances,
    )


def load_levels(
    levels_dir: Path, catalog: Catalog, require_stairs_down: bool = True
) -> dict[str, ParsedLevel]:
    """Loads and validates every `.lvl` file in a directory as one connected
    set of levels. Two passes: first collect every level's id (so stairway
    destinations can be checked), then fully validate each level against
    that known-id set. `require_stairs_down` is forwarded to every
    `load_level` call - see its docstring."""
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
            level = load_level(
                path, catalog, known_level_ids=known_level_ids,
                require_stairs_down=require_stairs_down,
            )
        except ContentValidationError as e:
            errors.extend(f"{path}: {err}" for err in e.errors)
            continue
        levels[level.id] = level

    if errors:
        raise ContentValidationError(str(levels_dir), errors)

    return levels


@dataclass
class Dungeon:
    """A validated dungeon: its manifest plus every level it contains."""

    id: str
    name: str
    starting_level: str
    description: str
    inspect_text: str
    requires_stairs_down: bool
    levels: dict[str, ParsedLevel]


def load_dungeon(dungeon_dir: Path, catalog: Catalog) -> Dungeon:
    """Loads one dungeon: its manifest (`dungeon_dir/dungeon.yaml`) plus
    every level under `dungeon_dir/levels/`."""
    manifest_path = dungeon_dir / "dungeon.yaml"
    raw = _load_yaml(manifest_path)
    try:
        manifest = DungeonDef(**(raw or {}))
    except ValidationError as e:
        raise ContentValidationError(str(manifest_path), [str(e)]) from e

    levels = load_levels(
        dungeon_dir / "levels", catalog, require_stairs_down=manifest.requires_stairs_down
    )

    if manifest.starting_level not in levels:
        raise ContentValidationError(
            str(manifest_path),
            [
                f"starting_level '{manifest.starting_level}' is not among "
                "this dungeon's levels"
            ],
        )

    return Dungeon(
        id=manifest.id,
        name=manifest.name,
        starting_level=manifest.starting_level,
        description=manifest.description,
        inspect_text=manifest.inspect_text,
        requires_stairs_down=manifest.requires_stairs_down,
        levels=levels,
    )


def load_dungeon_registry(dungeons_dir: Path, catalog: Catalog) -> dict[str, Dungeon]:
    """Discovers and loads every dungeon under `dungeons_dir` - each an
    immediate subdirectory containing its own `dungeon.yaml` + `levels/`.
    This is what a dungeon-select screen (or a future overworld) would
    enumerate."""
    dungeon_dirs = sorted(p for p in dungeons_dir.iterdir() if p.is_dir())
    if not dungeon_dirs:
        raise ContentValidationError(str(dungeons_dir), ["no dungeon subdirectories found"])

    registry: dict[str, Dungeon] = {}
    errors: list[str] = []
    for dungeon_dir in dungeon_dirs:
        try:
            dungeon = load_dungeon(dungeon_dir, catalog)
        except ContentValidationError as e:
            errors.extend(f"{dungeon_dir}: {err}" for err in e.errors)
            continue
        if dungeon.id in registry:
            errors.append(f"{dungeon_dir}: duplicate dungeon id '{dungeon.id}'")
            continue
        registry[dungeon.id] = dungeon

    if errors:
        raise ContentValidationError(str(dungeons_dir), errors)

    return registry
