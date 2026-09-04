"""Wave function collapse: a small constraint-propagation tile solver.

Unlike every other generator in this package, WFC's actual value isn't the
built-in default tileset below (a minimal, always-satisfiable "pillar hall"
demo) - it's that a caller can hand it a tileset built from a specific
dungeon bible's own motif vocabulary (adjacency rules describing which
tiles are allowed to touch which, in which direction) and get output that
obeys those rules everywhere, not just locally. This module owns the
solver; picking good tiles/adjacency for a given bible is the caller's job.
"""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field

from tools.procgen.base import Grid

_DELTA: dict[str, tuple[int, int]] = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}


@dataclass
class TileSpec:
    """One tile's collapse weight and, per direction, the set of tile names
    allowed immediately in that direction. Adjacency should be authored
    symmetrically (if `a.neighbors["N"]` contains `b`, `b.neighbors["S"]`
    should contain `a`) - an asymmetric ruleset is a guaranteed contradiction
    the moment the mismatched pair actually gets placed next to each other,
    which `generate` will burn its whole retry budget rediscovering."""

    weight: float = 1.0
    neighbors: dict[str, set[str]] = field(default_factory=dict)


# A minimal, always-satisfiable demo: floor is the common case, wall tiles
# are pillars that may never touch each other (no direction allows
# wall-adjacent-to-wall) - a real constraint (unlike an unconstrained
# preset, which would just be weighted random noise), simple enough to
# state, and one cellular automata/BSP can't trivially guarantee (isolated
# single-tile columns rather than wall blobs or straight partitions).
DEFAULT_TILESET: dict[str, TileSpec] = {
    "floor": TileSpec(weight=3.0, neighbors={d: {"floor", "wall"} for d in _DELTA}),
    "wall": TileSpec(weight=1.0, neighbors={d: {"floor"} for d in _DELTA}),
}


def _propagate(
    tileset: dict[str, TileSpec],
    width: int, height: int,
    domains: list[list[set[str]]],
    start: tuple[int, int],
    strict: bool,
) -> bool:
    """Worklist constraint propagation from `start`: whenever a cell's
    domain shrinks, every neighbor's domain is re-intersected against what
    that shrunk domain still permits, and any neighbor that shrinks as a
    result is queued in turn. In strict mode, a domain reduced to empty is
    a contradiction and aborts (returns False) - the caller retries the
    whole grid with a new seed. In non-strict mode (the last-resort
    fallback after every retry has been exhausted), an empty domain is
    instead reset to a single fixed fallback tile so generation can always
    finish, at the cost of a local rule violation right at that cell."""
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for d, (dx, dy) in _DELTA.items():
            nx, ny = x + dx, y + dy
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            allowed: set[str] = set()
            for tile in domains[y][x]:
                allowed |= tileset[tile].neighbors.get(d, set())
            new_domain = domains[ny][nx] & allowed
            if not new_domain:
                if strict:
                    return False
                new_domain = {min(tileset)}
            if new_domain != domains[ny][nx]:
                domains[ny][nx] = new_domain
                queue.append((nx, ny))
    return True


def _run_once(
    rng: random.Random,
    tileset: dict[str, TileSpec],
    width: int, height: int,
    strict: bool,
) -> list[list[str]] | None:
    tile_names = list(tileset.keys())
    domains: list[list[set[str]]] = [[set(tile_names) for _ in range(width)] for _ in range(height)]

    while True:
        best_len: int | None = None
        candidates: list[tuple[int, int]] = []
        for y in range(height):
            for x in range(width):
                n = len(domains[y][x])
                if n == 0:
                    return None
                if n > 1 and (best_len is None or n < best_len):
                    best_len, candidates = n, [(x, y)]
                elif n > 1 and n == best_len:
                    candidates.append((x, y))
        if not candidates:
            break

        x, y = rng.choice(candidates)
        options = list(domains[y][x])
        chosen = rng.choices(options, weights=[tileset[o].weight for o in options], k=1)[0]
        domains[y][x] = {chosen}
        if not _propagate(tileset, width, height, domains, (x, y), strict):
            return None

    return [[next(iter(domains[y][x])) for x in range(width)] for y in range(height)]


def generate(
    seed: int,
    width: int,
    height: int,
    tileset: dict[str, TileSpec] | None = None,
    max_retries: int = 20,
) -> Grid:
    """Collapses a `width`x`height` grid against `tileset`'s adjacency
    rules (default: DEFAULT_TILESET). Retries with a fresh derived seed up
    to `max_retries` times on contradiction; if every attempt contradicts,
    falls back to a non-strict run that always terminates (see
    `_propagate`'s non-strict mode) rather than raising."""
    tileset = DEFAULT_TILESET if tileset is None else tileset
    rng = random.Random(seed)

    for _ in range(max_retries):
        result = _run_once(rng, tileset, width, height, strict=True)
        if result is not None:
            break
    else:
        result = _run_once(rng, tileset, width, height, strict=False)

    grid = Grid.filled(width, height, result[0][0])
    for y in range(height):
        for x in range(width):
            grid.set(x, y, result[y][x])
    return grid
