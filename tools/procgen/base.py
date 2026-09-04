"""Shared infrastructure for the tools/procgen generator library: a common
grid representation, connectivity/carving helpers, and a converter from a
generated Grid to the .lvl YAML format every hand-authored level also uses
(see content/schema.py's LevelDef, content/loader.py's load_level).

Deliberately has no dependency on content/ - the tile-passability table
below is a small duplicate of content/schema.py's TILE_PASSABILITY rather
than an import, so this package stays usable as a standalone grid-generation
library. Kept in sync by tests/test_procgen_base.py's parity check against
the real table.
"""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field

DEFAULT_FLOOR = "floor"
DEFAULT_WALL = "wall"

# Mirrors content/schema.py's TILE_PASSABILITY - only the walkability half,
# since no generator here needs the transparency half. Anything not listed
# is walkable, matching that table's own default.
NOT_WALKABLE = {"wall", "mountain", "sea", "deep_water", "door"}


def is_walkable(tile: str) -> bool:
    return tile not in NOT_WALKABLE


@dataclass
class Grid:
    """cells[y][x] -> a TileType string (content/schema.py). Mutable in
    place; every carving helper below writes directly into `cells`."""

    width: int
    height: int
    cells: list[list[str]]

    @classmethod
    def filled(cls, width: int, height: int, tile: str = DEFAULT_WALL) -> "Grid":
        return cls(width, height, [[tile] * width for _ in range(height)])

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def get(self, x: int, y: int) -> str:
        return self.cells[y][x]

    def set(self, x: int, y: int, tile: str) -> None:
        self.cells[y][x] = tile

    def count(self, tile: str) -> int:
        return sum(row.count(tile) for row in self.cells)


def neighbors8(grid: Grid, x: int, y: int):
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = x + dx, y + dy
            if grid.in_bounds(nx, ny):
                yield nx, ny


def connected_component(
    grid: Grid, start: tuple[int, int], walkable=is_walkable
) -> set[tuple[int, int]]:
    """8-directional flood fill from `start`, matching content/loader.py's
    _reachable_tiles (and the player's real diagonal movement, which never
    blocks cutting a wall's corner)."""
    if not walkable(grid.get(*start)):
        return set()
    seen = {start}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for nx, ny in neighbors8(grid, x, y):
            if (nx, ny) not in seen and walkable(grid.get(nx, ny)):
                seen.add((nx, ny))
                queue.append((nx, ny))
    return seen


def keep_largest_component(
    grid: Grid, fill_tile: str = DEFAULT_WALL, walkable=is_walkable
) -> set[tuple[int, int]]:
    """Finds every walkable tile's connected component, keeps only the
    largest, and overwrites every tile in every other component with
    `fill_tile` - the "largest-connected-component extraction to guarantee
    full reachability" step described for the Silversilk Caves precedent
    (docs/content_design_process.md §0ae). Returns the surviving component;
    raises if the grid has no walkable tile at all."""
    seen_global: set[tuple[int, int]] = set()
    components: list[set[tuple[int, int]]] = []
    for y in range(grid.height):
        for x in range(grid.width):
            if (x, y) in seen_global or not walkable(grid.get(x, y)):
                continue
            comp = connected_component(grid, (x, y), walkable)
            seen_global |= comp
            components.append(comp)

    if not components:
        raise ValueError("grid has no walkable tile - nothing to keep")

    largest = max(components, key=len)
    for comp in components:
        if comp is largest:
            continue
        for (x, y) in comp:
            grid.set(x, y, fill_tile)
    return largest


def _farthest_from(grid: Grid, start: tuple[int, int], walkable) -> tuple[int, int]:
    dist = {start: 0}
    queue = deque([start])
    farthest = start
    while queue:
        x, y = queue.popleft()
        for nx, ny in neighbors8(grid, x, y):
            if (nx, ny) not in dist and walkable(grid.get(nx, ny)):
                dist[(nx, ny)] = dist[(x, y)] + 1
                queue.append((nx, ny))
                if dist[(nx, ny)] > dist[farthest]:
                    farthest = (nx, ny)
    return farthest


