"""Tests for the keymap layer. tcod.event.KeyDown instances can be constructed
directly without any window/context, so this is testable headlessly."""

import pytest
import tcod.event

from engine.actions import (
    BumpAction,
    CyclePotionKindAction,
    EscapeAction,
    FireModeAction,
    HelpAction,
    LookAction,
    QuestLogAction,
    RestartAction,
    SaveGameAction,
    ScrollLogAction,
    ShopAction,
    TrainerAction,
    WaitAction,
)
from engine.input_handlers import (
    handle_continue_prompt_event,
    handle_event,
    handle_help_event,
    handle_look_event,
    handle_quest_log_event,
    handle_shop_event,
    handle_target_event,
    handle_trainer_event,
)

NUMPAD_DIRECTIONS = [
    (tcod.event.KeySym.KP_7, (-1, -1)),
    (tcod.event.KeySym.KP_8, (0, -1)),
    (tcod.event.KeySym.KP_9, (1, -1)),
    (tcod.event.KeySym.KP_4, (-1, 0)),
    (tcod.event.KeySym.KP_6, (1, 0)),
    (tcod.event.KeySym.KP_1, (-1, 1)),
    (tcod.event.KeySym.KP_2, (0, 1)),
    (tcod.event.KeySym.KP_3, (1, 1)),
]


def key_down(sym: tcod.event.KeySym) -> tcod.event.KeyDown:
    return tcod.event.KeyDown(scancode=tcod.event.Scancode.A, sym=sym, mod=tcod.event.Modifier.NONE)


def test_handle_event_arrow_key_returns_bump_action():
    action = handle_event(key_down(tcod.event.KeySym.UP))
    assert isinstance(action, BumpAction)
    assert (action.dx, action.dy) == (0, -1)


@pytest.mark.parametrize("sym,delta", NUMPAD_DIRECTIONS)
def test_handle_event_numpad_key_returns_bump_action_with_diagonal_delta(sym, delta):
    action = handle_event(key_down(sym))
    assert isinstance(action, BumpAction)
    assert (action.dx, action.dy) == delta


def test_handle_event_kp5_returns_wait_action():
    assert isinstance(handle_event(key_down(tcod.event.KeySym.KP_5)), WaitAction)


def test_handle_event_l_returns_look_action():
    assert isinstance(handle_event(key_down(tcod.event.KeySym.L)), LookAction)


def test_handle_event_escape_returns_escape_action():
    assert isinstance(handle_event(key_down(tcod.event.KeySym.ESCAPE)), EscapeAction)


def test_handle_event_r_returns_restart_action():
    assert isinstance(handle_event(key_down(tcod.event.KeySym.R)), RestartAction)


def test_handle_event_q_returns_quest_log_action():
    assert isinstance(handle_event(key_down(tcod.event.KeySym.Q)), QuestLogAction)


def test_handle_event_b_returns_shop_action():
    assert isinstance(handle_event(key_down(tcod.event.KeySym.B)), ShopAction)


def test_handle_event_p_returns_trainer_action():
    assert isinstance(handle_event(key_down(tcod.event.KeySym.P)), TrainerAction)


def test_handle_event_s_returns_save_game_action():
    assert isinstance(handle_event(key_down(tcod.event.KeySym.S)), SaveGameAction)


def test_handle_event_c_returns_cycle_potion_kind_action():
    assert isinstance(handle_event(key_down(tcod.event.KeySym.C)), CyclePotionKindAction)


def test_handle_event_h_returns_help_action():
    assert isinstance(handle_event(key_down(tcod.event.KeySym.H)), HelpAction)


def test_handle_event_pageup_returns_scroll_log_action_back_into_history():
    action = handle_event(key_down(tcod.event.KeySym.PAGEUP))
    assert isinstance(action, ScrollLogAction)
    assert action.lines > 0


def test_handle_event_pagedown_returns_scroll_log_action_toward_latest():
    action = handle_event(key_down(tcod.event.KeySym.PAGEDOWN))
    assert isinstance(action, ScrollLogAction)
    assert action.lines < 0


def test_handle_continue_prompt_event_y_returns_yes():
    assert handle_continue_prompt_event(key_down(tcod.event.KeySym.Y)) == "yes"


def test_handle_continue_prompt_event_n_returns_no():
    assert handle_continue_prompt_event(key_down(tcod.event.KeySym.N)) == "no"


def test_handle_continue_prompt_event_escape_returns_no():
    assert handle_continue_prompt_event(key_down(tcod.event.KeySym.ESCAPE)) == "no"


def test_handle_continue_prompt_event_unmapped_key_returns_none():
    assert handle_continue_prompt_event(key_down(tcod.event.KeySym.A)) is None


def test_handle_event_unmapped_key_returns_none():
    assert handle_event(key_down(tcod.event.KeySym.Z)) is None


def test_handle_look_event_arrow_key_returns_cursor_delta():
    assert handle_look_event(key_down(tcod.event.KeySym.RIGHT)) == (1, 0)


@pytest.mark.parametrize("sym,delta", NUMPAD_DIRECTIONS)
def test_handle_look_event_numpad_key_returns_diagonal_cursor_delta(sym, delta):
    assert handle_look_event(key_down(sym)) == delta


@pytest.mark.parametrize("sym", [tcod.event.KeySym.ESCAPE, tcod.event.KeySym.L])
def test_handle_look_event_exit_keys(sym):
    assert handle_look_event(key_down(sym)) == "exit"


def test_handle_look_event_unmapped_key_returns_none():
    assert handle_look_event(key_down(tcod.event.KeySym.G)) is None


