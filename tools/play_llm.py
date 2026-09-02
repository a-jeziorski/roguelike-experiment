"""Headless, text-only CLI for playing the game - built so an LLM can drive a
real playthrough without an SDL window (no browser/GUI-automation tool
reaches this project's tcod window). No sprites, no color: every tile and
entity is shown as its plain authored ASCII glyph.

Stateless, one command per invocation: since separate tool calls can't hold
an interactive stdin/stdout loop open, each run loads persisted state from
a save file, applies exactly one command, saves state back, and prints the
result. The "session" between calls is an ordinary SaveGame file (see
engine/save.py) - the same mechanism the real game's Save action uses,
just auto-persisted every call instead of on demand.

Navigating the viewport by eye across separate invocations is unreliable -
it recenters on the player every call, so there's no stable frame to count
columns against. Prefer `walk`/`goto` over chains of single `move` calls:
they report explicitly whether each step succeeded, and `goto` pathfinds
for you using the full map (a deliberate testing aid - it doesn't pretend
not to know what the player hasn't personally explored yet).

Usage:
    python tools/play_llm.py new                  # start a fresh run
    python tools/play_llm.py look                  # re-print the current view, no turn taken
    python tools/play_llm.py map                    # full explored map, not just the viewport
    python tools/play_llm.py inspect 12 5            # look-mode text for a tile
    python tools/play_llm.py entities                # list every entity + coords + hostile/peaceful/item
    python tools/play_llm.py move n                   # n/s/e/w/ne/nw/se/sw - one turn, reports outcome
                                                         # (refuses if it would attack a still-peaceful NPC -
                                                         # see 'attack' below)
    python tools/play_llm.py walk n n n e e             # up to 5 steps in one call, stops before any
                                                          # blocked/occupied step or after taking damage
    python tools/play_llm.py attack n                    # deliberate bump-attack, even on a peaceful NPC -
                                                           # the explicit escape hatch 'move' refuses to take
    python tools/play_llm.py goto 40 12                    # pathfind + walk to an exact coordinate
    python tools/play_llm.py goto old drillmaster            # pathfind + walk adjacent to a matching entity
    python tools/play_llm.py wait                           # one turn
    python tools/play_llm.py pickup                          # one turn
    python tools/play_llm.py use                              # drink selected potion - one turn
    python tools/play_llm.py skill second_wind                 # trigger a learned active skill by id - one turn
    python tools/play_llm.py use_skill_slot 1                   # trigger whichever skill is on hotbar slot 1 - one turn
    python tools/play_llm.py use_potion_slot 2                   # drink whichever potion kind is on hotbar slot 2 - one turn
    python tools/play_llm.py fire 12 5                         # one turn
    python tools/play_llm.py restart                            # only once dead
    python tools/play_llm.py talk                                 # free
    python tools/play_llm.py buy healing_potion                    # free
    python tools/play_llm.py learn toughness_1                      # free
    python tools/play_llm.py character                               # free, full stat/hotbar readout
    python tools/play_llm.py bind_skill 1 second_wind                  # free, assign a skill hotbar slot (1-4)
    python tools/play_llm.py bind_potion 2 teleport                     # free, assign a potion hotbar slot (1-3)
    python tools/play_llm.py pin goblin_warning                        # free
    python tools/play_llm.py quests                                    # free, lists known quests

    python tools/play_llm.py --save saves/other_run.json move n

    # Pass the same --record path on every call to capture a replayable session -
    # watch it back afterward with real sprite art via tools/replay.py.
    python tools/play_llm.py --record saves/demo.jsonl new
    python tools/play_llm.py --record saves/demo.jsonl move n
    python tools/replay.py saves/demo.jsonl

    # Debug-only: spawn adjacent to a dungeon's entrance with a hand-picked build,
    # to balance-test it without a full playthrough. Discards any existing session
    # at --save. See tools/balance.py and docs/content_design_process.md §0s.
    python tools/play_llm.py --save saves/test.json testbuild the_windrest \\
        --weapon rusty_dagger --armor leather_armor --perk toughness_1 --potions 2
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from content.loader import (
    ContentValidationError,
    load_catalog,
    load_dungeon_registry,
    load_encounters,
    load_overworld,
    load_quests,
)
from content.schema import PEACEFUL_AI_TYPES
from engine.actions import (
    BumpAction,
    FireAction,
    PickupAction,
    RestartAction,
    UseItemAction,
    UsePotionSlotAction,
    UseSkillAction,
    UseSkillSlotAction,
    WaitAction,
)
from engine.clock import GameClock
from engine.combat import total_crit_chance, total_dodge_chance
from engine.engine import Engine
from engine.entity import apply_perk_stat_bonus, potion_kind
from engine.game_map import build_game_map, item_entity_from_def
from engine.quest import create_quest_log
from engine.render import TILE_VISUALS, VIEWPORT_HEIGHT, VIEWPORT_WIDTH, compute_camera, describe_tile
from engine.save import capture_save, load_from_path, restore_save, save_to_path
from main import (
    DUNGEONS_DIR,
    ENCOUNTERS_PATH,
    OVERWORLD_DIR,
    OVERWORLD_KEY,
    QUESTS_PATH,
    _check_destroyable_dungeons_have_ruin_content,
    _check_flag_dialogue_references_known_flags,
    dispatch_action,
    fresh_start,
    resolve_transition,
)
from tools.balance import build_xp_total

DEFAULT_SAVE_PATH = Path(__file__).resolve().parent.parent / "saves" / "llm_session.json"

# North = dy -1, matching engine/input_handlers.py's MOVE_KEYS (y grows downward).
DIRECTIONS = {
    "n": (0, -1), "s": (0, 1), "w": (-1, 0), "e": (1, 0),
    "ne": (1, -1), "nw": (-1, -1), "se": (1, 1), "sw": (-1, 1),
}

MESSAGE_LOG_TAIL = 20

# Commands that only answer a question about current state - no engine
# mutation, so they print their own focused output instead of the full
# HUD+map+log render (nothing about the world changed, so re-printing all
# of that would just be noise).
QUERY_COMMANDS = {"inspect", "quests", "entities", "character"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Play the game headlessly, in plain ASCII text.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--save", default=str(DEFAULT_SAVE_PATH),
        help=f"Session save-file path (default: {DEFAULT_SAVE_PATH})",
    )
    parser.add_argument(
        "--record", default=None, metavar="PATH",
        help=(
            "Append this call's resulting state to PATH as one JSON-Lines frame "
            "(see tools/replay.py) - off by default; pass the same PATH on every "
            "call you want captured, same statelessness as --save. Only commands "
            "that already persist state get recorded, so query commands "
            "(character/quests/entities/inspect) never add a frame."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("new", help="Start a fresh run, discarding any existing session.")
    sub.add_parser("look", help="Re-print the current view. Costs no turn.")
    sub.add_parser("map", help="Print the full explored map, not just the viewport.")

    p = sub.add_parser("inspect", help="Look-mode text for one tile.")
    p.add_argument("x", type=int)
    p.add_argument("y", type=int)

    sub.add_parser(
        "entities",
        help="List every entity on the current map with coordinates and a hostile/peaceful/item tag. Free.",
    )

    p = sub.add_parser(
        "move",
        help=(
            "Move/bump-attack one step. Costs a turn. Reports whether it moved. Refuses (no "
            "turn spent) if the destination holds a still-peaceful NPC - see 'attack' for the "
            "deliberate version."
        ),
    )
    p.add_argument("direction", choices=sorted(DIRECTIONS))

    p = sub.add_parser(
        "attack",
        help=(
            "Bump-attack one step, deliberately - unlike 'move', never refuses for a peaceful "
            "NPC. Costs a turn. The explicit escape hatch for when attacking a villager/guard "
            "is genuinely intended, not an accidental bump."
        ),
    )
    p.add_argument("direction", choices=sorted(DIRECTIONS))

    p = sub.add_parser(
        "walk",
        help=(
            "Move multiple steps in one call. Stops BEFORE spending a turn on any step that "
            "would leave the map, hit impassable terrain, or bump any entity (hostile or "
            "peaceful - never auto-attacks); also stops after a step that costs HP. Prefer "
            "this over chaining several 'move' calls."
        ),
    )
    p.add_argument("directions", nargs="+", choices=sorted(DIRECTIONS), metavar="DIRECTION")

    p = sub.add_parser(
        "goto",
        help=(
            "Pathfind and walk there: an exact coordinate ('goto 40 12') or the nearest tile "
            "adjacent to an entity whose name contains a case-insensitive match ('goto "
            "drillmaster'). Uses full map knowledge to plan the route (a deliberate testing "
            "aid - see the module docstring) and the same early-stop safety rules as 'walk'."
        ),
    )
    p.add_argument("target", nargs="+", metavar="X_Y_OR_NAME")

    sub.add_parser("wait", help="Pass the turn.")
    sub.add_parser("pickup", help="Pick up whatever's underfoot. Costs a turn.")
    sub.add_parser("use", help="Drink the currently selected potion. Costs a turn.")

    p = sub.add_parser("fire", help="Fire the equipped ranged weapon at (x, y). Costs a turn.")
    p.add_argument("x", type=int)
    p.add_argument("y", type=int)

    sub.add_parser("restart", help="Start over. Only works once dead.")
    sub.add_parser("talk", help="Talk to an adjacent NPC. Free.")

    p = sub.add_parser("buy", help="Buy an item from an adjacent shopkeeper. Free.")
    p.add_argument("item_id")

    p = sub.add_parser("learn", help="Learn a perk from an adjacent Trainer. Free.")
    p.add_argument("perk_id")

    p = sub.add_parser("skill", help="Trigger a learned active-skill perk (e.g. second_wind, ground_pound). Costs a turn.")
    p.add_argument("perk_id")

    sub.add_parser(
        "character",
        help="Full stat/equipment/perk/hotbar readout - what the graphical character screen shows. Free.",
    )

    p = sub.add_parser(
        "bind_skill",
        help="Assign a learned skill perk to a skill hotbar slot (1-4), or 'none' to clear it. Free.",
    )
    p.add_argument("slot", type=int, choices=range(1, 5))
    p.add_argument("perk_id")

    p = sub.add_parser(
        "bind_potion",
        help="Assign a potion kind to a potion hotbar slot (1-3), or 'none' to clear it. Free.",
    )
    p.add_argument("slot", type=int, choices=range(1, 4))
    p.add_argument("kind")

    p = sub.add_parser("use_skill_slot", help="Trigger whichever skill is on that hotbar slot (1-4). Costs a turn.")
    p.add_argument("slot", type=int, choices=range(1, 5))

    p = sub.add_parser("use_potion_slot", help="Drink whichever potion kind is on that hotbar slot (1-3). Costs a turn.")
    p.add_argument("slot", type=int, choices=range(1, 4))

    p = sub.add_parser("pin", help="Pin a quest as the one shown in the HUD. Free.")
    p.add_argument("quest_id")

    sub.add_parser("quests", help="List every known quest and its current status.")

    p = sub.add_parser(
        "testbuild",
        help=(
            "Debug-only: spawn directly next to a dungeon's entrance with a hand-picked "
            "build (perks pre-learned, gear pre-equipped), to balance-test that dungeon "
            "without a full playthrough. See tools/balance.py."
        ),
    )
    p.add_argument("dungeon", help="Dungeon registry id (e.g. the_windrest).")
    p.add_argument(
        "--perk", action="append", dest="perks", default=[], metavar="PERK_ID",
        help="A perk to pre-learn. Repeatable.",
    )
    p.add_argument("--weapon", default=None, metavar="ITEM_ID", help="Item id to equip as weapon.")
    p.add_argument("--armor", default=None, metavar="ITEM_ID", help="Item id to equip as armor.")
    p.add_argument("--ranged", default=None, metavar="ITEM_ID", help="Item id to equip as ranged weapon.")
    p.add_argument("--trinket", default=None, metavar="ITEM_ID", help="Item id to equip as trinket.")
    p.add_argument("--ammo", type=int, default=0, help="Ammo count to carry.")
    p.add_argument("--gold", type=int, default=0, help="Starting gold.")
    p.add_argument("--xp", type=int, default=0, help="Leftover XP after the build's perks.")
    p.add_argument("--potions", type=int, default=0, help="Healing potions to carry.")

    return parser.parse_args(argv)


def _entity_tag(entity) -> str:
    """hostile/peaceful/item, for the legend and the `entities` listing -
    entity.ai is None for an item spawn (only a monster/NPC ever sets it),
    so that's checked first. A still-disguised AI_MIMIC also tags as
    "item" despite having a real ai value - the whole point of the
    disguise is that it reads as inert scenery, on the map legend and in
    'walk'/'goto's own auto-attack-refusal check alike, not just in
    engine/render.py's own draw loop. Tags as "hostile" like anything else
    the instant it's revealed."""
    if entity.ai is None or entity.mimicking:
        return "item"
    return "peaceful" if entity.ai in PEACEFUL_AI_TYPES else "hostile"


