"""Engine/action/combat logic tests. Most are built directly against engine
world-objects (no content files involved) so game rules are verified independently
of parsing; a few level-transition tests use the real shipped dungeon content to
verify the loader and engine agree on level ids and player_start positions."""

import random
from pathlib import Path

import engine.combat
from content.loader import load_catalog, load_level, load_levels, load_overworld, load_quests
from content.schema import FlagDialogue, TightenDeadline, WorldConsequence
from engine.actions import (
    SMOKE_BOMB_TELEPORT_RADIUS,
    BumpAction,
    FireAction,
    PickupAction,
    UseItemAction,
    UsePotionSlotAction,
    UseSkillAction,
    UseSkillSlotAction,
    WaitAction,
)
from engine.clock import HOURS_PER_DAY, STARTING_DAY, STARTING_HOUR, STARTING_YEAR, GameClock
from engine.engine import (
    CINDER_MARCHES_BAND,
    ENVIRONMENTAL_HAZARD_DAMAGE,
    FRAYED_EDGE_BAND,
    HOLLOW_REACH_BAND,
    VISITOR_BAND_ENCOUNTER_CHANCE,
    Engine,
    roll_visitor_band,
)
from engine.entity import (
    RENDER_PRIORITY_ACTOR,
    RENDER_PRIORITY_ITEM,
    RENDER_PRIORITY_PLAYER,
    ActiveEffect,
    Entity,
    Fighter,
    ItemEffect,
    potion_kind,
)
from engine.game_map import DARK_FOV_RADIUS, FOV_RADIUS, PLAYER_ATTACK, GameMap, build_game_map, entity_from_def
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
    poison_potency=None, poison_duration=None, inflicts_effect=None,
    inflicts_potency=None, inflicts_duration=None,
    enrage_hp_pct=None, enrage_attack_bonus=None,
    pack_radius=None, pack_attack_bonus=None, regen_amount=None,
    drop_item_id=None, drop_chance=None,
    split_count=None, split_hp_fraction=None, can_split=True, entity_id="",
    summon_entity_id=None, summon_interval=None, summon_max_active=None,
    charge_range=None, charge_attack_bonus=None, territory_radius=None,
    ambush_bonus=None, scavenge_radius=None, scavenge_heal_fraction=None,
    mimic_bonus=None, blocks_movement=True,
) -> Entity:
    # poison_potency/poison_duration kept as this helper's own kwarg names
    # (translated below) purely so the many existing call sites that pass
    # them didn't all need touching for this generalization - inflicts_effect
    # is the real, general param, needed only by tests exercising stun/weaken.
    if poison_potency is not None or poison_duration is not None:
        inflicts_effect, inflicts_potency, inflicts_duration = (
            "poison", poison_potency, poison_duration,
        )
    return Entity(
        x, y, "r", (140, 90, 60), "Rat",
        blocks_movement=blocks_movement,
        render_priority=RENDER_PRIORITY_ACTOR,
        fighter=Fighter(max_hp=hp, hp=hp, attack=attack, defense=defense),
        ai=ai,
        alert_radius=alert_radius,
        flee_hp_pct=flee_hp_pct,
        ranged_range=ranged_range,
        inflicts_effect=inflicts_effect,
        inflicts_potency=inflicts_potency,
        inflicts_duration=inflicts_duration,
        enrage_hp_pct=enrage_hp_pct,
        enrage_attack_bonus=enrage_attack_bonus,
        pack_radius=pack_radius,
        pack_attack_bonus=pack_attack_bonus,
        regen_amount=regen_amount,
        drop_item_id=drop_item_id,
        drop_chance=drop_chance,
        split_count=split_count,
        split_hp_fraction=split_hp_fraction,
        can_split=can_split,
        summon_entity_id=summon_entity_id,
        summon_interval=summon_interval,
        summon_max_active=summon_max_active,
        charge_range=charge_range,
        charge_attack_bonus=charge_attack_bonus,
        territory_radius=territory_radius,
        ambush_bonus=ambush_bonus,
        scavenge_radius=scavenge_radius,
        scavenge_heal_fraction=scavenge_heal_fraction,
        mimic_bonus=mimic_bonus,
        stationary=stationary,
        entity_id=entity_id,
    )


def make_villager(
    x: int, y: int, dialogue="", entity_id="villager", name="Villager",
    shop_inventory: list[str] | None = None,
    trainer_perks: list[str] | None = None,
    flag_dialogue: list[FlagDialogue] | None = None,
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
        trainer_perks=trainer_perks,
        flag_dialogue=flag_dialogue,
    )


def make_potion(x: int, y: int, heal_amount=10) -> Entity:
    return Entity(
        x, y, "!", (220, 40, 100), "Healing Potion",
        blocks_movement=False,
        render_priority=RENDER_PRIORITY_ITEM,
        item=ItemEffect(heal_amount=heal_amount),
    )


def make_teleport_potion(x: int, y: int) -> Entity:
    return Entity(
        x, y, "?", (80, 120, 240), "Teleportation Potion",
        blocks_movement=False,
        render_priority=RENDER_PRIORITY_ITEM,
        item=ItemEffect(is_teleport=True),
    )


def make_water_walking_potion(x: int, y: int, duration: int = 20) -> Entity:
    return Entity(
        x, y, "~", (50, 190, 180), "Water Walking Potion",
        blocks_movement=False,
        render_priority=RENDER_PRIORITY_ITEM,
        item=ItemEffect(water_walking_duration=duration),
    )


def make_antidote_potion(x: int, y: int) -> Entity:
    return Entity(
        x, y, "!", (90, 200, 90), "Antidote",
        blocks_movement=False,
        render_priority=RENDER_PRIORITY_ITEM,
        item=ItemEffect(cures_effects=True),
    )


def make_vigor_potion(x: int, y: int, potency: int = 3, duration: int = 10) -> Entity:
    return Entity(
        x, y, "!", (230, 130, 40), "Elixir of Vigor",
        blocks_movement=False,
        render_priority=RENDER_PRIORITY_ITEM,
        item=ItemEffect(grants_buff="vigor", buff_potency=potency, buff_duration=duration),
    )


def make_haste_potion(x: int, y: int, duration: int = 3) -> Entity:
    return Entity(
        x, y, "!", (90, 220, 230), "Draught of Swiftness",
        blocks_movement=False,
        render_priority=RENDER_PRIORITY_ITEM,
        item=ItemEffect(grants_buff="haste", buff_duration=duration),
    )


def make_shadow_potion(x: int, y: int, duration: int = 8) -> Entity:
    return Entity(
        x, y, "!", (70, 60, 100), "Vial of Shadows",
        blocks_movement=False,
        render_priority=RENDER_PRIORITY_ITEM,
        item=ItemEffect(grants_buff="shadowed", buff_duration=duration),
    )


def make_second_sight_potion(x: int, y: int) -> Entity:
    return Entity(
        x, y, "!", (190, 170, 230), "Bottled Second Sight",
        blocks_movement=False,
        render_priority=RENDER_PRIORITY_ITEM,
        item=ItemEffect(reveals_map=True),
    )


def make_sure_footing_potion(x: int, y: int, duration: int = 15) -> Entity:
    return Entity(
        x, y, "!", (150, 120, 70), "Sure-Footing Draught",
        blocks_movement=False,
        render_priority=RENDER_PRIORITY_ITEM,
        item=ItemEffect(grants_buff="sure_footed", buff_duration=duration),
    )


def make_smoke_bomb(x: int, y: int, duration: int = 3) -> Entity:
    return Entity(
        x, y, "!", (110, 110, 120), "Smoke Bomb",
        blocks_movement=False,
        render_priority=RENDER_PRIORITY_ITEM,
        item=ItemEffect(local_teleport=True, grants_buff="shadowed", buff_duration=duration),
    )


def make_clarity_potion(x: int, y: int) -> Entity:
    return Entity(
        x, y, "!", (220, 200, 160), "Bezoar of Clarity",
        blocks_movement=False,
        render_priority=RENDER_PRIORITY_ITEM,
        item=ItemEffect(resets_skill_cooldowns=True),
    )


def make_key(x: int, y: int, key_id: str = "rusty_key", name: str = "Rusty Key") -> Entity:
    return Entity(
        x, y, "-", (200, 170, 60), name,
        blocks_movement=False,
        render_priority=RENDER_PRIORITY_ITEM,
        item=ItemEffect(key_id=key_id),
    )


def make_weapon(
    x: int, y: int, attack_bonus: int = 2, name: str = "Rusty Dagger",
    affix_effect=None, affix_potency=None, affix_duration=None, affix_chance=None,
) -> Entity:
    return Entity(
        x, y, "/", (180, 180, 190), name,
        render_priority=RENDER_PRIORITY_ITEM,
        item=ItemEffect(
            attack_bonus=attack_bonus,
            affix_effect=affix_effect, affix_potency=affix_potency,
            affix_duration=affix_duration, affix_chance=affix_chance,
        ),
    )


def make_armor(
    x: int, y: int, defense_bonus: int = 1, name: str = "Leather Armor",
    affix_effect=None, affix_potency=None, affix_duration=None, affix_chance=None,
) -> Entity:
    return Entity(
        x, y, "[", (150, 110, 60), name,
        render_priority=RENDER_PRIORITY_ITEM,
        item=ItemEffect(
            defense_bonus=defense_bonus,
            affix_effect=affix_effect, affix_potency=affix_potency,
            affix_duration=affix_duration, affix_chance=affix_chance,
        ),
    )


def make_ranged_weapon(
    x: int, y: int, ranged_attack_bonus: int = 3, range_: int = 5, name: str = "Hunting Bow"
) -> Entity:
    return Entity(
        x, y, "}", (160, 120, 70), name,
        render_priority=RENDER_PRIORITY_ITEM,
        item=ItemEffect(ranged_attack_bonus=ranged_attack_bonus, range=range_),
    )


def make_trinket(
    x: int, y: int, trinket_effect: str = "crit_chance", trinket_bonus: float = 0.5, name: str = "Lucky Charm",
) -> Entity:
    return Entity(
        x, y, "'", (230, 200, 90), name,
        render_priority=RENDER_PRIORITY_ITEM,
        item=ItemEffect(trinket_effect=trinket_effect, trinket_bonus=trinket_bonus),
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
    game_map.entities.extend([player, guard])
    engine = Engine(game_map, player, "Test Level")
    game_map.trigger_guard_hostility(engine.clock)

    engine.process_turn(WaitAction())

    assert (guard.x, guard.y) == (2, 1)  # stepped toward the player, distance was 3


def test_town_guard_attacks_when_provoked_and_already_adjacent():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, defense=0)
    guard = make_monster(2, 1, hp=14, attack=5, ai="town_guard")
    game_map.entities.extend([player, guard])
    engine = Engine(game_map, player, "Test Level")
    game_map.trigger_guard_hostility(engine.clock)

    engine.process_turn(WaitAction())

    assert player.fighter.hp == 30 - 5


# --- would_attack_peaceful_npc ---


def test_would_attack_peaceful_npc_returns_none_when_destination_is_empty():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")

    assert engine.would_attack_peaceful_npc(1, 0) is None


def test_would_attack_peaceful_npc_returns_none_for_a_hostile_monster():
    """A bump-attack on a genuinely hostile monster needs no confirmation -
    only a still-peaceful NPC does."""
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    rat = make_monster(2, 1, ai="hostile_basic")
    game_map.entities.extend([player, rat])
    engine = Engine(game_map, player, "Test Level")

    assert engine.would_attack_peaceful_npc(1, 0) is None


def test_would_attack_peaceful_npc_returns_the_entity_for_an_undamaged_villager():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    villager = make_villager(2, 1, dialogue="Hello.")
    game_map.entities.extend([player, villager])
    engine = Engine(game_map, player, "Test Level")

    assert engine.would_attack_peaceful_npc(1, 0) is villager


def test_would_attack_peaceful_npc_returns_none_for_an_already_fleeing_villager():
    """A villager already hurt is already "in it" - see
    Engine._is_currently_peaceful - so a further bump-attack doesn't need
    re-confirming."""
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    villager = make_villager(2, 1, dialogue="Hello.")
    villager.fighter.hp = 5  # already damaged, fleeing
    game_map.entities.extend([player, villager])
    engine = Engine(game_map, player, "Test Level")

    assert engine.would_attack_peaceful_npc(1, 0) is None


def test_would_attack_peaceful_npc_returns_the_entity_for_an_unprovoked_town_guard():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    guard = make_monster(2, 1, hp=14, attack=5, ai="town_guard")
    game_map.entities.extend([player, guard])
    engine = Engine(game_map, player, "Test Level")

    assert engine.would_attack_peaceful_npc(1, 0) is guard


def test_would_attack_peaceful_npc_returns_none_for_a_town_guard_once_the_map_is_provoked():
    """Once GameMap.guards_hostile is True, every town guard is already a
    legitimate combatant - no more confirmations."""
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    guard = make_monster(2, 1, hp=14, attack=5, ai="town_guard")
    game_map.entities.extend([player, guard])
    engine = Engine(game_map, player, "Test Level")
    game_map.trigger_guard_hostility(engine.clock)

    assert engine.would_attack_peaceful_npc(1, 0) is None


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


# --- enrage (bonus attack while badly hurt) ---


def test_enrage_behaves_normally_above_threshold():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, defense=0)
    monster = make_monster(
        2, 1, hp=10, attack=4, ai="enrage", enrage_hp_pct=0.3, enrage_attack_bonus=3,
    )
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert player.fighter.hp == 30 - 4  # full hp, above threshold: no bonus
    assert not any("berserk" in m for m in engine.message_log.messages)


def test_enrage_adds_attack_bonus_at_or_below_threshold():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, defense=0)
    monster = make_monster(
        2, 1, hp=10, attack=4, ai="enrage", enrage_hp_pct=0.3, enrage_attack_bonus=3,
    )
    monster.fighter.hp = 2  # 20%, at/below the 30% threshold
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert player.fighter.hp == 30 - (4 + 3)
    assert any("berserk" in m for m in engine.message_log.messages)


def test_enrage_uses_engine_level_defaults_when_unset():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, defense=0)
    monster = make_monster(2, 1, hp=10, attack=4, ai="enrage")
    monster.fighter.hp = 3  # 30%, at the default 0.3 threshold
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert player.fighter.hp == 30 - (4 + 2)  # DEFAULT_ENRAGE_ATTACK_BONUS


def test_enrage_recovers_if_healed_back_above_threshold():
    monster = make_monster(
        2, 1, hp=10, attack=4, ai="enrage", enrage_hp_pct=0.3, enrage_attack_bonus=3,
    )
    monster.fighter.hp = 2
    assert monster.is_enraged
    assert monster.effective_attack == 4 + 3

    monster.fighter.hp = 10
    assert not monster.is_enraged
    assert monster.effective_attack == 4


# --- pack_hunter (bonus attack with a nearby ally) ---


def test_pack_hunter_attacks_normally_with_no_nearby_ally():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, defense=0)
    monster = make_monster(2, 1, hp=10, attack=4, ai="pack_hunter", pack_radius=3, pack_attack_bonus=3)
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert player.fighter.hp == 30 - 4


def test_pack_hunter_gains_bonus_attack_with_a_nearby_hostile_ally():
    game_map = make_open_map(6, 3)
    player = make_player(0, 1, hp=30, defense=0)
    hunter = make_monster(1, 1, hp=10, attack=4, ai="pack_hunter", pack_radius=3, pack_attack_bonus=3)
    ally = make_monster(3, 1, hp=10, attack=1, ai="hostile_basic")  # too far to reach the player this turn
    game_map.entities.extend([player, hunter, ally])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert player.fighter.hp == 30 - (4 + 3)  # hunter's own hit, boosted
    assert hunter.pack_bonus_active == 3


def test_pack_hunter_ignores_an_ally_outside_pack_radius():
    game_map = make_open_map(10, 3)
    player = make_player(0, 1, hp=30, defense=0)
    hunter = make_monster(1, 1, hp=10, attack=4, ai="pack_hunter", pack_radius=2, pack_attack_bonus=3)
    ally = make_monster(9, 1, hp=10, attack=1, ai="hostile_basic")  # far outside pack_radius
    game_map.entities.extend([player, hunter, ally])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert player.fighter.hp == 30 - 4  # no bonus, ally too far


def test_pack_hunter_ignores_a_peaceful_nearby_entity():
    game_map = make_open_map(6, 3)
    player = make_player(0, 1, hp=30, defense=0)
    hunter = make_monster(1, 1, hp=10, attack=4, ai="pack_hunter", pack_radius=3, pack_attack_bonus=3)
    villager = make_villager(2, 2)
    game_map.entities.extend([player, hunter, villager])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert player.fighter.hp == 30 - 4  # a peaceful neighbor doesn't count as an ally


def test_pack_hunter_uses_engine_level_defaults_when_unset():
    game_map = make_open_map(6, 3)
    player = make_player(0, 1, hp=30, defense=0)
    hunter = make_monster(1, 1, hp=10, attack=4, ai="pack_hunter")
    ally = make_monster(3, 1, hp=10, attack=1, ai="hostile_basic")
    game_map.entities.extend([player, hunter, ally])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert player.fighter.hp == 30 - (4 + 1)  # DEFAULT_PACK_RADIUS=3 covers distance 2, DEFAULT_PACK_ATTACK_BONUS=1


# --- regenerator (heals every turn it acts) ---


def test_regenerator_heals_each_of_its_own_turns():
    game_map = make_open_map(10, 3)
    player = make_player(0, 1, hp=30, defense=0)
    monster = make_monster(5, 1, hp=20, attack=4, ai="regenerator", regen_amount=3)
    monster.fighter.hp = 10
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert monster.fighter.hp == 13  # healed even though nowhere near the player
    assert any("regenerates 3 HP" in m for m in engine.message_log.messages)


def test_regenerator_heal_caps_at_max_hp():
    game_map = make_open_map(10, 3)
    player = make_player(0, 1, hp=30, defense=0)
    monster = make_monster(5, 1, hp=20, attack=4, ai="regenerator", regen_amount=3)
    monster.fighter.hp = 19  # only 1 short of max_hp
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert monster.fighter.hp == 20  # capped, not 22
    assert any("regenerates 1 HP" in m for m in engine.message_log.messages)


def test_regenerator_does_not_heal_or_log_at_full_hp():
    game_map = make_open_map(10, 3)
    player = make_player(0, 1, hp=30, defense=0)
    monster = make_monster(5, 1, hp=20, attack=4, ai="regenerator", regen_amount=3)
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert monster.fighter.hp == 20
    assert not any("regenerates" in m for m in engine.message_log.messages)


def test_regenerator_heals_and_attacks_the_same_turn_when_adjacent():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, defense=0)
    monster = make_monster(2, 1, hp=20, attack=4, ai="regenerator", regen_amount=3)
    monster.fighter.hp = 10
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert monster.fighter.hp == 13  # healed, still attacked the same turn
    assert player.fighter.hp == 30 - 4


def test_regenerator_uses_default_regen_amount_when_unset():
    game_map = make_open_map(10, 3)
    player = make_player(0, 1, hp=30, defense=0)
    monster = make_monster(5, 1, hp=20, attack=4, ai="regenerator")
    monster.fighter.hp = 10
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert monster.fighter.hp == 12  # DEFAULT_REGEN_AMOUNT = 2


# --- splitter (spawns weaker copies on death) ---


def test_splitter_spawns_copies_on_death_at_adjacent_tiles():
    catalog = load_catalog()
    game_map = make_open_map(5, 5)
    player = make_player(0, 0)
    slime = make_monster(
        2, 2, hp=10, attack=3, defense=0, ai="splitter",
        split_count=2, split_hp_fraction=0.4, entity_id="slime",
    )
    game_map.entities.extend([player, slime])
    engine = Engine(game_map, player, "Test Level", catalog=catalog)

    engine.on_entity_death(slime)

    children = [e for e in game_map.entities if e.entity_id == "slime"]
    assert len(children) == 2
    for child in children:
        assert child.fighter.max_hp == 4  # ceil(10 * 0.4)
        assert child.fighter.hp == 4
        assert child.name == "Slime"
        assert child.can_split is False  # can't cascade
        assert max(abs(child.x - 2), abs(child.y - 2)) == 1  # adjacent to where the parent died
    assert any("splits into 2 more" in m for m in engine.message_log.messages)


def test_splitter_copies_cannot_split_again():
    catalog = load_catalog()
    game_map = make_open_map(5, 5)
    player = make_player(0, 0)
    slime = make_monster(
        2, 2, hp=10, attack=3, defense=0, ai="splitter",
        split_count=2, split_hp_fraction=0.4, entity_id="slime", can_split=False,
    )
    game_map.entities.extend([player, slime])
    engine = Engine(game_map, player, "Test Level", catalog=catalog)

    engine.on_entity_death(slime)

    assert [e for e in game_map.entities if e.entity_id == "slime"] == []
    assert not any("splits into" in m for m in engine.message_log.messages)


def test_splitter_uses_the_entitys_own_current_max_hp_not_the_catalog_base():
    """A slime with a boosted max_hp (elite-scaled, or otherwise) splits
    into copies scaled off its own current max_hp, not entities.yaml's
    base hp=16 - so an elite splitter's children are elite-sized too."""
    catalog = load_catalog()
    game_map = make_open_map(5, 5)
    player = make_player(0, 0)
    slime = make_monster(
        2, 2, hp=40, attack=3, defense=0, ai="splitter",
        split_count=1, split_hp_fraction=0.5, entity_id="slime",
    )
    game_map.entities.extend([player, slime])
    engine = Engine(game_map, player, "Test Level", catalog=catalog)

    engine.on_entity_death(slime)

    children = [e for e in game_map.entities if e.entity_id == "slime"]
    assert len(children) == 1
    assert children[0].fighter.max_hp == 20  # ceil(40 * 0.5), not ceil(16 * 0.5)


def test_splitter_spawns_fewer_copies_when_space_is_limited():
    """split_count=2, but only one adjacent tile is actually free - (2,1)
    is walkable but occupied by the player, so nearby_walkable_tiles can
    only offer one spot. Fewer than requested spawn; the request never
    crashes or blocks on missing space."""
    game_map = make_open_map(3, 3)
    game_map.walkable[:, :] = False
    for x, y in [(1, 1), (0, 1), (2, 1)]:
        game_map.walkable[x, y] = True
    catalog = load_catalog()
    player = make_player(2, 1)
    slime = make_monster(
        1, 1, hp=10, attack=3, defense=0, ai="splitter",
        split_count=2, split_hp_fraction=0.4, entity_id="slime",
    )
    game_map.entities.extend([player, slime])
    engine = Engine(game_map, player, "Test Level", catalog=catalog)

    engine.on_entity_death(slime)

    children = [e for e in game_map.entities if e.entity_id == "slime"]
    assert len(children) == 1
    assert (children[0].x, children[0].y) == (0, 1)


def test_splitter_spawns_nothing_when_completely_surrounded():
    game_map = make_open_map(3, 3)
    game_map.walkable[:, :] = False
    game_map.walkable[1, 1] = True  # the slime's own tile, nothing adjacent walkable
    catalog = load_catalog()
    player = make_player(1, 1)  # overlapping the slime is fine - this test never moves either
    slime = make_monster(
        1, 1, hp=10, attack=3, defense=0, ai="splitter",
        split_count=2, split_hp_fraction=0.4, entity_id="slime",
    )
    game_map.entities.append(slime)
    engine = Engine(game_map, player, "Test Level", catalog=catalog)

    engine.on_entity_death(slime)

    assert [e for e in game_map.entities if e.entity_id == "slime"] == []
    assert not any("splits into" in m for m in engine.message_log.messages)


def test_non_splitter_monster_never_splits():
    catalog = load_catalog()
    game_map = make_open_map(5, 5)
    player = make_player(0, 0)
    monster = make_monster(2, 2, hp=10, attack=3, defense=0, ai="hostile_basic", entity_id="rat")
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level", catalog=catalog)

    engine.on_entity_death(monster)

    assert len(game_map.entities) == 1  # just the player - monster removed, nothing spawned


def test_splitter_without_a_catalog_does_not_crash():
    game_map = make_open_map(5, 5)
    player = make_player(0, 0)
    slime = make_monster(
        2, 2, hp=10, attack=3, defense=0, ai="splitter",
        split_count=2, split_hp_fraction=0.4, entity_id="slime",
    )
    game_map.entities.extend([player, slime])
    engine = Engine(game_map, player, "Test Level")  # no catalog

    engine.on_entity_death(slime)  # must not raise

    assert [e for e in game_map.entities if e.entity_id == "slime"] == []


