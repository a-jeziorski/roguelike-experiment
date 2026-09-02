# The Weeping Cistern — Dungeon Bible

*A design document for one dungeon, written the way a GM would key a
site for a tabletop session: what's actually here, why, and what the
player is meant to feel room to room. See `docs/world_history.md` and
`docs/region_bibles/northern_steppe.md` for the realm/region-level facts
this dungeon has to agree with, and `docs/content_design_process.md` for
the mechanical authoring rules. Written first this pass, before any level
geometry, per standing convention.*

## The pitch

An Old Kingdom cistern, cut into the steppe to catch mountain runoff and
supply a garrison whose name nobody kept. Nothing magical, nothing
strategic - just infrastructure, the same "mundane job" register Drowned
Waystation's own pitch uses. The garrison is long gone; the cistern's
drainage failed before that, and its lower vaults have stood full ever
since. This dungeon exists to give the new water-walking mechanic a real
stage: a short, dry intro, then a stretch of standing water the player
cannot get past without the item found earlier in the same dungeon.

**Placement on the world bible**: Old Kingdom in origin, "fallen
infrastructure, present-day squatters" - the same category
`docs/world_history.md` already uses for Drowned Waystation and Sunken
Mine, just relocated to the Northern Steppe. Predates the Visitor's
corruption entirely and has nothing to do with it; the water here is
mountain runoff gone stagnant, not anything the Visitor touched.

**Placement on the region bible**: sits in the Frayed Edge band (local
y 60-89, "light corruption," nearest the Heartlands seam) at global
(95, 83) - open plains, well clear of Northern Watch Post (75, 72) and
the three still-reserved future-dungeon landmarks (the Goblin Camp, the
two Elder Age excavation sites) further north in the Cinder Marches and
Hollow Reach. `docs/region_bibles/northern_steppe.md`'s own tone note
explicitly allows this: the corruption bands' boundaries are "guidance,
not a hard fence." This is the region's first combat dungeon - Northern
Watch Post is deliberately peaceful and has none.

## Mood

Patient and administrative, not haunted - closer to Drowned Waystation's
"abandoned mid-routine" register than to anything Elder Age or
Visitor-corrupted. Nobody built this to be found; it was built to be
useful, stopped being maintained, and has simply sat here since. The
water is the whole obstacle: not a hazard that hurts the player (no
`ashen_plains`/`dunes`-style chip damage), just terrain that flatly
refuses to be crossed without the one item that lets it be.

## Structure overview

Two levels - a dry intro giving way to the dungeon's one real set piece:

| Level | Name | Set pieces it holds |
|---|---|---|
| `level_01` | The Cistern Head | The Antechamber, The Niche |
| `level_02` | The Flooded Vault | The Water Gate, The Far Vault |

## The named set pieces

### 1. The Antechamber (`level_01`)

The cistern's dry upper works - what would once have been walked through
daily by whoever maintained the drainage. One `drowned_wretch` still moves
through it, and a `gray_ooze` has settled further in, same "formless,
patient" role it plays at Drowned Waystation. Two `healing_potion`s are
placed here (one before each fight, not both up front) - the `gray_ooze`
fight runs longer than its raw hp suggests, since its weaken proc keeps
knocking the player's own attack down for as long as it keeps landing, so
the second potion exists specifically to cover that extension rather than
being a spare. A third `healing_potion` sits in `level_02`'s own dry
entrance room, before its `drowned_wretch` guard - a real CLI playthrough
of the two-potion version reached that fight down to single digits of HP
with nothing left to drink, which is too tight for a dungeon this early;
one potion per fight is the actual working ratio, not a cushion. No water
anywhere on this level - the mechanic isn't needed yet, only telegraphed.

*Why it's first*: establishes the dungeon as ordinary Old-Kingdom-remnant
territory before the player has any reason to think about water at all.

### 2. The Niche (`level_01`)

A small alcove off the main hall, reached through a single corridor gap,
holding the dungeon's first `water_walking_potion`. Its own flavor text
("still smells faintly of standing water, though none is in sight yet")
foreshadows level_02 without explaining it - the player finds the tool
before they know what it's for, the same "key before the lock" shape a
`rusty_key`/locked-door pair already uses elsewhere, just without an
actual lock.

## 3. The Water Gate (`level_02`)

A dry entrance room gives way, with no floor bridge at all, to nine tiles
of `deep_water` - the dungeon's whole reason to exist. No monster guards
this room: an earlier draft placed one here (first a second `gray_ooze`,
then a `drowned_wretch`), but a real CLI playthrough of both versions
showed that three back-to-back melee fights in a strictly linear, no-rest
dungeon left a fresh, unequipped character dead or down to single-digit
HP by the water's edge even using every potion in the dungeon - too tight
for what's meant to be an accessible mechanic showcase, not a gauntlet.
Cutting straight to the water instead matches this set piece's own stated
point: the crossing is the obstacle, not one more attrition fight bolted
onto it. A `healing_potion` in the dry entrance room and a **second**
`water_walking_potion` right at the water's edge are both still here - a
safety net in case either was already spent back in `level_01`. The
crossing is deliberately **forward-only**: there is no floor route back across this same water,
so a buff that runs out mid-crossing can delay the player but can never
strand them - once across, the far side has its own way out (set piece 4)
that never requires re-crossing.

