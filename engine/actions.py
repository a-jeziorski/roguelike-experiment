"""Player/monster actions. Each Action knows how to perform itself against an
Engine + acting Entity."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.combat import resolve_attack, resolve_ranged_attack
from engine.entity import potion_kind
from engine.targeting import is_valid_target

if TYPE_CHECKING:
    from engine.engine import Engine
    from engine.entity import Entity

DEFAULT_RANGED_RANGE = 5


class Action:
    def perform(self, engine: "Engine", entity: "Entity") -> None:
        raise NotImplementedError


class EscapeAction(Action):
    def perform(self, engine: "Engine", entity: "Entity") -> None:
        raise SystemExit()


class WaitAction(Action):
    def perform(self, engine: "Engine", entity: "Entity") -> None:
        pass


class RestartAction(Action):
    """Begins a fresh run. Only meaningful when the game has ended (dead/won);
    main.py is responsible for gating that, since a normal turn action would be
    silently dropped by Engine.process_turn once the game is no longer playing."""

    def perform(self, engine: "Engine", entity: "Entity") -> None:
        engine.restart()


class LookAction(Action):
    """Enters look mode: a free cursor for inspecting tiles that costs no turn.
    main.py recognizes this before it would ever reach Engine.process_turn and
    runs its own nested input loop instead - perform() is never actually called
    in practice, kept only so LookAction satisfies the Action interface."""

    def perform(self, engine: "Engine", entity: "Entity") -> None:
        pass


class FireModeAction(Action):
    """Enters targeting mode: an aiming cursor for firing a ranged weapon.
    main.py recognizes this before it would ever reach Engine.process_turn
    (aiming itself costs no turn, only the shot does) and runs its own
    nested input loop instead - perform() is never actually called in
    practice, kept only so FireModeAction satisfies the Action interface."""

    def perform(self, engine: "Engine", entity: "Entity") -> None:
        pass


class QuestLogAction(Action):
    """Enters the quest log screen: a free, non-turn screen for reviewing
    known quests and changing which one is pinned to the HUD. main.py
    recognizes this before it would ever reach Engine.process_turn and runs
    its own nested input loop instead - perform() is never actually called
    in practice, kept only so QuestLogAction satisfies the Action interface."""

    def perform(self, engine: "Engine", entity: "Entity") -> None:
        pass


class HelpAction(Action):
    """Enters the help screen: a free, non-turn reference sheet of every
    keybinding in the game. main.py recognizes this before it would ever
    reach Engine.process_turn and runs its own nested input loop instead -
    perform() is never actually called in practice, kept only so
    HelpAction satisfies the Action interface. Unlike every other free
    screen action, main.py dispatches this one unconditionally, not
    gated on game_state == "playing" - a reference sheet is exactly as
    useful (arguably more so) from the death screen as mid-run."""

    def perform(self, engine: "Engine", entity: "Entity") -> None:
        pass


class MuteAction(Action):
    """Toggles audio muting - free, costs no turn. Same "recognized before
    Engine.process_turn, perform() never actually called" shape as
    HelpAction/ScrollLogAction: main.py flips engine/audio.py's
    SoundManager.muted directly, since Engine itself has no notion of
    audio at all."""

    def perform(self, engine: "Engine", entity: "Entity") -> None:
        pass


class ToggleDecorationsAction(Action):
    """Toggles display of purely cosmetic map decorations (furniture,
    plants - see content.schema.DecorationKind) - free, costs no turn.
    Same shape as MuteAction: main.py flips its own local
    show_decorations bool directly, since Engine has no notion of display
    preferences at all."""

    def perform(self, engine: "Engine", entity: "Entity") -> None:
        pass


class ScrollLogAction(Action):
    """Scrolls the message log panel by `lines` (positive = further back
    into history, negative = toward the latest message) - free, costs no
    turn. main.py recognizes this before it would ever reach
    Engine.process_turn and adjusts its own local scroll-offset state
    directly instead; perform() is never actually called in practice, kept
    only so ScrollLogAction satisfies the Action interface."""

    def __init__(self, lines: int):
        self.lines = lines

    def perform(self, engine: "Engine", entity: "Entity") -> None:
        pass


class SaveGameAction(Action):
    """Saves the current run to disk - free, costs no turn, same shape as
    QuestLogAction/LookAction. main.py recognizes this before it would ever
    reach Engine.process_turn and writes the save file directly instead;
    perform() is never actually called in practice, kept only so
    SaveGameAction satisfies the Action interface."""

    def perform(self, engine: "Engine", entity: "Entity") -> None:
        pass


class ShopAction(Action):
    """Enters the shop screen: a free, non-turn screen for buying from a
    nearby shopkeeper. main.py recognizes this before it would ever reach
    Engine.process_turn and runs its own nested input loop instead -
    perform() is never actually called in practice, kept only so ShopAction
    satisfies the Action interface."""

    def perform(self, engine: "Engine", entity: "Entity") -> None:
        pass


class TrainerAction(Action):
    """Enters the trainer screen: a free, non-turn screen for learning perks
    from a nearby Trainer NPC. main.py recognizes this before it would ever
    reach Engine.process_turn and runs its own nested input loop instead -
    perform() is never actually called in practice, kept only so
    TrainerAction satisfies the Action interface."""

    def perform(self, engine: "Engine", entity: "Entity") -> None:
        pass


class TalkAction(Action):
    """Talks to an adjacent villager-type NPC - free, costs no turn, same
    shape as LookAction. main.py recognizes this before it would ever reach
    Engine.process_turn and calls Engine.talk_to_adjacent() directly instead;
    perform() is never actually called in practice, kept only so TalkAction
    satisfies the Action interface."""

    def perform(self, engine: "Engine", entity: "Entity") -> None:
        pass


class FireAction(Action):
    """Fires the equipped ranged weapon at (target_x, target_y). Unlike
    FireModeAction, this is a real turn action - dispatched through the
    normal Engine.process_turn path once a target is confirmed."""

    def __init__(self, target_x: int, target_y: int):
        self.target_x = target_x
        self.target_y = target_y

    def perform(self, engine: "Engine", entity: "Entity") -> None:
        weapon = entity.equipped_ranged_weapon
        if weapon is None:
            if entity is engine.player:
                engine.message_log.add("You have no ranged weapon equipped.")
            return

        ammo = next((it for it in entity.inventory if it.item.is_ammo), None)
        if ammo is None:
            if entity is engine.player:
                engine.message_log.add("You have no ammo.")
            return

        max_range = weapon.item.range or DEFAULT_RANGED_RANGE
        if not is_valid_target(engine.game_map, entity, self.target_x, self.target_y, max_range):
            if entity is engine.player:
                engine.message_log.add("No clear target there.")
            return

        target = engine.game_map.blocking_entity_at(self.target_x, self.target_y)

        ammo.item.quantity -= 1
        if ammo.item.quantity <= 0:
            entity.inventory.remove(ammo)

        resolve_ranged_attack(engine, attacker=entity, defender=target)


class MovementAction(Action):
    def __init__(self, dx: int, dy: int):
        self.dx = dx
        self.dy = dy

    def perform(self, engine: "Engine", entity: "Entity") -> None:
        dest_x, dest_y = entity.x + self.dx, entity.y + self.dy

        required_key_id = engine.game_map.locked_doors.get((dest_x, dest_y))
        if required_key_id is not None:
            matching_key = next(
                (it for it in entity.inventory if it.item and it.item.key_id == required_key_id),
                None,
            )
            if matching_key is None:
                if entity is engine.player:
                    engine.message_log.add("The door is locked.")
                return
            entity.inventory.remove(matching_key)
            engine.game_map.unlock_door(dest_x, dest_y)
            if entity is engine.player:
                engine.message_log.add(f"You use the {matching_key.name} to unlock the door.")
                engine.sound_events.append("door_unlock")

        if not engine.game_map.in_bounds(dest_x, dest_y):
            if entity is engine.player and engine.game_map.open_boundary:
                engine.on_player_reach_map_edge()
            return
        if not engine.game_map.is_walkable(dest_x, dest_y):
            return
        if engine.game_map.blocking_entity_at(dest_x, dest_y) is not None:
            return
        entity.x, entity.y = dest_x, dest_y
        if entity is engine.player and (dest_x, dest_y) in engine.game_map.stairs:
            kind = engine.game_map.kinds[dest_x, dest_y]
            engine.on_player_reach_stairs(engine.game_map.stairs[(dest_x, dest_y)], kind)
        if entity is engine.player and (dest_x, dest_y) in engine.game_map.dungeon_entrances:
            engine.pending_dungeon_entry = engine.game_map.dungeon_entrances[(dest_x, dest_y)]


class MeleeAction(Action):
    def __init__(self, dx: int, dy: int):
        self.dx = dx
        self.dy = dy

    def perform(self, engine: "Engine", entity: "Entity") -> None:
        dest_x, dest_y = entity.x + self.dx, entity.y + self.dy
        target = engine.game_map.blocking_entity_at(dest_x, dest_y)
        if target is None or target.fighter is None:
            return
        resolve_attack(engine, attacker=entity, defender=target)


class BumpAction(Action):
    """Moves into a tile, or attacks whatever is blocking it."""

    def __init__(self, dx: int, dy: int):
        self.dx = dx
        self.dy = dy

    def perform(self, engine: "Engine", entity: "Entity") -> None:
        dest_x, dest_y = entity.x + self.dx, entity.y + self.dy
        if engine.game_map.blocking_entity_at(dest_x, dest_y) is not None:
            MeleeAction(self.dx, self.dy).perform(engine, entity)
        else:
            MovementAction(self.dx, self.dy).perform(engine, entity)


_SLOT_ENTITY_ATTR = {
    "weapon": "equipped_weapon",
    "armor": "equipped_armor",
    "ranged": "equipped_ranged_weapon",
}
_SLOT_BONUS_ATTR = {
    "weapon": "attack_bonus",
    "armor": "defense_bonus",
    "ranged": "ranged_attack_bonus",
}
_SLOT_BONUS_WORD = {
    "weapon": "attack",
    "armor": "defense",
    "ranged": "ranged attack",
}
_TRINKET_EFFECT_WORD = {
    "crit_chance": "crit chance",
    "dodge_chance": "dodge chance",
    "xp_gain": "XP gain",
}


class PickupAction(Action):
    def perform(self, engine: "Engine", entity: "Entity") -> None:
        for candidate in list(engine.game_map.entities):
            if candidate.item is None or candidate.x != entity.x or candidate.y != entity.y:
                continue

            if candidate.item.attack_bonus:
                self._equip(engine, entity, candidate, slot="weapon")
            elif candidate.item.defense_bonus:
                self._equip(engine, entity, candidate, slot="armor")
            elif candidate.item.ranged_attack_bonus:
                self._equip(engine, entity, candidate, slot="ranged")
            elif candidate.item.trinket_effect is not None:
                self._equip_trinket(engine, entity, candidate)
            elif candidate.item.is_ammo:
                self._stack_ammo(engine, entity, candidate)
            elif candidate.item.gold_amount:
                self._collect_gold(engine, entity, candidate)
            else:
                entity.inventory.append(candidate)
                engine.game_map.entities.remove(candidate)
                engine.message_log.add(f"You picked up a {candidate.name}.")
                engine.sound_events.append("pickup_item")
            return

        engine.message_log.add("There is nothing here to pick up.")

    def _equip(self, engine: "Engine", entity: "Entity", candidate: "Entity", slot: str) -> None:
        """Equips `candidate` into `slot` ("weapon"/"armor"/"ranged") if it's
        better than what's already there, dropping the replaced item back
        onto the map (visible, re-collectible) rather than destroying it. If
        it's not better, `candidate` is left untouched on the ground."""
        entity_attr = _SLOT_ENTITY_ATTR[slot]
        bonus_attr = _SLOT_BONUS_ATTR[slot]
        new_bonus = getattr(candidate.item, bonus_attr)

        current = getattr(entity, entity_attr)
        current_bonus = getattr(current.item, bonus_attr) if current is not None else 0

        if current is not None and new_bonus <= current_bonus:
            engine.message_log.add(f"Your current {slot} is already at least as good.")
            return

        engine.game_map.entities.remove(candidate)
        setattr(entity, entity_attr, candidate)

        bonus_word = _SLOT_BONUS_WORD[slot]
        engine.message_log.add(f"You equip the {candidate.name} (+{new_bonus} {bonus_word}).")
        engine.sound_events.append("pickup_item")

        if current is not None:
            current.x, current.y = entity.x, entity.y
            engine.game_map.entities.append(current)
            engine.message_log.add(f"You drop your old {slot}, the {current.name}.")

    def _equip_trinket(self, engine: "Engine", entity: "Entity", candidate: "Entity") -> None:
        """Trinkets aren't comparable by one flat bonus number the way
        weapon/armor/ranged are (see _equip) - a crit-chance trinket and
        an XP-gain trinket aren't fungible. Auto-equips when nothing's
        equipped yet, or the candidate shares the current trinket's exact
        trinket_effect kind and beats it; any other case (a different
        kind, or the same kind but not better) is left on the ground,
        same "not obviously better, don't swap" outcome _equip already
        gives weapon/armor/ranged."""
        current = entity.equipped_trinket
        is_better = current is None or (
            candidate.item.trinket_effect == current.item.trinket_effect
            and candidate.item.trinket_bonus > current.item.trinket_bonus
        )
        if not is_better:
            engine.message_log.add("Your current trinket is already at least as good.")
            return

        engine.game_map.entities.remove(candidate)
        entity.equipped_trinket = candidate

        effect_word = _TRINKET_EFFECT_WORD[candidate.item.trinket_effect]
        bonus_pct = round(candidate.item.trinket_bonus * 100)
        engine.message_log.add(f"You equip the {candidate.name} (+{bonus_pct}% {effect_word}).")
        engine.sound_events.append("pickup_item")

        if current is not None:
            current.x, current.y = entity.x, entity.y
            engine.game_map.entities.append(current)
            engine.message_log.add(f"You drop your old trinket, the {current.name}.")

    def _stack_ammo(self, engine: "Engine", entity: "Entity", candidate: "Entity") -> None:
        """Merges a new ammo pickup into an existing stack in inventory
        (adding quantities) instead of cluttering inventory with a separate
        entry per pickup."""
        existing = next((it for it in entity.inventory if it.item.is_ammo), None)
        engine.game_map.entities.remove(candidate)
        engine.sound_events.append("pickup_item")

        if existing is not None:
            existing.item.quantity += candidate.item.quantity
            engine.message_log.add(
                f"You pick up {candidate.item.quantity} more {candidate.name} "
                f"({existing.item.quantity} total)."
            )
        else:
            entity.inventory.append(candidate)
            engine.message_log.add(f"You picked up {candidate.item.quantity}x {candidate.name}.")

    def _collect_gold(self, engine: "Engine", entity: "Entity", candidate: "Entity") -> None:
        """Folds a gold pickup straight into entity.gold - a scalar player
        stat, not an inventory entry, so unlike every other branch above this
        one never touches entity.inventory."""
        entity.gold += candidate.item.gold_amount
        engine.game_map.entities.remove(candidate)
        engine.sound_events.append("pickup_gold")
        engine.message_log.add(
            f"You pick up {candidate.item.gold_amount} gold ({entity.gold} total)."
        )


