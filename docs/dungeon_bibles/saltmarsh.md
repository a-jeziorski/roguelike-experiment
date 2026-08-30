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

Regenerated at 36x28 (up from the original 18x11, which had both the
Elder and the previously-undocumented `saltmarsh_witch` standing on bare
ground with no building at all) so both stationary residents get a real
interior - the same `stationary: true` -> real-interior rule Millhaven's
own regeneration established, applied here for the first time. Kept
deliberately modest even at the larger footprint: two small huts, a
landmark, and coastal texture, never a townscape - Saltmarsh is "the
smallest, plainest Settler town in the game" and should still read that
way after the redo, just no longer *empty*.

**Decoration stays specific to this place, not copied from Millhaven's
kit wholesale.** No `tilled_soil` and no trees - Saltmarsh doesn't farm
and isn't forested; it's coastal marsh. What's here instead: `herb_clump`
standing in for marsh reeds along the shoreline and the wet ground behind
the huts, `bush` for coastal scrub rather than a treeline, and the Drying
Racks (see set piece 4) turned into an actual `landmark` tile instead of
just a line in `dungeon.yaml`'s own `inspect_text`. One small unentered
wall cluster reads as a collapsed, unusable shack - the same "purely
decorative, no new mechanics" technique every other settlement pass uses.

**Second regeneration, applying `content_design_process.md` §0af.** The
first regeneration housed both stationary residents but left the road
half-finished - a single track down from the gate that never clearly
reached either hut's door and gave the town no real hub. This pass
redraws the network with the Drying Racks as the plaza it converges on
(a fishing hamlet's natural gathering point, and the one landmark this
bible already names), the Elder's hut touching the main street directly
near the gate, and the Witch's hut reached by a short connected branch.
Footprint trimmed again, 36x28 to 34x26 - same 5-entity cast, same 2
buildings. The gate also picked up the `town_gate` `tile_sprite`
Millhaven's own gate uses.

The user caught a real bug in the same pass: the perimeter wall on the
east edge was drawn *outside* the sea strip, meaning a stretch of open
water sat needlessly boxed in behind masonry it had no business needing
- the sea is already impassable and is the natural boundary here, the
same way `open_boundary` lets a level's own edge stand in for a wall
elsewhere. Fixed by dropping that wall column and extending the sea to
the map's actual edge instead - Saltmarsh's coastline is now bounded by
water, not a stone wall pretending to hold the tide back, which also
happens to be the one settlement in this batch where the boundary was
never meant to be a rectangle in the first place.

| Level | Name | Set pieces it holds |
|---|---|---|
| `level_01` | Saltmarsh Shore | The Elder, The Witch, The Tide-Watcher, The Netmender, The Drying Racks |

## The named set pieces

### 1. The Elder

**`saltmarsh_elder`** (new entity, `ai: villager`, `stationary: true`,
title only) - the one resident who remembers the Waystation as a working
building, not a ruin. Has a real hut now (bed, chest, chair), small and
plain, matching the "smallest, plainest" framing rather than contradicting
it - a real building doesn't have to be a grand one.

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

### 2. The Witch

**`saltmarsh_witch`** (existing entity, `ai: villager`, `stationary: true`,
`shop_inventory` set) - present in Saltmarsh since an earlier pass but
never given a place to stand or a mention in this bible; found this pass
standing on bare road with no building at all, the same kind of gap
Millhaven's Trainer and Debtor turned out to have. Brews and sells
potions to the rest of the hamlet (`healing_potion`,
`teleportation_potion`, `shadow_cloak_pin` - catalog-default
`shop_inventory`, untouched by this pass). Has a real hut now
(bookshelf, chest, table), separate from the Elder's, with the loose
`healing_potion` pickup that already sat in this level relocated just
outside her door rather than removed.

*Dialogue direction*: keeps the catalog's own default line ("Step right
up deary. Have I got brews for you!") rather than a per-spawn override -
nothing about her role needed a Saltmarsh-specific line the catalog
default didn't already cover.

*Why it's here*: closes a real gap - a shopkeeper with actual mechanical
weight (`shop_inventory`) standing unhoused and undocumented is exactly
the kind of oversight this settlement-redo pass exists to catch, not a
new addition invented to pad the roster.

### 3. The Tide-Watcher

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

### 4. The Netmender and The Drying Racks

Two more plain villagers, ordinary texture rather than named set pieces
of their own - the netmender doing upkeep, a second villager minding the
drying racks. The racks themselves are a real `landmark` tile now, not
just a line in `dungeon.yaml`'s own `inspect_text` ("nets strung out to
dry") - salt-stiffened rope and driftwood frames, described rather than
only implied. A barrel and a length of fence sit beside it, reading as
"kept by someone," the same "belongs to something" rule every other
settlement pass's decoration follows. Their job is to make Saltmarsh's
cast land at 100% unique dialogue (five talkable NPCs: the Elder, the
Witch, plus three villagers), comfortably clearing the 75% floor
`content_design_process.md` §1 requires, not to carry any plot weight.

## Roster

Two stationary `villager`-AI entities: `saltmarsh_elder` (new this pass,
unique catalog id - load-bearing the same way every other named
questgiver's id is, since `QuestLog.check_questgiver`/`check_delivery`
match on it globally, not per-dungeon) and `saltmarsh_witch` (pre-existing,
`shop_inventory` set - see set piece 2). Three plain `villager` spawns,
every one with its own per-spawn `dialogue`. No `town_guard` - Saltmarsh
is explicitly the un-fortified counterpart to Stonebridge; per
`dungeon.yaml`, nothing about it is defensive, and it shouldn't gain a
deterrent this pass just because its two Settler siblings have one.

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
