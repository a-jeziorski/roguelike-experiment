"""Engine/action/combat logic tests, built directly against engine world-objects
(no content files involved) so game rules are verified independently of parsing."""

from engine.actions import BumpAction, PickupAction, UseItemAction, WaitAction
from engine.engine import Engine
from engine.entity import (
    RENDER_PRIORITY_ACTOR,
    RENDER_PRIORITY_ITEM,
    RENDER_PRIORITY_PLAYER,
    Entity,
    Fighter,
    ItemEffect,
)
from engine.game_map import GameMap


def make_open_map(width: int, height: int) -> GameMap:
    """An all-floor map with no walls, for isolating action/combat logic."""
    game_map = GameMap(width, height)
    for x in range(width):
        for y in range(height):
            game_map.kinds[x, y] = "floor"
            game_map.walkable[x, y] = True
            game_map.transparent[x, y] = True
    return game_map


def make_player(x: int, y: int, hp: int = 30, attack: int = 5, defense: int = 1) -> Entity:
    return Entity(
        x, y, "@", (255, 255, 255), "Player",
        blocks_movement=True,
        render_priority=RENDER_PRIORITY_PLAYER,
        fighter=Fighter(max_hp=hp, hp=hp, attack=attack, defense=defense),
    )


def make_monster(x: int, y: int, hp=5, attack=2, defense=0, ai=None) -> Entity:
    return Entity(
        x, y, "r", (140, 90, 60), "Rat",
        blocks_movement=True,
        render_priority=RENDER_PRIORITY_ACTOR,
        fighter=Fighter(max_hp=hp, hp=hp, attack=attack, defense=defense),
        ai=ai,
    )


def make_potion(x: int, y: int, heal_amount=10) -> Entity:
    return Entity(
        x, y, "!", (220, 40, 100), "Healing Potion",
        blocks_movement=False,
        render_priority=RENDER_PRIORITY_ITEM,
        item=ItemEffect(heal_amount=heal_amount),
    )


def test_movement_into_open_floor():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(BumpAction(1, 0))

    assert (player.x, player.y) == (2, 1)


def test_movement_blocked_by_wall():
    game_map = make_open_map(3, 3)
    game_map.walkable[2, 1] = False
    player = make_player(1, 1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(BumpAction(1, 0))

    assert (player.x, player.y) == (1, 1)


def test_bump_into_monster_attacks_instead_of_moving():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    monster = make_monster(2, 1, hp=5, defense=0, ai=None)
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(BumpAction(1, 0))

    assert (player.x, player.y) == (1, 1)  # did not move into the monster's tile
    assert monster.fighter.hp == 5 - player.fighter.attack


def test_killing_a_monster_removes_it_from_the_map():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, attack=100)
    monster = make_monster(2, 1, hp=5, defense=0, ai=None)
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(BumpAction(1, 0))

    assert monster not in game_map.entities
    assert engine.game_state == "playing"


def test_hostile_monster_attacks_player_on_its_turn():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, defense=0)
    monster = make_monster(2, 1, hp=5, attack=4, ai="hostile_basic")
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert player.fighter.hp == 30 - 4


def test_player_death_sets_game_state_dead():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=1, defense=0)
    monster = make_monster(2, 1, hp=5, attack=99, ai="hostile_basic")
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert engine.game_state == "dead"


def test_pickup_and_use_healing_potion():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=10, attack=5)
    player.fighter.hp = 5  # damaged, so healing is observable
    potion = make_potion(1, 1, heal_amount=10)
    game_map.entities.extend([player, potion])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(PickupAction())
    assert potion not in game_map.entities
    assert len(player.inventory) == 1

    engine.process_turn(UseItemAction())
    assert player.fighter.hp == min(player.fighter.max_hp, 5 + 10)
    assert len(player.inventory) == 0


def test_reaching_stairs_wins():
    game_map = make_open_map(3, 3)
    game_map.kinds[2, 1] = "stairs_down"
    game_map.stairs_down = (2, 1)
    player = make_player(1, 1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(BumpAction(1, 0))

    assert engine.game_state == "won"