class UseItemAction(Action):
    """Drinks the potion of entity.selected_potion_kind (see POTION_KINDS/
    potion_kind, engine/entity.py), cycled via CyclePotionKindAction below.
    Keys are never selected here - they're consumed automatically when
    unlocking a matching door (see MovementAction), not "used" on demand."""

    def perform(self, engine: "Engine", entity: "Entity") -> None:
        kind = entity.selected_potion_kind
        item_entity = next(
            (it for it in entity.inventory if potion_kind(it.item) == kind), None
        )
        if item_entity is None:
            engine.message_log.add(f"You have no {kind} potion to use.")
            return

        if kind == "teleport" and engine.is_overworld:
            engine.message_log.add("You're already on the surface.")
            return

        entity.inventory.remove(item_entity)
        if kind == "healing":
            heal = item_entity.item.heal_amount
            entity.fighter.hp = min(entity.fighter.max_hp, entity.fighter.hp + heal)
            engine.message_log.add(f"You drink the {item_entity.name} and recover {heal} HP.")
        elif kind == "teleport":
            engine.message_log.add(
                f"You drink the {item_entity.name} and the world lurches sideways."
            )
            engine.wants_overworld = True


class UseSkillAction(Action):
    """Manually triggers a learned active-skill perk (see
    content/schema.py's PerkDef.skill_effect, Engine.use_skill) - a real,
    turn-costing action like UseItemAction above, not a free action like
    Talk/Look. main.py binds one fixed key per shipped skill (not a
    scalable hotbar - see engine/input_handlers.py) since there are only
    two of them so far."""

    def __init__(self, perk_id: str):
        self.perk_id = perk_id

    def perform(self, engine: "Engine", entity: "Entity") -> None:
        engine.use_skill(entity, self.perk_id)


class CyclePotionKindAction(Action):
    """Cycles entity.selected_potion_kind through POTION_KINDS - free, costs
    no turn, same shape as TalkAction. main.py recognizes this before it
    would ever reach Engine.process_turn and calls
    Engine.cycle_selected_potion_kind() directly instead; perform() is never
    actually called in practice, kept only so CyclePotionKindAction
    satisfies the Action interface."""

    def perform(self, engine: "Engine", entity: "Entity") -> None:
        pass
