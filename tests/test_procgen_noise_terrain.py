import pytest

from tools.procgen.base import connected_component
from tools.procgen.noise_terrain import DEFAULT_BAND_KINDS, generate


def test_generate_respects_requested_dimensions():
    grid = generate(seed=1, width=30, height=20)
    assert grid.width == 30
    assert grid.height == 20
    assert len(grid.cells) == 20
    assert all(len(row) == 30 for row in grid.cells)


def test_generate_only_uses_configured_band_kinds():
    grid = generate(seed=1, width=40, height=40)
    used = {tile for row in grid.cells for tile in row}
    assert used <= set(DEFAULT_BAND_KINDS)


def test_generate_is_deterministic_for_the_same_seed():
    a = generate(seed=42, width=25, height=25)
    b = generate(seed=42, width=25, height=25)
    assert a.cells == b.cells


def test_generate_differs_for_different_seeds():
    a = generate(seed=1, width=25, height=25)
    b = generate(seed=2, width=25, height=25)
    assert a.cells != b.cells


def test_generate_produces_a_continuous_field_not_pure_noise():
    """A real terrain field has broad contiguous regions of the same band,
    not a salt-and-pepper scatter - the point of interpolating a lattice
    rather than assigning each cell an independent random value."""
    grid = generate(seed=7, width=60, height=60, scale=20.0)
    walkable_kinds = {"plains", "forest"}
    start = next(
        (x, y)
        for y in range(grid.height)
        for x in range(grid.width)
        if grid.get(x, y) in walkable_kinds
    )
    component = connected_component(
        grid, start, walkable=lambda tile: tile in walkable_kinds
    )
    assert len(component) > 200


def test_band_kinds_length_must_match_thresholds_plus_one():
    with pytest.raises(ValueError):
        generate(seed=1, width=10, height=10, thresholds=[0.5], band_kinds=["a", "b", "c"])
