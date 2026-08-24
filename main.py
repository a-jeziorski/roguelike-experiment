"""Entry point: loads the dungeon registry and starts a run in the default dungeon."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import tcod
import tcod.event

from content.loader import (
    ContentValidationError,
    load_catalog,
    load_dungeon_registry,
    load_encounters,
    load_overworld,
    load_quests,
    load_sprite_manifest,
)
from engine.actions import (
    DEFAULT_RANGED_RANGE,
    CyclePotionKindAction,
    EscapeAction,
    FireAction,
    FireModeAction,
    LookAction,
    QuestLogAction,
    RestartAction,
    SaveGameAction,
    ShopAction,
    TalkAction,
)
from engine.clock import GameClock
from engine.engine import Engine
from engine.game_map import build_game_map
from engine.quest import QuestLog, create_quest_log
from engine.save import capture_save, load_from_path, restore_save, save_to_path
from engine.sprites import apply_sprites
from engine.input_handlers import (
    handle_continue_prompt_event,
    handle_event,
    handle_look_event,
    handle_quest_log_event,
    handle_shop_event,
    handle_target_event,
)
from engine.render import (
    VIEWPORT_HEIGHT,
    VIEWPORT_WIDTH,
    compute_camera,
    flash_impact,
    projectile_glyph,
    projectile_path,
    render_all,
    render_continue_prompt,
    render_look_frame,
    render_projectile,
    render_quest_log,
    render_shop,
    render_target_frame,
)
from engine.targeting import find_nearest_target

DUNGEONS_DIR = Path(__file__).resolve().parent / "data" / "dungeons"
OVERWORLD_LEVEL_PATH = Path(__file__).resolve().parent / "data" / "overworld.lvl"
QUESTS_PATH = Path(__file__).resolve().parent / "data" / "quests.yaml"
ENCOUNTERS_PATH = Path(__file__).resolve().parent / "data" / "encounters.yaml"
SPRITES_PATH = Path(__file__).resolve().parent / "data" / "sprites.yaml"
ASSETS_DIR = Path(__file__).resolve().parent / "assets" / "tilesets"
SAVE_PATH = Path(__file__).resolve().parent / "saves" / "save.json"
STARTING_DUNGEON_ID = "prison_tower"
OVERWORLD_KEY = "overworld"

# 16 rather than an arbitrary size: matches the Kenney sprite packs' native
# 16x16 resolution exactly (crisp, no resize) and downscales RLTiles' native
# 32x32 by a clean 2x - see engine/sprites.py.
TILE_SIZE = 16
# The console must be at least as wide as the map viewport (no horizontal HUD
# sidebar); its extra rows below VIEWPORT_HEIGHT are the HUD/message log area,
# sized independently of any level's actual height - see engine/render.py.
CONSOLE_COLUMNS = VIEWPORT_WIDTH
CONSOLE_ROWS = 40

PROJECTILE_FRAME_SECONDS = 0.035
IMPACT_FLASH_SECONDS = 0.09

FONT_CANDIDATES = [
    Path(os.environ.get("SystemRoot", r"C:\Windows")) / "Fonts" / "consola.ttf",
    Path(os.environ.get("SystemRoot", r"C:\Windows")) / "Fonts" / "cour.ttf",
]


def load_tileset() -> tcod.tileset.Tileset:
    for candidate in FONT_CANDIDATES:
        if candidate.exists():
            return tcod.tileset.load_truetype_font(str(candidate), TILE_SIZE, TILE_SIZE)
    raise RuntimeError(
        "No usable monospace TTF font found. Tried: "
        + ", ".join(str(c) for c in FONT_CANDIDATES)
    )


def dispatch_action(engine: Engine, action, on_player_turn_resolved=None) -> bool:
    """Routes a raw input Action to the engine. Returns True if the caller
    should quit.

    Escape and Restart are handled outside Engine.process_turn on purpose:
    process_turn no-ops once the game is no longer "playing" (so normal
    actions are ignored after death), which would otherwise silently
    swallow both quitting and restarting once the run has ended.

    A normal turn action resolves in Engine's two explicit phases -
    process_player_action then process_enemy_phase - with
    on_player_turn_resolved() called in between if given. That's the caller's
    hook for animating the player's own attack (see main()'s call sites)
    before any monster has had a chance to move on the same turn; left as a
    no-op by default so this function stays testable without SDL/animation.
    """
    if isinstance(action, EscapeAction):
        return True
    if isinstance(action, RestartAction):
        if engine.game_state != "playing":
            engine.restart()
        return False
    if action is not None:
        if engine.process_player_action(action):
            if on_player_turn_resolved is not None:
                on_player_turn_resolved()
            engine.process_enemy_phase()
    return False


def fire_mode_gate(engine: Engine) -> str | None:
    """Whether targeting mode can currently be entered. Returns an error
    message to log if not, or None if run_target_mode should run - pulled
    out for testability without SDL, same reasoning as dispatch_action."""
    if engine.player.equipped_ranged_weapon is None:
        return "You have no ranged weapon equipped."
    if not any(it.item.is_ammo for it in engine.player.inventory):
        return "You have no ammo."
    return None


def shop_gate(engine: Engine) -> str | None:
    """Whether shop mode can currently be entered. Returns an error message
    to log if not, or None if run_shop_mode should run - same reasoning as
    fire_mode_gate."""
    if engine.adjacent_shopkeeper() is None:
        return "There's no one here to buy from."
    return None


def handle_save_game_action(
    engine: Engine, active_key: str, active_engines: dict[str, Engine],
    clock: GameClock, quest_log: QuestLog, overworld_level, save_path: Path,
) -> None:
    """Captures and writes the current run to save_path, or does nothing
    while dead (no gate function needed - unlike fire_mode_gate/shop_gate,
    the only condition is game_state, the same inline check every other
    free/non-turn action already uses - see TalkAction/QuestLogAction's
    handling in main()). Pulled out of main()'s loop so it's testable
    without SDL, same reasoning as dispatch_action/resolve_transition."""
    if engine.game_state != "playing":
        return
    save = capture_save(active_key, active_engines, clock, quest_log, overworld_level)
    save_to_path(save, save_path)
    engine.message_log.add("Game saved.")


def run_target_mode(console: tcod.console.Console, context: tcod.context.Context, engine: Engine) -> tuple[int, int] | None:
    """Nested event loop for targeting: aims a cursor (starting on the
    nearest valid target) and re-renders until the player fires or cancels.
    Never touches Engine.process_turn - aiming costs no turn, only a
    confirmed shot does. Returns the chosen (x, y) to fire at, or None if
    cancelled."""
    weapon = engine.player.equipped_ranged_weapon
    max_range = weapon.item.range or DEFAULT_RANGED_RANGE
    nearest = find_nearest_target(engine.game_map, engine.player, max_range)
    cursor_x, cursor_y = (nearest.x, nearest.y) if nearest else (engine.player.x, engine.player.y)

    while True:
        render_target_frame(console, engine, cursor_x, cursor_y, max_range)
        context.present(console)

        for event in tcod.event.wait():
            context.convert_event(event)
            result = handle_target_event(event)

            if result == "cancel":
                return None
            if result == "fire":
                return (cursor_x, cursor_y)
            if isinstance(result, tuple):
                dx, dy = result
                cursor_x = max(0, min(engine.game_map.width - 1, cursor_x + dx))
                cursor_y = max(0, min(engine.game_map.height - 1, cursor_y + dy))


def run_look_mode(console: tcod.console.Console, context: tcod.context.Context, engine: Engine) -> None:
    """Nested event loop for look mode: moves a cursor and re-renders until the
    player exits. Never touches Engine.process_turn, so it costs no game turn."""
    cursor_x, cursor_y = engine.player.x, engine.player.y

    while True:
        render_look_frame(console, engine, cursor_x, cursor_y)
        context.present(console)

        for event in tcod.event.wait():
            context.convert_event(event)
            result = handle_look_event(event)

            if result == "exit":
                return
            if isinstance(result, tuple):
                dx, dy = result
                cursor_x = max(0, min(engine.game_map.width - 1, cursor_x + dx))
                cursor_y = max(0, min(engine.game_map.height - 1, cursor_y + dy))


def run_quest_log_mode(console: tcod.console.Console, context: tcod.context.Context, engine: Engine) -> None:
    """Nested event loop for the quest log screen: moves a selection and
    re-renders until the player exits. Never touches Engine.process_turn, so
    it costs no game turn - only pinning a quest as active is a side effect,
    and even that isn't a turn action."""
    quests = [q for q in engine.quest_log.quests.values() if q.status != "not_given"]
    if not quests:
        selected = 0
    else:
        selected = next(
            (i for i, q in enumerate(quests) if q.id == engine.quest_log.active_quest_id), 0
        )

    while True:
        description = (
            quests[selected].current_description(
                engine.player.inventory,
                engine.quest_log.killed_entity_ids,
                engine.quest_log.visited_dungeon_ids,
            )
            if quests else ""
        )
        render_quest_log(console, quests, selected, engine.quest_log.active_quest_id, description)
        context.present(console)

        for event in tcod.event.wait():
            context.convert_event(event)
            result = handle_quest_log_event(event)

            if result == "exit":
                return
            if result == "up" and quests:
                selected = (selected - 1) % len(quests)
            if result == "down" and quests:
                selected = (selected + 1) % len(quests)
            if result == "select" and quests:
                engine.quest_log.set_active_quest(quests[selected].id)


