from tools.procgen.wave_function_collapse import DEFAULT_TILESET, TileSpec, generate


def test_generate_respects_requested_dimensions():
    grid = generate(seed=1, width=20, height=15)
    assert grid.width == 20
    assert grid.height == 15
    assert len(grid.cells) == 15
    assert all(len(row) == 20 for row in grid.cells)


def test_generate_only_uses_configured_tile_names():
    grid = generate(seed=1, width=25, height=25)
    used = {tile for row in grid.cells for tile in row}
    assert used <= set(DEFAULT_TILESET)


def test_generate_is_deterministic_for_the_same_seed():
    a = generate(seed=42, width=20, height=20)
    b = generate(seed=42, width=20, height=20)
    assert a.cells == b.cells


def test_default_tileset_never_places_two_wall_tiles_adjacent():
    """DEFAULT_TILESET's whole point is a hard constraint plain weighted-
    random tile assignment couldn't guarantee: no two `wall` tiles ever
    touch, not even diagonally excluded here (WFC's adjacency here is
    4-directional; this asserts the 4-directional guarantee actually
    holds)."""
    grid = generate(seed=7, width=30, height=30)
    for y in range(grid.height):
        for x in range(grid.width):
            if grid.get(x, y) != "wall":
                continue
            for dx, dy in ((0, -1), (0, 1), (1, 0), (-1, 0)):
                nx, ny = x + dx, y + dy
                if grid.in_bounds(nx, ny):
                    assert grid.get(nx, ny) != "wall"


def test_generate_terminates_and_returns_valid_tiles_even_for_an_unsatisfiable_tileset():
    """`a` demands every neighbor be `b`, but `b` also demands every
    neighbor be `b` - the moment an `a` ends up next to anything, the
    far side's own rule (its neighbors must also be `b`) contradicts `a`
    being there at all. On any grid with more than one cell this always
    eventually contradicts, every retry - generate() must still terminate
    (via the non-strict fallback) rather than raising or hanging, and every
    cell must still be a name from the tileset."""
    unsatisfiable = {
        "a": TileSpec(weight=1.0, neighbors={d: {"b"} for d in ("N", "S", "E", "W")}),
        "b": TileSpec(weight=1.0, neighbors={d: {"b"} for d in ("N", "S", "E", "W")}),
    }
    grid = generate(seed=3, width=6, height=6, tileset=unsatisfiable, max_retries=2)
    assert grid.width == 6 and grid.height == 6
    used = {tile for row in grid.cells for tile in row}
    assert used <= {"a", "b"}