# --- summoner (spawns reinforcements instead of attacking) ---


def test_summoner_summons_on_its_first_turn_instead_of_attacking():
    catalog = load_catalog()
    game_map = make_open_map(5, 5)
    player = make_player(2, 2, hp=30, defense=0)
    caller = make_monster(
        2, 1, hp=14, attack=2, defense=0, ai="summoner",
        summon_entity_id="kobold", summon_interval=4, entity_id="bone_caller",
    )
    game_map.entities.extend([player, caller])
    engine = Engine(game_map, player, "Test Level", catalog=catalog)

    engine.process_turn(WaitAction())

    summoned = [e for e in game_map.entities if e.entity_id == "kobold"]
    assert len(summoned) == 1
    assert max(abs(summoned[0].x - 2), abs(summoned[0].y - 1)) == 1  # adjacent to the caller
    assert player.fighter.hp == 30  # summoning spent the turn, not an attack
    assert caller.summon_cooldown == 4  # reset after the attempt
    assert any("summons a Kobold" in m for m in engine.message_log.messages)


def test_summoner_attacks_normally_while_on_cooldown():
    catalog = load_catalog()
    game_map = make_open_map(5, 5)
    player = make_player(2, 2, hp=30, defense=0)
    caller = make_monster(
        2, 1, hp=14, attack=2, defense=0, ai="summoner",
        summon_entity_id="kobold", summon_interval=4, entity_id="bone_caller",
    )
    caller.summon_cooldown = 3  # not ready yet
    game_map.entities.extend([player, caller])
    engine = Engine(game_map, player, "Test Level", catalog=catalog)

    engine.process_turn(WaitAction())

    assert caller.summon_cooldown == 2  # ticked down, not reset
    assert player.fighter.hp == 30 - 2  # attacked normally instead of summoning
    assert [e for e in game_map.entities if e.entity_id == "kobold"] == []


def test_summoner_respects_its_max_active_cap():
    catalog = load_catalog()
    game_map = make_open_map(5, 5)
    player = make_player(0, 0, hp=30, defense=0)
    caller = make_monster(
        2, 2, hp=14, attack=2, defense=0, ai="summoner",
        summon_entity_id="kobold", summon_interval=4, summon_max_active=1, entity_id="bone_caller",
    )
    existing_child = make_monster(2, 3, hp=8, attack=3, defense=0, ai="hostile_basic", entity_id="kobold")
    caller.summoned_children = [existing_child]
    game_map.entities.extend([player, caller, existing_child])
    engine = Engine(game_map, player, "Test Level", catalog=catalog)

    engine.process_turn(WaitAction())

    kobolds = [e for e in game_map.entities if e.entity_id == "kobold"]
    assert len(kobolds) == 1  # still just the pre-existing one - cap held
    assert caller.summon_cooldown == 4  # the attempt still happened (and reset), just didn't spawn


def test_summoner_can_summon_again_once_a_child_dies():
    catalog = load_catalog()
    game_map = make_open_map(5, 5)
    player = make_player(0, 0, hp=30, defense=0)
    caller = make_monster(
        2, 2, hp=14, attack=2, defense=0, ai="summoner",
        summon_entity_id="kobold", summon_interval=4, summon_max_active=1, entity_id="bone_caller",
    )
    dead_child = make_monster(2, 3, hp=0, attack=3, defense=0, ai="hostile_basic", entity_id="kobold")
    caller.summoned_children = [dead_child]  # already dead - never added to game_map.entities
    game_map.entities.extend([player, caller])
    engine = Engine(game_map, player, "Test Level", catalog=catalog)

    engine.process_turn(WaitAction())

    kobolds = [e for e in game_map.entities if e.entity_id == "kobold"]
    assert len(kobolds) == 1  # the dead reference was pruned, a fresh one spawned


def test_summoner_summons_nothing_when_surrounded():
    game_map = make_open_map(3, 3)
    game_map.walkable[:, :] = False
    game_map.walkable[1, 1] = True
    catalog = load_catalog()
    player = make_player(1, 1)
    caller = make_monster(
        1, 1, hp=14, attack=2, defense=0, ai="summoner",
        summon_entity_id="kobold", summon_interval=4, entity_id="bone_caller",
    )
    game_map.entities.append(caller)
    engine = Engine(game_map, player, "Test Level", catalog=catalog)

    result = engine._maybe_summon(caller)

    assert result is False
    assert [e for e in game_map.entities if e.entity_id == "kobold"] == []
    assert caller.summon_cooldown == 4  # the attempt still happened and reset


def test_summoner_without_a_catalog_never_summons():
    game_map = make_open_map(5, 5)
    player = make_player(2, 2, hp=30, defense=0)
    caller = make_monster(
        2, 1, hp=14, attack=2, defense=0, ai="summoner",
        summon_entity_id="kobold", summon_interval=4, entity_id="bone_caller",
    )
    game_map.entities.extend([player, caller])
    engine = Engine(game_map, player, "Test Level")  # no catalog

    engine.process_turn(WaitAction())

    assert [e for e in game_map.entities if e.entity_id == "kobold"] == []
    assert player.fighter.hp == 30 - 2  # falls through to an ordinary attack instead


# --- charger (lunges several tiles for a bonus hit, then recovers) ---


def test_charger_lunges_across_the_gap_and_lands_a_bonus_hit():
    game_map = make_open_map(7, 3)
    player = make_player(5, 1, hp=30, defense=0)
    boar = make_monster(
        1, 1, hp=12, attack=4, defense=0, ai="charger",
        charge_range=4, charge_attack_bonus=4,
    )
    game_map.entities.extend([player, boar])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert (boar.x, boar.y) == (4, 1)  # covered 3 tiles to land adjacent
    assert player.fighter.hp == 30 - (4 + 4)  # attack + charge_attack_bonus
    assert boar.charge_recovering is True
    assert any("charges into" in m for m in engine.message_log.messages)


def test_charger_recovering_skips_its_entire_next_turn():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, defense=0)
    boar = make_monster(2, 1, hp=12, attack=4, defense=0, ai="charger", charge_range=4, charge_attack_bonus=4)
    boar.charge_recovering = True
    game_map.entities.extend([player, boar])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert player.fighter.hp == 30  # no attack at all this turn, despite being adjacent
    assert boar.charge_recovering is False  # cleared, ready to act again next turn
    assert any("recovering from the charge" in m for m in engine.message_log.messages)


def test_charger_blocked_partway_lands_no_hit_and_does_not_recover():
    game_map = make_open_map(7, 3)
    game_map.walkable[3, 1] = False  # a wall partway along the lunge
    player = make_player(5, 1, hp=30, defense=0)
    boar = make_monster(1, 1, hp=12, attack=4, defense=0, ai="charger", charge_range=4, charge_attack_bonus=4)
    game_map.entities.extend([player, boar])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert (boar.x, boar.y) == (2, 1)  # stopped at the wall, one tile short of it
    assert player.fighter.hp == 30  # never got close enough to land a hit
    assert boar.charge_recovering is False  # a blocked charge costs nothing


def test_charger_out_of_range_chases_one_tile_instead_of_charging():
    game_map = make_open_map(10, 3)
    player = make_player(7, 1, hp=30, defense=0)  # distance 6: past charge_range=4, within FOV_RADIUS=8
    boar = make_monster(1, 1, hp=12, attack=4, defense=0, ai="charger", charge_range=4, charge_attack_bonus=4)
    game_map.entities.extend([player, boar])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert (boar.x, boar.y) == (2, 1)  # ordinary single-step chase, distance (8) exceeds charge_range
    assert player.fighter.hp == 30
    assert boar.charge_recovering is False


def test_charger_not_aligned_chases_one_tile_instead_of_charging():
    game_map = make_open_map(10, 5)
    player = make_player(4, 2, hp=30, defense=0)  # dx=3, dy=1 - neither equal nor zero, not aligned
    boar = make_monster(1, 1, hp=12, attack=4, defense=0, ai="charger", charge_range=4, charge_attack_bonus=4)
    game_map.entities.extend([player, boar])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert (boar.x, boar.y) == (2, 2)  # one ordinary diagonal step, not a straight-line charge
    assert player.fighter.hp == 30
    assert boar.charge_recovering is False


def test_charger_already_adjacent_attacks_normally_without_charging():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, defense=0)
    boar = make_monster(2, 1, hp=12, attack=4, defense=0, ai="charger", charge_range=4, charge_attack_bonus=4)
    game_map.entities.extend([player, boar])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert player.fighter.hp == 30 - 4  # ordinary attack, no charge_attack_bonus applied
    assert boar.charge_recovering is False


def test_charger_uses_default_range_and_bonus_when_unset():
    game_map = make_open_map(7, 3)
    player = make_player(5, 1, hp=30, defense=0)
    boar = make_monster(1, 1, hp=12, attack=4, defense=0, ai="charger")
    game_map.entities.extend([player, boar])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert (boar.x, boar.y) == (4, 1)  # DEFAULT_CHARGE_RANGE=4 covers the gap
    assert player.fighter.hp == 30 - (4 + 3)  # DEFAULT_CHARGE_ATTACK_BONUS=3


# --- territorial (won't chase past a radius from home) ---


def test_territorial_chases_within_its_territory():
    game_map = make_open_map(10, 3)
    player = make_player(3, 1, hp=30, defense=0)
    bear = make_monster(1, 1, hp=22, attack=6, defense=1, ai="territorial", territory_radius=5)
    game_map.entities.extend([player, bear])
    engine = Engine(game_map, player, "Test Level")

    assert (bear.home_x, bear.home_y) == (1, 1)  # captured automatically at spawn

    engine.process_turn(WaitAction())

    assert (bear.x, bear.y) == (2, 1)  # ordinary chase step - still well within territory


def test_territorial_attacks_normally_when_adjacent_even_far_from_home():
    game_map = make_open_map(12, 3)
    player = make_player(11, 1, hp=30, defense=0)
    bear = make_monster(1, 1, hp=22, attack=6, defense=1, ai="territorial", territory_radius=5)
    bear.x, bear.y = 10, 1  # already dragged far outside its own territory
    game_map.entities.extend([player, bear])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert player.fighter.hp == 30 - 6  # still fights back when already adjacent
    assert (bear.x, bear.y) == (10, 1)  # didn't retreat mid-attack


def test_territorial_breaks_off_once_at_the_edge_of_its_territory():
    game_map = make_open_map(10, 3)
    player = make_player(9, 1, hp=30, defense=0)
    bear = make_monster(1, 1, hp=22, attack=6, defense=1, ai="territorial", territory_radius=5)
    bear.x, bear.y = 6, 1  # exactly territory_radius=5 from home (1,1) - the edge
    game_map.entities.extend([player, bear])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert (bear.x, bear.y) == (5, 1)  # stepped back toward home instead of chasing further
    assert player.fighter.hp == 30  # never got close enough to attack


def test_territorial_holds_position_once_home():
    game_map = make_open_map(5, 3)
    player = make_player(0, 0)
    bear = make_monster(2, 1, hp=22, attack=6, defense=1, ai="territorial", territory_radius=5)
    game_map.entities.extend([player, bear])
    engine = Engine(game_map, player, "Test Level")

    engine._return_home(bear)

    assert (bear.x, bear.y) == (2, 1)  # already home - holds position, doesn't jitter


def test_territorial_uses_default_radius_when_unset():
    game_map = make_open_map(10, 3)
    player = make_player(10 - 1, 1, hp=30, defense=0)
    bear = make_monster(1, 1, hp=22, attack=6, defense=1, ai="territorial")
    bear.x, bear.y = 7, 1  # exactly DEFAULT_TERRITORY_RADIUS=6 from home (1,1)
    game_map.entities.extend([player, bear])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert (bear.x, bear.y) == (6, 1)  # broke off at the default radius, not a configured one


# --- ambusher (invisible until adjacent, then a guaranteed reveal-strike) ---


def test_ambusher_entity_starts_hidden():
    lurker = make_monster(1, 1, ai="ambusher")
    assert lurker.hidden is True


def test_non_ambusher_entity_is_never_hidden():
    rat = make_monster(1, 1, ai="hostile_basic")
    assert rat.hidden is False


def test_ambusher_stays_hidden_and_motionless_when_not_adjacent():
    game_map = make_open_map(5, 3)
    player = make_player(3, 1, hp=30, defense=0)
    lurker = make_monster(1, 1, hp=14, attack=5, defense=1, ai="ambusher", ambush_bonus=6)
    game_map.entities.extend([player, lurker])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert (lurker.x, lurker.y) == (1, 1)  # didn't move at all
    assert lurker.hidden is True
    assert player.fighter.hp == 30


def test_ambusher_reveals_and_strikes_the_instant_the_player_is_adjacent():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, defense=0)
    lurker = make_monster(2, 1, hp=14, attack=5, defense=1, ai="ambusher", ambush_bonus=6)
    game_map.entities.extend([player, lurker])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert lurker.hidden is False
    assert player.fighter.hp == 30 - (5 + 6)  # attack + ambush_bonus
    assert any("bursts from hiding" in m for m in engine.message_log.messages)
    assert any("ambushes" in m for m in engine.message_log.messages)


def test_ambusher_behaves_like_an_ordinary_monster_once_revealed():
    game_map = make_open_map(5, 3)
    player = make_player(1, 1, hp=30, defense=0)
    lurker = make_monster(3, 1, hp=14, attack=5, defense=1, ai="ambusher", ambush_bonus=6)
    lurker.hidden = False  # already revealed, e.g. from an earlier turn
    game_map.entities.extend([player, lurker])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert (lurker.x, lurker.y) == (2, 1)  # ordinary single-step chase, not another ambush
    assert player.fighter.hp == 30  # not adjacent yet, so no attack this turn either


def test_ambusher_uses_default_bonus_when_unset():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, defense=0)
    lurker = make_monster(2, 1, hp=14, attack=5, defense=1, ai="ambusher")
    game_map.entities.extend([player, lurker])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert player.fighter.hp == 30 - (5 + 5)  # DEFAULT_AMBUSH_BONUS=5


# --- scavenger (heals off a nearby ally's death) ---


def test_scavenger_heals_when_a_nearby_ally_dies():
    game_map = make_open_map(10, 3)
    player = make_player(0, 1, hp=30, defense=0)
    vulture = make_monster(5, 1, hp=12, attack=3, ai="scavenger", scavenge_radius=6, scavenge_heal_fraction=0.5)
    vulture.fighter.hp = 4
    ally = make_monster(8, 1, hp=10, attack=2, ai="hostile_basic")
    game_map.entities.extend([player, vulture, ally])
    engine = Engine(game_map, player, "Test Level")

    engine.on_entity_death(ally)

    assert vulture.fighter.hp == 10  # 4 + ceil(12 * 0.5) = 10
    assert any("feeds on the fallen Rat, healing 6 HP" in m for m in engine.message_log.messages)


def test_scavenger_heal_caps_at_max_hp():
    game_map = make_open_map(10, 3)
    player = make_player(0, 1, hp=30, defense=0)
    vulture = make_monster(5, 1, hp=12, attack=3, ai="scavenger", scavenge_radius=6, scavenge_heal_fraction=0.5)
    vulture.fighter.hp = 10  # only 2 short of max_hp, less than the 6 a full feeding would give
    ally = make_monster(8, 1, hp=10, attack=2, ai="hostile_basic")
    game_map.entities.extend([player, vulture, ally])
    engine = Engine(game_map, player, "Test Level")

    engine.on_entity_death(ally)

    assert vulture.fighter.hp == 12  # capped, not 16
    assert any("healing 2 HP" in m for m in engine.message_log.messages)


def test_scavenger_out_of_radius_does_not_heal():
    game_map = make_open_map(10, 3)
    player = make_player(0, 1, hp=30, defense=0)
    vulture = make_monster(0, 1, hp=12, attack=3, ai="scavenger", scavenge_radius=3, scavenge_heal_fraction=0.5)
    vulture.fighter.hp = 4
    ally = make_monster(8, 1, hp=10, attack=2, ai="hostile_basic")  # 8 tiles away, beyond radius 3
    game_map.entities.extend([player, vulture, ally])
    engine = Engine(game_map, player, "Test Level")

    engine.on_entity_death(ally)

    assert vulture.fighter.hp == 4
    assert not any("feeds on" in m for m in engine.message_log.messages)


def test_scavenger_does_not_heal_from_a_peaceful_death():
    game_map = make_open_map(10, 3)
    player = make_player(0, 1, hp=30, defense=0)
    vulture = make_monster(5, 1, hp=12, attack=3, ai="scavenger", scavenge_radius=6, scavenge_heal_fraction=0.5)
    vulture.fighter.hp = 4
    villager = make_villager(6, 1)
    game_map.entities.extend([player, vulture, villager])
    engine = Engine(game_map, player, "Test Level")

    engine.on_entity_death(villager)

    assert vulture.fighter.hp == 4
    assert not any("feeds on" in m for m in engine.message_log.messages)


def test_scavenger_uses_default_radius_and_fraction_when_unset():
    game_map = make_open_map(10, 3)
    player = make_player(0, 1, hp=30, defense=0)
    vulture = make_monster(5, 1, hp=12, attack=3, ai="scavenger")  # DEFAULT_SCAVENGE_RADIUS=5, DEFAULT_SCAVENGE_HEAL_FRACTION=0.5
    vulture.fighter.hp = 4
    ally = make_monster(9, 1, hp=10, attack=2, ai="hostile_basic")  # 4 tiles away, within default radius 5
    game_map.entities.extend([player, vulture, ally])
    engine = Engine(game_map, player, "Test Level")

    engine.on_entity_death(ally)

    assert vulture.fighter.hp == 10  # 4 + ceil(12 * 0.5) = 10


def test_scavenger_at_full_hp_does_not_heal_or_log():
    game_map = make_open_map(10, 3)
    player = make_player(0, 1, hp=30, defense=0)
    vulture = make_monster(5, 1, hp=12, attack=3, ai="scavenger", scavenge_radius=6, scavenge_heal_fraction=0.5)
    ally = make_monster(8, 1, hp=10, attack=2, ai="hostile_basic")
    game_map.entities.extend([player, vulture, ally])
    engine = Engine(game_map, player, "Test Level")

    engine.on_entity_death(ally)

    assert vulture.fighter.hp == 12
    assert not any("feeds on" in m for m in engine.message_log.messages)


def test_non_scavenger_monster_never_feeds_on_a_nearby_death():
    game_map = make_open_map(10, 3)
    player = make_player(0, 1, hp=30, defense=0)
    rat = make_monster(5, 1, hp=12, attack=3, ai="hostile_basic")
    rat.fighter.hp = 4
    ally = make_monster(8, 1, hp=10, attack=2, ai="hostile_basic")
    game_map.entities.extend([player, rat, ally])
    engine = Engine(game_map, player, "Test Level")

    engine.on_entity_death(ally)

    assert rat.fighter.hp == 4


def test_scavenger_still_chases_and_attacks_normally_on_its_own_turn():
    game_map = make_open_map(5, 3)
    player = make_player(1, 1, hp=30, defense=0)
    vulture = make_monster(3, 1, hp=12, attack=3, ai="scavenger", scavenge_radius=6, scavenge_heal_fraction=0.5)
    game_map.entities.extend([player, vulture])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert (vulture.x, vulture.y) == (2, 1)  # ordinary single-step chase, same as hostile_basic


# --- mimic (disguised as an item until picked at) ---


def test_mimic_entity_starts_disguised_non_blocking_and_item_priority():
    catalog = load_catalog()
    edef = catalog.entities["mimic_flask"]
    mimic = entity_from_def(edef, 2, 2)

    assert mimic.mimicking is True
    assert mimic.blocks_movement is False
    assert mimic.render_priority == RENDER_PRIORITY_ITEM


def test_non_mimic_entity_is_never_mimicking():
    rat = make_monster(1, 1, ai="hostile_basic")
    assert rat.mimicking is False


def test_mimic_stays_disguised_and_motionless_when_not_picked_at():
    game_map = make_open_map(5, 3)
    player = make_player(1, 1, hp=30, defense=0)
    mimic = make_monster(3, 1, hp=14, attack=4, defense=1, ai="mimic", mimic_bonus=6, blocks_movement=False)
    game_map.entities.extend([player, mimic])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert (mimic.x, mimic.y) == (3, 1)  # didn't move at all
    assert mimic.mimicking is True
    assert mimic.blocks_movement is False
    assert player.fighter.hp == 30


def test_pickup_reveals_and_bites_a_disguised_mimic():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, defense=0)
    mimic = make_monster(1, 1, hp=14, attack=4, defense=1, ai="mimic", mimic_bonus=6, blocks_movement=False)
    game_map.entities.extend([player, mimic])
    engine = Engine(game_map, player, "Test Level")

    PickupAction().perform(engine, player)

    assert mimic.mimicking is False
    assert mimic.blocks_movement is True
    assert player.fighter.hp == 30 - (4 + 6)  # attack + mimic_bonus
    assert any("was a mimic all along" in m for m in engine.message_log.messages)
    assert any("bites" in m for m in engine.message_log.messages)
    assert not any("picked up" in m for m in engine.message_log.messages)


def test_pickup_uses_default_mimic_bonus_when_unset():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, defense=0)
    mimic = make_monster(1, 1, hp=14, attack=4, defense=1, ai="mimic", blocks_movement=False)
    game_map.entities.extend([player, mimic])
    engine = Engine(game_map, player, "Test Level")

    PickupAction().perform(engine, player)

    assert player.fighter.hp == 30 - (4 + 5)  # DEFAULT_MIMIC_BONUS=5


def test_revealed_mimic_does_not_also_attack_the_same_turn_it_was_revealed():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, defense=0)
    mimic = make_monster(1, 1, hp=14, attack=4, defense=1, ai="mimic", mimic_bonus=6, blocks_movement=False)
    game_map.entities.extend([player, mimic])
    engine = Engine(game_map, player, "Test Level")

    PickupAction().perform(engine, player)
    hp_after_reveal = player.fighter.hp
    engine._perform_ai(mimic)  # the same enemy phase's own turn for this entity

    assert player.fighter.hp == hp_after_reveal  # no second hit
    assert mimic.just_revealed is False


def test_revealed_mimic_behaves_like_an_ordinary_monster_on_a_later_turn():
    game_map = make_open_map(5, 3)
    player = make_player(1, 1, hp=30, defense=0)
    mimic = make_monster(1, 1, hp=14, attack=4, defense=1, ai="mimic", mimic_bonus=6, blocks_movement=False)
    game_map.entities.extend([player, mimic])
    engine = Engine(game_map, player, "Test Level")
    PickupAction().perform(engine, player)
    engine._perform_ai(mimic)  # consumes just_revealed, no-ops otherwise

    player.x, player.y = 4, 1  # step away so the next turn has somewhere to chase toward
    engine._perform_ai(mimic)

    assert (mimic.x, mimic.y) == (2, 1)  # ordinary single-step chase, not another reveal


def test_pickup_ignores_a_mimic_on_a_different_tile():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, defense=0)
    mimic = make_monster(2, 2, hp=14, attack=4, defense=1, ai="mimic", mimic_bonus=6, blocks_movement=False)
    game_map.entities.extend([player, mimic])
    engine = Engine(game_map, player, "Test Level")

    PickupAction().perform(engine, player)

    assert mimic.mimicking is True
    assert player.fighter.hp == 30
    assert any("nothing here to pick up" in m for m in engine.message_log.messages)


def test_pickup_still_collects_a_real_item_when_a_mimic_is_elsewhere():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, defense=0)
    potion = make_potion(1, 1)
    mimic = make_monster(2, 2, hp=14, attack=4, defense=1, ai="mimic", mimic_bonus=6, blocks_movement=False)
    game_map.entities.extend([player, potion, mimic])
    engine = Engine(game_map, player, "Test Level")

    PickupAction().perform(engine, player)

    assert potion in player.inventory
    assert mimic.mimicking is True


# --- monster drops (on-death loot) ---


def test_monster_drop_lands_on_the_ground_when_the_roll_succeeds(monkeypatch):
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, defense=0)
    monster = make_monster(
        2, 1, ai="hostile_basic", drop_item_id="healing_potion", drop_chance=0.5,
    )
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level", catalog=catalog)
    monkeypatch.setattr(random, "random", lambda: 0.4)  # below drop_chance - succeeds

    engine.on_entity_death(monster)

    drops = [e for e in game_map.entities if e.entity_id == "healing_potion"]
    assert len(drops) == 1
    assert (drops[0].x, drops[0].y) == (2, 1)  # dropped where the monster died
    assert any("drops a Healing Potion" in m for m in engine.message_log.messages)


