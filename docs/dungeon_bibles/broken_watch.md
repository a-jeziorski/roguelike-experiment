# The Broken Watch — Dungeon Bible

*A design document for one dungeon, written the way a GM would key a
site for a tabletop session: what's actually here, why, and what the
player is meant to feel room to room. See `docs/world_history.md` for
the realm-level facts this dungeon has to agree with,
`docs/content_design_process.md` for the mechanical authoring rules, and
`docs/quest_bibles/wayford_arc.md` for the two things this dungeon has
to carry for the arc: `bandit_captain` as a single, climactic spawn, and
one placement for the new `road_ledger` item, sitting unguarded in an
early or mid room. This document is the specific story of *this* place,
decided before any ASCII is drawn.*

## The pitch

Broken Watch was never a home. It was a watchtower - built to watch the
western approach for a Kingdom that stopped sending relief, stopped
sending orders, and eventually stopped existing in any way that reached
this far out. Nobody who's inside it now built it, inherited it, or was
assigned to it. A band of Opportunists found four intact walls, a
working gate (mostly), and a good sightline over the road, and moved in
- not because it was theirs, but because it was *available*, and that's
enough reason in the Long Quiet. Per its own `dungeon.yaml`: "holding
the yard and barracks with looted Kingdom steel and answering to
whichever bandit captain last proved it." No chain of command, no
loyalty to the place itself - just whoever's currently strong enough to
keep the best room.

**This is the load-bearing contrast with Prison Tower**, and it should
stay sharp in every line of flavor text written for this dungeon: Prison
Tower's garrison still believes, on some level, that their old jobs
matter - they're the same institution, just unsupervised. Broken Watch's
bandits know exactly what this place is to them: good walls, nothing
more. Nobody here is "still on duty." Nobody salutes anybody. The
Captain didn't inherit a rank, he just won an argument, most recently.

**Placement on the world bible**: Old Kingdom in origin (a mundane
military-administrative purpose - watching a road - exactly the kind of
site `world_history.md` says to default to for a new Old Kingdom
location), Opportunist in its present Long Quiet occupation. This is
that faction's clearest example per the world bible's own text: "bandits
holding a watchtower... practical, not evil, just taking what an empty
garrison offers."

## Mood