def farthest_pair(
    grid: Grid, component: set[tuple[int, int]], walkable=is_walkable
) -> tuple[tuple[int, int], tuple[int, int]]:
    """Approximate graph-diameter endpoints within `component`, via the
    standard double-BFS-sweep heuristic (BFS from an arbitrary tile to find
    a far tile, then BFS from that tile to find the true farthest one) -
    exact for trees, a good approximation for the loopy graphs a cave/room
    grid produces. Mirrors the "entry/exit chosen to maximize both graph
    distance and straight-line spread" placement described for the
    Silversilk Caves precedent (docs/content_design_process.md §0ae)."""
    if not component:
        raise ValueError("component is empty")
    start = next(iter(component))
    a = _farthest_from(grid, start, walkable)
    b = _farthest_from(grid, a, walkable)
    return a, b


def frame_border(grid: Grid, tile: str = DEFAULT_WALL) -> None:
    """Overwrites the outermost ring of the grid with `tile`. Several
    generators (Voronoi regions, wave function collapse, road networks -
    anything that doesn't itself guarantee its output stays clear of the
    edge) can otherwise leave floor sitting right at row/col 0 or
    width-1/height-1, which reads as an unenclosed level rather than a
    real bounded space (a hand-authored level is always walled on every
    side - see e.g. data/dungeons/millhaven/levels/level_01.lvl). Call
    this - before `keep_largest_component`/`farthest_pair`, so entry/exit
    placement never lands on a tile this is about to overwrite - as a
    standard last step whenever assembling a real dungeon file from a
    generated Grid, unless the algorithm already guarantees an enclosed
    result on its own (diffusion-limited aggregation's interior-radius
    cap mostly does, though a walker can still wander to the true edge
    during its random walk before sticking - so even DLA output should
    still be framed to be safe)."""
    for x in range(grid.width):
        grid.set(x, 0, tile)
        grid.set(x, grid.height - 1, tile)
    for y in range(grid.height):
        grid.set(0, y, tile)
        grid.set(grid.width - 1, y, tile)


def carve_room(grid: Grid, x: int, y: int, w: int, h: int, tile: str = DEFAULT_FLOOR) -> None:
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            if grid.in_bounds(xx, yy):
                grid.set(xx, yy, tile)


def carve_h_corridor(grid: Grid, x1: int, x2: int, y: int, tile: str = DEFAULT_FLOOR) -> None:
    for x in range(min(x1, x2), max(x1, x2) + 1):
        if grid.in_bounds(x, y):
            grid.set(x, y, tile)


def carve_v_corridor(grid: Grid, y1: int, y2: int, x: int, tile: str = DEFAULT_FLOOR) -> None:
    for y in range(min(y1, y2), max(y1, y2) + 1):
        if grid.in_bounds(x, y):
            grid.set(x, y, tile)


def carve_l_corridor(
    grid: Grid,
    x1: int, y1: int, x2: int, y2: int,
    rng: random.Random,
    tile: str = DEFAULT_FLOOR,
) -> None:
    """Connects two points with a single right-angle bend, its orientation
    randomized per call. A genuine 90-degree bend (not a diagonal line)
    matters here: a straight corridor doesn't isolate an encounter at
    FOV_RADIUS 8 (the player sees straight through it), but a real bend
    does - see docs/content_design_process.md's corridor-chokepoint
    guidance."""
    if rng.random() < 0.5:
        carve_h_corridor(grid, x1, x2, y1, tile)
        carve_v_corridor(grid, y1, y2, x2, tile)
    else:
        carve_v_corridor(grid, y1, y2, x1, tile)
        carve_h_corridor(grid, x1, x2, y2, tile)


@dataclass
class Overlay:
    """A single special point placed on top of a generated Grid's terrain -
    everything a generator itself never places (see module docstring)."""

    kind: str  # "player_start" | "stairs_down" | "stairs_up"
    next_level: str | None = None
    description: str | None = None


