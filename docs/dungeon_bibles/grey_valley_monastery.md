# Grey Valley Monastery — Dungeon Bible

*A design document for one location, written the way a GM would key a
site for a tabletop session: what's actually here, why, and what the
player is meant to feel room to room. See `docs/world_history.md` for
the realm-level facts this location has to agree with and
`docs/content_design_process.md` for the mechanical authoring rules.
Written for the Goblin Horde arc's Round 2 - the settlement whose
economy the horde's dispersal actually disrupted, three days after
Wayford's own deadline came and went.*

## The pitch

Grey Valley Monastery is Settlers doing what Settlers do - Millhaven,
Wayford, Stonebridge, and Saltmarsh's own choice, made again by a
smaller group in a harder-to-reach place. What makes this one distinct
isn't the people, it's the location: hidden deep in the forested Grey
Valley, far enough from the road network that nobody's forced to pass
through, they didn't build from nothing - they moved into the standing
ruins of an Old Kingdom monastery and made it livable again. And unlike
every other Settler town, their livelihood isn't farming, fishing, or
trade - it's hunting. Silversilk Caves sits right beside them, and for
as long as anyone here remembers, the caves' cave spiders have been
food and, more valuably, silk: the one thing this isolated community
actually has to offer anyone who makes the trip out to them. That
arrangement held until the Goblin Horde broke apart passing Wayford and
a splinter of it moved into the caves' upper reaches - the settlers'
own hunting grounds - cutting them off from the one resource their whole
economy runs on. They can't clear the goblins themselves; they can hire
someone who can, so long as that someone understands the caves aren't
empty of the *other* thing they still need.

**Placement on the world bible**: pure Long Quiet, pure Settlers, same
footing as every other present-day town - no faction of its own, no
ambiguity about what these people are. Its Old Kingdom monastery follows
`world_history.md`'s own explicit instruction for a new Old Kingdom
site: default to mundane institutional purpose, nothing overtly magical
about the architecture. A monastery fits that instruction cleanly - a
real, administrative-adjacent institution (record-keeping, teaching,
quiet routine) rather than anything mystical, the same "ordinary"
register the doc insists on for Prison Tower's garrison or Sunken Mine's
shafts.

## Mood

Isolated, self-sufficient, and - since the caves went quiet on them -
worried in a way none of the other Settler towns currently are.
Millhaven's "nothing here is trying to be more than it is" doesn't quite
fit; this is a community that chose distance from everyone else on
purpose, and is now finding out what that isolation costs when the one
resource it depends on gets contested. Nobody here is desperate yet -
they're resourceful, not helpless - but the Elder's welcome should carry
real relief that someone finally made the trip out, not just routine
hospitality.

## Structure overview

One level, matching every other Settler town's precedent - a small,
standard settlement doesn't need more than that to earn a proper cast.
Regenerated at 40x34 (up from the original 22x12, which had the Elder
and Weaver both standing in open plains) so both stationary residents
get a real building - the same `stationary: true` -> real-interior rule
Millhaven's own regeneration established, applied here for the first
time to this settlement. Deliberately smaller than Millhaven's own
60x60: a four-person cast doesn't need a town-sized footprint, only room
enough for two buildings, a landmark, and decoration that reads as
composed rather than a field with dots in it.

**Decoration stays specific to this place, not copied from Millhaven's
kit wholesale.** No `tilled_soil` anywhere - the pitch is explicit that
this settlement doesn't farm. No cemetery either; nothing in this
bible's own history calls for one, and inventing one just to match
Millhaven would be exactly the kind of unearned detail the process this
followed argues against. What's here instead: a heavy treeline along
both side walls (the valley's own forest, the reason this place is hard
to find), a stone cistern (a monastery's own water source, reusing the
`well` `tile_sprite_override` rather than authoring new art), and a
small storage nook of barrels/crates outside the Weaver's workshop
(goods and hunting gear, not farm produce). Two small unentered wall
clusters read as the parts of the monastery nobody got around to
rebuilding - same "purely decorative, no new mechanics" technique every
other settlement pass uses, framed as ruin rather than storehouse.

