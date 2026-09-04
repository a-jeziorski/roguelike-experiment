# Dust Reach — Region Bible

*Written per the region-bible convention `docs/region_bibles/northern_steppe.md`
established: decide the terrain and the tone before any ASCII is drawn, even
for a cell whose actual purpose this pass is infrastructure - exercising
`tools/procgen/`'s generator library against real, shipped content rather
than throwaway samples. See `docs/world_history.md` for the realm-level
facts this still has to agree with.*

## The pitch

`docs/world_history.md`'s Geography section already establishes "a drier
hill/badlands stretch to the west" *within* the Heartlands cell itself -
Broken Watch and Stonebridge sit there. Dust Reach is what's past that:
a whole new overworld cell, connected west of `heartlands.lvl` in
`data/overworld/cells.lvl`'s grid, continuing the same dry, rugged
character further out - rougher, sparser, and further from anyone's road
than the badlands the player already knows. Nobody in the present-day
roster (Millhaven, Wayford, the rest) has settled or mapped it yet.

Unlike the Northern Steppe, this bible does **not** pre-commit named set
pieces. Dust Reach exists to hold a short run of small test dungeons, one
per procedural-generation algorithm landing in `tools/procgen/` (see
`docs/procgen_algorithms.md`), added one at a time as each algorithm is
implemented. Each of those dungeons still gets its own dungeon bible when
it's built, per the usual per-dungeon discipline - this document only
covers the terrain and the tone they all have to sit inside, not who or
what is out here. That's deliberately decided per-dungeon as each one
lands, the same way Silver Mountain Caves' "natural, no era or faction"
framing was a per-dungeon call, not something a region bible dictated in
advance.

## Mood

Empty, dry, unclaimed. Open plains and sparse forest pockets, rockier and
less hospitable than the Heartlands proper, with mountain ridges breaking
the ground more often the further north you look. Nothing here reads as
dangerous by itself - it reads as *unattended*, which is exactly what
makes it a plausible place for a handful of small, unrelated things (a
mine, a ruin, a cave, a camp) to have gone quietly undiscovered.

## Structure overview

One overworld cell (`data/overworld/cells/dust_reach.lvl`, 150x90,
stitched west of `heartlands.lvl` via `cells.lvl`'s 2x2 grid), generated
with `tools/procgen/noise_terrain.py` (fractal value noise, seed 1,
`scale=24.0`, `octaves=4`, thresholds `[0.58, mountain]` where the
mountain threshold itself ramps from 0.85 at the cell's south edge down
to 0.57 at its north edge - biasing mountain coverage upward toward the
top of the cell so the terrain visibly thickens into a ridge going north,
the same way `docs/region_bibles/northern_steppe.md` describes its own
mountain spine "thickening... as it goes north" rather than stopping flat
at a cell boundary). The result is mostly open plains, forest in loose
pockets, and mountain concentrated as a northward-thickening ridge line -
verified fully connected from the Heartlands seam (every walkable tile in
the cell is reachable from the player's start; see
`tests/test_loader.py::test_load_overworld_dust_reach_is_reachable_from_the_player_start`).

**Cragspine** (`data/overworld/cells/cragspine.lvl`, same 150x90, north of
Dust Reach and west of Northern Steppe) fills the 2x2 grid's remaining
slot - the loader requires a full rectangle, and there's nothing narrative
that needs to live there yet. It's the same noise generator run with an
almost entirely mountain-weighted threshold (seed 10, thresholds
`[0.15, 0.3]`, ~94% mountain), read as the mountain spine's own bulk
continuing off the presently-mapped world rather than a real, explorable
place - the reason the map doesn't (yet) extend further northwest. It has
no player_start and no dungeon_entrance, and doesn't need either.

## Roster

Zero entities, zero items - matches every overworld cell (`load_overworld`
never produces spawns for any cell). Zero `dungeon_entrance` tiles as of
this pass; each subsequent procgen-algorithm pass adds exactly one, for
that pass's test dungeon.

## Tone notes for anyone (agent or human) revising this later

- Don't pre-assign an era or faction to Dust Reach as a whole. It's
  deliberately blank so each test dungeon can pick whatever era/faction
  fits its own generator best (an Old Kingdom mine for a branching-tunnel
  algorithm, a natural cave for an organic one, and so on) without this
  document constraining the choice in advance.
- Keep entrances spread out rather than clustered - this is meant to read
  as a handful of unrelated things scattered across genuinely empty
  country, not one dungeon complex with several doors.
- Cragspine stays undeveloped on purpose. If a future pass wants real
  content northwest of here, that's a new decision, not an oversight this
  document left open.
