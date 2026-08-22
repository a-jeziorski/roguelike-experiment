"""Engine/action/combat logic tests. Most are built directly against engine
world-objects (no content files involved) so game rules are verified independently
of parsing; a few level-transition tests use the real shipped dungeon content to
verify the loader and engine agree on level ids and player_start positions."""

import random
from pathlib import Path

from content.loader import load_catalog, load_level, load_levels, load_overworld, load_quests
from engine.actions import BumpAction, FireAction, PickupAction, UseItemAction, WaitAction
from engine.clock import HOURS_PER_DAY, STARTING_DAY, STARTING_HOUR, STARTING_YEAR, GameClock
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
from engine.quest import Quest, QuestLog, create_quest_log

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LEVELS_DIR = DATA_DIR / "dungeons" / "forgotten_ruins" / "levels"
PRISON_TOWER_LEVELS_DIR = DATA_DIR / "dungeons" / "prison_tower" / "levels"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
QUESTS_PATH = DATA_DIR / "quests.yaml"


def real_quest_log() -> QuestLog:
    """The real starting QuestLog, built from data/quests.yaml the same way
    main.py builds it - for tests that exercise real quest content
    (ids/entities/items/rewards) rather than a synthetic Quest/QuestLog."""
    catalog = load_catalog()
    return create_quest_log(load_quests(QUESTS_PATH, catalog))


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
    alert_radius=None, flee_hp_pct=None, ranged_range=None, stationary=False,
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
        stationary=stationary,
    )


def make_villager(
    x: int, y: int, dialogue="", entity_id="villager", name="Villager",
    shop_inventory: list[str] | None = None,
) -> Entity:
    return Entity(
        x, y, "v", (170, 140, 90), name,
        blocks_movement=True,
        render_priority=RENDER_PRIORITY_ACTOR,
        fighter=Fighter(max_hp=10, hp=10, attack=0, defense=0),
        ai="villager",
        dialogue=dialogue,
        entity_id=entity_id,
        shop_inventory=shop_inventory,
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


def make_gold(x: int, y: int, gold_amount: int = 10, name: str = "Gold Pile") -> Entity:
    return Entity(
        x, y, "$", (255, 210, 60), name,
        render_priority=RENDER_PRIORITY_ITEM,
        item=ItemEffect(gold_amount=gold_amount),
    )


def make_quest_item(x: int, y: int, entity_id: str, name: str = "Pale Fungus") -> Entity:
    """A plain item Entity with no ItemEffect fields set - matches how a
    fetch-quest item (e.g. pale_fungus) is actually authored: no
    heal_amount/bonuses/gold_amount, just a stable entity_id to match
    against Quest.target_item_id."""
    return Entity(
        x, y, "%", (180, 200, 150), name,
        render_priority=RENDER_PRIORITY_ITEM,
        item=ItemEffect(),
        entity_id=entity_id,
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


def test_combat_messages_are_logged_with_combat_category():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    monster = make_monster(2, 1, hp=5, defense=0, ai=None)
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(BumpAction(1, 0))

    assert engine.message_log.messages[-1].category == "combat"


def test_talk_dialogue_is_logged_with_dialogue_category():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    villager = make_villager(2, 1, dialogue="Hello.")
    game_map.entities.extend([player, villager])
    engine = Engine(game_map, player, "Test Level")

    engine.talk_to_adjacent()

    assert engine.message_log.messages[-1].category == "dialogue"


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


def test_process_player_action_returns_false_when_not_playing():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")
    engine.game_state = "dead"

    result = engine.process_player_action(BumpAction(1, 0))

    assert result is False
    assert (player.x, player.y) == (1, 1)  # action never performed


def test_process_player_action_returns_true_and_performs_the_action_when_playing():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")

    result = engine.process_player_action(BumpAction(1, 0))

    assert result is True
    assert (player.x, player.y) == (2, 1)


def test_process_enemy_phase_runs_ai_turns_on_its_own():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, defense=0)
    monster = make_monster(2, 1, hp=5, attack=4, ai="hostile_basic")
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_enemy_phase()

    assert player.fighter.hp == 30 - 4  # the monster attacked, with no process_player_action call this turn


def test_process_turn_matches_the_two_phases_called_back_to_back():
    """process_turn is a thin wrapper - splitting it must not change its
    externally observable behavior for any caller that doesn't care about
    mid-turn animation timing (every other test in this file relies on
    exactly this)."""
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, defense=0)
    monster = make_monster(2, 1, hp=5, attack=4, ai="hostile_basic")
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert player.fighter.hp == 30 - 4  # both phases ran within the one call


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


def test_stationary_villager_holds_position_when_undamaged(monkeypatch):
    # If _wander were called at all, this would move the villager - pinning
    # random.choice to a non-stay-put value makes sure stationary is what's
    # holding position, not a lucky "stay put" wander roll.
    monkeypatch.setattr(random, "choice", lambda seq: (1, 0))
    game_map = make_open_map(5, 3)
    player = make_player(0, 1, hp=30)
    villager = make_monster(2, 1, hp=4, attack=0, ai="villager", stationary=True)
    game_map.entities.extend([player, villager])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert (villager.x, villager.y) == (2, 1)  # held position - stationary, never wandered