def test_monster_drop_does_not_land_when_the_roll_fails(monkeypatch):
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, defense=0)
    monster = make_monster(
        2, 1, ai="hostile_basic", drop_item_id="healing_potion", drop_chance=0.5,
    )
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level", catalog=catalog)
    monkeypatch.setattr(random, "random", lambda: 0.9)  # at/above drop_chance - fails

    engine.on_entity_death(monster)

    assert not any(e.entity_id == "healing_potion" for e in game_map.entities)
    assert not any("drops a" in m for m in engine.message_log.messages)


def test_monster_without_drop_configured_never_drops_anything(monkeypatch):
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, defense=0)
    monster = make_monster(2, 1, ai="hostile_basic")
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level", catalog=catalog)
    monkeypatch.setattr(random, "random", lambda: 0.0)  # would always succeed if configured

    engine.on_entity_death(monster)

    assert not any("drops a" in m for m in engine.message_log.messages)


def test_monster_drop_no_ops_without_a_catalog(monkeypatch):
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, defense=0)
    monster = make_monster(
        2, 1, ai="hostile_basic", drop_item_id="healing_potion", drop_chance=0.5,
    )
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")  # no catalog passed
    monkeypatch.setattr(random, "random", lambda: 0.0)  # would always succeed if there were a catalog

    engine.on_entity_death(monster)

    assert not any("drops a" in m for m in engine.message_log.messages)


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


def test_use_item_action_ignores_wrong_kind_potion_in_inventory():
    """Selection actually filters, not just grabs the first match - the one
    genuinely new UseItemAction behavior vs. the old blind next()."""
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=10)
    player.fighter.hp = 5
    healing = make_potion(1, 1, heal_amount=10)
    player.inventory.append(healing)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")
    player.selected_potion_kind = "teleport"

    engine.process_turn(UseItemAction())

    assert healing in player.inventory  # not consumed
    assert player.fighter.hp == 5  # not healed
    assert engine.message_log.messages[-1] == "You have no teleport potion to use."


def test_use_item_action_drinks_teleport_potion_and_sets_wants_overworld():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    potion = make_teleport_potion(1, 1)
    player.inventory.append(potion)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")  # is_overworld defaults False
    player.selected_potion_kind = "teleport"

    engine.process_turn(UseItemAction())

    assert potion not in player.inventory
    assert engine.wants_overworld is True


def test_use_item_action_teleport_guards_against_already_being_on_overworld():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    potion = make_teleport_potion(1, 1)
    player.inventory.append(potion)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "The Overworld", is_overworld=True)
    player.selected_potion_kind = "teleport"

    engine.process_turn(UseItemAction())

    assert potion in player.inventory  # not consumed
    assert engine.wants_overworld is False
    assert engine.message_log.messages[-1] == "You're already on the surface."


def test_potion_kind_identifies_water_walking():
    assert potion_kind(ItemEffect(water_walking_duration=20)) == "water_walking"
    assert potion_kind(ItemEffect()) is None


def test_use_item_action_drinks_water_walking_potion_and_sets_turns_remaining():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    potion = make_water_walking_potion(1, 1, duration=20)
    player.inventory.append(potion)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")  # is_overworld defaults False
    player.selected_potion_kind = "water_walking"

    engine.process_turn(UseItemAction())

    assert potion not in player.inventory
    # 20 set by the drink, then process_enemy_phase ticks it down once
    # within the same turn - same "set then immediately ticked" shape
    # skill cooldowns already have.
    assert player.water_walking_turns_remaining == 19
    assert engine.message_log.messages[-1] == "You drink the Water Walking Potion and your feet no longer sink."


def test_is_walkable_water_walking_override_accepts_sea_and_deep_water():
    game_map = make_open_map(3, 3)
    game_map.kinds[1, 1] = "deep_water"
    game_map.walkable[1, 1] = False
    game_map.kinds[2, 1] = "sea"
    game_map.walkable[2, 1] = False

    assert game_map.is_walkable(1, 1, water_walking=True) is True
    assert game_map.is_walkable(2, 1, water_walking=True) is True
    assert game_map.is_walkable(1, 1) is False
    assert game_map.is_walkable(2, 1, water_walking=False) is False


def test_movement_action_lets_player_cross_deep_water_with_active_buff():
    game_map = make_open_map(3, 3)
    game_map.kinds[2, 1] = "deep_water"
    game_map.walkable[2, 1] = False
    player = make_player(1, 1)
    player.water_walking_turns_remaining = 5
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")  # is_overworld defaults False

    engine.process_turn(BumpAction(1, 0))

    assert (player.x, player.y) == (2, 1)


def test_movement_action_blocks_deep_water_without_active_buff():
    game_map = make_open_map(3, 3)
    game_map.kinds[2, 1] = "deep_water"
    game_map.walkable[2, 1] = False
    player = make_player(1, 1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(BumpAction(1, 0))

    assert (player.x, player.y) == (1, 1)  # never moved


def test_movement_action_water_walking_inert_on_the_overworld():
    game_map = make_open_map(3, 3)
    game_map.kinds[2, 1] = "deep_water"
    game_map.walkable[2, 1] = False
    player = make_player(1, 1)
    player.water_walking_turns_remaining = 5
    game_map.entities.append(player)
    engine = Engine(game_map, player, "The Overworld", is_overworld=True)

    engine.process_turn(BumpAction(1, 0))

    assert (player.x, player.y) == (1, 1)  # the buff never applies on the overworld


def test_water_walking_turns_remaining_ticks_down_each_turn():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    player.water_walking_turns_remaining = 2
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())
    assert player.water_walking_turns_remaining == 1

    engine.process_turn(WaitAction())
    assert player.water_walking_turns_remaining == 0

    engine.process_turn(WaitAction())
    assert player.water_walking_turns_remaining == 0  # never goes negative


def test_potion_kind_identifies_antidote():
    assert potion_kind(ItemEffect(cures_effects=True)) == "antidote"


def test_use_item_action_antidote_clears_every_active_effect():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    player.fighter.active_effects["poison"] = ActiveEffect(potency=2, turns_remaining=3)
    player.fighter.active_effects["weaken"] = ActiveEffect(potency=1, turns_remaining=2)
    potion = make_antidote_potion(1, 1)
    player.inventory.append(potion)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")
    player.selected_potion_kind = "antidote"

    engine.process_turn(UseItemAction())

    assert potion not in player.inventory
    assert player.fighter.active_effects == {}
    assert engine.message_log.messages[-1] == "You drink the Antidote and the afflictions lift."


def test_use_item_action_antidote_with_nothing_to_cure_still_consumes_it():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    potion = make_antidote_potion(1, 1)
    player.inventory.append(potion)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")
    player.selected_potion_kind = "antidote"

    engine.process_turn(UseItemAction())

    assert potion not in player.inventory
    assert engine.message_log.messages[-1] == "You drink the Antidote, but feel no different."


def test_potion_kind_identifies_vigor():
    assert potion_kind(ItemEffect(grants_buff="vigor", buff_potency=3, buff_duration=10)) == "vigor"


def test_use_item_action_vigor_grants_a_buff_and_boosts_effective_stats():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, attack=5, defense=2)
    base_attack = player.effective_attack
    base_defense = player.effective_defense
    potion = make_vigor_potion(1, 1, potency=3, duration=10)
    player.inventory.append(potion)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")
    player.selected_potion_kind = "vigor"

    engine.process_turn(UseItemAction())

    assert potion not in player.inventory
    # Granted and ticked in the same turn, same "first tick lands
    # immediately" convention as _tick_active_effects (see its own
    # docstring) - buff_duration=10 means 10 total ticks, the first one
    # this same turn, not the turn after.
    assert player.fighter.active_buffs["vigor"] == ActiveEffect(potency=3, turns_remaining=9)
    assert player.effective_attack == base_attack + 3
    assert player.effective_defense == base_defense + 3
    assert engine.message_log.messages[-1] == "You drink the Elixir of Vigor and strength floods your limbs."


def test_vigor_buff_ticks_down_and_expires():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    player.fighter.active_buffs["vigor"] = ActiveEffect(potency=3, turns_remaining=2)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())
    assert player.fighter.active_buffs["vigor"].turns_remaining == 1

    engine.process_turn(WaitAction())
    assert "vigor" not in player.fighter.active_buffs
    assert player.effective_attack == player.fighter.attack


def test_potion_kind_identifies_haste():
    assert potion_kind(ItemEffect(grants_buff="haste", buff_duration=3)) == "haste"


def test_use_item_action_haste_drinking_itself_costs_a_normal_turn():
    """Haste isn't active yet at the moment the drinking action itself
    runs (see Engine._consume_haste_action's own docstring) - so a
    hostile monster still gets its turn on the same turn the potion is
    drunk, and only the actions that follow are free."""
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, defense=0)
    monster = make_monster(2, 1, hp=50, attack=4, ai="hostile_basic")
    potion = make_haste_potion(1, 1, duration=3)
    player.inventory.append(potion)
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")
    player.selected_potion_kind = "haste"

    engine.process_turn(UseItemAction())

    assert potion not in player.inventory
    assert player.fighter.active_buffs["haste"] == ActiveEffect(potency=0, turns_remaining=3)
    assert player.fighter.hp == 30 - 4  # the monster still got a turn this turn
    assert "You drink the Draught of Swiftness and the world around you seems to slow." in engine.message_log.messages


def test_haste_grants_free_actions_that_skip_the_enemy_phase():
    """While haste is active, a hostile monster never gets to act, poison
    never ticks, and water-walking never burns down - the world simply
    doesn't move on a hasted action. Once haste runs out, everything
    resumes normally on the very next action."""
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, defense=0)
    player.fighter.active_buffs["haste"] = ActiveEffect(potency=0, turns_remaining=3)
    player.fighter.active_effects["poison"] = ActiveEffect(potency=2, turns_remaining=99)
    player.water_walking_turns_remaining = 5
    monster = make_monster(2, 1, hp=50, attack=4, ai="hostile_basic")
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())
    assert player.fighter.hp == 30  # monster never got a turn
    assert player.fighter.active_effects["poison"].turns_remaining == 99  # never ticked
    assert player.water_walking_turns_remaining == 5  # never ticked
    assert player.fighter.active_buffs["haste"].turns_remaining == 2

    engine.process_turn(WaitAction())
    assert player.fighter.active_buffs["haste"].turns_remaining == 1

    engine.process_turn(WaitAction())
    assert "haste" not in player.fighter.active_buffs
    assert player.fighter.hp == 30  # still untouched - the 3rd action was the last free one

    engine.process_turn(WaitAction())
    # haste exhausted - the monster's attack (4) and poison's own tick (2)
    # both resume on this, the first normal turn since drinking.
    assert player.fighter.hp == 30 - 4 - 2
    assert player.fighter.active_effects["poison"].turns_remaining == 98  # ticking resumed
    assert player.water_walking_turns_remaining == 4


def test_stunned_player_does_not_consume_a_haste_charge():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    player.fighter.active_buffs["haste"] = ActiveEffect(potency=0, turns_remaining=2)
    player.fighter.active_effects["stun"] = ActiveEffect(potency=0, turns_remaining=1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert player.fighter.active_buffs["haste"].turns_remaining == 2
    assert "stun" not in player.fighter.active_effects


def test_potion_kind_identifies_shadowed():
    assert potion_kind(ItemEffect(grants_buff="shadowed", buff_duration=8)) == "shadowed"


def test_use_item_action_shadowed_grants_the_buff():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    potion = make_shadow_potion(1, 1, duration=8)
    player.inventory.append(potion)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")
    player.selected_potion_kind = "shadowed"

    engine.process_turn(UseItemAction())

    assert potion not in player.inventory
    # Granted and ticked in the same turn, same "first tick lands
    # immediately" convention _tick_active_buffs already establishes.
    assert player.fighter.active_buffs["shadowed"] == ActiveEffect(potency=0, turns_remaining=7)
    assert "You drink the Vial of Shadows and fade into the shadows." in engine.message_log.messages


def test_shadowed_prevents_a_distant_hostile_monster_from_acting():
    game_map = make_open_map(5, 5)
    player = make_player(2, 2, hp=30, defense=0)
    player.fighter.active_buffs["shadowed"] = ActiveEffect(potency=0, turns_remaining=5)
    monster = make_monster(0, 2, hp=50, attack=4, ai="hostile_basic")  # distance 2
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert (monster.x, monster.y) == (0, 2)  # never closed the distance
    assert player.fighter.hp == 30


def test_shadowed_does_not_protect_an_already_adjacent_monster():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, defense=0)
    player.fighter.active_buffs["shadowed"] = ActiveEffect(potency=0, turns_remaining=5)
    monster = make_monster(2, 1, hp=50, attack=4, ai="hostile_basic")  # already adjacent
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert player.fighter.hp == 30 - 4  # still attacked - shadowed can't hide you at melee range


def test_shadowed_buff_ticks_down_and_expiry_restores_detection():
    game_map = make_open_map(5, 5)
    player = make_player(2, 2, hp=30, defense=0)
    player.fighter.active_buffs["shadowed"] = ActiveEffect(potency=0, turns_remaining=2)
    monster = make_monster(0, 2, hp=50, attack=4, ai="hostile_basic")
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())
    assert player.fighter.active_buffs["shadowed"].turns_remaining == 1
    assert (monster.x, monster.y) == (0, 2)

    engine.process_turn(WaitAction())
    assert "shadowed" not in player.fighter.active_buffs
    assert (monster.x, monster.y) == (0, 2)  # still didn't move - shadowed was active going into this turn too

    engine.process_turn(WaitAction())
    assert (monster.x, monster.y) == (1, 2)  # expired for good now - the monster closes in


def test_potion_kind_identifies_second_sight():
    assert potion_kind(ItemEffect(reveals_map=True)) == "second_sight"


def test_use_item_action_second_sight_reveals_the_whole_map_and_lists_creatures():
    # Larger than FOV_RADIUS (8) in every direction from the player's
    # corner, so a far corner becoming explored can only be the potion's
    # own doing, not ordinary FOV update_fov would have done anyway.
    game_map = make_open_map(30, 30)
    player = make_player(1, 1)
    potion = make_second_sight_potion(1, 1)
    player.inventory.append(potion)
    monster_a = make_monster(0, 0, ai="hostile_basic")
    monster_a.name = "Goblin"
    monster_b = make_monster(29, 29, ai="hostile_basic")
    monster_b.name = "Goblin"
    villager = make_villager(29, 0)
    game_map.entities.extend([player, monster_a, monster_b, villager])
    engine = Engine(game_map, player, "Test Level")
    player.selected_potion_kind = "second_sight"

    assert not game_map.explored[29, 29]
    engine.process_turn(UseItemAction())

    assert potion not in player.inventory
    assert game_map.explored[29, 29]  # far corner, well outside FOV_RADIUS
    assert (
        "You drink the Bottled Second Sight and a vision floods your mind: "
        "2 Goblins, 1 Villager." in engine.message_log.messages
    )


def test_use_item_action_second_sight_with_no_creatures_present():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    potion = make_second_sight_potion(1, 1)
    player.inventory.append(potion)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")
    player.selected_potion_kind = "second_sight"

    engine.process_turn(UseItemAction())

    assert potion not in player.inventory
    assert game_map.explored.all()
    assert (
        "You drink the Bottled Second Sight and a vision floods your mind, but nothing stirs here."
        in engine.message_log.messages
    )


def test_use_item_action_second_sight_refuses_on_the_overworld():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    potion = make_second_sight_potion(1, 1)
    player.inventory.append(potion)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "The Overworld", is_overworld=True)
    player.selected_potion_kind = "second_sight"

    engine.process_turn(UseItemAction())

    assert potion in player.inventory  # never consumed
    assert engine.message_log.messages[-1] == "There's too much ground out here for any vision to take in."


def test_potion_kind_identifies_smoke_bomb():
    assert potion_kind(ItemEffect(local_teleport=True, grants_buff="shadowed", buff_duration=3)) == "smoke_bomb"


def test_smoke_bomb_potion_kind_does_not_collide_with_plain_shadowed():
    """A smoke bomb sets grants_buff=shadowed on itself too (see
    ItemDef.local_teleport's own docstring) - potion_kind must still keep
    it distinct from a plain Vial of Shadows so both can occupy separate
    hotbar slots at once."""
    smoke_kind = potion_kind(ItemEffect(local_teleport=True, grants_buff="shadowed", buff_duration=3))
    shadow_kind = potion_kind(ItemEffect(grants_buff="shadowed", buff_duration=8))
    assert smoke_kind == "smoke_bomb"
    assert shadow_kind == "shadowed"


def test_use_item_action_smoke_bomb_relocates_the_player_and_grants_shadowed():
    game_map = make_open_map(11, 11)
    player = make_player(5, 5)
    potion = make_smoke_bomb(5, 5, duration=3)
    player.inventory.append(potion)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")
    player.selected_potion_kind = "smoke_bomb"

    engine.process_turn(UseItemAction())

    assert potion not in player.inventory
    assert (player.x, player.y) != (5, 5)  # moved somewhere
    assert max(abs(player.x - 5), abs(player.y - 5)) <= SMOKE_BOMB_TELEPORT_RADIUS
    # Granted and ticked in the same turn, same "first tick lands
    # immediately" convention every other active_buffs entry follows.
    assert player.fighter.active_buffs["shadowed"] == ActiveEffect(potency=0, turns_remaining=2)
    assert "You crack the Smoke Bomb and vanish in a burst of smoke." in engine.message_log.messages


def test_use_item_action_smoke_bomb_refuses_with_nowhere_to_go():
    game_map = GameMap(1, 1)
    game_map.kinds[0, 0] = "floor"
    game_map.walkable[0, 0] = True
    game_map.transparent[0, 0] = True
    player = make_player(0, 0)
    potion = make_smoke_bomb(0, 0)
    player.inventory.append(potion)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")
    player.selected_potion_kind = "smoke_bomb"

    engine.process_turn(UseItemAction())

    assert potion in player.inventory  # never consumed
    assert (player.x, player.y) == (0, 0)  # never moved
    assert engine.message_log.messages[-1] == "The smoke has nowhere to carry you."


def test_potion_kind_identifies_clarity():
    assert potion_kind(ItemEffect(resets_skill_cooldowns=True)) == "clarity"


def test_use_item_action_clarity_clears_every_skill_cooldown():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    player.skill_cooldowns["blink_strike"] = 4
    player.skill_cooldowns["war_horn"] = 2
    potion = make_clarity_potion(1, 1)
    player.inventory.append(potion)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")
    player.selected_potion_kind = "clarity"

    engine.process_turn(UseItemAction())

    assert potion not in player.inventory
    assert player.skill_cooldowns == {}
    assert (
        "You drink the Bezoar of Clarity and your mind sharpens - every skill feels ready again."
        in engine.message_log.messages
    )


def test_use_item_action_clarity_with_nothing_on_cooldown_still_consumes_it():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    potion = make_clarity_potion(1, 1)
    player.inventory.append(potion)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")
    player.selected_potion_kind = "clarity"

    engine.process_turn(UseItemAction())

    assert potion not in player.inventory
    assert engine.message_log.messages[-1] == "You drink the Bezoar of Clarity, but feel no different."


def test_assign_potion_slot_sets_a_valid_kind():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")

    message = engine.assign_potion_slot(2, "healing")

    assert player.potion_slots[2] == "healing"
    assert "Potion slot 3: healing." == message
    assert engine.message_log.messages[-1] == message


def test_assign_potion_slot_clears_with_none():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")

    engine.assign_potion_slot(0, None)

    assert player.potion_slots[0] is None


def test_assign_potion_slot_moves_a_duplicate_instead_of_allowing_two():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")
    assert player.potion_slots == ["healing", "teleport", None]

    engine.assign_potion_slot(2, "healing")

    assert player.potion_slots == [None, "teleport", "healing"]


def test_assign_potion_slot_rejects_an_unknown_kind():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")

    message = engine.assign_potion_slot(0, "not_a_real_kind")

    assert message == "That's not a potion kind."
    assert player.potion_slots[0] == "healing"  # unchanged


def test_assign_potion_slot_rejects_an_out_of_range_index():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")

    message = engine.assign_potion_slot(99, "healing")

    assert message == "Invalid potion slot."


def test_assign_skill_slot_sets_a_learned_skill_perk():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level", catalog=catalog)
    player.learned_perk_ids.add("second_wind")

    message = engine.assign_skill_slot(1, "second_wind")

    assert player.skill_slots[1] == "second_wind"
    assert message == "Skill slot 2: Second Wind."


def test_assign_skill_slot_rejects_an_unlearned_perk():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level", catalog=catalog)

    message = engine.assign_skill_slot(0, "second_wind")

    assert message == "That's not a skill you've learned."
    assert player.skill_slots[0] is None


def test_assign_skill_slot_rejects_a_non_skill_perk():
    """toughness_1 is a flat stat perk (no skill_effect) - even if learned,
    it can never occupy a skill hotbar slot."""
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level", catalog=catalog)
    player.learned_perk_ids.add("toughness_1")

    message = engine.assign_skill_slot(0, "toughness_1")

    assert message == "That's not a skill you've learned."
    assert player.skill_slots[0] is None


def test_assign_skill_slot_moves_a_duplicate_instead_of_allowing_two():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level", catalog=catalog)
    player.learned_perk_ids.add("second_wind")
    engine.assign_skill_slot(0, "second_wind")

    engine.assign_skill_slot(3, "second_wind")

    assert player.skill_slots == [None, None, None, "second_wind"]


def test_learn_perk_auto_assigns_a_new_skill_to_the_first_empty_slot():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    player.xp = 1000
    player.gold = 1000
    game_map.entities.append(player)
    catalog = load_catalog()
    trainer = make_monster(2, 1, ai="villager", entity_id="trainer")
    trainer.trainer_perks = ["second_wind"]
    game_map.entities.append(trainer)
    engine = Engine(game_map, player, "Test Level", catalog=catalog)

    engine.learn_perk("second_wind")

    assert player.skill_slots[0] == "second_wind"


def test_learn_perk_does_not_reassign_an_already_slotted_skill():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    player.xp = 1000
    player.gold = 1000
    game_map.entities.append(player)
    catalog = load_catalog()
    trainer = make_monster(2, 1, ai="villager", entity_id="trainer")
    trainer.trainer_perks = ["second_wind", "ground_pound"]
    game_map.entities.append(trainer)
    engine = Engine(game_map, player, "Test Level", catalog=catalog)
    engine.learn_perk("second_wind")
    engine.assign_skill_slot(2, "second_wind")  # player moved it manually

    engine.learn_perk("ground_pound")

    # second_wind stays put in slot 2; ground_pound takes the first empty
    # slot (0), not slot 2's neighbor - learn_perk never touches an
    # already-assigned skill.
    assert player.skill_slots == ["ground_pound", None, "second_wind", None]


def test_use_skill_slot_action_triggers_the_bound_perk():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=20)
    player.fighter.hp = 10
    game_map.entities.append(player)
    catalog = load_catalog()
    engine = Engine(game_map, player, "Test Level", catalog=catalog)
    player.learned_perk_ids.add("second_wind")
    player.skill_slots[0] = "second_wind"

    engine.process_turn(UseSkillSlotAction(0))

    assert player.fighter.hp > 10  # second_wind healed the player


def test_use_skill_slot_action_on_an_empty_slot_logs_and_costs_a_turn():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(UseSkillSlotAction(0))

    assert engine.message_log.messages[-1] == "No skill bound to that slot."


def test_use_potion_slot_action_drinks_the_bound_kind():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30)
    player.fighter.hp = 10
    potion = make_potion(1, 1, heal_amount=10)
    player.inventory.append(potion)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")
    player.potion_slots[0] = "healing"

    engine.process_turn(UsePotionSlotAction(0))

    assert player.fighter.hp == 20
    assert potion not in player.inventory
    assert player.selected_potion_kind == "healing"


def test_use_potion_slot_action_on_an_empty_slot_logs_and_costs_a_turn():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")
    player.potion_slots[2] = None

    engine.process_turn(UsePotionSlotAction(2))

    assert engine.message_log.messages[-1] == "Nothing bound to that slot."


