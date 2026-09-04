import random

import pytest

from content.schema import TILE_PASSABILITY
from tools.procgen.base import (
    Grid,
    Overlay,
    carve_l_corridor,
    carve_room,
    connected_component,
    farthest_pair,
    frame_border,
    is_walkable,
    keep_largest_component,
    to_lvl_yaml,
)


def test_is_walkable_matches_content_schema_tile_passability():
    for kind, (walkable, _transparent) in TILE_PASSABILITY.items():
        assert is_walkable(kind) == walkable, f"{kind} walkability mismatch"


def test_grid_filled_defaults_to_wall():
    grid = Grid.filled(5, 3)
    assert grid.width == 5 and grid.height == 3
    assert all(tile == "wall" for row in grid.cells for tile in row)


def test_carve_room_writes_floor_within_bounds_only():
    grid = Grid.filled(10, 10)
    carve_room(grid, 8, 8, 5, 5)
    assert grid.get(9, 9) == "floor"
    assert grid.get(0, 0) == "wall"


def test_connected_component_is_8_directional():
    grid = Grid.filled(3, 3)
    grid.set(0, 0, "floor")
    grid.set(1, 1, "floor")
    comp = connected_component(grid, (0, 0))
    assert (1, 1) in comp


def test_keep_largest_component_removes_smaller_islands():
    grid = Grid.filled(10, 1)
    for x in (0, 1, 5, 6, 7):
        grid.set(x, 0, "floor")
    largest = keep_largest_component(grid)
    assert largest == {(5, 0), (6, 0), (7, 0)}
    assert grid.get(0, 0) == "wall"
    assert grid.get(1, 0) == "wall"


def test_keep_largest_component_raises_on_no_walkable_tile():
    grid = Grid.filled(4, 4)
    with pytest.raises(ValueError):
        keep_largest_component(grid)


def test_farthest_pair_are_the_two_ends_of_a_corridor():
    grid = Grid.filled(10, 1)
    carve_h_corridor_for_test(grid)
    comp = connected_component(grid, (0, 0))
    a, b = farthest_pair(grid, comp)
    assert {a, b} == {(0, 0), (9, 0)}


def carve_h_corridor_for_test(grid: Grid) -> None:
    for x in range(grid.width):
        grid.set(x, 0, "floor")


def test_carve_l_corridor_connects_both_endpoints():
    grid = Grid.filled(10, 10)
    grid.set(1, 1, "floor")
    grid.set(8, 8, "floor")
    carve_l_corridor(grid, 1, 1, 8, 8, random.Random(0))
    comp = connected_component(grid, (1, 1))
    assert (8, 8) in comp


def test_frame_border_walls_off_every_edge():
    grid = Grid.filled(6, 4, "floor")
    frame_border(grid)
    for x in range(6):
        assert grid.get(x, 0) == "wall"
        assert grid.get(x, 3) == "wall"
    for y in range(4):
        assert grid.get(0, y) == "wall"
        assert grid.get(5, y) == "wall"
    assert grid.get(2, 1) == "floor"  # interior untouched


def test_to_lvl_yaml_round_trips_through_the_real_loader(tmp_path):
    from content.loader import load_level

    grid = Grid.filled(5, 5)
    carve_room(grid, 1, 1, 3, 3)
    overlays = {
        (1, 1): Overlay(kind="player_start"),
        (3, 3): Overlay(kind="stairs_down"),
    }
    text = to_lvl_yaml(grid, "procgen_test", "Procgen Test", overlays)

    path = tmp_path / "level.lvl"
    path.write_text(text, encoding="utf-8")

    class _FakeCatalog:
        entities: dict = {}
        items: dict = {}

    level = load_level(path, _FakeCatalog())
    assert level.player_start == (1, 1)
    assert any(s.kind == "stairs_down" for s in level.stairs)


def test_to_lvl_yaml_requires_exactly_one_player_start():
    grid = Grid.filled(3, 3)
    carve_room(grid, 0, 0, 3, 3)
    overlays = {(0, 0): Overlay(kind="stairs_down")}
    with pytest.raises(ValueError):
        to_lvl_yaml(grid, "x", "X", overlays)


def test_to_lvl_yaml_requires_stairs_down_unless_disabled():
    grid = Grid.filled(3, 3)
    carve_room(grid, 0, 0, 3, 3)
    overlays = {(0, 0): Overlay(kind="player_start")}
    with pytest.raises(ValueError):
        to_lvl_yaml(grid, "x", "X", overlays)
    # Should not raise when stairs_down isn't required (e.g. an open_boundary
    # settlement-style level).
    to_lvl_yaml(grid, "x", "X", overlays, open_boundary=True, require_stairs_down=False)
