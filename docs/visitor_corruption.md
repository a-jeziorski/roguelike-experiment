# Progressing Overworld Corruption — Design Plan

**Status (2026-09-05): shipped end to end.** All 7 implementation steps
below are done - schema/loader, the tile-remap/uncover engine mechanics,
save wiring, real content (Watch Post razing, both Elder Age dungeons,
all 4 corruption phases), and the graphical client's fade-to-black. This
document is kept as both the design record (read it before touching this
mechanic) and the step-by-step log of what actually shipped and when,
including the real-playtesting fixes and mid-course corrections found
along the way - not rewritten into a clean "as if we knew this from the
start" spec.

*Originally: resolves the open question `docs/main_story.md`'s "Mechanical
grounding" section flagged as genuinely new ("region-scale overworld
corruption... not yet chosen") and the thing
`docs/region_bibles/northern_steppe.md` explicitly declined to build
("Not a 'region corruption swap' mechanic... this region does not build
that - it's hand-authored as a single static snapshot"). This document
was the design pass main_story.md asked for.*

## Decisions made before drafting this plan

Four scoping questions were resolved with the user before design began;
recorded here so a future reader doesn't have to reconstruct the reasoning:

1. **Target region: the Northern Steppe, retrofit.** Not a brand-new
   region. The Steppe already ships as a static "the Visitor has been here
   for months" snapshot (three corruption bands, one built settlement -
   the Watch Post - two reserved-but-unbuilt Elder Age landmarks). This
   pass makes that snapshot start moving again in real time, picking up
   exactly where the region bible left off.
2. **Spread mechanism: programmatic radius/wavefront**, not hand-authored
   per-phase level files. Generalizes the single-tile
   `apply_dungeon_destruction` pattern (`engine/game_map.py`) that already
   powers dungeon razing - matches main_story.md's own "cheaper, less
   bespoke" framing of this option.
3. **Phase trigger: fixed in-game days**, reusing `GameClock`/deadline-check
   machinery (`QuestLog.check_deadlines`, `Engine._check_quest_deadlines`)
   almost as-is, rather than deriving phase timing from the (unbuilt)
   master Visitor-deadline quest.
4. **Content scope: wire the mechanic to what's already reserved.** No new
   named locations beyond the Northern Steppe bible's own two Hollow Reach
   Elder Age landmarks. The "necrocraft infestation" reuses the existing,
   already-designed Visitor bestiary (`ash_bound_husk` through
   `excavation_warden`, `data/entities.yaml`) rather than adding monsters.

## What already exists to build on

Everything below is real, shipped code/content this plan reuses rather
than reinvents:

- **Single-tile world mutation, with save-replay idempotency**:
  `apply_dungeon_destruction(game_map, dungeon_id, ruined_tile,
  ruined_description, ruined_starting_level)` in `engine/game_map.py` -
  swaps `kinds`/`walkable`/`transparent` in lockstep via
  `TILE_PASSABILITY`, updates `tile_descriptions`, optionally pops the
  tile from `dungeon_entrances`. Called both live
  (`Engine.destroy_dungeon`) and replayed on every save load
  (`engine/save.py`'s `restore_save`, for every id in
  `QuestLog.destroyed_dungeon_ids`) - because `build_game_map` always
  rebuilds from the static, unmodified level file, so every one-time
  mutation has to be redone after a fresh load, not just applied once.
- **Deadline-driven world consequences**: `WorldConsequence`
  (`content/schema.py`) - exactly one of `destroy_dungeon_id`/`set_flag`/
  `tighten_deadline` - fired from `QuestLog.check_deadlines` via
  `Engine._check_quest_deadlines`/`_apply_world_consequences`, called once
  per turn, only while `self.is_overworld` (`GameClock` only advances on
  the overworld). Deliberately fires for `not_given` quests too, not just
  `in_progress` - "the world moves on regardless of what the player did."
- **A scheduled, due-time world event**: `QuestLog.armed_encounters`
  (`dict[str, tuple[year, day, hour]]`), armed via
  `GameClock.plus_hours`, checked and consumed elsewhere in `Engine`. The
  closest existing precedent for "something fires automatically once the
  clock passes a stored timestamp," independent of any specific quest.
- **The Northern Steppe's own corrupted-terrain tiles**: `ashen_plains`
  (replaces `plains`) and `blighted_forest` (replaces `forest`), both
  already registered `TileType` values with hazard/passability behavior
  defined (`content/schema.py`, `Engine.ENVIRONMENTAL_HAZARD_MESSAGES`).
  **No new `TileType` values are needed for this pass** - the phases just
  grow the area these two already-shipped kinds cover.
