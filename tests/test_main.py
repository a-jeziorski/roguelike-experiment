"""Tests for main.py's action-dispatch glue - the interface between raw input
Actions and Engine/game-loop control. Pulled out into dispatch_action() so this
logic is testable without a real SDL window/event loop.

Regression coverage for a real bug: Escape only worked while game_state was
"playing", because Engine.process_turn no-ops once the run has ended, silently
swallowing the SystemExit that EscapeAction.perform() would otherwise raise."""

from pathlib import Path

from content.loader import load_catalog, load_levels
from engine.actions import EscapeAction, RestartAction, WaitAction
from engine.engine import Engine
from engine.entity import RENDER_PRIORITY_ITEM, Entity, ItemEffect
from engine.game_map import build_game_map
from main import dispatch_action, fire_mode_gate

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


def test_escape_quits_after_win():
    engine = make_engine()
    engine.game_state = "won"
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
