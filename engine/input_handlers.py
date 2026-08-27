"""Translates tcod key events into Actions."""

from __future__ import annotations

import tcod.event

from engine.actions import (
    Action,
    BumpAction,
    CyclePotionKindAction,
    EscapeAction,
    FireModeAction,
    HelpAction,
    LookAction,
    MuteAction,
    PickupAction,
    QuestLogAction,
    RestartAction,
    SaveGameAction,
    ScrollLogAction,
    ShopAction,
    TalkAction,
    TrainerAction,
    UseItemAction,
    UseSkillAction,
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

        if sym == tcod.event.KeySym.C:
            return CyclePotionKindAction()

        if sym == tcod.event.KeySym.R:
            return RestartAction()

        if sym == tcod.event.KeySym.L:
            return LookAction()

        if sym == tcod.event.KeySym.F:
            return FireModeAction()

        if sym == tcod.event.KeySym.T:
            return TalkAction()

        if sym == tcod.event.KeySym.Q:
            return QuestLogAction()

        if sym == tcod.event.KeySym.B:
            return ShopAction()

        if sym == tcod.event.KeySym.P:
            return TrainerAction()

        if sym == tcod.event.KeySym.S:
            return SaveGameAction()

        if sym == tcod.event.KeySym.H:
            return HelpAction()

        if sym == tcod.event.KeySym.M:
            return MuteAction()

        # Fixed 1:1 key bindings for the two shipped active-skill perks
        # (see content/schema.py's PerkDef.skill_effect, Engine.use_skill)
        # - not a scalable hotbar, just direct bindings, since there are
        # only two so far. Revisit if a third ever ships.
        if sym == tcod.event.KeySym.W:
            return UseSkillAction("second_wind")

        if sym == tcod.event.KeySym.K:
            return UseSkillAction("ground_pound")

        if sym == tcod.event.KeySym.PAGEUP:
            return ScrollLogAction(10)

        if sym == tcod.event.KeySym.PAGEDOWN:
            return ScrollLogAction(-10)

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


def handle_quest_log_event(event: tcod.event.Event) -> str | None:
    """Input while inside the quest log screen: up/down (arrows or numpad)
    move the selection, Enter/KP_Enter pins the selected quest as active,
    Escape/Q exit back to normal play. Returns "up", "down", "select",
    "exit", or None."""
    if isinstance(event, tcod.event.Quit):
        raise SystemExit()

    if isinstance(event, tcod.event.KeyDown):
        sym = event.sym

        if sym in (tcod.event.KeySym.UP, tcod.event.KeySym.KP_8):
            return "up"

        if sym in (tcod.event.KeySym.DOWN, tcod.event.KeySym.KP_2):
            return "down"

        if sym in (tcod.event.KeySym.RETURN, tcod.event.KeySym.KP_ENTER):
            return "select"

        if sym in (tcod.event.KeySym.ESCAPE, tcod.event.KeySym.Q):
            return "exit"

    return None


def handle_continue_prompt_event(event: tcod.event.Event) -> str | None:
    """Input while inside the startup continue-saved-game prompt: Y
    continues, N (or Escape - same "give up on this screen" meaning as
    every other mode's Escape binding) starts a new game. Returns "yes",
    "no", or None."""
    if isinstance(event, tcod.event.Quit):
        raise SystemExit()

    if isinstance(event, tcod.event.KeyDown):
        sym = event.sym

        if sym == tcod.event.KeySym.Y:
            return "yes"

        if sym in (tcod.event.KeySym.N, tcod.event.KeySym.ESCAPE):
            return "no"

    return None


def handle_shop_event(event: tcod.event.Event) -> str | None:
    """Input while inside the shop screen: up/down (arrows or numpad) move
    the selection, Enter/KP_Enter buys the selected item, Escape/B exit back
    to normal play. Returns "up", "down", "buy", "exit", or None."""
    if isinstance(event, tcod.event.Quit):
        raise SystemExit()

    if isinstance(event, tcod.event.KeyDown):
        sym = event.sym

        if sym in (tcod.event.KeySym.UP, tcod.event.KeySym.KP_8):
            return "up"

        if sym in (tcod.event.KeySym.DOWN, tcod.event.KeySym.KP_2):
            return "down"

        if sym in (tcod.event.KeySym.RETURN, tcod.event.KeySym.KP_ENTER):
            return "buy"

        if sym in (tcod.event.KeySym.ESCAPE, tcod.event.KeySym.B):
            return "exit"

    return None


def handle_trainer_event(event: tcod.event.Event) -> str | None:
    """Input while inside the trainer screen: up/down (arrows or numpad)
    move the selection, Enter/KP_Enter learns the selected perk, Escape/P
    exit back to normal play. Returns "up", "down", "learn", "exit", or
    None - same shape as handle_shop_event."""
    if isinstance(event, tcod.event.Quit):
        raise SystemExit()

    if isinstance(event, tcod.event.KeyDown):
        sym = event.sym

        if sym in (tcod.event.KeySym.UP, tcod.event.KeySym.KP_8):
            return "up"

        if sym in (tcod.event.KeySym.DOWN, tcod.event.KeySym.KP_2):
            return "down"

        if sym in (tcod.event.KeySym.RETURN, tcod.event.KeySym.KP_ENTER):
            return "learn"

        if sym in (tcod.event.KeySym.ESCAPE, tcod.event.KeySym.P):
            return "exit"

    return None


def handle_help_event(event: tcod.event.Event) -> str | None:
    """Input while inside the help screen: Escape/H exit back to normal
    play. No selection/cursor state - it's a static reference sheet, same
    shape as run_continue_prompt but simpler still (no yes/no choice
    either). Returns "exit" or None."""
    if isinstance(event, tcod.event.Quit):
        raise SystemExit()

    if isinstance(event, tcod.event.KeyDown):
        sym = event.sym

        if sym in (tcod.event.KeySym.ESCAPE, tcod.event.KeySym.H):
            return "exit"

    return None
