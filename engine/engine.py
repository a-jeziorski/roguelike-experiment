"""Owns game state and the turn loop. Rendering/windowing is driven from main.py
so Engine itself stays testable without an SDL window."""

from __future__ import annotations

from typing import TYPE_CHECKING

from content.schema import AI_HOSTILE_BASIC, AI_RANGED_BASIC, AI_SKITTISH, AI_SLEEPING_GUARD
from engine.actions import Action, MovementAction
from engine.combat import resolve_attack, resolve_ranged_attack
from engine.entity import Entity
from engine.game_map import GameMap, build_game_map

if TYPE_CHECKING:
    from content.loader import Catalog, ParsedLevel

# Fallbacks when a monster doesn't specify its own alert_radius/flee_hp_pct/
# ranged_range.
DEFAULT_ALERT_RADIUS = 4
DEFAULT_FLEE_HP_PCT = 0.3
DEFAULT_MONSTER_RANGED_RANGE = 4


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
        # (from_x, from_y, to_x, to_y) for every ranged attack resolved during
        # the last process_turn() call - combat.py appends here, main.py
        # drains it to drive a projectile animation. Engine itself never reads
        # it back; this is purely a mailbox to the SDL-dependent render layer,
        # which is why it lives here instead of forcing Engine to know about
        # rendering.
        self.ranged_attack_events: list[tuple[int, int, int, int]] = []

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
        self.ranged_attack_events = []
        self.game_map.update_fov((self.player.x, self.player.y))
        self.message_log.add(f"You enter {self.level_name}.")

    def _perform_ai(self, entity: Entity) -> None:
        if not self.game_map.visible[entity.x, entity.y]:
            return

        dx = self.player.x - entity.x
        dy = self.player.y - entity.y
        distance = max(abs(dx), abs(dy))

        if entity.ai == AI_HOSTILE_BASIC:
            self._chase_and_attack(entity, dx, dy, distance)

        elif entity.ai == AI_SLEEPING_GUARD:
            alert_radius = entity.alert_radius or DEFAULT_ALERT_RADIUS
            if distance <= alert_radius:
                self._chase_and_attack(entity, dx, dy, distance)

        elif entity.ai == AI_SKITTISH:
            flee_hp_pct = entity.flee_hp_pct or DEFAULT_FLEE_HP_PCT
            if entity.fighter.hp / entity.fighter.max_hp <= flee_hp_pct:
                self._flee(entity, dx, dy)
            else:
                self._chase_and_attack(entity, dx, dy, distance)

        elif entity.ai == AI_RANGED_BASIC:
            ranged_range = entity.ranged_range or DEFAULT_MONSTER_RANGED_RANGE
            if distance <= 1:
                resolve_attack(self, attacker=entity, defender=self.player)
            elif distance <= ranged_range:
                resolve_ranged_attack(self, attacker=entity, defender=self.player)
            else:
                step_x = (dx > 0) - (dx < 0)
                step_y = (dy > 0) - (dy < 0)
                MovementAction(step_x, step_y).perform(self, entity)

    def _chase_and_attack(self, entity: Entity, dx: int, dy: int, distance: int) -> None:
        if distance <= 1:
            resolve_attack(self, attacker=entity, defender=self.player)
        else:
            step_x = (dx > 0) - (dx < 0)
            step_y = (dy > 0) - (dy < 0)
            MovementAction(step_x, step_y).perform(self, entity)

    def _flee(self, entity: Entity, dx: int, dy: int) -> None:
        """Steps directly away from the player. If that's blocked (wall,
        another entity, a corner), MovementAction's own checks just no-op -
        the entity holds position rather than being forced to fight."""
        step_x = -((dx > 0) - (dx < 0))
        step_y = -((dy > 0) - (dy < 0))
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