def test_stationary_villager_still_flees_once_damaged():
    game_map = make_open_map(5, 3)
    player = make_player(2, 1, hp=30)
    villager = make_monster(3, 1, hp=4, attack=0, ai="villager", stationary=True)
    villager.fighter.hp = 3  # any damage at all
    game_map.entities.extend([player, villager])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert (villager.x, villager.y) == (4, 1)  # stepped directly away, same as any villager
    assert player.fighter.hp == 30


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


def test_town_guard_wanders_when_peaceful(monkeypatch):
    monkeypatch.setattr(random, "choice", lambda seq: (1, 0))
    game_map = make_open_map(5, 3)
    player = make_player(0, 1, hp=30)
    guard = make_monster(2, 1, hp=14, attack=5, ai="town_guard")
    game_map.entities.extend([player, guard])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert (guard.x, guard.y) == (3, 1)  # moved per the pinned random choice
    assert player.fighter.hp == 30  # never attacked


def test_town_guard_holds_position_when_wander_pick_is_stay_put(monkeypatch):
    monkeypatch.setattr(random, "choice", lambda seq: (0, 0))
    game_map = make_open_map(5, 3)
    player = make_player(0, 1, hp=30)
    guard = make_monster(2, 1, hp=14, attack=5, ai="town_guard")
    game_map.entities.extend([player, guard])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert (guard.x, guard.y) == (2, 1)


def test_town_guard_never_attacks_on_its_own_initiative_even_when_adjacent():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30)
    guard = make_monster(2, 1, hp=14, attack=5, ai="town_guard")
    game_map.entities.extend([player, guard])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert player.fighter.hp == 30  # adjacent, but the map was never provoked


def test_town_guard_chases_and_attacks_once_the_map_is_provoked():
    game_map = make_open_map(5, 3)
    player = make_player(0, 1, hp=30, defense=0)
    guard = make_monster(3, 1, hp=14, attack=5, ai="town_guard")
    game_map.player_attacked_peaceful_npc = True
    game_map.entities.extend([player, guard])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert (guard.x, guard.y) == (2, 1)  # stepped toward the player, distance was 3


def test_town_guard_attacks_when_provoked_and_already_adjacent():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, defense=0)
    guard = make_monster(2, 1, hp=14, attack=5, ai="town_guard")
    game_map.player_attacked_peaceful_npc = True
    game_map.entities.extend([player, guard])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert player.fighter.hp == 30 - 5


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


def test_gold_pickup_increments_player_gold_and_removes_from_map():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    gold = make_gold(1, 1, gold_amount=10)
    game_map.entities.extend([player, gold])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(PickupAction())

    assert player.gold == 10
    assert gold not in game_map.entities


def test_second_gold_pickup_adds_to_running_total():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    player.gold = 10
    more_gold = make_gold(1, 1, gold_amount=25, name="Gold Stash")
    game_map.entities.extend([player, more_gold])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(PickupAction())

    assert player.gold == 35
    assert more_gold not in game_map.entities


def test_gold_pickup_never_enters_inventory():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    gold = make_gold(1, 1, gold_amount=10)
    game_map.entities.extend([player, gold])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(PickupAction())

    assert player.inventory == []


def test_fetch_quest_item_pickup_is_always_an_ordinary_pickup():
    """PickupAction has no fetch-quest special case at all (see
    engine/actions.py) - picking up a fetch-quest item always enters
    inventory like anything else, regardless of the matching quest's
    status. Completion only ever happens later, via delivery - see
    test_talk_to_adjacent_completes_a_fetch_quest_when_carrying_the_item."""
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    fungus = make_quest_item(1, 1, entity_id="pale_fungus")
    game_map.entities.extend([player, fungus])
    quest = Quest(
        id="fetch_test", name="Fetch Test", description="",
        completion_message="Got it.", questgiver_entity_id="shopkeeper",
        target_item_id="pale_fungus", status="in_progress",
    )
    quest_log = QuestLog(quests={quest.id: quest})
    engine = Engine(game_map, player, "Test Level", quest_log=quest_log)

    engine.process_turn(PickupAction())

    assert quest.status == "in_progress"
    assert "Got it." not in engine.message_log.messages
    assert fungus not in game_map.entities
    assert len(player.inventory) == 1
    assert player.inventory[0] is fungus


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

    # Simulate a run in progress: damaged, geared up, gold collected, and one
    # monster killed.
    player.fighter.hp = 1
    player.equipped_weapon = make_weapon(0, 0, attack_bonus=10)
    player.inventory.append(make_potion(0, 0))
    player.gold = 50
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
    assert engine.player.gold == 0
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


def test_build_game_map_entity_dialogue_prefers_spawn_override(tmp_path):
    level_path = tmp_path / "with_dialogue.lvl"
    level_path.write_text(
        "id: with_dialogue\n"
        "name: Test Level\n"
        "map: |\n"
        "  ###\n"
        "  #@#\n"
        "  #v#\n"
        "  #>#\n"
        "  ###\n"
        "legend:\n"
        '  "#": wall\n'
        '  ".": floor\n'
        '  "@": player_start\n'
        '  ">": stairs_down\n'
        '  "v": { entity: villager, dialogue: "A specific line for this one." }\n',
        encoding="utf-8",
    )
    catalog = load_catalog()
    level = load_level(level_path, catalog)
    game_map, _player = build_game_map(level, catalog)

    villager = next(e for e in game_map.entities if e.name == "Villager")
    assert villager.dialogue == "A specific line for this one."
    assert villager.entity_id == "villager"


