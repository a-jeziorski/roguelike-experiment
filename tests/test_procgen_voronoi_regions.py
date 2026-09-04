from tools.procgen.base import connected_component
from tools.procgen.voronoi_regions import generate


def test_generate_respects_requested_dimensions():
    grid = generate(seed=1, width=40, height=25, num_regions=6)
    assert grid.width == 40
    assert grid.height == 25
    assert len(grid.cells) == 25
    assert all(len(row) == 40 for row in grid.cells)


def test_generate_only_uses_wall_and_floor():
    grid = generate(seed=1, width=40, height=30, num_regions=8)
    used = {tile for row in grid.cells for tile in row}
    assert used <= {"wall", "floor"}


def test_generate_is_deterministic_for_the_same_seed():
    a = generate(seed=5, width=40, height=30, num_regions=8)
    b = generate(seed=5, width=40, height=30, num_regions=8)
    assert a.cells == b.cells


def test_adjacent_regions_end_up_connected():
    """Every pair of regions whose raster cells actually touch gets a
    corridor between their seeds - the whole layout should end up one
    connected graph, not isolated rooms, as long as there's more than one
    region."""
    grid = generate(seed=3, width=45, height=30, num_regions=8)
    floor_tiles = {(x, y) for y in range(grid.height) for x in range(grid.width) if grid.get(x, y) == "floor"}
    start = next(iter(floor_tiles))
    component = connected_component(grid, start, walkable=lambda tile: tile == "floor")
    assert component == floor_tiles


def test_more_regions_produce_more_floor_area_than_a_single_region():
    """Sanity check that region carving actually does something - a
    single-region grid (everything nearest to the same seed, no boundary
    anywhere) should be almost entirely floor; many regions should carve
    visible wall boundaries between them."""
    one_region = generate(seed=1, width=40, height=30, num_regions=1)
    many_regions = generate(seed=1, width=40, height=30, num_regions=12)
    one_region_floor = one_region.count("floor")
    many_regions_floor = many_regions.count("floor")
    assert one_region_floor > many_regions_floor