def test_handle_look_event_quit_raises_system_exit():
    with pytest.raises(SystemExit):
        handle_look_event(tcod.event.Quit(sdl_event=None))


def test_handle_event_f_returns_fire_mode_action():
    assert isinstance(handle_event(key_down(tcod.event.KeySym.F)), FireModeAction)


def test_handle_target_event_arrow_key_returns_cursor_delta():
    assert handle_target_event(key_down(tcod.event.KeySym.UP)) == (0, -1)


@pytest.mark.parametrize("sym,delta", NUMPAD_DIRECTIONS)
def test_handle_target_event_numpad_key_returns_diagonal_cursor_delta(sym, delta):
    assert handle_target_event(key_down(sym)) == delta


def test_handle_target_event_f_returns_fire():
    assert handle_target_event(key_down(tcod.event.KeySym.F)) == "fire"


def test_handle_target_event_escape_returns_cancel():
    assert handle_target_event(key_down(tcod.event.KeySym.ESCAPE)) == "cancel"


def test_handle_target_event_unmapped_key_returns_none():
    assert handle_target_event(key_down(tcod.event.KeySym.G)) is None


def test_handle_target_event_quit_raises_system_exit():
    with pytest.raises(SystemExit):
        handle_target_event(tcod.event.Quit(sdl_event=None))


def test_handle_quest_log_event_up_and_down():
    assert handle_quest_log_event(key_down(tcod.event.KeySym.UP)) == "up"
    assert handle_quest_log_event(key_down(tcod.event.KeySym.KP_8)) == "up"
    assert handle_quest_log_event(key_down(tcod.event.KeySym.DOWN)) == "down"
    assert handle_quest_log_event(key_down(tcod.event.KeySym.KP_2)) == "down"


def test_handle_quest_log_event_select():
    assert handle_quest_log_event(key_down(tcod.event.KeySym.RETURN)) == "select"
    assert handle_quest_log_event(key_down(tcod.event.KeySym.KP_ENTER)) == "select"


@pytest.mark.parametrize("sym", [tcod.event.KeySym.ESCAPE, tcod.event.KeySym.Q])
def test_handle_quest_log_event_exit_keys(sym):
    assert handle_quest_log_event(key_down(sym)) == "exit"


def test_handle_quest_log_event_unmapped_key_returns_none():
    assert handle_quest_log_event(key_down(tcod.event.KeySym.G)) is None


def test_handle_quest_log_event_quit_raises_system_exit():
    with pytest.raises(SystemExit):
        handle_quest_log_event(tcod.event.Quit(sdl_event=None))


def test_handle_shop_event_up_and_down():
    assert handle_shop_event(key_down(tcod.event.KeySym.UP)) == "up"
    assert handle_shop_event(key_down(tcod.event.KeySym.KP_8)) == "up"
    assert handle_shop_event(key_down(tcod.event.KeySym.DOWN)) == "down"
    assert handle_shop_event(key_down(tcod.event.KeySym.KP_2)) == "down"


def test_handle_shop_event_buy():
    assert handle_shop_event(key_down(tcod.event.KeySym.RETURN)) == "buy"
    assert handle_shop_event(key_down(tcod.event.KeySym.KP_ENTER)) == "buy"


@pytest.mark.parametrize("sym", [tcod.event.KeySym.ESCAPE, tcod.event.KeySym.B])
def test_handle_shop_event_exit_keys(sym):
    assert handle_shop_event(key_down(sym)) == "exit"


def test_handle_shop_event_unmapped_key_returns_none():
    assert handle_shop_event(key_down(tcod.event.KeySym.G)) is None


def test_handle_shop_event_quit_raises_system_exit():
    with pytest.raises(SystemExit):
        handle_shop_event(tcod.event.Quit(sdl_event=None))


def test_handle_trainer_event_up_and_down():
    assert handle_trainer_event(key_down(tcod.event.KeySym.UP)) == "up"
    assert handle_trainer_event(key_down(tcod.event.KeySym.KP_8)) == "up"
    assert handle_trainer_event(key_down(tcod.event.KeySym.DOWN)) == "down"
    assert handle_trainer_event(key_down(tcod.event.KeySym.KP_2)) == "down"


def test_handle_trainer_event_learn():
    assert handle_trainer_event(key_down(tcod.event.KeySym.RETURN)) == "learn"
    assert handle_trainer_event(key_down(tcod.event.KeySym.KP_ENTER)) == "learn"


@pytest.mark.parametrize("sym", [tcod.event.KeySym.ESCAPE, tcod.event.KeySym.P])
def test_handle_trainer_event_exit_keys(sym):
    assert handle_trainer_event(key_down(sym)) == "exit"


def test_handle_trainer_event_unmapped_key_returns_none():
    assert handle_trainer_event(key_down(tcod.event.KeySym.G)) is None


def test_handle_trainer_event_quit_raises_system_exit():
    with pytest.raises(SystemExit):
        handle_trainer_event(tcod.event.Quit(sdl_event=None))


@pytest.mark.parametrize("sym", [tcod.event.KeySym.ESCAPE, tcod.event.KeySym.H])
def test_handle_help_event_exit_keys(sym):
    assert handle_help_event(key_down(sym)) == "exit"


def test_handle_help_event_unmapped_key_returns_none():
    assert handle_help_event(key_down(tcod.event.KeySym.G)) is None


def test_handle_help_event_quit_raises_system_exit():
    with pytest.raises(SystemExit):
        handle_help_event(tcod.event.Quit(sdl_event=None))
