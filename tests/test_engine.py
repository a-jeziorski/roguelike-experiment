"""Engine/action/combat logic tests. Most are built directly against engine
world-objects (no content files involved) so game rules are verified independently
of parsing; a few level-transition tests use the real shipped dungeon content to
verify the loader and engine agree on level ids and player_start positions."""

from pathlib import Path

from content.loader import load_catalog, load_dungeon
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
from engine.game_map import PLAYER_ATTACK, GameMap, build_game_map

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


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
    game_map.stairs[(2, 1)] = None
    player = make_player(1, 1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(BumpAction(1, 0))

    assert engine.game_state == "won"


def test_descending_stairs_swaps_level_and_preserves_player():
    catalog = load_catalog()
    levels = load_dungeon(DATA_DIR / "levels", catalog)
    level_01 = levels["level_01"]
    game_map, player = build_game_map(level_01, catalog)
    engine = Engine(game_map, player, level_01.name, catalog=catalog, levels=levels)

    player.fighter.hp = 20
    player.inventory.append(make_potion(0, 0))
    old_game_map = engine.game_map

    engine.on_player_reach_stairs("level_02a")

    assert engine.player is player  # same object: hp/inventory/attack carry over
    assert engine.game_map is not old_game_map
    assert engine.level_name == "The Flooded Crypt"
    assert engine.game_state == "playing"
    assert player.fighter.hp == 20
    assert len(player.inventory) == 1
    assert (player.x, player.y) == levels["level_02a"].player_start


def test_level_01_branches_to_two_different_levels():
    catalog = load_catalog()
    levels = load_dungeon(DATA_DIR / "levels", catalog)
    game_map, _player = build_game_map(levels["level_01"], catalog)

    destinations = set(game_map.stairs.values())
    assert destinations == {"level_02a", "level_02b"}


def test_restart_after_death_gives_a_fresh_run():
    catalog = load_catalog()
    levels = load_dungeon(DATA_DIR / "levels", catalog)
    level_01 = levels["level_01"]
    game_map, player = build_game_map(level_01, catalog)
    engine = Engine(
        game_map,
        player,
        level_01.name,
        catalog=catalog,
        levels=levels,
        starting_level=level_01,
    )

    # Simulate a run in progress: damaged, geared up, and one monster killed.
    player.fighter.hp = 1
    player.fighter.attack += 10
    player.inventory.append(make_potion(0, 0))
    killed_monster = next(e for e in game_map.entities if e.name == "Rat")
    game_map.entities.remove(killed_monster)
    engine.on_entity_death(player)
    assert engine.game_state == "dead"

    old_game_map = engine.game_map
    engine.restart()

    assert engine.game_state == "playing"
    assert engine.game_map is not old_game_map
    assert engine.player is not player  # fresh entity, not the one that died
    assert engine.player.fighter.hp == engine.player.fighter.max_hp
    assert engine.player.fighter.attack == PLAYER_ATTACK
    assert engine.player.inventory == []
    assert (engine.player.x, engine.player.y) == level_01.player_start
    assert len(engine.message_log.messages) == 1  # log cleared to just the entry message

    monster_names = sorted(e.name for e in engine.game_map.entities if e.ai is not None)
    assert monster_names == ["Goblin", "Rat", "Rat"]  # killed monster is back


def test_restart_after_win_returns_to_starting_level():
    catalog = load_catalog()
    levels = load_dungeon(DATA_DIR / "levels", catalog)
    level_01 = levels["level_01"]
    game_map, player = build_game_map(level_01, catalog)
    engine = Engine(
        game_map,
        player,
        level_01.name,
        catalog=catalog,
        levels=levels,
        starting_level=level_01,
    )

    engine.on_player_reach_stairs("level_02a")  # progress deeper into the dungeon
    engine.game_state = "won"  # simulate reaching the final terminal stairway

    engine.restart()

    assert engine.game_state == "playing"
    assert engine.level_name == "The Rotting Cellar"
    assert (engine.player.x, engine.player.y) == level_01.player_start
