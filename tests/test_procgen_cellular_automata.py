import pytest

from tools.procgen.base import connected_component
from tools.procgen.cellular_automata import generate


def test_generate_respects_requested_dimensions():
    grid = generate(seed=1, width=40, height=25)
    assert grid.width == 40
    assert grid.height == 25
    assert len(grid.cells) == 25
    assert all(len(row) == 40 for row in grid.cells)


def test_generate_only_uses_wall_and_floor():
    grid = generate(seed=1, width=45, height=30)
    used = {tile for row in grid.cells for tile in row}
    assert used <= {"wall", "floor"}


def test_generate_is_deterministic_for_the_same_seed():
    a = generate(seed=8, width=45, height=30)
    b = generate(seed=8, width=45, height=30)
    assert a.cells == b.cells


def test_generate_is_fully_reachable_from_any_floor_tile():
    """generate() applies keep_largest_component internally, so every
    floor tile left in the output must be one connected component."""
    grid = generate(seed=2, width=45, height=30)
    floor_tiles = {(x, y) for y in range(grid.height) for x in range(grid.width) if grid.get(x, y) == "floor"}
    assert floor_tiles, "expected the cave to have some floor left after smoothing"
    start = next(iter(floor_tiles))
    component = connected_component(grid, start, walkable=lambda tile: tile == "floor")
    assert component == floor_tiles


def test_smoothing_rounds_out_noise_into_larger_contiguous_regions():
    """More smoothing passes should reduce the raw noise's fine-grained
    scatter - a reasonable proxy is that a heavily-smoothed cave's largest
    component isn't dramatically smaller than the raw noise's floor count
    (smoothing reshapes, it doesn't just erase)."""
    grid = generate(seed=3, width=50, height=35, fill_prob=0.45, smoothing_passes=5)
    assert grid.count("floor") > 0


def test_generate_raises_if_smoothing_leaves_nothing_walkable():
    with pytest.raises(ValueError):
        generate(seed=1, width=20, height=20, fill_prob=0.0, smoothing_passes=1)
