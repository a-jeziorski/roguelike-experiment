"""Owns game state and the turn loop. Rendering/windowing is driven from main.py
so Engine itself stays testable without an SDL window."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.actions import Action, MovementAction
from engine.combat import resolve_attack
from engine.entity import Entity
from engine.game_map import GameMap, build_game_map

if TYPE_CHECKING:
    from content.loader import Catalog, ParsedLevel

HOSTILE_BASIC_AI = "hostile_basic"


class MessageLog:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def add(self, text: str) -> None:
        self.messages.append(text)


class Engine:
    def __init__(
        self,
        game_map: GameMap,
        player: Entity,
        level_name: str,
        *,
        catalog: "Catalog | None" = None,
        levels: "dict[str, ParsedLevel] | None" = None,
        starting_level: "ParsedLevel | None" = None,
    ):
        self.game_map = game_map
        self.player = player
        self.level_name = level_name
        self.message_log = MessageLog()
        self.game_state = "playing"  # "playing" | "dead" | "won"
        # Needed to resolve a stairway's destination id into content when
        # descending; only required if the dungeon actually branches/continues.
        self.catalog = catalog
        self.levels = levels
        # The level a fresh run begins at, kept so restart() can rebuild from
        # scratch; only required if restarting is supported for this Engine.
        self.starting_level = starting_level

        self.game_map.update_fov((player.x, player.y))
        self.message_log.add(f"You enter {level_name}.")

    def on_entity_death(self, entity: Entity) -> None:
        if entity is self.player:
            self.message_log.add("You have died...")
            self.game_state = "dead"
        else:
            self.message_log.add(f"The {entity.name} dies.")
            if entity in self.game_map.entities:
                self.game_map.entities.remove(entity)

    def on_player_reach_stairs(self, next_level_id: str | None) -> None:
        if next_level_id is None:
            self.message_log.add("You ascend the stairs and escape the dungeon. You win!")
            self.game_state = "won"
            return

        next_level = self.levels[next_level_id]
        self.game_map, self.player = build_game_map(next_level, self.catalog, player=self.player)
        self.level_name = next_level.name
        self.message_log.add(f"You descend into {next_level.name}.")
        self.game_map.update_fov((self.player.x, self.player.y))

    def restart(self) -> None:
        """Begins a fresh run from the starting level: a brand-new player (full
        hp, no inventory or picked-up attack bonus), a freshly built map (killed
        monsters and taken items restored), and a cleared message log."""
        self.game_map, self.player = build_game_map(self.starting_level, self.catalog)
        self.level_name = self.starting_level.name
        self.game_state = "playing"
        self.message_log = MessageLog()
        self.game_map.update_fov((self.player.x, self.player.y))
        self.message_log.add(f"You enter {self.level_name}.")

    def _perform_ai(self, entity: Entity) -> None:
        if entity.ai != HOSTILE_BASIC_AI:
            return
        if not self.game_map.visible[entity.x, entity.y]:
            return

        dx = self.player.x - entity.x
        dy = self.player.y - entity.y
        distance = max(abs(dx), abs(dy))

        if distance <= 1:
            resolve_attack(self, attacker=entity, defender=self.player)
        else:
            step_x = (dx > 0) - (dx < 0)
            step_y = (dy > 0) - (dy < 0)
            MovementAction(step_x, step_y).perform(self, entity)

    def _handle_enemy_turns(self) -> None:
        for entity in list(self.game_map.entities):
            if entity is self.player or not entity.is_alive or entity.ai is None:
                continue
            self._perform_ai(entity)

    def process_turn(self, action: Action) -> None:
        if self.game_state != "playing":
            return

        action.perform(self, self.player)

        if self.game_state == "playing":
            self._handle_enemy_turns()

        if self.game_state == "playing" and not self.player.is_alive:
            self.on_entity_death(self.player)

        self.game_map.update_fov((self.player.x, self.player.y))
