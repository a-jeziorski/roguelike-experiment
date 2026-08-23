"""Loads and validates hand-authored content files.

This is the safety net for the whole "content is hand-edited" workflow: anything
a human (or Claude) can get wrong in a .lvl or catalog file should be caught here,
with a clear message, before the engine ever sees it.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, get_args

import yaml
from pydantic import ValidationError

from content.schema import (
    PEACEFUL_AI_TYPES,
    TILE_PASSABILITY,
    DungeonDef,
    EntityDef,
    ItemDef,
    LevelDef,
    QuestDef,
    SpriteManifestDef,
    SpriteRef,
    SpriteSheetDef,
    TileType,
)

# Every TileType except player_start actually appears in a runtime GameMap -
# build_game_map always rewrites a player_start cell to "floor" (see
# engine/game_map.py), so it never exists as a live kind for a sprite to
# apply to. This is the valid key set for sprites.yaml's tile_kinds section.
_VALID_SPRITE_TILE_KINDS = set(get_args(TileType)) - {"player_start"}

# The player Entity's entity_id (see engine/game_map.py's build_game_map) -
# reserved rather than a real catalog entry, since the player is hardcoded
# outside entities.yaml. load_sprite_manifest allows this one id under
# sprites.yaml's entities section even though it never appears in
# Catalog.entities, so a sprite can still be authored for it.
PLAYER_ENTITY_ID = "player"

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
    dialogue: str | None = None


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
class TileDescriptionSpawn:
    x: int
    y: int
    text: str  # overrides the tile kind's generic look-mode description


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
    tile_descriptions: list[TileDescriptionSpawn]


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

    for entity_id, edef in entities.items():
        if not edef.shop_inventory:
            continue
        if edef.ai not in PEACEFUL_AI_TYPES:
            errors.append(
                f"entity '{entity_id}': shop_inventory is set but ai is "
                f"'{edef.ai}' - only a peaceful NPC (villager/town_guard) is "
                "ever reachable as a shopkeeper (see PEACEFUL_AI_TYPES), so "
                "this entity's stock could never be sold"
            )
        for item_id in edef.shop_inventory:
            if item_id not in items:
                errors.append(f"entity '{entity_id}': shop_inventory references unknown item '{item_id}'")
            elif items[item_id].cost is None:
                errors.append(
                    f"entity '{entity_id}': shop_inventory item '{item_id}' has "
                    "no cost set - Engine.shop_price treats a missing cost as "
                    "0, so it would sell for free"
                )

    if errors:
        raise ContentValidationError(
            f"{entities_path.name} / {items_path.name}", errors
        )

    return Catalog(entities=entities, items=items)


def load_quests(
    path: Path, catalog: Catalog, known_dungeon_ids: set[str] | None = None,
) -> dict[str, QuestDef]:
    """Loads and validates data/quests.yaml (see content/schema.py's
    QuestDef). `known_dungeon_ids` cross-checks target_dungeon_id the same
    way load_overworld checks dungeon_entrance - pass None to skip (e.g. a
    test not loading the full dungeon registry)."""
    raw = _load_yaml(path) or {}
    quests: dict[str, QuestDef] = {}
    errors: list[str] = []

    for quest_id, fields in raw.items():
        try:
            quest = QuestDef(id=quest_id, **fields)
        except ValidationError as e:
            errors.append(f"quest '{quest_id}': {e}")
            continue

        for label, entity_id in (
            ("questgiver_entity_id", quest.questgiver_entity_id),
            ("target_entity_id", quest.target_entity_id),
            ("target_kill_entity_id", quest.target_kill_entity_id),
            ("reward_shop_discount_entity_id", quest.reward_shop_discount_entity_id),
        ):
            if entity_id is not None and entity_id not in catalog.entities:
                errors.append(f"quest '{quest_id}': {label} references unknown entity '{entity_id}'")

        if (
            quest.reward_shop_discount_entity_id is not None
            and quest.reward_shop_discount_entity_id in catalog.entities
            and not catalog.entities[quest.reward_shop_discount_entity_id].shop_inventory
        ):
            errors.append(
                f"quest '{quest_id}': reward_shop_discount_entity_id "
                f"'{quest.reward_shop_discount_entity_id}' has no shop_inventory - "
                "it isn't reachable as a shopkeeper (see EntityDef.shop_inventory/"
                "Engine.adjacent_shopkeeper), so this discount could never apply to anything"
            )

        for label, item_id in (
            ("target_item_id", quest.target_item_id),
            ("reward_item_id", quest.reward_item_id),
        ):
            if item_id is not None and item_id not in catalog.items:
                errors.append(f"quest '{quest_id}': {label} references unknown item '{item_id}'")

        if quest.target_dungeon_id is not None and known_dungeon_ids is not None:
            if quest.target_dungeon_id not in known_dungeon_ids:
                errors.append(
                    f"quest '{quest_id}': target_dungeon_id references unknown "
                    f"dungeon '{quest.target_dungeon_id}'"
                )

        if quest.target_item_id is not None and quest.questgiver_entity_id is None:
            errors.append(
                f"quest '{quest_id}': target_item_id (a fetch/delivery quest) "
                "requires questgiver_entity_id too - QuestLog.check_delivery "
                "only ever completes a fetch quest by talking to its "
                "questgiver, so one without a questgiver can never complete"
            )

        if quest.target_kill_entity_id is not None and quest.questgiver_entity_id is None:
            errors.append(
                f"quest '{quest_id}': target_kill_entity_id (a kill quest) "
                "requires questgiver_entity_id too - QuestLog.check_kill_report "
                "only ever completes a kill quest by talking to its "
                "questgiver, so one without a questgiver can never complete"
            )

        if quest.target_dungeon_id is not None and quest.questgiver_entity_id is None:
            errors.append(
                f"quest '{quest_id}': target_dungeon_id (a dungeon-arrival "
                "quest) requires questgiver_entity_id too - "
                "QuestLog.check_dungeon_report only ever completes a "
                "dungeon-arrival quest by talking to its questgiver, so one "
                "without a questgiver can never complete"
            )

        if quest.requires_quest_id is not None and quest.requires_quest_id not in raw:
            errors.append(
                f"quest '{quest_id}': requires_quest_id references unknown "
                f"quest '{quest.requires_quest_id}'"
            )

        if quest.requires_quest_id == quest_id:
            errors.append(f"quest '{quest_id}': requires_quest_id can't reference itself")

        if quest.questgiver_entity_id is None and quest.starting_status == "not_given":
            errors.append(
                f"quest '{quest_id}': starting_status is 'not_given' but no "
                "questgiver_entity_id is set - QuestLog.check_questgiver is "
                "the only way a not_given quest is ever granted, so this "
                "quest could never start"
            )

        quests[quest_id] = quest

    if errors:
        raise ContentValidationError(str(path), errors)

    return quests


@dataclass
class SpriteManifest:
    sheets: dict[str, SpriteSheetDef]
    entities: dict[str, SpriteRef]
    items: dict[str, SpriteRef]
    tile_kinds: dict[str, SpriteRef]


def load_sprite_manifest(path: Path, catalog: Catalog) -> SpriteManifest:
    """Loads and validates data/sprites.yaml (see content/schema.py's
    SpriteManifestDef/SpriteRef/SpriteSheetDef). Stays pure-YAML validation
    like every other load_* here - no image/pixel decoding happens in this
    module; actual pixel-bounds checking happens in engine/sprites.py, the
    layer that opens the binary sheet file anyway. Any catalog id or tile
    kind with no entry in the returned manifest simply has no sprite -
    engine/render.py falls back to its authored ASCII glyph, so an empty
    manifest (or one missing entries) is always valid, never an error."""
    raw = _load_yaml(path) or {}
    try:
        parsed = SpriteManifestDef(**raw)
    except ValidationError as e:
        raise ContentValidationError(str(path), [str(e)]) from e

    errors: list[str] = []

    def _check_sheet(section: str, key: str, ref: SpriteRef) -> None:
        if ref.sheet not in parsed.sheets:
            errors.append(f"{section}['{key}']: unknown sheet '{ref.sheet}'")
        elif ref.name is not None and parsed.sheets[ref.sheet].index is None:
            errors.append(
                f"{section}['{key}']: addresses by 'name' but sheet "
                f"'{ref.sheet}' has no 'index' - only a sheet with a name "
                "index can be addressed this way, use col/row instead"
            )

    for entity_id, ref in parsed.entities.items():
        if entity_id != PLAYER_ENTITY_ID and entity_id not in catalog.entities:
            errors.append(f"entities['{entity_id}']: unknown entity id")
        if entity_id == PLAYER_ENTITY_ID and ref.recolor:
            errors.append(
                "entities['player']: recolor is only meaningful for a real "
                "catalog entity (the player has no EntityDef/.color field to "
                "tint toward - it's hardcoded in engine/game_map.py)"
            )
        _check_sheet("entities", entity_id, ref)

    for item_id, ref in parsed.items.items():
        if item_id not in catalog.items:
            errors.append(f"items['{item_id}']: unknown item id")
        _check_sheet("items", item_id, ref)

    for kind, ref in parsed.tile_kinds.items():
        if kind not in _VALID_SPRITE_TILE_KINDS:
            errors.append(f"tile_kinds['{kind}']: not a recognized tile kind")
        if ref.recolor:
            errors.append(
                f"tile_kinds['{kind}']: recolor is only meaningful for "
                "entities/items (a tile kind has no .color field to tint "
                "toward - see EntityDef.color/ItemDef.color)"
            )
        _check_sheet("tile_kinds", kind, ref)

    if errors:
        raise ContentValidationError(str(path), errors)

    return SpriteManifest(
        sheets=parsed.sheets, entities=parsed.entities,
        items=parsed.items, tile_kinds=parsed.tile_kinds,
    )


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


def _reachable_tiles(
    tiles: list[list[str]], width: int, height: int, start: tuple[int, int]
) -> set[tuple[int, int]]:
    """8-directional walkable-tile BFS from `start`, respecting TILE_PASSABILITY.
    A door is impassable in that table by default (its closed starting state),
    so this is exactly "everywhere reachable holding no keys at all" - the
    baseline `_check_doors_enclose_something` compares against. 8-directional
    to match the player's actual movement: `MovementAction` (engine/actions.py)
    never blocks a diagonal step for cutting a wall's corner, so a 4-directional
    BFS here would call a diagonal bypass "enclosed" when it's actually walkable
    in real play."""
    seen = {start}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if not (0 <= nx < width and 0 <= ny < height) or (nx, ny) in seen:
                    continue
                walkable, _ = TILE_PASSABILITY.get(tiles[ny][nx], (True, True))
                if walkable:
                    seen.add((nx, ny))
                    queue.append((nx, ny))
    return seen


def _check_doors_enclose_something(
    tiles: list[list[str]],
    doors: list["DoorSpawn"],
    player_start: tuple[int, int],
    width: int,
    height: int,
) -> list[str]:
    """A locked door only makes sense as a reward gate (see
    docs/content_design_process.md section 3): the point is that whatever is
    directly behind it is unreachable without the key. If every tile next to
    a door is already reachable from player_start with *no* doors open, the
    lock has no effect - almost certainly an accidental second route around
    it, not a deliberate long-way-around design (a real detour still has to
    pass through the door eventually to reach what's immediately behind it)."""
    if not doors:
        return []

    reachable_with_no_keys = _reachable_tiles(tiles, width, height, player_start)

    errors: list[str] = []
    for door in doors:
        far_side = [
            (door.x + dx, door.y + dy)
            for dx in (-1, 0, 1)
            for dy in (-1, 0, 1)
            if not (dx == 0 and dy == 0)
            and 0 <= door.x + dx < width
            and 0 <= door.y + dy < height
            and TILE_PASSABILITY.get(tiles[door.y + dy][door.x + dx], (True, True))[0]
            and (door.x + dx, door.y + dy) not in reachable_with_no_keys
        ]
        if not far_side:
            errors.append(
                f"door at ({door.x}, {door.y}) does not enclose anything - every "
                "tile next to it is already reachable without a key, so the lock "
                "has no effect (an unintended second route around it, not a "
                "deliberate detour)"
            )
    return errors


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
    tile_descriptions: list[TileDescriptionSpawn] = []

    for y, row in enumerate(rows):
        tile_row: list[str] = []
        for x, symbol in enumerate(row):
            entry = level.legend.get(symbol)
            if entry is None:
                tile_row.append("floor")
                continue

            tile_row.append(entry.tile)

            if entry.description:
                tile_descriptions.append(TileDescriptionSpawn(x=x, y=y, text=entry.description))

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
                        EntitySpawn(
                            x=x, y=y, entity=catalog.entities[entry.entity],
                            dialogue=entry.dialogue,
                        )
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

    if len(player_starts) == 1:
        errors.extend(
            _check_doors_enclose_something(tiles, doors, player_starts[0], width, height)
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
        tile_descriptions=tile_descriptions,
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
    tile_descriptions: list[TileDescriptionSpawn] = []

    for y, row in enumerate(rows):
        tile_row: list[str] = []
        for x, symbol in enumerate(row):
            entry = level.legend.get(symbol)
            if entry is None:
                tile_row.append("floor")
                continue

            tile_row.append(entry.tile)

            if entry.description:
                tile_descriptions.append(TileDescriptionSpawn(x=x, y=y, text=entry.description))

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
        tile_descriptions=tile_descriptions,
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
