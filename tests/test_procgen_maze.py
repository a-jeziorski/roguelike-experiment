from tools.procgen.base import connected_component
from tools.procgen.maze import generate


def test_generate_respects_requested_dimensions():
    grid = generate(seed=1, width=21, height=15)
    assert grid.width == 21
    assert grid.height == 15
    assert len(grid.cells) == 15
    assert all(len(row) == 21 for row in grid.cells)


def test_generate_only_uses_wall_and_floor():
    grid = generate(seed=1, width=21, height=15)
    used = {tile for row in grid.cells for tile in row}
    assert used <= {"wall", "floor"}


def test_generate_is_deterministic_for_the_same_seed():
    a = generate(seed=4, width=21, height=15)
    b = generate(seed=4, width=21, height=15)
    assert a.cells == b.cells


def test_generate_is_enclosed_by_a_wall_border():
    grid = generate(seed=1, width=21, height=15)
    assert all(grid.get(x, 0) == "wall" and grid.get(x, grid.height - 1) == "wall" for x in range(grid.width))
    assert all(grid.get(0, y) == "wall" and grid.get(grid.width - 1, y) == "wall" for y in range(grid.height))


def test_every_maze_cell_is_reachable():
    """A recursive-backtracker maze visits every cell by construction -
    the whole carved floor area must be one connected component."""
    grid = generate(seed=2, width=25, height=19)
    floor_tiles = {(x, y) for y in range(grid.height) for x in range(grid.width) if grid.get(x, y) == "floor"}
    start = next(iter(floor_tiles))
    component = connected_component(grid, start, walkable=lambda tile: tile == "floor")
    assert component == floor_tiles


def test_unbraided_maze_is_a_perfect_maze_with_exactly_one_path():
    """braid=0 should produce a spanning tree over the maze cells: exactly
    `cells_x * cells_y - 1` connector tiles (the odd-coordinate tiles
    between two adjacent cells), one fewer than the number of cells -
    the graph-theory signature of a tree (no cycles, fully connected)."""
    width, height = 21, 15
    grid = generate(seed=3, width=width, height=height, braid=0.0)
    cells_x, cells_y = (width - 1) // 2, (height - 1) // 2

    connector_count = 0
    for cy in range(cells_y):
        for cx in range(cells_x):
            tx, ty = 2 * cx + 1, 2 * cy + 1
            if cx + 1 < cells_x and grid.get(tx + 1, ty) == "floor":
                connector_count += 1
            if cy + 1 < cells_y and grid.get(tx, ty + 1) == "floor":
                connector_count += 1

    assert connector_count == cells_x * cells_y - 1


def test_braiding_adds_more_connectors_than_a_perfect_maze():
    width, height = 21, 15
    unbraided = generate(seed=3, width=width, height=height, braid=0.0)
    braided = generate(seed=3, width=width, height=height, braid=1.0)
    assert braided.count("floor") > unbraided.count("floor")