def _render_map_region(
    game_map, player, cam_x: int, cam_y: int, width: int, height: int,
) -> tuple[str, dict[str, str]]:
    """Plain-ASCII terrain+entities for one region of game_map, mirroring
    render_map/render_entities' exact visible-vs-explored policy (see
    engine/render.py) but as text: a tile shows if visible or explored, an
    entity shows only if its own tile is currently visible. Returns the
    rendered text plus a glyph->name legend for every entity actually
    drawn, each tagged hostile/peaceful/item/you (see _entity_tag) - a
    human recognizes both a glyph and a threat level from visual memory; a
    model reading raw text cold each call needs both spelled out. The tag
    is also what a chained 'walk'/'goto' call refuses to auto-attack (see
    _peek_step) - reading it here is how to plan around that."""
    w = min(width, game_map.width - cam_x)
    h = min(height, game_map.height - cam_y)
    grid = [[" "] * w for _ in range(h)]

    for sx in range(w):
        x = cam_x + sx
        for sy in range(h):
            y = cam_y + sy
            if game_map.visible[x, y] or game_map.explored[x, y]:
                grid[sy][sx] = TILE_VISUALS[game_map.kinds[x, y]]["glyph"]

    legend: dict[str, str] = {}
    for entity in sorted(game_map.entities, key=lambda e: e.render_priority):
        if not game_map.visible[entity.x, entity.y] or entity.hidden:
            continue
        sx, sy = entity.x - cam_x, entity.y - cam_y
        if 0 <= sx < w and 0 <= sy < h:
            grid[sy][sx] = entity.glyph
            tag = "you" if entity is player else _entity_tag(entity)
            legend[entity.glyph] = f"{entity.name} ({tag})"

    return "\n".join("".join(row) for row in grid), legend


