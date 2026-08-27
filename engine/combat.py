"""Damage resolution between two fighters."""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from content.schema import EFFECT_POISON, EFFECT_STUN, EFFECT_WEAKEN, PEACEFUL_AI_TYPES
from engine.entity import ActiveEffect

if TYPE_CHECKING:
    from engine.engine import Engine
    from engine.entity import Entity

# The message logged the instant an effect is inflicted (distinct from
# _tick_active_effects' own per-turn message, e.g. poison's "writhes from
# poison, taking N damage") - one per EffectKind, since each reads
# differently as a fresh affliction.
_EFFECT_INFLICT_MESSAGES = {
    EFFECT_POISON: "{name} is poisoned!",
    EFFECT_STUN: "{name} is stunned!",
    EFFECT_WEAKEN: "{name} is weakened!",
}

# Global on/off switch for the variance layer below - flip to False to
# fully restore the original deterministic formula (max(0, attack -
# defense), no randomness anywhere in combat) with no other code changes
# needed. Kept as a plain module constant rather than buried in Engine
# state specifically so disabling it is a one-line revert, not a design
# to unwind - this project has otherwise been fully deterministic in
# combat on purpose, and this is explicitly a "try it and see" addition.
#
# Applies symmetrically to attacker and defender, player or monster alike
# (same reasoning as poison being symmetric) - a fight staying
# unpredictable in both directions is the point, not just "the player
# gets lucky sometimes." Values are deliberately modest and roughly
# offsetting in aggregate: DODGE_CHANCE alone would lengthen an average
# fight by ~11% (1/(1-0.1)); CRIT_CHANCE/CRIT_MULTIPLIER alone adds ~5%
# average damage per hit - together they add real per-encounter texture
# without materially reflowing the hits-to-kill math
# docs/content_design_process.md's balance section already establishes,
# and leave room for a future perk (e.g. a ranged crit-chance bonus) to
# matter by not already maxing out the base rate.
COMBAT_VARIANCE_ENABLED = True
DODGE_CHANCE = 0.10
CRIT_CHANCE = 0.10
CRIT_MULTIPLIER = 1.5


def _trinket_bonus(entity: "Entity", kind: str) -> float:
    """The live rate bonus from entity's equipped trinket, if it matches
    kind ("crit_chance"/"dodge_chance") - 0.0 if no trinket is equipped,
    or the equipped one boosts something else. A trinket never touches
    effective_attack/defense (see engine/entity.py's Entity.equipped_trinket),
    so this - not effective_attack - is the whole read path for the
    combat-facing half of a trinket's effect (the other half, xp_gain, is
    read directly by Engine._award_xp instead, since it has nothing to do
    with a single attack)."""
    trinket = entity.equipped_trinket
    if trinket is None or trinket.item.trinket_effect != kind:
        return 0.0
    return trinket.item.trinket_bonus or 0.0


def _maybe_apply_weapon_affix(engine: "Engine", attacker: "Entity", defender: "Entity") -> None:
    """An offensive affix proc - attacker's equipped weapon (if any) has an
    affix_chance probability of inflicting affix_effect on defender,
    whenever a hit deals damage (see _apply_damage's damage > 0 gate,
    mirrored here since this is called from inside that same block). Reuses
    Fighter.active_effects/ActiveEffect exactly like a monster's innate
    inflicts_effect (§0t) - refreshes, never stacks, and coexists
    independently alongside any different kind already active. Monsters
    never equip weapons in shipped content, so this never doubles up with
    attacker.inflicts_effect in practice, but nothing here assumes that."""
    weapon = attacker.equipped_weapon
    if weapon is None or weapon.item.affix_effect is None:
        return
    if random.random() >= weapon.item.affix_chance:
        return
    defender.fighter.active_effects[weapon.item.affix_effect] = ActiveEffect(
        potency=weapon.item.affix_potency or 0, turns_remaining=weapon.item.affix_duration,
    )
    engine.message_log.add(
        _EFFECT_INFLICT_MESSAGES[weapon.item.affix_effect].format(name=defender.name), category="combat",
    )