- **The reserved Hollow Reach landmarks**: legend entries `3` ("a stone
  shape half-swallowed by the ash... something has been digging around its
  base, recently") and `4` ("a wide, terraced scar in the earth... dug
  with a patience nothing living seems to have. It is far from finished")
  in `data/overworld/cells/northern_steppe.lvl`. `4` in particular reads
  as an active dig site and is the natural corruption epicenter.
- **The Visitor's creations roster**: six entities in `data/entities.yaml`
  already calibrated by corruption band (Frayed Edge/Cinder
  Marches/Hollow Reach), already partially live via
  `Engine._maybe_trigger_visitor_band_encounter` +
  `visitor_band_ambush`. `excavation_warden` is *already* the documented
  "mechanical reason [the Elder Age sites] aren't accessible yet."
- **Confirmed while researching this plan**: `content/loader.py`'s
  cross-checks only validate that a *placed* `dungeon_entrance` points at
  a *known* dungeon id (and that quest/consequence dungeon ids are known)
  - nothing requires every `DungeonDef` in the catalog to have a placed
  entrance at load time. So the two new Elder Age dungeons can be fully
  authored and loaded with **zero** entrance tiles on day one, and the
  "uncover" phase just adds a fresh entry to `game_map.dungeon_entrances`
  at runtime - no "hidden entrance" trick needed. Worth a final grep
  confirmation immediately before implementation, since this reading came
  from tracing the loader, not from an explicit test.

## New data model

### `RegionCorruptionDef` (new schema, `content/schema.py`)

One YAML file per corrupted cell, sibling to a dungeon's `dungeon.yaml`
rather than a new field on the `.lvl` format itself - e.g.
`data/overworld/cells/northern_steppe.corruption.yaml`. Loaded by a new
`content/loader.py` function (`load_region_corruption`), validated the
same pydantic way as everything else, cross-checked against
`known_dungeon_ids`/the cell's own legend the same way `load_overworld`
already cross-checks entrances.

```
cell_id: northern_steppe
epicenter: [x, y]          # LOCAL cell coordinates - the terraced dig site (legend "4"),
                            # doubling as the necroship's own position (see below)
phases:
  - after_year: 87
    after_day: 80
    radius: <N1>             # tiles from epicenter; monotonic non-decreasing
  - after_year: 87
    after_day: 110
    radius: <N2>
  - after_year: 87
    after_day: 140
    radius: <N3>
    raze_dungeon_id: northern_watch_post
  - after_year: 87
    after_day: 170
    radius: <N4>              # maximum - saturates the cell; the Visitor moves on after this
    uncover:
      - {coord: [x3, y3], dungeon_id: elder_dig_site_a}   # legend "3"
      - {coord: [x4, y4], dungeon_id: elder_dig_site_b}   # legend "4" itself
```

Each phase is a strict superset of the last (radius only grows;
`raze_dungeon_id`/`uncover` fire exactly once, at the phase that first
lists them). `after_year`/`after_day` reuses the exact field-naming
convention `QuestDef.available_after_year/day` already established -
deliberate consistency, not a new vocabulary. **Day thresholds are now
decided** (previously placeholders, resolved by the user 2026-09-04): the
final phase lands at day 170 of year 87 P.S. - 120 days after
`STARTING_DAY` (50) - the point at which the Visitor has finished
whatever it came to the Northern Steppe for and moves on to a new region.
That relocation itself is out of scope for this pass (no other region is
being built yet) but the day-170 marker is the natural hook for it later.
The three earlier phases are spaced evenly across that 120-day span (day
80, 110, 140) rather than front- or back-loaded, since nothing in the
story specifically calls for uneven pacing here.

### Runtime state

- `Engine.region_corruption_defs: list[RegionCorruptionDef]` - loaded
  once, static for the run (mirrors `self.dungeon_ruin_data`).
- `QuestLog.corruption_phase: dict[str, int]` - `cell_id -> highest phase
  index already applied` (0 = none applied yet). Lives on `QuestLog`
  alongside `destroyed_dungeon_ids`/`world_flags`/`armed_encounters`,
  which are already exactly this shape of "world state that must survive
  save/load and never re-fire." **New `engine/save.py` touches required**:
  a `SavedQuestLog` field, `capture_save`, `restore_save` - the same three
  touches `[[feedback_new_player_state_needs_save_wiring]]` already flags
  as easy to silently miss. `restore_save` must *replay* every phase up to
  the saved index against the freshly rebuilt overworld `GameMap`, the
  same way it already replays `dungeon_ruin_data` for every entry in
  `destroyed_dungeon_ids` - not just restore the index number and trust
  the map matches (it won't; `build_game_map` always rebuilds from the
  static level file).

## Engine mechanics

### `Engine._check_region_corruption()`

New method, sibling to `_check_quest_deadlines`, called from the same
`process_turn` site, under the same `if self.is_overworld:` guard (the
clock only advances there). For each `RegionCorruptionDef`, find the
lowest not-yet-applied phase whose `(after_year, after_day) <=
(clock.year, clock.day)`. If found, apply it and advance
`corruption_phase[cell_id]` (only ever forward, mirrors
`_tighten_deadline`'s "only ever shortens" one-directional discipline).
Applying a phase does up to three things, in a fixed order:

1. **Tile remap** (`apply_corruption_radius`, new function in
   `engine/game_map.py`, generalizing `apply_dungeon_destruction`'s tile
   swap to many tiles at once): iterate a bounding box around the
   epicenter (padded a little past `radius` - cheap even at the largest
   radius used here), and for every `(x, y)` within (roughly - see below)
   that distance whose *current* kind is `plains`/`forest`/`road` (i.e.,
   still pristine - already-corrupted tiles from an earlier phase or
   hand-authored at ship time are a no-op, and structural tiles -
   `dungeon_entrance`, `landmark`, `stairs`, walls - are never touched),
   swap `plains -> ashen_plains` / `forest -> blighted_forest` /
   `road -> ashen_road` via the same `TILE_PASSABILITY`-driven
   walkable/transparent update `apply_dungeon_destruction` already uses.
   Idempotent and safe to replay from save. **"Roughly" that distance,
   not exactly** - see the "Resolved" note near the end of this document
   (2026-09-05): the boundary is Euclidean distance plus a deterministic,
   per-tile organic wobble, not a clean circle or (as first shipped) a
   Chebyshev square.
2. **Raze**, if this phase carries `raze_dungeon_id`: call
   `self.destroy_dungeon(raze_dungeon_id)` **unmodified** - already
   idempotent, already fails/voids the right quests via
   `QuestLog.void_by_dungeon`, already handles `not_given` correctly.
   Zero new engine code here; only new *content* (see below).
3. **Uncover**, if this phase carries `uncover` entries: new function
   `uncover_landmark(game_map, coord, dungeon_id)` in
   `engine/game_map.py` (not an Engine method - see the "Resolved since
   implementation" note below) - the mirror image of step 2. Sets
   `game_map.kinds[coord] = "dungeon_entrance"`,
   `walkable[coord] = True`, `transparent[coord]` per
   `TILE_PASSABILITY["dungeon_entrance"]`, registers
   `game_map.dungeon_entrances[coord] = dungeon_id`, and replaces
   `tile_descriptions[coord]` with a short "uncovered" variant of the
   landmark's original text (write both versions in the `.lvl` legend
   comment / dungeon bible, not hardcoded in Python).

### Fade-to-black transition signal

`_check_region_corruption` sets a transient
`Engine.pending_corruption_transition: str | None` (the cell id) for the
turn a phase actually applies **and** the player is currently standing in
that cell (compare the player's global position against the cell's
assembled bounding box - `load_overworld` already knows per-cell offsets
at load time; store them on `Engine` or `GameMap` once, rather than
recomputing). Consumed once by the presentation layer, then cleared -
same one-shot-flag shape as `record_encounter_triggered`'s "never fire
twice" bookkeeping, just read-then-clear instead of set-once.

- **Graphical client** (`main.py`/`engine/render.py`): after
  `process_turn`, check the flag; if set, run a short fade (a handful of
  frames blending `console.rgb[:, :]["bg"]` toward black and back via the
  same `console.rgb[...]["bg"] = ...` assignment `render.py` already does
  per-tile, just applied across the whole console, with `context.present`
  + a small delay between frames - no new library, no new dependency),
  then render the post-transition frame normally and clear the flag. Purely
  cosmetic; the world state change already happened atomically before the
  fade starts, so an interrupted/closed game mid-fade loses nothing.
- **CLI** (`tools/play_llm.py`): no visual fade is possible or needed;
  instead, `apply_corruption_radius`/`destroy_dungeon`/`uncover_landmark`
  should each still add a short flavor line to `self.message_log` (the
  same log every other world event already narrates through), so a CLI
  player sees *something* changed even without the animation. This is
  the only client-visible difference between the two front ends - the
  world-state application code is 100% shared.

## Content still to author

This is real content work, not just plumbing - flagged explicitly since
the "wire what's already reserved" decision doesn't mean zero authoring:

1. **Watch Post ruin variant** - `data/dungeons/northern_watch_post/`
   needs `ruined_tile`/`ruined_description`/`ruined_starting_level` added
   to its `dungeon.yaml` (currently has none - verified), plus a new
   `level_01_ruins`-shaped level file. Follow
   `[[razed_variant_decoration_pattern]]`: `scoured_ground` + `rubble`
   decoration, no copy-pasted pristine decoration. **Total loss, decided**
   (2026-09-04): no survivors at all, none of the three Watch Post NPCs
   left alive or fled. This isn't just "matches Wayford's precedent" - the
   user gave it a specific in-fiction reason worth preserving in the
   ruined_description prose itself: to the Visitor, a settlement's people
   aren't collateral damage, they're raw material for more necrocrafts
   (`docs/main_story.md`'s "Necromancy at scale" - "expendable labor...
   drawn from whoever and whatever the Visitor's arrival kills"). The
   Watch Post's ruined text should land closer to "nothing was left to
   flee, nothing was left to bury" than to an ordinary battle-ruin - a
   distinct, colder register from Wayford's own razing, not a copy of it.
   Also needs `voided_by_dungeon_id: northern_watch_post` confirmed/added
   on `word_from_the_north`/`a_warning_worth_carrying` so an
   already-`not_given` or `in_progress` copy of either quest fails cleanly
   per `[[feedback_quest_deadline_consequences_include_not_given]]`'s
   reference shape (`void_by_dungeon` already does this generically -
   just needs the quest field set, not new engine logic).
2. **Two full-size Elder Age dungeons** - `elder_dig_site_a` (legend `3`)
   and `elder_dig_site_b` (legend `4`, doubling as the corruption
   epicenter itself). **Sized up per explicit user request (2026-09-04):
   "at least the size of Silver Mountain"** - not the short shells the
   first draft of this plan assumed. `silver_mountain_caves` is the
   concrete sizing reference: **5 levels**, footprints of ~56x43
   (`level_01`/`level_02`, hand-authored) down to ~50x35 or ~48x33
   (`level_03`-`05`, cellular-automata-generated per
   `[[silversilk_caves_depths]]`'s method - noise + smoothing passes +
   largest-connected-component extraction), roughly 6-9 monster spawns
   per level, escalating difficulty across levels culminating in one solo
   climactic fight on the final level (`elder_widow`/`broodmother` there;
   `excavation_warden` is this roster's equivalent - see below). This is
   a substantial scope increase over the first draft: **two 5-level
   dungeons**, not two small shells - flagged explicitly so the
   implementation sequence (below) budgets for it as its own multi-session
   pass, not a quick addendum to the corruption mechanic itself.
   - Each site gets its own `docs/dungeon_bibles/*.md` first, per
     `[[feedback_dungeon_bible_before_geometry]]`, with real corridor
     chokepoints (`[[feedback_corridor_chokepoints_need_real_bends]]`) and
     genuine level-to-level variety, not five copies of one template
     (`[[feedback_level_geometry_variety]]`).
   - **No new monsters** (per the "wire what's already reserved" scoping
     decision) - both sites draw on the same seven already-designed
     Visitor creatures (`ash_bound_husk`, `bound_eye`, `stitched_vanguard`,
     `hollow_chanter`, `bound_crawler`, `charnel_colossus`,
     `excavation_warden`), escalating tier by depth the same way the
     region's own three corruption bands already do - early levels
     Frayed-Edge/Cinder-Marches tier, the final level or two Hollow-Reach
     tier. `excavation_warden` is the natural solo climactic guardian for
     each site's final level (already documented in
     `[[northern_steppe_bestiary]]` as "reserved specifically for the
     Elder Age sites... a long, attritional, genuinely-meant-to-deter-you
     fight" - this is exactly that placement, just arriving later than
     first implied).
   - **Differentiate the two sites through geometry and mood, not
     monsters**, since the roster is necessarily shared: legend `4` (the
     epicenter/necroship site, "a wide, terraced scar... dug with a
     patience nothing living seems to have") reads as an active,
     mundane-shaped excavation pit - benches, spoil-heaps, temporary
     Visitor infrastructure layered over something older underneath.
     Legend `3` (the standing "stone shape half-swallowed by the ash")
     should lean into `world_history.md`'s Elder Age masonry description
     - "no mortar, no right angles insisted upon... looks grown rather
     than built" - a genuinely different level-generation feel from the
     dig pit, even sharing the same monster pool.
   - Keep the Elder Age's own content exactly as vague as
     `world_history.md` insists - the dungeons are about the Visitor's
     excavation, not an explanation of what's being excavated. Bigger
     dungeons mean more opportunities for flavor text to over-explain;
     resist that specifically here.
3. **The `.corruption.yaml` file itself** - real epicenter coordinates and
   radius numbers, picked by overlaying the epicenter on the existing
   `.lvl` grid so each phase's radius plausibly reaches the next named
   landmark (the Frayed Edge tiles nearest the Heartlands seam should be
   the *last* thing touched, not the first, matching "corruption gets
   worse the further north" from the region bible's own Mood section).
4. **Bible updates**: `docs/region_bibles/northern_steppe.md`'s "Not a
   region corruption swap mechanic" paragraph needs rewriting once this
   ships (it currently says the mechanic doesn't exist), and
   `docs/main_story.md`'s open-questions list should drop the
   region-corruption bullet and gain a pointer to this document.

## Suggested implementation sequence

Small, independently testable/committable steps, in dependency order:

1. **Done (2026-09-04).** `RegionCorruptionDef`/`RegionCorruptionPhase`/
   `RegionCorruptionUncover` schema (`content/schema.py`, right after
   `DungeonDef`) + `content/loader.py`'s `load_region_corruption`
   (validates `<cell_id>.corruption.yaml` files under
   `overworld_dir/cells/`, cross-checking `cell_id` against
   `known_cell_ids` and `raze_dungeon_id`/`uncover[].dungeon_id` against
   `known_dungeon_ids`, both optional the same way `load_quests`'
   `known_dungeon_ids` is). Validates: phases non-empty and strictly
   increasing in `(after_year, after_day)`, radius non-decreasing across
   phases, `raze_dungeon_id`/each `uncover` target used at most once,
   epicenter/uncover coordinates non-negative. **Not yet done, deferred
   to this step's own follow-up**: cross-checking epicenter/uncover
   coordinates against each cell's actual width/height (needs the real
   per-cell dimensions `load_overworld` computes internally but doesn't
   currently expose - a natural fit for step 3's engine-wiring pass, not
   this one). **Not yet wired into `load_content()`** in
   `main.py`/`tools/play_llm.py` - no real `.corruption.yaml` file exists
   yet, and nothing consumes the return value until step 3. Tests:
   `tests/test_schema.py` (23 cases) + new `tests/test_region_corruption_loader.py`.
2. **Done (2026-09-04).** `apply_corruption_radius(game_map, epicenter,
   radius)` in `engine/game_map.py`, right after
   `apply_dungeon_destruction` - remaps every `plains`/`forest` tile
   within Chebyshev distance `radius` of `epicenter` to
   `ashen_plains`/`blighted_forest` (via a small `_CORRUPTIBLE_TILE_REMAP`
   dict), updating `walkable`/`transparent` in lockstep through
   `TILE_PASSABILITY`, the same pattern `apply_dungeon_destruction`
   already uses for its own single-tile swap. A Chebyshev ball is exactly
   a clipped square, so the loop only ever visits tiles it will actually
   touch or definitely skip - no separate distance check needed. Already-
   corrupted tiles and every structural kind (`road`/`wall`/
   `dungeon_entrance`/`landmark`/mountain/etc.) are left alone regardless
   of distance, which is what makes repeated calls with a growing radius
   idempotent - verified directly: calling at radius 1 then radius 2
   produces byte-identical `kinds`/`walkable`/`transparent` arrays to one
   call at radius 2 (this is the save-replay correctness property step 3
   needs). Pure function, no `RegionCorruptionDef`/`Engine` dependency -
   not yet called from anywhere. Tests: new `tests/test_game_map.py` (10
   cases, direct `GameMap` construction, no `Engine` needed).
3. **Done (2026-09-04).** `Engine._check_region_corruption` +
   `QuestLog.corruption_phase` + save wiring (`SavedQuestLogState` field,
   `capture_save`/`restore_save`, replay-on-load) - all tested against
   synthetic fixtures (`tests/test_engine.py`'s `make_corruption_def`
   helper, a real-plains-tile fixture in `tests/test_save.py`), not the
   real Northern Steppe file, which still doesn't exist. Key points where
   the actual implementation refined the design above:
   - `Engine._check_region_corruption` uses a `while`, not an `if`, per
     corruption def - catches up on more than one overdue phase in a
     single call (defensive; nothing today can skip a day, but a future
     bulk time-skip action might).
   - `corruption_phase[cell_id]` is only written when at least one phase
     actually applied that call - a cell with nothing due yet stays
     entirely absent from the dict rather than gaining an explicit `0`
     entry, matching the field's own "0 is the implicit default" docstring.
   - **Raze replay needed no new code at all**: `Engine.destroy_dungeon`
     already unconditionally adds to `quest_log.destroyed_dungeon_ids`,
     and `restore_save` already replays every id in that set generically
     (for *any* consequence source, not just corruption) - so a
     corruption-raized dungeon is already correctly re-razed on load by
     the existing loop, before the new corruption-replay code even runs.
     Corruption's own replay block in `restore_save` therefore only needs
     to redo the tile remap and any `uncover` - both via the same pure
     `apply_corruption_radius`/`uncover_landmark` functions used live.
   - **No separate `Engine._uncover_landmark` wrapper exists.** The tile-
     mutation logic lives in a plain module-level `uncover_landmark(game_map,
     coord, dungeon_id)` function in `engine/game_map.py` (the direct
     mirror-image sibling of `apply_dungeon_destruction`, at the same
     level of abstraction) - `Engine._apply_region_corruption_phase` calls
     it directly. Simpler than routing through an extra Engine method with
     nothing engine-specific to add.
   - `pending_corruption_transition` is set using **the just-applied
     phase's own radius around its epicenter** (the identical Chebyshev
     measure the tile remap itself just used) as the "is the player
     affected right now" test, rather than the cell-bounding-box idea
     floated in the original design - no per-cell offset bookkeeping
     needed at all. It's set inside `_check_region_corruption` (the live
     call path) and deliberately *not* inside
     `_apply_region_corruption_phase` (the pure, replay-safe core), so a
     save reload never spuriously queues a fade transition for a phase
     the player didn't just watch apply live.
   - `Engine.__init__` gained one new optional constructor parameter,
     `region_corruption_defs` (defaults to `None` -> `[]`), and
     `restore_save` gained the same - both additive and default-safe, so
     no existing call site in `main.py`/`tools/play_llm.py` needed
     touching for this step (they simply don't pass it yet, meaning
     "no corruption defs loaded," which is still true until step 4/5
     wires real content through `load_content()`).
   Tests: 9 new cases in `tests/test_engine.py` (a `--- _check_region_corruption
   ---` section) + 2 new cases in `tests/test_save.py` (a real-content
   round-trip, plus an old-save-missing-the-field default check). Full
   suite: 1655 passed.
4. **Done (2026-09-05).** Watch Post ruin content + a real, wired-up
   `data/overworld/cells/northern_steppe.corruption.yaml`, plus the
   `load_content()` wiring (step 3 had built the mechanism against
   fixtures only; this step is what actually threads real
   `region_corruption_defs` through `main.py`/`tools/play_llm.py`'s
   every overworld `Engine`/`resolve_transition`/`restore_save` call
   site). Concrete outcomes:
   - **Real epicenter/radii, from the real map**: epicenter `(100, 8)` -
     legend `4` in `northern_steppe.lvl`, the terraced excavation scar -
     confirmed by parsing the actual `.lvl` grid rather than guessing.
     Northern Steppe sits at overworld cell-grid offset `(0, 0)`, so its
     local coordinates equal the assembled overworld's global ones
     directly - no offset-conversion code was needed for this cell (a
     second corrupted cell at a non-zero offset would need one; flagged,
     not built, since nothing needs it yet). The Watch Post's own
     entrance `(75, 72)` is Chebyshev distance 64 from the epicenter -
     radii 30/50/65 across days 80/110/140 were chosen so the day-140
     raze phase's radius (65) just clears that distance, making the
     visible corruption front and the razing feel connected rather than
     coincidental. **Superseded 2026-09-05** - the metric changed from
     Chebyshev to Euclidean (see "Resolved from real playtesting" below),
     making the real distance ~68.7 and the shipped radius 72, not 65.
   - **Only 3 of the eventual 4 phases are authored.** The final phase
     (day 170, "maximum corruption" + uncovering the two Elder Age
     landmarks) needs `elder_dig_site_a`/`elder_dig_site_b` to exist as
     real dungeon ids first (step 5) - `load_region_corruption`'s
     `known_dungeon_ids` cross-check would otherwise reject it.
   - **Total loss, as decided**: `level_01_ruins` ships with zero entity
     spawns (new regression test:
     `test_northern_watch_post_ruins_has_no_survivors`,
     `tests/test_loader.py`). `dungeon.yaml` gained
     `ruined_tile: floor`/`ruined_description`/
     `ruined_starting_level: level_01_ruins`, following Wayford's exact
     field shape.
   - **`a_warning_worth_carrying` gained `voided_by_dungeon_id:
     northern_watch_post`** (its questgiver, `watch_post_sentry`, dies
     with the post) plus a matching `failure_message`/`failed_description`.
     `word_from_the_north` deliberately did *not* need the same change -
     traced through carefully: it's voided by Wayford, not the Watch
     Post, and its dungeon-arrival completion trigger fires on arrival
     alone, which still works against a razed-but-walkable ruins
     interior exactly as well as a populated one.
   - **A new validation helper**, `_check_region_corruption_raze_targets_have_ruin_content`
     (`main.py`), mirrors the existing
     `_check_destroyable_dungeons_have_ruin_content` check but for
     `RegionCorruptionPhase.raze_dungeon_id` instead of a quest's
     `on_fail` - catches the same "nothing to show" gap for corruption's
     own trigger.
   - **Real CLI verification**, not just unit tests: built a `testbuild`
     save adjacent to the Watch Post, hand-advanced its clock to day 140,
     and confirmed live via `tools/play_llm.py` that the surrounding
     terrain visibly corrupts (`,`/`T` → `;`/`Y` in the ASCII render),
     the entrance leads into "The Watch Post's Ruins" with
     `(no other entities on this map)`, the overworld tile's look-mode
     text shows the authored `ruined_description`, and
     `a_warning_worth_carrying`'s authored failure text appears correctly
     in the `quests` command's output.
   - Tests: 2 new cases in `tests/test_main.py` for the validation
     helper + 1 real-content end-to-end case
     (`test_real_region_corruption_razes_the_watch_post_and_voids_its_carry_quest`),
     1 new case in `tests/test_region_corruption_loader.py` (loads the
     real shipped file), 1 new case in `tests/test_loader.py` (the
     no-survivors regression guard). Also fixed a latent gap in
     `tests/test_main.py`'s own `_overworld_engine` test helper - it
     never built `dungeon_ruin_data`, so any test using it to exercise
     `destroy_dungeon` would have silently no-op'd; every real production
     construction site already did this correctly, only the test helper
     didn't. Full suite: 1661 passed.
   - Bible updates done alongside (not deferred to step 7): both
     `docs/dungeon_bibles/northern_watch_post.md` (new "After: the
     Razing" section, its stale "no ruin content" bullet removed) and
     `docs/region_bibles/northern_steppe.md` (its "Not a region
     corruption swap mechanic" bullet updated to say the mechanic now
     exists) are current as of this step.
5. The two Elder Age dungeons + wire `uncover` into the final phase.
   Given the revised Silver-Mountain-scale sizing, treated as two
   sub-passes (bible + geometry + balance per site) rather than one step -
   only wire `uncover` into the corruption phase once both are fully
   built and internally playtested on their own.
   - **`elder_dig_site_b` done (2026-09-05)**: `docs/dungeon_bibles/elder_dig_site_b.md`
     + 5 real levels (`data/dungeons/elder_dig_site_b/`) - `level_01`/
     `level_02` are room+corridor geometry (an excavation's cut trenches
     and terraces read as *built*, unlike an organic cave), `level_03`-
     `level_05` are cellular-automata caves (the dig breaking through
     into natural stone the diggers didn't make), matching
     `silver_mountain_caves.md`'s Depths methodology exactly - random
     noise, wall/floor smoothing passes, largest-connected-component
     extraction, entry/exit chosen by farthest-pair BFS distance, the
     climactic chamber deliberately widened. No new monsters: the same
     seven already-shipped Visitor creatures, escalating by level,
     `excavation_warden` placed exactly once, alone, on `level_05` (the
     stun-lock discipline its own catalog entry requires). Verified via
     `content/loader.py` (loads clean, no validation errors), `tools/preview.py`
     (all 5 levels render, connected, reachable), and a direct-`Engine`
     combat check with `COMBAT_VARIANCE_ENABLED` off (not `testbuild` -
     this dungeon deliberately has no overworld entrance yet, so
     `tools/play_llm.py testbuild` can't target it): a reference-tier
     player (broadsword/bone_plate/two Toughness perks) cleanly wins
     against the challenging tier (`Bound Eye`) and loses in an
     unmitigated stand-and-trade against the very-dangerous-and-up tiers
     (`Stitched Vanguard`/`Charnel Colossus`/`Excavation Warden`) -
     exactly the already-documented, already-accepted behavior for these
     exact stat blocks (nothing new to balance-verify, since no stats
     changed). New regression tests:
     `test_elder_dig_site_b_has_five_levels_escalating_to_a_solo_warden`
     (roster/level-chain integrity) in `tests/test_loader.py`, plus
     `elder_dig_site_b` added to `SHIPPED_DUNGEON_IDS`/`COMBAT_DUNGEON_IDS`
     there and a new `UNCOVERED_LATER_DUNGEON_IDS` set in
     `tests/test_main.py` (parallel to the existing
     `ENCOUNTER_ONLY_DUNGEON_IDS`) carving it out of the "every dungeon
     has a placed overworld entrance" check, since this one's entrance
     doesn't exist until a corruption phase adds it at runtime. Full
     suite: 1663 passed.
   - **`elder_dig_site_a` done (2026-09-05)**: `docs/dungeon_bibles/elder_dig_site_a.md`
     + 5 real levels (`data/dungeons/elder_dig_site_a/`) - per the plan's
     own differentiation call, organic cellular-automata caves at *every*
     level (not just 3-5), "grown, not built," matching `world_history.md`'s
     Elder Age masonry description, rather than `elder_dig_site_b`'s
     built-then-broken-through structure. Identical roster and escalation
     to its sibling (deliberately - the two sites are the same threat in
     two different physical shapes, not one harder than the other),
     `excavation_warden` solo on `level_05` only. Verified the same three
     ways as `elder_dig_site_b`: real loader (loads clean), `tools/preview.py`
     (all 5 levels render, connected), direct-`Engine` combat check with
     variance off (matches already-accepted precedent for the shared stat
     blocks). New test: `test_elder_dig_site_has_five_levels_escalating_to_a_solo_warden`
     parametrized over both dungeon ids (`tests/test_loader.py`), plus
     both ids added to `SHIPPED_DUNGEON_IDS`/`COMBAT_DUNGEON_IDS`/
     `UNCOVERED_LATER_DUNGEON_IDS`.
   - **The corruption file's 4th phase is done too**: day 170, `uncover`
     for both sites (`elder_dig_site_a` at `(45, 12)` - legend `3`;
     `elder_dig_site_b` at the epicenter itself, `(100, 8)` - legend `4`).
     Radius **80**, chosen empirically rather than by formula: it's the
     largest radius that still corrupts not one Heartlands tile (the
     assembled overworld's row 90+, immediately south of Northern Steppe)
     even at the noise's worst-case southward bulge - verified directly
     by running `apply_corruption_radius` at each candidate radius
     against the real two-cell-tall map and checking the corrupted
     tiles' own max `y`, not by reasoning about the noise formula in the
     abstract (radius 81 reaches Northern Steppe's own southernmost row
     with no bleed; 82 is the first radius that leaks into Heartlands).
     Both dig sites were already well within every earlier phase's
     radius by the time they're uncovered (`elder_dig_site_a` is
     Euclidean distance ~55 from the epicenter, inside phase 3's radius
     72 already) - being "in range" never matters for a landmark tile
     regardless, since `apply_corruption_radius` only ever touches
     plains/forest/road, never landmarks, so nothing opens early.
   - **Full CLI playthrough - done, and it found one real thing worth
     recording** (not a bug, a scope note): `tools/play_llm.py`'s `goto`
     stops after every single step that costs HP, and the freshly-
     corrupted ground between an ordinary starting position and either
     dig site is now hazardous almost the whole way - a real player
     crossing it will stop-and-resume many times over dozens of turns,
     which is fine in real play but made interactively `goto`-ing the
     full distance during this verification impractical. Verified the
     mechanic itself instead via a direct save-file position edit
     (teleporting adjacent to the entrance, still through the real
     `tools/play_llm.py` CLI) plus the automated end-to-end test
     `test_real_region_corruption_uncovers_both_elder_dig_sites_and_they_are_enterable`
     (`tests/test_main.py`), which drives the real `main.py` functions
     (`load_region_corruption`, `Engine._check_region_corruption`,
     `resolve_transition`) against the real overworld map - confirmed
     live: `"You enter The Terraces."` on stepping onto the newly-opened
     `elder_dig_site_b` entrance, monsters and items present exactly as
     authored. One cosmetic loose end noticed and deliberately left
     alone: `uncover_landmark` doesn't update `tile_descriptions`, so a
     look-mode inspection of an uncovered site still shows its original
     landmark flavor text rather than an "uncovered" variant - harmless
     here (the existing text - "a wide, terraced scar... far from
     finished" - still reads fine post-uncover) but worth a real fix if
     a future site's landmark text wouldn't age as gracefully.
   - Full suite: 1672 passed. **This closes the corruption+uncover arc
     for the Northern Steppe end to end** - progressing corruption,
     settlement razing, and both Elder Age dungeons opening, all wired
     and verified.
6. **Done (2026-09-05).** Fade-to-black in the graphical client - built
   as a fade-*in* from black, not a fade-out-then-in: the world state
   has already changed synchronously by the time `Engine.process_turn`
   returns (Engine has no concept of animation frames), so there's no
   "before" frame left to show - `main.py`'s new `animate_corruption_fade`
   renders the already-changed map once, snapshots that as the fade's
   target, then re-presents it at increasing brightness
   (`CORRUPTION_FADE_STEPS = 8` steps, `CORRUPTION_FADE_FRAME_SECONDS =
   0.05`s each, ~0.4s total) by rescaling `console.rgb["fg"]`/`["bg"]`
   from that saved snapshot each frame (never from the console's own
   already-dimmed state, which would compound rounding error and drift).
   Wired into both of `main.py`'s `dispatch_action` call sites, checked
   right after `play_queued_sounds` and before `resolve_transition`
   (so it plays on the *pre-transition* engine - the one
   `Engine._check_region_corruption` actually ran on this turn - even in
   the rare case the same turn also hands the player to a different
   `Engine`). `Engine._check_region_corruption` also gained a short
   flavor message logged alongside the flag unconditionally, so a CLI
   player (who has no fade to watch) still gets *some* signal that the
   ground around them just changed - the only client-visible difference
   between the two front ends, exactly as the original design called for.
   **Verified with real rendered frames**, per
   `[[feedback_settlement_layout_needs_road_network_and_screenshots]]`'s
   "don't trust ASCII, capture a real frame" discipline: a headless
   `tcod.context.new` harness built a real overworld `Engine`, called
   `animate_corruption_fade` directly, and captured screenshots plus a
   per-frame brightness measurement - frame 0 is pixel-black (245-byte
   PNG), brightness increases smoothly and roughly linearly across all 9
   frames, and the final frame is bit-for-bit identical to a plain,
   un-faded `render_all` call at the same region. New tests: the two
   existing `pending_corruption_transition` tests in `tests/test_engine.py`
   now also assert the flavor message is (or isn't) logged alongside the
   flag. Full suite: 1672 passed (unchanged - both new assertions
   extended existing tests rather than adding new ones).
7. Bible/doc reconciliation - **done incrementally as each step
   shipped** rather than deferred to the end: `docs/dungeon_bibles/northern_watch_post.md`
   and `docs/region_bibles/northern_steppe.md` were updated in step 4;
   `docs/main_story.md`'s "Genuinely new" bullet and "Open questions"
   list were updated once this arc closed (2026-09-05) to reflect the
   region-corruption design question as resolved and built, not open.

## Resolved since the first draft (2026-09-04)

- **Day thresholds**: fixed at 80 / 110 / 140 / 170 (year 87 P.S.), day
  170 being 120 days after `STARTING_DAY` and the point the Visitor
  finishes with this region. Still worth a real balance pass once
  `word_from_the_north` is playtested against this timeline (does the
  player realistically reach the Steppe and recon the Watch Post before
  day 140 razes it?) - the numbers are decided, not yet balance-tested.
- **Watch Post razing is total loss**, with an in-fiction reason (see
  above) rather than an arbitrary "no survivors" flag.
- **Encounter-rate scaling is explicitly out of scope for this pass.**
  The user's own instinct, recorded here for whenever it *is* picked up:
  `visitor_band_ambush` odds should eventually scale with **distance to
  the necroship and to the excavation sites**, not with which corruption
  band/stage a tile is in (today it's a flat 10% on any corrupted tile
  regardless of band - unchanged by this plan). This pairs naturally with
  a detail already in this doc: the corruption epicenter *is* the
  necroship's own position (hovering over the dig site it's currently
  supervising) - so "distance to the necroship" and "distance to the
  epicenter" are the same measurement, already computed every phase check
  for the radius test. A future pass could reuse that distance directly
  for encounter odds instead of adding a second distance metric. Not
  built now - flagged for later, per explicit instruction not to bother
  with it this pass.
- **The two Elder Age dungeons are now full-size** (5 levels each,
  Silver-Mountain-scale footprints, per the "Content still to author"
  item 2 rewrite above), not the short shells the first draft assumed -
  the single biggest scope change since the first draft.

## Resolved from real playtesting (2026-09-05)

The user actually explored the mechanic in-game after step 4 shipped and
found two real problems, both fixed the same session. **Every earlier
mention in this document of "Chebyshev distance" or a square/clipped-box
boundary describes the pre-fix behavior** - kept as-written rather than
silently edited, the same "a past pass's own reasoning stays as written"
convention this project already follows elsewhere, but superseded by
what's below wherever the two disagree.

- **The corruption boundary was a perfect rectangle and read as
  industrially paved, not organic.** `apply_corruption_radius`
  (`engine/game_map.py`) originally used Chebyshev distance - a clipped
  square by construction, with perfectly straight edges and sharp
  corners. Fixed by switching to Euclidean distance *and* layering a
  deterministic, per-tile organic "wobble" on top
  (`_corruption_edge_noise`/`_corruption_noise_amplitude`): coarse-grained
  smooth value noise (an 8-tile noise cell, bilinearly interpolated),
  seeded from the epicenter, that shifts each tile's effective inclusion
  threshold by up to 6 tiles either way once the radius is large enough
  for that to matter (a linear ramp from 0 wobble at radius <= 5 up to
  the full 6-tile cap by radius ~17, so small radii - the kind unit tests
  use for exact-coverage assertions - stay a clean, predictable circle).
  **The load-bearing constraint this had to preserve**: the noise is a
  pure function of `(tile, epicenter)` alone, never of `radius` or call
  history, which is what keeps `apply_corruption_radius`'s
  idempotency/replay-safety guarantee intact (a growing-radius replay on
  save load must still land on exactly the same tiles as one direct call
  at the final radius - re-verified with a dedicated test after the
  change). Real content's radii needed re-tuning as a consequence: the
  Watch Post's razing phase (`data/overworld/cells/northern_steppe.corruption.yaml`)
  moved from radius 65 (just enough under the old Chebyshev metric) to
  72 (enough to clear the new Euclidean distance of ~68.7, verified
  against the real noise value at that exact tile, plus a few tiles of
  margin - a radius chosen to exactly graze a target coordinate is
  fragile by construction and shouldn't be repeated).
- **Roads had no corrupted variant, so a road running through corrupted
  ground stayed a "safe lane"** - no chip damage, no `visitor_band_ambush`
  risk, an unintended (if mechanically interesting) side effect the user
  explicitly didn't want. Fixed with a new `TileType`, `ashen_road`
  (`content/schema.py`) - `road`'s own glyph, recolored to match
  `ashen_plains`/`scoured_ground`'s palette and reusing their sprite
  (`data/sprites.yaml`), added to `_CORRUPTIBLE_TILE_REMAP`
  (`engine/game_map.py`), `Engine.ENVIRONMENTAL_HAZARD_MESSAGES`, and
  `Engine.VISITOR_BAND_TILE_KINDS` (`engine/engine.py`) - the same three
  places `ashen_plains`/`blighted_forest` are already registered, so a
  corrupted road now carries identical chip damage and ambush risk to
  the ground around it.
- Tests: `tests/test_game_map.py` rewritten for the new circular-not-
  square shape (a radius-1 circle covers the center plus its 4 orthogonal
  neighbors, not the old full 3x3 square) plus new tests proving genuine
  irregularity (a tile well outside the nominal radius gets included in
  one direction while a tile exactly *at* the nominal radius is excluded
  in another) and pinning the idempotency guarantee still holds. New
  `ashen_road` tests added alongside the existing `ashen_plains`/
  `blighted_forest` ones in `tests/test_engine.py` (hazard damage, ambush
  arming) and `tests/test_game_map.py` (the remap itself). Two existing
  `tests/test_engine.py` tests that asserted the old square coverage were
  updated to the new circular one. Full suite: 1669 passed.
