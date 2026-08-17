"""Damage resolution between two fighters."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.engine import Engine
    from engine.entity import Entity


def resolve_attack(engine: "Engine", attacker: "Entity", defender: "Entity") -> None:
    damage = max(0, attacker.fighter.attack - defender.fighter.defense)

    if damage > 0:
        defender.fighter.hp -= damage
        engine.message_log.add(f"{attacker.name} hits {defender.name} for {damage} damage.")
    else:
        engine.message_log.add(f"{attacker.name} attacks {defender.name} but does no damage.")

    if defender.fighter.hp <= 0:
        engine.on_entity_death(defender)
