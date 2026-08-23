"""Tests for main.py's action-dispatch glue - the interface between raw input
Actions and Engine/game-loop control. Pulled out into dispatch_action() so this
logic is testable without a real SDL window/event loop.

Regression coverage for a real bug: Escape only worked while game_state was
"playing", because Engine.process_turn no-ops once the run has ended, silently
swallowing the SystemExit that EscapeAction.perform() would otherwise raise."""

from pathlib import Path

from content.loader import load_catalog, load_dungeon_registry, load_levels, load_overworld
from content.schema import EncounterDef
from engine.actions import BumpAction, EscapeAction, FireAction, RestartAction, WaitAction
from engine.clock import HOURS_PER_DAY, GameClock
from engine.engine import Engine
from engine.entity import (
    RENDER_PRIORITY_ACTOR,
    RENDER_PRIORITY_ITEM,
    RENDER_PRIORITY_PLAYER,
    Entity,
    Fighter,
    ItemEffect,
)
from engine.game_map import GameMap, build_game_map
from engine.quest import Quest, QuestLog
from main import DUNGEONS_DIR, OVERWORLD_KEY, OVERWORLD_LEVEL_PATH, dispatch_action, fire_mode_gate, resolve_transition, shop_gate

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LEVELS_DIR = DATA_DIR / "dungeons" / "forgotten_ruins" / "levels"


def make_engine() -> Engine:
    catalog = load_catalog()
    levels = load_levels(LEVELS_DIR, catalog)
    level_01 = levels["level_01"]
    game_map, player = build_game_map(level_01, catalog)
    return Engine(
        game_map,
        player,
        level_01.name,
        catalog=catalog,
        levels=levels,
        starting_level=level_01,
    )


def test_escape_quits_while_playing():
    engine = make_engine()
    assert dispatch_action(engine, EscapeAction()) is True


def test_escape_quits_after_death():
    engine = make_engine()
    engine.game_state = "dead"
    assert dispatch_action(engine, EscapeAction()) is True


def test_escape_quits_regardless_of_game_state():
    engine = make_engine()
    engine.game_state = "some-future-state"  # dispatch_action must not special-case values
    assert dispatch_action(engine, EscapeAction()) is True


def test_restart_is_ignored_while_playing():
    engine = make_engine()
    original_map = engine.game_map
    assert dispatch_action(engine, RestartAction()) is False
    assert engine.game_map is original_map
    assert engine.game_state == "playing"


def test_restart_is_applied_after_death():
    engine = make_engine()
    engine.game_state = "dead"
    assert dispatch_action(engine, RestartAction()) is False
    assert engine.game_state == "playing"


def test_normal_action_is_processed_while_playing():
    engine = make_engine()
    message_count_before = len(engine.message_log.messages)
    assert dispatch_action(engine, WaitAction()) is False
    assert len(engine.message_log.messages) == message_count_before


def test_none_action_is_a_noop():
    engine = make_engine()
    assert dispatch_action(engine, None) is False


def test_dispatch_action_calls_the_hook_before_enemy_ai_gets_to_move():
    """Regression test for a real visual bug: the impact flash used to
    render on a tile a monster had already left, because ranged combat
    events were drained and animated in one shot *after* enemy AI had
    already moved on the same turn. on_player_turn_resolved must fire with
    the monster still at the position recorded in the attack event - only
    the later, separate enemy-phase animation call should see it having
    moved."""
    game_map = GameMap(10, 3)
    for x in range(10):
        for y in range(3):
            game_map.kinds[x, y] = "floor"
            game_map.walkable[x, y] = True
            game_map.transparent[x, y] = True
    player = Entity(
        0, 1, "@", (255, 255, 255), "Player",
        blocks_movement=True, render_priority=RENDER_PRIORITY_PLAYER,
        fighter=Fighter(max_hp=30, hp=30, attack=5, defense=1),
    )
    player.equipped_ranged_weapon = Entity(
        0, 0, "}", (160, 120, 70), "Hunting Bow",
        render_priority=RENDER_PRIORITY_ITEM, item=ItemEffect(ranged_attack_bonus=3, range=5),
    )
    player.inventory.append(
        Entity(
            0, 0, "|", (190, 170, 140), "Arrows",
            render_priority=RENDER_PRIORITY_ITEM, item=ItemEffect(is_ammo=True, quantity=5),
        )
    )
    monster = Entity(
        4, 1, "g", (60, 140, 60), "Goblin",
        blocks_movement=True, render_priority=RENDER_PRIORITY_ACTOR,
        fighter=Fighter(max_hp=50, hp=50, attack=1, defense=0), ai="hostile_basic",
    )
    game_map.entities.extend([player, monster])
    engine = Engine(game_map, player, "Test Level")

    seen = []

    def hook():
        assert engine.ranged_attack_events, "expected a queued ranged attack event"
        _, _, tx, ty = engine.ranged_attack_events[0]
        seen.append(((tx, ty), (monster.x, monster.y)))

    dispatch_action(engine, FireAction(4, 1), on_player_turn_resolved=hook)

    assert seen, "the hook never fired"
    event_target, monster_position_at_hook_time = seen[0]
    assert event_target == monster_position_at_hook_time  # matched when the hook fired...
    assert (monster.x, monster.y) != event_target  # ...but has since moved, chasing the player
    assert monster.fighter.hp == 50 - 8  # 5 base + 3 bow bonus, confirms the shot landed


