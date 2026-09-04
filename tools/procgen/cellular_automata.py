"""Cellular automata caves: random noise smoothed into organic, rounded
cave shapes via the classic 4-5 rule. This formalizes the technique
originally applied by hand for Silver Mountain Caves levels 03-05
(docs/content_design_process.md §0ae - "random noise, several wall/floor
smoothing passes, largest-connected-component extraction to guarantee
full reachability") into reusable code.
"""

from __future__ import annotations

import random

from tools.procgen.base import DEFAULT_FLOOR, DEFAULT_WALL, Grid, keep_largest_component


def _count_wall_neighbors(grid: Grid, x: int, y: int) -> int:
    count = 0
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = x + dx, y + dy
            # Out-of-bounds counts as wall - biases the grid's own edges
            # toward walling themselves in, on top of the frame_border a
            # real dungeon build should still apply afterward.
            if not grid.in_bounds(nx, ny) or grid.get(nx, ny) == DEFAULT_WALL:
                count += 1
    return count


def _smooth(grid: Grid) -> None:
    new_cells = [row[:] for row in grid.cells]
    for y in range(grid.height):
        for x in range(grid.width):
            wall_neighbors = _count_wall_neighbors(grid, x, y)
            if grid.get(x, y) == DEFAULT_WALL:
                new_cells[y][x] = DEFAULT_WALL if wall_neighbors >= 4 else DEFAULT_FLOOR
            else:
                new_cells[y][x] = DEFAULT_WALL if wall_neighbors >= 5 else DEFAULT_FLOOR
    grid.cells = new_cells


def generate(
    seed: int,
    width: int,
    height: int,
    fill_prob: float = 0.45,
    smoothing_passes: int = 4,
) -> Grid:
    """Randomly fills each tile as floor with probability `fill_prob`
    (else wall), then runs `smoothing_passes` iterations of the classic
    4-5 rule (a tile becomes wall if it was already wall and at least 4 of
    its 8 neighbors are wall, or if it was floor and at least 5 of its 8
    neighbors are wall - out-of-bounds counts as wall) to round the noise
    into organic cave shapes, then keeps only the largest connected
    component so the result is always fully reachable from itself. Unlike
    most other generators here, `keep_largest_component` is applied
    internally rather than left to the caller, matching the original
    technique's own three-step definition."""
    rng = random.Random(seed)
    grid = Grid.filled(width, height, DEFAULT_WALL)
    for y in range(height):
        for x in range(width):
            grid.set(x, y, DEFAULT_FLOOR if rng.random() < fill_prob else DEFAULT_WALL)

    for _ in range(smoothing_passes):
        _smooth(grid)

    keep_largest_component(grid)
    return grid
