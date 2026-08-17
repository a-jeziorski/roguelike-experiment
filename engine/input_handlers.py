"""Translates tcod key events into Actions."""

from __future__ import annotations

import tcod.event

from engine.actions import (
    Action,
    BumpAction,
    EscapeAction,
    FireModeAction,
    LookAction,
    PickupAction,
    RestartAction,
    UseItemAction,
    WaitAction,
)

MOVE_KEYS = {
    tcod.event.KeySym.UP: (0, -1),
    tcod.event.KeySym.DOWN: (0, 1),
    tcod.event.KeySym.LEFT: (-1, 0),
    tcod.event.KeySym.RIGHT: (1, 0),
    # Numpad: classic roguelike 8-directional layout (KP_5 = wait, handled
    # separately below since it's not a movement delta).
    tcod.event.KeySym.KP_7: (-1, -1),
    tcod.event.KeySym.KP_8: (0, -1),
    tcod.event.KeySym.KP_9: (1, -1),
    tcod.event.KeySym.KP_4: (-1, 0),
    tcod.event.KeySym.KP_6: (1, 0),
    tcod.event.KeySym.KP_1: (-1, 1),
    tcod.event.KeySym.KP_2: (0, 1),
    tcod.event.KeySym.KP_3: (1, 1),
}


def handle_event(event: tcod.event.Event) -> Action | None:
    if isinstance(event, tcod.event.Quit):
        raise SystemExit()

    if isinstance(event, tcod.event.KeyDown):
        sym = event.sym

        if sym in MOVE_KEYS:
            dx, dy = MOVE_KEYS[sym]
            return BumpAction(dx, dy)

        if sym in (tcod.event.KeySym.PERIOD, tcod.event.KeySym.KP_5):
            return WaitAction()

        if sym == tcod.event.KeySym.G:
            return PickupAction()

        if sym == tcod.event.KeySym.U:
            return UseItemAction()

        if sym == tcod.event.KeySym.R:
            return RestartAction()

        if sym == tcod.event.KeySym.L:
            return LookAction()

        if sym == tcod.event.KeySym.F:
            return FireModeAction()

        if sym == tcod.event.KeySym.ESCAPE:
            return EscapeAction()

    return None


def handle_target_event(event: tcod.event.Event) -> tuple[int, int] | str | None:
    """Input while inside targeting mode: arrow/numpad keys move the aiming
    cursor, F confirms the shot, Escape cancels without firing. Returns a
    (dx, dy) cursor delta, "fire", "cancel", or None."""
    if isinstance(event, tcod.event.Quit):
        raise SystemExit()

    if isinstance(event, tcod.event.KeyDown):
        sym = event.sym

        if sym in MOVE_KEYS:
            return MOVE_KEYS[sym]

        if sym == tcod.event.KeySym.F:
            return "fire"

        if sym == tcod.event.KeySym.ESCAPE:
            return "cancel"

    return None


def handle_look_event(event: tcod.event.Event) -> tuple[int, int] | str | None:
    """Input while inside look mode: arrow keys move the cursor, Escape/L exit
    back to normal play (not "quit the game" - that's what Escape means outside
    look mode). Returns a (dx, dy) cursor delta, the string "exit", or None."""
    if isinstance(event, tcod.event.Quit):
        raise SystemExit()

    if isinstance(event, tcod.event.KeyDown):
        sym = event.sym

        if sym in MOVE_KEYS:
            return MOVE_KEYS[sym]

        if sym in (tcod.event.KeySym.ESCAPE, tcod.event.KeySym.L):
            return "exit"

    return None
