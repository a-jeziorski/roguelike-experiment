"""Tests for the keymap layer. tcod.event.KeyDown instances can be constructed
directly without any window/context, so this is testable headlessly."""

import pytest
import tcod.event

from engine.actions import BumpAction, EscapeAction, LookAction, RestartAction
from engine.input_handlers import handle_event, handle_look_event


def key_down(sym: tcod.event.KeySym) -> tcod.event.KeyDown:
    return tcod.event.KeyDown(scancode=tcod.event.Scancode.A, sym=sym, mod=tcod.event.Modifier.NONE)


def test_handle_event_arrow_key_returns_bump_action():
    action = handle_event(key_down(tcod.event.KeySym.UP))
    assert isinstance(action, BumpAction)
    assert (action.dx, action.dy) == (0, -1)


def test_handle_event_l_returns_look_action():
    assert isinstance(handle_event(key_down(tcod.event.KeySym.L)), LookAction)


def test_handle_event_escape_returns_escape_action():
    assert isinstance(handle_event(key_down(tcod.event.KeySym.ESCAPE)), EscapeAction)


def test_handle_event_r_returns_restart_action():
    assert isinstance(handle_event(key_down(tcod.event.KeySym.R)), RestartAction)


def test_handle_event_unmapped_key_returns_none():
    assert handle_event(key_down(tcod.event.KeySym.Z)) is None


def test_handle_look_event_arrow_key_returns_cursor_delta():
    assert handle_look_event(key_down(tcod.event.KeySym.RIGHT)) == (1, 0)


@pytest.mark.parametrize("sym", [tcod.event.KeySym.ESCAPE, tcod.event.KeySym.L])
def test_handle_look_event_exit_keys(sym):
    assert handle_look_event(key_down(sym)) == "exit"


def test_handle_look_event_unmapped_key_returns_none():
    assert handle_look_event(key_down(tcod.event.KeySym.G)) is None


def test_handle_look_event_quit_raises_system_exit():
    with pytest.raises(SystemExit):
        handle_look_event(tcod.event.Quit(sdl_event=None))
