"""Tests for pure engine/game_map.py functions that don't need a full Engine -
apply_dungeon_destruction's tests live in test_engine.py alongside
Engine.destroy_dungeon (its sole real caller); apply_corruption_radius has no
such caller yet (see docs/visitor_corruption.md), so it's tested directly
here instead."""

from engine.game_map import GameMap, apply_corruption_radius


def make_map(width: int, height: int, kinds: dict[tuple[int, int], str] | None = None) -> GameMap:
    """An all-plains map (the common corruptible baseline), with specific
    coordinates overridden to whatever kind the test needs."""
    game_map = GameMap(width, height)
    for x in range(width):
        for y in range(height):
            game_map.kinds[x, y] = "plains"
            game_map.walkable[x, y] = True
            game_map.transparent[x, y] = True
    for (x, y), kind in (kinds or {}).items():
        game_map.kinds[x, y] = kind
    return game_map


def test_apply_corruption_radius_remaps_a_small_radius_as_a_plain_circle():
    """Below the noise ramp-start (radius <= 5, see
    _corruption_noise_amplitude), there's no wobble at all - a predictable
    Euclidean circle, not the old Chebyshev square: at radius 1 that's the
    center plus its 4 orthogonal neighbors, NOT the diagonal corners
    (Euclidean distance sqrt(2) > 1)."""
    game_map = make_map(5, 5)

    apply_corruption_radius(game_map, epicenter=(2, 2), radius=1)

    assert game_map.kinds[2, 2] == "ashen_plains"
    for x, y in [(1, 2), (3, 2), (2, 1), (2, 3)]:
        assert game_map.kinds[x, y] == "ashen_plains", (x, y)
    for x, y in [(1, 1), (1, 3), (3, 1), (3, 3)]:
        assert game_map.kinds[x, y] == "plains", (x, y)  # diagonal - outside the circle


def test_apply_corruption_radius_leaves_tiles_outside_radius_untouched():
    game_map = make_map(5, 5)

    apply_corruption_radius(game_map, epicenter=(2, 2), radius=1)

    assert game_map.kinds[0, 0] == "plains"
    assert game_map.kinds[4, 4] == "plains"
    assert game_map.kinds[2, 0] == "plains"


def test_apply_corruption_radius_remaps_forest_to_blighted_forest():
    game_map = make_map(3, 3, kinds={(1, 1): "forest"})

    apply_corruption_radius(game_map, epicenter=(1, 1), radius=0)

    assert game_map.kinds[1, 1] == "blighted_forest"


def test_apply_corruption_radius_remaps_road_to_ashen_road():
    """A road must not become a safe, uncorrupted lane through corrupted
    ground - explicit user feedback (2026-09-05)."""
    game_map = make_map(3, 3, kinds={(1, 1): "road"})

    apply_corruption_radius(game_map, epicenter=(1, 1), radius=0)

    assert game_map.kinds[1, 1] == "ashen_road"


def test_apply_corruption_radius_updates_walkable_and_transparent_for_forest():
    game_map = make_map(3, 3, kinds={(1, 1): "forest"})
    game_map.walkable[1, 1] = True
    game_map.transparent[1, 1] = False

    apply_corruption_radius(game_map, epicenter=(1, 1), radius=0)

    # blighted_forest matches plain forest's own passability: walkable,
    # but blocks sightline (TILE_PASSABILITY["blighted_forest"]).
    assert bool(game_map.walkable[1, 1]) is True
    assert bool(game_map.transparent[1, 1]) is False


def test_apply_corruption_radius_updates_walkable_and_transparent_for_plains():
    game_map = make_map(3, 3)

    apply_corruption_radius(game_map, epicenter=(1, 1), radius=0)

    assert game_map.kinds[1, 1] == "ashen_plains"
    assert bool(game_map.walkable[1, 1]) is True
    assert bool(game_map.transparent[1, 1]) is True


def test_apply_corruption_radius_updates_walkable_and_transparent_for_road():
    game_map = make_map(3, 3, kinds={(1, 1): "road"})

    apply_corruption_radius(game_map, epicenter=(1, 1), radius=0)

    # ashen_road matches plain road's own passability - walkable and
    # transparent, same as plains/ashen_plains (no TILE_PASSABILITY entry
    # for either, both fall to the default).
    assert bool(game_map.walkable[1, 1]) is True
    assert bool(game_map.transparent[1, 1]) is True


