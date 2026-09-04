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
  (`carve_room`, `carve_l_corridor` for real 90-degree bends), `frame_border`
  (overwrites the outer ring with wall - a hand-authored level is always
  enclosed on every side, e.g. `data/dungeons/millhaven/levels/level_01.lvl`,
  but plenty of these algorithms' raw output isn't, so **call
  `frame_border` before `keep_largest_component`/`farthest_pair` as a
  standard last step whenever assembling a real dungeon file**, even for
  an algorithm that mostly keeps clear of the edge on its own), and
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

## Wave function collapse (`tools/procgen/wave_function_collapse.py`)

A general small constraint-propagation solver, not a fixed algorithm with
tunable parameters like the others here - the caller supplies a `tileset`
(`dict[str, TileSpec]`, each `TileSpec` a collapse `weight` plus, per
direction (`N`/`S`/`E`/`W`), the set of tile names allowed immediately in
that direction) and gets a grid where every adjacency obeys those rules
everywhere, not just locally (lowest-entropy-cell-first collapse, worklist
constraint propagation to neighbors, bounded retries on contradiction, a
non-strict best-effort fallback if every retry contradicts so it always
terminates). This is the one algorithm here whose real value is entirely
in the tileset a caller brings - `DEFAULT_TILESET` (two tiles, `floor` and
`wall`, with the hard rule that no two `wall` tiles may ever be adjacent)
is a minimal, always-satisfiable demo, not the interesting case.

**Fits bible language like**: "obeys a specific visual rule everywhere,"
"never two of X touching," "a repeating motif with hard adjacency rules" -
anything where local placement has to satisfy a *global* pattern
constraint a purely local algorithm (cellular automata's neighbor-count
rule, a random walk) can't guarantee. A real dungeon-specific use means
authoring a real tileset (more than two tile names, meaningful per-
direction adjacency) to match that bible's own vocabulary - the built-in
default is a working example of the shape, not a template to keep reusing
as-is.

