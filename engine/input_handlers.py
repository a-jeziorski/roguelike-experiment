"""Translates tcod key events into Actions."""

from __future__ import annotations

import tcod.event

from engine.actions import (
    Action,
    BumpAction,
    EscapeAction,
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
}


def handle_event(event: tcod.event.Event) -> Action | None:
    if isinstance(event, tcod.event.Quit):
        raise SystemExit()

    if isinstance(event, tcod.event.KeyDown):
        sym = event.sym

        if sym in MOVE_KEYS:
            dx, dy = MOVE_KEYS[sym]
            return BumpAction(dx, dy)

        if sym == tcod.event.KeySym.PERIOD:
            return WaitAction()

        if sym == tcod.event.KeySym.G:
            return PickupAction()

        if sym == tcod.event.KeySym.U:
            return UseItemAction()

        if sym == tcod.event.KeySym.R:
            return RestartAction()

        if sym == tcod.event.KeySym.ESCAPE:
            return EscapeAction()

    return None
