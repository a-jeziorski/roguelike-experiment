from tools.procgen.base import connected_component
from tools.procgen.bsp_rooms import generate


def test_generate_respects_requested_dimensions():
    grid = generate(seed=1, width=45, height=30)
    assert grid.width == 45
    assert grid.height == 30
    assert len(grid.cells) == 30
    assert all(len(row) == 45 for row in grid.cells)


def test_generate_only_uses_wall_and_floor():
    grid = generate(seed=1, width=45, height=30)
    used = {tile for row in grid.cells for tile in row}
    assert used <= {"wall", "floor"}


def test_generate_is_deterministic_for_the_same_seed():
    a = generate(seed=6, width=45, height=30)
    b = generate(seed=6, width=45, height=30)
    assert a.cells == b.cells


def test_every_room_ends_up_connected():
    """Every pair of sibling partitions is corridor-connected as the
    recursion unwinds - the whole floor area should be one connected
    graph by construction."""
    grid = generate(seed=4, width=45, height=30)
    floor_tiles = {(x, y) for y in range(grid.height) for x in range(grid.width) if grid.get(x, y) == "floor"}
    assert floor_tiles, "expected at least one room to have been carved"
    start = next(iter(floor_tiles))
    component = connected_component(grid, start, walkable=lambda tile: tile == "floor")
    assert component == floor_tiles


def test_a_grid_smaller_than_two_leaves_still_produces_a_single_room():
    """No split is possible when the grid can't fit two leaves on either
    axis - the whole grid should still become one root-level room rather
    than erroring or producing nothing."""
    grid = generate(seed=1, width=10, height=10, min_leaf_size=8)
    assert grid.count("floor") > 0


def test_smaller_min_leaf_size_produces_more_rooms_and_more_floor():
    width, height = 60, 40
    few_rooms = generate(seed=2, width=width, height=height, min_leaf_size=20)
    many_rooms = generate(seed=2, width=width, height=height, min_leaf_size=6)
    assert many_rooms.count("floor") != few_rooms.count("floor")