def _maybe_apply_armor_affix(engine: "Engine", attacker: "Entity", defender: "Entity") -> None:
    """A defensive/retaliation affix proc - the mirror of
    _maybe_apply_weapon_affix: defender's equipped armor (if any) has an
    affix_chance probability of striking *back*, inflicting affix_effect
    on attacker instead. Triggers off the same "a hit landed" moment as
    the weapon affix, not off whether defender survives it."""
    armor = defender.equipped_armor
    if armor is None or armor.item.affix_effect is None:
        return
    if random.random() >= armor.item.affix_chance:
        return
    attacker.fighter.active_effects[armor.item.affix_effect] = ActiveEffect(
        potency=armor.item.affix_potency or 0, turns_remaining=armor.item.affix_duration,
    )
    engine.message_log.add(
        _EFFECT_INFLICT_MESSAGES[armor.item.affix_effect].format(name=attacker.name), category="combat",
    )


def _apply_damage(
    engine: "Engine", attacker: "Entity", defender: "Entity", attack_value: int, verb: str
) -> None:
    # Triggers on the attack itself, not on damage dealt (a 0-damage hit
    # still counts) - matches "attacks the villagers," not "hurts the
    # villagers." Only the player's own attacks count; no monster ever
    # attacks a peaceful NPC today. Also records the hit for an
    # intimidate-quest target (QuestLog.record_entity_intimidated) - same
    # condition, unconditional even if this hit turns out lethal (see
    # QuestLog.fail_intimidate_by_death, triggered separately below via
    # on_entity_death). trigger_guard_hostility arms/re-arms this map's
    # cooldown (GameMap.guards_hostile) - permanent instead if the hit
    # turns out lethal, but that's decided later, in on_entity_death.
    # Deliberately unconditional on the dodge roll below too - this is
    # about the attack being *attempted*, not whether it connects, same
    # "0-damage still counts" philosophy already established.
    if attacker is engine.player and defender.ai in PEACEFUL_AI_TYPES:
        engine.game_map.trigger_guard_hostility(engine.clock)
        engine.quest_log.record_entity_intimidated(defender.entity_id)

    dodge_chance = DODGE_CHANCE + _trinket_bonus(defender, "dodge_chance")
    if COMBAT_VARIANCE_ENABLED and random.random() < dodge_chance:
        engine.message_log.add(
            f"{defender.name} dodges {attacker.name}'s attack.", category="combat"
        )
        return

    damage = max(0, attack_value - defender.effective_defense)
    is_critical = False
    crit_chance = CRIT_CHANCE + _trinket_bonus(attacker, "crit_chance")
    if COMBAT_VARIANCE_ENABLED and damage > 0 and random.random() < crit_chance:
        # ceil, not round: a crit must always deal strictly more than the
        # base hit would have, even at low single-digit damage where
        # round()'s banker's-rounding could otherwise land back on the
        # same integer.
        damage = math.ceil(damage * CRIT_MULTIPLIER)
        is_critical = True

    if damage > 0:
        defender.fighter.hp -= damage
        engine.message_log.add(
            f"{attacker.name} {verb} {defender.name} for {damage} damage.", category="combat"
        )
        if is_critical:
            engine.message_log.add("Critical hit!", category="combat")
        if attacker.is_enraged:
            engine.message_log.add(f"{attacker.name} fights with berserk fury!", category="combat")
        # Refreshes, never stacks: a repeat hit of the same kind overwrites
        # that dict entry rather than adding to it (see
        # Fighter.active_effects) - a different kind coexists independently.
        if attacker.inflicts_effect:
            defender.fighter.active_effects[attacker.inflicts_effect] = ActiveEffect(
                potency=attacker.inflicts_potency or 0,
                turns_remaining=attacker.inflicts_duration,
            )
            engine.message_log.add(
                _EFFECT_INFLICT_MESSAGES[attacker.inflicts_effect].format(name=defender.name),
                category="combat",
            )
        _maybe_apply_weapon_affix(engine, attacker, defender)
        _maybe_apply_armor_affix(engine, attacker, defender)
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