def test_build_game_map_entity_dialogue_falls_back_to_catalog_default(tmp_path):
    level_path = tmp_path / "no_dialogue.lvl"
    level_path.write_text(
        "id: no_dialogue\n"
        "name: Test Level\n"
        "map: |\n"
        "  ###\n"
        "  #@#\n"
        "  #v#\n"
        "  #>#\n"
        "  ###\n"
        "legend:\n"
        '  "#": wall\n'
        '  ".": floor\n'
        '  "@": player_start\n'
        '  ">": stairs_down\n'
        '  "v": { entity: villager }\n',
        encoding="utf-8",
    )
    catalog = load_catalog()
    level = load_level(level_path, catalog)
    game_map, _player = build_game_map(level, catalog)

    villager = next(e for e in game_map.entities if e.name == "Villager")
    assert villager.dialogue == catalog.entities["villager"].dialogue
    assert villager.dialogue  # the real catalog entry sets a non-empty fallback


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


def test_engine_defaults_quest_log_to_empty():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")

    assert engine.quest_log == QuestLog()


def test_engine_stores_given_quest_log():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    quest_log = real_quest_log()
    engine = Engine(game_map, player, "Test Level", quest_log=quest_log)

    assert engine.quest_log is quest_log


def test_process_turn_logs_quest_failure_once_deadline_crossed_on_the_overworld():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    quest = Quest(
        id="test_quest", name="Test Quest", description="",
        completion_message="done", failure_message="too late",
        deadline_year=STARTING_YEAR, deadline_day=STARTING_DAY, target_dungeon_id="millhaven",
        status="in_progress",
    )
    quest_log = QuestLog(quests={quest.id: quest})
    clock = GameClock(year=STARTING_YEAR, day=STARTING_DAY, hour=HOURS_PER_DAY - 1)
    engine = Engine(
        game_map, player, "The Overworld", is_overworld=True, clock=clock, quest_log=quest_log,
    )

    engine.process_turn(WaitAction())  # crosses into the next day - deadline passed

    assert quest.status == "failed"
    assert "too late" in engine.message_log.messages

    engine.process_turn(WaitAction())  # a later turn must not repeat the message

    assert engine.message_log.messages.count("too late") == 1


def test_process_turn_does_not_touch_quest_state_in_a_dungeon():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    quest = Quest(
        id="test_quest", name="Test Quest", description="",
        completion_message="done", failure_message="too late",
        deadline_year=STARTING_YEAR, deadline_day=STARTING_DAY, target_dungeon_id="millhaven",
        status="in_progress",
    )
    quest_log = QuestLog(quests={quest.id: quest})
    clock = GameClock(year=STARTING_YEAR, day=STARTING_DAY, hour=HOURS_PER_DAY - 1)
    engine = Engine(game_map, player, "Test Level", clock=clock, quest_log=quest_log)

    engine.process_turn(WaitAction())

    assert quest.status == "in_progress"
    assert engine.message_log.messages == ["You enter Test Level."]


def test_restart_resets_the_shared_quest_log():
    catalog = load_catalog()
    levels = load_levels(LEVELS_DIR, catalog)
    starting_level = levels["level_01"]
    game_map, player = build_game_map(starting_level, catalog)
    quest_log = real_quest_log()
    engine = Engine(
        game_map, player, starting_level.name,
        catalog=catalog, levels=levels, starting_level=starting_level, quest_log=quest_log,
    )
    quest_log.quests["goblin_warning"].status = "failed"

    engine.restart()

    assert quest_log.quests["goblin_warning"].status == "in_progress"


def test_shared_quest_log_object_is_visible_across_engines():
    quest_log = real_quest_log()

    overworld_map = make_open_map(3, 3)
    overworld_player = make_player(1, 1)
    overworld_map.entities.append(overworld_player)
    overworld_engine = Engine(
        overworld_map, overworld_player, "The Overworld", is_overworld=True, quest_log=quest_log,
    )

    dungeon_map = make_open_map(3, 3)
    dungeon_player = make_player(1, 1)
    dungeon_map.entities.append(dungeon_player)
    dungeon_engine = Engine(dungeon_map, dungeon_player, "Test Level", quest_log=quest_log)

    assert dungeon_engine.quest_log is overworld_engine.quest_log

    dungeon_engine.quest_log.check_talked_to("village_chief")

    assert overworld_engine.quest_log.quests["goblin_warning"].status == "completed"


def test_talk_to_adjacent_shows_the_villagers_dialogue():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    villager = make_villager(2, 1, dialogue="Well held up better than most things.")
    game_map.entities.extend([player, villager])
    engine = Engine(game_map, player, "Test Level")

    engine.talk_to_adjacent()

    assert 'Villager: "Well held up better than most things."' in engine.message_log.messages


def test_talk_to_adjacent_falls_back_to_catalog_default_dialogue():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    villager = make_villager(2, 1, dialogue="")  # no per-spawn override
    game_map.entities.extend([player, villager])
    engine = Engine(game_map, player, "Test Level")

    engine.talk_to_adjacent()

    assert 'Villager: "They don\'t seem to have anything to say."' in engine.message_log.messages


def test_talk_to_adjacent_with_no_one_nearby():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")

    engine.talk_to_adjacent()

    assert "There's no one here to talk to." in engine.message_log.messages


def test_talk_to_adjacent_ignores_hostile_monsters():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    rat = make_monster(2, 1, ai="hostile_basic")
    game_map.entities.extend([player, rat])
    engine = Engine(game_map, player, "Test Level")

    engine.talk_to_adjacent()

    assert "There's no one here to talk to." in engine.message_log.messages


