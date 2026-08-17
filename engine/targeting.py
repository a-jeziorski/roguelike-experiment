"""Pure helpers for ranged-weapon target selection, decoupled from
rendering/input so they're unit-testable without a console - same pattern as
content/loader.py and Engine."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.entity import Entity
    from engine.game_map import GameMap


def in_range(shooter: "Entity", x: int, y: int, max_range: int) -> bool:
    return max(abs(x - shooter.x), abs(y - shooter.y)) <= max_range


def is_valid_target(game_map: "GameMap", shooter: "Entity", x: int, y: int, max_range: int) -> bool:
    """Whether `shooter` could hit something by firing at (x, y): in bounds,
    within range, currently visible (reusing the same FOV array everything
    else trusts for line-of-sight), and a living, blocking entity is there."""
    if not game_map.in_bounds(x, y):
        return False
    if not in_range(shooter, x, y, max_range):
        return False
    if not game_map.visible[x, y]:
        return False
    target = game_map.blocking_entity_at(x, y)
    return target is not None and target is not shooter and target.fighter is not None


def find_nearest_target(game_map: "GameMap", shooter: "Entity", max_range: int) -> "Entity | None":
    """The closest visible, in-range, attackable entity to `shooter` - used to
    default the aiming cursor's starting position."""
    candidates = [
        e
        for e in game_map.entities
        if e is not shooter
        and e.fighter is not None
        and e.blocks_movement
        and game_map.visible[e.x, e.y]
        and in_range(shooter, e.x, e.y, max_range)
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda e: max(abs(e.x - shooter.x), abs(e.y - shooter.y)))
