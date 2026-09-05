# The Excavation — Dungeon Bible (`elder_dig_site_b`)

*A design document for one location, written the way a GM would key a
site for a tabletop session: what's actually here, why, and what the
player is meant to feel room to room. See `docs/world_history.md` and
`docs/main_story.md` for the realm-level facts this location has to
agree with, `docs/region_bibles/northern_steppe.md` for the region this
sits in (the Hollow Reach, its epicenter), and `docs/visitor_corruption.md`
for the mechanic that unlocks it - `docs/content_design_process.md` §0d
requires this document before any ASCII is drawn.*

## The pitch

This is legend `4` in `data/overworld/cells/northern_steppe.lvl` - "a
wide, terraced scar in the earth... dug with a patience nothing living
seems to have. It is far from finished" - and the Visitor's own
corruption epicenter (`data/overworld/cells/northern_steppe.corruption.yaml`).
Narratively, the necroship itself hovers over this exact ground: this is
where the Visitor has actually been, for months, while the rest of the
region withered around the edges of what it was doing here. Reaching
this place at all means the excavation has progressed past the point of
being merely watched from a distance - `excavation_warden`'s own
description ("posted at the dig and forgotten there on purpose") is the
mechanical answer to "why wasn't this accessible sooner," not narration
that needs its own separate explanation.

**Placement on the world bible**: Elder Age site, presently occupied by
the Visitor's excavation - the same "the Visitor is excavating sites
already in the game" relationship `main_story.md` establishes for
Forgotten Ruins and the Elder Cairn, just a *new* site rather than a
previously-shipped one getting a second visitor. The Elder Age itself
stays exactly as vague as everywhere else in this project: what's being
dug for, and what's actually down there, is never explained past "older
than anything with a name." The player can deny the Visitor this place;
they never get to learn what it is.

**No new monsters.** Every entity below is already shipped
(`data/entities.yaml`'s "Visitor's creations" block, calibrated in
`docs/content_design_process.md` §0ac) - per the explicit scoping
decision in `docs/visitor_corruption.md`, this dungeon wires up what's
already reserved rather than inventing new threats. `excavation_warden`
in particular is *already* documented there as "reserved specifically for
the Elder Age excavation sites" - this dungeon (and its sibling,
`elder_dig_site_a`) is that reservation finally being spent.

## Mood

Two registers, layered depth by depth. The first two levels read as an
active, mundane *industrial* site wearing corruption like grime - spoil
heaps, cut trenches, crude scaffolding, the practical, unglamorous
texture of actual excavation work, just being done by things that don't
tire and don't need light. Nothing here should read as ceremonial or
grand; the Visitor studies the Sundering with the same "ordinary
institutional appetite" register the Old Kingdom itself once had digging
for Elder Age power (`world_history.md`), and its dig site should look
exactly that unglamorous. Past `level_02`, the excavation breaks through
into something the diggers didn't build and don't understand any better
than the player does - the register shifts from "industrial site" to
Silversilk's own "dread-of-scale," but for a different reason: not
ancient-and-undisturbed, but *disturbed on purpose, recently, by
something that shouldn't have been able to*. `excavation_warden`'s own
patience ("in no hurry to let anyone closer") is the last word on what
that difference feels like to meet.

## Structure overview

Five levels, matching Silver Mountain Caves' Depths precedent for scale
(`docs/dungeon_bibles/silver_mountain_caves.md`) - hand-authored upper
levels giving way to cellular-automata-carved depths once the dig breaks
through into natural stone.

| Level | Name | Generation | Danger | Climax |
|---|---|---|---|---|
| `level_01` | The Terraces | Hand-authored, ~56x43 | Challenging | Perimeter patrol |
| `level_02` | The Cutting | Hand-authored, ~56x43 | Very dangerous | Denser mid-tier patrol |
| `level_03` | The Threshold | Cellular automata, ~50x35 | Very dangerous | First `charnel_colossus` |
| `level_04` | The Ossuary Hollow | Cellular automata, ~48x34 | Extremely dangerous | Massed `charnel_colossus` |
| `level_05` | What the Dig Found | Cellular automata, ~48x33 | Extremely dangerous, solo | `excavation_warden` |

## The named set pieces

### 1. The Terraces (`level_01`)