Scavenged and lived-in, not gothic and not squalid either - these
people are getting by well enough that "squalid" would undersell it.
Looted Kingdom gear worn without ceremony (mail "like it was always
his," per `bandit_captain`'s own catalog description), fires lit in
rooms that were never meant to be lived in, nothing maintained beyond
what's actually useful to the people living here right now. The dread,
where it exists, is entirely practical - these are armed people
defending a position they want to keep, not a haunted or cursed place.

## Structure overview

Three levels, unchanged in count and order from the current shipped
dungeon - "The Outer Yard" -> "The Barracks" -> "The Captain's Watch"
already reads as exactly the right shape (approach, living quarters,
climactic perch) and this pass keeps it, rebuilding each level's
geometry and named set pieces from scratch rather than restructuring:

| Level | Name | Set pieces it holds |
|---|---|---|
| `level_01` | The Outer Yard | The Broken Gate, The Watch Room |
| `level_02` | The Barracks | The Barracks Floor, a fortified chokepoint |
| `level_03` | The Captain's Watch | The Captain's Perch |

## The named set pieces

### 1. The Broken Gate (`level_01`)

The entrance, matching `dungeon.yaml`'s own `inspect_text` exactly: "its
gate hanging on one hinge." Patched enough to slow someone down, never
repaired properly - the first proof this place is occupied by people
using it, not people who built it or care about its upkeep beyond what's
functional.

*Why it's first*: sets the mood immediately without a single line of
dialogue needed - a gate that's been *propped*, not fixed, tells the
whole "available, not inherited" story on its own.

### 2. The Watch Room (`level_01` or `level_02` - whichever the rebuilt
### geometry naturally places early/mid)

An old duty room - maps, a lookout post, and the garrison's own
paperwork, none of which the current occupants have any use for. This is
where `road_ledger` sits: not guarded, not displayed, not even moved -
just where the Kingdom's own record-keeping ended up the day everyone
who cared about it stopped coming back. Matches the "administrative
debris nobody cared about" tone `sunken_mine.md` already established for
Old Kingdom institutional decay elsewhere in the world.

*Why it's here*: gives `road_ledger` a placement that explains itself -
the bandits don't value records, so of course it's just sitting here,
unguarded, exactly as the arc bible requires.

### 3. The Barracks Floor (`level_02`)

Bandits' actual living quarters - bedrolls, looted gear repurposed for
everyday use rather than displayed as trophies, a fire that's clearly
lit every night. The dungeon's main population center; most of the
`bandit` roster lives here.

*Why it's here*: the "moved in, not assigned" thesis made physical -
contrast deliberately with Prison Tower's Barracks Floor set piece,
which reads as a workplace between shifts. This one should read as
someone's actual, if temporary, home.

### 4. A fortified chokepoint (`level_02`)

Per `content_design_process.md`'s existing roster note calling this
dungeon's geometry "fortified-compound" - at least one deliberate
chokepoint or interior-pillar break, not a bare rectangle, matching the
geometry-variety discipline already applied to Prison Tower's Gatehouse.
Reads as genuine defensive structure the Kingdom built and the bandits
are still, incidentally, benefiting from.

### 5. The Captain's Perch (`level_03`)

The tower's actual original watch-post, now repurposed as one person's
personal space instead of a duty station - a small irony worth playing
up in flavor text: this room was built to watch the road for the
Kingdom, and now watches it for exactly one man's own advantage instead.
`bandit_captain` is centered here, and here only - **this must remain
the dungeon's single spawn of that entity**, per the arc bible's kill-
quest constraint. The terminal stairs down sit past him, same
"climax by construction" logic as Prison Tower's Warden.

*Why it's last*: the dungeon's climax and the arc's kill-target land in
the same beat on purpose - clearing this room isn't just finishing the
dungeon, it's completing "Clearing the Watch Road" at the same moment.

## Roster and balance (unchanged - existing roster, documented here for
## the first time)

| Monster | Where | Why here specifically |
|---|---|---|
| `bandit` (hp 13/atk 5/def 1, hostile_basic) | `level_01`, `level_02` | The Watch's actual population - straightforward fights, no gimmick, matching people who took this place for its walls, not for any tactical cleverness. |
| `rat` (hp 6/atk 2/def 0, skittish) | `level_01` | Ordinary vermin - a garrison this informally kept has them same as anywhere else abandoned-then-reoccupied. |
| `bandit_captain` (hp 20/atk 7/def 2, hostile_basic) | `level_03` only | The dungeon's climax and the arc's kill-quest target - see set piece 5. Never placed anywhere else; **this constraint is load-bearing for `docs/quest_bibles/wayford_arc.md`'s kill-quest, not just pacing.** |

Hits-to-kill against player baseline (30 hp / 5 atk / 1 def), unchanged
stats: `bandit` deals 4/hit, dies in 4 hits; `bandit_captain` deals
6/hit, dies in 7 hits - the hardest single fight in the dungeon,
consistent with being both the structural climax and the quest's actual
target. No stat changes this pass - reused exactly as shipped.

## Tone notes for anyone (agent or human) revising this later

- Nobody here is "still on duty." If a line of flavor text implies
  loyalty to a chain of command, a lingering sense of assigned duty, or
  guilt about the place not being theirs, it's drifted into Prison
  Tower's register, not this dungeon's - opportunists took this place
  because it was useful, not because they were told to hold it.
- No proper names, same discipline as everywhere else in the project -
  `bandit_captain` stays a title (per his own catalog description,
  "whoever's left standing at the top of the watchtower's rickety
  hierarchy"), not a person the player is meant to recognize by name.
- Keep the Kingdom's own leftover administration (the ledger, any other
  paperwork) explicitly *unwanted* by the current occupants - it's set
  dressing to them, not something to fight over or protect. That's what
  makes `road_ledger`'s placement (unguarded, in a duty room nobody
  cares about anymore) read as natural rather than convenient.
- Stonebridge sits past this dungeon on the same western road (per
  `content_design_process.md`'s roster note) - fine to gesture at in
  flavor text (a lookout position toward "the fortified town further
  on," say) but Stonebridge itself is out of scope for this pass, per
  the arc bible.
