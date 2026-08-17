"""World-object model: the player, monsters, and items as they exist in a running
game (as opposed to content.schema, which describes how they're *defined* in
content files)."""

from __future__ import annotations

from dataclasses import dataclass

Color = tuple[int, int, int]

# Draw order when multiple entities could occupy visual space: items under actors.
RENDER_PRIORITY_ITEM = 0
RENDER_PRIORITY_ACTOR = 1
RENDER_PRIORITY_PLAYER = 2


@dataclass
class Fighter:
    max_hp: int
    hp: int
    attack: int
    defense: int


@dataclass
class ItemEffect:
    heal_amount: int | None = None
    attack_bonus: int | None = None
    key_id: str | None = None


class Entity:
    def __init__(
        self,
        x: int,
        y: int,
        glyph: str,
        color: Color,
        name: str,
        *,
        blocks_movement: bool = False,
        render_priority: int = RENDER_PRIORITY_ITEM,
        fighter: Fighter | None = None,
        item: ItemEffect | None = None,
        ai: str | None = None,
    ):
        self.x = x
        self.y = y
        self.glyph = glyph
        self.color = color
        self.name = name
        self.blocks_movement = blocks_movement
        self.render_priority = render_priority
        self.fighter = fighter
        self.item = item
        self.ai = ai
        self.inventory: list[Entity] = []

    @property
    def is_alive(self) -> bool:
        return self.fighter is not None and self.fighter.hp > 0

    def __repr__(self) -> str:
        return f"Entity({self.name!r} at ({self.x},{self.y}))"
