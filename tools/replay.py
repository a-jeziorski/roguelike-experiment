"""Watches a recorded tools/play_llm.py session back with real sprite art,
using the exact same rendering code (engine/render.py, engine/sprites.py)
main.py's graphical client uses.

Never re-runs game logic or randomness: each recorded frame is a full
SaveGame snapshot of already-decided history (see tools/play_llm.py's
--record, engine/save.py's capture_save/restore_save), so stepping through
frames only changes what's *displayed*, never the game state itself - see
docs/content_design_process.md §0ao for why this is a state-snapshot
recorder rather than an action-replay one (combat/AI randomness would make
replayed actions diverge from what actually happened).

Usage:
    python tools/play_llm.py --record saves/demo.jsonl new
    python tools/play_llm.py --record saves/demo.jsonl move n
    ...
    python tools/replay.py saves/demo.jsonl
    python tools/replay.py saves/demo.jsonl --speed 0.25

Controls:
    Right / Space / N    next frame
    Left / Backspace / P previous frame
    Home / End           jump to first / last frame
    F                    toggle autoplay (stops at the last frame, doesn't loop)
    + / -                adjust autoplay speed
    Escape / Q           quit
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tcod.console
import tcod.context
import tcod.event

from content.loader import load_sprite_manifest
from engine.engine import Message
from engine.render import render_all
from engine.save import SaveGame, restore_save
from engine.sprites import apply_sprites
from main import ASSETS_DIR, CONSOLE_COLUMNS, CONSOLE_ROWS, OVERWORLD_KEY, SPRITES_PATH, load_tileset
from tools.play_llm import load_content

# Two extra rows below the real HUD/map/log layout, reserved for this
# viewer's own frame/command caption - render_all itself is never touched,
# so the game area looks pixel-identical to a real play_llm session.
CAPTION_ROWS = 2
CAPTION_FG = (200, 200, 200)
NOTES_FG = (150, 150, 150)

MIN_SPEED = 0.05
MAX_SPEED = 5.0


def load_frames(path: Path) -> list[dict]:
    """Reads a --record JSON-Lines file into a list of frame dicts, oldest
    first - the same objects tools/play_llm.py's _append_replay_frame wrote.
    Raises rather than silently showing an empty window for a missing or
    empty recording."""
    if not path.exists():
        raise FileNotFoundError(f"No such recording: {path}")
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        raise ValueError(f"{path} has no recorded frames - nothing to replay.")
    return [json.loads(line) for line in lines]


def clamp_index(current: int, delta: int, total: int) -> int:
    """current + delta, clamped to [0, total - 1] - shared math for next/
    prev (delta=+-1) and first/last (delta=+-total, always clamping to an
    edge)."""
    return max(0, min(total - 1, current + delta))


def _build_engine_for_frame(
    frame: dict, catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry, sprite_codepoints,
):
    """Rebuilds the exact Engine a real save-load would for this frame's
    snapshot (restore_save - no new reconstruction logic), then overwrites
    its message log with the frame's own recorded messages - restore_save
    always starts with an empty log by design (SaveGame never persists
    messages), which is correct for real gameplay resumption but would
    otherwise make every replayed frame's log panel blank."""
    save = SaveGame.model_validate(frame["save"])
    active_key, active_engines, _clock, _quest_log = restore_save(
        save, catalog, dungeon_registry, overworld_level, quest_defs,
        encounter_registry, sprite_codepoints, OVERWORLD_KEY,
    )
    engine = active_engines[active_key]
    engine.message_log.messages = [
        Message(m["text"], m["category"], m["speaker"]) for m in frame["messages"]
    ]
    return engine


