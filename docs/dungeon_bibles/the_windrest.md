# The Windrest — Dungeon Bible

*A design document for one dungeon, written the way a GM would key a
site for a tabletop session: what's actually here, why, and what the
player is meant to feel room to room. See `docs/world_history.md` for
the realm-level facts this dungeon has to agree with,
`docs/content_design_process.md` (particularly §0p, the `dunes` hazard
this dungeon's whole premise depends on), and
`docs/dungeon_bibles/windbreak_hold.md` for the settlement whose quest
targets this dungeon's `windrest_captain`. This document is the specific
story of *this* place, decided before any ASCII is drawn.*

## The pitch

The Windrest was never a home, a garrison, or a mystery - it was a rest
stop. The Old Kingdom farmed the Scoured Reach when it was just open
farmland, not yet scoured, and built a proper waystation here for
whoever worked that land or crossed it: real windbreak walls, a
stone-floored common room, enough shelter that a day's crossing didn't
mean a day lost to grit and exhaustion. Whatever kept its walls sound
and its drainage clear stopped the same week everything else did. The
wind found the gaps first, scouring the land around it down to dune
sand over the years since; a band of Opportunists found the place
shortly after, and unlike Broken Watch's bandits (who took a watchtower
for its sightline) these people took the Windrest for the one thing
that actually matters out here: it's the only real shelter for miles,
and shelter is worth more than loot in a place where the ground itself
is the real threat.

**Placement on the world bible**: Old Kingdom in origin - a waystation,
one of `world_history.md`'s own listed examples of ordinary Kingdom
institutional purpose, no different in kind from Drowned Waystation's
own coastal counterpart. Opportunist in its present occupation, the
same "practical, not evil, just taking what an empty garrison offers"
logic Broken Watch already established - reused deliberately rather than
inventing a second faction motive, since it's the correct one here too.

## Mood

Practical, not sinister - these people are here for the walls, not for
anything the building itself represents. Where Broken Watch's occupants
settled in and made themselves at home, the Windrest's occupants should
read as more recently arrived and more purely functional about it:
supplies stacked rather than displayed, sleeping spots claimed near the
better-sealed walls, nothing decorative. The wind should be audible in
the flavor text even indoors - a building that mostly works, not one
that's forgotten what it's for.

## Structure overview

One level - the Windrest is a single waystation building, not a sprawling
complex; matching a modest, standard combat dungeon's scope rather than
Broken Watch's three-level structure. The location's real novelty lives
in the dune approach outside it, not in this building's own size.

| Level | Name | Set pieces it holds |
|---|---|---|
| `level_01` | The Windrest | The Storm Door, The Common Room, The Captain's Corner |

## The named set pieces

### 1. The Storm Door

The building's actual entrance - a heavy, iron-braced door (a real term
for exactly this: an outer door built specifically against weather,
older than the Sundering), the one piece of the original structure
clearly still maintained (by whoever's inside now, out of self-interest,
not reverence). The literal threshold between the dunes outside and
safety inside; crossing it should be the same kind of mechanical relief
as reaching Windbreak Hold's own wall, just earned through a fight
instead of a walk.

*Why it's first*: the dungeon's whole thesis in one object - a door
worth keeping sealed, on both sides, for exactly the same reason.

### 2. The Common Room

The waystation's original main hall - what would have been a shared
rest space for Old Kingdom travelers, wide enough that its Kingdom-built
proportions are still obvious under whatever the current occupants have
piled into it. This is the dungeon's main population center; most of the
roster lives and sleeps here, in a real if graceless way that
distinguishes them from Broken Watch's more comfortable Barracks Floor -
these people took a rest stop, not a home, and it still shows.

*Why it's here*: the largest, most contested space, matching its role
as the building's actual center - a wide room built for people passing
through, now occupied by people who don't intend to leave.

### 3. The Captain's Corner (climactic)

Not a separate room - the Common Room's best-sealed corner, the one spot
even the wind can't reach, claimed by whoever's currently in charge the
same "won an argument, most recently" logic `broken_watch.md` already
establishes for its own captain. `windrest_captain` is centered here, and
here only - **this must remain the dungeon's single spawn of that
entity**, since `windbreak_hold.md`'s `reclaiming_the_windrest` quest
targets it specifically. Its own display `name` is plain "Bandit
Captain" (matching `bandit_captain`'s at Broken Watch), deliberately not
"Windrest Captain" - both this dungeon and its neighboring settlement
already carry "wind"/"Windrest"/"Windbreak" in their own names, and
`windbreak_captain`'s own display name is simply "Captain"; a second
"Windrest Captain" title would read as confusingly similar to a player
being sent by one to kill the other. The terminal exit (a `stairs_down`
tile at the Storm Door itself, `stairs_down: null` per `elder_cairn.md`'s own
precedent for a terminal exit regardless of literal up/down flavor) sits
near the entrance, not past this corner - leaving after the fight means
walking back out into the open, same as arriving did.

*Why it's the climax without being physically deepest*: this is a small,
single-level dungeon: the climax is who's hardest to reach and best
defended within the one room that matters, not distance from the
entrance the way a larger dungeon's final level would be.

## Roster and balance (reused roster, no new monsters)

| Monster | Where | Why here specifically |
|---|---|---|
| `bandit` (hp 13/atk 5/def 1, hostile_basic) | Common Room | The Windrest's actual occupants - same stats, same straightforward-fight intent as Broken Watch's own use of this entity; no gimmick, people who took this place for its walls. |
| `windrest_captain` (hp 20/atk 7/def 2, hostile_basic) | The Captain's Corner only | The dungeon's climax and `reclaiming_the_windrest`'s kill target - see set piece 3. Never placed anywhere else. |

Hits-to-kill against player baseline (30 hp/5 atk/1 def), unchanged
stats: `bandit` deals 4/hit, dies in 4 hits; `windrest_captain` deals
6/hit, dies in 7 hits - consistent with Broken Watch's own use of the
same two entities, no rebalancing needed. A `healing_potion` sits near
the Storm Door - a "brace yourself" placement before the Common Room's
fight, and a practical one too: whatever the player took crossing the
dunes outside, this is the first chance to recover from it before the
real fight starts.

## Tone notes for anyone (agent or human) revising this later

- These people are here for shelter, not loot or territory - if a line
  of flavor text implies they're guarding treasure or defending a
  strategic position, that's drifted into Broken Watch's register, not
  this dungeon's. The correct framing is closer to "squatting in the one
  dry room for a hundred miles."
- No proper names - `windrest_captain` stays a title ("Bandit Captain,"
  see set piece 3), same discipline as
  everywhere else.
- Keep the wind audible even indoors - a line or two of ambient flavor
  text (wind against the walls, a loose shutter, sand hissing under a
  door) helps this dungeon feel continuous with the hazard outside it
  rather than a wholly separate
  space the player steps into and forgets about.
