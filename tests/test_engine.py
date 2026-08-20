"""Engine/action/combat logic tests. Most are built directly against engine
world-objects (no content files involved) so game rules are verified independently
of parsing; a few level-transition tests use the real shipped dungeon content to
verify the loader and engine agree on level ids and player_start positions."""

import random
from pathlib import Path

from content.loader import load_catalog, load_levels, load_overworld
from engine.actions import BumpAction, FireAction, PickupAction, UseItemAction, WaitAction
from engine.clock import STARTING_HOUR, GameClock
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
LEVELS_DIR = DATA_DIR / "dungeons" / "forgotten_ruins" / "levels"
PRISON_TOWER_LEVELS_DIR = DATA_DIR / "dungeons" / "prison_tower" / "levels"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


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
    x: int, y: int, hp=5, attack=2, defense=0, ai=None,
    alert_radius=None, flee_hp_pct=None, ranged_range=None,
) -> Entity:
    return Entity(
        x, y, "r", (140, 90, 60), "Rat",
        blocks_movement=True,
        render_priority=RENDER_PRIORITY_ACTOR,
        fighter=Fighter(max_hp=hp, hp=hp, attack=attack, defense=defense),
        ai=ai,
        alert_radius=alert_radius,
        flee_hp_pct=flee_hp_pct,
        ranged_range=ranged_range,
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


def make_ranged_weapon(
    x: int, y: int, ranged_attack_bonus: int = 3, range_: int = 5, name: str = "Hunting Bow"
) -> Entity:
    return Entity(
        x, y, "}", (160, 120, 70), name,
        render_priority=RENDER_PRIORITY_ITEM,
        item=ItemEffect(ranged_attack_bonus=ranged_attack_bonus, range=range_),
    )


def make_ammo(x: int, y: int, quantity: int = 5, name: str = "Arrows") -> Entity:
    return Entity(
        x, y, "|", (190, 170, 140), name,
        render_priority=RENDER_PRIORITY_ITEM,
        item=ItemEffect(is_ammo=True, quantity=quantity),
    )


def test_movement_into_open_floor():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(BumpAction(1, 0))

    assert (player.x, player.y) == (2, 1)


def test_diagonal_movement_into_open_floor():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(BumpAction(1, 1))

    assert (player.x, player.y) == (2, 2)


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


def test_villager_wanders_when_undamaged(monkeypatch):
    monkeypatch.setattr(random, "choice", lambda seq: (1, 0))
    game_map = make_open_map(5, 3)
    player = make_player(0, 1, hp=30)
    villager = make_monster(2, 1, hp=4, attack=0, ai="villager")
    game_map.entities.extend([player, villager])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert (villager.x, villager.y) == (3, 1)  # moved per the pinned random choice
    assert player.fighter.hp == 30  # never attacked


def test_villager_holds_position_when_wander_pick_is_stay_put(monkeypatch):
    monkeypatch.setattr(random, "choice", lambda seq: (0, 0))
    game_map = make_open_map(5, 3)
    player = make_player(0, 1, hp=30)
    villager = make_monster(2, 1, hp=4, attack=0, ai="villager")
    game_map.entities.extend([player, villager])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert (villager.x, villager.y) == (2, 1)


def test_villager_flees_once_damaged():
    game_map = make_open_map(5, 3)
    player = make_player(2, 1, hp=30)
    villager = make_monster(3, 1, hp=4, attack=0, ai="villager")
    villager.fighter.hp = 3  # any damage at all, not a percentage threshold
    game_map.entities.extend([player, villager])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert (villager.x, villager.y) == (4, 1)  # stepped directly away
    assert player.fighter.hp == 30  # never attacked, even though adjacent


def test_villager_holds_position_when_flee_is_blocked():
    game_map = make_open_map(3, 3)
    game_map.walkable[2, 1] = False  # wall directly behind the villager's escape route
    player = make_player(0, 1, hp=30)
    villager = make_monster(1, 1, hp=4, attack=0, ai="villager")
    villager.fighter.hp = 1
    game_map.entities.extend([player, villager])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert (villager.x, villager.y) == (1, 1)  # blocked - held position, did not crash
    assert player.fighter.hp == 30


def test_villager_never_attacks_even_when_wander_picks_the_players_tile(monkeypatch):
    # (-1, 0) would step the villager directly onto the adjacent player.
    monkeypatch.setattr(random, "choice", lambda seq: (-1, 0))
    game_map = make_open_map(5, 3)
    player = make_player(2, 1, hp=30)
    villager = make_monster(3, 1, hp=4, attack=0, ai="villager")
    game_map.entities.extend([player, villager])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert player.fighter.hp == 30
    assert engine.melee_attack_events == []
    assert (villager.x, villager.y) == (3, 1)  # held position - MovementAction no-ops, blocked by player


def test_villager_ignores_player_when_not_visible():
    game_map = make_open_map(10, 3)
    for y in range(3):
        game_map.walkable[5, y] = False
        game_map.transparent[5, y] = False  # a wall column blocking line of sight
    player = make_player(0, 1, hp=30)
    villager = make_monster(8, 1, hp=4, attack=0, ai="villager")
    game_map.entities.extend([player, villager])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert (villager.x, villager.y) == (8, 1)  # never acted at all - not even a wander step


def test_ranged_basic_fires_when_in_range_but_not_adjacent():
    game_map = make_open_map(10, 3)
    player = make_player(0, 1, hp=30, defense=0)
    archer = make_monster(3, 1, hp=12, attack=4, ai="ranged_basic", ranged_range=5)
    game_map.entities.extend([player, archer])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert (archer.x, archer.y) == (3, 1)  # held position, did not close in
    assert player.fighter.hp == 30 - 4
    assert "shoots" in engine.message_log.messages[-1]


def test_ranged_basic_shot_records_a_ranged_attack_event():
    game_map = make_open_map(10, 3)
    player = make_player(0, 1, hp=30, defense=0)
    archer = make_monster(3, 1, hp=12, attack=4, ai="ranged_basic", ranged_range=5)
    game_map.entities.extend([player, archer])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert engine.ranged_attack_events == [(3, 1, 0, 1)]


def test_melee_attack_does_not_record_a_ranged_attack_event():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    monster = make_monster(2, 1, hp=6, attack=2, ai="hostile_basic")
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert engine.ranged_attack_events == []


def test_melee_attack_records_a_melee_attack_event_at_the_defender():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    monster = make_monster(2, 1, hp=6, attack=2, ai="hostile_basic")
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())  # monster is adjacent, so it melees the player

    assert engine.melee_attack_events == [(1, 1)]  # the player's tile