def run_shop_mode(console: tcod.console.Console, context: tcod.context.Context, engine: Engine) -> None:
    """Nested event loop for the shop screen: moves a selection and buys the
    selected item on confirm, re-rendering until the player exits. Never
    touches Engine.process_turn, so it costs no game turn - same as talking
    or browsing the quest log. Reads its item list from whichever
    shopkeeper is actually adjacent (see EntityDef.shop_inventory) rather
    than a single hardcoded list - shop_gate already guarantees a
    shopkeeper is adjacent before this is ever called, and this loop never
    moves the player, so that stays true for its whole lifetime."""
    shopkeeper = engine.adjacent_shopkeeper()
    item_ids = shopkeeper.shop_inventory if shopkeeper is not None else []
    selected = 0
    status = ""

    while True:
        prices = {item_id: engine.shop_price(item_id, shopkeeper) for item_id in item_ids}
        render_shop(console, engine.catalog, item_ids, prices, selected, engine.player.gold, status)
        context.present(console)

        for event in tcod.event.wait():
            context.convert_event(event)
            result = handle_shop_event(event)

            if result == "exit":
                return
            if result == "up" and item_ids:
                selected = (selected - 1) % len(item_ids)
            if result == "down" and item_ids:
                selected = (selected + 1) % len(item_ids)
            if result == "buy" and item_ids:
                status = engine.buy_from_shop(item_ids[selected])