The excavation's outermost ring - stepped spoil-heap terraces (the
"terraced scar" the overworld landmark's own description names), cut
by the crude, practical geometry of a project built for function, not
form: straight cut-lines, no ornament. `ash_bound_husk` (pack_hunter,
hp30/atk13/def2) patrols in small packs along the terrace edges;
`bound_eye` (ranged_basic, hp22/atk12/def1) is posted at range on the
higher terraces, watching the cut lines below the way a real sentry
would. This is deliberately the gentlest level in the dungeon - a
player who's already crossed the Hollow Reach to get here has proven
they can survive its ambient corruption; the dungeon itself should open
by confirming that, not immediately punishing it.

### 2. The Cutting (`level_02`)

Narrower, deeper trenches - the terraces give way to a single
excavated cut, walls higher than a person, that the whole site funnels
into. `stitched_vanguard` (regenerator, hp40/atk18/def4) and
`hollow_chanter` (ranged_basic + weaken, hp28/atk16/def2) hold the cut
in pairs, backed by `bound_crawler` (poison, hp30/atk16/def3) patrolling
the trench floor - the first level where more than one Visitor-creation
archetype threatens the player in the same encounter, matching
`silver_mountain_caves.md`'s own "the floor drops" escalation shape one
level early, since this dungeon only has five levels to Silversilk's
five and needs to reach `excavation_warden`'s tier by the end.

### 3. The Threshold (`level_03`)

Where the cut finally breaks through - hewn stone gives way, without
transition, to something that was never cut at all. First appearance of
`charnel_colossus` (enrage, hp48/atk24/def6), placed alone at first as a
real escalation beat, backed by thinning `ash_bound_husk`/`bound_eye`
patrols still working this shallow. The level's own geometry should mark
the transition physically: hand-authored trench walls for the first
stretch, opening into the cellular-automata cave proper without a
loading-screen-style hard cut.

### 4. The Ossuary Hollow (`level_04`)

Named for what the excavation has actually been unearthing down here,
described only ever obliquely (bone, but never confirmed whose, never
explained why there's so much of it) - the Elder Age discipline applies
here as much as anywhere. Two to three `charnel_colossus` patrol this
level, the closest thing to a "common enemy" tier this dungeon has,
plus a `hollow_chanter` or two providing ranged support from the
hollow's edges. Two `healing_potion`s along the route, matching
Silversilk's own "real, earned rest before the climax" precedent.

### 5. What the Dig Found (`level_05`)

The dungeon's true apex and the reason this site isn't accessible yet
without a purpose: `excavation_warden` (sleeping_guard, hp55/atk16/def8,
stun on every landed hit), alone, in the largest chamber in the
dungeon, guarding whatever the terraces above have spent months
reaching. Per the roster's own stun-lock caution
(`docs/content_design_process.md` §0t) and the wraith-precedent
discipline it invokes: solo, nothing else drawing the player's attention
in the same encounter, no ambient population sharing this room. What's
actually down here is never shown or described past what the Elder
Age's own established vagueness already permits - the fight, not an
explanation, is the reward for reaching it.

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

No new monsters, no new items, no new decoration kinds - every entity
above is already in `data/entities.yaml`, calibrated and shipped.
`healing_potion` is the only item placed (two per level from `level_02`
onward, matching this project's usual mid-to-late-dungeon rest-point
density); no unique reward item - what's earned here is access to
`level_05`'s fight and (mechanically) this dungeon's own existence as a
destination, not loot.

## Terrain

`level_01`/`level_02` are hand-authored: straight cut-lines, terraced
elevation implied by wall placement (no true z-axis - a stepped-terrace
*read*, not a mechanic), scaffolding conveyed through existing
decoration kinds (`crate`/`barrel`/`rubble`) rather than any new one.
`level_03`-`level_05` are cellular-automata-carved caves, the same
technique `silver_mountain_caves.md`'s Depths section names in detail:
random noise, several wall/floor smoothing passes, largest-connected-
component extraction for guaranteed reachability, entry/exit chosen to
maximize both graph distance and straight-line spread. `level_05`'s
climactic chamber is a deliberately widened room, matching Silversilk's
"the boss's den reads as a destination" precedent - no hand-carved
chokepoint before it, since a solo encounter doesn't need the anti-swarm
protection a chokepoint exists for.

## Explicitly out of scope

- No unique reward item, no `balance_reference_xp` beyond what the
  existing roster's own hits-to-kill math already established at
  shipping time (`docs/content_design_process.md` §0ac/§0u) - nothing
  here needed re-verifying since no stats changed.
- No Elder Age exposition beyond what's already established project-wide.
  This dungeon's whole job is showing the *consequence* of the Visitor's
  excavation, not explaining what it found.
- No `requires_key`/locked doors - straightforward linear-with-branches
  progression, matching this project's combat-dungeon default.