# Preferred legend glyph per tile/overlay kind - matches the glyphs used in
# hand-authored levels (e.g. data/dungeons/silver_mountain_caves/levels)
# where there's no conflict, so generated files read the same way.
_SYMBOL_PREFERENCES: dict[str, str] = {
    "wall": "#", "floor": "F", "player_start": "@", "stairs_down": ">",
    "stairs_up": "<", "door": "+", "road": ".", "plains": ",", "town": "n",
    "forest": "T", "blighted_forest": "Y", "mountain": "^", "sea": "~",
    "deep_water": "~", "landmark": "'", "dunes": "s", "ashen_plains": ";",
    "scoured_ground": ";",
}
_FALLBACK_SYMBOLS = "0123456789ABCDEGHIJKLMNOPQRSTUVWXZbcdefghijklmopqrtuvwxyz"


def _allocate_symbols(kinds: list[str]) -> dict[str, str]:
    used: set[str] = set()
    symbols: dict[str, str] = {}
    fallback = iter(_FALLBACK_SYMBOLS)
    for kind in kinds:
        candidate = _SYMBOL_PREFERENCES.get(kind)
        if candidate is None or candidate in used:
            candidate = next(c for c in fallback if c not in used)
        symbols[kind] = candidate
        used.add(candidate)
    return symbols


def to_lvl_yaml(
    grid: Grid,
    level_id: str,
    name: str,
    overlays: dict[tuple[int, int], Overlay],
    player_start_tile: str = DEFAULT_FLOOR,
    open_boundary: bool = False,
    require_stairs_down: bool = True,
) -> str:
    """Renders a Grid plus its overlays as a .lvl file's text, in the same
    hand-authored style as data/dungeons/*/levels/*.lvl (id/name/map/legend,
    map as a `|` block scalar, every legend symbol double-quoted). The
    result is plain terrain plus player_start/stairs only - no entities,
    items, doors, or decoration; those are a later authoring pass (see
    module docstring)."""
    if require_stairs_down and not any(o.kind == "stairs_down" for o in overlays.values()):
        raise ValueError("overlays must include a stairs_down unless require_stairs_down=False")
    if sum(1 for o in overlays.values() if o.kind == "player_start") != 1:
        raise ValueError("overlays must include exactly one player_start")

    terrain_kinds = sorted({tile for row in grid.cells for tile in row})
    overlay_kinds = sorted({o.kind for o in overlays.values()})
    symbols = _allocate_symbols(terrain_kinds + overlay_kinds)

    rows: list[str] = []
    for y in range(grid.height):
        row_chars = []
        for x in range(grid.width):
            overlay = overlays.get((x, y))
            row_chars.append(symbols[overlay.kind] if overlay is not None else symbols[grid.get(x, y)])
        rows.append("".join(row_chars))
    map_block = "\n".join("  " + r for r in rows)

    legend_lines = []
    for kind in terrain_kinds:
        legend_lines.append(f'  "{symbols[kind]}": {kind}')
    for kind in overlay_kinds:
        matching = [o for o in overlays.values() if o.kind == kind]
        sample = matching[0]
        if kind == "player_start":
            legend_lines.append(f'  "{symbols[kind]}": player_start')
        elif sample.next_level is not None:
            desc = f', description: "{sample.description}"' if sample.description else ""
            legend_lines.append(f'  "{symbols[kind]}": {{ tile: {kind}, next_level: {sample.next_level}{desc} }}')
        else:
            legend_lines.append(f'  "{symbols[kind]}": {kind}')
    legend_block = "\n".join(legend_lines)

    extra_fields = []
    if player_start_tile != DEFAULT_FLOOR:
        extra_fields.append(f"player_start_tile: {player_start_tile}")
    if open_boundary:
        extra_fields.append("open_boundary: true")
    extra_block = ("\n" + "\n".join(extra_fields) + "\n") if extra_fields else "\n"

    return f"id: {level_id}\nname: {name}\n{extra_block}\nmap: |\n{map_block}\n\nlegend:\n{legend_block}\n"
