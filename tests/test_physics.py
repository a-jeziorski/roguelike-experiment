"""Tests for engine/physics.py - the damage-magnitude-driven knockback/
wall-smashing/shockwave system. Same helper shapes as tests/test_engine.py's
make_open_map/make_player/make_monster, with a local make_entity that also
accepts poise (not needed by the rest of the suite, so not added there)."""

from content.schema import DEFAULT_FLOOR_DRAG, DEFAULT_WALL_DESTROY_COST, TILE_FORCE_COST
from engine.combat import resolve_attack, resolve_skill_damage
from engine.engine import Engine
from engine.entity import RENDER_PRIORITY_ACTOR, RENDER_PRIORITY_PLAYER, Entity, Fighter
from engine.game_map import GameMap
from engine.physics import cast_force_ray, direction_toward, force_from_damage

WALL_COST = TILE_FORCE_COST["wall"]
BRITTLE_COST = TILE_FORCE_COST["wall_brittle"]
assert TILE_FORCE_COST["wall_reinforced"] is None


def make_open_map(width: int, height: int) -> GameMap:
    game_map = GameMap(width, height)
    for x in range(width):
        for y in range(height):
            game_map.kinds[x, y] = "floor"
            game_map.walkable[x, y] = True
            game_map.transparent[x, y] = True
    return game_map


def make_entity(x, y, *, hp=100, attack=5, defense=0, poise=0, blocks_movement=True, name="Dummy") -> Entity:
    return Entity(
        x, y, "d", (200, 200, 200), name,
        blocks_movement=blocks_movement,
        render_priority=RENDER_PRIORITY_ACTOR,
        fighter=Fighter(max_hp=hp, hp=hp, attack=attack, defense=defense, poise=poise),
    )


def make_player(x, y, *, hp=100, attack=5, defense=0) -> Entity:
    return Entity(
        x, y, "@", (255, 255, 255), "Player",
        blocks_movement=True,
        render_priority=RENDER_PRIORITY_PLAYER,
        fighter=Fighter(max_hp=hp, hp=hp, attack=attack, defense=defense),
    )


def make_engine(game_map: GameMap, player: Entity) -> Engine:
    if player not in game_map.entities:
        game_map.entities.append(player)
    return Engine(game_map, player, "Test Level")


# --- force_from_damage ------------------------------------------------------


def test_force_from_damage_is_zero_for_zero_or_negative_damage():
    assert force_from_damage(0) == 0.0
    assert force_from_damage(-5) == 0.0


def test_force_from_damage_is_monotonically_increasing():
    values = [force_from_damage(d) for d in (1, 5, 20, 100, 1000, 10_000, 100_000, 1_000_000)]
    assert values == sorted(values)
    assert len(set(values)) == len(values)


def test_force_from_damage_is_negligible_for_ordinary_combat_damage():
    """The whole point of FORCE_LOG_DIVISOR being large relative to typical
    hits (see engine/physics.py's own comment): a routine early-game attack
    (even a heavily-equipped player's, up to ~20ish damage) must produce
    less force than DEFAULT_FLOOR_DRAG - i.e. not even enough to cross one
    open floor tile - so ordinary combat is unaffected by this system."""
    assert force_from_damage(20) < DEFAULT_FLOOR_DRAG


def test_force_from_damage_is_sublinear_at_the_high_end():
    """A 100x jump in raw damage (10,000 -> 1,000,000) must yield much less
    than 100x growth in force - the "soft cap" decision #3 asked for."""
    force_10k = force_from_damage(10_000)
    force_1m = force_from_damage(1_000_000)
    assert force_1m > force_10k
    assert force_1m < force_10k * 3


def test_force_from_damage_ten_thousand_can_just_smash_one_ordinary_wall():
    """Tuned reference point: the 10,000-damage debug tier is meant to be
    exactly around where one ordinary wall (cost WALL_COST) becomes
    breakable - see data/dungeons/physics_arena's debug weapon tiers."""
    assert force_from_damage(10_000) >= WALL_COST


# --- direction_toward --------------------------------------------------------


def test_direction_toward_all_eight_directions_and_same_point():
    assert direction_toward((5, 5), (5, 5)) == (0, 0)
    assert direction_toward((5, 5), (8, 5)) == (1, 0)
    assert direction_toward((5, 5), (2, 5)) == (-1, 0)
    assert direction_toward((5, 5), (5, 8)) == (0, 1)
    assert direction_toward((5, 5), (5, 2)) == (0, -1)
    assert direction_toward((5, 5), (8, 8)) == (1, 1)
    assert direction_toward((5, 5), (2, 8)) == (-1, 1)
    assert direction_toward((5, 5), (8, 2)) == (1, -1)
    assert direction_toward((5, 5), (2, 2)) == (-1, -1)


# --- cast_force_ray -----------------------------------------------------------


def test_cast_force_ray_destroys_exactly_as_many_walls_as_the_budget_affords():
    game_map = make_open_map(10, 3)
    for x in (2, 3, 4):
        game_map.kinds[x, 1] = "wall"
        game_map.walkable[x, 1] = False
        game_map.transparent[x, 1] = False
    mover = make_entity(1, 1)
    engine = make_engine(game_map, mover)

    result = cast_force_ray(engine, mover, (1, 0), WALL_COST * 2)

    assert result.destroyed_walls == [(2, 1), (3, 1)]
    assert result.stopped_by == "budget_exhausted"
    assert (mover.x, mover.y) == (3, 1)
    assert game_map.destroyed_wall_tiles == {(2, 1), (3, 1)}
    assert game_map.walkable[2, 1] and game_map.walkable[3, 1]
    assert not game_map.walkable[4, 1]  # the third wall was never touched


