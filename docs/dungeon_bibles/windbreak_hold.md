# Windbreak Hold — Dungeon Bible

*A design document for one location, written the way a GM would key a
site for a tabletop session: what's actually here, why, and what the
player is meant to feel room to room. See `docs/world_history.md` for
the realm-level facts this location has to agree with and
`docs/content_design_process.md` for the mechanical authoring rules -
in particular §0p, the new `dunes` hazard tile this location and its
neighboring dungeon (`the_windrest`) exist to justify.*

## The pitch

The map's east-central expanse has always read as empty - open plains,
no forest, no mountains, nothing placed there through several content
passes. Windbreak Hold is the answer to why: a wind that never fully
settles has spent longer than anyone's been alive scouring this stretch
down to loose, shifting dune sand - not a storm passing through, a
permanent condition of the ground itself. Crossing it on foot, gritty
and exhausting mile after mile, is a real, ongoing cost, not just flavor
text. The Old Kingdom farmed this land once, before the wind won (this
is ordinary, administrative countryside in `world_history.md`'s own
terms, not a mystery), and built a proper waystation - The Windrest -
specifically to shelter travelers and workers crossing it. Whatever kept
that shelter's windbreak walls maintained stopped with the Sundering,
same as everywhere else, and the dunes have had the run of the place
since.

A small band of Settlers tried to resettle here anyway - the land itself
is good, if anyone could stand to work it - and found that the Windrest,
the one real shelter for miles, was already held: Opportunists got there
first, the same "practical, not evil, just taking what an empty garrison
offers" logic `world_history.md` already establishes for Broken Watch.
Unable to take the real shelter, the settlers built their own - cruder,
smaller, salvaged rather than Kingdom-built - in the lee of a low rise
nearby, and named it for the one thing it actually does: break the wind
enough to survive behind. They want the Windrest back. Not for its own
sake - for what having *real* walls again would mean.

**Placement on the world bible**: pure Long Quiet, pure Settlers, same
footing as every other present-day town - no faction of its own, no
ruin under it (their own hold is a fresh, if crude, structure). Its
neighbor, the Windrest, is the mundane Old Kingdom site (a waystation,
explicitly one of `world_history.md`'s own listed examples of ordinary
Kingdom institutional purpose) now squatted by Opportunists - the exact
"fallen infrastructure, present-day occupants" shape Broken Watch and
Sunken Mine already established, just with a wind-scoured plain instead
of a hill or a mineshaft as the terrain hook.

## Mood

Exposed and provisional, in a way none of the other Settler towns are.
Millhaven's unhurried, Saltmarsh is plain and unbothered, Grey Valley is
isolated but settled-in - Windbreak Hold should read as newer and less
certain than any of them, a camp that's proven it can survive one season
out here but hasn't proven it can survive many. The wind is a constant
presence even inside the palisade's earshot, less a weather event than
just the sound this ground makes now; nobody here talks about it much,
the way people stop remarking on a noise that's simply always running
underneath everything else.

## Structure overview

One level, matching every other Settler town's precedent.

| Level | Name | Set pieces it holds |
|---|---|---|
| `level_01` | Windbreak Hold | The Windbreak Wall, The Captain, The Windrest's Shadow |

## The named set pieces

### 1. The Windbreak Wall

Not a real fortification - a curved line of salvaged timber and packed
earth, angled to break the prevailing wind rather than to stop an
attacker, the whole reason anyone can stand upright inside it without
being worn down turn by turn. The settlement's own tiles sit on ordinary
`plains`, not `dunes` - this is the one pocket of the Scoured Reach the
wind hasn't scoured bare, and it should read as a deliberate, hard-won
exception to everything just outside it, not as unremarkable safe
ground.

*Why it matters mechanically*: the contrast is the whole point. A
player who's just crossed even a short stretch of `dunes` to reach this
settlement should feel the wall as relief the instant they're inside it
- the game's only location so far where "you've arrived" is a
mechanical event (hazard damage stops), not just a narrative one.

### 2. The Captain

**`windbreak_captain`** (new entity, `ai: villager`, `stationary: true`,
title only) - leads the settlers who built and hold this place. Not an
Elder in the Millhaven/Grey Valley sense (nobody here has had time to
become one) - a working title for whoever's proven capable of keeping a
season-old camp alive, positioned near the wall's strongest-built
section.

*Questgiver*: gives `reclaiming_the_windrest` (kill `windrest_captain` at
`the_windrest`, then report back) - the same familiar kill-the-leader
shape Broken Watch's own quests already use (`clearing_the_watch_road`,
`a_wall_worth_holding`), deliberately not a new trigger type. This
location's one piece of real novelty is the `dunes` hazard itself;
stacking a second new quest-mechanic on top of it in the same pass would
blur which one the location is actually about. No deadline - the
Opportunists aren't advancing on the Hold, they're just sitting on
something the settlers want back; the pressure here is environmental
(the crossing itself), not a ticking clock.

*Dialogue direction*: practical, a little worn down, focused on the
concrete difference real walls would make rather than on any grievance
against the Opportunists personally - "they're not doing anything with
it, they're just *in* it" is the right register, not a grudge.

### 3. The Windrest's Shadow

A plain villager positioned to look out toward where the Windrest sits,
just past sight - the settlement's own reminder of what it's actually
after. Ordinary texture, not a named set piece of its own; exists mainly
to help this small roster clear the 75% unique-dialogue floor
comfortably (three talkable NPCs: the Captain plus two villagers).

## Roster

One new stationary `villager`-AI entity (`windbreak_captain`, unique
catalog id). Two plain `villager` spawns, each with its own per-spawn
`dialogue`. No `town_guard` - this settlement can't spare anyone as a
dedicated guard, and its actual defense is the wall's geometry, not a
combatant; a guard here would undercut the "barely holding on" mood the
same way one would have undercut Saltmarsh's un-fortified calm.

## Tone notes for anyone (agent or human) revising this later

- No proper names - `Captain`, matching every other named NPC's
  titles-only discipline (a working title earned by circumstance, not a
  formal rank).
- The dunes are terrain, not weather. `dunes` (§0p) reads as a concrete,
  permanent ground condition - loose sand, gritty and exhausting to
  cross - not an active storm the player is caught in. Avoid "storm"
  language in new flavor text for this reason; the wind explains how the
  ground got this way, it isn't itself the hazard. Mundane either way,
  matching `world_history.md`'s Old-Kingdom-default-to-mundane
  instruction - nothing here should be personified or supernatural.
- Keep this place feeling newer and more provisional than every other
  Settler town - a proven-for-one-season camp, not an established
  community. Its whole ask (a real shelter instead of a salvaged one)
  should read as reasonable and overdue, not greedy.