def test_talk_to_adjacent_ignores_a_fleeing_villager():
    """Regression test: an NPC that's been hurt (and so is permanently
    fleeing per AI_VILLAGER's own rules) shouldn't be talkable - the player
    shouldn't be able to attack a villager and then still get their normal
    dialogue line."""
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    villager = make_villager(2, 1, dialogue="Hello.")
    villager.fighter.hp = 5  # any damage at all triggers permanent fleeing
    game_map.entities.extend([player, villager])
    engine = Engine(game_map, player, "Test Level")

    engine.talk_to_adjacent()

    assert "There's no one here to talk to." in engine.message_log.messages
    assert 'Villager: "Hello."' not in engine.message_log.messages


def test_talk_to_adjacent_completes_a_matching_quest():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    chief = make_villager(2, 1, dialogue="Tell me what you can, then.", entity_id="village_chief")
    game_map.entities.extend([player, chief])
    quest_log = real_quest_log()
    engine = Engine(game_map, player, "Test Level", quest_log=quest_log)

    engine.talk_to_adjacent()

    quest = quest_log.quests["goblin_warning"]
    assert quest.status == "completed"
    assert quest.completion_message in engine.message_log.messages


def test_talk_to_adjacent_chief_uses_the_followup_line_after_the_quest_completes():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    chief = make_villager(2, 1, dialogue="Tell me what you can, then.", entity_id="village_chief", name="Village Chief")
    game_map.entities.extend([player, chief])
    quest_log = real_quest_log()
    engine = Engine(game_map, player, "Test Level", quest_log=quest_log)

    engine.talk_to_adjacent()  # first Talk: shows the original line, completes the quest
    engine.message_log.messages.clear()
    engine.talk_to_adjacent()  # second Talk: quest is now completed

    quest = quest_log.quests["goblin_warning"]
    assert f'Village Chief: "{quest.target_done_dialogue}"' in engine.message_log.messages
    assert 'Village Chief: "Tell me what you can, then."' not in engine.message_log.messages
    assert quest.completion_message not in engine.message_log.messages  # not repeated


def test_talk_to_adjacent_does_not_complete_a_non_target_villager():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    villager = make_villager(2, 1, dialogue="Can't talk.", entity_id="villager")
    game_map.entities.extend([player, villager])
    quest_log = real_quest_log()
    engine = Engine(game_map, player, "Test Level", quest_log=quest_log)

    engine.talk_to_adjacent()

    quest = quest_log.quests["goblin_warning"]
    assert quest.status == "in_progress"
    assert quest.completion_message not in engine.message_log.messages


def test_talk_to_adjacent_does_not_repeat_completion_message():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    chief = make_villager(2, 1, dialogue="Tell me what you can, then.", entity_id="village_chief")
    game_map.entities.extend([player, chief])
    quest_log = real_quest_log()
    engine = Engine(game_map, player, "Test Level", quest_log=quest_log)

    engine.talk_to_adjacent()
    engine.talk_to_adjacent()

    quest = quest_log.quests["goblin_warning"]
    assert engine.message_log.messages.count(quest.completion_message) == 1


def test_talk_to_adjacent_after_deadline_failure_does_not_complete_the_quest():
    """Talk isn't turn-coupled to movement the way dungeon-entry was, so the
    old same-turn race between deadline-failure and completion can't happen
    for this trigger - but a quest that already failed on an earlier turn
    must still stay failed if the player talks to the target NPC afterward."""
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    chief = make_villager(2, 1, dialogue="Tell me what you can, then.", entity_id="village_chief")
    game_map.entities.extend([player, chief])
    quest_log = real_quest_log()
    quest = quest_log.quests["goblin_warning"]
    clock = GameClock(year=quest.deadline_year, day=quest.deadline_day + 1, hour=0)
    engine = Engine(game_map, player, "Test Level", clock=clock, quest_log=quest_log)
    engine._check_quest_deadlines()
    assert quest.status == "failed"

    engine.talk_to_adjacent()

    assert quest.status == "failed"
    assert quest.completion_message not in engine.message_log.messages


def test_talk_to_adjacent_never_advances_the_clock_or_processes_enemy_turns():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    villager = make_villager(2, 1, dialogue="Hello.")
    rat = make_monster(0, 0, ai="hostile_basic")
    game_map.entities.extend([player, villager, rat])
    clock = GameClock()
    engine = Engine(game_map, player, "The Overworld", is_overworld=True, clock=clock)
    rat_start = (rat.x, rat.y)

    engine.talk_to_adjacent()

    assert engine.clock == GameClock()  # untouched
    assert (rat.x, rat.y) == rat_start  # no enemy turn was processed


# --- questgivers, kill-quests, and reward granting ---


def make_warden(x: int, y: int, hp: int = 5) -> Entity:
    return Entity(
        x, y, "W", (140, 40, 40), "Warden",
        blocks_movement=True,
        render_priority=RENDER_PRIORITY_ACTOR,
        fighter=Fighter(max_hp=hp, hp=hp, attack=0, defense=0),
        entity_id="warden",
    )


