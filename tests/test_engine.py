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


def make_monster(
    x: int, y: int, hp=5, attack=2, defense=0, ai=None, alert_radius=None, flee_hp_pct=None
) -> Entity:
    return Entity(
        x, y, "r", (140, 90, 60), "Rat",
        blocks_movement=True,
        render_priority=RENDER_PRIORITY_ACTOR,
        fighter=Fighter(max_hp=hp, hp=hp, attack=attack, defense=defense),
        ai=ai,
        alert_radius=alert_radius,
        flee_hp_pct=flee_hp_pct,
    )


def make_potion(x: int, y: int, heal_amount=10) -> Entity:
    return Entity(
        x, y, "!", (220, 40, 100), "Healing Potion",
        blocks_movement=False,
        render_priority=RENDER_PRIORITY_ITEM,
        item=ItemEffect(heal_amount=heal_amount),
    )


def make_key(x: int, y: int, key_id: str = "rusty_key", name: str = "Rusty Key") -> Entity:
    return Entity(
        x, y, "-", (200, 170, 60), name,
        blocks_movement=False,
        render_priority=RENDER_PRIORITY_ITEM,
        item=ItemEffect(key_id=key_id),
    )


def make_weapon(x: int, y: int, attack_bonus: int = 2, name: str = "Rusty Dagger") -> Entity:
    return Entity(
        x, y, "/", (180, 180, 190), name,
        render_priority=RENDER_PRIORITY_ITEM,
        item=ItemEffect(attack_bonus=attack_bonus),
    )


def make_armor(x: int, y: int, defense_bonus: int = 1, name: str = "Leather Armor") -> Entity:
    return Entity(
        x, y, "[", (150, 110, 60), name,
        render_priority=RENDER_PRIORITY_ITEM,
        item=ItemEffect(defense_bonus=defense_bonus),
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


def test_sleeping_guard_ignores_player_outside_alert_radius():
    game_map = make_open_map(10, 3)
    player = make_player(0, 1)
    guard = make_monster(6, 1, hp=16, attack=5, ai="sleeping_guard", alert_radius=3)
    game_map.entities.extend([player, guard])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert (guard.x, guard.y) == (6, 1)  # stayed put, player is out of range
    assert player.fighter.hp == player.fighter.max_hp


def test_sleeping_guard_wakes_once_player_within_alert_radius():
    game_map = make_open_map(10, 3)
    player = make_player(0, 1)
    guard = make_monster(2, 1, hp=16, attack=5, ai="sleeping_guard", alert_radius=3)
    game_map.entities.extend([player, guard])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert (guard.x, guard.y) == (1, 1)  # chased toward the player


def test_skittish_behaves_normally_above_flee_threshold():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, defense=0)
    monster = make_monster(2, 1, hp=10, attack=4, ai="skittish", flee_hp_pct=0.3)
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert player.fighter.hp == 30 - 4  # full hp (10/10), above threshold: attacks as usual


def test_skittish_flees_instead_of_attacking_when_hurt():
    game_map = make_open_map(5, 3)
    player = make_player(2, 1)
    monster = make_monster(3, 1, hp=10, attack=4, ai="skittish", flee_hp_pct=0.3)
    monster.fighter.hp = 2  # 20%, below the 30% threshold
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert (monster.x, monster.y) == (4, 1)  # stepped away, even though adjacent
    assert player.fighter.hp == player.fighter.max_hp  # did not attack


def test_skittish_holds_position_when_flee_is_blocked():
    game_map = make_open_map(3, 3)
    game_map.walkable[2, 1] = False  # wall directly behind the monster's escape route
    player = make_player(0, 1)
    monster = make_monster(1, 1, hp=10, attack=4, ai="skittish", flee_hp_pct=0.5)
    monster.fighter.hp = 1
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert (monster.x, monster.y) == (1, 1)  # blocked - held position, did not crash
    assert player.fighter.hp == player.fighter.max_hp  # still did not attack


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


def test_first_weapon_pickup_equips_directly():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, attack=5)
    weapon = make_weapon(1, 1, attack_bonus=2, name="Rusty Dagger")
    game_map.entities.extend([player, weapon])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(PickupAction())

    assert player.equipped_weapon is weapon
    assert weapon not in game_map.entities
    assert player.effective_attack == 5 + 2


def test_picking_up_better_weapon_swaps_and_drops_old_one():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, attack=5)
    player.equipped_weapon = make_weapon(0, 0, attack_bonus=2, name="Rusty Dagger")
    better_weapon = make_weapon(1, 1, attack_bonus=4, name="Iron Sword")
    game_map.entities.extend([player, better_weapon])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(PickupAction())

    assert player.equipped_weapon is better_weapon
    assert player.effective_attack == 5 + 4
    dropped = [e for e in game_map.entities if e.name == "Rusty Dagger"]
    assert len(dropped) == 1
    assert (dropped[0].x, dropped[0].y) == (1, 1)  # dropped at the player's feet