# Mirrors engine/render.py's own _EFFECT_HUD_LABELS - a parallel copy, not
# a shared import, same "own implementation, not reaching into render.py's
# console-shaped internals" reasoning as render_hud_text's own docstring.
_EFFECT_HUD_LABELS = {
    "poison": lambda e: f"POISONED: {e.potency} dmg/turn ({e.turns_remaining} turn(s) left)",
    "stun": lambda e: f"STUNNED: can't act ({e.turns_remaining} turn(s) left)",
    "weaken": lambda e: f"WEAKENED: -{e.potency} attack ({e.turns_remaining} turn(s) left)",
}


def render_hud_text(engine) -> str:
    """Mirrors engine/render.py's render_hud field-for-field, as an
    f-string block instead of console.print calls - a parallel
    implementation of the same field list, not a shared helper, since
    render_hud is fundamentally console-shaped."""
    player = engine.player
    fighter = player.fighter
    inventory = player.inventory
    selected_potion = player.selected_potion_kind
    keys = sum(1 for it in inventory if it.item.key_id)
    ammo = sum(it.item.quantity for it in inventory if it.item.is_ammo)
    weapon_name = player.equipped_weapon.name if player.equipped_weapon else "none"
    armor_name = player.equipped_armor.name if player.equipped_armor else "none"
    ranged_name = player.equipped_ranged_weapon.name if player.equipped_ranged_weapon else "none"
    trinket_name = player.equipped_trinket.name if player.equipped_trinket else "none"

    lines = [
        engine.level_name, engine.clock.format_for_hud(),
        f"Position: ({player.x}, {player.y})",
    ]
    active_quest = engine.quest_log.active_quest()
    if active_quest is not None:
        lines.append(active_quest.format_for_hud())
    lines.append(f"HP: {fighter.hp}/{fighter.max_hp}")
    for kind, effect in fighter.active_effects.items():
        lines.append(_EFFECT_HUD_LABELS[kind](effect))
    lines.append(
        f"ATK: {player.effective_attack}  DEF: {player.effective_defense}  "
        f"RANGED ATK: {player.effective_ranged_attack}"
    )
    lines.append(f"Weapon: {weapon_name}  Armor: {armor_name}  Ranged: {ranged_name}  Trinket: {trinket_name}")
    skill_parts = []
    if engine.catalog is not None:
        for i, perk_id in enumerate(player.skill_slots):
            if perk_id is None:
                continue
            perk = engine.catalog.perks.get(perk_id)
            if perk is None:
                continue
            remaining = player.skill_cooldowns.get(perk_id, 0)
            status = "ready" if remaining <= 0 else f"{remaining}{'h' if perk.skill_cooldown_kind == 'hours' else 't'}"
            skill_parts.append(f"[{i + 1}] {perk.name}: {status}")
    if skill_parts:
        lines.append("Skills: " + "  ".join(skill_parts))
    potion_parts = []
    for i, kind in enumerate(player.potion_slots):
        if kind is None:
            continue
        count = sum(1 for it in inventory if potion_kind(it.item) == kind)
        marker = ">" if selected_potion == kind else " "
        potion_parts.append(f"{marker}[{i + 5}] {kind.replace('_', ' ').capitalize()} {count}")
    potions_text = "  ".join(potion_parts) if potion_parts else "(none bound)"
    lines.append(
        f"Potions: {potions_text}  Keys: {keys}  Ammo: {ammo}  Gold: {player.gold}  XP: {player.xp}"
    )
    if engine.game_state == "dead":
        lines.append("YOU HAVE DIED. Use 'restart' to play again.")
    return "\n".join(lines)


