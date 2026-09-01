"""Tests for the pure ranged-targeting helpers (no console/tcod dependency)."""

from engine.entity import RENDER_PRIORITY_ACTOR, RENDER_PRIORITY_ITEM, Entity, Fighter, ItemEffect
from engine.game_map import GameMap
from engine.targeting import find_nearest_target, in_range, is_valid_target


def make_open_map(width: int, height: int) -> GameMap:
    game_map = GameMap(width, height)
    for x in range(width):
        for y in range(height):
            game_map.kinds[x, y] = "floor"
            game_map.walkable[x, y] = True
            game_map.transparent[x, y] = True
            game_map.visible[x, y] = True
    return game_map


def make_shooter(x: int, y: int) -> Entity:
    return Entity(
        x, y, "@", (255, 255, 255), "Player",
        blocks_movement=True,
        fighter=Fighter(max_hp=30, hp=30, attack=5, defense=1),
    )


def make_monster(x: int, y: int) -> Entity:
    return Entity(
        x, y, "r", (140, 90, 60), "Rat",
        blocks_movement=True,
        render_priority=RENDER_PRIORITY_ACTOR,
        fighter=Fighter(max_hp=6, hp=6, attack=2, defense=0),
    )


def test_in_range_true_within_chebyshev_distance():
    shooter = make_shooter(0, 0)
    assert in_range(shooter, 3, 3, max_range=3) is True


def test_in_range_false_beyond_distance():
    shooter = make_shooter(0, 0)
    assert in_range(shooter, 4, 0, max_range=3) is False


def test_is_valid_target_false_out_of_bounds():
    game_map = make_open_map(5, 5)
    shooter = make_shooter(0, 0)
    assert is_valid_target(game_map, shooter, 10, 10, max_range=5) is False


def test_is_valid_target_false_out_of_range():
    game_map = make_open_map(10, 3)
    shooter = make_shooter(0, 1)
    monster = make_monster(8, 1)
    game_map.entities.append(monster)
    assert is_valid_target(game_map, shooter, 8, 1, max_range=3) is False


def test_is_valid_target_false_not_visible():
    game_map = make_open_map(5, 3)
    game_map.visible[3, 1] = False
    shooter = make_shooter(0, 1)
    monster = make_monster(3, 1)
    game_map.entities.append(monster)
    assert is_valid_target(game_map, shooter, 3, 1, max_range=5) is False


def test_is_valid_target_false_no_entity():
    game_map = make_open_map(5, 3)
    shooter = make_shooter(0, 1)
    assert is_valid_target(game_map, shooter, 3, 1, max_range=5) is False


def test_is_valid_target_false_entity_without_fighter():
    game_map = make_open_map(5, 3)
    shooter = make_shooter(0, 1)
    item = Entity(
        3, 1, "!", (220, 40, 100), "Healing Potion",
        blocks_movement=False,
        render_priority=RENDER_PRIORITY_ITEM,
        item=ItemEffect(heal_amount=10),
    )
    game_map.entities.append(item)
    assert is_valid_target(game_map, shooter, 3, 1, max_range=5) is False


def test_is_valid_target_true_for_a_real_target():
    game_map = make_open_map(5, 3)
    shooter = make_shooter(0, 1)
    monster = make_monster(3, 1)
    game_map.entities.append(monster)
    assert is_valid_target(game_map, shooter, 3, 1, max_range=5) is True


def test_is_valid_target_false_for_a_hidden_ambusher():
    game_map = make_open_map(5, 3)
    shooter = make_shooter(0, 1)
    lurker = make_monster(3, 1)
    lurker.ai = "ambusher"
    lurker.hidden = True
    game_map.entities.append(lurker)
    assert is_valid_target(game_map, shooter, 3, 1, max_range=5) is False


def test_find_nearest_target_picks_closest_of_several():
    game_map = make_open_map(10, 3)
    shooter = make_shooter(0, 1)
    far = make_monster(8, 1)
    near = make_monster(3, 1)
    game_map.entities.extend([far, near])

    nearest = find_nearest_target(game_map, shooter, max_range=9)
    assert nearest is near


def test_find_nearest_target_ignores_non_blocking_items():
    game_map = make_open_map(5, 3)
    shooter = make_shooter(0, 1)
    item = Entity(
        2, 1, "!", (220, 40, 100), "Healing Potion",
        blocks_movement=False,
        render_priority=RENDER_PRIORITY_ITEM,
        item=ItemEffect(heal_amount=10),
    )
    game_map.entities.append(item)

    assert find_nearest_target(game_map, shooter, max_range=5) is None


def test_find_nearest_target_none_when_nothing_qualifies():
    game_map = make_open_map(5, 3)
    shooter = make_shooter(0, 1)
    assert find_nearest_target(game_map, shooter, max_range=5) is None


def test_find_nearest_target_skips_a_hidden_ambusher_for_a_farther_visible_one():
    game_map = make_open_map(10, 3)
    shooter = make_shooter(0, 1)
    lurker = make_monster(2, 1)  # closer, but hidden - should never be picked
    lurker.ai = "ambusher"
    lurker.hidden = True
    visible_monster = make_monster(5, 1)
    game_map.entities.extend([lurker, visible_monster])

    nearest = find_nearest_target(game_map, shooter, max_range=9)

    assert nearest is visible_monster
