"""Standalone content-review tool.

Validates level file(s) against the catalogs and prints an ASCII rendering plus a
summary, with no engine/game loop involved. This is the fast "does this look right"
check for a human reviewing hand-authored (or Claude-authored) content.

Usage:
    python tools/preview.py data/levels/level_01.lvl   # single level
    python tools/preview.py data/levels                # whole dungeon (all .lvl
                                                         # files), including
                                                         # cross-checking every
                                                         # stairway's destination
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from content.loader import ContentValidationError, load_catalog, load_dungeon, load_level

TILE_GLYPHS = {
    "wall": "#",
    "floor": ".",
    "stairs_down": ">",
    "player_start": "@",
    "door": "+",
}


def render(level) -> str:
    """Reconstruct the map from parsed tiles + spawns, as an independent check
    that the loader placed everything where the source file said to."""
    grid = [[TILE_GLYPHS[tile] for tile in row] for row in level.tiles]

    for spawn in level.item_spawns:
        grid[spawn.y][spawn.x] = spawn.item.glyph
    # Entities drawn last so they're visible even standing on an item tile.
    for spawn in level.entity_spawns:
        grid[spawn.y][spawn.x] = spawn.entity.glyph

    px, py = level.player_start
    grid[py][px] = "@"

    return "\n".join("".join(row) for row in grid)


def summarize(level) -> str:
    entity_counts = Counter(s.entity.name for s in level.entity_spawns)
    item_counts = Counter(s.item.name for s in level.item_spawns)

    lines = [
        f"id: {level.id}",
        f"name: {level.name}",
        f"size: {level.width}x{level.height}",
        f"player_start: {level.player_start}",
        "stairways:",
    ]
    for stairs in level.stairs:
        destination = stairs.next_level if stairs.next_level is not None else "WIN (terminal)"
        lines.append(f"  ({stairs.x}, {stairs.y}) -> {destination}")

    if level.doors:
        lines.append("doors:")
        for door in level.doors:
            lines.append(f"  ({door.x}, {door.y}) -> requires '{door.requires_key}'")

    lines.append("monsters:")
    lines += [f"  {count}x {name}" for name, count in entity_counts.items()] or ["  (none)"]
    lines.append("items:")
    lines += [f"  {count}x {name}" for name, count in item_counts.items()] or ["  (none)"]
    return "\n".join(lines)


def preview_one(level) -> None:
    print(render(level))
    print()
    print(summarize(level))


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: python {argv[0]} <level_file.lvl | levels_dir>", file=sys.stderr)
        return 2

    target = Path(argv[1])

    try:
        catalog = load_catalog()
        if target.is_dir():
            levels = load_dungeon(target, catalog)
            for i, level_id in enumerate(sorted(levels)):
                if i > 0:
                    print("\n" + "=" * 40 + "\n")
                preview_one(levels[level_id])
        else:
            preview_one(load_level(target, catalog))
    except ContentValidationError as e:
        print(str(e), file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