def test_fire_mode_gate_blocks_without_a_ranged_weapon():
    engine = make_engine()
    assert fire_mode_gate(engine) == "You have no ranged weapon equipped."


def test_fire_mode_gate_blocks_without_ammo():
    engine = make_engine()
    engine.player.equipped_ranged_weapon = Entity(
        0, 0, "}", (160, 120, 70), "Hunting Bow",
        render_priority=RENDER_PRIORITY_ITEM,
        item=ItemEffect(ranged_attack_bonus=3, range=5),
    )
    assert fire_mode_gate(engine) == "You have no ammo."


def test_fire_mode_gate_allows_when_armed_and_stocked():
    engine = make_engine()
    engine.player.equipped_ranged_weapon = Entity(
        0, 0, "}", (160, 120, 70), "Hunting Bow",
        render_priority=RENDER_PRIORITY_ITEM,
        item=ItemEffect(ranged_attack_bonus=3, range=5),
    )
    engine.player.inventory.append(
        Entity(
            0, 0, "|", (190, 170, 140), "Arrows",
            render_priority=RENDER_PRIORITY_ITEM,
            item=ItemEffect(is_ammo=True, quantity=5),
        )
    )
    assert fire_mode_gate(engine) is None


def test_shop_gate_blocks_without_a_shopkeeper_nearby():
    engine = make_engine()  # forgotten_ruins level_01: no villagers at all
    assert shop_gate(engine) == "There's no one here to buy from."


def test_shop_gate_allows_when_a_shopkeeper_is_adjacent():
    game_map = GameMap(3, 3)
    for x in range(3):
        for y in range(3):
            game_map.kinds[x, y] = "floor"
            game_map.walkable[x, y] = True
            game_map.transparent[x, y] = True
    player = Entity(
        1, 1, "@", (255, 255, 255), "Player",
        blocks_movement=True, render_priority=RENDER_PRIORITY_PLAYER,
        fighter=Fighter(max_hp=30, hp=30, attack=5, defense=1),
    )
    shopkeeper = Entity(
        2, 1, "m", (200, 160, 70), "Shopkeeper",
        blocks_movement=True, render_priority=RENDER_PRIORITY_ACTOR,
        fighter=Fighter(max_hp=10, hp=10, attack=0, defense=0),
        ai="villager", shop_inventory=["healing_potion"],
    )
    game_map.entities.extend([player, shopkeeper])
    engine = Engine(game_map, player, "Test Level")

    assert shop_gate(engine) is None


def test_shop_gate_blocks_when_the_shopkeeper_is_fleeing():
    game_map = GameMap(3, 3)
    for x in range(3):
        for y in range(3):
            game_map.kinds[x, y] = "floor"
            game_map.walkable[x, y] = True
            game_map.transparent[x, y] = True
    player = Entity(
        1, 1, "@", (255, 255, 255), "Player",
        blocks_movement=True, render_priority=RENDER_PRIORITY_PLAYER,
        fighter=Fighter(max_hp=30, hp=30, attack=5, defense=1),
    )
    shopkeeper = Entity(
        2, 1, "m", (200, 160, 70), "Shopkeeper",
        blocks_movement=True, render_priority=RENDER_PRIORITY_ACTOR,
        fighter=Fighter(max_hp=10, hp=5, attack=0, defense=0),  # already hurt - fleeing
        ai="villager", shop_inventory=["healing_potion"],
    )
    game_map.entities.extend([player, shopkeeper])
    engine = Engine(game_map, player, "Test Level")

    assert shop_gate(engine) == "There's no one here to buy from."


def _world():
    """Real shipped content: catalog, dungeon registry, and the overworld -
    what resolve_transition actually needs at runtime."""
    catalog = load_catalog()
    dungeon_registry = load_dungeon_registry(DUNGEONS_DIR, catalog)
    overworld_level = load_overworld(
        OVERWORLD_LEVEL_PATH, catalog, known_dungeon_ids=set(dungeon_registry)
    )
    return catalog, dungeon_registry, overworld_level


def _entrance_for(overworld_level, dungeon_id: str) -> tuple[int, int]:
    entrance = next(e for e in overworld_level.dungeon_entrances if e.dungeon_id == dungeon_id)
    return (entrance.x, entrance.y)


def _dungeon_engine(dungeon_registry, catalog, dungeon_id: str, clock=None, quest_log=None) -> Engine:
    dungeon = dungeon_registry[dungeon_id]
    starting_level = dungeon.levels[dungeon.starting_level]
    game_map, player = build_game_map(starting_level, catalog)
    return Engine(
        game_map, player, starting_level.name,
        catalog=catalog, levels=dungeon.levels, starting_level=starting_level,
        clock=clock, quest_log=quest_log,
    )


