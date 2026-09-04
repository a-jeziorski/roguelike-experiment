"""A library of procedural level-generation algorithms for this roguelike.

Each module under tools/procgen/ implements one algorithm and exposes a
`generate(...)` function returning a tools.procgen.base.Grid of plain
terrain (see content/schema.py's TileType) - no player_start, stairs,
entities, items, doors, or decoration. Placing those, and validating the
result, is tools/procgen/cli.py's job, which converts a Grid to the same
.lvl YAML format every hand-authored level uses (content/loader.py's
load_level).

See docs/procgen_algorithms.md for what each algorithm produces and which
dungeon-bible language it fits.
"""
