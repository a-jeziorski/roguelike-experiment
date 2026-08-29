# Visitor Band Ambush — Dungeon Bible

*A short site key for `data/dungeons/visitor_band_ambush/`, per the
mandatory per-dungeon-bible convention (`docs/content_design_process.md`
§0d) - no exception for a small map. Read
`docs/content_design_process.md` §0ad (the encounter mechanism itself)
and `docs/region_bibles/northern_steppe.md` (the roster this dungeon
draws on) before touching this level.*

## The pitch

Not a real place - a scripted overworld encounter
(`Engine._maybe_trigger_visitor_band_encounter`, `main.py`'s
`_redirect_into_visitor_band`), reached only by lingering on the
Northern Steppe's corrupted ground (`ashen_plains`/`blighted_forest`),
never by walking to it. Modeled directly on `goblin_ambush.md`'s shape -
same "pulled off the overworld, fleeable at any time, not a lock"
contract - but with one deliberate difference: **this level carries no
fixed roster of its own.** Every other encounter dungeon (goblin_ambush
included) is a complete, hand-placed fight; this one is reused across
every trigger, with `roll_visitor_band` (`engine/engine.py`) picking a
fresh, randomly-sized band from the Northern Steppe bestiary each time
it fires, tiered by wherever on the Northern Steppe the player actually
was standing. The level itself is just the stage.

**Why an open field, not a chokepoint**: `goblin_ambush`'s narrows exist
because that fight is always exactly 3 goblins with known stats -
geometry can be built around one specific encounter's math. This
dungeon's fight might be 2 `bound_eye` or 2 `charnel_colossus` depending
on the roll, so no single chokepoint placement could be correct for
every possible band. An open field keeps the geometry neutral and lets
the player's own approach (fight in the open, retreat toward an edge,
use `open_boundary` to disengage entirely) carry the tactical weight
instead - the same reasoning `docs/content_design_process.md` §2 gives
for checking gear fairness across branching paths: don't bake in an
assumption a variable encounter can't guarantee.

## Terrain

A single open clearing, every tile walkable - no border at all, so
`open_boundary`'s "at least one walkable perimeter tile" requirement
(`content/schema.py`'s validator catches a fully-sealed ring at
content-load time) is trivially satisfied from any edge. An earlier
version of this level used a `mountain` ring with gaps carved in for
egress; simplified to a fully open field since geometry can't be built
around any one specific encounter here anyway (see "why an open field"
above) - a border was adding shape without adding a design decision it
was actually enforcing.

The ground itself is `scoured_ground`
(`content/schema.py`'s `TileType`, `engine/render.py`'s `TILE_VISUALS`) -
visually identical to `ashen_plains` (same glyph, same colors, same
sprite) so the arena still *reads* as Northern Steppe corruption, but
deliberately excluded from `Engine.ENVIRONMENTAL_HAZARD_MESSAGES`, so it
deals no chip damage. This was originally plain `plains` for exactly the
opposite-looking reason (avoid stacking hazard damage on top of a live
monster band), then briefly `ashen_plains` itself (which brought the
damage back), before landing here: the corrupted *look* was worth
keeping for atmosphere, the corrupted *hazard* wasn't - the encounter is
already the danger, the ground doesn't need to be too (see
`docs/content_design_process.md` §0p's own "narrow enough to cross in
one push" discipline, applied here as "don't punish standing still to
fight").

## Roster

None authored in the level file - see the pitch above.
`_redirect_into_visitor_band` places the rolled band on walkable,
unoccupied tiles near `player_start` (`engine/game_map.py`'s
`nearby_walkable_tiles`) after building this level's otherwise-empty
map. `excavation_warden` never appears here (see
`docs/region_bibles/northern_steppe.md`'s Roster table) - it's reserved
for a future, deliberate Elder Age dig-site placement, not this ambient
encounter.

## Explicitly out of scope

- No loot, no reward item - same as `goblin_ambush`.
- No second level, no `stairs_down` - `requires_stairs_down: false`.
- No overworld `dungeon_entrance` tile anywhere targets this dungeon.
- **Known limitation, accepted rather than solved this pass**: a band's
  monsters are injected directly onto the built `GameMap`, not through
  `LevelDef.entity_spawns` - `engine/save.py`'s
  `capture_save`/`restore_save` only round-trip monster state via
  `GameMap.entity_spawn_index`, which these entities never populate.
  Saving mid-encounter and reloading loses the band entirely (the arena
  comes back empty) - same "conservative first pass, document the gap"
  precedent as monster status effects never persisting across a
  save/load. Not enforced or blocked at runtime; just don't expect a
  saved-and-reloaded fight to resume with its monsters intact.
