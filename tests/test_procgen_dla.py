from tools.procgen.base import connected_component
from tools.procgen.dla import generate


def test_generate_respects_requested_dimensions():
    grid = generate(seed=1, width=40, height=25, fill_fraction=0.2)
    assert grid.width == 40
    assert grid.height == 25
    assert len(grid.cells) == 25
    assert all(len(row) == 40 for row in grid.cells)


def test_generate_only_uses_wall_and_floor():
    grid = generate(seed=1, width=40, height=30, fill_fraction=0.25)
    used = {tile for row in grid.cells for tile in row}
    assert used <= {"wall", "floor"}


def test_generate_is_deterministic_for_the_same_seed():
    a = generate(seed=7, width=40, height=30, fill_fraction=0.25)
    b = generate(seed=7, width=40, height=30, fill_fraction=0.25)
    assert a.cells == b.cells


def test_every_floor_tile_is_connected_to_the_seed():
    """DLA grows by sticking to existing floor, so the whole structure
    must be one connected blob rooted at the center seed - never a
    disconnected fleck."""
    grid = generate(seed=3, width=45, height=30, fill_fraction=0.3)
    cx, cy = grid.width // 2, grid.height // 2
    floor_tiles = {(x, y) for y in range(grid.height) for x in range(grid.width) if grid.get(x, y) == "floor"}
    component = connected_component(grid, (cx, cy), walkable=lambda tile: tile == "floor")
    assert component == floor_tiles


def test_generate_terminates_and_makes_progress_toward_the_fill_fraction():
    """With a generous attempt budget, generation should get reasonably
    close to the requested fill fraction, not stop after a handful of
    walkers."""
    width, height = 45, 30
    grid = generate(seed=5, width=width, height=height, fill_fraction=0.3, max_attempts=20000)
    floor_count = grid.count("floor")
    assert floor_count > (width * height) * 0.15