def test_restart_resets_selected_potion_kind():
    """restart() allocates a brand-new player Entity via build_game_map, so
    the selection resets to the default for free - no explicit reset line
    needed in Engine.restart()."""
    catalog = load_catalog()
    levels = load_levels(PRISON_TOWER_LEVELS_DIR, catalog)
    level_01 = levels["level_01"]
    game_map, player = build_game_map(level_01, catalog)
    engine = Engine(
        game_map, player, level_01.name,
        catalog=catalog, levels=levels, starting_level=level_01,
    )
    player.selected_potion_kind = "teleport"

    engine.restart()

    assert engine.player.selected_potion_kind == "healing"


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


def test_trinket_pickup_equips_when_nothing_equipped_yet():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    trinket = make_trinket(1, 1, trinket_effect="crit_chance", trinket_bonus=0.1, name="Lucky Charm")
    game_map.entities.extend([player, trinket])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(PickupAction())

    assert player.equipped_trinket is trinket
    assert trinket not in game_map.entities


def test_trinket_pickup_swaps_when_same_kind_and_better():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    player.equipped_trinket = make_trinket(0, 0, trinket_effect="crit_chance", trinket_bonus=0.1, name="Lucky Charm")
    better = make_trinket(1, 1, trinket_effect="crit_chance", trinket_bonus=0.2, name="Rabbit's Foot")
    game_map.entities.extend([player, better])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(PickupAction())

    assert player.equipped_trinket is better
    dropped = [e for e in game_map.entities if e.name == "Lucky Charm"]
    assert len(dropped) == 1
    assert (dropped[0].x, dropped[0].y) == (1, 1)  # dropped at the player's feet


def test_trinket_pickup_is_left_on_the_ground_when_same_kind_but_not_better():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    current = make_trinket(0, 0, trinket_effect="crit_chance", trinket_bonus=0.2, name="Rabbit's Foot")
    player.equipped_trinket = current
    worse = make_trinket(1, 1, trinket_effect="crit_chance", trinket_bonus=0.1, name="Lucky Charm")
    game_map.entities.extend([player, worse])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(PickupAction())

    assert player.equipped_trinket is current  # unchanged
    assert worse in game_map.entities  # left untouched on the ground


def test_trinket_pickup_of_a_different_kind_is_left_on_the_ground():
    """A crit-chance trinket and a dodge-chance trinket aren't comparable
    by a single number - a different kind is never auto-swapped in, even
    if its own bonus value is numerically larger."""
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    current = make_trinket(0, 0, trinket_effect="crit_chance", trinket_bonus=0.1, name="Lucky Charm")
    player.equipped_trinket = current
    different_kind = make_trinket(1, 1, trinket_effect="dodge_chance", trinket_bonus=0.5, name="Shadow Cloak Pin")
    game_map.entities.extend([player, different_kind])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(PickupAction())

    assert player.equipped_trinket is current  # unchanged
    assert different_kind in game_map.entities  # left untouched on the ground


def test_trinket_does_not_affect_effective_attack_or_defense():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, attack=5, defense=1)
    player.equipped_trinket = make_trinket(0, 0, trinket_effect="crit_chance", trinket_bonus=0.5)

    assert player.effective_attack == 5
    assert player.effective_defense == 1


def test_trinket_crit_chance_bonus_triggers_a_crit_the_base_rate_would_have_missed(monkeypatch):
    monkeypatch.setattr(engine.combat, "COMBAT_VARIANCE_ENABLED", True)
    import math

    # Dodge roll first (must not beat DODGE_CHANCE=0.10), then crit roll:
    # 0.3 is above the base CRIT_CHANCE=0.10 but below the trinket-boosted
    # 0.60 - a crit here can only be the trinket's doing.
    monkeypatch.setattr(random, "random", iter([0.99, 0.3]).__next__)
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, attack=5, defense=1)
    player.equipped_trinket = make_trinket(0, 0, trinket_effect="crit_chance", trinket_bonus=0.5)
    monster = make_monster(2, 1, hp=20, attack=0, defense=0, ai=None)
    game_map.entities.extend([player, monster])
    engine_ = Engine(game_map, player, "Test Level")

    engine_.process_turn(BumpAction(1, 0))

    base_damage = player.effective_attack - monster.effective_defense
    expected_crit_damage = math.ceil(base_damage * engine.combat.CRIT_MULTIPLIER)
    assert 20 - monster.fighter.hp == expected_crit_damage


def test_trinket_dodge_chance_bonus_triggers_a_dodge_the_base_rate_would_have_missed(monkeypatch):
    monkeypatch.setattr(engine.combat, "COMBAT_VARIANCE_ENABLED", True)
    # 0.3 is above the base DODGE_CHANCE=0.10 but below the trinket-boosted
    # 0.60 - a dodge here can only be the trinket's doing.
    monkeypatch.setattr(random, "random", lambda: 0.3)
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, defense=0)
    player.equipped_trinket = make_trinket(0, 0, trinket_effect="dodge_chance", trinket_bonus=0.5)
    monster = make_monster(2, 1, hp=5, attack=10, ai=None)
    game_map.entities.extend([player, monster])
    engine_ = Engine(game_map, player, "Test Level")

    from engine.combat import resolve_attack
    resolve_attack(engine_, attacker=monster, defender=player)

    assert player.fighter.hp == 30  # fully dodged
    assert "dodges" in engine_.message_log.messages[-1]


def test_trinket_dodge_chance_bonus_is_ignored_for_a_wrong_kind_trinket(monkeypatch):
    monkeypatch.setattr(engine.combat, "COMBAT_VARIANCE_ENABLED", True)
    # 0.3 would dodge if the (mismatched) crit_chance trinket somehow
    # boosted dodge too - it must not, so this hit lands normally.
    monkeypatch.setattr(random, "random", iter([0.3, 0.99]).__next__)
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, defense=0)
    player.equipped_trinket = make_trinket(0, 0, trinket_effect="crit_chance", trinket_bonus=0.5)
    monster = make_monster(2, 1, hp=5, attack=10, ai=None)
    game_map.entities.extend([player, monster])
    engine_ = Engine(game_map, player, "Test Level")

    from engine.combat import resolve_attack
    resolve_attack(engine_, attacker=monster, defender=player)

    assert player.fighter.hp == 30 - 10  # not dodged - wrong trinket kind


def test_xp_gain_trinket_boosts_a_kill_reward(monkeypatch):
    monkeypatch.setattr(engine.combat, "COMBAT_VARIANCE_ENABLED", True)
    monkeypatch.setattr(random, "random", lambda: 0.99)  # no dodge, no crit
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, attack=99, defense=0)
    player.equipped_trinket = make_trinket(0, 0, trinket_effect="xp_gain", trinket_bonus=0.5)
    monster = make_monster(2, 1, hp=1, attack=0, defense=0, ai=None)
    monster.xp_reward = 10
    game_map.entities.extend([player, monster])
    engine_ = Engine(game_map, player, "Test Level")

    engine_.process_turn(BumpAction(1, 0))

    assert player.xp == 15  # ceil(10 * 1.5)
    assert any("You gain 15 XP" in m for m in engine_.message_log.messages)


def test_xp_gain_trinket_has_no_effect_without_one_equipped():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, attack=99, defense=0)
    monster = make_monster(2, 1, hp=1, attack=0, defense=0, ai=None)
    monster.xp_reward = 10
    game_map.entities.extend([player, monster])
    engine_ = Engine(game_map, player, "Test Level")

    engine_.process_turn(BumpAction(1, 0))

    assert player.xp == 10


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


# --- weapon/armor affixes (secondary status-effect procs) ---


def test_weapon_affix_inflicts_its_effect_on_a_successful_proc(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.1)  # below affix_chance=0.3 - procs
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, attack=5, defense=1)
    player.equipped_weapon = make_weapon(
        0, 0, attack_bonus=0, affix_effect="poison", affix_potency=1, affix_duration=3, affix_chance=0.3,
    )
    monster = make_monster(2, 1, hp=20, attack=0, defense=0, ai=None)
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(BumpAction(1, 0))

    assert monster.fighter.active_effects["poison"].potency == 1
    assert monster.fighter.active_effects["poison"].turns_remaining == 2  # duration 3, minus this turn's tick
    assert any("poisoned" in m for m in engine.message_log.messages)


def test_weapon_affix_does_not_inflict_on_a_failed_proc(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.9)  # above affix_chance=0.3 - fails
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, attack=5, defense=1)
    player.equipped_weapon = make_weapon(
        0, 0, attack_bonus=0, affix_effect="poison", affix_potency=1, affix_duration=3, affix_chance=0.3,
    )
    monster = make_monster(2, 1, hp=20, attack=0, defense=0, ai=None)
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(BumpAction(1, 0))

    assert "poison" not in monster.fighter.active_effects


def test_weapon_without_an_affix_never_procs_anything(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.0)  # would always proc if there were an affix
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, attack=5, defense=1)
    player.equipped_weapon = make_weapon(0, 0, attack_bonus=2)  # no affix
    monster = make_monster(2, 1, hp=20, attack=0, defense=0, ai=None)
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(BumpAction(1, 0))

    assert monster.fighter.active_effects == {}


def test_armor_affix_retaliates_against_the_attacker_on_a_successful_proc(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.1)  # below affix_chance=0.3 - procs
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, attack=0, defense=0)
    player.equipped_armor = make_armor(
        0, 0, defense_bonus=0, affix_effect="weaken", affix_potency=2, affix_duration=2, affix_chance=0.3,
    )
    monster = make_monster(2, 1, hp=20, attack=5, defense=0, ai=None)
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    from engine.combat import resolve_attack
    resolve_attack(engine, attacker=monster, defender=player)

    assert monster.fighter.active_effects["weaken"].potency == 2
    assert any("weakened" in m for m in engine.message_log.messages)


def test_armor_affix_does_not_retaliate_on_a_failed_proc(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.9)  # above affix_chance=0.3 - fails
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, attack=0, defense=0)
    player.equipped_armor = make_armor(
        0, 0, defense_bonus=0, affix_effect="weaken", affix_potency=2, affix_duration=2, affix_chance=0.3,
    )
    monster = make_monster(2, 1, hp=20, attack=5, defense=0, ai=None)
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    from engine.combat import resolve_attack
    resolve_attack(engine, attacker=monster, defender=player)

    assert "weaken" not in monster.fighter.active_effects


def test_weapon_and_armor_affixes_apply_independently_to_different_sides(monkeypatch):
    """Both procs can fire off the same hit: the attacker's weapon affix
    hits the defender, the defender's armor affix retaliates onto the
    attacker - two different entities, two different effect kinds, no
    interference between them."""
    monkeypatch.setattr(random, "random", lambda: 0.1)  # below both affix_chance values
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, attack=5, defense=1)
    player.equipped_weapon = make_weapon(
        0, 0, attack_bonus=0, affix_effect="poison", affix_potency=1, affix_duration=3, affix_chance=0.3,
    )
    monster = make_monster(2, 1, hp=20, attack=0, defense=0, ai=None)
    monster.equipped_armor = make_armor(
        0, 0, defense_bonus=0, affix_effect="weaken", affix_potency=2, affix_duration=2, affix_chance=0.3,
    )
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(BumpAction(1, 0))

    assert "poison" in monster.fighter.active_effects  # weapon affix hit the monster
    assert "weaken" in player.fighter.active_effects  # armor affix retaliated onto the player


def test_combat_variance_disabled_by_default_in_tests():
    """The conftest.py autouse fixture must actually be doing its job -
    if this ever fails, every other deterministic combat test in this
    suite is silently at risk of flaking."""
    assert engine.combat.COMBAT_VARIANCE_ENABLED is False


def test_crit_deals_more_than_the_base_hit(monkeypatch):
    import math

    monkeypatch.setattr(engine.combat, "COMBAT_VARIANCE_ENABLED", True)
    # Two random.random() calls per hit: dodge roll first (must NOT beat
    # DODGE_CHANCE, or the hit never lands at all), crit roll second (must
    # beat CRIT_CHANCE).
    monkeypatch.setattr(random, "random", iter([0.99, 0.0]).__next__)
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, attack=5, defense=1)
    monster = make_monster(2, 1, hp=20, attack=0, defense=0, ai=None)
    game_map.entities.extend([player, monster])
    engine_ = Engine(game_map, player, "Test Level")

    engine_.process_turn(BumpAction(1, 0))

    base_damage = player.effective_attack - monster.effective_defense  # 5 - 0 = 5
    expected_crit_damage = math.ceil(base_damage * engine.combat.CRIT_MULTIPLIER)
    damage_dealt = 20 - monster.fighter.hp
    assert damage_dealt == expected_crit_damage
    assert damage_dealt > base_damage
    assert any(f"for {expected_crit_damage} damage." in m for m in engine_.message_log.messages)
    assert "Critical hit!" in engine_.message_log.messages


def test_dodge_prevents_all_damage_and_any_on_hit_effect(monkeypatch):
    monkeypatch.setattr(engine.combat, "COMBAT_VARIANCE_ENABLED", True)
    monkeypatch.setattr(random, "random", lambda: 0.0)  # always beats DODGE_CHANCE
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, defense=0)
    monster = make_monster(
        2, 1, hp=5, attack=10, ai=None, poison_potency=2, poison_duration=3,
    )
    game_map.entities.extend([player, monster])
    engine_ = Engine(game_map, player, "Test Level")

    from engine.combat import resolve_attack
    resolve_attack(engine_, attacker=monster, defender=player)

    assert player.fighter.hp == 30  # fully dodged, not even a 0-damage hit
    assert "poison" not in player.fighter.active_effects  # no on-hit effect from a non-connecting attack
    assert "dodges" in engine_.message_log.messages[-1]


def test_crit_and_dodge_never_fire_when_variance_is_disabled(monkeypatch):
    """COMBAT_VARIANCE_ENABLED = False (the default, see conftest.py) must
    fully restore the original deterministic formula - a one-line revert,
    not a partial one - regardless of what random.random() would return."""
    monkeypatch.setattr(random, "random", lambda: 0.0)  # would always crit/dodge if variance were on
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, attack=5, defense=1)
    monster = make_monster(2, 1, hp=20, attack=0, defense=0, ai=None)
    game_map.entities.extend([player, monster])
    engine_ = Engine(game_map, player, "Test Level")

    engine_.process_turn(BumpAction(1, 0))

    assert monster.fighter.hp == 20 - 5  # plain 5 attack - 0 defense, no crit
    assert "Critical hit!" not in engine_.message_log.messages


def test_dodge_roll_only_checked_when_variance_enabled(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.0)  # would always dodge if variance were on
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, attack=5, defense=1)
    monster = make_monster(2, 1, hp=20, attack=0, defense=0, ai=None)
    game_map.entities.extend([player, monster])
    engine_ = Engine(game_map, player, "Test Level")

    engine_.process_turn(BumpAction(1, 0))

    assert monster.fighter.hp == 20 - 5  # landed normally, not dodged


def test_poisonous_attacker_afflicts_poison_on_a_landed_hit():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, defense=0)
    monster = make_monster(2, 1, hp=5, attack=4, ai="hostile_basic", poison_potency=2, poison_duration=3)
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert player.fighter.hp == 30 - 4 - 2  # direct hit, then poison's own first tick
    assert player.fighter.active_effects["poison"].potency == 2
    assert player.fighter.active_effects["poison"].turns_remaining == 2  # duration 3, minus this turn's own tick


def test_poison_does_not_apply_when_the_hit_is_fully_absorbed_by_defense():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, defense=2)
    monster = make_monster(2, 1, hp=5, attack=2, ai="hostile_basic", poison_potency=2, poison_duration=3)
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert player.fighter.hp == 30  # attack 2 - defense 2 = 0 damage
    assert "poison" not in player.fighter.active_effects


def test_poison_ticks_the_same_turn_it_is_inflicted():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, defense=0)
    monster = make_monster(2, 1, hp=5, attack=4, ai="hostile_basic", poison_potency=2, poison_duration=3)
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    # -4 direct damage, then poison's own first tick (-2) lands the SAME
    # turn as the bite - duration=3 means 3 total ticks starting now, not
    # starting next turn (see Engine._tick_active_effects's docstring).
    assert player.fighter.hp == 30 - 4 - 2
    assert player.fighter.active_effects["poison"].turns_remaining == 2


def test_poison_expires_after_its_full_duration():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, defense=0)
    monster = make_monster(2, 1, hp=5, attack=4, ai="hostile_basic", poison_potency=2, poison_duration=3)
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())  # bite + poison's first tick
    game_map.entities.remove(monster)  # isolate poison's own remaining decay from a second bite

    engine.process_turn(WaitAction())  # second tick
    engine.process_turn(WaitAction())  # third and final tick
    assert "poison" not in player.fighter.active_effects

    hp_after_poison_expires = player.fighter.hp
    engine.process_turn(WaitAction())
    assert player.fighter.hp == hp_after_poison_expires  # no more ticks


def test_a_new_poisoning_hit_refreshes_rather_than_stacks():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, defense=0)
    monster = make_monster(2, 1, hp=20, attack=1, ai="hostile_basic", poison_potency=3, poison_duration=5)
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())
    assert player.fighter.active_effects["poison"].potency == 3
    assert player.fighter.active_effects["poison"].turns_remaining == 4  # duration 5, minus this turn's own tick

    monster.inflicts_potency = 1
    monster.inflicts_duration = 2
    engine.process_turn(WaitAction())

    # Overwritten, not stacked: potency is the NEW bite's potency (1, not
    # 3+1=4 or max(3,1)=3), and turns_remaining is the NEW bite's own
    # duration minus this turn's own tick (2-1=1, not summed with what was
    # left of the old affliction).
    assert player.fighter.active_effects["poison"].potency == 1
    assert player.fighter.active_effects["poison"].turns_remaining == 1


def test_poison_kills_a_poisoned_monster_via_on_entity_death():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, defense=0)
    monster = make_monster(2, 2, hp=3, attack=0, ai=None)
    monster.xp_reward = 5
    # Nothing in-game poisons a monster today (only cave_spider inflicts
    # poison, and only the player is ever its defender) - set the live
    # affliction directly to exercise _tick_active_effects' monster path.
    monster.fighter.active_effects["poison"] = ActiveEffect(potency=3, turns_remaining=1)
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert monster not in game_map.entities
    assert player.xp == 5  # awarded exactly once - guards on_entity_death against a double-fire


def test_poison_kills_the_player_and_sets_dead_game_state():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, defense=0)
    player.fighter.active_effects["poison"] = ActiveEffect(potency=30, turns_remaining=1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert engine.game_state == "dead"
    assert player.fighter.hp <= 0


# --- weaken (temporary attack reduction) ---


def test_weaken_reduces_effective_attack_and_ranged_attack_while_active():
    player = make_player(1, 1, attack=5)
    player.fighter.active_effects["weaken"] = ActiveEffect(potency=2, turns_remaining=3)

    assert player.effective_attack == 3
    assert player.effective_ranged_attack == 3


def test_weaken_never_drives_effective_attack_negative():
    player = make_player(1, 1, attack=1)
    player.fighter.active_effects["weaken"] = ActiveEffect(potency=5, turns_remaining=3)

    assert player.effective_attack == 0


def test_weaken_does_not_affect_effective_defense():
    player = make_player(1, 1, defense=3)
    player.fighter.active_effects["weaken"] = ActiveEffect(potency=2, turns_remaining=3)

    assert player.effective_defense == 3


def test_weakening_attacker_afflicts_weaken_on_a_landed_hit():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, defense=0, attack=5)
    monster = make_monster(
        2, 1, hp=5, attack=4, ai="hostile_basic",
        inflicts_effect="weaken", inflicts_potency=2, inflicts_duration=3,
    )
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert player.fighter.active_effects["weaken"].potency == 2
    assert player.fighter.active_effects["weaken"].turns_remaining == 2  # duration 3, minus this turn's own tick
    assert player.effective_attack == 3  # 5 base - 2 weaken
    assert "Player is weakened!" in engine.message_log.messages


def test_weaken_expires_after_its_full_duration_and_restores_effective_attack():
    player = make_player(1, 1, attack=5)
    player.fighter.active_effects["weaken"] = ActiveEffect(potency=2, turns_remaining=1)
    game_map = make_open_map(3, 3)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert "weaken" not in player.fighter.active_effects
    assert player.effective_attack == 5


# --- stun (skips a turn) ---


def test_stunned_player_skips_their_action_but_the_world_still_moves():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, defense=0)
    player.fighter.active_effects["stun"] = ActiveEffect(potency=0, turns_remaining=1)
    monster = make_monster(2, 1, hp=20, attack=3, ai="hostile_basic")
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(BumpAction(1, 0))  # would attack the monster if not stunned

    assert monster.fighter.hp == 20  # the attack never happened
    assert player.fighter.hp == 30 - 3  # but the monster still got its own turn
    assert "You are stunned and can't act!" in engine.message_log.messages


def test_stunned_monster_skips_its_turn():
    game_map = make_open_map(5, 3)
    player = make_player(0, 1, hp=30)
    monster = make_monster(2, 1, hp=10, attack=5, ai="hostile_basic")
    monster.fighter.active_effects["stun"] = ActiveEffect(potency=0, turns_remaining=1)
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert (monster.x, monster.y) == (2, 1)  # never chased
    assert player.fighter.hp == 30  # never attacked
    assert "Rat is stunned and can't act." in engine.message_log.messages


def test_stun_expires_after_its_duration():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30)
    player.fighter.active_effects["stun"] = ActiveEffect(potency=0, turns_remaining=1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())
    assert "stun" not in player.fighter.active_effects

    # No longer stunned - a real action now goes through.
    monster = make_monster(2, 1, hp=5, attack=0, defense=0, ai=None)
    game_map.entities.append(monster)
    engine.process_turn(BumpAction(1, 0))
    assert monster.fighter.hp < 5


def test_stunning_attacker_afflicts_stun_on_a_landed_hit():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, defense=0)
    monster = make_monster(
        2, 1, hp=5, attack=4, ai="hostile_basic",
        inflicts_effect="stun", inflicts_duration=1,
    )
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert "stun" in player.fighter.active_effects
    assert "Player is stunned!" in engine.message_log.messages


# --- multiple simultaneous effects ---


def test_poisoned_and_weakened_effects_tick_independently_on_the_same_entity():
    player = make_player(1, 1, hp=30, attack=5)
    player.fighter.active_effects["poison"] = ActiveEffect(potency=2, turns_remaining=2)
    player.fighter.active_effects["weaken"] = ActiveEffect(potency=1, turns_remaining=1)
    game_map = make_open_map(3, 3)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert player.fighter.hp == 30 - 2  # poison ticked
    assert player.fighter.active_effects["poison"].turns_remaining == 1  # still active
    assert "weaken" not in player.fighter.active_effects  # expired on its own, independently
    assert player.effective_attack == 5  # weaken's penalty is gone with it


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


def test_stepping_off_an_open_boundary_map_edge_signals_wants_overworld():
    game_map = make_open_map(3, 3)
    game_map.open_boundary = True
    game_map.open_boundary_message = "You break off into the trees."
    player = make_player(0, 1)  # already on the west edge
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(BumpAction(-1, 0))  # step further west, off the grid

    assert engine.wants_overworld is True
    assert engine.game_state == "playing"
    assert engine.message_log.messages[-1] == "You break off into the trees."
    assert (player.x, player.y) == (0, 1)  # left in place, not moved out of bounds