**Signature**: `generate(seed, width, height, tileset=None, max_retries=20)`.
`tileset` defaults to `DEFAULT_TILESET`; adjacency should be authored
symmetrically (see `TileSpec`'s docstring) or contradictions become
common and `max_retries` gets burned rediscovering the same asymmetry
every attempt.

**Worked example**: `data/dungeons/fallen_colonnade/levels/level_01.lvl`
(45x30, `DEFAULT_TILESET`, seed 5, framed with `frame_border` since the
tileset has no concept of an edge and would otherwise leave floor sitting
on the map's own boundary) - an Old Kingdom hall on Dust Reach, an even
scatter of isolated single-tile pillars across open floor, entrance
placed via `docs/dungeon_bibles/fallen_colonnade.md`. Its
`dungeon_entrance` sits at (75, 45) in `data/overworld/cells/dust_reach.lvl`.

## Road network (`tools/procgen/road_network.py`)

An agent-based generator, not a grid-fill: four walkers start at the
grid's center, one heading each cardinal direction, each stepping forward
and carving `road` over a `plains` field, occasionally turning
(`turn_chance`) and occasionally spawning a branch walker
(`branch_chance`, capped by `max_branches`). No buildings - this is purely
the road skeleton half of laying out a settlement; building footprints are
a later, bible-driven authoring pass on top, per the project's "draw
roads first" settlement-layout convention. The generator's own output has
no wall anywhere (roads/plains reach every edge); a real dungeon built
from it should still call `frame_border` afterward and punch one gap
through for a gate, the same way a real settlement is walled with a
single entrance (see `data/dungeons/millhaven`).

**Fits bible language like**: "a crossroads," "roads worn into the
ground before anything's been built," "the leading edge of present-day
traffic reaching somewhere new" - an outdoor, peaceful, non-progression
place (`requires_stairs_down: false` on the `dungeon.yaml`, matching
`data/dungeons/millhaven`'s shape) rather than a combat dungeon. Inside
the boundary, the whole field is walkable `plains`, so roads there are a
purely visual/flavor distinction, not a navigation constraint - there's
no "getting lost off the road" mechanic here.

**Signature**: `generate(seed, width, height, turn_chance=0.06,
branch_chance=0.03, max_branches=10, max_segment_length=300,
base_kind="plains", road_kind="road")`. Every walker stops at the grid
edge or after `max_segment_length` steps, whichever comes first.

**Worked example**: `data/dungeons/dust_crossing/levels/level_01.lvl`
(45x30, seed 2, `turn_chance=0.05, branch_chance=0.04, max_branches=8`,
framed with `frame_border` then a single gap punched through the wall
next to a road tile that originally reached the edge) - a crossroads on
Dust Reach with no settlement built yet, `player_start` at the network's
own center and a terminal `stairs_up` "gate" at that gap. See
`docs/dungeon_bibles/dust_crossing.md`. Its `dungeon_entrance` sits at
(30, 20) in `data/overworld/cells/dust_reach.lvl`.

## Voronoi region partitioning (`tools/procgen/voronoi_regions.py`)

Scatters `num_regions` seed points, raster-assigns every cell to its
nearest one (brute-force distance - no computational-geometry library, none
is in requirements.txt, and it's fast enough at level-grid sizes), then
erodes a `wall_margin`-tile buffer around every region boundary to `wall`.
What survives per region reads as a distinct room; every pair of regions
whose cells actually touch gets a corridor between their seed points, so
the whole layout stays one connected graph. Produces a warren of
irregularly-shaped, walled-off chambers - visually distinct from both
BSP's rectangular rooms and cellular automata's smooth cave blobs.

**Fits bible language like**: "a warren of small chambers," "oddly
regular, too deliberate to be natural" (a good mechanical match for an
Elder Age site's usual vagueness - organic-looking boundaries that are
nonetheless too evenly divided to be a real cave), "a district of
distinct rooms" for a settlement or multi-biome dungeon at larger scale.

**Signature**: `generate(seed, width, height, num_regions=8,
wall_margin=2)`. More regions means smaller, more numerous chambers; a
larger `wall_margin` means thicker walls and less floor area overall (see
`tests/test_procgen_voronoi_regions.py`'s
`test_more_regions_produce_more_floor_area_than_a_single_region`).

**Worked example**: `data/dungeons/cloven_warren/levels/level_01.lvl`
(45x30, seed 1, `num_regions=9, wall_margin=1`, framed with `frame_border`
since a region right at the raster's edge can otherwise reach the map's
own boundary unwalled) - an Elder Age warren of small partitioned
chambers on Dust Reach, no guardian or explanation attached. See
`docs/dungeon_bibles/cloven_warren.md`. Its `dungeon_entrance` sits at
(130, 15) in `data/overworld/cells/dust_reach.lvl`.

## Diffusion-limited aggregation (`tools/procgen/dla.py`)

A single floor tile seeds the grid's center; random walkers spawn near
the aggregate's current frontier (a square `spawn_margin` tiles beyond its
farthest floor tile so far - spawning further out, right on the literal
grid border, causes a saturation artifact, see `_spawn_on_square`'s
docstring) and take a 4-directional random walk until they touch existing
floor, at which point they stick. Growth is asymmetric and branching -
the structure thickens wherever walkers happen to stick more, the way
roots, cracks, or mineral veins actually grow - visually distinct from
cellular automata's smooth, evenly-rounded blobs and from Voronoi's
straight-walled rooms.

**Fits bible language like**: "branches outward like roots or veins,"
"grew this way rather than being carved," "asymmetric, no two arms alike"
- a natural, no-era-or-faction site (the same category
`silver_mountain_caves` belongs to) where the shape itself is the whole
premise, not a ruin or a built structure.

**Signature**: `generate(seed, width, height, fill_fraction=0.35,
max_walker_steps=2000, max_attempts=20000, spawn_margin=6)`. Note: the
aggregate can only grow within a region kept strictly inside the grid
(`max_interior_radius`, computed from the grid's own dimensions) - on a
small or very non-square grid this caps how much of `fill_fraction` is
actually reachable before generation exhausts `max_attempts` and stops
early; a larger, closer-to-square grid gives the branching structure more
room to read as branching rather than saturating into a dense blob (this
is why the worked example below uses 60x40 rather than the 45x30 the
other algorithms' test dungeons use).

**Worked example**: `data/dungeons/rootfall_hollow/levels/level_01.lvl`
(60x40, seed 8, `fill_fraction=0.18, spawn_margin=14, max_attempts=40000`,
still framed with `frame_border` even though the interior-radius cap
mostly keeps growth off the edge already - a walker's random walk isn't
itself confined the way its spawn point is, so it can occasionally reach
and stick right at the true boundary) - a natural, no-era hollow on Dust
Reach that grew rather than was dug. See
`docs/dungeon_bibles/rootfall_hollow.md`. Its `dungeon_entrance` sits at
(100, 80) in `data/overworld/cells/dust_reach.lvl`.

## Maze generation (`tools/procgen/maze.py`)

A recursive-backtracker random walk over a doubled-coordinate cell grid:
logical maze cells sit at odd tile coordinates two tiles apart, and
visiting an unvisited neighbor cell carves the tile between as a
corridor, backtracking via a stack when a cell has no unvisited neighbor
left. By default (`braid=0`) this produces a *perfect* maze - exactly one
path between any two cells, no loops, every corridor purposeful. A
`braid` pass afterward knocks some dead ends into loops (see the
algorithm's own docstring for the exact rule), trading maze purity for a
less punishing, less backtrack-heavy layout. **Note**: unlike every other
generator here, `width`/`height` still describe the *returned grid's*
tile dimensions (consistent with the rest of the library) - but only
`(width - 1) // 2` maze cells actually fit along that axis, so pass an
odd width/height to use the grid fully.

**Fits bible language like**: "a labyrinth," "deliberately confusing, not
natural," "exactly one way through" (braid=0) or "a maze with a few
shortcuts worn into it" (braid>0) - a built, purposeful structure (a
security maze, a puzzle vault), never a cave or ruin.

**Signature**: `generate(seed, width, height, braid=0.0)`. Already
enclosed by construction for an odd width/height (a solid wall column/row
survives past the last cell on each axis) - `frame_border` is still
called at the end regardless, for consistency with the rest of the
library rather than because this algorithm specifically needs it.

**Worked example**: `data/dungeons/tangle_lock/levels/level_01.lvl`
(45x29, seed 3, `braid=0.15`) - an Old Kingdom security maze on Dust
Reach, what it once guarded left unstated. See
`docs/dungeon_bibles/tangle_lock.md`. Its `dungeon_entrance` sits at
(60, 10) in `data/overworld/cells/dust_reach.lvl`.

## Room accretion (`tools/procgen/room_accretion.py`)

Rejection sampling, not a partition: repeatedly proposes a random-sized
rectangular room at a random position, accepting it only if it doesn't
overlap any already-placed room plus a `buffer`-tile gap, then corridor-
connects each accepted room to whichever already-placed room is nearest
(center to center, via `carve_l_corridor`). Unlike BSP (rooms derived from
a recursive partition tree) or Voronoi (rooms derived from a raster
diagram), placement here has no underlying structure at all - rooms land
wherever they happen to fit, so spacing and arrangement read as genuinely
irregular rather than following a hidden geometric rule.

**Fits bible language like**: "a scatter of rooms, none of them
matching," "built rather than found, but unplanned," "irregular spacing,
no underlying pattern" - a practical, improvised structure (a camp, a
squatted-and-expanded ruin) rather than anything laid out on purpose the
way a maze or a formal building would be.

**Signature**: `generate(seed, width, height, min_room_size=4,
max_room_size=10, buffer=1, num_attempts=200)`. Most attempts near the
end of a run fail as the grid fills up - that's expected, not a bug;
`num_attempts` is a budget, not a guaranteed room count.

**Worked example**: `data/dungeons/ragged_camp/levels/level_01.lvl`
(45x30, seed 4, `min_room_size=3, max_room_size=8, buffer=1,
num_attempts=300`) - an Opportunists' camp on Dust Reach, built rather
than squatted since there was nothing here to squat, since abandoned. See
`docs/dungeon_bibles/ragged_camp.md`. Its `dungeon_entrance` sits at
(145, 55) in `data/overworld/cells/dust_reach.lvl`.

## Drunkard's walk (`tools/procgen/drunkards_walk.py`)

The simplest generator here: one or more random walkers, 4-directional,
carving floor at every step. The first walker starts at the grid's
center; every later one starts from a random already-carved floor tile,
so the whole result stays one connected component by construction no
matter how many walkers run. Produces narrow, winding, purely organic
tunnels - no straight walls (unlike BSP/room accretion/maze), no
branching dendrite structure (unlike DLA), no smooth rounded blobs
(unlike cellular automata, next up).

**Fits bible language like**: "a tunnel that wanders rather than runs
straight," "narrow, winding, no straight walls," "the way a mined seam
actually follows ground rather than a surveyor's line" - naturally-worn
or hand-dug-by-following-something passages, not a built or excavated-
on-purpose structure.

**Signature**: `generate(seed, width, height, fill_fraction=0.4,
walker_count=1, max_steps_per_walker=50000, brush_radius=0)`. A walker's
random walk isn't capped the way DLA's spawn point is, so it can reach
the true grid edge on its own - **`frame_border` matters more here than
for most other algorithms in this run**.

**Worked example**: `data/dungeons/long_drift/levels/level_01.lvl`
(45x30, seed 5, `fill_fraction=0.32, walker_count=3, brush_radius=0`) -
an unclaimed Old Kingdom mining tunnel on Dust Reach, a different seam
from `sunken_mine` and unrelated to it. See
`docs/dungeon_bibles/long_drift.md`. Its `dungeon_entrance` sits at
(5, 15) in `data/overworld/cells/dust_reach.lvl`.