def render_message_log_text(engine) -> str:
    tail = engine.message_log.messages[-MESSAGE_LOG_TAIL:]
    return "\n".join(f"[{m.category}] {m}" for m in tail)


def render_state(engine, full_map: bool = False) -> str:
    if full_map:
        map_text, legend = _render_map_region(
            engine.game_map, engine.player, 0, 0, engine.game_map.width, engine.game_map.height,
        )
    else:
        cam_x, cam_y = compute_camera(
            engine.game_map.width, engine.game_map.height, VIEWPORT_WIDTH, VIEWPORT_HEIGHT,
            engine.player.x, engine.player.y,
        )
        map_text, legend = _render_map_region(
            engine.game_map, engine.player, cam_x, cam_y, VIEWPORT_WIDTH, VIEWPORT_HEIGHT,
        )
    legend_text = "\n".join(f"{g}: {n}" for g, n in sorted(legend.items())) or "(none visible)"
    message_text = render_message_log_text(engine) or "(none yet)"

    return "\n\n".join([
        render_hud_text(engine),
        "Map:\n" + map_text,
        "Legend:\n" + legend_text,
        "Recent messages:\n" + message_text,
    ])


def _peek_step(engine, dx: int, dy: int) -> tuple[bool, str]:
    """Whether the single step (dx, dy) from the player's current position
    is safe for 'walk'/'goto' to auto-execute without spending a turn on a
    surprise. Never treats a blocking entity as safe - hostile or
    peaceful, any entity in the way stops the sequence so the caller
    decides explicitly via 'move' (which does bump-attack, same as the
    real keymap) or 'fire' - exactly the accidental-bump-turns-a-whole-
    town-hostile scenario this exists to prevent. Returns (True, "") if
    safe, else (False, a human-readable reason)."""
    game_map = engine.game_map
    dest_x, dest_y = engine.player.x + dx, engine.player.y + dy
    if not game_map.in_bounds(dest_x, dest_y):
        return False, "the edge of the map"
    if (dest_x, dest_y) in game_map.locked_doors:
        required_key_id = game_map.locked_doors[(dest_x, dest_y)]
        has_key = any(
            it.item is not None and it.item.key_id == required_key_id
            for it in engine.player.inventory
        )
        if not has_key:
            return False, "a locked door (no matching key)"
    water_walking = not engine.is_overworld and engine.player.water_walking_turns_remaining > 0
    if not game_map.is_walkable(dest_x, dest_y, water_walking):
        return False, f"impassable terrain ({game_map.kinds[dest_x, dest_y]})"
    blocker = game_map.blocking_entity_at(dest_x, dest_y)
    if blocker is not None:
        return False, f"{blocker.name} ({_entity_tag(blocker)}) at ({dest_x}, {dest_y})"
    return True, ""


def _bfs_path(
    game_map, start: tuple[int, int], goal: tuple[int, int], water_walking: bool = False,
) -> list[tuple[int, int]] | None:
    """Shortest walkable-terrain path from start to goal, as a list of
    (dx, dy) steps - using full map knowledge (walkable/kinds are known
    for the whole level the moment it's built, never gated by the
    player's own explored/visible state). A deliberate testing aid: this
    tool exists for efficient testing, not to simulate what a blind
    player could find by eye - see the module docstring. Ignores
    entities entirely (they move turn to turn); the caller re-peeks each
    step against the live map at execution time via _peek_step.
    water_walking, if True, lets the path cross deep_water/sea tiles too -
    the caller computes it the same way _peek_step does. None if no
    walkable path exists."""
    if start == goal:
        return []
    if not game_map.in_bounds(*goal) or not game_map.is_walkable(*goal, water_walking):
        return None
    visited = {start}
    queue = deque([start])
    came_from: dict[tuple[int, int], tuple[tuple[int, int], tuple[int, int]]] = {}
    while queue:
        current = queue.popleft()
        if current == goal:
            break
        for dx, dy in DIRECTIONS.values():
            nxt = (current[0] + dx, current[1] + dy)
            if nxt in visited or not game_map.in_bounds(*nxt) or not game_map.is_walkable(*nxt, water_walking):
                continue
            visited.add(nxt)
            came_from[nxt] = (current, (dx, dy))
            queue.append(nxt)
    if goal not in visited:
        return None
    path: list[tuple[int, int]] = []
    node = goal
    while node != start:
        prev, step = came_from[node]
        path.append(step)
        node = prev
    path.reverse()
    return path