def prompt_continue_saved_game(console: tcod.console.Console, context: tcod.context.Context) -> bool:
    """Nested event loop for the startup "continue a saved game?" screen -
    no Engine yet at this point (that's the whole reason this exists as a
    standalone loop rather than one of the run_X_mode screens above, which
    all take an already-built Engine). Returns True to load the save,
    False to start a new game."""
    while True:
        render_continue_prompt(console)
        context.present(console)

        for event in tcod.event.wait():
            context.convert_event(event)
            result = handle_continue_prompt_event(event)

            if result == "yes":
                return True
            if result == "no":
                return False


def animate_ranged_attacks(
    console: tcod.console.Console, context: tcod.context.Context, engine: Engine
) -> None:
    """Plays a brief flying-projectile-then-impact-flash animation for every
    ranged attack currently queued in engine.ranged_attack_events (player-
    fired via FireAction, or monster-fired via a ranged_basic AI's shot) and
    discards the events. Called twice per turn from dispatch_action's two
    phases - once right after the player's own action, once after enemy AI
    turns - so a monster's impact flash always renders before that monster
    has had a chance to move again; calling this only once per turn, after
    both phases, used to draw a surviving target's flash on the tile it had
    already left. Damage is already fully applied by the time this runs -
    Engine resolves combat synchronously and has no concept of animation
    frames - so this is pure visual flavor layered on top of
    already-final game state, not a step in Engine.process_turn."""
    events = engine.ranged_attack_events
    engine.ranged_attack_events = []
    cam_x, cam_y = compute_camera(
        engine.game_map.width, engine.game_map.height, VIEWPORT_WIDTH, VIEWPORT_HEIGHT,
        engine.player.x, engine.player.y,
    )

    for fx, fy, tx, ty in events:
        glyph = projectile_glyph(fx, fy, tx, ty)
        for x, y in projectile_path(fx, fy, tx, ty):
            render_all(console, engine)
            render_projectile(console, cam_x, cam_y, x, y, glyph)
            context.present(console)
            time.sleep(PROJECTILE_FRAME_SECONDS)

        render_all(console, engine)
        flash_impact(console, engine.game_map, cam_x, cam_y, tx, ty)
        context.present(console)
        time.sleep(IMPACT_FLASH_SECONDS)


