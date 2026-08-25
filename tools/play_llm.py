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

Usage:
    python tools/play_llm.py new                  # start a fresh run
    python tools/play_llm.py look                  # re-print the current view, no turn taken
    python tools/play_llm.py map                    # full explored map, not just the viewport
    python tools/play_llm.py inspect 12 5            # look-mode text for a tile
    python tools/play_llm.py move n                  # n/s/e/w/ne/nw/se/sw - one turn
    python tools/play_llm.py wait                     # one turn
    python tools/play_llm.py pickup                   # one turn
    python tools/play_llm.py use                       # drink selected potion - one turn
    python tools/play_llm.py fire 12 5                  # one turn
    python tools/play_llm.py restart                     # only once dead
    python tools/play_llm.py talk                          # free
    python tools/play_llm.py buy healing_potion              # free
    python tools/play_llm.py learn toughness_1                 # free
    python tools/play_llm.py cycle_potion                        # free
    python tools/play_llm.py pin goblin_warning                    # free
    python tools/play_llm.py quests                                 # free, lists known quests

    python tools/play_llm.py --save saves/other_run.json move n
"""

from __future__ import annotations

import argparse
import sys
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
from engine.actions import BumpAction, FireAction, PickupAction, RestartAction, UseItemAction, WaitAction
from engine.entity import potion_kind
from engine.render import TILE_VISUALS, VIEWPORT_HEIGHT, VIEWPORT_WIDTH, compute_camera, describe_tile
from engine.save import capture_save, load_from_path, restore_save, save_to_path
from main import (
    DUNGEONS_DIR,
    ENCOUNTERS_PATH,
    OVERWORLD_KEY,
    OVERWORLD_LEVEL_PATH,
    QUESTS_PATH,
    _check_destroyable_dungeons_have_ruin_content,
    _check_flag_dialogue_references_known_flags,
    dispatch_action,
    fresh_start,
    resolve_transition,
)

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
QUERY_COMMANDS = {"inspect", "quests"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Play the game headlessly, in plain ASCII text.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--save", default=str(DEFAULT_SAVE_PATH),
        help=f"Session save-file path (default: {DEFAULT_SAVE_PATH})",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("new", help="Start a fresh run, discarding any existing session.")
    sub.add_parser("look", help="Re-print the current view. Costs no turn.")
    sub.add_parser("map", help="Print the full explored map, not just the viewport.")

    p = sub.add_parser("inspect", help="Look-mode text for one tile.")
    p.add_argument("x", type=int)
    p.add_argument("y", type=int)

    p = sub.add_parser("move", help="Move/bump-attack one step. Costs a turn.")
    p.add_argument("direction", choices=sorted(DIRECTIONS))

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

    sub.add_parser("cycle_potion", help="Cycle which potion kind 'use' drinks. Free.")

    p = sub.add_parser("pin", help="Pin a quest as the one shown in the HUD. Free.")
    p.add_argument("quest_id")

    sub.add_parser("quests", help="List every known quest and its current status.")

    return parser.parse_args(argv)


def _render_map_region(
    game_map, cam_x: int, cam_y: int, width: int, height: int,
) -> tuple[str, dict[str, str]]:
    """Plain-ASCII terrain+entities for one region of game_map, mirroring
    render_map/render_entities' exact visible-vs-explored policy (see
    engine/render.py) but as text: a tile shows if visible or explored, an
    entity shows only if its own tile is currently visible. Returns the
    rendered text plus a glyph->name legend for every entity actually
    drawn (a human recognizes a glyph from visual memory; a model reading
    raw text cold each call needs it spelled out)."""
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
        if not game_map.visible[entity.x, entity.y]:
            continue
        sx, sy = entity.x - cam_x, entity.y - cam_y
        if 0 <= sx < w and 0 <= sy < h:
            grid[sy][sx] = entity.glyph
            legend[entity.glyph] = entity.name

    return "\n".join("".join(row) for row in grid), legend


def render_hud_text(engine) -> str:
    """Mirrors engine/render.py's render_hud field-for-field, as an
    f-string block instead of console.print calls - a parallel
    implementation of the same field list, not a shared helper, since
    render_hud is fundamentally console-shaped."""
    player = engine.player
    fighter = player.fighter
    inventory = player.inventory
    healing_potions = sum(1 for it in inventory if potion_kind(it.item) == "healing")
    teleport_potions = sum(1 for it in inventory if potion_kind(it.item) == "teleport")
    selected_potion = player.selected_potion_kind
    keys = sum(1 for it in inventory if it.item.key_id)
    ammo = sum(it.item.quantity for it in inventory if it.item.is_ammo)
    weapon_name = player.equipped_weapon.name if player.equipped_weapon else "none"
    armor_name = player.equipped_armor.name if player.equipped_armor else "none"
    ranged_name = player.equipped_ranged_weapon.name if player.equipped_ranged_weapon else "none"

    lines = [engine.level_name, engine.clock.format_for_hud()]
    active_quest = engine.quest_log.active_quest()
    if active_quest is not None:
        lines.append(active_quest.format_for_hud())
    lines.append(f"HP: {fighter.hp}/{fighter.max_hp}")
    lines.append(
        f"ATK: {player.effective_attack}  DEF: {player.effective_defense}  "
        f"RANGED ATK: {player.effective_ranged_attack}"
    )
    lines.append(f"Weapon: {weapon_name}  Armor: {armor_name}  Ranged: {ranged_name}")
    healing_marker = ">" if selected_potion == "healing" else " "
    teleport_marker = ">" if selected_potion == "teleport" else " "
    lines.append(
        f"Potions: {healing_marker}Healing {healing_potions} "
        f"{teleport_marker}Teleport {teleport_potions}  "
        f"Keys: {keys}  Ammo: {ammo}  Gold: {player.gold}  XP: {player.xp}"
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
            engine.game_map, 0, 0, engine.game_map.width, engine.game_map.height,
        )
    else:
        cam_x, cam_y = compute_camera(
            engine.game_map.width, engine.game_map.height, VIEWPORT_WIDTH, VIEWPORT_HEIGHT,
            engine.player.x, engine.player.y,
        )
        map_text, legend = _render_map_region(
            engine.game_map, cam_x, cam_y, VIEWPORT_WIDTH, VIEWPORT_HEIGHT,
        )
    legend_text = "\n".join(f"{g}: {n}" for g, n in sorted(legend.items())) or "(none visible)"
    message_text = render_message_log_text(engine) or "(none yet)"

    return "\n\n".join([
        render_hud_text(engine),
        "Map:\n" + map_text,
        "Legend:\n" + legend_text,
        "Recent messages:\n" + message_text,
    ])


def apply_command(
    args: argparse.Namespace, active_key: str, active_engines: dict, engine,
    clock, quest_log, dungeon_registry: dict, overworld_level, catalog, encounter_registry,
) -> tuple[str, object, bool]:
    """Applies one non-query command; returns the possibly-updated
    (active_key, engine, full_map) - resolve_transition can hand the
    player off to a different Engine entirely (a new dungeon/overworld),
    so the caller must use the returned engine, not the one passed in."""
    cmd = args.command
    full_map = False

    turn_action = None
    if cmd == "move":
        dx, dy = DIRECTIONS[args.direction]
        turn_action = BumpAction(dx, dy)
    elif cmd == "wait":
        turn_action = WaitAction()
    elif cmd == "pickup":
        turn_action = PickupAction()
    elif cmd == "use":
        turn_action = UseItemAction()
    elif cmd == "fire":
        turn_action = FireAction(args.x, args.y)
    elif cmd == "restart":
        turn_action = RestartAction()

    if turn_action is not None:
        dispatch_action(engine, turn_action)
        # Normally drained by main.py's animate_melee_attacks/
        # animate_ranged_attacks (pure visual flourish, never called here) -
        # skipping that drain would otherwise leak queued events across
        # every future turn for the life of the session file.
        engine.melee_attack_events.clear()
        engine.ranged_attack_events.clear()
        active_key, engine = resolve_transition(
            active_key, engine, active_engines, dungeon_registry, overworld_level, catalog,
            clock=clock, quest_log=quest_log, sprite_codepoints=None,
            encounter_registry=encounter_registry,
        )
    elif cmd == "talk":
        engine.talk_to_adjacent()
    elif cmd == "buy":
        engine.buy_from_shop(args.item_id)
    elif cmd == "learn":
        engine.learn_perk(args.perk_id)
    elif cmd == "cycle_potion":
        engine.cycle_selected_potion_kind()
    elif cmd == "pin":
        engine.quest_log.set_active_quest(args.quest_id)
    elif cmd == "map":
        full_map = True
    # "look" and "new" fall through with no engine mutation - the standard
    # render_state() call after this function returns is the whole point.

    return active_key, engine, full_map


def run_query_command(args: argparse.Namespace, engine, catalog) -> None:
    if args.command == "inspect":
        for line in describe_tile(engine.game_map, catalog, args.x, args.y, engine.dungeon_inspect_text):
            print(line)
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
            )
            print(f"    {description}")


def load_content():
    catalog = load_catalog()
    dungeon_registry = load_dungeon_registry(DUNGEONS_DIR, catalog)
    overworld_level = load_overworld(
        OVERWORLD_LEVEL_PATH, catalog, known_dungeon_ids=set(dungeon_registry)
    )
    quest_defs = load_quests(QUESTS_PATH, catalog, known_dungeon_ids=set(dungeon_registry))
    _check_destroyable_dungeons_have_ruin_content(quest_defs, dungeon_registry)
    _check_flag_dialogue_references_known_flags(quest_defs, dungeon_registry)
    encounter_registry = load_encounters(
        ENCOUNTERS_PATH, known_dungeon_ids=set(dungeon_registry), known_quest_ids=set(quest_defs),
    )
    return catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry


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


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    save_path = Path(args.save)

    try:
        catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry = load_content()
    except ContentValidationError as e:
        print(str(e), file=sys.stderr)
        return 1

    active_key, active_engines, clock, quest_log = load_state(
        save_path, args.command == "new", catalog, dungeon_registry, overworld_level,
        quest_defs, encounter_registry,
    )
    engine = active_engines[active_key]

    if args.command in QUERY_COMMANDS:
        run_query_command(args, engine, catalog)
        return 0

    active_key, engine, full_map = apply_command(
        args, active_key, active_engines, engine, clock, quest_log,
        dungeon_registry, overworld_level, catalog, encounter_registry,
    )

    save = capture_save(active_key, active_engines, clock, quest_log, overworld_level)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    save_to_path(save, save_path)

    print(render_state(engine, full_map=full_map))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