def _resolve_goto_target(engine, target_tokens: list[str]) -> tuple[tuple[int, int] | None, str]:
    """Resolves 'goto's arguments to a concrete (x, y) to pathfind to, plus
    a human-readable description for the status note. Exactly two integer
    tokens ("goto 12 5") means a raw coordinate; anything else is joined
    into a case-insensitive substring match against every currently-
    spawned entity's name ("goto old drillmaster"), resolving to whichever
    walkable tile among a matching entity's 8 neighbors has the shortest
    path from the player - never the entity's own tile, which is occupied
    and would just be reported as blocked by _peek_step on the final step."""
    if len(target_tokens) == 2:
        try:
            x, y = int(target_tokens[0]), int(target_tokens[1])
        except ValueError:
            pass
        else:
            return (x, y), f"({x}, {y})"

    name_query = " ".join(target_tokens).lower()
    game_map = engine.game_map
    candidates = [
        e for e in game_map.entities
        if e is not engine.player and not e.hidden and name_query in e.name.lower()
    ]
    if not candidates:
        return None, f"no entity matching '{name_query}'"

    water_walking = not engine.is_overworld and engine.player.water_walking_turns_remaining > 0
    start = (engine.player.x, engine.player.y)
    best_target: tuple[int, int] | None = None
    best_len: int | None = None
    best_entity = None
    for entity in candidates:
        for dx, dy in DIRECTIONS.values():
            nx, ny = entity.x + dx, entity.y + dy
            if not game_map.in_bounds(nx, ny) or not game_map.is_walkable(nx, ny, water_walking):
                continue
            path = _bfs_path(game_map, start, (nx, ny), water_walking)
            if path is None:
                continue
            if best_len is None or len(path) < best_len:
                best_len, best_target, best_entity = len(path), (nx, ny), entity
    if best_target is None:
        return None, f"'{name_query}' found but no walkable path adjacent to it"
    return best_target, f"{best_entity.name} at ({best_entity.x}, {best_entity.y})"


def _execute_walk(
    engine, steps: list[tuple[int, int]], active_key: str, active_engines: dict,
    clock, quest_log, dungeon_registry: dict, overworld_level, catalog, encounter_registry,
    on_step=None,
) -> tuple[str, object, list[str]]:
    """Executes up to len(steps) BumpAction moves ((dx, dy) tuples),
    stopping before spending a turn on any step _peek_step flags unsafe,
    or right after a step that changes game_state, hands the player to a
    different place, or costs HP - shared by the `walk` and `goto`
    commands. Returns the possibly-updated (active_key, engine, notes).

    on_step, if given, is called as on_step(active_key, engine, step_number,
    total_steps) immediately after each step actually executes (including
    the one that ends the loop, whatever the reason) - main()'s hook for
    recording one --record frame per step, rather than one for the whole
    multi-step command, so a replay shows the route actually walked instead
    of jumping straight from start to end (see tools/replay.py)."""
    notes: list[str] = []
    executed = 0
    stop_reason: str | None = None
    entered_new_area = False
    start_pos = (engine.player.x, engine.player.y)

    for dx, dy in steps:
        safe, reason = _peek_step(engine, dx, dy)
        if not safe:
            stop_reason = f"blocked by {reason}"
            break

        pre_hp = engine.player.fighter.hp
        dispatch_action(engine, BumpAction(dx, dy))
        # Normally drained by main.py's animate_melee_attacks/
        # animate_ranged_attacks (pure visual flourish, never called here) -
        # skipping that drain would otherwise leak queued events across
        # every future turn for the life of the session file.
        engine.melee_attack_events.clear()
        engine.ranged_attack_events.clear()
        new_active_key, engine = resolve_transition(
            active_key, engine, active_engines, dungeon_registry, overworld_level, catalog,
            clock=clock, quest_log=quest_log, sprite_codepoints=None,
            encounter_registry=encounter_registry,
        )
        executed += 1
        entered_new_area = new_active_key != active_key
        active_key = new_active_key

        if on_step is not None:
            on_step(active_key, engine, executed, len(steps))

        if engine.game_state == "dead":
            stop_reason = "you died"
            break
        if entered_new_area:
            stop_reason = f"entered a new area ({engine.level_name})"
            break
        if engine.player.fighter.hp < pre_hp:
            stop_reason = f"took damage ({pre_hp} -> {engine.player.fighter.hp} HP)"
            break

    end_pos = (engine.player.x, engine.player.y)
    if entered_new_area:
        # end_pos is in the *new* level's own coordinate space - reporting
        # it as "(start) -> (end)" would silently blend two unrelated
        # coordinate systems into one misleading line (see
        # docs/content_design_process.md's goto write-up). Report the
        # step count and the arrival separately instead.
        notes.append(f"Walked {executed}/{len(steps)} step(s) from ({start_pos[0]}, {start_pos[1]}).")
        notes.append(f"Entered {engine.level_name} at ({end_pos[0]}, {end_pos[1]}).")
    else:
        notes.append(
            f"Walked {executed}/{len(steps)} step(s): "
            f"({start_pos[0]}, {start_pos[1]}) -> ({end_pos[0]}, {end_pos[1]})."
        )
        if stop_reason is not None:
            notes.append(f"Stopped early: {stop_reason}.")
        elif executed == len(steps):
            notes.append("Completed all requested steps.")
    return active_key, engine, notes