def animate_melee_attacks(
    console: tcod.console.Console, context: tcod.context.Context, engine: Engine
) -> None:
    """Same idea as animate_ranged_attacks but for melee hits: no travel to
    show, just the same impact flash on the struck tile, so a sword hit
    reads as an event on the map instead of only a message-log line."""
    events = engine.melee_attack_events
    engine.melee_attack_events = []
    cam_x, cam_y = compute_camera(
        engine.game_map.width, engine.game_map.height, VIEWPORT_WIDTH, VIEWPORT_HEIGHT,
        engine.player.x, engine.player.y,
    )

    for x, y in events:
        render_all(console, engine)
        flash_impact(console, engine.game_map, cam_x, cam_y, x, y)
        context.present(console)
        time.sleep(IMPACT_FLASH_SECONDS)


def animate_combat_feedback(
    console: tcod.console.Console, context: tcod.context.Context, engine: Engine
) -> None:
    animate_melee_attacks(console, context, engine)
    animate_ranged_attacks(console, context, engine)


def _match_entrance(overworld_map, from_dungeon_id: str) -> tuple[int, int] | None:
    """The overworld tile whose dungeon_entrance targets from_dungeon_id, if
    one exists - where the player should land after leaving that dungeon.
    Re-derived on every arrival (never cached) since the player can return
    via a different dungeon than the one they last left through."""
    for coord, dungeon_id in overworld_map.dungeon_entrances.items():
        if dungeon_id == from_dungeon_id:
            return coord
    return None


def _armable_encounter(from_dungeon_id, quest_log: QuestLog, encounter_registry):
    """The first not-yet-triggered EncounterDef (data/encounters.yaml) whose
    trigger_dungeon_id matches from_dungeon_id and whose gate_quest_id is
    currently at gate_quest_status, or None - the moment its delay timer
    should (re)start (see QuestLog.arm_encounter), not the moment it fires.
    First match wins if more than one is ever eligible at once - only one
    encounter exists today, but this mirrors the same "file order is
    meaningful" convention already documented for data/quests.yaml's
    active-quest-pin tiebreak, should a second overlapping encounter ever
    be added."""
    for encounter in (encounter_registry or {}).values():
        if encounter.trigger_dungeon_id != from_dungeon_id:
            continue
        if encounter.id in quest_log.triggered_encounter_ids:
            continue
        quest = quest_log.quests.get(encounter.gate_quest_id)
        if quest is not None and quest.status == encounter.gate_quest_status:
            return encounter
    return None