def test_on_entity_death_completes_a_kill_quest_and_grants_reward():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    warden = make_warden(2, 1)
    game_map.entities.extend([player, warden])
    quest_log = real_quest_log()
    quest = quest_log.quests["kill_the_warden"]
    quest.status = "in_progress"  # simulate having already been granted
    engine = Engine(game_map, player, "Test Level", catalog=catalog, quest_log=quest_log)

    engine.on_entity_death(warden)

    assert quest.status == "completed"
    assert quest.completion_message in engine.message_log.messages
    assert len(player.inventory) == 1
    assert player.inventory[0].name == "Healing Potion"


def test_on_entity_death_records_kill_before_quest_is_given():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    warden = make_warden(2, 1)
    game_map.entities.extend([player, warden])
    quest_log = real_quest_log()  # kill_the_warden still "not_given"
    engine = Engine(game_map, player, "Test Level", catalog=catalog, quest_log=quest_log)

    engine.on_entity_death(warden)

    quest = quest_log.quests["kill_the_warden"]
    assert quest.status == "not_given"
    assert "warden" in quest_log.killed_entity_ids
    assert player.inventory == []  # no reward - the quest was never completed


def test_talk_to_adjacent_grants_a_questgiver_quest():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    prisoner = make_villager(2, 1, dialogue="Made it out too.", entity_id="escaped_prisoner", name="Escaped Prisoner")
    game_map.entities.extend([player, prisoner])
    quest_log = real_quest_log()
    engine = Engine(game_map, player, "Test Level", catalog=catalog, quest_log=quest_log)

    engine.talk_to_adjacent()

    quest = quest_log.quests["kill_the_warden"]
    assert quest.status == "in_progress"
    assert quest.given_message in engine.message_log.messages
    assert player.inventory == []  # not completed yet, no reward


def test_talk_to_adjacent_questgiver_already_done_completes_immediately():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    prisoner = make_villager(2, 1, dialogue="Made it out too.", entity_id="escaped_prisoner", name="Escaped Prisoner")
    game_map.entities.extend([player, prisoner])
    quest_log = real_quest_log()
    quest_log.record_entity_killed("warden")  # already killed before being asked
    engine = Engine(game_map, player, "Test Level", catalog=catalog, quest_log=quest_log)

    engine.talk_to_adjacent()

    quest = quest_log.quests["kill_the_warden"]
    assert quest.status == "completed"
    assert quest.already_done_message in engine.message_log.messages
    assert quest.given_message not in engine.message_log.messages
    assert len(player.inventory) == 1
    assert player.inventory[0].name == "Healing Potion"


def test_talk_to_adjacent_auto_pins_a_granted_quest_when_nothing_was_pinned():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    prisoner = make_villager(2, 1, dialogue="Made it out too.", entity_id="escaped_prisoner", name="Escaped Prisoner")
    game_map.entities.extend([player, prisoner])
    quest_log = real_quest_log()
    quest_log.active_quest_id = None
    engine = Engine(game_map, player, "Test Level", catalog=catalog, quest_log=quest_log)

    engine.talk_to_adjacent()

    assert quest_log.active_quest_id == "kill_the_warden"


def test_talk_to_adjacent_does_not_bump_an_already_pinned_quest():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    prisoner = make_villager(2, 1, dialogue="Made it out too.", entity_id="escaped_prisoner", name="Escaped Prisoner")
    game_map.entities.extend([player, prisoner])
    quest_log = real_quest_log()  # active_quest_id starts as "goblin_warning"
    engine = Engine(game_map, player, "Test Level", catalog=catalog, quest_log=quest_log)

    engine.talk_to_adjacent()

    assert quest_log.active_quest_id == "goblin_warning"  # unchanged


def test_talk_to_adjacent_retroactive_completion_does_not_auto_pin():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    prisoner = make_villager(2, 1, dialogue="Made it out too.", entity_id="escaped_prisoner", name="Escaped Prisoner")
    game_map.entities.extend([player, prisoner])
    quest_log = real_quest_log()
    quest_log.active_quest_id = None
    quest_log.record_entity_killed("warden")
    engine = Engine(game_map, player, "Test Level", catalog=catalog, quest_log=quest_log)

    engine.talk_to_adjacent()

    assert quest_log.active_quest_id is None  # a just-finished quest never auto-pins


def test_talk_to_adjacent_still_shows_normal_dialogue_before_quest_is_completed():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    prisoner = make_villager(2, 1, dialogue="Made it out too.", entity_id="escaped_prisoner", name="Escaped Prisoner")
    game_map.entities.extend([player, prisoner])
    quest_log = real_quest_log()
    engine = Engine(game_map, player, "Test Level", catalog=catalog, quest_log=quest_log)

    engine.talk_to_adjacent()  # grants the quest, does not complete it

    assert 'Escaped Prisoner: "Made it out too."' in engine.message_log.messages


def test_talk_to_adjacent_uses_the_followup_line_after_the_quest_completes():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    prisoner = make_villager(2, 1, dialogue="Made it out too.", entity_id="escaped_prisoner", name="Escaped Prisoner")
    game_map.entities.extend([player, prisoner])
    quest_log = real_quest_log()
    quest_log.record_entity_killed("warden")  # already dead
    engine = Engine(game_map, player, "Test Level", catalog=catalog, quest_log=quest_log)

    engine.talk_to_adjacent()  # first Talk: completes the quest retroactively
    engine.message_log.messages.clear()
    engine.talk_to_adjacent()  # second Talk: quest is now completed

    quest = quest_log.quests["kill_the_warden"]
    assert f'Escaped Prisoner: "{quest.questgiver_done_dialogue}"' in engine.message_log.messages
    assert 'Escaped Prisoner: "Made it out too."' not in engine.message_log.messages
    # the reward and completion message aren't repeated on a later re-talk
    assert quest.completion_message not in engine.message_log.messages
    assert len(player.inventory) == 1


