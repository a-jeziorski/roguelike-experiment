# Wayford — Dungeon Bible

*A design document for one location, written the way a GM would key a
site for a tabletop session: what's actually here, why, and what the
player is meant to feel room to room. See `docs/world_history.md` for
the realm-level facts this location has to agree with,
`docs/content_design_process.md` for the mechanical authoring rules, and
`docs/quest_bibles/wayford_arc.md` for the three questgivers this
regeneration exists to seat - this document is the specific story of
*this* place, decided before any ASCII is drawn, but it inherits its
cast list from that arc bible rather than inventing one independently.*

## The pitch

Wayford's own `dungeon.yaml` already says it: "a crossroads town where
three or four old Kingdom roads still meet, even if none of them lead
anywhere in particular anymore." This regeneration takes that "anymore"
personally. Where Millhaven proved a handful of people could just decide
to stay put and keep a green mowed, Wayford is the same project one
stage further along - large enough that staying put stopped being
enough, and someone started asking what the roads are actually *for*
again. That's not heroism, it's administration: a warden who wants the
road west safe, a clerk who wants to know where the roads still go, a
caravan master who wants proof the road to Millhaven still holds. Three
ordinary jobs, each one quietly trying to turn "a town at a crossroads"
back into "a town that *uses* its crossroads."