def _handle_replay_event(event: tcod.event.Event) -> str | None:
    """This viewer's own tiny keymap - deliberately separate from
    engine/input_handlers.py, since frame navigation isn't a gameplay
    concern (same reasoning tools/preview.py/tools/balance.py already have
    their own bespoke logic rather than extending the core input layer)."""
    if isinstance(event, tcod.event.Quit):
        return "quit"
    if isinstance(event, tcod.event.KeyDown):
        sym = event.sym
        if sym in (tcod.event.KeySym.RIGHT, tcod.event.KeySym.SPACE, tcod.event.KeySym.N):
            return "next"
        if sym in (tcod.event.KeySym.LEFT, tcod.event.KeySym.BACKSPACE, tcod.event.KeySym.P):
            return "prev"
        if sym == tcod.event.KeySym.HOME:
            return "first"
        if sym == tcod.event.KeySym.END:
            return "last"
        if sym == tcod.event.KeySym.F:
            return "toggle_play"
        if sym in (tcod.event.KeySym.PLUS, tcod.event.KeySym.KP_PLUS, tcod.event.KeySym.EQUALS):
            return "speed_up"
        if sym in (tcod.event.KeySym.MINUS, tcod.event.KeySym.KP_MINUS):
            return "speed_down"
        if sym in (tcod.event.KeySym.ESCAPE, tcod.event.KeySym.Q):
            return "quit"
    return None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("record", help="Path to a --record JSON-Lines file (see tools/play_llm.py).")
    parser.add_argument(
        "--speed", type=float, default=0.5,
        help="Seconds per frame during autoplay (default: 0.5).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        frames = load_frames(Path(args.record))
    except (FileNotFoundError, ValueError) as e:
        print(str(e), file=sys.stderr)
        return 1

    catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry = load_content()
    sprite_manifest = load_sprite_manifest(SPRITES_PATH, catalog, known_dungeon_ids=set(dungeon_registry))
    tileset = load_tileset()
    sprite_codepoints = apply_sprites(tileset, sprite_manifest, catalog, ASSETS_DIR)

    current = 0
    speed = args.speed
    playing = False

    with tcod.context.new(
        columns=CONSOLE_COLUMNS, rows=CONSOLE_ROWS + CAPTION_ROWS, tileset=tileset,
        title="Roguelike Replay",
    ) as context:
        console = tcod.console.Console(CONSOLE_COLUMNS, CONSOLE_ROWS + CAPTION_ROWS, order="F")

        while True:
            frame = frames[current]
            engine = _build_engine_for_frame(
                frame, catalog, dungeon_registry, overworld_level, quest_defs, encounter_registry,
                sprite_codepoints,
            )
            render_all(console, engine)
            caption = f"Frame {current + 1}/{len(frames)}: {' '.join(frame['argv']) or '(none)'}"
            if playing:
                caption += f"  [playing, {speed:.2f}s/frame]"
            console.print(0, CONSOLE_ROWS, caption, fg=CAPTION_FG)
            if frame["notes"]:
                console.print(0, CONSOLE_ROWS + 1, "  ".join(frame["notes"]), fg=NOTES_FG)
            context.present(console)

            # Blocks indefinitely while paused (no CPU spin waiting for a
            # keypress); while playing, returns after `speed` seconds even
            # with no events, which is what actually drives autoplay below.
            events = list(tcod.event.wait(timeout=speed if playing else None))
            moved = False
            for event in events:
                context.convert_event(event)
                result = _handle_replay_event(event)
                if result == "quit":
                    return 0
                if result == "next":
                    current = clamp_index(current, 1, len(frames))
                    playing = False
                    moved = True
                elif result == "prev":
                    current = clamp_index(current, -1, len(frames))
                    playing = False
                    moved = True
                elif result == "first":
                    current = 0
                    playing = False
                    moved = True
                elif result == "last":
                    current = len(frames) - 1
                    playing = False
                    moved = True
                elif result == "toggle_play":
                    playing = not playing
                elif result == "speed_up":
                    speed = max(MIN_SPEED, speed / 1.5)
                elif result == "speed_down":
                    speed = min(MAX_SPEED, speed * 1.5)

            if playing and not moved:
                # The timeout elapsed with nothing meaningful pressed -
                # autoplay's own advance. Stops at the end rather than
                # looping back to the start.
                if current < len(frames) - 1:
                    current += 1
                else:
                    playing = False


if __name__ == "__main__":
    raise SystemExit(main())