def test_talk_to_adjacent_completes_a_fetch_quest_when_carrying_the_item():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    fungus = make_quest_item(1, 1, entity_id="pale_fungus")
    player.inventory.append(fungus)
    shopkeeper = make_villager(2, 1, dialogue="Anything I can get you?", entity_id="shopkeeper", name="Shopkeeper")
    game_map.entities.extend([player, shopkeeper])
    quest_log = real_quest_log()
    quest_log.quests["fetch_fungus"].status = "in_progress"  # already given, not yet delivered
    engine = Engine(game_map, player, "Test Level", catalog=catalog, quest_log=quest_log)

    engine.talk_to_adjacent()

    quest = quest_log.quests["fetch_fungus"]
    assert quest.status == "completed"
    assert quest.completion_message in engine.message_log.messages
    assert fungus not in player.inventory
    assert engine.shop_price("healing_potion") == 20  # discount reward granted


def test_talk_to_adjacent_does_not_complete_a_fetch_quest_without_the_item():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    shopkeeper = make_villager(2, 1, dialogue="Anything I can get you?", entity_id="shopkeeper", name="Shopkeeper")
    game_map.entities.extend([player, shopkeeper])
    quest_log = real_quest_log()
    quest_log.quests["fetch_fungus"].status = "in_progress"
    engine = Engine(game_map, player, "Test Level", catalog=catalog, quest_log=quest_log)

    engine.talk_to_adjacent()

    quest = quest_log.quests["fetch_fungus"]
    assert quest.status == "in_progress"
    assert player.inventory == []


def test_talk_to_adjacent_does_not_complete_a_fetch_quest_via_the_wrong_npc():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    fungus = make_quest_item(1, 1, entity_id="pale_fungus")
    player.inventory.append(fungus)
    prisoner = make_villager(2, 1, dialogue="Made it out too.", entity_id="escaped_prisoner", name="Escaped Prisoner")
    game_map.entities.extend([player, prisoner])
    quest_log = real_quest_log()
    quest_log.quests["fetch_fungus"].status = "in_progress"
    engine = Engine(game_map, player, "Test Level", catalog=catalog, quest_log=quest_log)

    engine.talk_to_adjacent()

    quest = quest_log.quests["fetch_fungus"]
    assert quest.status == "in_progress"
    assert fungus in player.inventory


def test_talk_to_adjacent_grants_and_delivers_a_fetch_quest_in_one_talk_when_already_carrying_the_item():
    """Emergent behavior from check_questgiver and check_delivery both
    running inside the same talk_to_adjacent call: if the player already
    picked up the fungus (an entirely ordinary pickup - see
    test_fetch_quest_item_pickup_is_always_an_ordinary_pickup) before ever
    talking to the shopkeeper, one Talk both grants and immediately
    delivers the quest."""
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    fungus = make_quest_item(1, 1, entity_id="pale_fungus")
    player.inventory.append(fungus)
    shopkeeper = make_villager(2, 1, dialogue="Anything I can get you?", entity_id="shopkeeper", name="Shopkeeper")
    game_map.entities.extend([player, shopkeeper])
    quest_log = real_quest_log()  # fetch_fungus starts not_given
    engine = Engine(game_map, player, "Test Level", catalog=catalog, quest_log=quest_log)

    engine.talk_to_adjacent()

    quest = quest_log.quests["fetch_fungus"]
    assert quest.status == "completed"
    assert fungus not in player.inventory


def test_complete_quest_with_no_reward_item_leaves_inventory_untouched():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level", catalog=catalog)
    quest = Quest(
        id="no_reward", name="No Reward", description="",
        completion_message="Done.", reward_item_id=None,
    )

    engine.complete_quest(quest)

    assert "Done." in engine.message_log.messages
    assert player.inventory == []


def test_complete_quest_with_a_shop_discount_reward_logs_the_discount_message():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    quest_log = QuestLog()
    engine = Engine(game_map, player, "Test Level", quest_log=quest_log)
    quest = Quest(
        id="discount_test", name="Discount Test", description="",
        completion_message="Done.", reward_shop_discount_pct=0.2,
    )
    quest_log.quests[quest.id] = quest

    engine.complete_quest(quest)

    assert "Done." in engine.message_log.messages
    assert "20% discount" in engine.message_log.messages[-1]
    assert player.inventory == []
    assert player.gold == 0


def test_complete_quest_with_no_catalog_does_not_crash():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")  # catalog defaults to None
    quest = Quest(
        id="with_reward", name="With Reward", description="",
        completion_message="Done.", reward_item_id="healing_potion",
    )

    engine.complete_quest(quest)  # must not raise

    assert "Done." in engine.message_log.messages
    assert player.inventory == []


# --- town guard hostility trigger (engine/combat.py) ---


def test_attacking_a_villager_sets_the_map_hostility_flag():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    villager = make_villager(2, 1)
    game_map.entities.extend([player, villager])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(BumpAction(1, 0))

    assert game_map.player_attacked_peaceful_npc is True


def test_attacking_a_town_guard_sets_the_map_hostility_flag():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    guard = make_monster(2, 1, hp=14, attack=5, ai="town_guard")
    game_map.entities.extend([player, guard])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(BumpAction(1, 0))

    assert game_map.player_attacked_peaceful_npc is True


