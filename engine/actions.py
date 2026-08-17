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


class MovementAction(Action):
    def __init__(self, dx: int, dy: int):
        self.dx = dx
        self.dy = dy

    def perform(self, engine: "Engine", entity: "Entity") -> None:
        dest_x, dest_y = entity.x + self.dx, entity.y + self.dy
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
                entity.fighter.attack += candidate.item.attack_bonus
                engine.message_log.add(
                    f"You equip the {candidate.name} (+{candidate.item.attack_bonus} attack)."
                )
                engine.game_map.entities.remove(candidate)
            else:
                entity.inventory.append(candidate)
                engine.game_map.entities.remove(candidate)
                engine.message_log.add(f"You picked up a {candidate.name}.")
            return

        engine.message_log.add("There is nothing here to pick up.")


class UseItemAction(Action):
    def perform(self, engine: "Engine", entity: "Entity") -> None:
        if not entity.inventory:
            engine.message_log.add("You have nothing to use.")
            return

        item_entity = entity.inventory.pop(0)
        heal = item_entity.item.heal_amount or 0
        entity.fighter.hp = min(entity.fighter.max_hp, entity.fighter.hp + heal)
        engine.message_log.add(f"You drink the {item_entity.name} and recover {heal} HP.")