def test_resolve_transition_first_overworld_visit_lands_at_matched_entrance():
    catalog, dungeon_registry, overworld_level = _world()
    engine = _dungeon_engine(dungeon_registry, catalog, "prison_tower")
    engine.on_player_reach_stairs(None, "stairs_up")  # the retreat stairs near player_start

    active_key, new_engine = resolve_transition(
        "prison_tower", engine, {"prison_tower": engine}, dungeon_registry, overworld_level, catalog,
    )

    assert active_key == OVERWORLD_KEY
    assert new_engine.is_overworld is True
    assert (new_engine.player.x, new_engine.player.y) == _entrance_for(overworld_level, "prison_tower")


def test_resolve_transition_passes_the_given_clock_to_the_overworld_engine():
    catalog, dungeon_registry, overworld_level = _world()
    clock = GameClock()
    engine = _dungeon_engine(dungeon_registry, catalog, "prison_tower", clock=clock)
    engine.on_player_reach_stairs(None, "stairs_up")

    _, new_engine = resolve_transition(
        "prison_tower", engine, {"prison_tower": engine}, dungeon_registry, overworld_level, catalog,
        clock=clock,
    )

    assert new_engine.clock is clock


def test_resolve_transition_without_a_clock_still_works():
    catalog, dungeon_registry, overworld_level = _world()
    engine = _dungeon_engine(dungeon_registry, catalog, "prison_tower")
    engine.on_player_reach_stairs(None, "stairs_up")

    active_key, new_engine = resolve_transition(
        "prison_tower", engine, {"prison_tower": engine}, dungeon_registry, overworld_level, catalog,
    )

    assert active_key == OVERWORLD_KEY
    assert new_engine.clock == GameClock()


def _quest_log_with_dungeon_target(dungeon_id: str) -> QuestLog:
    """A synthetic QuestLog for exercising resolve_transition's wiring to
    QuestLog.record_dungeon_arrival - the same trigger shape the real
    word_down_the_road quest uses (see test_engine.py for that quest's own
    full report-based completion), kept here as isolated infrastructure
    coverage for resolve_transition's own wiring specifically."""
    quest = Quest(
        id="test_quest",
        name="Test Quest",
        description="",
        completion_message="Quest complete!",
        failure_message="Quest failed!",
        deadline_year=9999,
        deadline_day=1,
        target_dungeon_id=dungeon_id,
        questgiver_entity_id="test_questgiver",
        status="in_progress",
    )
    return QuestLog(quests={quest.id: quest})


def test_resolve_transition_dungeon_arrival_records_the_visit_but_does_not_complete_the_quest():
    """Arriving in the target dungeon only records the visit now (see
    QuestLog.record_dungeon_arrival) - completion requires reporting back to
    the questgiver (QuestLog.check_dungeon_report), same two-step shape as a
    fetch quest's pickup vs. delivery."""
    catalog, dungeon_registry, overworld_level = _world()
    quest_log = _quest_log_with_dungeon_target("millhaven")
    active_engines: dict = {}

    prison_engine = _dungeon_engine(dungeon_registry, catalog, "prison_tower", quest_log=quest_log)
    prison_engine.on_player_reach_stairs(None, "stairs_up")
    active_engines["prison_tower"] = prison_engine
    active_key, overworld_engine = resolve_transition(
        "prison_tower", prison_engine, active_engines, dungeon_registry, overworld_level, catalog,
        quest_log=quest_log,
    )

    overworld_engine.pending_dungeon_entry = "millhaven"
    active_key, millhaven_engine = resolve_transition(
        OVERWORLD_KEY, overworld_engine, active_engines, dungeon_registry, overworld_level, catalog,
        quest_log=quest_log,
    )

    assert active_key == "millhaven"
    assert "millhaven" in quest_log.visited_dungeon_ids
    assert quest_log.quests["test_quest"].status == "in_progress"
    assert quest_log.quests["test_quest"].completion_message not in millhaven_engine.message_log.messages


def test_resolve_transition_dungeon_arrival_then_report_grants_a_reward():
    """The follow-through once the visit's been recorded: reporting to the
    questgiver (QuestLog.check_dungeon_report, same call Engine.talk_to_adjacent
    makes) completes the quest and grants its reward."""
    catalog, dungeon_registry, overworld_level = _world()
    quest_log = _quest_log_with_dungeon_target("millhaven")
    quest_log.quests["test_quest"].reward_item_id = "healing_potion"
    active_engines: dict = {}

    prison_engine = _dungeon_engine(dungeon_registry, catalog, "prison_tower", quest_log=quest_log)
    prison_engine.on_player_reach_stairs(None, "stairs_up")
    active_engines["prison_tower"] = prison_engine
    active_key, overworld_engine = resolve_transition(
        "prison_tower", prison_engine, active_engines, dungeon_registry, overworld_level, catalog,
        quest_log=quest_log,
    )

    overworld_engine.pending_dungeon_entry = "millhaven"
    active_key, millhaven_engine = resolve_transition(
        OVERWORLD_KEY, overworld_engine, active_engines, dungeon_registry, overworld_level, catalog,
        quest_log=quest_log,
    )

    for quest in millhaven_engine.quest_log.check_dungeon_report("test_questgiver"):
        millhaven_engine.complete_quest(quest)

    assert quest_log.quests["test_quest"].status == "completed"
    assert len(millhaven_engine.player.inventory) == 1
    assert millhaven_engine.player.inventory[0].name == "Healing Potion"


