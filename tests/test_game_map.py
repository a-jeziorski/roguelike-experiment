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


def test_apply_corruption_radius_remaps_plains_within_radius():
    game_map = make_map(5, 5)

    apply_corruption_radius(game_map, epicenter=(2, 2), radius=1)

    for x in range(1, 4):
        for y in range(1, 4):
            assert game_map.kinds[x, y] == "ashen_plains", (x, y)


def test_apply_corruption_radius_leaves_tiles_outside_radius_untouched():
    game_map = make_map(5, 5)

    apply_corruption_radius(game_map, epicenter=(2, 2), radius=1)

    # Chebyshev distance 2 from the epicenter - outside a radius-1 box.
    assert game_map.kinds[0, 0] == "plains"
    assert game_map.kinds[4, 4] == "plains"
    assert game_map.kinds[2, 0] == "plains"


def test_apply_corruption_radius_remaps_forest_to_blighted_forest():
    game_map = make_map(3, 3, kinds={(1, 1): "forest"})

    apply_corruption_radius(game_map, epicenter=(1, 1), radius=0)

    assert game_map.kinds[1, 1] == "blighted_forest"


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


def test_apply_corruption_radius_leaves_already_corrupted_tiles_alone():
    game_map = make_map(3, 3, kinds={(1, 1): "ashen_plains"})

    apply_corruption_radius(game_map, epicenter=(1, 1), radius=0)

    assert game_map.kinds[1, 1] == "ashen_plains"


def test_apply_corruption_radius_leaves_structural_tiles_alone():
    game_map = make_map(
        5, 5,
        kinds={
            (2, 2): "road", (2, 1): "wall", (1, 2): "dungeon_entrance",
            (3, 2): "landmark", (2, 3): "mountain",
        },
    )

    apply_corruption_radius(game_map, epicenter=(2, 2), radius=1)

    assert game_map.kinds[2, 2] == "road"
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
    incremental = make_map(7, 7)
    apply_corruption_radius(incremental, epicenter=(3, 3), radius=1)
    apply_corruption_radius(incremental, epicenter=(3, 3), radius=2)

    direct = make_map(7, 7)
    apply_corruption_radius(direct, epicenter=(3, 3), radius=2)

    assert (incremental.kinds == direct.kinds).all()
    assert (incremental.walkable == direct.walkable).all()
    assert (incremental.transparent == direct.transparent).all()