def _due_encounter(quest_log: QuestLog, encounter_registry, clock: GameClock):
    """The first armed EncounterDef whose delay has actually elapsed, or
    None. Re-checks gate_quest_status is still current - an armed encounter
    whose gate quest's status changed during the delay (e.g. somehow
    completed some other way) never fires, even once its timer runs out."""
    for encounter_id, due in quest_log.armed_encounters.items():
        if encounter_id in quest_log.triggered_encounter_ids:
            continue
        if (clock.year, clock.day, clock.hour) < due:
            continue
        encounter = (encounter_registry or {}).get(encounter_id)
        if encounter is None:
            continue
        quest = quest_log.quests.get(encounter.gate_quest_id)
        if quest is not None and quest.status == encounter.gate_quest_status:
            return encounter
    return None


def _redirect_into_encounter(
    encounter, overworld_engine: Engine, active_engines: dict[str, Engine],
    dungeon_registry: dict, catalog, sprite_codepoints, position: tuple[int, int],
) -> tuple[str, Engine]:
    """Departs the player from overworld_engine and hands them to
    encounter.encounter_dungeon_id's Engine (built fresh on first fire,
    resumed thereafter) - the actual mechanics of an overworld encounter
    firing, shared by both the "just landed on the overworld" and "already
    walking the overworld, timer ran out" call sites in resolve_transition.
    `position` is wherever the player actually was on the overworld the
    moment this fired - see Engine.overworld_return_position, which uses it
    to hand the player back to that exact spot once they later leave. Logs
    encounter.encounter_message (if any) right after the generic "You enter
    <level_name>." line every arrival already gets, explaining to the
    player why they were just pulled off the overworld."""
    enc_player = overworld_engine.depart_player()
    enc_target = active_engines.get(encounter.encounter_dungeon_id)
    if enc_target is None:
        dungeon = dungeon_registry[encounter.encounter_dungeon_id]
        starting_level = dungeon.levels[dungeon.starting_level]
        enc_map, _ = build_game_map(starting_level, catalog, player=enc_player)
        enc_target = Engine(
            enc_map, enc_player, starting_level.name,
            catalog=catalog, levels=dungeon.levels, starting_level=starting_level,
            clock=overworld_engine.clock, quest_log=overworld_engine.quest_log,
            sprite_codepoints=sprite_codepoints, overworld_return_position=position,
        )
        active_engines[encounter.encounter_dungeon_id] = enc_target
    else:
        enc_target.arrive_player(enc_player)
    if encounter.encounter_message:
        enc_target.message_log.add(encounter.encounter_message)
    enc_target.quest_log.record_dungeon_arrival(encounter.encounter_dungeon_id)
    enc_target.quest_log.record_encounter_triggered(encounter.id)
    return encounter.encounter_dungeon_id, enc_target