def test_resolve_transition_dungeon_arrival_does_not_complete_a_non_matching_quest():
    catalog, dungeon_registry, overworld_level = _world()
    quest_log = _quest_log_with_dungeon_target("millhaven")
    active_engines: dict = {}

    prison_engine = _dungeon_engine(dungeon_registry, catalog, "prison_tower", quest_log=quest_log)
    prison_engine.on_player_reach_stairs(None, "stairs_up")
    active_engines["prison_tower"] = prison_engine
    active_key, overworld_engine = resolve_transition(
        "prison_tower", prison_engine, active_engines, dungeon_registry, overworld_level, catalog,
        quest_log=quest_log,
    )

    overworld_engine.pending_dungeon_entry = "forgotten_ruins"
    resolve_transition(
        OVERWORLD_KEY, overworld_engine, active_engines, dungeon_registry, overworld_level, catalog,
        quest_log=quest_log,
    )

    assert quest_log.quests["test_quest"].status == "in_progress"


def test_resolve_transition_without_a_quest_log_still_works():
    catalog, dungeon_registry, overworld_level = _world()
    engine = _dungeon_engine(dungeon_registry, catalog, "prison_tower")
    engine.pending_dungeon_entry = "millhaven"

    active_key, new_engine = resolve_transition(
        "prison_tower", engine, {"prison_tower": engine}, dungeon_registry, overworld_level, catalog,
    )

    assert active_key == "millhaven"
    # record_dungeon_arrival still fires unconditionally on the fresh,
    # otherwise-empty QuestLog Engine() defaults to - see record_dungeon_arrival.
    assert new_engine.quest_log == QuestLog(visited_dungeon_ids={"millhaven"})


def test_resolve_transition_deadline_failure_wins_a_same_turn_tie_with_arrival():
    """Documented, accepted edge case for the dungeon-arrival completion
    mechanism (still-valid general infrastructure - see
    _quest_log_with_dungeon_target): if the very turn the player steps onto
    a dungeon's entrance tile is also the turn the clock crosses the
    deadline, the deadline-failure check (which runs inside process_turn,
    before resolve_transition is ever called) wins the tie. The real
    starting quest no longer uses this trigger (it completes via Talk
    instead, which isn't turn-coupled to movement the same way - see
    test_engine.py), but a future dungeon-arrival quest could still hit
    this race, so it stays covered here."""
    catalog, dungeon_registry, overworld_level = _world()
    quest_log = _quest_log_with_dungeon_target("millhaven")
    quest = quest_log.quests["test_quest"]
    clock = GameClock(year=quest.deadline_year, day=quest.deadline_day, hour=HOURS_PER_DAY - 1)

    overworld_map, overworld_player = build_game_map(overworld_level, catalog)
    overworld_engine = Engine(
        overworld_map, overworld_player, overworld_level.name,
        catalog=catalog, is_overworld=True, clock=clock, quest_log=quest_log,
    )
    overworld_engine.pending_dungeon_entry = "millhaven"  # simulates having just stepped onto the tile

    overworld_engine.process_turn(WaitAction())  # the clock crosses the deadline this same turn
    assert quest.status == "failed"

    resolve_transition(
        OVERWORLD_KEY, overworld_engine, {OVERWORLD_KEY: overworld_engine},
        dungeon_registry, overworld_level, catalog, quest_log=quest_log,
    )

    assert quest.status == "failed"  # arrival does not revive an already-failed quest


def test_resolve_transition_builds_overworld_engine_with_dungeon_inspect_text():
    catalog, dungeon_registry, overworld_level = _world()
    engine = _dungeon_engine(dungeon_registry, catalog, "prison_tower")
    engine.on_player_reach_stairs(None, "stairs_up")

    _, overworld_engine = resolve_transition(
        "prison_tower", engine, {"prison_tower": engine}, dungeon_registry, overworld_level, catalog,
    )

    assert overworld_engine.dungeon_inspect_text["prison_tower"] == dungeon_registry["prison_tower"].inspect_text
    assert overworld_engine.dungeon_inspect_text["forgotten_ruins"] == dungeon_registry["forgotten_ruins"].inspect_text


def test_resolve_transition_each_dungeons_departure_lands_at_its_own_entrance():
    catalog, dungeon_registry, overworld_level = _world()
    active_engines: dict = {}

    prison_engine = _dungeon_engine(dungeon_registry, catalog, "prison_tower")
    prison_engine.on_player_reach_stairs(None, "stairs_up")
    active_engines["prison_tower"] = prison_engine
    _, overworld_engine = resolve_transition(
        "prison_tower", prison_engine, active_engines, dungeon_registry, overworld_level, catalog,
    )

    ruins_engine = _dungeon_engine(dungeon_registry, catalog, "forgotten_ruins")
    ruins_engine.on_player_reach_stairs(None, "stairs_up")
    active_engines["forgotten_ruins"] = ruins_engine
    active_key, same_overworld_engine = resolve_transition(
        "forgotten_ruins", ruins_engine, active_engines, dungeon_registry, overworld_level, catalog,
    )

    assert active_key == OVERWORLD_KEY
    assert same_overworld_engine is overworld_engine  # cached, not rebuilt
    assert (same_overworld_engine.player.x, same_overworld_engine.player.y) == _entrance_for(
        overworld_level, "forgotten_ruins"
    )


