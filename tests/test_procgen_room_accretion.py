from tools.procgen.base import connected_component
from tools.procgen.room_accretion import generate


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
    a = generate(seed=6, width=45, height=30)
    b = generate(seed=6, width=45, height=30)
    assert a.cells == b.cells


def test_every_room_ends_up_connected():
    """Each new room is corridor-connected to its nearest already-placed
    room by construction - the whole floor area should be one connected
    graph, never isolated rooms."""
    grid = generate(seed=4, width=45, height=30)
    floor_tiles = {(x, y) for y in range(grid.height) for x in range(grid.width) if grid.get(x, y) == "floor"}
    assert floor_tiles, "expected at least one room to have been placed"
    start = next(iter(floor_tiles))
    component = connected_component(grid, start, walkable=lambda tile: tile == "floor")
    assert component == floor_tiles


def test_overlap_predicate_respects_the_buffer_margin():
    """Sanity check on the rejection-sampling helper the real placement
    loop relies on: two rooms 4 tiles apart (edge to edge) should overlap
    under a 2-tile buffer requirement, but two rooms far apart shouldn't."""
    from tools.procgen.room_accretion import _overlaps

    assert _overlaps((0, 0, 5, 5), (6, 0, 5, 5), buffer=2)
    assert not _overlaps((0, 0, 5, 5), (20, 20, 5, 5), buffer=2)


def test_more_attempts_places_more_floor_up_to_a_point():
    small = generate(seed=1, width=45, height=30, num_attempts=5)
    large = generate(seed=1, width=45, height=30, num_attempts=200)
    assert large.count("floor") > small.count("floor")