def resolve_transition(
    active_key: str,
    engine: Engine,
    active_engines: dict[str, Engine],
    dungeon_registry: dict,
    overworld_level,
    catalog,
    *,
    clock: GameClock | None = None,
    quest_log: QuestLog | None = None,
    sprite_codepoints=None,
    encounter_registry=None,
) -> tuple[str, Engine]:
    """After a dispatch, checks the active engine's transition mailbox
    (Engine.wants_overworld / Engine.pending_dungeon_entry) and performs the
    cross-Engine player handoff if one is pending, returning whichever
    (key, Engine) should be active next - unchanged if nothing is pending.

    Gated on game_state == "playing": if the player also died on the same
    turn they reached a leave-tile (a monster's retaliation after the move
    that triggered the transition), the death screen for that dungeon takes
    priority - the transition simply doesn't fire this turn.

    Each dungeon (and the overworld) gets at most one Engine, lazily created
    on first visit and cached in active_engines thereafter, so leaving and
    later returning resumes exactly the state that dungeon was left in.

    `encounter_registry` (data/encounters.yaml, EncounterDef -> ...) drives
    a two-step arm-then-fire sequence, not an instant redirect: departing
    trigger_dungeon_id with its gate quest at gate_quest_status arms a
    delay_hours-long timer (QuestLog.armed_encounters/arm_encounter); the
    player is only actually redirected into encounter_dungeon_id once that
    many *overworld* hours have elapsed (_due_encounter), checked both here
    (whenever the current engine is the overworld one, covering the timer
    running out mid-walk on some later turn) and again right after arming
    (covering a delay that's already elapsed the instant it's set). `None`
    (the default) disables the feature entirely - every existing
    caller/test that doesn't pass it keeps behaving exactly as before.
    """
    if engine.game_state != "playing":
        return active_key, engine

    if engine.is_overworld:
        encounter = _due_encounter(engine.quest_log, encounter_registry, engine.clock)
        if encounter is not None:
            return _redirect_into_encounter(
                encounter, engine, active_engines, dungeon_registry, catalog,
                sprite_codepoints, (engine.player.x, engine.player.y),
            )

    if engine.wants_overworld:
        player = engine.depart_player()
        target = active_engines.get(OVERWORLD_KEY)
        if target is None:
            game_map, _ = build_game_map(overworld_level, catalog, player=player)
            position = engine.overworld_return_position or _match_entrance(game_map, active_key) or overworld_level.player_start
            player.x, player.y = position
            dungeon_inspect_text = {d_id: d.inspect_text for d_id, d in dungeon_registry.items()}
            dungeon_ruin_data = {
                d_id: (d.ruined_tile, d.ruined_description)
                for d_id, d in dungeon_registry.items() if d.ruined_tile
            }
            target = Engine(
                game_map, player, overworld_level.name,
                catalog=catalog, is_overworld=True, dungeon_inspect_text=dungeon_inspect_text,
                dungeon_ruin_data=dungeon_ruin_data,
                clock=clock, quest_log=quest_log, sprite_codepoints=sprite_codepoints,
            )
            active_engines[OVERWORLD_KEY] = target
        else:
            position = engine.overworld_return_position or _match_entrance(target.game_map, active_key) or overworld_level.player_start
            target.arrive_player(player, position)

        armable = _armable_encounter(active_key, target.quest_log, encounter_registry)
        if armable is not None:
            target.quest_log.arm_encounter(armable.id, target.clock.plus_hours(armable.delay_hours))
            encounter = _due_encounter(target.quest_log, encounter_registry, target.clock)
            if encounter is not None:
                return _redirect_into_encounter(
                    encounter, target, active_engines, dungeon_registry, catalog,
                    sprite_codepoints, (target.player.x, target.player.y),
                )

        return OVERWORLD_KEY, target

    if engine.pending_dungeon_entry is not None:
        dungeon_id = engine.pending_dungeon_entry
        player = engine.depart_player()
        target = active_engines.get(dungeon_id)
        if target is None:
            dungeon = dungeon_registry[dungeon_id]
            starting_level = dungeon.levels[dungeon.starting_level]
            game_map, _ = build_game_map(starting_level, catalog, player=player)
            target = Engine(
                game_map, player, starting_level.name,
                catalog=catalog, levels=dungeon.levels, starting_level=starting_level,
                clock=clock, quest_log=quest_log, sprite_codepoints=sprite_codepoints,
            )
            active_engines[dungeon_id] = target
        else:
            target.arrive_player(player)  # position=None: resume exactly where they left
        target.quest_log.record_dungeon_arrival(dungeon_id)
        return dungeon_id, target

    return active_key, engine