def test_stepping_off_an_open_boundary_map_edge_with_no_custom_message_uses_the_default():
    game_map = make_open_map(3, 3)
    game_map.open_boundary = True
    player = make_player(0, 1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(BumpAction(-1, 0))

    assert engine.wants_overworld is True
    assert engine.message_log.messages[-1] == "You walk past the edge of the map, back onto open ground."


def test_stepping_off_a_non_open_boundary_map_edge_is_silently_blocked():
    game_map = make_open_map(3, 3)  # open_boundary left at its default (False)
    player = make_player(0, 1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(BumpAction(-1, 0))

    assert engine.wants_overworld is False
    assert (player.x, player.y) == (0, 1)


def test_monster_stepping_off_an_open_boundary_map_edge_is_blocked_and_never_transitions():
    game_map = make_open_map(3, 3)
    game_map.open_boundary = True
    player = make_player(1, 1)
    monster = make_monster(0, 1, hp=10, ai=None)  # already on the west edge
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    BumpAction(-1, 0).perform(engine, monster)

    assert engine.wants_overworld is False
    assert (monster.x, monster.y) == (0, 1)


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


def test_on_player_reach_stairs_resets_the_message_log():
    """Regression test: moving between levels of the same dungeon must not
    keep surfacing messages logged on a different level - the same "old
    dialogue lines resurfacing" bug arrive_player fixes, but for intra-
    dungeon stairs instead of a dungeon/overworld round trip."""
    catalog = load_catalog()
    levels = load_levels(PRISON_TOWER_LEVELS_DIR, catalog)
    level_01 = levels["level_01"]
    game_map, player = build_game_map(level_01, catalog)
    engine = Engine(
        game_map, player, level_01.name,
        catalog=catalog, levels=levels, starting_level=level_01,
    )
    engine.message_log.add("Something from level_01.")

    engine.on_player_reach_stairs("level_02")

    assert "Something from level_01." not in engine.message_log.messages
    assert engine.message_log.messages == ["You descend into The Guard Barracks."]


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
    assert monster_names == ["Giant Rat", "Goblin", "Rat", "Rat"]  # killed monster is back


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
    assert engine.message_log.messages[-1] == "You have no healing potion to use."


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
        FIXTURES_DIR / "overworld_valid", catalog, known_dungeon_ids={"prison_tower"}
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
        FIXTURES_DIR / "overworld_valid", catalog, known_dungeon_ids={"prison_tower"}
    )
    game_map, _player = build_game_map(level, catalog)

    assert game_map.dungeon_entrances == {(3, 1): "prison_tower"}


def test_build_game_map_populates_tile_descriptions():
    catalog = load_catalog()
    level = load_overworld(
        FIXTURES_DIR / "overworld_valid", catalog, known_dungeon_ids={"prison_tower"}
    )
    game_map, _player = build_game_map(level, catalog)

    assert game_map.tile_descriptions == {(3, 1): "A black stone tower."}


def test_build_game_map_populates_entity_and_item_spawn_index(tmp_path):
    """GameMap.entity_spawn_index/item_spawn_index (see engine/save.py) map
    each ParsedLevel.entity_spawns/item_spawns list index to the exact
    Entity build_game_map produced for it, in the same order - the stable
    identity a save file reconciles against."""
    level_path = tmp_path / "indexed.lvl"
    level_path.write_text(
        "id: indexed\n"
        "name: Test Level\n"
        "map: |\n"
        "  #####\n"
        "  #@..#\n"
        "  #v.g#\n"
        "  #.!>#\n"
        "  #####\n"
        "legend:\n"
        '  "#": wall\n'
        '  ".": floor\n'
        '  "@": player_start\n'
        '  ">": stairs_down\n'
        '  "v": { entity: villager, dialogue: "First spawn." }\n'
        '  "g": { entity: goblin }\n'
        '  "!": { item: healing_potion }\n',
        encoding="utf-8",
    )
    catalog = load_catalog()
    level = load_level(level_path, catalog)
    game_map, _player = build_game_map(level, catalog)

    assert set(game_map.entity_spawn_index) == {0, 1}
    villager = game_map.entity_spawn_index[0]
    goblin = game_map.entity_spawn_index[1]
    assert villager.name == "Villager"
    assert villager.dialogue == "First spawn."
    assert goblin.name == "Goblin"
    assert (villager.x, villager.y) == (1, 2)
    assert (goblin.x, goblin.y) == (3, 2)

    assert set(game_map.item_spawn_index) == {0}
    potion = game_map.item_spawn_index[0]
    assert potion.name == "Healing Potion"
    assert (potion.x, potion.y) == (2, 3)

    # every indexed entity is a real member of game_map.entities, not a copy
    assert villager in game_map.entities
    assert goblin in game_map.entities


def test_build_game_map_elite_spawn_boosts_stats_name_color_and_drop(tmp_path):
    level_path = tmp_path / "elite.lvl"
    level_path.write_text(
        "id: elite\n"
        "name: Test Level\n"
        "map: |\n"
        "  #####\n"
        "  #@..#\n"
        "  #.g.#\n"
        "  #..>#\n"
        "  #####\n"
        "legend:\n"
        '  "#": wall\n'
        '  ".": floor\n'
        '  "@": player_start\n'
        '  ">": stairs_down\n'
        '  "g": { entity: goblin, elite: true }\n',
        encoding="utf-8",
    )
    catalog = load_catalog()
    base = catalog.entities["goblin"]
    level = load_level(level_path, catalog)
    game_map, _player = build_game_map(level, catalog)

    elite = game_map.entity_spawn_index[0]

    assert elite.name == "Elite Goblin"
    assert elite.fighter.max_hp == 24  # base 12, ELITE_STAT_MULTIPLIER=2.0
    assert elite.fighter.hp == 24  # spawns at full (boosted) hp
    assert elite.fighter.attack == 8  # base 4, doubled
    assert elite.fighter.defense == base.defense + 1  # flat ELITE_DEFENSE_BONUS
    assert elite.xp_reward == base.xp_reward * 2
    assert elite.drop_chance == 1.0  # base goblin's 0.25 becomes guaranteed
    assert elite.drop_item_id == base.drop_item_id
    assert elite.color != base.color  # visually distinct from an ordinary goblin


def test_build_game_map_non_elite_spawn_is_unaffected(tmp_path):
    level_path = tmp_path / "not_elite.lvl"
    level_path.write_text(
        "id: not_elite\n"
        "name: Test Level\n"
        "map: |\n"
        "  #####\n"
        "  #@..#\n"
        "  #.g.#\n"
        "  #..>#\n"
        "  #####\n"
        "legend:\n"
        '  "#": wall\n'
        '  ".": floor\n'
        '  "@": player_start\n'
        '  ">": stairs_down\n'
        '  "g": { entity: goblin }\n',
        encoding="utf-8",
    )
    catalog = load_catalog()
    base = catalog.entities["goblin"]
    level = load_level(level_path, catalog)
    game_map, _player = build_game_map(level, catalog)

    goblin = game_map.entity_spawn_index[0]

    assert goblin.name == "Goblin"
    assert goblin.fighter.max_hp == base.hp
    assert goblin.fighter.attack == base.attack
    assert goblin.fighter.defense == base.defense
    assert goblin.xp_reward == base.xp_reward
    assert goblin.drop_chance == base.drop_chance
    assert goblin.color == base.color


def test_build_game_map_populates_auto_announce_tiles_only_for_flagged_spawns(tmp_path):
    level_path = tmp_path / "announce.lvl"
    level_path.write_text(
        "id: announce\n"
        "name: Test Level\n"
        "map: |\n"
        "  #####\n"
        "  #@..#\n"
        "  #o.n#\n"
        "  #..>#\n"
        "  #####\n"
        "legend:\n"
        '  "#": wall\n'
        '  ".": floor\n'
        '  "@": player_start\n'
        '  ">": stairs_down\n'
        '  "o": { tile: landmark, description: "Announced.", announce: true }\n'
        '  "n": { tile: landmark, description: "Not announced." }\n',
        encoding="utf-8",
    )
    catalog = load_catalog()
    level = load_level(level_path, catalog)
    game_map, _player = build_game_map(level, catalog)

    assert game_map.auto_announce_tiles == {(1, 2): "Announced."}
    # both still show up in look mode's tile_descriptions regardless of announce
    assert game_map.tile_descriptions[(1, 2)] == "Announced."
    assert game_map.tile_descriptions[(3, 2)] == "Not announced."


def test_build_game_map_uses_normal_fov_radius_by_default(tmp_path):
    level_path = tmp_path / "lit.lvl"
    level_path.write_text(
        "id: lit\n"
        "name: Test Level\n"
        "map: |\n"
        "  #####\n"
        "  #@.>#\n"
        "  #####\n"
        "legend:\n"
        '  "#": wall\n'
        '  ".": floor\n'
        '  "@": player_start\n'
        '  ">": stairs_down\n',
        encoding="utf-8",
    )
    catalog = load_catalog()
    level = load_level(level_path, catalog)
    game_map, _player = build_game_map(level, catalog)

    assert game_map.fov_radius == FOV_RADIUS


def test_dark_level_shrinks_fov_radius_and_actual_visibility(tmp_path):
    # A long, straight corridor - a tile between DARK_FOV_RADIUS (3) and
    # FOV_RADIUS (8) away from player_start is the whole point of the test.
    level_path = tmp_path / "dark.lvl"
    level_path.write_text(
        "id: dark\n"
        "name: Test Level\n"
        "dark: true\n"
        "map: |\n"
        "  ############\n"
        "  #@........>#\n"
        "  ############\n"
        "legend:\n"
        '  "#": wall\n'
        '  ".": floor\n'
        '  "@": player_start\n'
        '  ">": stairs_down\n',
        encoding="utf-8",
    )
    catalog = load_catalog()
    level = load_level(level_path, catalog)
    game_map, player = build_game_map(level, catalog)

    assert game_map.fov_radius == DARK_FOV_RADIUS

    game_map.update_fov((player.x, player.y))

    assert game_map.visible[player.x + 2, player.y]  # within DARK_FOV_RADIUS
    assert not game_map.visible[player.x + 6, player.y]  # beyond it, within the normal FOV_RADIUS


def test_newly_seen_tile_announcements_returns_nothing_before_visible():
    game_map = make_open_map(20, 3)
    game_map.auto_announce_tiles[(15, 1)] = "A distant landmark."

    assert game_map.newly_seen_tile_announcements() == []


def test_newly_seen_tile_announcements_fires_once_when_visible():
    game_map = make_open_map(20, 3)
    game_map.auto_announce_tiles[(15, 1)] = "A distant landmark."

    game_map.update_fov((14, 1))  # well within FOV_RADIUS (8) of (15, 1)

    assert game_map.newly_seen_tile_announcements() == [("A distant landmark.", False)]
    # a repeat call with no intervening update_fov yields nothing more
    assert game_map.newly_seen_tile_announcements() == []


def test_newly_seen_tile_announcements_flags_a_landmark_coordinate():
    game_map = make_open_map(20, 3)
    game_map.auto_announce_tiles[(15, 1)] = "A distant landmark."
    game_map.landmark_announce_tiles.add((15, 1))

    game_map.update_fov((14, 1))

    assert game_map.newly_seen_tile_announcements() == [("A distant landmark.", True)]


def test_newly_seen_tile_announcements_does_not_repeat_on_a_later_update_fov():
    game_map = make_open_map(20, 3)
    game_map.auto_announce_tiles[(15, 1)] = "A distant landmark."

    game_map.update_fov((14, 1))
    game_map.newly_seen_tile_announcements()  # first sighting, consumed
    game_map.update_fov((14, 1))  # same position again, still visible

    assert game_map.newly_seen_tile_announcements() == []


def test_process_turn_announces_a_flagged_landmark_the_turn_it_enters_fov():
    game_map = make_open_map(20, 3)
    game_map.auto_announce_tiles[(15, 1)] = "A distant landmark."
    game_map.tile_descriptions[(15, 1)] = "A distant landmark."
    player = make_player(1, 1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")

    # starting position (1, 1) is well outside FOV_RADIUS (8) of (15, 1)
    assert engine.message_log.messages == ["You enter Test Level."]

    for _ in range(9):  # walks (1,1) -> (10,1), crossing into range at (7,1)
        engine.process_turn(BumpAction(1, 0))

    assert engine.message_log.messages.count("A distant landmark.") == 1
    assert engine.message_log.messages[-1] == "A distant landmark."

    # walking away and back doesn't repeat the announcement
    engine.process_turn(BumpAction(-1, 0))
    engine.process_turn(BumpAction(1, 0))

    assert engine.message_log.messages.count("A distant landmark.") == 1


def test_build_game_map_threads_is_teleport_through_item_entity(tmp_path):
    """item_entity_from_def hand-copies each ItemDef field into ItemEffect -
    confirms is_teleport is one of them, not silently dropped."""
    level_path = tmp_path / "teleport_spawn.lvl"
    level_path.write_text(
        "id: teleport_spawn\n"
        "name: Test Level\n"
        "map: |\n"
        "  #####\n"
        "  #@t>#\n"
        "  #####\n"
        "legend:\n"
        '  "#": wall\n'
        '  ".": floor\n'
        '  "@": player_start\n'
        '  ">": stairs_down\n'
        '  "t": { item: teleportation_potion }\n',
        encoding="utf-8",
    )
    catalog = load_catalog()
    level = load_level(level_path, catalog)
    game_map, _player = build_game_map(level, catalog)

    potion = game_map.item_spawn_index[0]
    assert potion.item.is_teleport is True
    assert potion.item.heal_amount is None


def test_build_game_map_player_start_cell_defaults_to_floor(tmp_path):
    level_path = tmp_path / "default_start.lvl"
    level_path.write_text(
        "id: default_start\n"
        "name: Test Level\n"
        "map: |\n"
        "  ###\n"
        "  #@>\n"
        "  ###\n"
        "legend:\n"
        '  "#": wall\n'
        '  "@": player_start\n'
        '  ">": stairs_down\n',
        encoding="utf-8",
    )
    catalog = load_catalog()
    level = load_level(level_path, catalog)
    game_map, player = build_game_map(level, catalog)

    assert game_map.kinds[player.x, player.y] == "floor"


def test_build_game_map_player_start_cell_uses_the_configured_override(tmp_path):
    level_path = tmp_path / "custom_start.lvl"
    level_path.write_text(
        "id: custom_start\n"
        "name: Test Level\n"
        "player_start_tile: plains\n"
        "map: |\n"
        "  ###\n"
        "  #@>\n"
        "  ###\n"
        "legend:\n"
        '  "#": wall\n'
        '  "@": player_start\n'
        '  ">": stairs_down\n',
        encoding="utf-8",
    )
    catalog = load_catalog()
    level = load_level(level_path, catalog)
    game_map, player = build_game_map(level, catalog)

    assert game_map.kinds[player.x, player.y] == "plains"


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


def test_build_game_map_populates_entity_flag_dialogue_from_spawn(tmp_path):
    level_path = tmp_path / "with_flag_dialogue.lvl"
    level_path.write_text(
        "id: with_flag_dialogue\n"
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
        '  "v": { entity: villager, flag_dialogue: [{ flag: wayford_razed, line: "It is gone." }] }\n',
        encoding="utf-8",
    )
    catalog = load_catalog()
    level = load_level(level_path, catalog)
    game_map, _player = build_game_map(level, catalog)

    villager = next(e for e in game_map.entities if e.name == "Villager")
    assert villager.flag_dialogue == [FlagDialogue(flag="wayford_razed", line="It is gone.")]


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
    # Not necessarily the last message: a tile-announcement (e.g. the
    # level_01 healing potion, within FOV from (4, 4)) can legitimately
    # follow it - see Engine._log_newly_seen_tile_announcements, always
    # called after the enter-message at every update_fov call site.
    assert engine.message_log.messages[0] == f"You enter {level_01.name}."


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


def test_arrive_player_resets_the_message_log():
    """Regression test: a cached Engine persists for the whole run (see
    docstring on Engine, "each dungeon gets at most one live Engine"), so
    without a reset, returning to it later would keep surfacing every
    message from an earlier visit alongside whatever's happening now -
    reported as old dialogue lines resurfacing when revisiting a town."""
    catalog = load_catalog()
    levels = load_levels(PRISON_TOWER_LEVELS_DIR, catalog)
    level_01 = levels["level_01"]
    game_map, player = build_game_map(level_01, catalog)
    engine = Engine(game_map, player, level_01.name, catalog=catalog)
    engine.message_log.add("Something from the first visit.")
    engine.depart_player()

    engine.arrive_player(player)

    assert "Something from the first visit." not in engine.message_log.messages
    assert engine.message_log.messages == [f"You enter {level_01.name}."]


def test_movement_onto_dungeon_entrance_sets_pending_dungeon_entry():
    catalog = load_catalog()
    level = load_overworld(
        FIXTURES_DIR / "overworld_valid", catalog, known_dungeon_ids={"prison_tower"}
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


def test_process_turn_applies_dune_damage_on_a_dunes_tile():
    game_map = make_open_map(3, 3)
    game_map.kinds[1, 1] = "dunes"
    player = make_player(1, 1, hp=30)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "The Overworld", is_overworld=True)

    engine.process_turn(WaitAction())

    # -ENVIRONMENTAL_HAZARD_DAMAGE from the hazard, +1 from the overworld's
    # passive heal (see _advance_world_clock) - net loss, the whole point of
    # the hazard.
    assert player.fighter.hp == 30 - ENVIRONMENTAL_HAZARD_DAMAGE + 1


def test_process_turn_no_dune_damage_off_a_dunes_tile():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30)
    player.fighter.hp = 20
    game_map.entities.append(player)
    engine = Engine(game_map, player, "The Overworld", is_overworld=True)

    engine.process_turn(WaitAction())

    assert player.fighter.hp == 21  # only the passive heal applied


def test_dune_damage_applies_off_the_overworld_too_since_it_is_tile_based():
    game_map = make_open_map(3, 3)
    game_map.kinds[1, 1] = "dunes"
    player = make_player(1, 1, hp=30)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")  # is_overworld defaults False

    engine.process_turn(WaitAction())

    assert player.fighter.hp == 30 - ENVIRONMENTAL_HAZARD_DAMAGE  # no passive heal outside the overworld


def test_dune_damage_can_kill_the_player():
    game_map = make_open_map(3, 3)
    game_map.kinds[1, 1] = "dunes"
    player = make_player(1, 1, hp=ENVIRONMENTAL_HAZARD_DAMAGE)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert engine.game_state == "dead"


def test_potion_kind_identifies_sure_footed():
    assert potion_kind(ItemEffect(grants_buff="sure_footed", buff_duration=15)) == "sure_footed"


def test_sure_footed_buff_grants_full_hazard_immunity():
    game_map = make_open_map(3, 3)
    game_map.kinds[1, 1] = "dunes"
    player = make_player(1, 1, hp=30)
    player.fighter.active_buffs["sure_footed"] = ActiveEffect(potency=0, turns_remaining=5)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert player.fighter.hp == 30  # no damage, no message
    assert "Wind-driven sand tears at exposed skin and eyes." not in engine.message_log.messages


def test_use_item_action_sure_footed_grants_the_buff_and_stops_dune_damage():
    game_map = make_open_map(3, 3)
    game_map.kinds[1, 1] = "dunes"
    player = make_player(1, 1, hp=30)
    potion = make_sure_footing_potion(1, 1, duration=15)
    player.inventory.append(potion)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")
    player.selected_potion_kind = "sure_footed"

    engine.process_turn(UseItemAction())

    assert potion not in player.inventory
    # Granted and ticked in the same turn, same "first tick lands
    # immediately" convention every other active_buffs entry follows.
    assert player.fighter.active_buffs["sure_footed"] == ActiveEffect(potency=0, turns_remaining=14)
    assert player.fighter.hp == 30  # the dune tile did nothing this turn either
    assert "You drink the Sure-Footing Draught and your footing turns certain." in engine.message_log.messages


def test_sure_footed_expiry_restores_dune_damage():
    game_map = make_open_map(3, 3)
    game_map.kinds[1, 1] = "dunes"
    player = make_player(1, 1, hp=30)
    player.fighter.active_buffs["sure_footed"] = ActiveEffect(potency=0, turns_remaining=1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())
    assert player.fighter.hp == 30  # still immune this turn
    assert "sure_footed" not in player.fighter.active_buffs

    engine.process_turn(WaitAction())
    assert player.fighter.hp == 30 - ENVIRONMENTAL_HAZARD_DAMAGE  # immunity expired - dune damage resumes


def test_ashen_plains_reuses_the_same_hazard_mechanic_as_dunes():
    game_map = make_open_map(3, 3)
    game_map.kinds[1, 1] = "ashen_plains"
    player = make_player(1, 1, hp=30)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")  # is_overworld defaults False

    engine.process_turn(WaitAction())

    # Same ENVIRONMENTAL_HAZARD_DAMAGE as dunes - only the flavor text differs.
    assert player.fighter.hp == 30 - ENVIRONMENTAL_HAZARD_DAMAGE


def test_blighted_forest_reuses_the_same_hazard_mechanic_as_dunes():
    game_map = make_open_map(3, 3)
    game_map.kinds[1, 1] = "blighted_forest"
    player = make_player(1, 1, hp=30)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert player.fighter.hp == 30 - ENVIRONMENTAL_HAZARD_DAMAGE


def test_scoured_ground_looks_corrupted_but_deals_no_damage():
    """scoured_ground shares ashen_plains' exact look (engine/render.py's
    TILE_VISUALS, data/sprites.yaml) but is deliberately absent from
    ENVIRONMENTAL_HAZARD_MESSAGES - ground that reads as Northern Steppe
    corruption without punishing a player for standing on it (see
    data/dungeons/visitor_band_ambush)."""
    game_map = make_open_map(3, 3)
    game_map.kinds[1, 1] = "scoured_ground"
    player = make_player(1, 1, hp=30)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")

    for _ in range(10):
        engine.process_turn(WaitAction())

    assert player.fighter.hp == 30


# --- Visitor band ambush encounters (ashen_plains/blighted_forest only) ---
# See tests/test_main.py for the actual redirect-into-a-dungeon mechanics
# (goblin_ambush's own shape) - these only cover the mailbox flag Engine
# sets for main.py's resolve_transition to act on.


def test_visitor_band_encounter_does_not_arm_off_a_corrupted_tile(monkeypatch):
    game_map = make_open_map(11, 11)
    player = make_player(5, 5, hp=30)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "The Overworld", is_overworld=True)
    monkeypatch.setattr(random, "random", lambda: 0.0)  # would always succeed on a corrupted tile

    engine._maybe_trigger_visitor_band_encounter()

    assert engine.wants_visitor_band_encounter is False


def test_visitor_band_encounter_does_not_arm_when_the_roll_fails(monkeypatch):
    game_map = make_open_map(11, 11)
    game_map.kinds[5, 5] = "ashen_plains"
    player = make_player(5, 5, hp=30)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "The Overworld", is_overworld=True)
    monkeypatch.setattr(random, "random", lambda: VISITOR_BAND_ENCOUNTER_CHANCE)  # at threshold - fails

    engine._maybe_trigger_visitor_band_encounter()

    assert engine.wants_visitor_band_encounter is False


def test_visitor_band_encounter_does_not_arm_off_the_overworld(monkeypatch):
    game_map = make_open_map(11, 11)
    game_map.kinds[5, 5] = "ashen_plains"
    player = make_player(5, 5, hp=30)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")  # is_overworld defaults False
    monkeypatch.setattr(random, "random", lambda: 0.0)  # would always succeed on the overworld

    engine._maybe_trigger_visitor_band_encounter()

    assert engine.wants_visitor_band_encounter is False


def test_visitor_band_encounter_arms_on_ashen_plains_when_the_roll_succeeds(monkeypatch):
    game_map = make_open_map(11, 11)
    game_map.kinds[5, 5] = "ashen_plains"
    player = make_player(5, 5, hp=30)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "The Overworld", is_overworld=True)
    monkeypatch.setattr(random, "random", lambda: 0.0)

    engine._maybe_trigger_visitor_band_encounter()

    assert engine.wants_visitor_band_encounter is True


def test_visitor_band_encounter_arms_on_blighted_forest_too(monkeypatch):
    game_map = make_open_map(11, 11)
    game_map.kinds[5, 5] = "blighted_forest"
    player = make_player(5, 5, hp=30)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "The Overworld", is_overworld=True)
    monkeypatch.setattr(random, "random", lambda: 0.0)

    engine._maybe_trigger_visitor_band_encounter()

    assert engine.wants_visitor_band_encounter is True


def test_process_turn_can_arm_a_visitor_band_encounter_on_ashen_plains(monkeypatch):
    game_map = make_open_map(11, 11)
    game_map.kinds[5, 5] = "ashen_plains"
    player = make_player(5, 5, hp=30)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "The Overworld", is_overworld=True)
    monkeypatch.setattr(random, "random", lambda: 0.0)

    engine.process_turn(WaitAction())

    assert engine.wants_visitor_band_encounter is True


def test_roll_visitor_band_picks_the_hollow_reach_tier_in_the_north(monkeypatch):
    monkeypatch.setattr(random, "randint", lambda lo, hi: lo)

    band = roll_visitor_band(0)  # y=0 <= HOLLOW_REACH_MAX_Y

    assert len(band) == HOLLOW_REACH_BAND[1][0]
    assert all(entity_id in HOLLOW_REACH_BAND[0] for entity_id in band)


def test_roll_visitor_band_picks_the_cinder_marches_tier_in_the_middle(monkeypatch):
    monkeypatch.setattr(random, "randint", lambda lo, hi: lo)

    band = roll_visitor_band(45)  # HOLLOW_REACH_MAX_Y < 45 <= CINDER_MARCHES_MAX_Y

    assert len(band) == CINDER_MARCHES_BAND[1][0]
    assert all(entity_id in CINDER_MARCHES_BAND[0] for entity_id in band)