**Second regeneration, applying `content_design_process.md` §0af.** The
first regeneration gave both stationary residents real buildings but
never gave the settlement a real road - the Elder's Hall, the Weaver's
Workshop, and the Cistern all stood independently in open plains with
nothing connecting them, the same structureless-layout problem
Millhaven's own fourth pass diagnosed and fixed. This pass draws a main
street from the gate to a plaza anchored on the Cistern first, then
places both buildings against it (the Elder's Hall touching the plaza
directly, the Weaver's Workshop reached by a short connected branch),
and shrinks the footprint again, from 40x34 to 34x28 - the same
4-entity cast and 2 buildings, sized to what that cast actually
justifies rather than the round number the first regeneration picked.
Nothing else about the cast, dialogue, or named set pieces changed.

| Level | Name | Set pieces it holds |
|---|---|---|
| `level_01` | Grey Valley Monastery | The Elder, The Weaver, The Settlers, The Cistern |

## The named set pieces

### 1. The Elder

**`grey_valley_elder`** (new entity, `ai: villager`, `stationary: true`,
title only) - leads this community the same way every other Settler
town's Elder/Chief figure does. Positioned centrally, in a real one-room
hall now - the old monastery's own main hall, furnished plainly
(hearth, table, a shelf of what records this place still keeps, a
couple of chairs) - matching the "administrative-adjacent institution"
register `world_history.md` calls for. A cistern sits just outside the
door (see set piece 4).

*Questgiver*: gives the goblin-cull quest (see
`docs/dungeon_bibles/silver_mountain_caves.md` for the dungeon itself),
available only `available_after_year: 87`/`available_after_day: 67` -
three days after `spreading_the_warning`'s own deadline, once the
horde's dispersal has actually had time to reach this far. Before that
day, and regardless of whether Wayford stood or fell, the Elder has
nothing to offer yet - the crisis simply hasn't started. Folded directly
into this bible rather than its own quest-bible file, per Saltmarsh's own
established convention: a single quest with a single questgiver doesn't
warrant a separate arc document.

*Dialogue direction*: the Elder's default line is written to hold
steady whether spoken to before or after day 67 - concern about the
caves that reads as ongoing low-level worry rather than a specific,
dated crisis, so the transition into an actual quest offer never
contradicts what the player heard on an earlier visit.

*Why it's here*: gives the caves' new goblin problem (this same pass's
other half) somewhere to be reported and rewarded from, the same way
every other cull/kill/fetch quest in this game routes through exactly
one named questgiver.

### 2. The Weaver

A shopkeeper NPC, **`grey_valley_weaver`** (new entity, `ai: villager`,
`stationary: true`, `shop_inventory` set), tying directly into the
pitch's own silk detail - this is who actually turns hunted cave spiders
into the community's one real export. Has a real workshop now, distinct
from the Elder's hall - two chests (the silk itself, stored rather than
displayed) and a table doing duty as a workbench, a small barrel-and-
crate nook just outside standing in for hunting gear and goods rather
than farm produce (this settlement doesn't grow anything - see the
decoration note above).

*Dialogue direction*: practical and a little proud - silk is this
settlement's whole claim to being worth the trip out, and the Weaver
should sound like someone who knows it.

### 3. The Settlers

One to two plain `villager` spawns, ordinary texture rather than named
set pieces of their own - people going about the business of a small,
isolated community (mending, general upkeep of a building never built
to be lived in). Their job is to clear the 75% unique-dialogue floor
`content_design_process.md` §1 requires comfortably at this small a
roster (four talkable NPCs: the Elder, the Weaver, plus one or two
villagers, all with distinct lines), not to carry plot weight of their
own.

### 4. The Cistern

A `landmark` tile just outside the Elder's hall, using the `well`
`tile_sprite_override` (`data/sprites.yaml`) rather than the shared
generic landmark icon - the same mechanism and the same sprite Millhaven's
own well uses, reused rather than re-sourced, since a monastery's stone
cistern and a town's well are close enough in kind that inventing a
second icon for the same idea wouldn't buy anything.

*Landmark description*: *"A stone cistern, still catching what rain gets
through what's left of the roof - the one part of the old monastery
nobody had to rebuild."*

*Why it's here*: this settlement's own water source, and a small,
concrete way to make the "repurposed ruin" framing visible rather than
only stated - some of what's here was never rebuilt because it never
needed to be.

## Roster

Two new stationary `villager`-AI entities (`grey_valley_elder`,
`grey_valley_weaver` - both unique catalog ids, load-bearing the same way
every other named questgiver's/shopkeeper's id is). One to two plain
`villager` spawns, every one with its own per-spawn `dialogue`. No
`town_guard` - nothing about this settlement's pitch is defensive or
under direct threat; its problem is an economic cutoff, not an armed
one, and a deterrent here wouldn't fit the "isolated, self-sufficient"
mood any better than it would have fit Saltmarsh's.

## Tone notes for anyone (agent or human) revising this later

- No proper names - `Elder`/`Weaver`, matching every other named NPC's
  titles-only discipline.
- Isolated, not besieged. The crisis here is a cut-off resource, not an
  incoming threat to the settlement itself - nothing in this location's
  own flavor text should imply the goblins are coming *here* next.
- Keep the monastery's Old Kingdom origin mundane, per
  `world_history.md`'s own instruction - a repurposed institutional
  building, not a mystical ruin. Anything genuinely strange belongs to
  the Elder Age, not to this settlement's foundations.
- This bible deliberately doesn't add a discovery aid (a signpost, a
  road connection) pointing toward this location - it's meant to read as
  found by a player who went looking off the beaten path, per the
  pitch's own "hidden in the forested Grey Valley" framing. Don't
  undercut that by making it easy to stumble onto from the existing road
  network.