def apply_command(
    args: argparse.Namespace, active_key: str, active_engines: dict, engine,
    clock, quest_log, dungeon_registry: dict, overworld_level, catalog, encounter_registry,
    on_step=None,
) -> tuple[str, object, bool, list[str]]:
    """Applies one non-query command; returns the possibly-updated
    (active_key, engine, full_map, notes) - resolve_transition can hand
    the player off to a different Engine entirely (a new dungeon/
    overworld), so the caller must use the returned engine, not the one
    passed in. `notes` are short status lines (move outcome, walk/goto
    summary) printed before the standard render - the "did that actually
    work" feedback a chain of blind moves otherwise lacks.

    on_step is passed straight through to _execute_walk for `walk`/`goto`
    (the only commands that can span more than one turn) - see that
    function's own docstring."""
    cmd = args.command
    full_map = False
    notes: list[str] = []

    if cmd == "walk":
        steps = [DIRECTIONS[d] for d in args.directions]
        active_key, engine, notes = _execute_walk(
            engine, steps, active_key, active_engines, clock, quest_log,
            dungeon_registry, overworld_level, catalog, encounter_registry,
            on_step=on_step,
        )
        return active_key, engine, full_map, notes

    if cmd == "goto":
        target, description = _resolve_goto_target(engine, args.target)
        if target is None:
            notes.append(f"Goto failed: {description}.")
            return active_key, engine, full_map, notes
        water_walking = not engine.is_overworld and engine.player.water_walking_turns_remaining > 0
        path = _bfs_path(engine.game_map, (engine.player.x, engine.player.y), target, water_walking)
        if path is None:
            notes.append(f"No path found to {description}.")
            return active_key, engine, full_map, notes
        notes.append(f"Pathfinding to {description}: {len(path)} step(s).")
        active_key, engine, walk_notes = _execute_walk(
            engine, path, active_key, active_engines, clock, quest_log,
            dungeon_registry, overworld_level, catalog, encounter_registry,
            on_step=on_step,
        )
        notes.extend(walk_notes)
        return active_key, engine, full_map, notes

    turn_action = None
    pre_pos = (engine.player.x, engine.player.y)
    if cmd == "move":
        dx, dy = DIRECTIONS[args.direction]
        blocker = engine.would_attack_peaceful_npc(dx, dy)
        if blocker is not None:
            notes.append(
                f"Refused: that would attack {blocker.name}, who isn't hostile. "
                f"Use 'attack {args.direction}' if that's deliberate."
            )
            return active_key, engine, full_map, notes
        turn_action = BumpAction(dx, dy)
    elif cmd == "attack":
        dx, dy = DIRECTIONS[args.direction]
        turn_action = BumpAction(dx, dy)
    elif cmd == "wait":
        turn_action = WaitAction()
    elif cmd == "pickup":
        turn_action = PickupAction()
    elif cmd == "use":
        turn_action = UseItemAction()
    elif cmd == "skill":
        turn_action = UseSkillAction(args.perk_id)
    elif cmd == "use_skill_slot":
        turn_action = UseSkillSlotAction(args.slot - 1)
    elif cmd == "use_potion_slot":
        turn_action = UsePotionSlotAction(args.slot - 1)
    elif cmd == "fire":
        turn_action = FireAction(args.x, args.y)
    elif cmd == "restart":
        turn_action = RestartAction()

    if turn_action is not None:
        dispatch_action(engine, turn_action)
        engine.melee_attack_events.clear()
        engine.ranged_attack_events.clear()
        active_key, engine = resolve_transition(
            active_key, engine, active_engines, dungeon_registry, overworld_level, catalog,
            clock=clock, quest_log=quest_log, sprite_codepoints=None,
            encounter_registry=encounter_registry,
        )
        if cmd in ("move", "attack"):
            post_pos = (engine.player.x, engine.player.y)
            if post_pos == pre_pos:
                notes.append(
                    f"Position unchanged at ({pre_pos[0]}, {pre_pos[1]}) - see messages below for why."
                )
            else:
                notes.append(
                    f"Moved: ({pre_pos[0]}, {pre_pos[1]}) -> ({post_pos[0]}, {post_pos[1]})."
                )
    elif cmd == "talk":
        engine.talk_to_adjacent()
    elif cmd == "buy":
        engine.buy_from_shop(args.item_id)
    elif cmd == "learn":
        engine.learn_perk(args.perk_id)
    elif cmd == "bind_skill":
        engine.assign_skill_slot(args.slot - 1, None if args.perk_id == "none" else args.perk_id)
    elif cmd == "bind_potion":
        engine.assign_potion_slot(args.slot - 1, None if args.kind == "none" else args.kind)
    elif cmd == "pin":
        engine.quest_log.set_active_quest(args.quest_id)
    elif cmd == "map":
        full_map = True
    # "look" and "new" fall through with no engine mutation - the standard
    # render_state() call after this function returns is the whole point.

    return active_key, engine, full_map, notes