def test_ranged_basic_shot_does_not_record_a_melee_attack_event():
    game_map = make_open_map(10, 3)
    player = make_player(0, 1, hp=30, defense=0)
    archer = make_monster(3, 1, hp=12, attack=4, ai="ranged_basic", ranged_range=5)
    game_map.entities.extend([player, archer])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert engine.melee_attack_events == []


def test_player_bump_attack_records_a_melee_attack_event_at_the_monster():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    monster = make_monster(2, 1, hp=6, attack=2, ai=None)
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(BumpAction(1, 0))

    assert engine.melee_attack_events == [(2, 1)]  # the monster's tile


def test_ranged_basic_melees_when_adjacent():
    game_map = make_open_map(10, 3)
    player = make_player(0, 1, hp=30, defense=0)
    archer = make_monster(1, 1, hp=12, attack=4, ai="ranged_basic", ranged_range=5)
    game_map.entities.extend([player, archer])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert player.fighter.hp == 30 - 4
    assert "hits" in engine.message_log.messages[-1]


def test_ranged_basic_approaches_when_out_of_range():
    game_map = make_open_map(10, 3)
    player = make_player(0, 1)
    archer = make_monster(7, 1, hp=12, attack=4, ai="ranged_basic", ranged_range=5)
    game_map.entities.extend([player, archer])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert (archer.x, archer.y) == (6, 1)  # stepped toward the player, distance was 7 > 5
    assert player.fighter.hp == player.fighter.max_hp