def test_cast_force_ray_exhausts_over_open_floor():
    game_map = make_open_map(10, 3)
    mover = make_entity(1, 1)
    engine = make_engine(game_map, mover)

    result = cast_force_ray(engine, mover, (1, 0), DEFAULT_FLOOR_DRAG * 3.5)

    assert result.stopped_by == "budget_exhausted"
    assert (mover.x, mover.y) == (4, 1)  # 3 full tiles of drag, the 4th unaffordable


def test_cast_force_ray_stops_dead_against_an_indestructible_wall():
    game_map = make_open_map(10, 3)
    game_map.kinds[2, 1] = "wall_reinforced"
    game_map.walkable[2, 1] = False
    game_map.transparent[2, 1] = False
    mover = make_entity(1, 1, hp=1000)
    engine = make_engine(game_map, mover)
    starting_hp = mover.fighter.hp

    result = cast_force_ray(engine, mover, (1, 0), 100.0)

    assert result.stopped_by == "indestructible_wall"
    assert (mover.x, mover.y) == (1, 1)  # never moved
    assert not game_map.destroyed_wall_tiles
    assert mover.fighter.hp < starting_hp  # took impact damage


def test_cast_force_ray_a_sufficiently_poised_entity_does_not_budge():
    game_map = make_open_map(10, 3)
    mover = make_entity(1, 1, hp=1000)
    occupant = make_entity(2, 1, hp=1000, poise=100)
    game_map.entities.append(occupant)
    engine = make_engine(game_map, mover)

    result = cast_force_ray(engine, mover, (1, 0), 50.0)

    assert result.stopped_by == "poised_entity"
    assert (mover.x, mover.y) == (1, 1)
    assert (occupant.x, occupant.y) == (2, 1)  # the tank didn't move either
    assert occupant.fighter.hp < 1000  # but still took collision damage
    assert mover.fighter.hp < 1000


def test_cast_force_ray_a_low_poise_entity_gets_bumped_and_the_ray_continues():
    game_map = make_open_map(10, 3)
    mover = make_entity(1, 1, hp=1000)
    occupant = make_entity(2, 1, hp=1000, poise=0)
    game_map.entities.append(occupant)
    engine = make_engine(game_map, mover)

    result = cast_force_ray(engine, mover, (1, 0), 50.0)

    assert mover.x > 2  # advanced past the occupant's original tile
    assert (occupant.x, occupant.y) != (2, 1)  # the bumped entity moved too
    assert occupant.fighter.hp < 1000
    assert mover.fighter.hp < 1000


def test_cast_force_ray_a_zero_direction_does_nothing():
    game_map = make_open_map(5, 5)
    mover = make_entity(2, 2)
    engine = make_engine(game_map, mover)

    result = cast_force_ray(engine, mover, (0, 0), 100.0)

    assert result.path == []
    assert (mover.x, mover.y) == (2, 2)


# --- shockwave ----------------------------------------------------------------


def test_shockwave_excludes_both_attacker_and_defender():
    """Regression test: the shockwave must never fling the attacker who
    delivered the hit, or double-hit the defender - both are already fully
    resolved by apply_attack_physics before the shockwave radiates out."""
    game_map = make_open_map(11, 11)
    attacker = make_player(5, 5, attack=1_000_000)
    # High poise keeps the defender from actually flying off (irrelevant to
    # what this test checks) so the shockwave's impact point stays put at
    # the defender's original tile, making the bystander's distance to it
    # predictable.
    defender = make_entity(6, 5, hp=10_000_000, defense=0, poise=1_000_000)
    bystander = make_entity(6, 7, hp=1000, defense=0)
    game_map.entities.extend([defender, bystander])
    engine = make_engine(game_map, attacker)

    attacker_start = (attacker.x, attacker.y)
    resolve_attack(engine, attacker, defender)

    assert (attacker.x, attacker.y) == attacker_start  # the swing's own shockwave didn't fling the attacker
    assert bystander.fighter.hp < 1000  # but a nearby bystander felt it


# --- end-to-end wiring through engine/combat.py --------------------------------


def test_resolve_skill_damage_triggers_wall_smashing_and_knockback_too():
    """decision #4: physics applies to skill damage exactly like ordinary
    attacks, with zero per-skill special-casing - resolve_skill_damage is
    the shared entry point every active skill's damage already funnels
    through (see engine/combat.py)."""
    game_map = make_open_map(12, 3)
    for x in (3, 4):
        game_map.kinds[x, 1] = "wall"
        game_map.walkable[x, 1] = False
        game_map.transparent[x, 1] = False
    attacker = make_player(1, 1)
    defender = make_entity(2, 1, hp=10_000_000, defense=0)
    game_map.entities.append(defender)
    engine = make_engine(game_map, attacker)

    resolve_skill_damage(engine, attacker, defender, 1_000_000, "obliterates")

    assert game_map.destroyed_wall_tiles  # at least one wall came down
    assert (defender.x, defender.y) != (2, 1)  # defender was sent flying
    assert engine.wall_destruction_events or engine.knockback_events


def test_zero_damage_hit_triggers_no_physics():
    game_map = make_open_map(5, 3)
    attacker = make_player(1, 1, attack=0)
    defender = make_entity(2, 1, hp=100, defense=100)
    game_map.entities.append(defender)
    engine = make_engine(game_map, attacker)

    resolve_attack(engine, attacker, defender)

    assert (defender.x, defender.y) == (2, 1)
    assert not engine.knockback_events
    assert not engine.wall_destruction_events
