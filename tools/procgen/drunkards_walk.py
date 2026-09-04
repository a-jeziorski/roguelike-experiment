"""Drunkard's walk: one or more random walkers carving floor as they go,
producing winding, narrow, irregular tunnels - no straight walls (unlike
BSP/room accretion/maze), no branching dendrite structure (unlike DLA),
no smooth rounded blobs (unlike cellular automata). The simplest of the
generators in this package, and the most obviously "just wandered here."
"""

from __future__ import annotations

import random

from tools.procgen.base import DEFAULT_FLOOR, DEFAULT_WALL, Grid

_STEPS = ((-1, 0), (1, 0), (0, -1), (0, 1))


def generate(
    seed: int,
    width: int,
    height: int,
    fill_fraction: float = 0.4,
    walker_count: int = 1,
    max_steps_per_walker: int = 50000,
    brush_radius: int = 0,
) -> Grid:
    """Carves floor at the grid's center, then runs `walker_count` walkers
    one after another - the first starting at the center, every later one
    starting from a random already-carved floor tile (so the result is
    always one connected component by construction, never disjoint
    tunnels) - each taking a 4-directional random walk, carving floor at
    every step (widened to a `brush_radius`-tile square if set), until
    `fill_fraction` of the grid is floor or that walker's
    `max_steps_per_walker` budget runs out."""
    rng = random.Random(seed)
    grid = Grid.filled(width, height, DEFAULT_WALL)
    cx, cy = width // 2, height // 2
    target = max(1, int(width * height * fill_fraction))
    floor_count = 0

    def carve(x: int, y: int) -> None:
        nonlocal floor_count
        for dx in range(-brush_radius, brush_radius + 1):
            for dy in range(-brush_radius, brush_radius + 1):
                nx, ny = x + dx, y + dy
                if grid.in_bounds(nx, ny) and grid.get(nx, ny) != DEFAULT_FLOOR:
                    grid.set(nx, ny, DEFAULT_FLOOR)
                    floor_count += 1

    carve(cx, cy)

    for walker_index in range(walker_count):
        if floor_count >= target:
            break
        if walker_index == 0:
            x, y = cx, cy
        else:
            floor_tiles = [
                (fx, fy) for fy in range(height) for fx in range(width) if grid.get(fx, fy) == DEFAULT_FLOOR
            ]
            x, y = rng.choice(floor_tiles)

        for _ in range(max_steps_per_walker):
            if floor_count >= target:
                break
            dx, dy = rng.choice(_STEPS)
            nx, ny = x + dx, y + dy
            if grid.in_bounds(nx, ny):
                x, y = nx, ny
            carve(x, y)

    return grid
