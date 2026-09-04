# Procedural Generation Algorithms

`tools/procgen/` is a library of level-generation algorithms, built so a
future Claude session (or a human) can choose one and a set of parameters
to fit a specific dungeon or region bible's terrain description, rather
than hand-drawing ASCII maps from scratch every time - the practical
motivation described in `docs/content_design_process.md`'s own authoring
discipline. Every algorithm shares the same shape:

- Lives in its own module under `tools/procgen/`, exposing a
  `generate(seed, width, height, ...)` function that returns a
  `tools.procgen.base.Grid` of plain terrain (`content/schema.py`'s
  `TileType`) - no player_start, stairs, entities, items, doors, or
  decoration. Placing those, and validating the result, is a separate
  authoring step (by hand, or via a future CLI - see `tools/procgen/base.py`'s
  `to_lvl_yaml`), consistent with the project's bible-first convention: a
  generator produces a skeleton, a dungeon/region bible-driven pass dresses
  it.
- `tools/procgen/base.py` supplies the shared plumbing every algorithm
  builds on: `Grid`, connectivity helpers (`connected_component`,
  `keep_largest_component`, `farthest_pair` - the same "largest-connected-
  component extraction, entry/exit chosen to maximize graph distance"
  discipline first used ad hoc for Silver Mountain Caves levels 03-05, see
  `docs/content_design_process.md` §0ae, now reusable), corridor carving
  (`carve_room`, `carve_l_corridor` for real 90-degree bends), and
  `to_lvl_yaml` (renders a Grid + overlays as a real `.lvl` file's text).
- Tested in `tests/test_procgen_<name>.py`: seed determinism, bounds
  respected, and connectivity/invariant checks - never exact tile-by-tile
  output, which isn't meaningful for anything procedural.

This document tracks each algorithm as it lands: what it produces, what
bible language it fits, and a worked real-content example where one
exists. Algorithms are being added one at a time (see the Dust Reach
region, `docs/region_bibles/dust_reach.md`, built specifically to host one
small test dungeon per algorithm) - this file grows a new section per
landing, oldest first below matches build order.

## Noise terrain (`tools/procgen/noise_terrain.py`)

Fractal value noise (a lattice of random values, bilinearly interpolated
with a smoothstep fade curve, summed across octaves for fractal Brownian
motion - the same *kind* of continuous field classic Perlin noise
produces, without needing a third-party noise library) thresholded into
terrain bands. Produces broad, continuous, naturalistic terrain -
plains/forest/mountain/sea blending into each other - not room-and-
corridor structure. This is an **overworld-cell** generator, not a
dungeon-level one; a generated `Grid` still round-trips through
`to_lvl_yaml`/`load_level` (useful for testing), but wiring its output
into the actual `data/overworld/cells/*.lvl` + `cells.lvl` stitching
format (`content/loader.py`'s `load_overworld`) is presently a manual step
(see the worked example below), not yet automated by a CLI.

**Fits bible language like**: "open plains blending into forest," "a
mountain ridge thickening toward the north," "rolling, naturalistic
terrain" - anything describing a *region's* broad shape rather than a
building or cave's internal layout.

**Signature**: `generate(seed, width, height, scale=20.0, octaves=4,
persistence=0.5, lacunarity=2.0, thresholds=None, band_kinds=None)`.
`scale` is the lattice spacing in tiles (bigger = broader, slower-changing
features - start around `width/6` for one or two major landforms across
the whole grid). `thresholds`/`band_kinds` divide the noise field's `[0,
1]` range into bands (`len(band_kinds) == len(thresholds) + 1`); the
default (`DEFAULT_THRESHOLDS`/`DEFAULT_BAND_KINDS`) is `sea` below 0.3,
`plains` to 0.55, `forest` to 0.8, `mountain` above that. Directional bias
(e.g. more mountain toward one edge, to continue a mountain spine across a
cell boundary) isn't a library parameter - apply it in the calling script
by nudging the threshold per-row/column before calling `generate`, the way
the worked example below does, so the reusable algorithm itself stays
generic.

**Worked example**: `data/overworld/cells/dust_reach.lvl` (150x90, west of
`heartlands.lvl`) - seed 1, `scale=24.0`, `thresholds=[0.58, mountain]`
where the mountain threshold ramps from 0.85 at the south edge to 0.57 at
the north edge (more mountain the further north, continuing the spine
`docs/world_history.md`'s Geography section already establishes).
`data/overworld/cells/cragspine.lvl` (the same cell size, filling the
grid's remaining northwest slot) reuses the same generator with a heavily
mountain-weighted threshold (seed 10, `thresholds=[0.15, 0.3]`, ~94%
mountain) to read as unmapped high country rather than real content. See
`docs/region_bibles/dust_reach.md` for the full design reasoning.