*Why forward-only*: a there-and-back crossing over the same water would
let an expired buff strand the player on a `deep_water` tile with no
walkable neighbor. Making the gate one-way structurally removes that
failure mode instead of relying on generous duration alone.

### 4. The Far Vault (`level_02`)

Past the water: `chain_mail` (already flavored "Old Kingdom-issue" in its
own item description - a natural fit for exactly this dungeon) and a
`gold_stash`. The dungeon's true exit is here too - a `stairs_down` with
`next_level: null`, Drowned Waystation `level_02`'s own exact convention
for a dungeon's deepest level - so the player never needs to re-cross the
water to leave.

## Roster and balance

| Monster | Where | Why here specifically |
|---|---|---|
| `drowned_wretch` (hp 11/atk 4/def 0, hostile_basic) | `level_01` x1 only | Old Kingdom remnant, same "someone was posted here" register as Drowned Waystation's own roster - this cistern had staff once, too. |
| `gray_ooze` (hp 16/atk 4/def 1, hostile_basic) | `level_01` x1 only | Formless and motiveless, same role it plays at Drowned Waystation - the one thing here that isn't a leftover person, just something that found standing water it liked. |

Against player baseline (30 hp / 5 attack / 1 defense, the same reference
point Drowned Waystation's own bible uses):

- `drowned_wretch`: player deals 5/hit (0 defense) → dies in `ceil(11/5)` = 3
  hits. Deals 4-1=3/hit unarmored → a clean, cheap fight.
- `gray_ooze`: player deals 5-1=4/hit → `ceil(16/4)` = 4 hits *if the fight
  never slows down* - but its weaken proc knocks the player's own attack to
  3/hit for as long as it keeps landing, which stretches a real fight
  toward 5-6 hits, not 4.

**Both monsters live on `level_01` only - `level_02` has none.** This
dungeon went through two heavier rosters before landing here, both caught
by real `tools/play_llm.py` playthroughs rather than left to hits-to-kill
math alone:

1. Two `drowned_wretch` in one open hall (no chokepoints) let both
   converge on the player at once - a straight pile-on, not a fair fight.
   Fixed by splitting `level_01` into rooms joined by genuinely bent
   corridors (see the tone note below).
2. Even one `drowned_wretch`/`gray_ooze` each on `level_01`, plus a third
   melee fight guarding `level_02`'s Water Gate, added up to three
   back-to-back fights in a strictly linear, no-rest dungeon - a fresh,
   unequipped character reached the third fight critically low or dead
   even spending every potion in the dungeon along the way. Fixed by
   cutting the Water Gate's guard entirely: the water crossing is this
   dungeon's intended obstacle, and a third attrition fight bolted onto
   it was redundant with that, not additive.

With the guard gone, a fresh 30/5/1 character clears both fights on
`level_01` using its own two `healing_potion`s (one per fight, not both
up front - the `gray_ooze` fight is the one that actually needs it) and
reaches `level_02` with a full-ish reserve and nothing left to fight
before the water itself.

`balance_reference_xp: 80` matches Drowned Waystation's own tier - same
general roster, appropriate for a small side dungeon that exists to carry
one mechanic rather than to test a geared-up player.

## Tone notes for anyone (agent or human) revising this later

- The water is an obstacle, not a hazard - `deep_water` never deals chip
  damage the way `ashen_plains`/`dunes` do. The whole point is a route-
  around-or-drink-the-potion choice, not another source of attrition.
- Don't call this dungeon's water `sea` - it's landlocked mountain runoff,
  not ocean, which is exactly why `deep_water` exists as its own tile kind
  (see `docs/content_design_process.md` §0ap). Keep any new flavor text
  consistent with "still, standing, stagnant," never "tide," "salt," or
  "coast."
- Keep the Water Gate forward-only if this dungeon is ever extended
  further - a future level_03 should continue past The Far Vault, never
  loop back across the same water tiles.
- `level_01`'s corridors genuinely bend (two 90-degree turns, not just a
  wall segment beside an open sightline) and its two monsters are placed
  more than `FOV_RADIUS` (8) tiles apart in a straight line. This isn't
  decorative: `Engine._perform_ai` only skips a monster whose own tile
  isn't currently visible to the player, so a long straight corridor (the
  original layout's mistake, caught by a real CLI playthrough) lets the
  player see and simultaneously aggro every monster on it at once, and a
  1-wide corridor open at both ends lets them pincer the player from
  opposite sides - worse than an open room, since there's no way to back
  off and face only one. Any future edit to this level's geometry should
  keep both the bends and the distance, not just one or the other.
- This is unrelated to the Visitor's corruption and to any of the region
  bible's three still-reserved future-dungeon slots (the Goblin Camp, the
  two Elder Age sites) - don't retroactively tie it to that arc.

## Decoration and content-variety pass

`rubble` (both levels) and `chest` (`level_02`, beside the gold_stash) -
the same two kinds Drowned Waystation already established for a flooded
Old Kingdom ruin. `kelp` was deliberately not used here: its fixed flavor
line ("The sea's been here a while") is ocean-specific and would
reintroduce the exact sea/not-sea mismatch `deep_water` exists to fix.

## Verification

Both levels load cleanly via the real content loader (entity/item/
decoration/stairs counts match the authored legend), full `pytest -q`,
`tools/preview.py data/dungeons` full registry, a real `tools/play_llm.py`
CLI playthrough exercising the water-walking potion end to end, and a
`main.py` smoke-launch with a screenshot of both levels.