def test_resolve_transition_reentering_a_dungeon_resumes_the_exact_retreat_spot():
    catalog, dungeon_registry, overworld_level = _world()
    active_engines: dict = {}

    prison_engine = _dungeon_engine(dungeon_registry, catalog, "prison_tower")
    original_map = prison_engine.game_map
    retreat_spot = (prison_engine.player.x, prison_engine.player.y)
    prison_engine.on_player_reach_stairs(None, "stairs_up")
    active_engines["prison_tower"] = prison_engine

    active_key, overworld_engine = resolve_transition(
        "prison_tower", prison_engine, active_engines, dungeon_registry, overworld_level, catalog,
    )
    assert active_key == OVERWORLD_KEY

    # Walk onto the prison_tower entrance tile on the overworld to trigger re-entry.
    overworld_engine.pending_dungeon_entry = "prison_tower"
    active_key, back_engine = resolve_transition(
        OVERWORLD_KEY, overworld_engine, active_engines, dungeon_registry, overworld_level, catalog,
    )

    assert active_key == "prison_tower"
    assert back_engine.game_map is original_map  # same cached map, not rebuilt
    assert (back_engine.player.x, back_engine.player.y) == retreat_spot


def test_resolve_transition_does_nothing_when_not_playing():
    catalog, dungeon_registry, overworld_level = _world()
    engine = _dungeon_engine(dungeon_registry, catalog, "prison_tower")
    engine.wants_overworld = True
    engine.game_state = "dead"  # e.g. killed the same turn a leave-tile was reached

    active_key, same_engine = resolve_transition(
        "prison_tower", engine, {"prison_tower": engine}, dungeon_registry, overworld_level, catalog,
    )

    assert active_key == "prison_tower"
    assert same_engine is engine
    assert engine.wants_overworld is True  # untouched - the death screen takes priority


def test_resolve_transition_round_trip_preserves_dungeon_state():
    catalog, dungeon_registry, overworld_level = _world()
    active_engines: dict = {}

    prison_engine = _dungeon_engine(dungeon_registry, catalog, "prison_tower")
    guard = next(e for e in prison_engine.game_map.entities if e.name == "Guard")
    prison_engine.on_entity_death(guard)
    assert guard not in prison_engine.game_map.entities

    prison_engine.on_player_reach_stairs(None, "stairs_up")
    active_engines["prison_tower"] = prison_engine
    active_key, overworld_engine = resolve_transition(
        "prison_tower", prison_engine, active_engines, dungeon_registry, overworld_level, catalog,
    )

    # Detour: overworld -> forgotten_ruins -> overworld -> back to prison_tower.
    overworld_engine.pending_dungeon_entry = "forgotten_ruins"
    active_key, ruins_engine = resolve_transition(
        active_key, overworld_engine, active_engines, dungeon_registry, overworld_level, catalog,
    )
    ruins_engine.on_player_reach_stairs(None, "stairs_up")
    active_key, overworld_engine_2 = resolve_transition(
        active_key, ruins_engine, active_engines, dungeon_registry, overworld_level, catalog,
    )
    assert overworld_engine_2 is overworld_engine  # still the one cached overworld Engine

    overworld_engine_2.pending_dungeon_entry = "prison_tower"
    active_key, prison_engine_2 = resolve_transition(
        active_key, overworld_engine_2, active_engines, dungeon_registry, overworld_level, catalog,
    )

    assert active_key == "prison_tower"
    assert prison_engine_2 is prison_engine
    assert guard not in prison_engine_2.game_map.entities  # still dead after the detour


# --- resolve_transition: overworld encounter redirect ---


def _quest_log_with_ambush_quest(status: str) -> QuestLog:
    """A synthetic QuestLog with one quest at id 'spreading_the_warning' -
    matches the real shipped data/encounters.yaml's warning_ambush entry's
    gate_quest_id exactly, so a real EncounterDef built directly (not loaded
    from the file - see _ambush_encounter below) can be checked against it
    without a filesystem dependency."""
    quest = Quest(
        id="spreading_the_warning", name="Spreading the Warning", description="",
        completion_message="Warning delivered.", status=status,
    )
    return QuestLog(quests={quest.id: quest})


def _ambush_encounter() -> dict[str, EncounterDef]:
    """Built directly rather than loaded from data/encounters.yaml, so these
    tests don't depend on that file's exact contents - only on the real
    millhaven/goblin_ambush dungeons existing in the registry, which
    _world() already provides."""
    return {
        "warning_ambush": EncounterDef(
            id="warning_ambush", trigger_dungeon_id="millhaven",
            gate_quest_id="spreading_the_warning", encounter_dungeon_id="goblin_ambush",
            encounter_message="You've been ambushed!",
        ),
    }