**Placement on the world bible**: pure Long Quiet, pure Settlers -
identical footing to Millhaven, just later-stage. No Old Kingdom ruin
under it, no faction tension at its own gate (that's still Stonebridge's
job, not Wayford's). The only thing this pass adds beyond Millhaven's
precedent is *outward-facing* ambition - Wayford is the one Settler town
whose people think about the rest of the map on purpose, because it's
the one town actually sitting where the map's old roads cross.

## Mood

Busier and more purposeful than Millhaven, not more anxious. Nobody in
Wayford itself is in danger - the tension this pass adds lives entirely
outside the walls (the road west, the silence from Millhaven's
direction), never inside them, same discipline Millhaven's own bible
insists on for itself. The difference from Millhaven is texture, not
threat level: people here have jobs with actual scope (records, trade
runs, a road to watch), not just chores.

## Structure overview

Still one level - Wayford doesn't need multiple floors to earn its
depth any more than Millhaven did, just room to hold four stationary
NPCs (three questgivers plus the Provisioner) in real buildings, on top
of the wandering cast. Resized larger than Millhaven's regenerated
44x46 footprint - Wayford's own `dungeon.yaml` calls it "the largest
settlement," and a bigger footprint than Millhaven's is what actually
makes that true instead of asserted. Same technique as Millhaven's
regeneration for the larger canvas: real building interiors only for
the entities whose premise depends on being findable in one specific
spot every time, decorative unentered wall clusters elsewhere so the
larger footprint reads as a real town's worth of houses and storehouses
(matching Wayford's own description) rather than a big empty field with
dots in it.

| Level | Name | Set pieces it holds |
|---|---|---|
| `level_01` | Wayford Crossing | The Crossroads, The Road Warden's Post, The Clerk's Record House, The Caravan Yard, The Provisioner, The Watch, two named villagers |

## The named set pieces

### 1. The Crossroads

The town's literal center and its whole reason for existing - a
`landmark` tile where the old roads visibly converge, not just implied
by the town's name. Everything else in this bible is arranged around
it, the same way Millhaven's Gate-watch set the tone by being the very
first thing a player reads.

*Landmark description*: something establishing that the roads are real,
physical, and going in more than one direction - the visual proof behind
the "three or four old Kingdom roads still meet" line already in
`dungeon.yaml`.

*Why it's first*: Millhaven's identity is a green; Wayford's identity is
the roads meeting on top of it. Leading with the crossroads instead of a
gate is the one structural difference that should make Wayford feel like
a genuinely different kind of town, not a bigger Millhaven.

### 2. The Road Warden's Post

Positioned toward the west road - the direction of Broken Watch and,
past it, Stonebridge - not centrally. This is a post with a specific
job, not a doorstep to stumble past.

*Questgiver*: `wayford_road_warden`, gives "Clearing the Watch Road"
(kill `bandit_captain`, per the arc bible). `stationary: true` - the
post is the point, same reasoning as Millhaven's chief/shopkeeper.

*Dialogue direction*: worried about the road specifically, not about
Wayford itself - raids, not fear of the town being reached. Practical
tone: this is a logistics problem to the Warden, not a crisis.

*Why it's here*: the arc's "security" facet made physical - watching the
one road that actually has a known threat on it right now.

### 3. The Clerk's Record House

Tucked near the crossroads but indoors, off to one side - a records
office, not a public square. This is the arc's "record-keeping" facet,
and record-keeping should read as *quiet* work, unlike the Warden's post.

*Questgiver*: `wayford_clerk`, gives "A Record Worth Keeping" (fetch
`road_ledger` from Broken Watch, per the arc bible). `stationary: true`.

*Dialogue direction*: dry, administrative, genuinely curious about
*where the roads go* rather than about Broken Watch or its people at
all - the Clerk cares about the ledger's contents, not the errand's
danger. Keep this the most "ordinary institutional appetite" NPC in the
town, echoing the Old Kingdom's own bureaucratic instinct
(`world_history.md`) now inherited by a Settler town on purpose.

*Why it's here*: the one NPC in Wayford whose motivation is explicitly
about *knowledge*, not safety or trade - rounds out the three facets so
they don't collapse into two.

### 4. The Caravan Yard

An actual working yard - space for a cart, not just another house.
Positioned where a road leading toward Millhaven's direction would
plausibly depart from town, distinct from the Road Warden's westward
post.

*Questgiver*: `wayford_caravan_master`, gives "Word Down the Road"
(arrive at `millhaven`, per the arc bible - no target inside Millhaven
itself). `stationary: true`.

*Dialogue direction*: forward-looking and mildly impatient - wants to
*resume* something (a run to Millhaven), not start something from
scratch. This is the arc's "contact" facet, and the only one of the
three where success is about reopening a connection rather than
removing or recovering something.

*Why it's here*: gives the yard itself a reason to exist as a distinct
place, not just another villager spawn - the location and the
questgiver justify each other.

### 5. The Provisioner

Wayford's shop - not part of the quest arc, but part of the same
"Wayford is Millhaven one stage further along" throughline. A real
storehouse, bigger than Millhaven's one-room shop, with a broader stock
to match - exact list decided at authoring time, but should read as
"an actual operation," not a bigger version of the same one item.

*Entity*: `wayford_provisioner`. `stationary: true`, `shop_inventory`
set to more than one item.

*Dialogue direction*: confident, established - this person has been
doing this a while and it shows, distinct from Millhaven's shopkeeper's
"rare enough these days that I don't ask where it came from" wariness
about coin's scarcity. Wayford's Provisioner should sound like coin
spending here is closer to normal than remarkable.

*Why it's here*: per the user's explicit ask for a shopkeeper with their
own inventory, and it's the natural size-appropriate payoff for "the
largest settlement" - more coin, more trade, a real stock.

### 6. The Watch

One or two `town_guard`-AI spawns (reusing the existing catalog entity -
see the Roster note on genericizing its description first), positioned
visibly along the roads near the Crossroads rather than tucked away -
same "a deterrent works by being seen" logic Millhaven's own Town Guard
set piece already established. Wayford being bigger and more trafficked
than Millhaven is the justification for more than one.

*Dialogue direction*: per-spawn override, distinct from Millhaven's
guard's line but landing the same mechanical point (attacking any
peaceful NPC here turns every guard on this map hostile, for the rest
of the visit).

### 7. The wandering villagers

**Correction after playtesting**: this bible originally said everyone
outside the six named/mechanical NPCs above could stay anonymous, on the
catalog's generic fallback line. That was wrong, and the user caught it
- with twelve anonymous villagers all sharing one repeated "they don't
have much to say," Wayford read as thinner than Millhaven despite being
the bigger town. `docs/content_design_process.md` §1 now states the
corrected rule: at least 75% of a settlement's villager/town_guard spawns
need their own per-spawn `dialogue` - a floor, not a per-town judgment
call, though not literally every single spawn either (the user felt the
original 100%-with-no-exceptions fix over-corrected). Wayford's own
roster still lands at 100% unique, comfortably clearing that floor - the
fix wasn't undone, just the *rule* was relaxed for whatever gets
authored next.

Matching Millhaven's technique, scaled to Wayford's larger cast: one
dismissive villager (mid-chore, plainly not interested), one nudge line
per questgiver (three total, one each toward the Road Warden, the Clerk,
and the Caravan Master - each still discoverable without the game ever
needing a quest marker), two lines carrying real world texture (a
Sundering-era aside about the crossroads' busier past, a plain
observation about the roads themselves), and the rest atmosphere and
personality - market bustle, a dry joke about the town's quiet season,
a plug for the Provisioner's stock, a couple of plainly unremarkable
greetings. All fourteen lines (twelve plain villagers plus the
dismissive and one nudge from this set piece) are distinct; none repeat
the catalog default.

## Roster

Four new stationary `villager`-AI entities (`wayford_road_warden`,
`wayford_clerk`, `wayford_caravan_master`, `wayford_provisioner`), each
with a **unique catalog id, never reusing any Millhaven id** - this
isn't just a naming preference, it's load-bearing: `entity_id` is the
global key `QuestLog.check_questgiver`/`check_delivery` match against,
not scoped per-dungeon, so reusing `"shopkeeper"` or `"village_chief"`
here would make talking to *Wayford's* NPC also grant or complete
*Millhaven's* quests. One or two reused `town_guard` spawns (safe to
reuse - no quest ever targets it by id) plus twelve plain `villager`
spawns, all fourteen (twelve villagers plus the two named-with-dialogue
spawns from set piece 7) given their own per-spawn `dialogue` - Wayford
comfortably clears the 75% floor `docs/content_design_process.md` §1
requires of a settlement's cast, though that floor no longer demands
literally every spawn.