def test_roll_visitor_band_picks_the_frayed_edge_tier_in_the_south(monkeypatch):
    monkeypatch.setattr(random, "randint", lambda lo, hi: lo)

    band = roll_visitor_band(89)  # y > CINDER_MARCHES_MAX_Y

    assert len(band) == FRAYED_EDGE_BAND[1][0]
    assert all(entity_id in FRAYED_EDGE_BAND[0] for entity_id in band)


def test_roll_visitor_band_never_rolls_excavation_warden():
    for y in (0, 15, 29, 30, 45, 59, 60, 75, 89):
        for _ in range(20):
            assert "excavation_warden" not in roll_visitor_band(y)


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


# --- destroy_dungeon ---


def test_destroy_dungeon_seals_the_entrance_and_updates_the_tile():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    game_map.dungeon_entrances[(2, 0)] = "wayford"
    engine = Engine(
        game_map, player, "The Overworld", is_overworld=True,
        dungeon_ruin_data={"wayford": ("road", "Ash and quiet.", None)},
    )

    engine.destroy_dungeon("wayford")

    assert (2, 0) not in game_map.dungeon_entrances
    assert game_map.kinds[2, 0] == "road"
    assert bool(game_map.walkable[2, 0]) is True
    assert game_map.tile_descriptions[(2, 0)] == "Ash and quiet."
    assert "wayford" in engine.quest_log.destroyed_dungeon_ids


def test_build_game_map_spawns_an_inert_decoration_entity():
    from content.loader import DecorationSpawn, ParsedLevel
    from content.schema import DECORATION_NAMES
    from engine.game_map import DECORATION_FG

    catalog = load_catalog()
    level = ParsedLevel(
        id="level_01", name="Test", width=3, height=3, tiles=[["floor"] * 3] * 3,
        player_start=(1, 1), player_start_tile="floor",
        entity_spawns=[], item_spawns=[], stairs=[], doors=[],
        dungeon_entrances=[], tile_descriptions=[],
        open_boundary=False, open_boundary_message="", dark=False,
        decoration_spawns=[DecorationSpawn(x=0, y=0, kind="table")],
    )

    game_map, player = build_game_map(level, catalog)

    assert len(game_map.decorations) == 1
    decoration = game_map.decorations[0]
    assert (decoration.x, decoration.y) == (0, 0)
    assert decoration.entity_id == "table"
    assert decoration.name == DECORATION_NAMES["table"]
    assert decoration.fighter is None
    assert decoration.item is None
    assert decoration.ai is None
    assert decoration.blocks_movement is False
    # Regression guard: fg=(255,255,255) is an identity multiply in tcod's
    # console.print (see engine/game_map.py's DECORATION_FG docstring) - a
    # decoration rendered at full, undimmed brightness reads as a highlight/
    # glow next to everything else in a scene, which does get dimmed by its
    # own fg color. Must stay a real, non-white tint.
    assert decoration.color == DECORATION_FG
    assert decoration.color != (255, 255, 255)
    # A decoration never enters game_map.entities - nothing that iterates it
    # (combat, AI, blocking_entity_at, save/load) should ever see one.
    assert decoration not in game_map.entities
    assert game_map.blocking_entity_at(0, 0) is None
    assert game_map.is_walkable(0, 0) is True


def test_engine_current_level_id_defaults_to_starting_level():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    from content.loader import ParsedLevel

    level = ParsedLevel(
        id="level_01", name="Test", width=3, height=3, tiles=[["floor"] * 3] * 3,
        player_start=(1, 1), player_start_tile="floor",
        entity_spawns=[], item_spawns=[], stairs=[], doors=[],
        dungeon_entrances=[], tile_descriptions=[],
        open_boundary=False, open_boundary_message="", dark=False,
    )
    engine = Engine(game_map, player, "Test", starting_level=level)

    assert engine.current_level_id == "level_01"


def test_engine_current_level_id_explicit_override_wins():
    """The case this exists for: a razed dungeon's fresh-entry Engine
    shows a different level (the ruins) than its own pristine
    starting_level (kept only for Engine.restart() to rebuild from) - see
    main.py's resolve_transition and engine/save.py's restore_save."""
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    from content.loader import ParsedLevel

    level = ParsedLevel(
        id="level_01", name="Test", width=3, height=3, tiles=[["floor"] * 3] * 3,
        player_start=(1, 1), player_start_tile="floor",
        entity_spawns=[], item_spawns=[], stairs=[], doors=[],
        dungeon_entrances=[], tile_descriptions=[],
        open_boundary=False, open_boundary_message="", dark=False,
    )
    engine = Engine(
        game_map, player, "Test's Ruins", starting_level=level,
        current_level_id="level_01_ruins",
    )

    assert engine.current_level_id == "level_01_ruins"


def _make_two_level_goblin_dungeon(tmp_path):
    """A synthetic 2-level dungeon (level_01: 2 goblins, level_02: 1
    goblin), require_stairs_down: false so neither level needs a real
    stairs chain - just enough content to test
    Engine._entity_type_cleared_from_dungeon's whole-dungeon,
    visited-and-unvisited-level population check."""
    levels_dir = tmp_path / "levels"
    levels_dir.mkdir(parents=True)
    (levels_dir / "level_01.lvl").write_text(
        "id: level_01\n"
        "name: Test Level One\n"
        "map: |\n"
        "  #######\n"
        "  #@gg.x#\n"
        "  #######\n"
        "legend:\n"
        '  "#": wall\n'
        '  ".": floor\n'
        '  "@": player_start\n'
        '  "g": { entity: goblin }\n'
        '  "x": stairs_up\n',
        encoding="utf-8",
    )
    (levels_dir / "level_02.lvl").write_text(
        "id: level_02\n"
        "name: Test Level Two\n"
        "map: |\n"
        "  #######\n"
        "  #@.g.x#\n"
        "  #######\n"
        "legend:\n"
        '  "#": wall\n'
        '  ".": floor\n'
        '  "@": player_start\n'
        '  "g": { entity: goblin }\n'
        '  "x": stairs_up\n',
        encoding="utf-8",
    )
    catalog = load_catalog()
    levels = load_levels(levels_dir, catalog, require_stairs_down=False)
    game_map, player = build_game_map(levels["level_01"], catalog)
    engine = Engine(
        game_map, player, "Test Level One",
        catalog=catalog, levels=levels, starting_level=levels["level_01"],
        current_level_id="level_01",
    )
    return engine, levels


def test_entity_type_cleared_from_dungeon_false_while_current_level_has_survivors(tmp_path):
    engine, _ = _make_two_level_goblin_dungeon(tmp_path)
    assert engine._entity_type_cleared_from_dungeon("goblin") is False


def test_entity_type_cleared_from_dungeon_false_while_an_unvisited_level_has_spawns(tmp_path):
    engine, _ = _make_two_level_goblin_dungeon(tmp_path)
    # Kill both goblins on the current (visited) level, directly - level_02
    # is never visited, so its own goblin is still authored-alive.
    for goblin in [e for e in engine.game_map.entities if e.entity_id == "goblin"]:
        engine.game_map.entities.remove(goblin)

    assert engine._entity_type_cleared_from_dungeon("goblin") is False


def test_entity_type_cleared_from_dungeon_true_once_every_level_is_accounted_for(tmp_path):
    engine, levels = _make_two_level_goblin_dungeon(tmp_path)
    for goblin in [e for e in engine.game_map.entities if e.entity_id == "goblin"]:
        engine.game_map.entities.remove(goblin)
    # Now "visit" level_02 too, with its own goblin already dead.
    catalog = load_catalog()
    level_02_map, _ = build_game_map(levels["level_02"], catalog)
    for goblin in [e for e in level_02_map.entities if e.entity_id == "goblin"]:
        level_02_map.entities.remove(goblin)
    engine.visited_maps["level_02"] = level_02_map

    assert engine._entity_type_cleared_from_dungeon("goblin") is True


def test_entity_type_cleared_from_dungeon_false_for_a_non_dungeon_engine():
    """self.levels is None for an Engine with no dungeon (e.g. the
    overworld, or a bare test Engine) - the check is meaningless there and
    must not crash."""
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    engine = Engine(game_map, player, "Test Level")

    assert engine._entity_type_cleared_from_dungeon("goblin") is False


def test_on_entity_death_marks_cleared_species_ids_once_the_whole_dungeon_is_clear(tmp_path):
    engine, levels = _make_two_level_goblin_dungeon(tmp_path)
    catalog = load_catalog()
    level_02_map, _ = build_game_map(levels["level_02"], catalog)
    engine.visited_maps["level_02"] = level_02_map
    for goblin in [e for e in level_02_map.entities if e.entity_id == "goblin"]:
        level_02_map.entities.remove(goblin)
    quest = Quest(
        id="clear_the_goblins", name="Clear the Goblins", description="",
        completion_message="Done!", failure_message="",
        target_cull_entity_id="goblin", questgiver_entity_id="grey_valley_elder",
        status="in_progress",
    )
    engine.quest_log = QuestLog(quests={quest.id: quest})

    goblins = [e for e in engine.game_map.entities if e.entity_id == "goblin"]
    engine.on_entity_death(goblins[0])
    assert "goblin" not in engine.quest_log.cleared_species_ids  # one goblin still alive

    engine.on_entity_death(goblins[1])
    assert "goblin" in engine.quest_log.cleared_species_ids


def test_on_entity_death_does_not_scan_when_no_quest_cares(tmp_path):
    """The whole-dungeon scan is gated on a live quest actually targeting
    this species - confirmed indirectly: killing every goblin with no cull
    quest in the log at all must not raise or otherwise misbehave."""
    engine, levels = _make_two_level_goblin_dungeon(tmp_path)
    goblins = list(engine.game_map.entities)
    for goblin in [e for e in goblins if e.entity_id == "goblin"]:
        engine.on_entity_death(goblin)

    assert engine.quest_log.cleared_species_ids == set()


def test_on_entity_death_fails_a_cull_quest_once_preservation_tolerance_is_exceeded():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    engine = Engine(game_map, player, "Test Level")
    quest = Quest(
        id="clear_the_goblins", name="Clear the Goblins", description="",
        completion_message="Done!", failure_message="Too many spiders died.",
        target_cull_entity_id="goblin", target_preserve_entity_id="cave_spider",
        target_preserve_tolerance=1, questgiver_entity_id="grey_valley_elder",
        status="in_progress",
    )
    engine.quest_log = QuestLog(quests={quest.id: quest})
    spider_1 = make_monster(2, 1, hp=1, ai="skittish")
    spider_1.entity_id = "cave_spider"
    spider_2 = make_monster(2, 2, hp=1, ai="skittish")
    spider_2.entity_id = "cave_spider"
    game_map.entities.extend([spider_1, spider_2])

    engine.on_entity_death(spider_1)
    assert quest.status == "in_progress"  # first loss - within tolerance

    engine.on_entity_death(spider_2)
    assert quest.status == "failed"
    assert "Too many spiders died." in engine.message_log.messages


def test_destroy_dungeon_with_ruined_starting_level_keeps_the_entrance_walkable():
    """The walkable-ruins case (see docs/dungeon_bibles/wayford.md's
    "After: the Razing") - unlike the plain seal-it-off case above, the
    entrance must stay in dungeon_entrances so MovementAction can still
    route the player in, just leading to a different level once there
    (see main.py's resolve_transition)."""
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    game_map.dungeon_entrances[(2, 0)] = "wayford"
    engine = Engine(
        game_map, player, "The Overworld", is_overworld=True,
        dungeon_ruin_data={"wayford": ("floor", "Ash and quiet.", "level_01_ruins")},
    )

    engine.destroy_dungeon("wayford")

    assert game_map.dungeon_entrances[(2, 0)] == "wayford"
    assert game_map.kinds[2, 0] == "floor"
    assert game_map.tile_descriptions[(2, 0)] == "Ash and quiet."
    assert "wayford" in engine.quest_log.destroyed_dungeon_ids


def test_destroy_dungeon_voids_matching_quests_and_logs_only_in_progress_ones():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    game_map.dungeon_entrances[(2, 0)] = "wayford"
    in_progress_quest = Quest(
        id="q1", name="Q1", description="", completion_message="done",
        failure_message="q1 failed", voided_by_dungeon_id="wayford", status="in_progress",
    )
    not_given_quest = Quest(
        id="q2", name="Q2", description="", completion_message="done",
        failure_message="q2 failed", voided_by_dungeon_id="wayford", status="not_given",
    )
    unrelated_quest = Quest(
        id="q3", name="Q3", description="", completion_message="done",
        voided_by_dungeon_id="millhaven", status="in_progress",
    )
    quest_log = QuestLog(quests={
        in_progress_quest.id: in_progress_quest,
        not_given_quest.id: not_given_quest,
        unrelated_quest.id: unrelated_quest,
    })
    engine = Engine(
        game_map, player, "The Overworld", is_overworld=True, quest_log=quest_log,
        dungeon_ruin_data={"wayford": ("road", "Ash and quiet.", None)},
    )

    engine.destroy_dungeon("wayford")

    assert in_progress_quest.status == "failed"
    assert not_given_quest.status == "failed"
    assert unrelated_quest.status == "in_progress"
    assert "q1 failed" in engine.message_log.messages
    assert "q2 failed" not in engine.message_log.messages


def test_destroy_dungeon_is_a_safe_no_op_for_an_unmapped_dungeon_id():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "The Overworld", is_overworld=True)

    engine.destroy_dungeon("nonexistent")  # no ruin data registered - must not raise

    assert engine.quest_log.destroyed_dungeon_ids == set()


def test_destroy_dungeon_is_idempotent_when_called_twice():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    game_map.dungeon_entrances[(2, 0)] = "wayford"
    engine = Engine(
        game_map, player, "The Overworld", is_overworld=True,
        dungeon_ruin_data={"wayford": ("road", "Ash and quiet.", None)},
    )

    engine.destroy_dungeon("wayford")
    engine.destroy_dungeon("wayford")  # already gone from dungeon_entrances - must not raise

    assert (2, 0) not in game_map.dungeon_entrances


def test_process_turn_destroys_dungeon_when_a_deadline_quest_with_on_fail_destroy_dungeon_id_expires():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    game_map.dungeon_entrances[(2, 0)] = "wayford"
    quest = Quest(
        id="spreading_the_warning", name="Spreading the Warning", description="",
        completion_message="done", failure_message="too late",
        deadline_year=STARTING_YEAR, deadline_day=STARTING_DAY,
        on_fail=[WorldConsequence(destroy_dungeon_id="wayford")], status="in_progress",
    )
    voided_quest = Quest(
        id="clearing_the_watch_road", name="Clearing the Watch Road", description="",
        completion_message="done", failure_message="wayford is gone",
        voided_by_dungeon_id="wayford", status="in_progress",
    )
    quest_log = QuestLog(quests={quest.id: quest, voided_quest.id: voided_quest})
    clock = GameClock(year=STARTING_YEAR, day=STARTING_DAY, hour=HOURS_PER_DAY - 1)
    engine = Engine(
        game_map, player, "The Overworld", is_overworld=True, clock=clock, quest_log=quest_log,
        dungeon_ruin_data={"wayford": ("road", "Ash and quiet.", None)},
    )

    engine.process_turn(WaitAction())  # crosses into the next day - both deadlines cross

    assert quest.status == "failed"
    assert voided_quest.status == "failed"
    assert (2, 0) not in game_map.dungeon_entrances
    assert game_map.kinds[2, 0] == "road"
    assert "too late" in engine.message_log.messages
    assert "wayford is gone" in engine.message_log.messages
    assert "wayford" in quest_log.destroyed_dungeon_ids


def test_process_turn_sets_world_flag_when_a_deadline_quest_with_on_fail_set_flag_expires():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    quest = Quest(
        id="a_quiet_failure", name="A Quiet Failure", description="",
        completion_message="done", failure_message="too late",
        deadline_year=STARTING_YEAR, deadline_day=STARTING_DAY,
        on_fail=[WorldConsequence(set_flag="wayford_population_thinned")], status="in_progress",
    )
    quest_log = QuestLog(quests={quest.id: quest})
    clock = GameClock(year=STARTING_YEAR, day=STARTING_DAY, hour=HOURS_PER_DAY - 1)
    engine = Engine(
        game_map, player, "The Overworld", is_overworld=True, clock=clock, quest_log=quest_log,
        # No dungeon_ruin_data/dungeon_entrances at all - a set_flag
        # consequence needs no dungeon involvement whatsoever.
    )

    engine.process_turn(WaitAction())  # crosses into the next day - deadline crosses

    assert quest.status == "failed"
    assert quest_log.world_flags == {"wayford_population_thinned"}
    assert game_map.dungeon_entrances == {}


def test_process_turn_applies_both_consequences_when_on_fail_has_a_destroy_and_a_flag():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    game_map.dungeon_entrances[(2, 0)] = "wayford"
    quest = Quest(
        id="spreading_the_warning", name="Spreading the Warning", description="",
        completion_message="done", failure_message="too late",
        deadline_year=STARTING_YEAR, deadline_day=STARTING_DAY,
        on_fail=[
            WorldConsequence(destroy_dungeon_id="wayford"),
            WorldConsequence(set_flag="wayford_razed"),
        ],
        status="in_progress",
    )
    quest_log = QuestLog(quests={quest.id: quest})
    clock = GameClock(year=STARTING_YEAR, day=STARTING_DAY, hour=HOURS_PER_DAY - 1)
    engine = Engine(
        game_map, player, "The Overworld", is_overworld=True, clock=clock, quest_log=quest_log,
        dungeon_ruin_data={"wayford": ("road", "Ash and quiet.", None)},
    )

    engine.process_turn(WaitAction())  # crosses into the next day - deadline crosses

    assert (2, 0) not in game_map.dungeon_entrances
    assert "wayford" in quest_log.destroyed_dungeon_ids
    assert quest_log.world_flags == {"wayford_razed"}


def test_process_turn_applies_on_fail_consequences_even_when_the_quest_was_never_given():
    """Regression test: the player never picked up spreading_the_warning
    (status stays "not_given" - e.g. they never talked to the Village
    Chief to receive it), but its deadline still passes. Wayford must
    still be razed - the world doesn't wait for the player to have taken
    the quest before its consequences land. Unlike the in_progress case
    above, no failure_message should be logged: announcing the failure of
    a quest the player never received would be confusing."""
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    game_map.dungeon_entrances[(2, 0)] = "wayford"
    quest = Quest(
        id="spreading_the_warning", name="Spreading the Warning", description="",
        completion_message="done", failure_message="too late",
        deadline_year=STARTING_YEAR, deadline_day=STARTING_DAY,
        on_fail=[
            WorldConsequence(destroy_dungeon_id="wayford"),
            WorldConsequence(set_flag="wayford_razed"),
        ],
        status="not_given",
    )
    quest_log = QuestLog(quests={quest.id: quest})
    clock = GameClock(year=STARTING_YEAR, day=STARTING_DAY, hour=HOURS_PER_DAY - 1)
    engine = Engine(
        game_map, player, "The Overworld", is_overworld=True, clock=clock, quest_log=quest_log,
        dungeon_ruin_data={"wayford": ("road", "Ash and quiet.", None)},
    )

    engine.process_turn(WaitAction())  # crosses into the next day - deadline crosses

    assert quest.status == "failed"
    assert (2, 0) not in game_map.dungeon_entrances
    assert "wayford" in quest_log.destroyed_dungeon_ids
    assert quest_log.world_flags == {"wayford_razed"}
    assert "too late" not in engine.message_log.messages


def test_tighten_deadline_shortens_a_later_deadline():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    target = Quest(
        id="a_wall_worth_holding", name="A Wall Worth Holding", description="",
        completion_message="done", deadline_year=87, deadline_day=70, status="not_given",
    )
    quest_log = QuestLog(quests={target.id: target})
    engine = Engine(game_map, player, "The Overworld", is_overworld=True, quest_log=quest_log)

    engine._tighten_deadline(TightenDeadline(quest_id="a_wall_worth_holding", new_day=66))

    assert target.deadline_day == 66


def test_tighten_deadline_is_a_noop_when_new_day_is_later():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    target = Quest(
        id="a_wall_worth_holding", name="A Wall Worth Holding", description="",
        completion_message="done", deadline_year=87, deadline_day=70, status="not_given",
    )
    quest_log = QuestLog(quests={target.id: target})
    engine = Engine(game_map, player, "The Overworld", is_overworld=True, quest_log=quest_log)

    engine._tighten_deadline(TightenDeadline(quest_id="a_wall_worth_holding", new_day=75))

    assert target.deadline_day == 70


def test_tighten_deadline_is_a_noop_on_a_completed_target():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    target = Quest(
        id="a_wall_worth_holding", name="A Wall Worth Holding", description="",
        completion_message="done", deadline_year=87, deadline_day=70, status="completed",
    )
    quest_log = QuestLog(quests={target.id: target})
    engine = Engine(game_map, player, "The Overworld", is_overworld=True, quest_log=quest_log)

    engine._tighten_deadline(TightenDeadline(quest_id="a_wall_worth_holding", new_day=66))

    assert target.deadline_day == 70


def test_tighten_deadline_is_a_noop_on_a_failed_target():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    target = Quest(
        id="a_wall_worth_holding", name="A Wall Worth Holding", description="",
        completion_message="done", deadline_year=87, deadline_day=70, status="failed",
    )
    quest_log = QuestLog(quests={target.id: target})
    engine = Engine(game_map, player, "The Overworld", is_overworld=True, quest_log=quest_log)

    engine._tighten_deadline(TightenDeadline(quest_id="a_wall_worth_holding", new_day=66))

    assert target.deadline_day == 70


def test_tighten_deadline_is_a_noop_on_an_unknown_quest():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    quest_log = QuestLog(quests={})
    engine = Engine(game_map, player, "The Overworld", is_overworld=True, quest_log=quest_log)

    engine._tighten_deadline(TightenDeadline(quest_id="nonexistent_quest", new_day=66))  # must not raise


def test_tighten_deadline_works_on_a_not_given_target():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    target = Quest(
        id="a_wall_worth_holding", name="A Wall Worth Holding", description="",
        completion_message="done", deadline_year=87, deadline_day=70, status="not_given",
    )
    quest_log = QuestLog(quests={target.id: target})
    engine = Engine(game_map, player, "The Overworld", is_overworld=True, quest_log=quest_log)

    engine._tighten_deadline(TightenDeadline(quest_id="a_wall_worth_holding", new_day=66))

    assert target.deadline_day == 66


def test_process_turn_tightens_a_deadline_when_on_fail_tighten_deadline_expires():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    quest = Quest(
        id="spreading_the_warning", name="Spreading the Warning", description="",
        completion_message="done", failure_message="too late",
        deadline_year=STARTING_YEAR, deadline_day=STARTING_DAY,
        on_fail=[WorldConsequence(
            tighten_deadline=TightenDeadline(quest_id="a_wall_worth_holding", new_day=66)
        )],
        status="in_progress",
    )
    target = Quest(
        id="a_wall_worth_holding", name="A Wall Worth Holding", description="",
        completion_message="done", deadline_year=STARTING_YEAR, deadline_day=70, status="not_given",
    )
    quest_log = QuestLog(quests={quest.id: quest, target.id: target})
    clock = GameClock(year=STARTING_YEAR, day=STARTING_DAY, hour=HOURS_PER_DAY - 1)
    engine = Engine(
        game_map, player, "The Overworld", is_overworld=True, clock=clock, quest_log=quest_log,
    )

    engine.process_turn(WaitAction())  # crosses into the next day - deadline crosses

    assert quest.status == "failed"
    assert target.deadline_day == 66


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


def test_talk_to_adjacent_dialogue_message_carries_the_speakers_name():
    """See engine/render.py's render_message_log - the speaker field is
    what lets the log highlight who's talking, separate from the message
    text itself (which stays unchanged for backward compatibility)."""
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    villager = make_villager(2, 1, dialogue="Well held up better than most things.", name="Elder")
    game_map.entities.extend([player, villager])
    engine = Engine(game_map, player, "Test Level")

    engine.talk_to_adjacent()

    message = engine.message_log.messages[-1]
    assert message.speaker == "Elder"
    assert message.category == "dialogue"


def test_talk_to_adjacent_falls_back_to_catalog_default_dialogue():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    villager = make_villager(2, 1, dialogue="")  # no per-spawn override
    game_map.entities.extend([player, villager])
    engine = Engine(game_map, player, "Test Level")

    engine.talk_to_adjacent()

    assert 'Villager: "They don\'t seem to have anything to say."' in engine.message_log.messages


