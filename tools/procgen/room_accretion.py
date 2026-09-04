"""Room accretion: scatter random-sized rectangular rooms at random
positions via rejection sampling, connecting each newly-placed room to
its nearest already-placed room. Unlike BSP (a partition tree) or Voronoi
(a raster diagram), room placement here isn't derived from any underlying
subdivision of the grid - rooms land wherever they happen to fit, so
spacing and arrangement are irregular rather than following a hidden
structure.
"""

from __future__ import annotations

import random

from tools.procgen.base import DEFAULT_WALL, Grid, carve_l_corridor, carve_room

_Room = tuple[int, int, int, int]  # x, y, w, h


def _overlaps(a: _Room, b: _Room, buffer: int) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return not (
        ax + aw + buffer <= bx or bx + bw + buffer <= ax
        or ay + ah + buffer <= by or by + bh + buffer <= ay
    )


def generate(
    seed: int,
    width: int,
    height: int,
    min_room_size: int = 4,
    max_room_size: int = 10,
    buffer: int = 1,
    num_attempts: int = 200,
) -> Grid:
    """Attempts `num_attempts` random room placements (uniform random size
    in `[min_room_size, max_room_size]` per axis, uniform random position
    with a 1-tile margin from the grid edge), accepting a candidate only
    if it doesn't overlap any already-placed room plus a `buffer`-tile gap
    (rejection sampling - most attempts near the end fail as the grid
    fills up, which is expected and fine). Each accepted room is
    corridor-connected (`carve_l_corridor`, center to center) to whichever
    already-placed room is nearest, so the result is always one connected
    graph - never isolated rooms - by construction."""
    rng = random.Random(seed)
    grid = Grid.filled(width, height, DEFAULT_WALL)
    rooms: list[_Room] = []
    centers: list[tuple[int, int]] = []

    for _ in range(num_attempts):
        w = rng.randint(min_room_size, max_room_size)
        h = rng.randint(min_room_size, max_room_size)
        if width - w - 2 < 1 or height - h - 2 < 1:
            continue
        x = rng.randint(1, width - w - 1)
        y = rng.randint(1, height - h - 1)
        candidate: _Room = (x, y, w, h)
        if any(_overlaps(candidate, room, buffer) for room in rooms):
            continue

        carve_room(grid, x, y, w, h)
        center = (x + w // 2, y + h // 2)
        if centers:
            nearest = min(centers, key=lambda c: (c[0] - center[0]) ** 2 + (c[1] - center[1]) ** 2)
            carve_l_corridor(grid, center[0], center[1], nearest[0], nearest[1], rng)
        rooms.append(candidate)
        centers.append(center)

    return grid