def run_query_command(args: argparse.Namespace, engine, catalog) -> None:
    if args.command == "inspect":
        for line in describe_tile(engine.game_map, catalog, args.x, args.y, engine.dungeon_inspect_text):
            print(line)
        return

    if args.command == "entities":
        # Deliberately still excludes a hidden AI_AMBUSHER even though this
        # command otherwise uses full map knowledge (goto's own docstring) -
        # that omniscience is about geography/exploration, not X-ray vision
        # into a concealed monster; listing it here would trivially spoil
        # the one mechanic that depends on the player not knowing it's there.
        entities = [e for e in engine.game_map.entities if e is not engine.player and not e.hidden]
        if not entities:
            print("(no other entities on this map)")
            return
        for entity in sorted(entities, key=lambda e: (e.x, e.y)):
            # Same disguise-preserving guard as _entity_tag above - a
            # still-disguised AI_MIMIC shows no HP here either.
            hp_text = (
                f", HP {entity.fighter.hp}/{entity.fighter.max_hp}"
                if entity.fighter and not entity.mimicking
                else ""
            )
            print(f"({entity.x}, {entity.y}) {entity.name} [{_entity_tag(entity)}]{hp_text}")
        return

    if args.command == "character":
        player = engine.player
        fighter = player.fighter
        print(f"HP: {fighter.hp}/{fighter.max_hp}")
        print(
            f"Attack: {player.effective_attack}  Defense: {player.effective_defense}  "
            f"Ranged: {player.effective_ranged_attack}"
        )
        print(f"Crit chance: {total_crit_chance(player):.0%}  Dodge chance: {total_dodge_chance(player):.0%}")
        print(f"Gold: {player.gold}  XP: {player.xp}")
        weapon_name = player.equipped_weapon.name if player.equipped_weapon else "none"
        armor_name = player.equipped_armor.name if player.equipped_armor else "none"
        ranged_name = player.equipped_ranged_weapon.name if player.equipped_ranged_weapon else "none"
        trinket_name = player.equipped_trinket.name if player.equipped_trinket else "none"
        print(f"Weapon: {weapon_name}  Armor: {armor_name}  Ranged: {ranged_name}  Trinket: {trinket_name}")

        print("Perks learned:")
        learned_any = False
        for perk_id, perk in catalog.perks.items():
            if perk_id not in player.learned_perk_ids:
                continue
            learned_any = True
            print(f"  {perk.name} - {perk.description}")
        if not learned_any:
            print("  (none yet)")

        print("Skill hotbar:")
        for i, perk_id in enumerate(player.skill_slots):
            value = catalog.perks[perk_id].name if perk_id and perk_id in catalog.perks else "(empty)"
            print(f"  [{i + 1}] {value}")

        print("Potion hotbar:")
        for i, kind in enumerate(player.potion_slots):
            print(f"  [{i + 5}] {kind.replace('_', ' ').capitalize() if kind else '(empty)'}")
        return

    if args.command == "quests":
        quests = [q for q in engine.quest_log.quests.values() if q.status != "not_given"]
        if not quests:
            print("(no quests yet)")
            return
        for quest in quests:
            marker = "*" if quest.id == engine.quest_log.active_quest_id else " "
            print(f"{marker} [{quest.id}] {quest.format_for_hud()}")
            description = quest.current_description(
                engine.player.inventory, engine.quest_log.killed_entity_ids,
                engine.quest_log.visited_dungeon_ids,
                engine.quest_log.intimidated_entity_ids,
                engine.quest_log.cleared_species_ids,
            )
            print(f"    {description}")


def load_content():
    catalog = load_catalog()
    dungeon_registry = load_dungeon_registry(DUNGEONS_DIR, catalog)
    overworld_level = load_overworld(
        OVERWORLD_DIR, catalog, known_dungeon_ids=set(dungeon_registry)
    )
    quest_defs = load_quests(QUESTS_PATH, catalog, known_dungeon_ids=set(dungeon_registry))
    _check_destroyable_dungeons_have_ruin_content(quest_defs, dungeon_registry)
    _check_flag_dialogue_references_known_flags(quest_defs, dungeon_registry)
    encounter_registry = load_encounters(
        ENCOUNTERS_PATH, known_dungeon_ids=set(dungeon_registry), known_quest_ids=set(quest_defs),
    )
    return catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry


def test_build_start(
    args: argparse.Namespace, catalog, dungeon_registry: dict, overworld_level, quest_defs: dict,
) -> tuple[str, dict, GameClock, object]:
    """Debug-only alternative to load_state/fresh_start for the `testbuild`
    command: a brand-new overworld state with the player spawned adjacent
    to args.dungeon's entrance (not on it - the same "one step off, then
    walk in" shape 'goto' already needs, see the module docstring) and a
    hand-picked build already applied. Bypasses the normal adjacent-Trainer/
    adjacent-shopkeeper requirements entirely and deliberately - this exists
    to test a dungeon's balance in isolation, not to simulate reaching it
    legitimately. Returns the same 4-tuple shape as load_state, so main()'s
    call site is a one-line branch."""
    dungeon = dungeon_registry.get(args.dungeon)
    if dungeon is None:
        raise SystemExit(f"testbuild: unknown dungeon '{args.dungeon}'")
    entrance = next(
        (e for e in overworld_level.dungeon_entrances if e.dungeon_id == args.dungeon), None,
    )
    if entrance is None:
        raise SystemExit(f"testbuild: '{args.dungeon}' has no entrance on the overworld map")

    clock = GameClock()
    quest_log = create_quest_log(quest_defs)
    game_map, player = build_game_map(overworld_level, catalog)

    spawn = next(
        (
            (entrance.x + dx, entrance.y + dy) for dx, dy in DIRECTIONS.values()
            if game_map.in_bounds(entrance.x + dx, entrance.y + dy)
            and game_map.is_walkable(entrance.x + dx, entrance.y + dy)
        ),
        None,
    )
    if spawn is None:
        raise SystemExit(f"testbuild: no walkable tile adjacent to '{args.dungeon}'s entrance")
    player.x, player.y = spawn

    for perk_id in args.perks:
        perk = catalog.perks.get(perk_id)
        if perk is None:
            raise SystemExit(f"testbuild: unknown perk '{perk_id}'")
        apply_perk_stat_bonus(player.fighter, perk)
        player.learned_perk_ids.add(perk_id)
        if perk.max_hp_bonus:
            player.fighter.hp += perk.max_hp_bonus
        # Same auto-slotting learn_perk gives a live purchase (see
        # Engine.learn_perk) - a pre-built skill perk should show up
        # correctly hotbarred, not silently unassigned, since this bypasses
        # learn_perk entirely.
        if perk.skill_effect is not None and perk_id not in player.skill_slots:
            if None in player.skill_slots:
                player.skill_slots[player.skill_slots.index(None)] = perk_id

    for item_id, slot in (
        (args.weapon, "equipped_weapon"), (args.armor, "equipped_armor"), (args.ranged, "equipped_ranged_weapon"),
        (args.trinket, "equipped_trinket"),
    ):
        if item_id is None:
            continue
        item = catalog.items.get(item_id)
        if item is None:
            raise SystemExit(f"testbuild: unknown item '{item_id}'")
        setattr(player, slot, item_entity_from_def(item))

    if args.ammo:
        ammo = item_entity_from_def(catalog.items["arrows"])
        ammo.item.quantity = args.ammo
        player.inventory.append(ammo)
    for _ in range(args.potions):
        player.inventory.append(item_entity_from_def(catalog.items["healing_potion"]))
    player.gold = args.gold
    player.xp = args.xp

    dungeon_inspect_text = {d_id: d.inspect_text for d_id, d in dungeon_registry.items()}
    dungeon_ruin_data = {
        d_id: (d.ruined_tile, d.ruined_description, d.ruined_starting_level)
        for d_id, d in dungeon_registry.items() if d.ruined_tile
    }
    engine = Engine(
        game_map, player, overworld_level.name,
        catalog=catalog, is_overworld=True, dungeon_inspect_text=dungeon_inspect_text,
        dungeon_ruin_data=dungeon_ruin_data, starting_level=overworld_level,
        clock=clock, quest_log=quest_log, sprite_codepoints=None,
    )
    active_engines = {OVERWORLD_KEY: engine}

    total = build_xp_total(catalog, args.perks, args.weapon, args.armor, args.ranged)
    summary = f"Build total: {total:g} XP-equivalent"
    if dungeon.balance_reference_xp is not None:
        summary += f" - dungeon reference: {dungeon.balance_reference_xp} XP ({total - dungeon.balance_reference_xp:+g})"
    print(summary)

    return OVERWORLD_KEY, active_engines, clock, quest_log