def test_resolve_transition_arms_but_does_not_immediately_redirect():
    """Leaving Millhaven no longer instantly ambushes the player - it only
    arms delay_hours' timer (see EncounterDef.delay_hours)."""
    catalog, dungeon_registry, overworld_level = _world()
    clock = GameClock()
    engine = _dungeon_engine(dungeon_registry, catalog, "millhaven", clock=clock, quest_log=_quest_log_with_ambush_quest("in_progress"))
    engine.on_player_reach_stairs(None, "stairs_up")

    active_key, new_engine = resolve_transition(
        "millhaven", engine, {"millhaven": engine}, dungeon_registry, overworld_level, catalog,
        clock=clock, quest_log=engine.quest_log, encounter_registry=_ambush_encounter(),
    )

    assert active_key == OVERWORLD_KEY
    assert new_engine.is_overworld is True
    assert "warning_ambush" in engine.quest_log.armed_encounters
    assert "warning_ambush" not in engine.quest_log.triggered_encounter_ids


def test_resolve_transition_does_not_fire_before_the_delay_elapses():
    catalog, dungeon_registry, overworld_level = _world()
    clock = GameClock()
    quest_log = _quest_log_with_ambush_quest("in_progress")
    engine = _dungeon_engine(dungeon_registry, catalog, "millhaven", clock=clock, quest_log=quest_log)
    engine.on_player_reach_stairs(None, "stairs_up")
    encounter_registry = _ambush_encounter()  # delay_hours defaults to 3

    active_key, overworld_engine = resolve_transition(
        "millhaven", engine, {"millhaven": engine}, dungeon_registry, overworld_level, catalog,
        clock=clock, quest_log=quest_log, encounter_registry=encounter_registry,
    )
    assert active_key == OVERWORLD_KEY

    for _ in range(2):  # fewer than the 3-hour delay
        clock.advance_hour()
        active_key, overworld_engine = resolve_transition(
            active_key, overworld_engine, {"millhaven": engine, OVERWORLD_KEY: overworld_engine},
            dungeon_registry, overworld_level, catalog,
            clock=clock, quest_log=quest_log, encounter_registry=encounter_registry,
        )

    assert active_key == OVERWORLD_KEY
    assert overworld_engine.is_overworld is True
    assert "warning_ambush" not in quest_log.triggered_encounter_ids


def test_resolve_transition_fires_once_the_delay_elapses():
    catalog, dungeon_registry, overworld_level = _world()
    clock = GameClock()
    quest_log = _quest_log_with_ambush_quest("in_progress")
    engine = _dungeon_engine(dungeon_registry, catalog, "millhaven", clock=clock, quest_log=quest_log)
    engine.on_player_reach_stairs(None, "stairs_up")
    encounter_registry = _ambush_encounter()
    active_engines = {"millhaven": engine}

    active_key, overworld_engine = resolve_transition(
        "millhaven", engine, active_engines, dungeon_registry, overworld_level, catalog,
        clock=clock, quest_log=quest_log, encounter_registry=encounter_registry,
    )
    active_engines[OVERWORLD_KEY] = overworld_engine

    for _ in range(3):  # exactly the default delay_hours
        clock.advance_hour()
        active_key, engine_now = resolve_transition(
            active_key, overworld_engine, active_engines, dungeon_registry, overworld_level, catalog,
            clock=clock, quest_log=quest_log, encounter_registry=encounter_registry,
        )

    assert active_key == "goblin_ambush"
    assert engine_now.is_overworld is False
    goblins = [e for e in engine_now.game_map.entities if e.name == "Goblin"]
    assert len(goblins) == 3
    assert "warning_ambush" in quest_log.triggered_encounter_ids
    assert "goblin_ambush" in quest_log.visited_dungeon_ids
    assert "You've been ambushed!" in engine_now.message_log.messages
    assert engine_now.message_log.messages[-1] == "You've been ambushed!"  # logged right after "You enter..."


def test_resolve_transition_fires_with_no_encounter_message_logs_nothing_extra():
    catalog, dungeon_registry, overworld_level = _world()
    clock = GameClock()
    quest_log = _quest_log_with_ambush_quest("in_progress")
    engine = _dungeon_engine(dungeon_registry, catalog, "millhaven", clock=clock, quest_log=quest_log)
    engine.on_player_reach_stairs(None, "stairs_up")
    encounter_registry = {
        "warning_ambush": EncounterDef(
            id="warning_ambush", trigger_dungeon_id="millhaven",
            gate_quest_id="spreading_the_warning", encounter_dungeon_id="goblin_ambush",
        ),  # encounter_message left unset, defaults to ""
    }
    active_engines = {"millhaven": engine}

    active_key, overworld_engine = resolve_transition(
        "millhaven", engine, active_engines, dungeon_registry, overworld_level, catalog,
        clock=clock, quest_log=quest_log, encounter_registry=encounter_registry,
    )
    active_engines[OVERWORLD_KEY] = overworld_engine

    for _ in range(3):
        clock.advance_hour()
        active_key, engine_now = resolve_transition(
            active_key, overworld_engine, active_engines, dungeon_registry, overworld_level, catalog,
            clock=clock, quest_log=quest_log, encounter_registry=encounter_registry,
        )

    assert active_key == "goblin_ambush"
    assert engine_now.message_log.messages[-1] == f"You enter {engine_now.level_name}."


