"""Player/monster actions. Each Action knows how to perform itself against an
Engine + acting Entity."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.combat import resolve_attack

if TYPE_CHECKING:
    from engine.engine import Engine
    from engine.entity import Entity


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

        if not engine.game_map.is_walkable(dest_x, dest_y):
            return
        if engine.game_map.blocking_entity_at(dest_x, dest_y) is not None:
            return
        entity.x, entity.y = dest_x, dest_y
        if entity is engine.player and (dest_x, dest_y) in engine.game_map.stairs:
            engine.on_player_reach_stairs(engine.game_map.stairs[(dest_x, dest_y)])


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


class PickupAction(Action):
    def perform(self, engine: "Engine", entity: "Entity") -> None:
        for candidate in list(engine.game_map.entities):
            if candidate.item is None or candidate.x != entity.x or candidate.y != entity.y:
                continue

            if candidate.item.attack_bonus:
                self._equip(engine, entity, candidate, slot="weapon")
            elif candidate.item.defense_bonus:
                self._equip(engine, entity, candidate, slot="armor")
            else:
                entity.inventory.append(candidate)
                engine.game_map.entities.remove(candidate)
                engine.message_log.add(f"You picked up a {candidate.name}.")
            return

        engine.message_log.add("There is nothing here to pick up.")

    def _equip(self, engine: "Engine", entity: "Entity", candidate: "Entity", slot: str) -> None:
        """Equips `candidate` into `slot` ("weapon" or "armor") if it's better
        than what's already there, dropping the replaced item back onto the
        map (visible, re-collectible) rather than destroying it. If it's not
        better, `candidate` is left untouched on the ground."""
        bonus_attr = "attack_bonus" if slot == "weapon" else "defense_bonus"
        new_bonus = getattr(candidate.item, bonus_attr)

        current = entity.equipped_weapon if slot == "weapon" else entity.equipped_armor
        current_bonus = getattr(current.item, bonus_attr) if current is not None else 0

        if current is not None and new_bonus <= current_bonus:
            engine.message_log.add(f"Your current {slot} is already at least as good.")
            return

        engine.game_map.entities.remove(candidate)
        if slot == "weapon":
            entity.equipped_weapon = candidate
        else:
            entity.equipped_armor = candidate

        bonus_word = "attack" if slot == "weapon" else "defense"
        engine.message_log.add(f"You equip the {candidate.name} (+{new_bonus} {bonus_word}).")

        if current is not None:
            current.x, current.y = entity.x, entity.y
            engine.game_map.entities.append(current)
            engine.message_log.add(f"You drop your old {slot}, the {current.name}.")


class UseItemAction(Action):
    """Drinks the first usable (healing) item in inventory. Keys are never
    selected here - they're consumed automatically when unlocking a matching
    door (see MovementAction), not "used" on demand."""

    def perform(self, engine: "Engine", entity: "Entity") -> None:
        item_entity = next((it for it in entity.inventory if it.item.heal_amount), None)
        if item_entity is None:
            engine.message_log.add("You have nothing to use.")
            return

        entity.inventory.remove(item_entity)
        heal = item_entity.item.heal_amount
        entity.fighter.hp = min(entity.fighter.max_hp, entity.fighter.hp + heal)
        engine.message_log.add(f"You drink the {item_entity.name} and recover {heal} HP.")