def test_apply_corruption_radius_leaves_already_corrupted_tiles_alone():
    game_map = make_map(3, 3, kinds={(1, 1): "ashen_plains"})

    apply_corruption_radius(game_map, epicenter=(1, 1), radius=0)

    assert game_map.kinds[1, 1] == "ashen_plains"


def test_apply_corruption_radius_leaves_structural_tiles_alone():
    game_map = make_map(
        5, 5,
        kinds={
            (2, 1): "wall", (1, 2): "dungeon_entrance",
            (3, 2): "landmark", (2, 3): "mountain",
        },
    )

    apply_corruption_radius(game_map, epicenter=(2, 2), radius=1)

    assert game_map.kinds[2, 1] == "wall"
    assert game_map.kinds[1, 2] == "dungeon_entrance"
    assert game_map.kinds[3, 2] == "landmark"
    assert game_map.kinds[2, 3] == "mountain"


def test_apply_corruption_radius_clips_to_map_bounds_without_error():
    game_map = make_map(4, 4)

    # radius far larger than the map - must not raise or wrap around.
    apply_corruption_radius(game_map, epicenter=(0, 0), radius=100)

    for x in range(4):
        for y in range(4):
            assert game_map.kinds[x, y] == "ashen_plains"


def test_apply_corruption_radius_is_a_no_op_re_call_at_the_same_radius():
    game_map = make_map(5, 5)

    apply_corruption_radius(game_map, epicenter=(2, 2), radius=1)
    first_pass = game_map.kinds.copy()
    apply_corruption_radius(game_map, epicenter=(2, 2), radius=1)

    assert (game_map.kinds == first_pass).all()


def test_apply_corruption_radius_growing_across_two_calls_matches_one_call_at_the_larger_radius():
    """The core idempotency/replay-safety guarantee (see
    engine/save.py's restore_save): the boundary noise is a pure function
    of (tile, epicenter) alone, never of radius or call history, so
    applying radius 1 then radius 30 must land on exactly the same tiles
    as applying radius 30 directly - the same property the old, simpler
    square-boundary version had, now re-verified against the irregular
    boundary."""
    incremental = make_map(80, 80)
    apply_corruption_radius(incremental, epicenter=(40, 40), radius=1)
    apply_corruption_radius(incremental, epicenter=(40, 40), radius=30)

    direct = make_map(80, 80)
    apply_corruption_radius(direct, epicenter=(40, 40), radius=30)

    assert (incremental.kinds == direct.kinds).all()
    assert (incremental.walkable == direct.walkable).all()
    assert (incremental.transparent == direct.transparent).all()


def test_apply_corruption_radius_boundary_is_irregular_not_a_perfect_circle_or_square():
    """Direct regression test for explicit user feedback (2026-09-05):
    'the radius of the expanding corruption appears as a perfect
    rectangle and looks a bit silly... apply some irregularity to its
    edges.' At radius 20 (well past the noise ramp-start), the boundary
    must bulge past the nominal radius in some directions and fall short
    of it in others - not land on any clean geometric edge, square or
    circle."""
    game_map = make_map(100, 100, kinds={})
    apply_corruption_radius(game_map, epicenter=(50, 50), radius=20)

    # Bulges outward well past the nominal radius (Euclidean distance
    # ~22.6, radius is 20) along one direction...
    assert game_map.kinds[66, 66] == "ashen_plains"
    # ...while falling short of it along others, at exactly the distance
    # a perfect (noiseless) circle would have included.
    assert game_map.kinds[50, 70] == "plains"  # Euclidean distance exactly 20
    assert game_map.kinds[50, 30] == "plains"  # Euclidean distance exactly 20
    # And it's not the old Chebyshev square either - that shape would
    # have included this corner (Chebyshev distance exactly 20); the
    # Euclidean-based shape (distance ~28.3, far past radius + the noise
    # cap of 6) correctly excludes it.
    assert game_map.kinds[70, 70] == "plains"


def test_apply_corruption_radius_noise_amplitude_is_zero_at_the_ramp_start():
    """radius == 5 (the ramp-start) is the largest radius with exactly
    zero wobble - a boundary case worth pinning directly, since
    _corruption_noise_amplitude's ramp formula is easy to get off-by-one
    wrong."""
    game_map = make_map(15, 15)

    apply_corruption_radius(game_map, epicenter=(7, 7), radius=5)

    for x in range(15):
        for y in range(15):
            distance_squared = (x - 7) ** 2 + (y - 7) ** 2
            expected = "ashen_plains" if distance_squared <= 25 else "plains"
            assert game_map.kinds[x, y] == expected, (x, y)