def test_resolve_transition_fires_at_the_players_current_overworld_position():
    """The ambush catches up wherever the player actually is when the timer
    runs out, not back at Millhaven's entrance - Engine.overworld_return_position
    reflects wherever they'd wandered to during the delay."""
    catalog, dungeon_registry, overworld_level = _world()
    clock = GameClock()
    quest_log = _quest_log_with_ambush_quest("in_progress")
    engine = _dungeon_engine(dungeon_registry, catalog, "millhaven", clock=clock, quest_log=quest_log)
    engine.on_player_reach_stairs(None, "stairs_up")
    encounter_registry = _ambush_encounter()
    active_engines = {"millhaven": engine}

    active_key, overworld_engine = resolve_transition(
        "millhaven", engine, active_engines, dungeon_registry, overworld_level, catalog,
        clock=clock, quest_log=quest_log, encounter_registry=encounter_registry,
    )
    active_engines[OVERWORLD_KEY] = overworld_engine

    # Simulate the player wandering elsewhere on the overworld during the delay.
    wandered_to = (overworld_engine.player.x + 3, overworld_engine.player.y + 2)
    overworld_engine.player.x, overworld_engine.player.y = wandered_to

    for _ in range(3):
        clock.advance_hour()
        active_key, ambush_engine = resolve_transition(
            active_key, overworld_engine, active_engines, dungeon_registry, overworld_level, catalog,
            clock=clock, quest_log=quest_log, encounter_registry=encounter_registry,
        )

    assert active_key == "goblin_ambush"

    ambush_engine.on_player_reach_stairs(None, "stairs_up")  # flee the ambush
    active_key, back_on_overworld = resolve_transition(
        active_key, ambush_engine, active_engines, dungeon_registry, overworld_level, catalog,
        clock=clock, quest_log=quest_log, encounter_registry=encounter_registry,
    )

    assert active_key == OVERWORLD_KEY
    assert (back_on_overworld.player.x, back_on_overworld.player.y) == wandered_to


def test_resolve_transition_redeparting_before_firing_resets_the_timer():
    catalog, dungeon_registry, overworld_level = _world()
    clock = GameClock()
    quest_log = _quest_log_with_ambush_quest("in_progress")
    engine = _dungeon_engine(dungeon_registry, catalog, "millhaven", clock=clock, quest_log=quest_log)
    engine.on_player_reach_stairs(None, "stairs_up")
    encounter_registry = _ambush_encounter()

    resolve_transition(
        "millhaven", engine, {"millhaven": engine}, dungeon_registry, overworld_level, catalog,
        clock=clock, quest_log=quest_log, encounter_registry=encounter_registry,
    )
    first_due = quest_log.armed_encounters["warning_ambush"]

    clock.advance_hour()
    clock.advance_hour()  # 2 hours elapsed, still not due

    # Re-enter and leave Millhaven again - the timer should restart from here.
    engine_2 = _dungeon_engine(dungeon_registry, catalog, "millhaven", clock=clock, quest_log=quest_log)
    engine_2.on_player_reach_stairs(None, "stairs_up")
    resolve_transition(
        "millhaven", engine_2, {"millhaven": engine_2}, dungeon_registry, overworld_level, catalog,
        clock=clock, quest_log=quest_log, encounter_registry=encounter_registry,
    )
    second_due = quest_log.armed_encounters["warning_ambush"]

    assert second_due != first_due
    assert second_due > first_due


def test_resolve_transition_does_not_trigger_the_ambush_from_a_different_dungeon():
    catalog, dungeon_registry, overworld_level = _world()
    engine = _dungeon_engine(dungeon_registry, catalog, "forgotten_ruins", quest_log=_quest_log_with_ambush_quest("in_progress"))
    engine.on_player_reach_stairs(None, "stairs_up")

    active_key, new_engine = resolve_transition(
        "forgotten_ruins", engine, {"forgotten_ruins": engine}, dungeon_registry, overworld_level, catalog,
        quest_log=engine.quest_log, encounter_registry=_ambush_encounter(),
    )

    assert active_key == OVERWORLD_KEY
    assert new_engine.is_overworld is True


def test_resolve_transition_does_not_trigger_the_ambush_when_the_quest_is_not_in_progress():
    catalog, dungeon_registry, overworld_level = _world()
    engine = _dungeon_engine(dungeon_registry, catalog, "millhaven", quest_log=_quest_log_with_ambush_quest("completed"))
    engine.on_player_reach_stairs(None, "stairs_up")

    active_key, new_engine = resolve_transition(
        "millhaven", engine, {"millhaven": engine}, dungeon_registry, overworld_level, catalog,
        quest_log=engine.quest_log, encounter_registry=_ambush_encounter(),
    )

    assert active_key == OVERWORLD_KEY
    assert new_engine.is_overworld is True


