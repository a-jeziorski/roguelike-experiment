# The Leaning Stone — Dungeon Bible (`elder_dig_site_a`)

*A design document for one location, written the way a GM would key a
site for a tabletop session: what's actually here, why, and what the
player is meant to feel room to room. See `docs/world_history.md` and
`docs/main_story.md` for the realm-level facts this location has to
agree with, `docs/region_bibles/northern_steppe.md` for the region this
sits in (the Hollow Reach), `docs/dungeon_bibles/elder_dig_site_b.md`
for its sibling site (deliberately built differently - see "How this
differs from the Excavation" below), and `docs/visitor_corruption.md`
for the mechanic that unlocks it - `docs/content_design_process.md` §0d
requires this document before any ASCII is drawn.*

## The pitch

This is legend `3` in `data/overworld/cells/northern_steppe.lvl` - "a
stone shape half-swallowed by the ash, its lines too deliberate to be
natural. Something has been digging around its base, recently." Unlike
`elder_dig_site_b` (the Visitor's own active excavation, and the
corruption's epicenter), this site is something the Visitor *found*
already standing - a second target, dug around rather than dug *for*,
uncovered by the same final corruption phase once the region's front
has spread far enough west and south to reach it.

**Placement on the world bible**: Elder Age site, presently disturbed by
the Visitor's digging - same relationship to `main_story.md` as its
sibling. The Elder Age itself stays exactly as vague as everywhere else:
what the "stone shape" actually is, and why the Visitor cares about it
specifically, is never explained past "older than anything with a name."

**No new monsters**, per the same scoping decision as `elder_dig_site_b`:
the same seven already-shipped Visitor creatures, `excavation_warden`
reserved for this site's own final level too - two separate guardians at
two separate sites, not one guardian shared between them.

## How this differs from the Excavation

`elder_dig_site_b` reads as an active industrial dig site: cut trenches
and terraces for its first two levels, only breaking into unbuilt stone
once the excavation goes deep enough. This site is the opposite premise
from its very first level: **nothing here was ever built, so nothing
here should ever read as cut, planned, or right-angled.** Every level -
not just the deep ones - is a cellular-automata-carved cave, matching
`world_history.md`'s own description of Elder Age construction ("no
mortar, no right angles insisted upon, a masonry style that looks grown
rather than built"). Where site B's mood arc moves from "industrial" to
"disturbed-on-purpose," this site is disturbed-on-purpose from the
moment the player steps through the entrance - the Visitor's crude
digging (implied by ambient rubble/bones, not shown as trenches) cuts
across ground that was never meant to be cut at all.

The two sites deliberately share every stat block and escalate on the
same schedule (see Roster below) - the point of building two is that
they're the *same threat*, arrived at two different physical shapes, not
that one is harder than the other.

## Mood

Quieter and older-feeling than the Excavation, closer to Silver Mountain
Caves' "dread-of-scale" register than to an industrial site's grime -
except where Silversilk's depths are dangerous because they're
*undisturbed*, this site is dangerous because something disturbed it
that had no business being able to. The stone shape itself (referenced
only obliquely past the overworld landmark's own text - never named,
never explained) should feel like the one fixed, ancient thing in a
space the Visitor's creatures have overrun since. Corruption grows
denser and the passages grow tighter and more disorienting the deeper
the player goes, without the industrial site's sense that intent
organized any of it - it wasn't planned this way, it grew this way.

## Structure overview

Five levels, all cellular-automata caves - the technique
`silver_mountain_caves.md`'s Depths section and `elder_dig_site_b.md`'s
own `level_03`-`05` already use (random noise, several wall/floor
smoothing passes, largest-connected-component extraction, entry/exit
chosen by farthest-pair graph distance, climactic chamber deliberately
widened).

| Level | Name | Danger | Climax |
|---|---|---|---|
| `level_01` | The Ash-Choked Threshold | Challenging | Perimeter patrol |
| `level_02` | The Leaning Passages | Very dangerous | Denser mid-tier patrol |
| `level_03` | The Deep Cut | Very dangerous | First `charnel_colossus` |
| `level_04` | The Buried Hollow | Extremely dangerous | Massed `charnel_colossus` |
| `level_05` | The Stone's Own Floor | Extremely dangerous, solo | `excavation_warden` |

## The named set pieces

### 1. The Ash-Choked Threshold (`level_01`)

The cave mouth the Visitor's diggers actually widened to get in -
ash and disturbed rubble mark where crude digging met stone that
resisted it. `ash_bound_husk` (pack_hunter) patrols in small packs
through the winding entry passages; `bound_eye` (ranged_basic) watches
from side-passages. Gentlest level in the dungeon, same reasoning as
`elder_dig_site_b.md`'s own `level_01` - confirming the player can
survive here before anything harder is asked of them.

### 2. The Leaning Passages (`level_02`)

Named for the stone shape's own influence starting to show - passages
that bend at angles nothing dug on purpose would choose, deep enough
that natural light stops reaching. `stitched_vanguard` (regenerator)
and `hollow_chanter` (ranged + weaken) hold key junctions in pairs,
`bound_crawler` (poison) patrols between them - the same "more than one
archetype in the same encounter" escalation `elder_dig_site_b.md`'s own
`level_02` uses.

### 3. The Deep Cut (`level_03`)

Where the Visitor's own digging finally gives out and the cave continues
on terms nothing living set. First appearance of `charnel_colossus`
(enrage), placed alone as an escalation beat, with thinning
`ash_bound_husk`/`bound_eye` patrols still working this shallow -
mirroring `elder_dig_site_b.md`'s own `level_03` beat for beat, since
both sites are meant to escalate identically.

### 4. The Buried Hollow (`level_04`)

Two to three `charnel_colossus` patrol a wide, disorienting stretch of
passages, backed by `hollow_chanter` support from side-galleries. Two
`healing_potion`s along the route - the same "real rest before the
climax" precedent every prior dungeon in this project uses.

### 5. The Stone's Own Floor (`level_05`)

The dungeon's apex and the reason this site isn't accessible without a
reason to be here: `excavation_warden` (sleeping_guard, stun on every
landed hit), alone, in the largest chamber in the dungeon - the stone
shape's own base, finally reached. Same stun-lock placement discipline
as its sibling's `level_05`: solo, nothing else drawing the player's
attention in the same encounter. What the stone actually is stays
unexplained, same as everywhere else the Elder Age appears in this
project.

## Roster

| Entity | Tier | Role | Levels placed |
|---|---|---|---|
| `ash_bound_husk` | Challenging | Pack melee | 1, 3 (thinning) |
| `bound_eye` | Challenging | Ranged support | 1, 3 (thinning) |
| `stitched_vanguard` | Very dangerous | Regenerating melee | 2 |
| `hollow_chanter` | Very dangerous | Ranged weaken | 2, 4 |
| `bound_crawler` | Very dangerous | Poison melee | 2 |
| `charnel_colossus` | Extremely dangerous | Common patrol | 3, 4 |
| `excavation_warden` | Extremely dangerous, solo | Climactic guardian | 5 |

Identical to `elder_dig_site_b.md`'s own roster table, deliberately -
see "How this differs" above. `healing_potion` is the only item placed
(two per level from `level_02` onward); no unique reward item.

## Terrain

All five levels are cellular-automata-carved caves - see "How this
differs from the Excavation" above for why this is the one structural
difference from its sibling site. No hand-authored right-angled geometry
anywhere in this dungeon, matching the Elder Age masonry description
this site exists to embody. `level_05`'s climactic chamber is a
deliberately widened room, same as every other solo-boss den in this
project.

## Explicitly out of scope

- No unique reward item, no new `balance_reference_xp` beyond the
  already-established roster calibration - nothing here needed
  re-verifying since no stats changed.
- No Elder Age exposition beyond what's already established
  project-wide. This dungeon shows the Visitor disturbing something old,
  not an explanation of what it is.
- No `requires_key`/locked doors - straightforward linear-with-branches
  progression, matching this project's combat-dungeon default.
