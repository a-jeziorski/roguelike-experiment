"""BSP tree rooms & corridors: the classic Rogue-style dungeon - recursively
partition the grid into rectangles down to a minimum leaf size, carve one
room per leaf (with a margin so it doesn't touch its own partition cell's
boundary), then connect sibling partitions with real 90-degree-bend
corridors as the recursion unwinds. Straight walls, rectangular rooms,
structured throughout - the one algorithm in this library whose rooms are
derived from a strict recursive partition, unlike Voronoi's raster diagram
or room accretion's unstructured rejection sampling.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from tools.procgen.base import DEFAULT_WALL, Grid, carve_l_corridor, carve_room


@dataclass
class _Node:
    x: int
    y: int
    w: int
    h: int
    left: "_Node | None" = None
    right: "_Node | None" = None


def _split(node: _Node, rng: random.Random, min_leaf_size: int) -> bool:
    can_split_h = node.h >= min_leaf_size * 2
    can_split_v = node.w >= min_leaf_size * 2
    if not can_split_h and not can_split_v:
        return False
    split_horizontal = rng.random() < 0.5 if (can_split_h and can_split_v) else can_split_h

    if split_horizontal:
        split = rng.randint(min_leaf_size, node.h - min_leaf_size)
        node.left = _Node(node.x, node.y, node.w, split)
        node.right = _Node(node.x, node.y + split, node.w, node.h - split)
    else:
        split = rng.randint(min_leaf_size, node.w - min_leaf_size)
        node.left = _Node(node.x, node.y, split, node.h)
        node.right = _Node(node.x + split, node.y, node.w - split, node.h)
    return True


def _build_tree(node: _Node, rng: random.Random, min_leaf_size: int) -> None:
    if _split(node, rng, min_leaf_size):
        _build_tree(node.left, rng, min_leaf_size)
        _build_tree(node.right, rng, min_leaf_size)


def _carve_leaf_room(node: _Node, grid: Grid, rng: random.Random, room_margin: int) -> tuple[int, int]:
    avail_w = max(1, node.w - 2 * room_margin)
    avail_h = max(1, node.h - 2 * room_margin)
    w = rng.randint(max(1, avail_w - avail_w // 3), avail_w) if avail_w > 1 else avail_w
    h = rng.randint(max(1, avail_h - avail_h // 3), avail_h) if avail_h > 1 else avail_h
    x = node.x + room_margin + rng.randint(0, avail_w - w)
    y = node.y + room_margin + rng.randint(0, avail_h - h)
    carve_room(grid, x, y, w, h)
    return x + w // 2, y + h // 2


def _process(node: _Node, grid: Grid, rng: random.Random, room_margin: int) -> tuple[int, int]:
    if node.left is None:
        return _carve_leaf_room(node, grid, rng, room_margin)
    left_point = _process(node.left, grid, rng, room_margin)
    right_point = _process(node.right, grid, rng, room_margin)
    carve_l_corridor(grid, left_point[0], left_point[1], right_point[0], right_point[1], rng)
    return left_point


def generate(
    seed: int,
    width: int,
    height: int,
    min_leaf_size: int = 8,
    room_margin: int = 1,
) -> Grid:
    """Recursively partitions the grid down to leaves no smaller than
    `min_leaf_size` on either axis (a leaf larger than `2 * min_leaf_size`
    on an axis is always split further; the split axis is chosen randomly
    when both are eligible), carves one room per leaf inset by
    `room_margin` tiles from its partition cell's own boundary, and
    connects every pair of sibling partitions (`carve_l_corridor`, a real
    90-degree bend) as the recursion unwinds - always one connected
    component by construction."""
    rng = random.Random(seed)
    grid = Grid.filled(width, height, DEFAULT_WALL)
    root = _Node(0, 0, width, height)
    _build_tree(root, rng, min_leaf_size)
    _process(root, grid, rng, room_margin)
    return grid