def test_resolve_transition_does_not_retrigger_an_already_triggered_ambush():
    catalog, dungeon_registry, overworld_level = _world()
    quest_log = _quest_log_with_ambush_quest("in_progress")
    quest_log.triggered_encounter_ids.add("warning_ambush")
    engine = _dungeon_engine(dungeon_registry, catalog, "millhaven", quest_log=quest_log)
    engine.on_player_reach_stairs(None, "stairs_up")

    active_key, new_engine = resolve_transition(
        "millhaven", engine, {"millhaven": engine}, dungeon_registry, overworld_level, catalog,
        quest_log=quest_log, encounter_registry=_ambush_encounter(),
    )

    assert active_key == OVERWORLD_KEY
    assert new_engine.is_overworld is True


def _arm_and_fire_ambush(dungeon_registry, catalog, overworld_level, clock, quest_log, active_engines):
    """Shared setup for tests past the arm/fire split that don't care about
    the delay mechanics themselves: departs Millhaven, advances the clock
    through the default 3-hour delay_hours, and returns (active_key, engine)
    once the ambush has actually fired."""
    encounter_registry = _ambush_encounter()
    engine = _dungeon_engine(dungeon_registry, catalog, "millhaven", clock=clock, quest_log=quest_log)
    engine.on_player_reach_stairs(None, "stairs_up")
    active_engines["millhaven"] = engine

    active_key, current = resolve_transition(
        "millhaven", engine, active_engines, dungeon_registry, overworld_level, catalog,
        clock=clock, quest_log=quest_log, encounter_registry=encounter_registry,
    )
    active_engines[OVERWORLD_KEY] = current

    for _ in range(3):
        clock.advance_hour()
        active_key, current = resolve_transition(
            active_key, current, active_engines, dungeon_registry, overworld_level, catalog,
            clock=clock, quest_log=quest_log, encounter_registry=encounter_registry,
        )
    return active_key, current


def test_resolve_transition_ambush_resumes_the_same_cached_engine_after_a_restart():
    """Engine.restart() (called elsewhere, not exercised directly here) only
    rebuilds the *current* Engine and clears QuestLog.triggered_encounter_ids/
    armed_encounters - it doesn't evict active_engines. Pinning that a
    second ambush trigger (simulated by clearing that state directly, the
    same effect restart's QuestLog.reset() has) resumes the exact same
    cached Engine rather than rebuilding a fresh one - consistent with
    every other cached dungeon's documented behavior (see QuestLog.reset's
    own docstring)."""
    catalog, dungeon_registry, overworld_level = _world()
    clock = GameClock()
    quest_log = _quest_log_with_ambush_quest("in_progress")
    active_engines: dict = {}

    active_key, ambush_engine = _arm_and_fire_ambush(dungeon_registry, catalog, overworld_level, clock, quest_log, active_engines)
    assert active_key == "goblin_ambush"
    goblin = next(e for e in ambush_engine.game_map.entities if e.name == "Goblin")
    ambush_engine.on_entity_death(goblin)
    assert goblin not in ambush_engine.game_map.entities

    # Simulate a restart: the quest goes back to in_progress (a fresh run
    # re-grants it) and the encounter's arm/trigger record clears, exactly
    # like QuestLog.reset() - but active_engines isn't touched.
    quest_log.triggered_encounter_ids.discard("warning_ambush")
    quest_log.armed_encounters.clear()

    active_key_2, ambush_engine_2 = _arm_and_fire_ambush(dungeon_registry, catalog, overworld_level, clock, quest_log, active_engines)

    assert active_key_2 == "goblin_ambush"
    assert ambush_engine_2 is ambush_engine
    assert goblin not in ambush_engine_2.game_map.entities  # still dead, not rebuilt fresh


# Dungeons deliberately unreachable by walking there - only ever entered via
# an EncounterDef's redirect (see main.py's _armable_encounter/_due_encounter)
# - carved out of the "every registered dungeon has an overworld entrance"
# check below.
ENCOUNTER_ONLY_DUNGEON_IDS = {"goblin_ambush"}


def test_overworld_has_all_ten_shipped_entrances_mutually_reachable():
    """Every dungeon_entrance on the real overworld map must be reachable from
    player_start via ordinary 8-directional movement, and vice versa - a
    location an entrance leads to that nothing can walk to would be shippable
    content nobody could ever reach. Every registered dungeon must have a
    matching entrance, except ENCOUNTER_ONLY_DUNGEON_IDS - those are reached
    through a scripted redirect instead, never by walking there."""
    catalog, dungeon_registry, overworld_level = _world()

    assert {e.dungeon_id for e in overworld_level.dungeon_entrances} == set(dungeon_registry) - ENCOUNTER_ONLY_DUNGEON_IDS
    assert len(overworld_level.dungeon_entrances) == 10

    game_map, _ = build_game_map(overworld_level, catalog)

    from collections import deque

    start = overworld_level.player_start
    seen = {start}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if (nx, ny) not in seen and game_map.is_walkable(nx, ny):
                    seen.add((nx, ny))
                    queue.append((nx, ny))

    for entrance in overworld_level.dungeon_entrances:
        assert (entrance.x, entrance.y) in seen, (
            f"{entrance.dungeon_id} entrance at ({entrance.x}, {entrance.y}) "
            "is unreachable from player_start"
        )
