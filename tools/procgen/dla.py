"""Diffusion-limited aggregation: branching, organic growth from a single
seed - a random walker spawned near the aggregate's current frontier
sticks the moment it touches existing floor, so structure grows outward
from the center as dendritic branches rather than being carved into a
filled field the way cellular automata/drunkard's walk are.
"""

from __future__ import annotations

import random

from tools.procgen.base import DEFAULT_FLOOR, DEFAULT_WALL, Grid

_STEPS = ((-1, 0), (1, 0), (0, -1), (0, 1))


def _spawn_on_square(rng: random.Random, cx: int, cy: int, radius: int) -> tuple[int, int]:
    """A point on the perimeter of the square of half-width `radius`
    centered at (cx, cy). Spawning here - rather than always on the outer
    grid border - keeps new walkers near the aggregate's actual growing
    frontier. `radius` must be kept strictly inside the grid (see
    `generate`'s `max_interior_radius`): if the spawn square is ever
    clamped flush against the real grid edge, every later spawn on that
    clamped edge lands adjacent to whichever walker stuck there first,
    and the entire edge cascades solid within a few attempts - actual
    edge tiles should only ever fill in from a walker genuinely wandering
    there, not from spawning directly on top of the border."""
    x0, x1 = cx - radius, cx + radius
    y0, y1 = cy - radius, cy + radius
    side = rng.randrange(4)
    if side == 0:
        return rng.randint(x0, x1), y0
    if side == 1:
        return rng.randint(x0, x1), y1
    if side == 2:
        return x0, rng.randint(y0, y1)
    return x1, rng.randint(y0, y1)


def _touches_floor(grid: Grid, x: int, y: int) -> bool:
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = x + dx, y + dy
            if grid.in_bounds(nx, ny) and grid.get(nx, ny) == DEFAULT_FLOOR:
                return True
    return False


def generate(
    seed: int,
    width: int,
    height: int,
    fill_fraction: float = 0.35,
    max_walker_steps: int = 2000,
    max_attempts: int = 20000,
    spawn_margin: int = 6,
) -> Grid:
    """Seeds a single floor tile at the grid's center, then repeatedly
    spawns a random walker on the perimeter of a square `spawn_margin`
    tiles beyond the aggregate's current farthest floor tile (see
    `_spawn_on_square`) that takes a 4-directional random walk (up to
    `max_walker_steps`) until it's 8-directionally adjacent to existing
    floor, at which point it sticks - stopping once `fill_fraction` of the
    grid is floor or `max_attempts` walkers have been spent (a walker that
    wanders off-grid or times out without sticking is simply abandoned,
    not retried indefinitely, so generation always terminates)."""
    rng = random.Random(seed)
    grid = Grid.filled(width, height, DEFAULT_WALL)
    cx, cy = width // 2, height // 2
    grid.set(cx, cy, DEFAULT_FLOOR)
    floor_count = 1
    target = max(1, int(width * height * fill_fraction))
    # Keep every spawn square strictly inside the grid (never flush against
    # the real edge - see _spawn_on_square's docstring for why).
    max_interior_radius = max(0, min(cx, width - 1 - cx, cy, height - 1 - cy) - 1)
    aggregate_radius = 0

    attempts = 0
    while floor_count < target and attempts < max_attempts:
        attempts += 1
        spawn_radius = min(max_interior_radius, aggregate_radius + spawn_margin)
        x, y = _spawn_on_square(rng, cx, cy, spawn_radius)
        if grid.get(x, y) == DEFAULT_FLOOR:
            continue

        for _ in range(max_walker_steps):
            if _touches_floor(grid, x, y):
                grid.set(x, y, DEFAULT_FLOOR)
                floor_count += 1
                aggregate_radius = max(aggregate_radius, abs(x - cx), abs(y - cy))
                break
            dx, dy = rng.choice(_STEPS)
            nx, ny = x + dx, y + dy
            if not grid.in_bounds(nx, ny):
                break
            x, y = nx, ny

    return grid