def test_attacking_a_hostile_monster_does_not_set_the_map_hostility_flag():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    monster = make_monster(2, 1, hp=5, defense=0, ai=None)
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(BumpAction(1, 0))

    assert game_map.player_attacked_peaceful_npc is False


def test_a_monster_attacking_the_player_does_not_set_the_map_hostility_flag():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, defense=0)
    monster = make_monster(2, 1, hp=5, attack=4, ai="hostile_basic")
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())  # the monster attacks the player, not the other way around

    assert game_map.player_attacked_peaceful_npc is False


def test_a_zero_damage_attack_on_a_villager_still_sets_the_flag():
    """Confirms the trigger is 'attacks,' not 'hurts' - a hit that deals no
    damage still counts as an attack."""
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, attack=0)  # 0 attack vs 0 defense = no damage
    villager = make_villager(2, 1)
    game_map.entities.extend([player, villager])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(BumpAction(1, 0))

    assert villager.fighter.hp == villager.fighter.max_hp  # confirms no damage was dealt
    assert game_map.player_attacked_peaceful_npc is True


def test_talk_to_adjacent_works_on_a_peaceful_town_guard():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    guard = make_villager(2, 1, dialogue="Keep the peace and we've got no trouble between us.", entity_id="town_guard", name="Town Guard")
    guard.ai = "town_guard"
    guard.fighter = Fighter(max_hp=14, hp=14, attack=5, defense=2)
    game_map.entities.extend([player, guard])
    engine = Engine(game_map, player, "Test Level")

    engine.talk_to_adjacent()

    assert 'Town Guard: "Keep the peace and we\'ve got no trouble between us."' in engine.message_log.messages


def test_talk_to_adjacent_ignores_a_town_guard_once_the_map_is_provoked_even_if_undamaged():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    guard = make_villager(2, 1, dialogue="Keep the peace.", entity_id="town_guard", name="Town Guard")
    guard.ai = "town_guard"
    guard.fighter = Fighter(max_hp=14, hp=14, attack=5, defense=2)  # still at full hp
    game_map.player_attacked_peaceful_npc = True
    game_map.entities.extend([player, guard])
    engine = Engine(game_map, player, "Test Level")

    engine.talk_to_adjacent()

    assert "There's no one here to talk to." in engine.message_log.messages
    assert 'Town Guard: "Keep the peace."' not in engine.message_log.messages


def test_talk_to_adjacent_villager_unaffected_by_the_town_wide_hostility_flag():
    """Confirms the guard/villager asymmetry is intentional: the map flag
    only governs town_guard entities - a villager stays talkable (as long
    as they're personally undamaged) even after the flag trips."""
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    villager = make_villager(2, 1, dialogue="Hello.")
    game_map.player_attacked_peaceful_npc = True
    game_map.entities.extend([player, villager])
    engine = Engine(game_map, player, "Test Level")

    engine.talk_to_adjacent()

    assert 'Villager: "Hello."' in engine.message_log.messages


# --- shopkeeper / buy_from_shop ---


def test_adjacent_shopkeeper_finds_an_npc_with_shop_inventory():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    shopkeeper = make_villager(
        2, 1, dialogue="Coin still spends here.", entity_id="shopkeeper", name="Shopkeeper",
        shop_inventory=["healing_potion"],
    )
    game_map.entities.extend([player, shopkeeper])
    engine = Engine(game_map, player, "Test Level")

    assert engine.adjacent_shopkeeper() is shopkeeper


def test_adjacent_shopkeeper_ignores_a_plain_villager_with_no_shop_inventory():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    villager = make_villager(2, 1, dialogue="Hello.", entity_id="villager")
    game_map.entities.extend([player, villager])
    engine = Engine(game_map, player, "Test Level")

    assert engine.adjacent_shopkeeper() is None


def test_adjacent_shopkeeper_none_when_nothing_nearby():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")

    assert engine.adjacent_shopkeeper() is None


def test_adjacent_shopkeeper_ignores_a_fleeing_shopkeeper():
    """Regression test: attacking the shopkeeper and making them flee must
    also close off the shop, not just ordinary Talk."""
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    shopkeeper = make_villager(
        2, 1, dialogue="Coin still spends here.", entity_id="shopkeeper", name="Shopkeeper",
        shop_inventory=["healing_potion"],
    )
    shopkeeper.fighter.hp = 5
    game_map.entities.extend([player, shopkeeper])
    engine = Engine(game_map, player, "Test Level")

    assert engine.adjacent_shopkeeper() is None


def test_adjacent_shopkeeper_finds_a_distinct_shopkeeper_with_its_own_stock():
    """The generalization this refactor is for: any catalog entity can be
    an independent shopkeeper with its own shop_inventory - not just one
    hardcoded id - so two different towns' shopkeepers each work
    unchanged, on their own stock, with no shared state between them."""
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    weapon_seller = make_villager(
        2, 1, entity_id="wayford_weaponsmith", name="Weaponsmith",
        shop_inventory=["rusty_dagger"],
    )
    game_map.entities.extend([player, weapon_seller])
    engine = Engine(game_map, player, "Test Level")

    found = engine.adjacent_shopkeeper()

    assert found is weapon_seller
    assert found.shop_inventory == ["rusty_dagger"]


