"""Damage-magnitude-driven environmental physics: wall smashing, knockback,
entity collisions, and shockwaves.

The whole premise (see docs/content_design_process.md's physics-arena entry
for the full design rationale): in a game where damage numbers scale into
the thousands or millions, the environment should react proportionally
instead of a 1,000,000-damage hit doing exactly what a 10-damage hit does.
engine/combat.py's _apply_damage calls apply_attack_physics for every landed
hit - melee, ranged, and skill damage alike - unconditionally; there is no
opt-in flag, by design (a big hit can fling collateral damage onto
bystanders, and that emergent tension is the point).

Every entry point here resolves synchronously to a final position within one
call - there is no multi-turn "currently flying" state anywhere in this
engine, so nothing about an in-progress knockback needs to be saved (see
engine/save.py's destroyed_wall_tiles, the only new persisted state this
feature needs).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from content.schema import DEFAULT_FLOOR_DRAG, DEFAULT_WALL_DESTROY_COST, TILE_FORCE_COST

if TYPE_CHECKING:
    from engine.engine import Engine
    from engine.entity import Entity
    from engine.game_map import GameMap

Coord = tuple[int, int]

# --- damage -> force ------------------------------------------------------

# force_from_damage's tunables, isolated here so the physics arena can retune
# them without touching any call site. log1p keeps 0 damage -> 0 force (a
# fully-mitigated hit pushes nothing) and grows unboundedly but ever more
# slowly as damage climbs - the sub-linear "soft cap" the design calls for,
# so a jump from thousands to millions of damage doesn't multiply destroyed-
# tile counts anywhere near that factor. FORCE_LOG_DIVISOR is deliberately
# large relative to ordinary combat damage (a fully-geared player's routine
# hit is roughly 10-20): the physics system is meant to stay dormant for
# everyday numbers and only wake up once damage climbs into the hundreds and
# beyond, not nudge every mundane fight. Worked reference points (recompute
# these if the constants below change): damage 20 -> force ~0.43 (below
# DEFAULT_FLOOR_DRAG - no movement at all); damage 100 -> ~1.9; damage 10,000
# -> ~18.5 (just enough to smash exactly one ordinary wall); damage
# 1,000,000 -> ~40.0. A 100x jump from 10,000 to 1,000,000 damage yields
# roughly 2x growth in force.
FORCE_LOG_DIVISOR = 200.0
FORCE_SCALE = 4.7


def force_from_damage(damage: int) -> float:
    if damage <= 0:
        return 0.0
    return FORCE_SCALE * math.log1p(damage / FORCE_LOG_DIVISOR)


def direction_toward(origin: Coord, target: Coord) -> Coord:
    """One of the 8 unit vectors pointing from origin to target - (0, 0)
    only when origin == target. Works identically for an adjacent melee hit,
    a ranged shot's own (fx, fy, tx, ty), or a skill's AoE target at any
    Chebyshev distance - callers just pass whichever two coordinates they
    already have."""
    dx, dy = target[0] - origin[0], target[1] - origin[1]
    return ((dx > 0) - (dx < 0), (dy > 0) - (dy < 0))


def _tile_force_cost(game_map: "GameMap", x: int, y: int) -> float | None:
    kind = game_map.kinds[x, y]
    if kind in TILE_FORCE_COST:
        return TILE_FORCE_COST[kind]
    return DEFAULT_FLOOR_DRAG if game_map.walkable[x, y] else DEFAULT_WALL_DESTROY_COST


# --- impact/collision damage (deliberately bypasses engine/combat.py) -----

# Fraction of the force budget still unspent at the moment of impact that
# becomes flat physical damage - kept well below FORCE_SCALE's own magnitude
# so a hit's *direct* damage still dominates the total; this is the
# secondary "smashed into something" damage on top of that, not a
# replacement for it.
IMPACT_DAMAGE_FACTOR = 0.5
COLLISION_DAMAGE_FACTOR = 0.5
# Flat cost paid out of the ray's own remaining budget when it powers past a
# bumped entity's old tile, on top of whatever collision damage was already
# dealt - keeps "flies through several weak entities for free" from being
# free.
COLLISION_PASS_THROUGH_COST = 4.0
# The bumped occupant's own onward ray gets this fraction of whatever budget
# was left at the moment of collision - deliberately not a recursive
# re-entry into the mover's own budget bookkeeping (see cast_force_ray's
# docstring): a chain of three or more entities knocked into each other in
# sequence is an explicit MVP scope cut, not modeled here.
BUMPED_ENTITY_FORCE_SHARE = 0.5


def _damage_from_budget(budget: float, factor: float) -> int:
    """Truncates (not rounds up) a fraction of a force budget into flat
    damage - a budget too small to matter (e.g. a shockwave's distance-
    falloff tail) must be able to round down to exactly 0, not be inflated
    to a guaranteed minimum of 1 the way math.ceil would."""
    return int(budget * factor)


def _apply_impact_damage(engine: "Engine", entity: "Entity", amount: int, verb: str) -> None:
    """Physical impact/collision damage - no dodge/crit/affix/riposte roll,
    and critically, no physics of its own. Routing this back through
    engine/combat.py's _apply_damage (which is what calls apply_attack_
    physics below) would let a knockback ray recursively spawn more
    knockback. Mirrors Engine._apply_environmental_hazard's direct
    fighter.hp -= shape rather than _apply_damage's own pipeline. A no-op on
    an already-dead entity (e.g. a corpse still being flung after the raw
    hit that killed it) - nothing to damage further, and on_entity_death
    must never run twice for the same entity."""
    if amount <= 0 or entity.fighter is None or not entity.is_alive:
        return
    entity.fighter.hp -= amount
    engine.message_log.add(
        f"{entity.name} slams into {verb} for {amount} impact damage.", category="combat"
    )
    if entity.fighter.hp <= 0:
        engine.on_entity_death(entity)


# --- the core primitive -----------------------------------------------------


@dataclass
class ForceRayResult:
    path: list[Coord] = field(default_factory=list)
    destroyed_walls: list[Coord] = field(default_factory=list)
    final_position: Coord = (0, 0)
    # "budget_exhausted" | "indestructible_wall" | "poised_entity" | "world_edge"
    stopped_by: str = "budget_exhausted"


def _resolve_collision(
    engine: "Engine", mover: "Entity", occupant: "Entity", direction: Coord, budget: float
) -> tuple[bool, float]:
    """One collision step inside cast_force_ray's walk loop. Returns
    (ray_should_stop, mover's own remaining budget). Comic-book physics:
    a sufficiently-poised occupant (durable/heavy) barely budges and stops
    the ray outright; anything else gets a single, non-chained nudge and the
    mover continues past it."""
    collision_dmg = _damage_from_budget(budget, COLLISION_DAMAGE_FACTOR)
    _apply_impact_damage(engine, mover, collision_dmg, occupant.name)
    _apply_impact_damage(engine, occupant, collision_dmg, mover.name)

    if occupant.fighter is None or occupant.fighter.poise >= budget:
        return True, budget

    occupant_start = (occupant.x, occupant.y)
    if occupant.is_alive:
        cast_force_ray(engine, occupant, direction, budget * BUMPED_ENTITY_FORCE_SHARE)
    if occupant.is_alive and (occupant.x, occupant.y) == occupant_start:
        # The nudge didn't actually move it (blocked immediately by the
        # world edge or something else behind it) - mover can't advance
        # onto a tile that's still occupied, so this is a stop after all,
        # not a pass-through. A dead occupant (is_alive False) skips this
        # check entirely: on_entity_death already vacated its tile.
        return True, budget
    return False, budget - COLLISION_PASS_THROUGH_COST


def cast_force_ray(engine: "Engine", mover: "Entity", direction: Coord, budget: float) -> ForceRayResult:
    """Walks mover tile-by-tile in `direction`, spending `budget` as it
    goes: destroying an affordable destructible wall and continuing through
    it, paying a small drag cost to cross open floor (so even a huge force
    has a soft travel cap in open terrain, not just against walls), and
    stopping - with impact damage - against an indestructible wall or a
    sufficiently-poised entity. `mover.fighter.poise` is subtracted from the
    budget once, up front: a high-Poise entity can be immune to displacement
    even from a hit that would otherwise one-shot it, which is the entire
    point of the stat. Resolves to a single final position, written once at
    the end (no interpolated multi-step movement, matching
    engine/actions.py's MovementAction)."""
    game_map = engine.game_map
    dx, dy = direction
    origin = (mover.x, mover.y)
    result = ForceRayResult(final_position=origin)
    if dx == 0 and dy == 0:
        return result

    budget -= mover.fighter.poise
    if budget <= 0:
        result.stopped_by = "poised_entity"
        return result

    x, y = origin
    while budget > 0:
        nx, ny = x + dx, y + dy
        if not game_map.in_bounds(nx, ny):
            result.stopped_by = "world_edge"
            break

        occupant = game_map.blocking_entity_at(nx, ny)
        if occupant is not None and occupant is not mover:
            should_stop, budget = _resolve_collision(engine, mover, occupant, direction, budget)
            if should_stop:
                result.stopped_by = "poised_entity"
                break
            x, y = nx, ny
            result.path.append((x, y))
            continue

        if game_map.walkable[nx, ny]:
            cost = _tile_force_cost(game_map, nx, ny)
            if budget < cost:
                result.stopped_by = "budget_exhausted"
                break
            budget -= cost
            x, y = nx, ny
            result.path.append((x, y))
            continue

        cost = _tile_force_cost(game_map, nx, ny)
        if cost is None:
            impact = _damage_from_budget(budget, IMPACT_DAMAGE_FACTOR)
            _apply_impact_damage(engine, mover, impact, "an unyielding wall")
            result.stopped_by = "indestructible_wall"
            break
        if budget < cost:
            result.stopped_by = "budget_exhausted"
            break
        budget -= cost
        game_map.destroy_wall_tile(nx, ny)
        result.destroyed_walls.append((nx, ny))
        engine.wall_destruction_events.append((nx, ny))
        engine.message_log.add(f"{mover.name} smashes clean through a wall!", category="combat")
        x, y = nx, ny
        result.path.append((x, y))
    else:
        result.stopped_by = "budget_exhausted"

    mover.x, mover.y = x, y
    result.final_position = (x, y)
    if result.path:
        engine.knockback_events.append((origin[0], origin[1], x, y))
        engine.message_log.add(
            f"{mover.name} is sent flying {len(result.path)} tile(s)!", category="combat"
        )
    return result


# --- shockwave --------------------------------------------------------------

# Always smaller than the primary hit's own force - a lesser echo, not an
# equal blast (decision #5).
SHOCKWAVE_FORCE_FRACTION = 0.35
SHOCKWAVE_RADIUS = 3
SHOCKWAVE_DAMAGE_FACTOR = 0.3
# Fragile map dressing cleared by a big enough shockwave - cosmetic, no
# decoration-HP system invented for this.
FRAGILE_DECORATION_KINDS = {"barrel", "crate", "rubble", "bones", "cobwebs"}
FRAGILE_DECORATION_FORCE_THRESHOLD = 4.0


def apply_shockwave(
    engine: "Engine", impact_point: Coord, primary_force: float, exclude: "frozenset[Entity]"
) -> None:
    """A smaller, radius-based echo of the primary hit's force - hits every
    living fighter within SHOCKWAVE_RADIUS of impact_point, `exclude` (the
    attacker and defender of the hit that caused this shockwave, both
    already fully resolved by apply_attack_physics - an attack's own
    recoil doesn't fling the person delivering it) aside. Deliberately does
    NOT filter out peaceful/allied entities the way Engine.use_skill's War
    Horn branch does (see SKILL_EFFECT_WAR_HORN) - collateral damage to
    *other* bystanders is the intended emergent tension (decision #4), not
    an oversight."""
    ix, iy = impact_point
    shock_budget = primary_force * SHOCKWAVE_FORCE_FRACTION
    if shock_budget <= 0:
        return

    candidates = [
        e for e in list(engine.game_map.entities)
        if e not in exclude and e.fighter is not None and e.is_alive
        and max(abs(e.x - ix), abs(e.y - iy)) <= SHOCKWAVE_RADIUS
    ]
    for target in candidates:
        dist = max(abs(target.x - ix), abs(target.y - iy))
        falloff = 1.0 - dist / (SHOCKWAVE_RADIUS + 1)
        budget = shock_budget * falloff
        if budget <= 0:
            continue
        shock_dmg = _damage_from_budget(budget, SHOCKWAVE_DAMAGE_FACTOR)
        _apply_impact_damage(engine, target, shock_dmg, "the shockwave")
        if target.is_alive:
            cast_force_ray(engine, target, direction_toward(impact_point, (target.x, target.y)), budget)

    if shock_budget >= FRAGILE_DECORATION_FORCE_THRESHOLD:
        engine.game_map.decorations = [
            d for d in engine.game_map.decorations
            if not (
                d.entity_id in FRAGILE_DECORATION_KINDS
                and max(abs(d.x - ix), abs(d.y - iy)) <= SHOCKWAVE_RADIUS
            )
        ]


def apply_attack_physics(engine: "Engine", attacker: "Entity", defender: "Entity", damage: int) -> None:
    """The single hook engine/combat.py's _apply_damage calls for every
    landed hit - melee, ranged, and skill damage alike (decision #4) - after
    _apply_damage has already fully resolved its own death check. Computes
    this hit's force from `damage`, knocks defender back/through terrain
    (even a defender that the raw hit just killed still gets sent flying -
    that's part of the appeal, and _apply_impact_damage's is_alive guard
    means a corpse takes no further damage from it), then radiates a
    smaller shockwave from wherever defender ended up."""
    force = force_from_damage(damage)
    if force <= 0:
        return
    direction = direction_toward((attacker.x, attacker.y), (defender.x, defender.y))
    cast_force_ray(engine, defender, direction, force)
    apply_shockwave(engine, (defender.x, defender.y), force, exclude=frozenset((attacker, defender)))