def test_picking_up_worse_weapon_is_left_on_the_ground():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, attack=5)
    current_weapon = make_weapon(0, 0, attack_bonus=4, name="Iron Sword")
    player.equipped_weapon = current_weapon
    worse_weapon = make_weapon(1, 1, attack_bonus=2, name="Rusty Dagger")
    game_map.entities.extend([player, worse_weapon])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(PickupAction())

    assert player.equipped_weapon is current_weapon  # unchanged
    assert worse_weapon in game_map.entities  # left untouched on the ground
    assert (worse_weapon.x, worse_weapon.y) == (1, 1)


def test_armor_pickup_swaps_the_same_way_as_weapons():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, defense=1)
    player.equipped_armor = make_armor(0, 0, defense_bonus=1, name="Leather Armor")
    better_armor = make_armor(1, 1, defense_bonus=3, name="Bone Plate")
    game_map.entities.extend([player, better_armor])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(PickupAction())

    assert player.equipped_armor is better_armor
    assert player.effective_defense == 1 + 3
    dropped = [e for e in game_map.entities if e.name == "Leather Armor"]
    assert len(dropped) == 1
    assert (dropped[0].x, dropped[0].y) == (1, 1)


def test_combat_damage_reflects_equipped_weapon_and_armor():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, attack=5, defense=1)
    player.equipped_weapon = make_weapon(0, 0, attack_bonus=4)
    monster = make_monster(2, 1, hp=20, attack=8, defense=0, ai=None)
    monster.equipped_armor = make_armor(0, 0, defense_bonus=3)
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(BumpAction(1, 0))

    # player attack 5+4=9 vs monster defense 0+3=3 -> 6 damage
    assert monster.fighter.hp == 20 - 6


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


def test_full_dungeon_chain_is_completable():
    """End-to-end regression: walks the whole shipped dungeon via
    on_player_reach_stairs (one path through the 02a/02b branch), confirming
    every hop resolves and the run actually reaches "won" - not just that
    each transition works in isolation."""
    catalog = load_catalog()
    levels = load_dungeon(DATA_DIR / "levels", catalog)
    level_01 = levels["level_01"]
    game_map, player = build_game_map(level_01, catalog)
    engine = Engine(game_map, player, level_01.name, catalog=catalog, levels=levels)

    for next_level_id in ("level_02a", "level_03", "level_04", "level_05"):
        engine.on_player_reach_stairs(next_level_id)
        assert engine.game_state == "playing"
        assert engine.player is player

    engine.on_player_reach_stairs(None)  # level_05's terminal stairs
    assert engine.game_state == "won"


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
    player.equipped_weapon = make_weapon(0, 0, attack_bonus=10)
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
    assert engine.player.effective_attack == PLAYER_ATTACK
    assert engine.player.equipped_weapon is None
    assert engine.player.inventory == []
    assert (engine.player.x, engine.player.y) == level_01.player_start
    assert len(engine.message_log.messages) == 1  # log cleared to just the entry message

    monster_names = sorted(e.name for e in engine.game_map.entities if e.ai is not None)
    assert monster_names == ["Goblin", "Rat", "Rat"]  # killed monster is back


def test_locked_door_blocks_movement_without_key():
    game_map = make_open_map(3, 3)
    game_map.kinds[2, 1] = "door"
    game_map.walkable[2, 1] = False
    game_map.transparent[2, 1] = False
    game_map.locked_doors[(2, 1)] = "rusty_key"
    player = make_player(1, 1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(BumpAction(1, 0))

    assert (player.x, player.y) == (1, 1)  # blocked
    assert (2, 1) in game_map.locked_doors  # still locked


def test_locked_door_unlocks_and_consumes_matching_key():
    game_map = make_open_map(3, 3)
    game_map.kinds[2, 1] = "door"
    game_map.walkable[2, 1] = False
    game_map.transparent[2, 1] = False
    game_map.locked_doors[(2, 1)] = "rusty_key"
    player = make_player(1, 1)
    key = make_key(0, 0)
    player.inventory.append(key)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(BumpAction(1, 0))

    assert (player.x, player.y) == (2, 1)  # moved through the now-open door
    assert (2, 1) not in game_map.locked_doors
    assert game_map.walkable[2, 1]
    assert key not in player.inventory


def test_use_item_action_never_consumes_a_key():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    key = make_key(0, 0)
    player.inventory.append(key)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(UseItemAction())

    assert key in player.inventory  # not consumed
    assert engine.message_log.messages[-1] == "You have nothing to use."


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