def fresh_start(
    catalog, dungeon_registry: dict, overworld_level, quest_defs: dict, sprite_codepoints,
) -> tuple[str, dict[str, Engine], GameClock, QuestLog]:
    """A brand-new run in STARTING_DUNGEON_ID - exactly what main() always
    built before save/load existed, pulled out unchanged so
    build_initial_state can fall back to it when there's no save to
    continue (or the player declines it)."""
    clock = GameClock()
    quest_log = create_quest_log(quest_defs)

    dungeon = dungeon_registry[STARTING_DUNGEON_ID]
    levels = dungeon.levels
    starting_level = levels[dungeon.starting_level]
    game_map, player = build_game_map(starting_level, catalog)
    engine = Engine(
        game_map,
        player,
        starting_level.name,
        catalog=catalog,
        levels=levels,
        starting_level=starting_level,
        clock=clock,
        quest_log=quest_log,
        sprite_codepoints=sprite_codepoints,
    )
    active_key = STARTING_DUNGEON_ID
    active_engines: dict[str, Engine] = {active_key: engine}
    return active_key, active_engines, clock, quest_log


def _check_destroyable_dungeons_have_ruin_content(quest_defs: dict, dungeon_registry: dict) -> None:
    """A quest's on_fail_destroy_dungeon_id (see QuestDef, Engine.destroy_dungeon)
    is only useful if the dungeon it names actually has ruined_tile/
    ruined_description authored (content/schema.py's DungeonDef) - without
    them, Engine.destroy_dungeon has nothing to show and silently no-ops.
    Neither load_quests nor load_dungeon_registry can catch this alone
    (each only sees one side), so it's checked here, right after both are
    loaded, with the same ContentValidationError reporting shape as every
    other content problem."""
    errors: list[str] = []
    for quest_id, quest in quest_defs.items():
        dungeon_id = quest.on_fail_destroy_dungeon_id
        if dungeon_id is None:
            continue
        dungeon = dungeon_registry.get(dungeon_id)
        if dungeon is not None and dungeon.ruined_tile is None:
            errors.append(
                f"quest '{quest_id}': on_fail_destroy_dungeon_id '{dungeon_id}' "
                "has no ruined_tile/ruined_description set in its dungeon.yaml - "
                "Engine.destroy_dungeon would have nothing to show"
            )
    if errors:
        raise ContentValidationError(str(QUESTS_PATH), errors)


def build_initial_state(
    catalog, dungeon_registry: dict, overworld_level, quest_defs: dict, encounter_registry,
    sprite_codepoints, console: tcod.console.Console, context: tcod.context.Context, save_path: Path,
) -> tuple[str, dict[str, Engine], GameClock, QuestLog]:
    """Either restores save_path (if it exists, is readable, and the player
    confirms via prompt_continue_saved_game) or falls back to fresh_start -
    the one place main() decides which. A save that fails to restore (e.g.
    it references a quest/dungeon id that no longer exists in the
    currently loaded content, following a content update since it was
    written) falls back to a fresh start rather than crashing, same spirit
    as a ContentValidationError being reported rather than propagated raw.
    Takes save_path explicitly (main()'s only real caller passes SAVE_PATH)
    rather than reading that module constant directly, so a test can point
    it at a tmp_path location instead."""
    if save_path.exists():
        save = load_from_path(save_path)
        if save is not None and prompt_continue_saved_game(console, context):
            try:
                return restore_save(
                    save, catalog, dungeon_registry, overworld_level, quest_defs,
                    encounter_registry, sprite_codepoints, OVERWORLD_KEY,
                )
            except (KeyError, ValueError):
                pass
    return fresh_start(catalog, dungeon_registry, overworld_level, quest_defs, sprite_codepoints)


