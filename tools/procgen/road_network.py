"""Agent-based road network generation: a road skeleton grown outward from
a central point, over open ground - the "draw roads first" half of laying
out a settlement. Produces no buildings; footprint placement for those is
a later, bible-driven authoring pass, same as every other generator here.
"""

from __future__ import annotations

import random
from collections import deque

from tools.procgen.base import Grid

_HEADINGS: dict[str, tuple[int, int]] = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}
_LEFT_TURN: dict[str, str] = {"N": "W", "W": "S", "S": "E", "E": "N"}
_RIGHT_TURN: dict[str, str] = {"N": "E", "E": "S", "S": "W", "W": "N"}


def generate(
    seed: int,
    width: int,
    height: int,
    turn_chance: float = 0.06,
    branch_chance: float = 0.03,
    max_branches: int = 10,
    max_segment_length: int = 300,
    base_kind: str = "plains",
    road_kind: str = "road",
) -> Grid:
    """Grows a road network from the grid's center: one walker per cardinal
    direction, each stepping forward (occasionally turning, per
    `turn_chance`) and carving `road_kind` over a `base_kind` field, with a
    `branch_chance` per step of spawning a new walker (a perpendicular
    branch) up to `max_branches` total. Walkers stop at the grid edge or
    after `max_segment_length` steps, whichever comes first."""
    rng = random.Random(seed)
    grid = Grid.filled(width, height, base_kind)
    cx, cy = width // 2, height // 2

    branches_spawned = 0
    queue: deque[tuple[int, int, str]] = deque((cx, cy, heading) for heading in _HEADINGS)
    while queue:
        x, y, heading = queue.popleft()
        for _ in range(max_segment_length):
            if not grid.in_bounds(x, y):
                break
            grid.set(x, y, road_kind)

            if rng.random() < turn_chance:
                heading = rng.choice([_LEFT_TURN[heading], _RIGHT_TURN[heading]])
            if branches_spawned < max_branches and rng.random() < branch_chance:
                branch_heading = rng.choice([_LEFT_TURN[heading], _RIGHT_TURN[heading]])
                queue.append((x, y, branch_heading))
                branches_spawned += 1

            dx, dy = _HEADINGS[heading]
            x, y = x + dx, y + dy

    return grid
