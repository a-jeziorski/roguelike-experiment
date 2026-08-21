"""Damage resolution between two fighters."""

from __future__ import annotations

from typing import TYPE_CHECKING

from content.schema import PEACEFUL_AI_TYPES

if TYPE_CHECKING:
    from engine.engine import Engine
    from engine.entity import Entity


def _apply_damage(
    engine: "Engine", attacker: "Entity", defender: "Entity", attack_value: int, verb: str
) -> None:
    # Triggers on the attack itself, not on damage dealt (a 0-damage hit
    # still counts) - matches "attacks the villagers," not "hurts the
    # villagers." Only the player's own attacks count; no monster ever
    # attacks a peaceful NPC today.
    if attacker is engine.player and defender.ai in PEACEFUL_AI_TYPES:
        engine.game_map.player_attacked_peaceful_npc = True

    damage = max(0, attack_value - defender.effective_defense)

    if damage > 0:
        defender.fighter.hp -= damage
        engine.message_log.add(
            f"{attacker.name} {verb} {defender.name} for {damage} damage.", category="combat"
        )
    else:
        engine.message_log.add(
            f"{attacker.name} {verb} {defender.name} but does no damage.", category="combat"
        )

    if defender.fighter.hp <= 0:
        engine.on_entity_death(defender)


def resolve_attack(engine: "Engine", attacker: "Entity", defender: "Entity") -> None:
    engine.melee_attack_events.append((defender.x, defender.y))
    _apply_damage(engine, attacker, defender, attacker.effective_attack, "hits")


def resolve_ranged_attack(engine: "Engine", attacker: "Entity", defender: "Entity") -> None:
    engine.ranged_attack_events.append((attacker.x, attacker.y, defender.x, defender.y))
    _apply_damage(engine, attacker, defender, attacker.effective_ranged_attack, "shoots")
