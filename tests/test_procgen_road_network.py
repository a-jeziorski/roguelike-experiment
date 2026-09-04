from tools.procgen.base import connected_component
from tools.procgen.road_network import generate


def test_generate_respects_requested_dimensions():
    grid = generate(seed=1, width=40, height=25)
    assert grid.width == 40
    assert grid.height == 25
    assert len(grid.cells) == 25
    assert all(len(row) == 40 for row in grid.cells)


def test_generate_only_uses_base_and_road_kinds_by_default():
    grid = generate(seed=1, width=50, height=50)
    used = {tile for row in grid.cells for tile in row}
    assert used <= {"plains", "road"}


def test_generate_is_deterministic_for_the_same_seed():
    a = generate(seed=9, width=40, height=40)
    b = generate(seed=9, width=40, height=40)
    assert a.cells == b.cells


def test_road_network_is_connected_from_the_center():
    """A road network's whole point is one continuous skeleton grown from
    the center - every road tile must be reachable from the center along
    other road tiles, not a scatter of disconnected segments."""
    grid = generate(seed=3, width=40, height=30, branch_chance=0.05, max_branches=10)
    cx, cy = grid.width // 2, grid.height // 2
    assert grid.get(cx, cy) == "road"

    road_tiles = {(x, y) for y in range(grid.height) for x in range(grid.width) if grid.get(x, y) == "road"}
    component = connected_component(grid, (cx, cy), walkable=lambda tile: tile == "road")
    assert component == road_tiles


def test_generate_spreads_roads_in_every_direction_from_the_center():
    """One walker starts heading each of N/S/E/W - the network should
    visibly spread outward on every side of the center, not just one or
    two, even once turning/branching is allowed to bend individual
    walkers off their starting heading."""
    grid = generate(seed=1, width=60, height=60)
    cx, cy = grid.width // 2, grid.height // 2
    road_tiles = [(x, y) for y in range(grid.height) for x in range(grid.width) if grid.get(x, y) == "road"]
    assert any(x > cx + 10 for x, y in road_tiles)
    assert any(x < cx - 10 for x, y in road_tiles)
    assert any(y > cy + 10 for x, y in road_tiles)
    assert any(y < cy - 10 for x, y in road_tiles)


def test_custom_base_and_road_kinds_are_honored():
    grid = generate(seed=1, width=20, height=20, base_kind="ashen_plains", road_kind="floor")
    used = {tile for row in grid.cells for tile in row}
    assert used <= {"ashen_plains", "floor"}
