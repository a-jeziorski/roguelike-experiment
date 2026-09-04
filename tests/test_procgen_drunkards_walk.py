from tools.procgen.base import connected_component
from tools.procgen.drunkards_walk import generate


def test_generate_respects_requested_dimensions():
    grid = generate(seed=1, width=40, height=25, fill_fraction=0.2)
    assert grid.width == 40
    assert grid.height == 25
    assert len(grid.cells) == 25
    assert all(len(row) == 40 for row in grid.cells)


def test_generate_only_uses_wall_and_floor():
    grid = generate(seed=1, width=40, height=30, fill_fraction=0.3)
    used = {tile for row in grid.cells for tile in row}
    assert used <= {"wall", "floor"}


def test_generate_is_deterministic_for_the_same_seed():
    a = generate(seed=9, width=40, height=30, fill_fraction=0.3)
    b = generate(seed=9, width=40, height=30, fill_fraction=0.3)
    assert a.cells == b.cells


def test_every_floor_tile_is_connected_to_the_center():
    """Every walker starts on already-carved floor (the center, or a
    random already-carved tile for later walkers) and only ever steps to
    an adjacent tile - the whole structure must be one connected
    component by construction, even with multiple walkers."""
    grid = generate(seed=3, width=45, height=30, fill_fraction=0.35, walker_count=4)
    cx, cy = grid.width // 2, grid.height // 2
    floor_tiles = {(x, y) for y in range(grid.height) for x in range(grid.width) if grid.get(x, y) == "floor"}
    component = connected_component(grid, (cx, cy), walkable=lambda tile: tile == "floor")
    assert component == floor_tiles


def test_generate_gets_reasonably_close_to_the_fill_fraction():
    width, height = 45, 30
    grid = generate(seed=5, width=width, height=height, fill_fraction=0.3, max_steps_per_walker=100000)
    floor_count = grid.count("floor")
    assert floor_count >= (width * height) * 0.25


def test_brush_radius_widens_the_carved_path():
    """A high fill_fraction (never reached in the small step budget used
    here) keeps the walker from stopping early, so the same fixed number
    of steps should carve more floor with a wider brush."""
    width, height = 45, 30
    narrow = generate(seed=2, width=width, height=height, fill_fraction=1.0, max_steps_per_walker=50, brush_radius=0)
    wide = generate(seed=2, width=width, height=height, fill_fraction=1.0, max_steps_per_walker=50, brush_radius=2)
    assert wide.count("floor") > narrow.count("floor")