**`town_guard`'s existing catalog `description`** ("Keeps the peace on
Millhaven's green, mostly by not needing to.") is Millhaven-specific
text on what's about to become a genuinely shared entity - needs a
one-line genericization (drop the place name) as part of this pass, so
look-mode reads correctly for both towns. Per-spawn `dialogue` can still
carry town-specific flavor without touching that shared default.

Three questgiver mechanics live on this roster, one per new NPC (see
`docs/quest_bibles/wayford_arc.md` for the full quest design - this
document only owns their placement and voice): a kill-quest questgiver
(`wayford_road_warden`), a fetch-quest questgiver (`wayford_clerk`), and
- for the first time in the game - a dungeon-arrival questgiver
(`wayford_caravan_master`). Plus the shop mechanic, on `wayford_provisioner`,
mechanically identical to Millhaven's shopkeeper but with its own
`shop_inventory` list - proof the shop system (refactored to be
per-entity content) actually supports a second, independently-stocked
shop, not just a second copy of the first one.

## Tone notes for anyone (agent or human) revising this later

- No proper names, same discipline as everywhere else in the project -
  titles only (Road Warden, Town Clerk, Caravan Master, Provisioner).
- Keep the tension entirely outside Wayford's own walls - on the road
  west, and in Millhaven's silence - never inside the town itself.
  Wayford should never need a reason to feel unsafe; that's still
  Stonebridge's job, not this town's, even though Stonebridge itself
  isn't touched by this pass.
- The three questgivers are colleagues doing adjacent jobs, not a chain
  of command - nobody here outranks anybody else, and none of the three
  quests should reference the other two directly. Their only real
  connection is that they're all facets of the same underlying ambition
  (see the pitch above), not a plot the player needs to piece together.
- Provisioner's confidence vs. Millhaven's shopkeeper's wariness about
  coin is a deliberate contrast, not an inconsistency - it's the same
  "further along" relationship the whole town has to Millhaven, made
  audible in one line each.
