"""Voronoi region partitioning: scatter seed points, raster-assign every
cell to its nearest seed, and read the resulting regions as rooms - a
district/region layout rather than a hand-shaped room-and-corridor
dungeon. No third-party computational-geometry library: brute-force
nearest-seed distance is fine at level-grid sizes, and none is in
requirements.txt.
"""

from __future__ import annotations

import random

from tools.procgen.base import DEFAULT_FLOOR, DEFAULT_WALL, Grid, carve_l_corridor


def _nearest_seed(x: int, y: int, seeds: list[tuple[int, int]]) -> int:
    best_index, best_dist = 0, None
    for i, (sx, sy) in enumerate(seeds):
        dist = (sx - x) ** 2 + (sy - y) ** 2
        if best_dist is None or dist < best_dist:
            best_dist, best_index = dist, i
    return best_index


def generate(
    seed: int,
    width: int,
    height: int,
    num_regions: int = 8,
    wall_margin: int = 2,
) -> Grid:
    """Scatters `num_regions` seed points, assigns every cell to its
    nearest one (a raster Voronoi diagram), then erodes a `wall_margin`-
    tile buffer around every region boundary to `wall` - what's left of
    each region reads as a distinct room, walled off from its neighbors.
    Every pair of regions whose cells actually touch (share an un-eroded
    boundary) is then connected seed-to-seed via `carve_l_corridor`, so
    the whole layout stays one connected graph rather than isolated
    islands."""
    rng = random.Random(seed)
    seeds = [(rng.randrange(width), rng.randrange(height)) for _ in range(num_regions)]

    region_of = [[_nearest_seed(x, y, seeds) for x in range(width)] for y in range(height)]

    grid = Grid.filled(width, height, DEFAULT_WALL)
    for y in range(height):
        for x in range(width):
            own = region_of[y][x]
            near_boundary = any(
                grid.in_bounds(x + dx, y + dy) and region_of[y + dy][x + dx] != own
                for dy in range(-wall_margin, wall_margin + 1)
                for dx in range(-wall_margin, wall_margin + 1)
            )
            if not near_boundary:
                grid.set(x, y, DEFAULT_FLOOR)

    adjacent_pairs: set[tuple[int, int]] = set()
    for y in range(height):
        for x in range(width):
            own = region_of[y][x]
            for dx, dy in ((1, 0), (0, 1)):
                nx, ny = x + dx, y + dy
                if grid.in_bounds(nx, ny) and region_of[ny][nx] != own:
                    adjacent_pairs.add(tuple(sorted((own, region_of[ny][nx]))))

    for a, b in adjacent_pairs:
        ax, ay = seeds[a]
        bx, by = seeds[b]
        carve_l_corridor(grid, ax, ay, bx, by, rng)

    return grid