def test_talk_to_adjacent_shows_flag_dialogue_when_flag_is_set():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    villager = make_villager(
        2, 1, dialogue="Normal line.",
        flag_dialogue=[FlagDialogue(flag="wayford_razed", line="It is gone.")],
    )
    game_map.entities.extend([player, villager])
    engine = Engine(game_map, player, "Test Level")
    engine.quest_log.world_flags.add("wayford_razed")

    engine.talk_to_adjacent()

    assert 'Villager: "It is gone."' in engine.message_log.messages


def test_talk_to_adjacent_ignores_flag_dialogue_when_flag_is_not_set():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    villager = make_villager(
        2, 1, dialogue="Normal line.",
        flag_dialogue=[FlagDialogue(flag="wayford_razed", line="It is gone.")],
    )
    game_map.entities.extend([player, villager])
    engine = Engine(game_map, player, "Test Level")

    engine.talk_to_adjacent()

    assert 'Villager: "Normal line."' in engine.message_log.messages


def test_talk_to_adjacent_flag_dialogue_checks_list_in_order_first_match_wins():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    villager = make_villager(
        2, 1, dialogue="Normal line.",
        flag_dialogue=[
            FlagDialogue(flag="first_flag", line="First line."),
            FlagDialogue(flag="second_flag", line="Second line."),
        ],
    )
    game_map.entities.extend([player, villager])
    engine = Engine(game_map, player, "Test Level")
    engine.quest_log.world_flags.update({"first_flag", "second_flag"})

    engine.talk_to_adjacent()

    assert 'Villager: "First line."' in engine.message_log.messages


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


def test_on_entity_death_records_a_kill_quests_target_but_does_not_complete_it():
    """Killing the target is only step one now - same two-step shape as a
    fetch quest's pickup vs. delivery. Completion only happens when the
    player reports back to the questgiver (see
    test_talk_to_adjacent_completes_a_kill_quest_after_the_target_is_dead)."""
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

    assert quest.status == "in_progress"
    assert quest.completion_message not in engine.message_log.messages
    assert "warden" in quest_log.killed_entity_ids
    assert player.inventory == []


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


def test_on_entity_death_fails_an_in_progress_intimidate_quest_immediately():
    """The intimidate shape's unique failure path: unlike a kill quest,
    which only records the death and waits for the next report, a target's
    death immediately force-fails an intimidate quest - it can never be
    "intimidated" after the fact."""
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    debtor = make_villager(2, 1, entity_id="millhaven_debtor")
    game_map.entities.extend([player, debtor])
    quest = Quest(
        id="a_debt_worth_collecting", name="A Debt Worth Collecting", description="",
        completion_message="done", failure_message="The debtor's dead, and dead men don't pay.",
        target_intimidate_entity_id="millhaven_debtor", status="in_progress",
    )
    quest_log = QuestLog(quests={quest.id: quest})
    engine = Engine(game_map, player, "Test Level", quest_log=quest_log)

    engine.on_entity_death(debtor)

    assert quest.status == "failed"
    assert "The debtor's dead, and dead men don't pay." in engine.message_log.messages


def test_on_entity_death_silently_fails_a_not_given_intimidate_quest():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    debtor = make_villager(2, 1, entity_id="millhaven_debtor")
    game_map.entities.extend([player, debtor])
    quest = Quest(
        id="a_debt_worth_collecting", name="A Debt Worth Collecting", description="",
        completion_message="done", failure_message="The debtor's dead, and dead men don't pay.",
        target_intimidate_entity_id="millhaven_debtor", status="not_given",
    )
    quest_log = QuestLog(quests={quest.id: quest})
    engine = Engine(game_map, player, "Test Level", quest_log=quest_log)

    engine.on_entity_death(debtor)

    assert quest.status == "failed"
    assert "The debtor's dead, and dead men don't pay." not in engine.message_log.messages


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


def test_talk_to_adjacent_flag_dialogue_outranks_an_active_followup_line():
    """A world-flag reaction takes priority even over an already-active
    QuestLog.followup_dialogue line - something happened in the world that
    supersedes recycled per-quest thank-you chatter (see
    docs/content_design_process.md §0k)."""
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    prisoner = make_villager(
        2, 1, dialogue="Made it out too.", entity_id="escaped_prisoner", name="Escaped Prisoner",
        flag_dialogue=[FlagDialogue(flag="wayford_razed", line="Heard about Wayford.")],
    )
    game_map.entities.extend([player, prisoner])
    quest_log = real_quest_log()
    quest_log.record_entity_killed("warden")  # already dead
    engine = Engine(game_map, player, "Test Level", catalog=catalog, quest_log=quest_log)

    engine.talk_to_adjacent()  # first Talk: completes the quest retroactively
    engine.talk_to_adjacent()  # second Talk: followup_dialogue is now active
    engine.message_log.messages.clear()
    engine.quest_log.world_flags.add("wayford_razed")

    engine.talk_to_adjacent()  # third Talk: the flag line must win

    quest = quest_log.quests["kill_the_warden"]
    assert 'Escaped Prisoner: "Heard about Wayford."' in engine.message_log.messages
    assert f'Escaped Prisoner: "{quest.questgiver_done_dialogue}"' not in engine.message_log.messages


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
    assert engine.shop_price("healing_potion", shopkeeper) == 20  # discount reward granted


def test_talk_to_adjacent_chains_spreading_the_warning_after_goblin_warning():
    """Full requires_quest_id chain against the real shipped content, now
    three links deep (goblin_warning -> spreading_the_warning ->
    word_from_the_north): each quest is withheld until its prerequisite is
    actually completed, needs a second Talk to grant (check_questgiver runs
    before check_talked_to/check_dungeon_report within the same call, so a
    chain quest can't grant itself in the same Talk that completes its
    prerequisite), and each questgiver's post-completion line updates
    instead of getting stuck on the prerequisite's own line (the
    followup_dialogue reversed-order fix)."""
    catalog = load_catalog()
    game_map = make_open_map(5, 5)
    player = make_player(1, 1)
    chief = make_villager(2, 1, dialogue="Let's hear it.", entity_id="village_chief", name="Village Chief")
    warden = make_villager(2, 3, entity_id="wayford_road_warden", name="Road Warden")
    game_map.entities.extend([player, chief, warden])
    quest_log = real_quest_log()
    engine = Engine(game_map, player, "Test Level", catalog=catalog, quest_log=quest_log)

    goblin_warning = quest_log.quests["goblin_warning"]
    chained = quest_log.quests["spreading_the_warning"]
    assert goblin_warning.status == "in_progress"  # starts in_progress, no questgiver needed
    assert chained.status == "not_given"

    engine.talk_to_adjacent()  # delivers the warning to the Chief

    assert goblin_warning.status == "completed"
    assert chained.status == "not_given"  # not granted in the same Talk that completed the prerequisite

    engine.talk_to_adjacent()  # talk to the Chief again

    assert chained.status == "in_progress"
    # this talk's spoken line is still goblin_warning's done-dialogue (spreading_the_warning
    # isn't completed yet, so it doesn't win the followup_dialogue precedence check below);
    # the new quest's given_message is a separate line logged right after it
    assert engine.message_log.messages[-2] == f'Village Chief: "{goblin_warning.target_done_dialogue}"'
    assert engine.message_log.messages[-1] == chained.given_message

    player.x, player.y = 1, 3  # move to be adjacent to the Road Warden instead
    engine.talk_to_adjacent()  # completes spreading_the_warning by talking to its target

    assert chained.status == "completed"
    assert chained.completion_message in engine.message_log.messages

    engine.talk_to_adjacent()  # talk to the Warden again: his own line replays, and it also grants the next chained quest

    next_chained = quest_log.quests["word_from_the_north"]
    assert next_chained.status == "in_progress"  # granted by this same Talk - a third link in the chain
    assert engine.message_log.messages[-2] == f'Road Warden: "{chained.target_done_dialogue}"'
    assert engine.message_log.messages[-1] == next_chained.given_message

    player.x, player.y = 1, 1  # back to the Chief
    engine.talk_to_adjacent()

    # both quests involving the Chief are now completed - the later-defined
    # one (spreading_the_warning) wins over goblin_warning's stale line
    assert engine.message_log.messages[-1] == f'Village Chief: "{chained.questgiver_done_dialogue}"'


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


def test_talk_to_adjacent_completes_a_kill_quest_after_the_target_is_dead():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    prisoner = make_villager(2, 1, dialogue="Made it out too.", entity_id="escaped_prisoner", name="Escaped Prisoner")
    game_map.entities.extend([player, prisoner])
    quest_log = real_quest_log()
    quest_log.quests["kill_the_warden"].status = "in_progress"  # already given
    quest_log.record_entity_killed("warden")  # killed, not yet reported
    engine = Engine(game_map, player, "Test Level", catalog=catalog, quest_log=quest_log)

    engine.talk_to_adjacent()

    quest = quest_log.quests["kill_the_warden"]
    assert quest.status == "completed"
    assert quest.completion_message in engine.message_log.messages
    assert len(player.inventory) == 1
    assert player.inventory[0].name == "Healing Potion"


def test_talk_to_adjacent_completes_an_intimidate_quest_after_the_target_is_hit():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    provisioner = make_villager(2, 1, dialogue="Coin's good here.", entity_id="wayford_provisioner", name="Provisioner")
    game_map.entities.extend([player, provisioner])
    quest_log = real_quest_log()
    quest_log.quests["a_debt_worth_collecting"].status = "in_progress"  # already given
    quest_log.record_entity_intimidated("millhaven_debtor")  # hit, not yet reported
    engine = Engine(game_map, player, "Test Level", catalog=catalog, quest_log=quest_log)

    engine.talk_to_adjacent()

    quest = quest_log.quests["a_debt_worth_collecting"]
    assert quest.status == "completed"
    assert quest.completion_message in engine.message_log.messages


def test_talk_to_adjacent_does_not_complete_an_intimidate_quest_before_the_target_is_hit():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    provisioner = make_villager(2, 1, dialogue="Coin's good here.", entity_id="wayford_provisioner", name="Provisioner")
    game_map.entities.extend([player, provisioner])
    quest_log = real_quest_log()
    quest_log.quests["a_debt_worth_collecting"].status = "in_progress"
    engine = Engine(game_map, player, "Test Level", catalog=catalog, quest_log=quest_log)

    engine.talk_to_adjacent()

    quest = quest_log.quests["a_debt_worth_collecting"]
    assert quest.status == "in_progress"


def test_talk_to_adjacent_does_not_complete_a_kill_quest_before_the_target_is_dead():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    prisoner = make_villager(2, 1, dialogue="Made it out too.", entity_id="escaped_prisoner", name="Escaped Prisoner")
    game_map.entities.extend([player, prisoner])
    quest_log = real_quest_log()
    quest_log.quests["kill_the_warden"].status = "in_progress"
    engine = Engine(game_map, player, "Test Level", catalog=catalog, quest_log=quest_log)

    engine.talk_to_adjacent()

    quest = quest_log.quests["kill_the_warden"]
    assert quest.status == "in_progress"
    assert player.inventory == []


def test_talk_to_adjacent_does_not_complete_a_kill_quest_via_the_wrong_npc():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    shopkeeper = make_villager(2, 1, dialogue="Anything I can get you?", entity_id="shopkeeper", name="Shopkeeper")
    game_map.entities.extend([player, shopkeeper])
    quest_log = real_quest_log()
    quest_log.quests["kill_the_warden"].status = "in_progress"
    quest_log.record_entity_killed("warden")
    engine = Engine(game_map, player, "Test Level", catalog=catalog, quest_log=quest_log)

    engine.talk_to_adjacent()

    quest = quest_log.quests["kill_the_warden"]
    assert quest.status == "in_progress"


def test_talk_to_adjacent_completes_a_dungeon_arrival_quest_after_the_dungeon_is_visited():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    caravan_master = make_villager(2, 1, dialogue="Off to Millhaven?", entity_id="wayford_caravan_master", name="Caravan Master")
    game_map.entities.extend([player, caravan_master])
    quest_log = real_quest_log()
    quest_log.quests["word_down_the_road"].status = "in_progress"  # already given
    quest_log.record_dungeon_arrival("millhaven")  # visited, not yet reported
    engine = Engine(game_map, player, "Test Level", catalog=catalog, quest_log=quest_log)

    engine.talk_to_adjacent()

    quest = quest_log.quests["word_down_the_road"]
    assert quest.status == "completed"
    assert quest.completion_message in engine.message_log.messages


def test_talk_to_adjacent_does_not_complete_a_dungeon_arrival_quest_before_the_dungeon_is_visited():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    caravan_master = make_villager(2, 1, dialogue="Off to Millhaven?", entity_id="wayford_caravan_master", name="Caravan Master")
    game_map.entities.extend([player, caravan_master])
    quest_log = real_quest_log()
    quest_log.quests["word_down_the_road"].status = "in_progress"
    engine = Engine(game_map, player, "Test Level", catalog=catalog, quest_log=quest_log)

    engine.talk_to_adjacent()

    quest = quest_log.quests["word_down_the_road"]
    assert quest.status == "in_progress"


def test_talk_to_adjacent_does_not_complete_a_dungeon_arrival_quest_via_the_wrong_npc():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    shopkeeper = make_villager(2, 1, dialogue="Anything I can get you?", entity_id="shopkeeper", name="Shopkeeper")
    game_map.entities.extend([player, shopkeeper])
    quest_log = real_quest_log()
    quest_log.quests["word_down_the_road"].status = "in_progress"
    quest_log.record_dungeon_arrival("millhaven")
    engine = Engine(game_map, player, "Test Level", catalog=catalog, quest_log=quest_log)

    engine.talk_to_adjacent()

    quest = quest_log.quests["word_down_the_road"]
    assert quest.status == "in_progress"


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


def test_complete_quest_with_a_gold_reward_adds_to_the_player_gold_stat():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    player.gold = 10
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")
    quest = Quest(
        id="gold_test", name="Gold Test", description="",
        completion_message="Done.", reward_gold_amount=30,
    )

    engine.complete_quest(quest)

    assert "Done." in engine.message_log.messages
    assert "30 gold" in engine.message_log.messages[-1]
    assert player.gold == 40
    assert player.inventory == []  # gold never enters inventory, same as a map pickup


def test_complete_quest_with_no_gold_reward_leaves_gold_untouched():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    player.gold = 10
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")
    quest = Quest(
        id="no_gold_reward", name="No Gold Reward", description="",
        completion_message="Done.", reward_gold_amount=None,
    )

    engine.complete_quest(quest)

    assert player.gold == 10


def test_complete_quest_with_a_shop_discount_reward_logs_the_discount_message():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    quest_log = QuestLog()
    engine = Engine(game_map, player, "Test Level", catalog=catalog, quest_log=quest_log)
    quest = Quest(
        id="discount_test", name="Discount Test", description="",
        completion_message="Done.", reward_shop_discount_pct=0.2,
        reward_shop_discount_entity_id="shopkeeper",
    )
    quest_log.quests[quest.id] = quest

    engine.complete_quest(quest)

    assert "Done." in engine.message_log.messages
    assert "20% discount" in engine.message_log.messages[-1]
    assert "Shopkeeper" in engine.message_log.messages[-1]  # names the specific shop, not every shop
    assert player.inventory == []
    assert player.gold == 0


def test_complete_quest_with_a_shop_discount_reward_and_no_catalog_still_logs_a_message():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    quest_log = QuestLog()
    engine = Engine(game_map, player, "Test Level", quest_log=quest_log)
    quest = Quest(
        id="discount_test", name="Discount Test", description="",
        completion_message="Done.", reward_shop_discount_pct=0.2,
        reward_shop_discount_entity_id="shopkeeper",
    )
    quest_log.quests[quest.id] = quest

    engine.complete_quest(quest)

    assert "20% discount" in engine.message_log.messages[-1]


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


def test_attacking_a_villager_records_it_for_an_intimidate_quest():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    villager = make_villager(2, 1, entity_id="millhaven_debtor")
    game_map.entities.extend([player, villager])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(BumpAction(1, 0))

    assert "millhaven_debtor" in engine.quest_log.intimidated_entity_ids


def test_attacking_a_hostile_monster_does_not_record_an_intimidation():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    monster = make_monster(2, 1, hp=5, defense=0, ai=None)
    monster.entity_id = "rat"
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(BumpAction(1, 0))

    assert engine.quest_log.intimidated_entity_ids == set()


def test_attacking_a_villager_arms_a_seven_day_hostility_expiry():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    villager = make_villager(2, 1)
    game_map.entities.extend([player, villager])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(BumpAction(1, 0))

    assert game_map.hostility_expires_at == engine.clock.plus_hours(7 * 24)
    assert game_map.player_murdered_peaceful_npc is False


# --- guard hostility cooldown/permanence (engine/game_map.py) ---


def test_guards_hostile_is_false_before_any_provocation():
    game_map = make_open_map(3, 3)
    clock = GameClock()

    assert game_map.guards_hostile(clock) is False


def test_guards_hostile_is_true_immediately_after_a_provocation():
    game_map = make_open_map(3, 3)
    clock = GameClock()

    game_map.trigger_guard_hostility(clock)

    assert game_map.guards_hostile(clock) is True


def test_guards_hostile_is_true_just_before_the_seven_day_cooldown_elapses():
    game_map = make_open_map(3, 3)
    clock = GameClock()
    game_map.trigger_guard_hostility(clock)

    later = GameClock(*clock.plus_hours(7 * 24 - 1))

    assert game_map.guards_hostile(later) is True


def test_guards_hostile_is_false_once_the_seven_day_cooldown_elapses():
    game_map = make_open_map(3, 3)
    clock = GameClock()
    game_map.trigger_guard_hostility(clock)

    later = GameClock(*clock.plus_hours(7 * 24))

    assert game_map.guards_hostile(later) is False


def test_trigger_guard_hostility_resets_the_cooldown_on_a_second_provocation():
    """A second provocation while the first cooldown is still running
    restarts the countdown from that later moment rather than continuing
    the original one - same convention as QuestLog.arm_encounter."""
    game_map = make_open_map(3, 3)
    clock = GameClock()
    game_map.trigger_guard_hostility(clock)  # expires at clock + 7 days

    five_days_later = GameClock(*clock.plus_hours(5 * 24))
    game_map.trigger_guard_hostility(five_days_later)  # reset to expire at clock + 12 days

    eight_days_after_the_first_hit = GameClock(*clock.plus_hours(8 * 24))
    # the original 7-day cooldown would have already lapsed by now, but the
    # second provocation reset it to expire 5 days later than that instead
    assert game_map.guards_hostile(eight_days_after_the_first_hit) is True

    twelve_days_after_the_first_hit = GameClock(*clock.plus_hours(12 * 24))
    assert game_map.guards_hostile(twelve_days_after_the_first_hit) is False


def test_mark_peaceful_npc_murdered_makes_hostility_never_expire():
    game_map = make_open_map(3, 3)
    clock = GameClock()
    game_map.trigger_guard_hostility(clock)
    game_map.mark_peaceful_npc_murdered()

    far_future = GameClock(*clock.plus_hours(365 * 24))

    assert game_map.guards_hostile(far_future) is True


def test_mark_peaceful_npc_murdered_is_a_no_op_before_any_provocation():
    """guards_hostile's own player_attacked_peaceful_npc gate still applies
    even once murdered - a map that's never actually been provoked has no
    hostile guards to begin with, regardless of this flag."""
    game_map = make_open_map(3, 3)
    game_map.mark_peaceful_npc_murdered()

    assert game_map.guards_hostile(GameClock()) is False


def test_on_entity_death_of_a_villager_makes_this_maps_hostility_permanent():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    villager = make_villager(2, 1)
    game_map.entities.extend([player, villager])
    engine = Engine(game_map, player, "Test Level")
    game_map.trigger_guard_hostility(engine.clock)

    engine.on_entity_death(villager)

    assert game_map.player_murdered_peaceful_npc is True
    far_future = GameClock(*engine.clock.plus_hours(365 * 24))
    assert game_map.guards_hostile(far_future) is True


def test_on_entity_death_of_a_town_guard_makes_this_maps_hostility_permanent():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    guard = make_monster(2, 1, hp=14, attack=5, ai="town_guard")
    game_map.entities.extend([player, guard])
    engine = Engine(game_map, player, "Test Level")

    engine.on_entity_death(guard)

    assert game_map.player_murdered_peaceful_npc is True


def test_on_entity_death_of_a_hostile_monster_does_not_affect_hostility_permanence():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    monster = make_monster(2, 1, hp=5, attack=4, ai="hostile_basic")
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.on_entity_death(monster)

    assert game_map.player_murdered_peaceful_npc is False


def test_town_guard_wanders_again_once_the_hostility_cooldown_expires():
    game_map = make_open_map(5, 3)
    player = make_player(0, 1, hp=30, defense=0)
    guard = make_monster(3, 1, hp=14, attack=5, ai="town_guard")
    game_map.entities.extend([player, guard])
    clock = GameClock()
    engine = Engine(game_map, player, "Test Level", clock=clock)
    game_map.trigger_guard_hostility(clock)
    clock.year, clock.day, clock.hour = clock.plus_hours(7 * 24)  # cooldown just expired

    engine.process_turn(WaitAction())

    assert player.fighter.hp == 30  # never attacked - reverted to wandering/peaceful


def test_town_guard_stays_hostile_past_the_cooldown_if_a_villager_was_killed():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, defense=0)
    guard = make_monster(2, 1, hp=14, attack=5, ai="town_guard")
    villager = make_villager(0, 0)
    game_map.entities.extend([player, guard, villager])
    clock = GameClock()
    engine = Engine(game_map, player, "Test Level", clock=clock)
    game_map.trigger_guard_hostility(clock)
    engine.on_entity_death(villager)
    clock.year, clock.day, clock.hour = clock.plus_hours(365 * 24)

    engine.process_turn(WaitAction())

    assert player.fighter.hp == 30 - 5  # still hostile long after any cooldown would have lapsed


def test_would_attack_peaceful_npc_returns_the_entity_for_a_town_guard_once_the_cooldown_expires():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    guard = make_monster(2, 1, hp=14, attack=5, ai="town_guard")
    game_map.entities.extend([player, guard])
    clock = GameClock()
    engine = Engine(game_map, player, "Test Level", clock=clock)
    game_map.trigger_guard_hostility(clock)
    clock.year, clock.day, clock.hour = clock.plus_hours(7 * 24)

    assert engine.would_attack_peaceful_npc(1, 0) is guard


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
    game_map.entities.extend([player, guard])
    engine = Engine(game_map, player, "Test Level")
    game_map.trigger_guard_hostility(engine.clock)

    engine.talk_to_adjacent()

    assert "There's no one here to talk to." in engine.message_log.messages
    assert 'Town Guard: "Keep the peace."' not in engine.message_log.messages


def test_talk_to_adjacent_villager_unaffected_by_the_town_wide_hostility_flag():
    """Confirms the guard/villager asymmetry is intentional: guards_hostile
    only governs town_guard entities - a villager stays talkable (as long
    as they're personally undamaged) even after it trips."""
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    villager = make_villager(2, 1, dialogue="Hello.")
    game_map.entities.extend([player, villager])
    engine = Engine(game_map, player, "Test Level")
    game_map.trigger_guard_hostility(engine.clock)

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
    shopkeeper = make_shopkeeper(2, 1)
    game_map.entities.extend([player, shopkeeper])
    engine = Engine(game_map, player, "Test Level", catalog=catalog)

    assert engine.shop_price("healing_potion", shopkeeper) == 25


def test_shop_price_reflects_the_fungus_quests_discount_once_completed():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    shopkeeper = make_shopkeeper(2, 1)
    game_map.entities.extend([player, shopkeeper])
    quest_log = real_quest_log()
    quest_log.quests["fetch_fungus"].status = "completed"
    engine = Engine(game_map, player, "Test Level", catalog=catalog, quest_log=quest_log)

    assert engine.shop_price("healing_potion", shopkeeper) == 20