def test_ranged_basic_ignores_player_when_not_visible():
    game_map = make_open_map(10, 3)
    for y in range(3):
        game_map.walkable[5, y] = False
        game_map.transparent[5, y] = False  # a wall column blocking line of sight
    player = make_player(0, 1)
    archer = make_monster(8, 1, hp=12, attack=4, ai="ranged_basic", ranged_range=5)
    game_map.entities.extend([player, archer])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert (archer.x, archer.y) == (8, 1)  # never acted, out of sight
    assert player.fighter.hp == player.fighter.max_hp


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


def test_first_ranged_weapon_pickup_equips_directly():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    bow = make_ranged_weapon(1, 1, ranged_attack_bonus=3, name="Hunting Bow")
    game_map.entities.extend([player, bow])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(PickupAction())

    assert player.equipped_ranged_weapon is bow
    assert bow not in game_map.entities
    assert player.effective_ranged_attack == player.fighter.attack + 3


def test_picking_up_better_ranged_weapon_swaps_and_drops_old_one():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    player.equipped_ranged_weapon = make_ranged_weapon(0, 0, ranged_attack_bonus=2, name="Sling")
    better = make_ranged_weapon(1, 1, ranged_attack_bonus=3, name="Hunting Bow")
    game_map.entities.extend([player, better])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(PickupAction())

    assert player.equipped_ranged_weapon is better
    dropped = [e for e in game_map.entities if e.name == "Sling"]
    assert len(dropped) == 1
    assert (dropped[0].x, dropped[0].y) == (1, 1)


def test_ammo_pickup_creates_a_stack():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    ammo = make_ammo(1, 1, quantity=5)
    game_map.entities.extend([player, ammo])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(PickupAction())

    assert len(player.inventory) == 1
    assert player.inventory[0].item.quantity == 5
    assert ammo not in game_map.entities


def test_second_ammo_pickup_merges_into_existing_stack():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    player.inventory.append(make_ammo(0, 0, quantity=3))
    more_ammo = make_ammo(1, 1, quantity=5)
    game_map.entities.extend([player, more_ammo])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(PickupAction())

    assert len(player.inventory) == 1  # merged, not a second entry
    assert player.inventory[0].item.quantity == 8
    assert more_ammo not in game_map.entities


def test_fire_action_without_ranged_weapon_does_nothing():
    game_map = make_open_map(5, 3)
    player = make_player(1, 1)
    monster = make_monster(3, 1, hp=6, ai=None)
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(FireAction(3, 1))

    assert monster.fighter.hp == 6


def test_fire_action_without_ammo_does_nothing():
    game_map = make_open_map(5, 3)
    player = make_player(1, 1)
    player.equipped_ranged_weapon = make_ranged_weapon(0, 0)
    monster = make_monster(3, 1, hp=6, ai=None)
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(FireAction(3, 1))

    assert monster.fighter.hp == 6


def test_fire_action_at_invalid_target_does_nothing_and_keeps_ammo():
    game_map = make_open_map(10, 3)
    player = make_player(1, 1)
    player.equipped_ranged_weapon = make_ranged_weapon(0, 0, range_=3)
    player.inventory.append(make_ammo(0, 0, quantity=5))
    game_map.entities.append(player)
    monster = make_monster(9, 1, hp=6, ai=None)  # 8 tiles away, beyond range 3
    game_map.entities.append(monster)
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(FireAction(9, 1))

    assert monster.fighter.hp == 6
    assert player.inventory[0].item.quantity == 5


def test_fire_action_hits_target_and_consumes_ammo():
    game_map = make_open_map(5, 3)
    player = make_player(1, 1, attack=5)
    player.equipped_ranged_weapon = make_ranged_weapon(0, 0, ranged_attack_bonus=3)
    player.inventory.append(make_ammo(0, 0, quantity=5))
    monster = make_monster(3, 1, hp=20, defense=0, ai=None)
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(FireAction(3, 1))

    # 5 base + 3 bow bonus - 0 defense = 8 damage
    assert monster.fighter.hp == 20 - 8
    assert player.inventory[0].item.quantity == 4


