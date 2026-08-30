# The Watch Post — Dungeon Bible

*A design document for one location, written the way a GM would key a
site for a tabletop session: what's actually here, why, and what the
player is meant to feel room to room. See `docs/world_history.md` and
`docs/main_story.md` for the realm-level facts this location has to
agree with, `docs/region_bibles/northern_steppe.md` for the region this
sits in (the Frayed Edge, its lightest-corrupted band), and
`docs/content_design_process.md` for the mechanical authoring rules -
§0d requires this document before any ASCII is drawn, no exception for a
small map.*

## The pitch

The region bible reserved this landmark's meaning but deliberately left
one question open: is anyone still here? Answer: yes, barely. When the
corruption started spreading and the goblin tribe further north broke
and ran, most of whoever kept this post went with them - the same flight
that eventually reached Wayford as a horde. One or two didn't go. Not
out of heroism - someone has to keep watching the road south, and
whoever's left here has made peace with that being their job now. This
is the Sundered Realm's whole "small, deliberate pockets of ordinary
life" pattern (`world_history.md`'s Long Quiet era) under real strain
for the first time: not a town rebuilding, a handful of people choosing
not to leave yet.

**Placement on the world bible**: pure Long Quiet, pure Settlers - same
footing as Millhaven or Farrow's Stake, just further along a much worse
timeline. No Elder Age content here (that's the Hollow Reach's job, not
the Frayed Edge's); no Visitor lore explained or named - nobody at this
post has ever seen it, they've only seen what it leaves behind. Keep
strictly to what a frightened, practical watcher would actually know:
the land north of here has gone wrong, things live in it now that
didn't before, and fewer people pass through every season.

**Why this quest is a dungeon-arrival, not a kill quest**: this is
deliberately the safest possible destination in the Northern Steppe -
the whole point of sending the player here first is to prove the region
can be approached and survived without a fight, before anything harder
is ever asked of them. No hostile entity anywhere in this level.

## Mood

Tired, not desperate - closer to Windbreak Hold's "barely holding on"
than Farrow's Stake's optimism, but without Windbreak's active threat.
Nobody here is under attack right now. They're just doing a job most of
their own people already decided wasn't worth the risk, and they know
it. The player should leave feeling like they've met someone who's
already made a harder call than the one being asked of the player today.

## Structure overview

One level, matching every other Settler outpost's precedent. Regenerated
at 26x16 (up from the original 20x11, which had the Sentry standing in
open plains with no shelter at all) so the Sentry gets a real structure -
the same `stationary: true` -> real-interior rule Millhaven's own
regeneration established. Kept deliberately small even at the larger
footprint: this is the sparsest of the four settlements this rule has
now been applied to, on purpose.

**The Sentry's shelter is a lean-to, not a house.** Three walls (west,
south, east) open on the north face, toward the entrance the player
arrives through - matching both `dungeon.yaml`'s own `inspect_text` ("A
lean-to roof, still standing") and the Sentry's own dialogue direction
("facing the entrance the player arrives through makes sense - they're
watching for exactly this"). Using the same wall-built-box technique
every other settlement's `house()` helper uses, just missing its fourth
wall - the right shape for someone keeping watch, not settling in.

**Decoration stays deliberately sparse, not composed like a living
town.** Millhaven, Grey Valley Monastery, and Saltmarsh all earn dense,
composed decoration because they're places people actively keep up; the
Watch Post's whole pitch is the opposite - most of its people are gone,
and nobody left has the numbers to spare for upkeep. What's here: a
fireplace and a bed under the lean-to (the one thing that's actually
maintained), a low picket line a few paces out marking the real watch
line, a collapsed structure (the same "purely decorative, no new
mechanics" `wall_block` technique every other pass uses, here reframed
as an abandoned building rather than a ruin nobody built) with a barrel
and crate sitting forgotten beside it, and a handful of `herb_clump`/
`bush` placements thin enough to read as wind-scoured ground that mostly
grows nothing, not a green space. No `tilled_soil`, no cemetery, no
treeline - nothing here calls for any of them, and a fuller composition
would undercut the "tired, barely holding on" mood this bible's own Mood
section asks for.

**Second regeneration, applying `content_design_process.md` §0af - at
the scale this settlement's own pitch calls for.** The first
regeneration gave the Sentry a real lean-to but connected it to nothing;
§0af's road-network-first rule still applies here, just not as a network
- a bustling set of branching streets would contradict the "fewer hands
than needed" pitch as badly as an oversized footprint would. What's here
instead: one single worn track from the gate straight to the lean-to,
the one path someone still keeps clear because it's the one thing that
still matters. No plaza, no branches - the absence of a fuller network
is itself in tone. Footprint unchanged at 26x16; it was already sized
correctly for a 3-entity cast and one small structure.

| Level | Name | Set pieces it holds |
|---|---|---|
| `level_01` | The Watch Post | The Sentry, The Ones Who Stayed |

## The named set pieces

### 1. The Sentry

**`watch_post_sentry`** (new entity, `ai: villager`, `stationary: true`,
title only, per this project's no-proper-names convention) - keeps the
actual watch this post is named for. Now has a real lean-to (see
Structure overview above) at the north-facing lookout point, fireplace
and bed the only furnishing - the one shelter still being maintained.

*Role*: carries `word_from_the_north`'s `target_visited_description`
weight (the player meeting them IS the proof of a completed recon,
mechanically recorded the instant this dungeon is entered - talking to
them isn't required to satisfy that quest, but it's the emotional
payoff of the trip). Also `a_warning_worth_carrying`'s questgiver -
asks the player to carry word to Millhaven specifically, closing the
loop the region bible's own "sends the player with their warning to
Millhaven" line promised.

*Dialogue direction*: plain and unromantic. Not "you must warn them of
the danger" - closer to "someone should tell Millhaven before they hear
it secondhand from whoever runs next." No mention of the Visitor by
name or nature; the Sentry has no idea what's actually up there, only
that fewer people come back from farther north than used to.

### 2. The Ones Who Stayed

Two plain `villager` spawns, each with their own per-spawn `dialogue` -
ordinary texture, clears the 75%-unique-dialogue floor comfortably (all
three NPCs distinct, same as Farrow's Stake's own cast). One should
gesture at *why* they stayed (nowhere better to go, or someone still
out there they're not leaving without); the other can carry a small
piece of concrete, ungrand detail about what changed (a trade route that
stopped, a season without a caravan) - matching the project's
"environmental storytelling, not narration" discipline.

## Roster

`watch_post_sentry` (unique catalog id) plus two plain `villager`
spawns with per-spawn dialogue. No `town_guard` - nothing here reads as
defended or defensible; that's not this location's premise. No hostile
entities at all.

## Terrain

Interior `wall`/`plains` dungeon geometry, matching `farrows_stake`'s
own template exactly - a small walled clearing, single `stairs_up` back
to the overworld (not `open_boundary`; this is a real, finished
destination to stand in and talk, not a fight to be able to flee).
`requires_stairs_down: false`.

## Explicitly out of scope

- No loot, no reward item from this dungeon itself - both quests reward
  XP only, matching `word_down_the_road`'s own reward-shape precedent
  for a "prove the road/prove it's safe" beat.
- No hostile roster, no `balance_reference_xp` - nothing here to
  balance-test (same reasoning `windbreak_hold`/`farrows_stake` already
  established for a pure settlement).
- No ruin content (`ruined_tile`/`ruined_description`) - nothing
  currently threatens this specific post the way Wayford or Stonebridge
  are threatened; revisit if a future pass gives the Frayed Edge its own
  escalating danger to this location specifically.
- No Elder Age or Visitor exposition - see the pitch above. This
  location's whole job is establishing that something is *wrong*, not
  explaining *what*.
