"""Tests for main.py's action-dispatch glue - the interface between raw input
Actions and Engine/game-loop control. Pulled out into dispatch_action() so this
logic is testable without a real SDL window/event loop.

Regression coverage for a real bug: Escape only worked while game_state was
"playing", because Engine.process_turn no-ops once the run has ended, silently
swallowing the SystemExit that EscapeAction.perform() would otherwise raise."""

from pathlib import Path

from content.loader import load_catalog, load_dungeon
from engine.actions import EscapeAction, RestartAction, WaitAction
from engine.engine import Engine
from engine.game_map import build_game_map
from main import dispatch_action

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def make_engine() -> Engine:
    catalog = load_catalog()
    levels = load_dungeon(DATA_DIR / "levels", catalog)
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