def test_fire_action_records_a_ranged_attack_event():
    game_map = make_open_map(5, 3)
    player = make_player(1, 1, attack=5)
    player.equipped_ranged_weapon = make_ranged_weapon(0, 0, ranged_attack_bonus=3)
    player.inventory.append(make_ammo(0, 0, quantity=5))
    monster = make_monster(3, 1, hp=20, defense=0, ai=None)
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(FireAction(3, 1))

    assert engine.ranged_attack_events == [(1, 1, 3, 1)]


def test_ranged_attack_events_do_not_persist_across_process_turn_calls():
    """main.py drains and clears this list every turn; a stale event from a
    prior turn must never leak into a turn where nothing was fired."""
    game_map = make_open_map(5, 3)
    player = make_player(1, 1, attack=5)
    player.equipped_ranged_weapon = make_ranged_weapon(0, 0, ranged_attack_bonus=3)
    player.inventory.append(make_ammo(0, 0, quantity=5))
    monster = make_monster(3, 1, hp=20, defense=0, ai=None)
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(FireAction(3, 1))
    engine.ranged_attack_events = []  # main.py's drain, simulated
    engine.process_turn(WaitAction())

    assert engine.ranged_attack_events == []


def test_fire_action_removes_ammo_stack_when_it_reaches_zero():
    game_map = make_open_map(5, 3)
    player = make_player(1, 1)
    player.equipped_ranged_weapon = make_ranged_weapon(0, 0)
    player.inventory.append(make_ammo(0, 0, quantity=1))
    monster = make_monster(3, 1, hp=20, ai=None)
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(FireAction(3, 1))

    assert player.inventory == []