def test_talk_to_adjacent_still_works_unfiltered_alongside_the_shopkeeper_filter():
    """Regression test: generalizing _find_adjacent_peaceful_npc to accept a
    requires_shop filter must not change talk_to_adjacent's own unfiltered
    no-arg call."""
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    shopkeeper = make_villager(
        2, 1, dialogue="Coin still spends here.", entity_id="shopkeeper", name="Shopkeeper",
        shop_inventory=["healing_potion"],
    )
    game_map.entities.extend([player, shopkeeper])
    engine = Engine(game_map, player, "Test Level")

    engine.talk_to_adjacent()

    assert 'Shopkeeper: "Coin still spends here."' in engine.message_log.messages


def make_shopkeeper(x: int, y: int, shop_inventory=("healing_potion",)) -> Entity:
    return make_villager(
        x, y, entity_id="shopkeeper", name="Shopkeeper", shop_inventory=list(shop_inventory),
    )


def test_buy_from_shop_with_enough_gold_deducts_gold_and_grants_item():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    player.gold = 30
    game_map.entities.extend([player, make_shopkeeper(2, 1)])
    engine = Engine(game_map, player, "Test Level", catalog=catalog)

    message = engine.buy_from_shop("healing_potion")

    assert player.gold == 5
    assert len(player.inventory) == 1
    assert player.inventory[0].name == "Healing Potion"
    assert message == "You buy a Healing Potion for 25 gold."
    assert message in engine.message_log.messages


def test_buy_from_shop_without_enough_gold_does_nothing():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    player.gold = 10
    game_map.entities.extend([player, make_shopkeeper(2, 1)])
    engine = Engine(game_map, player, "Test Level", catalog=catalog)

    message = engine.buy_from_shop("healing_potion")

    assert player.gold == 10
    assert player.inventory == []
    assert message == "You can't afford that."
    assert message in engine.message_log.messages


def test_buy_from_shop_a_second_time_rechecks_affordability_against_the_lower_total():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    player.gold = 30
    game_map.entities.extend([player, make_shopkeeper(2, 1)])
    engine = Engine(game_map, player, "Test Level", catalog=catalog)

    first = engine.buy_from_shop("healing_potion")
    second = engine.buy_from_shop("healing_potion")

    assert first == "You buy a Healing Potion for 25 gold."
    assert second == "You can't afford that."
    assert player.gold == 5
    assert len(player.inventory) == 1


def test_buy_from_shop_rejects_a_catalog_item_not_in_this_shopkeepers_stock():
    """The gap closed by this refactor: buy_from_shop used to only check
    the catalog, so any real item id would sell regardless of what the
    adjacent shopkeeper actually stocks. iron_sword is a real catalog item
    with a cost, just not one this shopkeeper sells."""
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    player.gold = 100
    game_map.entities.extend([player, make_shopkeeper(2, 1, shop_inventory=["healing_potion"])])
    engine = Engine(game_map, player, "Test Level", catalog=catalog)

    message = engine.buy_from_shop("iron_sword")

    assert message == "The shop is unavailable."
    assert player.gold == 100
    assert player.inventory == []


def test_buy_from_shop_with_no_shopkeeper_adjacent_is_unavailable():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    player.gold = 100
    game_map.entities.append(player)  # no shopkeeper anywhere
    engine = Engine(game_map, player, "Test Level", catalog=catalog)

    message = engine.buy_from_shop("healing_potion")

    assert message == "The shop is unavailable."
    assert player.gold == 100
    assert player.inventory == []


def test_shop_price_is_the_full_cost_with_no_discount_unlocked():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level", catalog=catalog)

    assert engine.shop_price("healing_potion") == 25


def test_shop_price_reflects_the_fungus_quests_discount_once_completed():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    quest_log = real_quest_log()
    quest_log.quests["fetch_fungus"].status = "completed"
    engine = Engine(game_map, player, "Test Level", catalog=catalog, quest_log=quest_log)

    assert engine.shop_price("healing_potion") == 20


def test_buy_from_shop_charges_the_discounted_price():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    player.gold = 20
    game_map.entities.extend([player, make_shopkeeper(2, 1)])
    quest_log = real_quest_log()
    quest_log.quests["fetch_fungus"].status = "completed"
    engine = Engine(game_map, player, "Test Level", catalog=catalog, quest_log=quest_log)

    message = engine.buy_from_shop("healing_potion")

    assert message == "You buy a Healing Potion for 20 gold."
    assert player.gold == 0
    assert len(player.inventory) == 1


def test_buy_from_shop_with_no_catalog_does_not_crash():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    player.gold = 100
    game_map.entities.extend([player, make_shopkeeper(2, 1)])
    engine = Engine(game_map, player, "Test Level")  # catalog defaults to None

    message = engine.buy_from_shop("healing_potion")  # must not raise

    assert message == "The shop is unavailable."
    assert player.gold == 100
    assert player.inventory == []


def test_buy_from_shop_never_advances_the_clock_or_processes_enemy_turns():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    player.gold = 30
    rat = make_monster(0, 0, ai="hostile_basic")
    game_map.entities.extend([player, rat, make_shopkeeper(2, 1)])
    clock = GameClock()
    engine = Engine(game_map, player, "The Overworld", is_overworld=True, catalog=catalog, clock=clock)
    rat_start = (rat.x, rat.y)

    engine.buy_from_shop("healing_potion")

    assert engine.clock == GameClock()  # untouched
    assert (rat.x, rat.y) == rat_start  # no enemy turn was processed
