# Prison Tower — Dungeon Bible

*A design document for one dungeon, written the way a GM would key a
site for a tabletop session: what's actually here, why, and what the
player is meant to feel room to room. See `docs/world_history.md` for
the realm-level facts this dungeon has to agree with, and
`docs/content_design_process.md` for the mechanical authoring rules
(balance math, geometry variety, the three story surfaces). This
document is the missing middle layer between those two - the specific
story of *this* place.

Prison Tower is the game's starting dungeon and its four levels have
been shipped since before this document convention existed. This bible
documents what's already there rather than redesigning it, and treats
this as step 0 of the checklist before adding gold to three of its
levels - the first content this dungeon has gained since it shipped.*

## The pitch

Prison Tower isn't a ruin that used to be a prison. It's a prison that
never stopped being one - just stopped having anyone left to answer to.
Nobody sent new orders, nobody relieved the garrison, nobody came to
collect the prisoners on trial or execute a sentence. The guards, the
warden, and the prisoners all just... kept going, each still playing
their old role because nobody told them to stop, in a building with no
outside authority left to overrule any of them. The player starts here,
already thrown in a cell, and escape means descending floor by floor -
past guards still doing their old jobs, prisoners broken by however many
years of this, and a warden still running things exactly like it
matters - to the gatehouse and the world outside.

**Placement on the world bible**: squarely the Old Kingdom's remnants -
`world_history.md`'s own framing, verbatim: "guards, wardens, and
prisoners who kept doing their old jobs (or their old grudges) with no
one left to report to." A functioning justice system implies a
functioning state, so this is Old Kingdom-era in origin; its present,
feral-but-still-operating state is pure Long Quiet. Not a picked-clean
ruin - a still-inhabited institution nobody's shut down, just cut off.

## Mood

Institutional, not gothic. The dread here is procedural - locked doors,
routine violence, a chain of command still technically intact - rather
than supernatural. Every guard and the warden believe, on some level,
that they're still doing their job. The player's escape isn't breaking
into somewhere forbidden; it's walking out of somewhere that quietly
stopped being able to stop them.

## Structure overview

Four levels, one continuous descent - not a hub, not a branch, the
descent itself *is* the escape (the engine has no "climb up" mechanic,
so going down had to double as going out):

| Level | Name | Set pieces it holds |
|---|---|---|
| `level_01` | The Solitary Cell | The Broken Cell, The Chokepoint |
| `level_02` | The Guard Barracks | The Barracks Floor, The Armory |
| `level_03` | The Lower Cellblock | The Cellblock |
| `level_04` | The Gatehouse | The Warden's Floor |

## The named set pieces

### 1. The Broken Cell (`level_01`)

The player starts here: a small cell, already broken open (the escape
that sets the whole dungeon in motion has already happened by the time
the game begins - this isn't a jailbreak the player performs, it's one
they wake up in the middle of). A narrow one-tile corridor is the only
way out - a deliberate chokepoint before the first real room, forcing
a single-file approach rather than letting the player see the whole
floor at once.

*Why it's first*: establishes the whole dungeon's shape in miniature -
confinement, then a forced narrow passage, then whatever's on the other
side. No monster in the cell itself; the first real threat waits past
the chokepoint.

