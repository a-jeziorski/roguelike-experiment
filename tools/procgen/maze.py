"""Maze generation: a recursive-backtracker random walk over a doubled-
coordinate cell grid, producing a "perfect maze" (exactly one path between
any two cells, no loops) by default, with an optional `braid` pass that
knocks down some dead ends into loops.

`generate`'s `width`/`height` are tile dimensions of the returned Grid,
consistent with every other generator in this package - not a count of
maze cells. Internally, logical maze cells sit at odd tile coordinates
(1, 3, 5, ...) two tiles apart, with the even coordinate between two
linked cells carved as the connecting corridor tile; `(width - 1) // 2`
cells fit along the x axis (likewise for height). Pass an odd width/height
to use every tile; an even one leaves an extra wall column/row along the
far edge, which is harmless (frame_border would enclose it anyway).
"""

from __future__ import annotations

import random

from tools.procgen.base import DEFAULT_FLOOR, DEFAULT_WALL, Grid, frame_border

_DIRECTIONS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def _cell_tile(cx: int, cy: int) -> tuple[int, int]:
    return 2 * cx + 1, 2 * cy + 1


def generate(
    seed: int,
    width: int,
    height: int,
    braid: float = 0.0,
) -> Grid:
    """Carves a perfect maze via randomized depth-first search (visit an
    unvisited neighbor cell, carve the wall between, recurse; backtrack via
    a stack when a cell has no unvisited neighbors left), then optionally
    braids it: for every dead-end cell (exactly one linked neighbor), with
    probability `braid` knocks down the wall to one more random unlinked
    neighbor too, adding a loop (`braid=0` keeps a perfect maze; `braid=1`
    removes nearly every dead end)."""
    rng = random.Random(seed)
    grid = Grid.filled(width, height, DEFAULT_WALL)
    cells_x = max(1, (width - 1) // 2)
    cells_y = max(1, (height - 1) // 2)

    visited = [[False] * cells_x for _ in range(cells_y)]
    tx, ty = _cell_tile(0, 0)
    grid.set(tx, ty, DEFAULT_FLOOR)
    visited[0][0] = True
    stack = [(0, 0)]

    while stack:
        cx, cy = stack[-1]
        unvisited_neighbors = [
            (cx + dx, cy + dy, dx, dy)
            for dx, dy in _DIRECTIONS
            if 0 <= cx + dx < cells_x and 0 <= cy + dy < cells_y and not visited[cy + dy][cx + dx]
        ]
        if not unvisited_neighbors:
            stack.pop()
            continue

        nx, ny, dx, dy = rng.choice(unvisited_neighbors)
        tx, ty = _cell_tile(cx, cy)
        grid.set(tx + dx, ty + dy, DEFAULT_FLOOR)
        ntx, nty = _cell_tile(nx, ny)
        grid.set(ntx, nty, DEFAULT_FLOOR)
        visited[ny][nx] = True
        stack.append((nx, ny))

    if braid > 0:
        for cy in range(cells_y):
            for cx in range(cells_x):
                tx, ty = _cell_tile(cx, cy)
                linked, unlinked = [], []
                for dx, dy in _DIRECTIONS:
                    nx, ny = cx + dx, cy + dy
                    if not (0 <= nx < cells_x and 0 <= ny < cells_y):
                        continue
                    (linked if grid.get(tx + dx, ty + dy) == DEFAULT_FLOOR else unlinked).append((dx, dy))
                if len(linked) == 1 and unlinked and rng.random() < braid:
                    dx, dy = rng.choice(unlinked)
                    grid.set(tx + dx, ty + dy, DEFAULT_FLOOR)

    frame_border(grid)
    return grid