def test_shop_price_ignores_the_fungus_quests_discount_at_a_different_shopkeeper():
    """The actual bug this fix closes: completing Millhaven's discount quest
    used to discount every shop in the game, including one it was never
    meant to touch. Now reward_shop_discount_entity_id scopes the discount
    to the one shopkeeper that earned it."""
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    other_shopkeeper = make_villager(
        2, 1, entity_id="wayford_provisioner", name="Provisioner",
        shop_inventory=["healing_potion"],
    )
    game_map.entities.extend([player, other_shopkeeper])
    quest_log = real_quest_log()
    quest_log.quests["fetch_fungus"].status = "completed"  # scoped to "shopkeeper", not this one
    engine = Engine(game_map, player, "Test Level", catalog=catalog, quest_log=quest_log)

    assert engine.shop_price("healing_potion", other_shopkeeper) == 25


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


# --- trainer / learn_perk ---


def make_trainer(x: int, y: int, trainer_perks=("toughness_1",)) -> Entity:
    return make_villager(
        x, y, entity_id="trainer", name="Trainer", trainer_perks=list(trainer_perks),
    )


def test_adjacent_trainer_finds_an_npc_with_trainer_perks():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.extend([player, make_trainer(2, 1)])
    engine = Engine(game_map, player, "Test Level")

    assert engine.adjacent_trainer() is not None
    assert engine.adjacent_trainer().trainer_perks == ["toughness_1"]


def test_adjacent_trainer_ignores_a_plain_villager_with_no_trainer_perks():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    villager = make_villager(2, 1, dialogue="Hello.", entity_id="villager")
    game_map.entities.extend([player, villager])
    engine = Engine(game_map, player, "Test Level")

    assert engine.adjacent_trainer() is None


def test_adjacent_trainer_none_when_nothing_nearby():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")

    assert engine.adjacent_trainer() is None


def test_learn_perk_with_enough_xp_deducts_xp_and_applies_max_hp_bonus():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30)
    player.xp = 40
    game_map.entities.extend([player, make_trainer(2, 1)])
    engine = Engine(game_map, player, "Test Level", catalog=catalog)

    message = engine.learn_perk("toughness_1")

    assert player.xp == 0
    assert player.fighter.max_hp == 35
    assert player.fighter.hp == 35  # instant full benefit
    assert "toughness_1" in player.learned_perk_ids
    assert message == "You learn Toughness."
    assert message in engine.message_log.messages


def test_learn_perk_applies_attack_bonus():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, attack=5)
    player.xp = 45
    game_map.entities.extend([player, make_trainer(2, 1, trainer_perks=["weapon_training_1"])])
    engine = Engine(game_map, player, "Test Level", catalog=catalog)

    engine.learn_perk("weapon_training_1")

    assert player.fighter.attack == 7
    assert player.effective_attack == 7


def test_learn_perk_applies_defense_bonus():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, defense=1)
    player.xp = 45
    game_map.entities.extend([player, make_trainer(2, 1, trainer_perks=["shield_training_1"])])
    engine = Engine(game_map, player, "Test Level", catalog=catalog)

    engine.learn_perk("shield_training_1")

    assert player.fighter.defense == 3
    assert player.effective_defense == 3


def test_learn_perk_applies_ranged_attack_bonus():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, attack=5)
    player.xp = 40
    game_map.entities.extend([player, make_trainer(2, 1, trainer_perks=["marksman_training_1"])])
    engine = Engine(game_map, player, "Test Level", catalog=catalog)

    engine.learn_perk("marksman_training_1")

    assert player.fighter.perk_ranged_attack_bonus == 2
    assert player.effective_ranged_attack == 7


def test_learn_perk_without_enough_xp_does_nothing():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    player.xp = 10
    game_map.entities.extend([player, make_trainer(2, 1)])
    engine = Engine(game_map, player, "Test Level", catalog=catalog)

    message = engine.learn_perk("toughness_1")

    assert message == "You can't afford that."
    assert player.xp == 10
    assert player.learned_perk_ids == set()
    assert player.fighter.max_hp == 30


def test_learn_perk_a_second_time_rejects_an_already_learned_perk():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    player.xp = 100
    game_map.entities.extend([player, make_trainer(2, 1)])
    engine = Engine(game_map, player, "Test Level", catalog=catalog)

    first = engine.learn_perk("toughness_1")
    second = engine.learn_perk("toughness_1")

    assert first == "You learn Toughness."
    assert second == "You already know that."
    assert player.xp == 60  # only charged once
    assert player.fighter.max_hp == 35  # not double-applied


# --- perk tiers (requires_perk_id) ---


def test_learn_perk_rejects_a_tiered_perk_without_the_prerequisite():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30)
    player.xp = 100
    game_map.entities.extend([player, make_trainer(2, 1, trainer_perks=["toughness_1", "toughness_2"])])
    engine = Engine(game_map, player, "Test Level", catalog=catalog)

    message = engine.learn_perk("toughness_2")

    assert message == "You need to learn Toughness first."
    assert "toughness_2" not in player.learned_perk_ids
    assert player.xp == 100  # not charged
    assert player.fighter.max_hp == 30  # unchanged


def test_learn_perk_allows_a_tiered_perk_once_the_prerequisite_is_learned():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30)
    player.xp = 200
    game_map.entities.extend([player, make_trainer(2, 1, trainer_perks=["toughness_1", "toughness_2"])])
    engine = Engine(game_map, player, "Test Level", catalog=catalog)

    engine.learn_perk("toughness_1")
    message = engine.learn_perk("toughness_2")

    assert message == "You learn Greater Toughness."
    assert "toughness_2" in player.learned_perk_ids
    assert player.fighter.max_hp == 30 + 5 + 8  # both tiers stack


def test_learn_perk_tier_prerequisite_can_come_from_a_different_trainer():
    """The prerequisite check is purely learned_perk_ids membership, not
    "taught by the same trainer" - once toughness_1 is learned anywhere,
    it satisfies toughness_2's requirement everywhere."""
    catalog = load_catalog()
    game_map = make_open_map(6, 3)
    player = make_player(1, 1, hp=30)
    player.xp = 200
    trainer_a = make_trainer(0, 1, trainer_perks=["toughness_1"])
    trainer_b = make_trainer(4, 1, trainer_perks=["toughness_2"])
    game_map.entities.extend([player, trainer_a, trainer_b])
    engine = Engine(game_map, player, "Test Level", catalog=catalog)

    engine.learn_perk("toughness_1")
    player.x = 3  # move adjacent to trainer_b only - trainer_a now out of range
    message = engine.learn_perk("toughness_2")

    assert message == "You learn Greater Toughness."
    assert "toughness_2" in player.learned_perk_ids


def test_learn_perk_rejects_a_catalog_perk_not_taught_by_this_trainer():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    player.xp = 100
    game_map.entities.extend([player, make_trainer(2, 1, trainer_perks=["toughness_1"])])
    engine = Engine(game_map, player, "Test Level", catalog=catalog)

    message = engine.learn_perk("weapon_training_1")

    assert message == "The trainer is unavailable."
    assert player.xp == 100
    assert player.learned_perk_ids == set()


def test_learn_perk_with_no_trainer_adjacent_is_unavailable():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    player.xp = 100
    game_map.entities.append(player)  # no trainer anywhere
    engine = Engine(game_map, player, "Test Level", catalog=catalog)

    message = engine.learn_perk("toughness_1")

    assert message == "The trainer is unavailable."
    assert player.xp == 100


def test_learn_perk_with_no_catalog_does_not_crash():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    player.xp = 100
    game_map.entities.extend([player, make_trainer(2, 1)])
    engine = Engine(game_map, player, "Test Level")  # catalog defaults to None

    message = engine.learn_perk("toughness_1")  # must not raise

    assert message == "The trainer is unavailable."
    assert player.xp == 100


def test_learn_perk_never_advances_the_clock_or_processes_enemy_turns():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    player.xp = 100
    rat = make_monster(0, 0, ai="hostile_basic")
    game_map.entities.extend([player, rat, make_trainer(2, 1)])
    clock = GameClock()
    engine = Engine(game_map, player, "The Overworld", is_overworld=True, catalog=catalog, clock=clock)
    rat_start = (rat.x, rat.y)

    engine.learn_perk("toughness_1")

    assert engine.clock == GameClock()  # untouched
    assert (rat.x, rat.y) == rat_start  # no enemy turn was processed


# --- passive rate-bonus perks (crit_chance_bonus/dodge_chance_bonus) ---


def test_learn_perk_applies_crit_chance_bonus():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    player.xp = 45
    game_map.entities.extend([player, make_trainer(2, 1, trainer_perks=["steady_aim"])])
    engine = Engine(game_map, player, "Test Level", catalog=catalog)

    engine.learn_perk("steady_aim")

    assert player.fighter.perk_crit_chance_bonus == 0.05


def test_learn_perk_applies_dodge_chance_bonus():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    player.xp = 45
    game_map.entities.extend([player, make_trainer(2, 1, trainer_perks=["light_feet"])])
    engine = Engine(game_map, player, "Test Level", catalog=catalog)

    engine.learn_perk("light_feet")

    assert player.fighter.perk_dodge_chance_bonus == 0.05


def test_perk_crit_chance_bonus_triggers_a_crit_the_base_rate_would_have_missed(monkeypatch):
    monkeypatch.setattr(engine.combat, "COMBAT_VARIANCE_ENABLED", True)
    import math

    # Dodge roll first (must not beat DODGE_CHANCE=0.10), then crit roll:
    # 0.3 is above the base CRIT_CHANCE=0.10 but below the perk-boosted
    # 0.60 - a crit here can only be the perk's doing.
    monkeypatch.setattr(random, "random", iter([0.99, 0.3]).__next__)
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, attack=5, defense=1)
    player.fighter.perk_crit_chance_bonus = 0.5
    monster = make_monster(2, 1, hp=20, attack=0, defense=0, ai=None)
    game_map.entities.extend([player, monster])
    engine_ = Engine(game_map, player, "Test Level")

    engine_.process_turn(BumpAction(1, 0))

    base_damage = player.effective_attack - monster.effective_defense
    expected_crit_damage = math.ceil(base_damage * engine.combat.CRIT_MULTIPLIER)
    assert 20 - monster.fighter.hp == expected_crit_damage


def test_perk_dodge_chance_bonus_triggers_a_dodge_the_base_rate_would_have_missed(monkeypatch):
    monkeypatch.setattr(engine.combat, "COMBAT_VARIANCE_ENABLED", True)
    # 0.3 is above the base DODGE_CHANCE=0.10 but below the perk-boosted
    # 0.60 - a dodge here can only be the perk's doing.
    monkeypatch.setattr(random, "random", lambda: 0.3)
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30, defense=0)
    player.fighter.perk_dodge_chance_bonus = 0.5
    monster = make_monster(2, 1, hp=5, attack=10, ai=None)
    game_map.entities.extend([player, monster])
    engine_ = Engine(game_map, player, "Test Level")

    from engine.combat import resolve_attack
    resolve_attack(engine_, attacker=monster, defender=player)

    assert player.fighter.hp == 30  # fully dodged
    assert "dodges" in engine_.message_log.messages[-1]


# --- active-skill perks (Engine.use_skill / UseSkillAction) ---


def test_use_skill_heal_restores_hp_and_sets_cooldown():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30)
    player.fighter.hp = 10
    player.learned_perk_ids.add("second_wind")
    game_map.entities.append(player)
    engine_ = Engine(game_map, player, "Test Level", catalog=catalog)

    message = engine_.use_skill(player, "second_wind")

    assert player.fighter.hp == 25  # 10 + ceil(30 * 0.5) = 25
    assert player.skill_cooldowns["second_wind"] == 24
    assert message == "You use Second Wind and recover 15 HP."
    assert message in engine_.message_log.messages


def test_use_skill_heal_caps_at_max_hp():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30)
    player.fighter.hp = 25  # only 5 short of max - less than the skill would normally heal
    player.learned_perk_ids.add("second_wind")
    game_map.entities.append(player)
    engine_ = Engine(game_map, player, "Test Level", catalog=catalog)

    engine_.use_skill(player, "second_wind")

    assert player.fighter.hp == 30  # capped, not 40


def test_use_skill_without_learning_it_first_does_nothing():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30)
    player.fighter.hp = 10
    game_map.entities.append(player)
    engine_ = Engine(game_map, player, "Test Level", catalog=catalog)

    message = engine_.use_skill(player, "second_wind")

    assert player.fighter.hp == 10  # unchanged
    assert message == "You don't know that skill."


def test_use_skill_on_cooldown_does_nothing():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30)
    player.fighter.hp = 10
    player.learned_perk_ids.add("second_wind")
    player.skill_cooldowns["second_wind"] = 5
    game_map.entities.append(player)
    engine_ = Engine(game_map, player, "Test Level", catalog=catalog)

    message = engine_.use_skill(player, "second_wind")

    assert player.fighter.hp == 10  # unchanged
    assert message == "Second Wind is still on cooldown."


def test_use_skill_with_unknown_perk_id_does_nothing():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    engine_ = Engine(game_map, player, "Test Level", catalog=catalog)

    assert engine_.use_skill(player, "nonexistent_skill") == "That skill doesn't exist."


def test_use_skill_with_no_catalog_does_not_crash():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    engine_ = Engine(game_map, player, "Test Level")  # no catalog

    assert engine_.use_skill(player, "second_wind") == "That skill doesn't exist."


def test_use_skill_rejects_a_passive_perk():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    player.learned_perk_ids.add("toughness_1")  # learned, but not an active skill
    game_map.entities.append(player)
    engine_ = Engine(game_map, player, "Test Level", catalog=catalog)

    assert engine_.use_skill(player, "toughness_1") == "You don't know that skill."


def test_use_skill_aoe_damage_hits_all_adjacent_hostile_entities():
    catalog = load_catalog()
    game_map = make_open_map(5, 5)
    player = make_player(2, 2, defense=0)
    player.learned_perk_ids.add("ground_pound")
    monster_n = make_monster(2, 1, hp=10, defense=0, ai=None)
    monster_e = make_monster(3, 2, hp=10, defense=0, ai=None)
    far_monster = make_monster(4, 4, hp=10, defense=0, ai=None)  # not adjacent
    game_map.entities.extend([player, monster_n, monster_e, far_monster])
    engine_ = Engine(game_map, player, "Test Level", catalog=catalog)

    engine_.use_skill(player, "ground_pound")

    assert monster_n.fighter.hp == 10 - 4  # skill_aoe_damage=4, 0 defense
    assert monster_e.fighter.hp == 10 - 4
    assert far_monster.fighter.hp == 10  # untouched, not adjacent
    assert player.skill_cooldowns["ground_pound"] == 5


def test_use_skill_aoe_damage_ignores_peaceful_npcs():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, defense=0)
    player.learned_perk_ids.add("ground_pound")
    villager = make_villager(2, 1)
    game_map.entities.extend([player, villager])
    engine_ = Engine(game_map, player, "Test Level", catalog=catalog)

    engine_.use_skill(player, "ground_pound")

    assert villager.fighter.hp == villager.fighter.max_hp  # untouched


def test_use_skill_aoe_damage_can_kill_an_adjacent_monster():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, defense=0)
    player.learned_perk_ids.add("ground_pound")
    monster = make_monster(2, 1, hp=1, defense=0, ai=None)
    monster.xp_reward = 5
    game_map.entities.extend([player, monster])
    engine_ = Engine(game_map, player, "Test Level", catalog=catalog)

    engine_.use_skill(player, "ground_pound")

    assert monster not in game_map.entities
    assert player.xp == 5


def test_use_skill_action_triggers_the_skill_through_process_turn():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30)
    player.fighter.hp = 10
    player.learned_perk_ids.add("second_wind")
    game_map.entities.append(player)
    engine_ = Engine(game_map, player, "Test Level", catalog=catalog)

    engine_.process_turn(UseSkillAction("second_wind"))

    assert player.fighter.hp == 25


def test_ground_pound_cooldown_ticks_down_each_turn_and_expires():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    player.learned_perk_ids.add("ground_pound")
    game_map.entities.append(player)
    engine_ = Engine(game_map, player, "Test Level", catalog=catalog)

    engine_.use_skill(player, "ground_pound")
    assert player.skill_cooldowns["ground_pound"] == 5

    for _ in range(4):
        engine_.process_turn(WaitAction())
    assert player.skill_cooldowns["ground_pound"] == 1

    engine_.process_turn(WaitAction())
    assert "ground_pound" not in player.skill_cooldowns  # expired, deleted


def test_second_wind_cooldown_does_not_tick_in_a_dungeon():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    player.learned_perk_ids.add("second_wind")
    game_map.entities.append(player)
    engine_ = Engine(game_map, player, "Test Level", catalog=catalog)  # is_overworld=False

    engine_.use_skill(player, "second_wind")
    assert player.skill_cooldowns["second_wind"] == 24

    for _ in range(5):
        engine_.process_turn(WaitAction())

    assert player.skill_cooldowns["second_wind"] == 24  # unchanged - never left to rest


def test_second_wind_cooldown_ticks_down_only_on_overworld_turns():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    player.learned_perk_ids.add("second_wind")
    game_map.entities.append(player)
    clock = GameClock()
    engine_ = Engine(game_map, player, "The Overworld", is_overworld=True, catalog=catalog, clock=clock)

    engine_.use_skill(player, "second_wind")
    assert player.skill_cooldowns["second_wind"] == 24

    engine_.process_turn(WaitAction())

    assert player.skill_cooldowns["second_wind"] == 23


def test_second_wind_cooldown_expires_after_24_overworld_hours():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    player.learned_perk_ids.add("second_wind")
    game_map.entities.append(player)
    clock = GameClock()
    engine_ = Engine(game_map, player, "The Overworld", is_overworld=True, catalog=catalog, clock=clock)

    engine_.use_skill(player, "second_wind")
    for _ in range(24):
        engine_.process_turn(WaitAction())

    assert "second_wind" not in player.skill_cooldowns


# --- XP awards (kills, quests, landmark discovery) ---


def test_on_entity_death_awards_xp_reward_on_a_monster_kill():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    monster = make_monster(2, 1, hp=1, ai="hostile_basic")
    monster.xp_reward = 5
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.on_entity_death(monster)

    assert player.xp == 5
    assert "You gain 5 XP (kill)." in engine.message_log.messages


def test_on_entity_death_with_zero_xp_reward_awards_nothing():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    monster = make_monster(2, 1, hp=1, ai="hostile_basic")  # xp_reward defaults to 0
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.on_entity_death(monster)

    assert player.xp == 0
    assert not any("XP" in m for m in engine.message_log.messages)


def test_complete_quest_awards_reward_xp_amount():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")
    quest = Quest(
        id="q1", name="Test Quest", description="", completion_message="Done!",
        failure_message="", reward_xp_amount=15,
    )

    engine.complete_quest(quest)

    assert player.xp == 15
    assert "You gain 15 XP (quest)." in engine.message_log.messages


def test_complete_quest_with_no_reward_xp_amount_leaves_xp_untouched():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")
    quest = Quest(
        id="q1", name="Test Quest", description="", completion_message="Done!",
        failure_message="",
    )

    engine.complete_quest(quest)

    assert player.xp == 0


# --- Engine.sound_events - a mailbox to main.py's SoundManager, same
# append/drain lifecycle as melee_attack_events/ranged_attack_events (see
# e.g. test_melee_attack_records_a_melee_attack_event_at_the_defender
# above). Engine never reads these back; only that the right semantic key
# is queued at the right moment is under test here.

def test_melee_attack_queues_a_melee_hit_sound():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    monster = make_monster(2, 1, hp=6, attack=2, ai=None)
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(BumpAction(1, 0))

    assert "melee_hit" in engine.sound_events


def test_ranged_attack_queues_a_ranged_hit_sound():
    game_map = make_open_map(5, 3)
    player = make_player(1, 1, attack=5)
    player.equipped_ranged_weapon = make_ranged_weapon(0, 0, ranged_attack_bonus=3)
    player.inventory.append(make_ammo(0, 0, quantity=5))
    monster = make_monster(3, 1, hp=20, defense=0, ai=None)
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(FireAction(3, 1))

    assert "ranged_hit" in engine.sound_events


def test_sound_events_do_not_persist_across_process_turn_calls():
    """main.py drains and clears this list every turn, same as
    melee_attack_events/ranged_attack_events - a stale key from a prior
    turn must never leak into a turn where nothing happened."""
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    monster = make_monster(2, 1, hp=6, attack=2, ai=None)
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(BumpAction(1, 0))
    engine.sound_events = []  # main.py's drain, simulated
    engine.process_turn(WaitAction())

    assert engine.sound_events == []


def test_monster_death_queues_an_entity_death_sound():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, attack=99)
    monster = make_monster(2, 1, hp=1, defense=0, ai=None)
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(BumpAction(1, 0))

    assert "entity_death" in engine.sound_events
    assert "player_death" not in engine.sound_events


def test_player_death_queues_a_player_death_sound():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=1, defense=0)
    monster = make_monster(2, 1, hp=5, attack=99, ai="hostile_basic")
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(WaitAction())

    assert "player_death" in engine.sound_events
    assert "entity_death" not in engine.sound_events


def test_generic_item_pickup_queues_a_pickup_item_sound():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    scroll = Entity(
        1, 1, "?", (200, 200, 200), "Mysterious Scroll",
        render_priority=RENDER_PRIORITY_ITEM, item=ItemEffect(),
    )
    game_map.entities.extend([player, scroll])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(PickupAction())

    assert engine.sound_events == ["pickup_item"]


def test_weapon_pickup_queues_a_pickup_item_sound():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, attack=5)
    weapon = make_weapon(1, 1, attack_bonus=2, name="Rusty Dagger")
    game_map.entities.extend([player, weapon])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(PickupAction())

    assert engine.sound_events == ["pickup_item"]


def test_ammo_pickup_queues_a_pickup_item_sound():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    ammo = make_ammo(1, 1, quantity=5)
    game_map.entities.extend([player, ammo])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(PickupAction())

    assert engine.sound_events == ["pickup_item"]


def test_gold_pickup_queues_a_pickup_gold_sound():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    gold = make_gold(1, 1, gold_amount=10)
    game_map.entities.extend([player, gold])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(PickupAction())

    assert engine.sound_events == ["pickup_gold"]


def test_a_weapon_not_better_than_the_current_one_queues_no_sound():
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, attack=5)
    player.equipped_weapon = make_weapon(0, 0, attack_bonus=4, name="Iron Sword")
    worse_weapon = make_weapon(1, 1, attack_bonus=2, name="Rusty Dagger")
    game_map.entities.extend([player, worse_weapon])
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(PickupAction())

    assert engine.sound_events == []


def test_door_unlock_queues_a_door_unlock_sound():
    game_map = make_open_map(3, 3)
    game_map.kinds[2, 1] = "door"
    game_map.walkable[2, 1] = False
    game_map.transparent[2, 1] = False
    game_map.locked_doors[(2, 1)] = "rusty_key"
    player = make_player(1, 1)
    player.inventory.append(make_key(0, 0))
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(BumpAction(1, 0))

    assert "door_unlock" in engine.sound_events


def test_locked_door_with_no_matching_key_queues_no_sound():
    game_map = make_open_map(3, 3)
    game_map.kinds[2, 1] = "door"
    game_map.walkable[2, 1] = False
    game_map.transparent[2, 1] = False
    game_map.locked_doors[(2, 1)] = "rusty_key"
    player = make_player(1, 1)
    game_map.entities.append(player)
    engine = Engine(game_map, player, "Test Level")

    engine.process_turn(BumpAction(1, 0))

    assert engine.sound_events == []


def test_buy_from_shop_queues_a_shop_buy_sound():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    player.gold = 30
    game_map.entities.extend([player, make_shopkeeper(2, 1)])
    engine = Engine(game_map, player, "Test Level", catalog=catalog)

    engine.buy_from_shop("healing_potion")

    assert engine.sound_events == ["shop_buy"]


def test_buy_from_shop_without_enough_gold_queues_no_sound():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.extend([player, make_shopkeeper(2, 1)])
    engine = Engine(game_map, player, "Test Level", catalog=catalog)

    engine.buy_from_shop("healing_potion")

    assert engine.sound_events == []


def test_learn_perk_queues_a_perk_learn_sound():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1, hp=30)
    player.xp = 40
    game_map.entities.extend([player, make_trainer(2, 1)])
    engine = Engine(game_map, player, "Test Level", catalog=catalog)

    engine.learn_perk("toughness_1")

    assert engine.sound_events == ["perk_learn"]


def test_learn_perk_without_enough_xp_queues_no_sound():
    catalog = load_catalog()
    game_map = make_open_map(3, 3)
    player = make_player(1, 1)
    game_map.entities.extend([player, make_trainer(2, 1)])
    engine = Engine(game_map, player, "Test Level", catalog=catalog)

    engine.learn_perk("toughness_1")

    assert engine.sound_events == []