**New this pass**: a `healing_potion` sits just past the chokepoint,
directly ahead of the `rusty_dagger` - the room's two threats (`guard`,
`crossbow_guard`) are both effectively mandatory (the room is fully
open, and neither AI type has a stealth/alert-radius gate - see
`content_design_process.md`'s balance methodology), and until now this
was the only level in the dungeon with zero healing anywhere on it.
*"A guard's basic kit, kept at the post for exactly the kind of trouble a
post like this expects."* - institutional, not treasure, matching this
dungeon's whole procedural mood: a post like this would keep basic aid
on hand the same reflexive way it still keeps a locked door or a loaded
crossbow.

### 2. The Barracks Floor (`level_02`)

The guards' living quarters - not a fortified checkpoint, just a place
people who worked here actually lived between shifts. A `guard` occupies
the main room; a `feral_prisoner` (per the catalog: "a prisoner broken
by years in the dark") sits in a separate cell nearby, distinct from the
guards both in placement and in what they represent - not everyone here
is still playing their old role intact.

**New this pass**: a `gold_pile` sits in the guard's own room - his
wages, still on him. *"A guard's wages, kept close instead of banked -
there was nowhere left to bank it."* Ties into the shared framing below:
this is coin that was already his, not an active payroll still running.

### 3. The Armory (`level_02`)

A reward room behind a locked door (`rusty_key`, found off the critical
path near the `feral_prisoner`'s cell), holding an `iron_sword`. Per the
established convention, locked doors gate rewards, not paths - this room
is never mandatory. Reads as: whoever ran this barracks kept the good
gear locked up, same as any functioning armory would, and never got the
chance to hand it out.

### 4. The Cellblock (`level_03`)

Eight small cell-alcoves off a shared corridor (four to a side) - a
`feral_prisoner`, a `rat`, and a resupply beat (`healing_potion`,
`arrows`) spread across them before the final level. This is the dungeon's "vermin and the broken" floor - what's left
of the people this prison actually held, alongside what's moved in since
nobody's been exterminating pests either.

**No gold here, deliberately.** Prisoners have nothing to loot - adding
coin to this floor would contradict what the floor is *for* (these are
the people the coin was never theirs to begin with) and would clutter a
level whose whole identity is "resupply, not treasure." The absence is
as intentional as every other floor's presence.

### 5. The Warden's Floor (`level_04`)

The Gatehouse: one large room broken up by interior pillar-blocks (not a
bare rectangle - see the geometry-variety note in
`content_design_process.md`), a `crossbow_guard` covering one approach,
and the `warden` himself, centered in the room. Per the catalog: "not
eager to let his prize escape." The terminal stairs down - freedom -
sit past him, so this fight is the dungeon's climax by construction, not
just placement.

**New this pass**: a `gold_stash` sits just past where the warden falls
- his own hoard, the first item this level has ever had. *"The Warden's
own hoard - coin taken off every prisoner and guard who never asked for
it back."* Framed explicitly as *his*, specifically, not the barracks'
shared wages - a warden who kept running this place on his own terms for
however long the Long Quiet has lasted would have accumulated more than
any one guard's pay, and taken it from people with no one left to
complain to.

## Why there's gold here at all

Nothing in this world's fiction describes a functioning economy in the
Long Quiet - there's no central authority left to mint, tax, or pay
anyone (`world_history.md`). So every gold placement in this dungeon is
explicitly *inert, already-possessed coin*, never wages currently being
paid or a market currently operating: money people already had on them,
or already had locked away, when the lines of communication went quiet,
carried or hoarded out of habit ever since. It explains why coin is just
sitting here without inventing a payroll system this world doesn't have
- and it's coin that hasn't been spendable anywhere in a generation,
which is exactly what makes it worth carrying back out.

## Roster and balance (unchanged - existing content, documented here for the first time)

| Monster | Where | Why here specifically |
|---|---|---|
| `guard` (hp 14/atk 5/def 2, hostile_basic) | `level_01`, `level_02` | The garrison still doing its job - a straightforward fight, no gimmick, because guarding is exactly what it's still trying to do. |
| `crossbow_guard` (hp 10/atk 4/def 1, ranged_basic) | `level_01`, `level_04` | Watches an approach from range rather than closing immediately - reads as a guard actually covering a post, not just standing in a room. |
| `feral_prisoner` (hp 8/atk 3/def 0, skittish) | `level_02`, `level_03` | What years in the dark did to whoever else was held here - lashes out, then flees, never a controlled fight. |
| `rat` (hp 6/atk 2/def 0, skittish) | `level_03` | Ordinary vermin; a prison this abandoned has them same as anywhere else. |
| `warden` (hp 26/atk 7/def 3, hostile_basic) | `level_04` | The dungeon's climax - see set piece 5. Highest stats of any monster in this dungeon, deliberately: he's the one person here who never stopped believing he was still in charge. |

Hits-to-kill against player baseline (30 hp / 5 atk / 1 def) are
unchanged from every other use of these monster types elsewhere in the
game - no stats touched, this section documents existing balance rather
than introducing new. The warden (7 atk vs 1 def = 6/hit, needs ~5 hits
at 26 hp / 4 dmg-per-hit) is the hardest single fight in the dungeon,
consistent with being the final encounter - and, per the escape route
note directly below, isn't expected to be winnable on a first pass.

**Escape-route feasibility (verified this pass via an actual playthrough,
not just arithmetic on paper)**: `guard` and `crossbow_guard` are both
effectively mandatory on `level_01`. `crossbow_guard` sits in a small
pocket set off from the rest of the room by a short wall, but that
pocket connects back to the open floor through a single unwalled row -
enough of a sightline that neither `hostile_basic` nor `ranged_basic`
(neither of which has any stealth/alert-radius gate, see
`content_design_process.md`) needs the player to walk past the wall to
notice them; both monsters close in or open fire the moment they're
anywhere in the player's own FOV. Fighting both back to
back, bare-handed, against player baseline costs roughly 28-34 damage -
more than the entire starting HP pool, and the `rusty_dagger` alone
(reachable first, right at the room's entrance) only brings that down to
~17-23. Combined with zero healing anywhere on the level before this
pass, this made `level_01` a real, repeatable near-death or death on
otherwise-ordinary play, not just a hard fight - the `healing_potion`
added this pass (see set piece 1) is the fix, not a stat change to
either monster.

Reaching `level_04` and defeating the `warden` in the same trip is
*not* the bar for "the escape route is feasible" - `engine/engine.py`'s
`_perform_ai` never chases a monster the player has broken line of sight
with (it's a no-op the instant `game_map.visible` no longer covers the
monster's own tile), so retreating out of `level_04` mid-fight and
regrouping is already a fully supported strategy, and "An Old Debt"
(Millhaven's sidequest built around the warden's death) already assumes
a later return trip. The bar is: a player who plays reasonably carefully
through `level_01`-`level_03` should be able to reach `level_04` with a
real HP margin, not already gutted before the dungeon's actual climax.

## Decoration pass (first content this dungeon has gained since gold)

Zero decorations existed anywhere in this dungeon before this pass -
every room was bare `floor` with entities/items and nothing else. Two
new `DecorationKind`s were added specifically for it (`content/schema.py`/
`data/sprites.yaml`): `cell_bars` (`rltiles` `iron_bars`) and `chains`
(`rltiles` `iron_chain`) - nothing in the existing kit covered a literal
prison cell, and this is the one dungeon in the game where that's the
whole point. No cart/weapon-rack sprite exists in either Kenney sheet
(checked, same conclusion Wayford's own razed-decoration pass reached
for a cart) - the Armory reuses `chest` for stored gear instead of
forcing a bad fit. Kept institutional, not gothic, per the Mood section
above: no bones, no blood, no cobwebs - `cell_bars`/`chains` read as
*maintained* fixtures of a still-functioning prison, not the ruin of
one.

- **`level_01`**: a `bed` and `cell_bars` in the player's own starting
  cell (already broken open); `table`/`chair` at the guard's post past
  the chokepoint; `barrel`/`crate` near the `thorned_plate` as a small
  supply cache; a lone `chair` at the crossbow guard's watch pocket,
  deliberately sparse - a post, not living quarters.
- **`level_02`**: two `bed`s in the guards' shared room (plural,
  matching "barracks"), plus a `table`/`chair`; `chest`/`barrel` in the
  Armory; `cell_bars`/`chains` in the feral prisoner's own cell.
- **`level_03`**: every one of the eight cell-alcoves gets `cell_bars` -
  the floor's entire identity is "these were cells," so the decoration
  says so in every one of them. Two of the still-empty alcoves also get
  a `bed` or `chains` for texture, so it doesn't read as one decoration
  repeated eight times.
- **`level_04`**: `bookshelf`/`table`/`chair` at the Warden's own desk -
  he's still keeping records that matter to nobody but him - plus a
  `chest` beside the `gold_stash`, and `barrel`/`crate` near the
  entrance as old gatehouse supplies.

## Tone notes for anyone (agent or human) revising this later

- Everyone here still believes, on some level, that their old job still
  matters. The guards aren't opportunists who moved in after - they're
  the same institution, just unsupervised. Keep that distinction from
  `broken_watch` (Opportunists, people who moved into infrastructure
  that was never theirs) sharp.
- The warden is the one character in this dungeon it's worth writing as
  a specific person rather than a type - see his catalog description
  ("not eager to let his prize escape") and Millhaven's "An Old Debt"
  sidequest, which treats his death as something another former prisoner
  specifically asked for.
- Gold placed here is always *someone's*, never a generic dungeon
  treasure drop - a guard's wages, a warden's hoard. If this dungeon
  ever gains more gold placements later, keep that discipline: name
  whose it was and why they still had it, per the framing above.