def main() -> int:
    try:
        catalog = load_catalog()
        dungeon_registry = load_dungeon_registry(DUNGEONS_DIR, catalog)
        overworld_level = load_overworld(
            OVERWORLD_LEVEL_PATH, catalog, known_dungeon_ids=set(dungeon_registry)
        )
        quest_defs = load_quests(QUESTS_PATH, catalog, known_dungeon_ids=set(dungeon_registry))
        _check_destroyable_dungeons_have_ruin_content(quest_defs, dungeon_registry)
        encounter_registry = load_encounters(
            ENCOUNTERS_PATH,
            known_dungeon_ids=set(dungeon_registry), known_quest_ids=set(quest_defs),
        )
        sprite_manifest = load_sprite_manifest(
            SPRITES_PATH, catalog, known_dungeon_ids=set(dungeon_registry)
        )
    except ContentValidationError as e:
        print(str(e), file=sys.stderr)
        return 1

    tileset = load_tileset()
    sprite_codepoints = apply_sprites(tileset, sprite_manifest, catalog, ASSETS_DIR)

    with tcod.context.new(
        columns=CONSOLE_COLUMNS,
        rows=CONSOLE_ROWS,
        tileset=tileset,
        title="Claude-Authored Roguelike",
    ) as context:
        console = tcod.console.Console(CONSOLE_COLUMNS, CONSOLE_ROWS, order="F")

        active_key, active_engines, clock, quest_log = build_initial_state(
            catalog, dungeon_registry, overworld_level, quest_defs,
            encounter_registry, sprite_codepoints, console, context, SAVE_PATH,
        )
        engine = active_engines[active_key]

        while True:
            render_all(console, engine)
            context.present(console)

            for event in tcod.event.wait():
                context.convert_event(event)
                try:
                    action = handle_event(event)
                except SystemExit:
                    return 0

                if isinstance(action, LookAction):
                    if engine.game_state == "playing":
                        run_look_mode(console, context, engine)
                    continue

                if isinstance(action, TalkAction):
                    if engine.game_state == "playing":
                        engine.talk_to_adjacent()
                    continue

                if isinstance(action, CyclePotionKindAction):
                    if engine.game_state == "playing":
                        engine.cycle_selected_potion_kind()
                    continue

                if isinstance(action, QuestLogAction):
                    if engine.game_state == "playing":
                        run_quest_log_mode(console, context, engine)
                    continue

                if isinstance(action, SaveGameAction):
                    handle_save_game_action(
                        engine, active_key, active_engines, clock, quest_log, overworld_level, SAVE_PATH,
                    )
                    continue

                if isinstance(action, ShopAction):
                    if engine.game_state == "playing":
                        error = shop_gate(engine)
                        if error:
                            engine.message_log.add(error)
                        else:
                            run_shop_mode(console, context, engine)
                    continue

                if isinstance(action, FireModeAction):
                    if engine.game_state == "playing":
                        error = fire_mode_gate(engine)
                        if error:
                            engine.message_log.add(error)
                        else:
                            target = run_target_mode(console, context, engine)
                            if target is not None:
                                dispatch_action(
                                    engine, FireAction(*target),
                                    on_player_turn_resolved=lambda: animate_combat_feedback(console, context, engine),
                                )
                                animate_combat_feedback(console, context, engine)
                                active_key, engine = resolve_transition(
                                    active_key, engine, active_engines,
                                    dungeon_registry, overworld_level, catalog,
                                    clock=clock, quest_log=quest_log,
                                    sprite_codepoints=sprite_codepoints,
                                    encounter_registry=encounter_registry,
                                )
                    continue

                if dispatch_action(
                    engine, action,
                    on_player_turn_resolved=lambda: animate_combat_feedback(console, context, engine),
                ):
                    return 0
                animate_combat_feedback(console, context, engine)
                active_key, engine = resolve_transition(
                    active_key, engine, active_engines, dungeon_registry, overworld_level, catalog,
                    clock=clock, quest_log=quest_log, sprite_codepoints=sprite_codepoints,
                    encounter_registry=encounter_registry,
                )


if __name__ == "__main__":
    raise SystemExit(main())
