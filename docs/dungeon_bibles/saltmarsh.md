# Saltmarsh — Dungeon Bible

*A design document for one location, written the way a GM would key a
site for a tabletop session: what's actually here, why, and what the
player is meant to feel room to room. See `docs/world_history.md` for
the realm-level facts this location has to agree with and
`docs/content_design_process.md` for the mechanical authoring rules.
Written for this pass: Saltmarsh shipped in an earlier round with no
bible of its own, no named cast, and no reason for the player to come
back once they'd seen it.*

## The pitch

Saltmarsh's own `dungeon.yaml` already draws the shape: a handful of
shacks and drying racks above the tideline, home to fewer than a dozen
people who make their living off the sea rather than out of it - built
within sight of the Drowned Waystation on purpose, by people who decided
a flooded ruin wasn't reason enough to leave a good stretch of water. If
Millhaven is "people choosing to stay," Saltmarsh is the same choice made
by people who never had anywhere grander to begin with - the smallest,
plainest Settler town in the game, and it should read that way without
reading as *lesser*. This pass gives it one thing to make it a real
place rather than a stop on the way to the Waystation: an Elder who
remembers what this coast used to be, and a quest that gives the
Waystation's own leftover paperwork (`waystation_manifest`, placed there
this same pass - see `docs/dungeon_bibles/drowned_waystation.md`)
somewhere to go.

**Placement on the world bible**: pure Long Quiet, pure Settlers, same
footing as Millhaven, Wayford, and Stonebridge - no ruin under it, no
faction of its own. Its only distinguishing feature is proximity: it's
the one Settler town built close enough to a fallen Old Kingdom site to
actually remember what stood there before the Sundering reached it,
where Wayford and Stonebridge's own nearby ruins (Broken Watch) are
Opportunist-occupied rather than simply abandoned.

## Mood

Small and unhurried, closer to Millhaven's "nothing here is trying to be
more than it is" register than Wayford's ambition or Stonebridge's
watchfulness. Nobody in Saltmarsh is afraid of the Waystation - it's just
offshore scenery that happens to have a history, the way an old wreck
might. The one exception is `wayford_razed`'s flag reaction (see set
piece 3): even here, at the edge of the map, news of a whole town's fall
reaches people and briefly interrupts the unhurried tone - proof the
reactive-world mechanism's reach isn't limited to the towns directly
involved.

## Structure overview

One level, matching every other Settler town's precedent - Saltmarsh
doesn't need more than that to earn a proper cast, just a reason for at
least one of its residents to be worth talking to twice.

| Level | Name | Set pieces it holds |
|---|---|---|
| `level_01` | Saltmarsh Shore | The Elder, The Tide-Watcher, The Netmender, The Drying Racks |

## The named set pieces

### 1. The Elder

**`saltmarsh_elder`** (new entity, `ai: villager`, `stationary: true`,
title only) - the one resident who remembers the Waystation as a working
building, not a ruin. Positioned toward the shoreline side of the
hamlet, facing the water the Waystation sits in.

*Questgiver*: gives `what_the_tide_kept` (fetch `waystation_manifest`
from the Drowned Waystation - see `docs/quest_bibles/` convention for a
single-quest addition folded directly into the dungeon bible rather than
a separate arc document, since this is one quest, not a multi-questgiver
arc). No deadline - deliberately, to diversify the game's mix of
deadline and non-deadline quests; recovering a piece of the past isn't
time-pressured the way a live threat is.

*Dialogue direction*: curious and a little wistful, never urgent -
"sometimes I wonder what they were even carrying, back then" is
memory-keeping, not a demand. Contrast deliberately with Wayford's
Clerk, whose curiosity about old records is administrative; the Elder's
is personal.

*Why it's here*: gives the Waystation's own leftover item (placed there
as part of this same pass) somewhere to matter, the same way
`a_record_worth_keeping` gives Broken Watch's `road_ledger` somewhere to
go - a small town's version of the same "someone still cares what the
old infrastructure meant" throughline.

### 2. The Tide-Watcher

A plain villager positioned near the shoreline, carrying this pass's
`wayford_razed` flag reaction (`content_design_process.md` §0k) -
distant news reaching the smallest, most out-of-the-way town in the game
on purpose, to show the mechanism's reach isn't limited to towns
directly involved in the consequence that fired it.

*Dialogue direction*: their normal line is about the tide itself
("strange this season... not the worst you'd call wrong"), so the flag
line reading as a genuine interruption of an otherwise unremarkable day
is the point - the news should land as incongruous with their usual
small concerns, not as something they were already braced for.

### 3. The Netmender and The Drying Racks

Two more plain villagers, ordinary texture rather than named set pieces
of their own - the netmender doing upkeep, a second villager minding the
drying racks (both physical details already present in `dungeon.yaml`'s
own `inspect_text`: "nets strung out to dry"). Their job is to make
Saltmarsh's cast land at 100% unique dialogue (four talkable NPCs: the
Elder plus three villagers), comfortably clearing the 75% floor
`content_design_process.md` §1 requires, not to carry any plot weight.

## Roster

One new stationary `villager`-AI entity (`saltmarsh_elder`, unique
catalog id - load-bearing the same way every other named questgiver's id
is, since `QuestLog.check_questgiver`/`check_delivery` match on it
globally, not per-dungeon). Three plain `villager` spawns, every one with
its own per-spawn `dialogue`. No `town_guard` - Saltmarsh is explicitly
the un-fortified counterpart to Stonebridge; per `dungeon.yaml`, nothing
about it is defensive, and it shouldn't gain a deterrent this pass just
because its two Settler siblings have one.

## Tone notes for anyone (agent or human) revising this later

- No proper names - `Elder`, matching every other named NPC's
  titles-only discipline.
- Keep Saltmarsh un-fortified and un-anxious. It sits near a ruin, not a
  threat - the Drowned Waystation holds nothing that's ever moved toward
  this shore, and no flavor text here should imply otherwise. Stonebridge
  gets the watchfulness; Saltmarsh gets curiosity about the past instead.
- The Elder's quest requires zero changes to the Drowned Waystation's own
  combat/geometry - `waystation_manifest` sits there as a placed item,
  same "arrival is the target, not a fight" shape `word_down_the_road`
  already established for a different trigger type.