def load_state(save_path: Path, force_new: bool, catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry):
    if not force_new and save_path.exists():
        save = load_from_path(save_path)
        if save is not None:
            try:
                return restore_save(
                    save, catalog, dungeon_registry, overworld_level, quest_defs,
                    encounter_registry, None, OVERWORLD_KEY,
                )
            except (KeyError, ValueError):
                pass
    return fresh_start(catalog, dungeon_registry, overworld_level, quest_defs, None)


def _strip_session_flags(argv: list[str]) -> list[str]:
    """argv, minus --save/--record and their values - just the subcommand
    and its own args, for the replay viewer's on-screen caption (see
    _append_replay_frame) rather than the noisy full invocation."""
    result = []
    skip_next = False
    for token in argv:
        if skip_next:
            skip_next = False
            continue
        if token in ("--save", "--record"):
            skip_next = True
            continue
        result.append(token)
    return result


def _append_replay_frame(record_path: Path, argv: list[str], notes: list[str], engine, save) -> None:
    """Appends one JSON-Lines frame to record_path (see tools/replay.py) -
    the raw argv that produced this frame (for the viewer's own caption),
    apply_command's own notes, this step's own message log (SaveGame
    deliberately never persists messages - each CLI invocation gets a
    fresh one by design - so they're captured here, separately, and
    re-injected by the viewer at replay time), and the full state snapshot
    itself (save.model_dump(mode="json"), the same serialization
    save_to_path already uses). Pure append - never rewrites the file, so
    a growing session costs one write per call, not a rewrite of
    everything recorded so far."""
    record_path.parent.mkdir(parents=True, exist_ok=True)
    frame = {
        "argv": argv,
        "notes": notes,
        "messages": [
            {"text": str(m), "category": m.category, "speaker": m.speaker}
            for m in engine.message_log.messages
        ],
        "save": save.model_dump(mode="json"),
    }
    with record_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(frame) + "\n")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    save_path = Path(args.save)
    call_argv = _strip_session_flags(list(argv) if argv is not None else sys.argv[1:])

    try:
        catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry = load_content()
    except ContentValidationError as e:
        print(str(e), file=sys.stderr)
        return 1

    if args.command == "testbuild":
        active_key, active_engines, clock, quest_log = test_build_start(
            args, catalog, dungeon_registry, overworld_level, quest_defs,
        )
    else:
        active_key, active_engines, clock, quest_log = load_state(
            save_path, args.command == "new", catalog, dungeon_registry, overworld_level,
            quest_defs, encounter_registry,
        )
    engine = active_engines[active_key]

    if args.command in QUERY_COMMANDS:
        run_query_command(args, engine, catalog)
        return 0

    on_step = None
    if args.record:
        def on_step(step_active_key, step_engine, step_number, total_steps):
            # One frame per turn `walk`/`goto` actually executes, not one
            # for the whole multi-step command - otherwise a replay would
            # jump straight from the start position to the end position in
            # a single frame instead of showing the route walked (see
            # tools/replay.py, docs/content_design_process.md's goto
            # write-up). Reuses the exact same frame shape/helper the
            # end-of-command recording below uses.
            step_save = capture_save(step_active_key, active_engines, clock, quest_log, overworld_level)
            _append_replay_frame(
                Path(args.record), call_argv, [f"Step {step_number}/{total_steps}"],
                step_engine, step_save,
            )

    active_key, engine, full_map, notes = apply_command(
        args, active_key, active_engines, engine, clock, quest_log,
        dungeon_registry, overworld_level, catalog, encounter_registry,
        on_step=on_step,
    )

    save = capture_save(active_key, active_engines, clock, quest_log, overworld_level)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    save_to_path(save, save_path)
    if args.record:
        _append_replay_frame(Path(args.record), call_argv, notes, engine, save)

    for note in notes:
        print(note)
    if notes:
        print()
    print(render_state(engine, full_map=full_map))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