def test_reaching_terminal_stairs_down_signals_wants_overworld():
    game_map = make_open_map(3, 3)
    game_map.kinds[2, 1] = "stairs_down"
    game_map.stairs[(2, 1)] = None
    player = make_player(1, 1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(BumpAction(1, 0))

    assert engine.wants_overworld is True
    assert engine.game_state == "playing"  # the run continues, just on a different Engine


def test_reaching_terminal_stairs_up_also_signals_wants_overworld():
    game_map = make_open_map(3, 3)
    game_map.kinds[2, 1] = "stairs_up"
    game_map.stairs[(2, 1)] = None
    player = make_player(1, 1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(BumpAction(1, 0))

    assert engine.wants_overworld is True
    assert engine.game_state == "playing"
    assert "retreat" in engine.message_log.messages[-1]


def test_descending_stairs_swaps_level_and_preserves_player():
    catalog = load_catalog()
    levels = load_levels(LEVELS_DIR, catalog)
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
    every hop resolves and the run actually reaches its terminal stairs - not
    just that each transition works in isolation."""
    catalog = load_catalog()
    levels = load_levels(LEVELS_DIR, catalog)
    level_01 = levels["level_01"]
    game_map, player = build_game_map(level_01, catalog)
    engine = Engine(game_map, player, level_01.name, catalog=catalog, levels=levels)

    for next_level_id in ("level_02a", "level_03", "level_04", "level_05"):
        engine.on_player_reach_stairs(next_level_id)
        assert engine.game_state == "playing"
        assert engine.player is player

    engine.on_player_reach_stairs(None)  # level_05's terminal stairs
    assert engine.wants_overworld is True
    assert engine.game_state == "playing"


def test_full_prison_tower_chain_is_completable():
    """Same end-to-end shape as the Forgotten Ruins chain test, for the
    other shipped dungeon - a linear escape, no branch to pick between."""
    catalog = load_catalog()
    levels = load_levels(PRISON_TOWER_LEVELS_DIR, catalog)
    level_01 = levels["level_01"]
    game_map, player = build_game_map(level_01, catalog)
    engine = Engine(game_map, player, level_01.name, catalog=catalog, levels=levels)

    for next_level_id in ("level_02", "level_03", "level_04"):
        engine.on_player_reach_stairs(next_level_id)
        assert engine.game_state == "playing"
        assert engine.player is player

    engine.on_player_reach_stairs(None)  # level_04's terminal stairs (the gatehouse exit)
    assert engine.wants_overworld is True
    assert engine.game_state == "playing"


def test_ascending_returns_to_the_same_cached_map_with_state_preserved():
    """The core promise of this feature: a revisited level is the *same*
    GameMap object, not a respawned copy - so a dead monster stays dead and
    a picked-up item stays gone across the round trip."""
    catalog = load_catalog()
    levels = load_levels(PRISON_TOWER_LEVELS_DIR, catalog)
    level_01 = levels["level_01"]
    game_map, player = build_game_map(level_01, catalog)
    engine = Engine(
        game_map, player, level_01.name,
        catalog=catalog, levels=levels, starting_level=level_01,
    )
    original_level_01_map = engine.game_map

    guard = next(e for e in engine.game_map.entities if e.name == "Guard")
    engine.on_entity_death(guard)
    assert guard not in engine.game_map.entities

    dagger = next(e for e in engine.game_map.entities if e.name == "Rusty Dagger")
    engine.game_map.entities.remove(dagger)
    player.inventory.append(dagger)

    engine.on_player_reach_stairs("level_02")  # down through level_01's ">"
    assert engine.game_map is not original_level_01_map
    assert engine.level_name == "The Guard Barracks"

    engine.on_player_reach_stairs("level_01", "stairs_up")  # back up via level_02's "<"

    assert engine.game_map is original_level_01_map  # same object - not rebuilt
    assert (player.x, player.y) == (20, 12)  # landed on level_01's ">" tile, not player_start
    assert guard not in engine.game_map.entities  # still dead
    assert dagger in player.inventory  # still picked up, not respawned
    assert engine.message_log.messages[-1] == "You ascend to The Solitary Cell."


def test_departing_a_level_removes_the_player_from_its_entity_list():
    """Regression test: build_game_map re-appends the player into the new
    map but never removed them from the old one - harmless while old maps
    were always discarded, but would leave a stale duplicate @ behind now
    that maps get cached and reused."""
    catalog = load_catalog()
    levels = load_levels(PRISON_TOWER_LEVELS_DIR, catalog)
    level_01 = levels["level_01"]
    game_map, player = build_game_map(level_01, catalog)
    engine = Engine(
        game_map, player, level_01.name,
        catalog=catalog, levels=levels, starting_level=level_01,
    )
    old_map = engine.game_map

    engine.on_player_reach_stairs("level_02")

    assert player not in old_map.entities
    assert player in engine.game_map.entities


def test_arrival_falls_back_to_player_start_when_no_return_stairway():
    """forgotten_ruins defines no stairs_up anywhere, so every hop there
    must keep landing at player_start exactly as it did before this
    feature existed."""
    catalog = load_catalog()
    levels = load_levels(LEVELS_DIR, catalog)
    level_01 = levels["level_01"]
    game_map, player = build_game_map(level_01, catalog)
    engine = Engine(
        game_map, player, level_01.name,
        catalog=catalog, levels=levels, starting_level=level_01,
    )

    engine.on_player_reach_stairs("level_02a")

    assert (player.x, player.y) == levels["level_02a"].player_start


def test_restart_clears_the_visited_level_cache():
    catalog = load_catalog()
    levels = load_levels(PRISON_TOWER_LEVELS_DIR, catalog)
    level_01 = levels["level_01"]
    game_map, player = build_game_map(level_01, catalog)
    engine = Engine(
        game_map, player, level_01.name,
        catalog=catalog, levels=levels, starting_level=level_01,
    )

    guard = next(e for e in engine.game_map.entities if e.name == "Guard")
    engine.on_entity_death(guard)
    engine.on_player_reach_stairs("level_02")
    engine.on_player_reach_stairs("level_01", "stairs_up")
    assert guard not in engine.game_map.entities  # confirmed cached (still dead)

    engine.restart()
    engine.on_player_reach_stairs("level_02")
    engine.on_player_reach_stairs("level_01", "stairs_up")

    assert any(e.name == "Guard" for e in engine.game_map.entities)  # back - fresh map


def test_level_01_branches_to_two_different_levels():
    catalog = load_catalog()
    levels = load_levels(LEVELS_DIR, catalog)
    game_map, _player = build_game_map(levels["level_01"], catalog)

    # None is the terminal retreat stairs_up (leaves to the overworld), not
    # a branch destination - excluded here since this test is specifically
    # about the two different *level* destinations.
    destinations = set(game_map.stairs.values()) - {None}
    assert destinations == {"level_02a", "level_02b"}


def test_restart_after_death_gives_a_fresh_run():
    catalog = load_catalog()
    levels = load_levels(LEVELS_DIR, catalog)
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


def test_restart_after_reaching_terminal_stairs_returns_to_starting_level():
    catalog = load_catalog()
    levels = load_levels(LEVELS_DIR, catalog)
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
    engine.on_player_reach_stairs(None)  # reach a terminal stairway, wants_overworld set

    engine.restart()

    assert engine.game_state == "playing"
    assert engine.wants_overworld is False  # cleared, not carried into the fresh run
    assert engine.level_name == "The Rotting Cellar"
    assert (engine.player.x, engine.player.y) == level_01.player_start


def test_build_game_map_assigns_terrain_passability():
    catalog = load_catalog()
    level = load_overworld(
        FIXTURES_DIR / "overworld_valid.lvl", catalog, known_dungeon_ids={"prison_tower"}
    )
    game_map, _player = build_game_map(level, catalog)

    # "#" -> mountain: impassable and opaque, like a dungeon wall.
    assert not game_map.walkable[0, 0]
    assert not game_map.transparent[0, 0]
    # "." -> plains: ordinary open ground.
    assert game_map.walkable[2, 1]
    assert game_map.transparent[2, 1]


def test_build_game_map_populates_dungeon_entrances():
    catalog = load_catalog()
    level = load_overworld(
        FIXTURES_DIR / "overworld_valid.lvl", catalog, known_dungeon_ids={"prison_tower"}
    )
    game_map, _player = build_game_map(level, catalog)

    assert game_map.dungeon_entrances == {(3, 1): "prison_tower"}


def test_build_game_map_populates_tile_descriptions():
    catalog = load_catalog()
    level = load_overworld(
        FIXTURES_DIR / "overworld_valid.lvl", catalog, known_dungeon_ids={"prison_tower"}
    )
    game_map, _player = build_game_map(level, catalog)

    assert game_map.tile_descriptions == {(3, 1): "A black stone tower."}


def test_depart_player_removes_and_caches_and_clears_mailbox():
    catalog = load_catalog()
    levels = load_levels(PRISON_TOWER_LEVELS_DIR, catalog)
    level_01 = levels["level_01"]
    game_map, player = build_game_map(level_01, catalog)
    engine = Engine(
        game_map, player, level_01.name, catalog=catalog, levels=levels, starting_level=level_01,
    )
    engine.wants_overworld = True
    engine.pending_dungeon_entry = "forgotten_ruins"

    returned = engine.depart_player()

    assert returned is player
    assert player not in engine.game_map.entities
    assert engine.visited_maps["level_01"] is engine.game_map
    assert engine.wants_overworld is False
    assert engine.pending_dungeon_entry is None


def test_arrive_player_with_explicit_position_repositions():
    catalog = load_catalog()
    levels = load_levels(PRISON_TOWER_LEVELS_DIR, catalog)
    level_01 = levels["level_01"]
    game_map, player = build_game_map(level_01, catalog)
    engine = Engine(game_map, player, level_01.name, catalog=catalog)
    engine.game_map.entities.remove(player)

    engine.arrive_player(player, position=(4, 4))

    assert (player.x, player.y) == (4, 4)
    assert player in engine.game_map.entities
    assert engine.message_log.messages[-1] == f"You enter {level_01.name}."


def test_arrive_player_with_no_position_resumes_last_departure_spot():
    """arrive_player(position=None) must restore *this* Engine's own
    remembered last_position, not just whatever the player Entity's current
    x/y happen to be - those get overwritten by every other map the player
    visits in between (typically the overworld), so trusting the entity's
    live position instead of last_position was a real bug."""
    catalog = load_catalog()
    levels = load_levels(PRISON_TOWER_LEVELS_DIR, catalog)
    level_01 = levels["level_01"]
    game_map, player = build_game_map(level_01, catalog)
    engine = Engine(game_map, player, level_01.name, catalog=catalog)
    player.x, player.y = 7, 9

    engine.depart_player()  # records last_position = (7, 9)
    player.x, player.y = 99, 99  # simulate the player moving on some other map

    engine.arrive_player(player)  # no position -> resume exactly where they left

    assert (player.x, player.y) == (7, 9)
    assert player in engine.game_map.entities


def test_movement_onto_dungeon_entrance_sets_pending_dungeon_entry():
    catalog = load_catalog()
    level = load_overworld(
        FIXTURES_DIR / "overworld_valid.lvl", catalog, known_dungeon_ids={"prison_tower"}
    )
    game_map, player = build_game_map(level, catalog)
    engine = Engine(game_map, player, level.name, catalog=catalog)

    engine.process_turn(BumpAction(1, 0))  # (1,1) -> (2,1), open plains, no trigger
    assert engine.pending_dungeon_entry is None

    engine.process_turn(BumpAction(1, 0))  # (2,1) -> (3,1), the dungeon_entrance tile

    assert engine.pending_dungeon_entry == "prison_tower"
    assert engine.wants_overworld is False  # the two mailboxes are independent


def test_engine_defaults_dungeon_inspect_text_to_empty_dict():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")

    assert engine.dungeon_inspect_text == {}


def test_engine_stores_given_dungeon_inspect_text():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    engine = Engine(
        game_map, player, "Test Level",
        dungeon_inspect_text={"prison_tower": "A black stone tower."},
    )

    assert engine.dungeon_inspect_text == {"prison_tower": "A black stone tower."}


def test_process_turn_advances_clock_on_the_overworld():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "The Overworld", is_overworld=True)

    engine.process_turn(WaitAction())

    assert engine.clock.hour == STARTING_HOUR + 1


def test_process_turn_does_not_advance_clock_in_a_dungeon():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")  # is_overworld defaults False

    engine.process_turn(WaitAction())

    assert engine.clock == GameClock()


def test_process_turn_heals_player_by_one_hp_on_the_overworld():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30)
    player.fighter.hp = 10
    game_map.entities.append(player)
    engine = Engine(game_map, player, "The Overworld", is_overworld=True)

    engine.process_turn(WaitAction())

    assert player.fighter.hp == 11


def test_process_turn_heal_is_capped_at_max_hp():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "The Overworld", is_overworld=True)

    engine.process_turn(WaitAction())

    assert player.fighter.hp == 30


def test_process_turn_advances_clock_regardless_of_action_success():
    game_map = make_open_map(3, 3)
    game_map.walkable[2, 1] = False  # a wall to bump into
    player = make_player(1, 1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "The Overworld", is_overworld=True)

    engine.process_turn(BumpAction(1, 0))

    assert (player.x, player.y) == (1, 1)  # the move failed...
    assert engine.clock.hour == STARTING_HOUR + 1  # ...but the hour still passed


def test_restart_resets_the_shared_world_clock():
    catalog = load_catalog()
    levels = load_levels(LEVELS_DIR, catalog)
    starting_level = levels["level_01"]
    game_map, player = build_game_map(starting_level, catalog)
    engine = Engine(
        game_map, player, starting_level.name,
        catalog=catalog, levels=levels, starting_level=starting_level,
    )
    for _ in range(5):
        engine.clock.advance_hour()
    assert engine.clock != GameClock()

    engine.restart()

    assert engine.clock == GameClock()


def test_shared_clock_object_is_visible_across_engines():
    clock = GameClock()

    overworld_map = make_open_map(3, 3)
    overworld_player = make_player(1, 1)
    overworld_map.entities.append(overworld_player)
    overworld_engine = Engine(
        overworld_map, overworld_player, "The Overworld", is_overworld=True, clock=clock
    )

    dungeon_map = make_open_map(3, 3)
    dungeon_player = make_player(1, 1)
    dungeon_map.entities.append(dungeon_player)
    dungeon_engine = Engine(dungeon_map, dungeon_player, "Test Level", clock=clock)

    assert dungeon_engine.clock is overworld_engine.clock

    overworld_engine.process_turn(WaitAction())

    assert dungeon_engine.clock.hour == STARTING_HOUR + 1
