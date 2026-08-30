# Farrow's Stake — Dungeon Bible

*A design document for one location, written the way a GM would key a
site for a tabletop session: what's actually here, why, and what the
player is meant to feel room to room. See `docs/world_history.md` for
the realm-level facts this location has to agree with and
`docs/content_design_process.md` for the mechanical authoring rules -
in particular §0q, the new `dark` level flag this location's neighboring
dungeon (`sunless_hollow`) exists to use.*

## The pitch

`word_down_the_road` already proved something worth building on: the
road between Wayford and Millhaven still holds, safe enough that a
Caravan Master who hadn't sent a cart out in years finally did. Farrow's
Stake is that proof taken one step further - a small band of Settlers
staking a claim on a stretch of open plains south of the mountains,
aiming to open a *new* spur off the proven road rather than just walk
the old one. Good, empty land, the kind every existing Settler town
would want more of. The one thing standing in the way: a wolf pack has
denned in a natural hollow directly along the surveyed route, and
nothing carrying trade goods gets past a den nobody's cleared.

This isn't a monastery-scale crisis or a storm-scoured wasteland - it's
the small, practical problem every genuine expansion runs into. The
stakes are lower than the Goblin Horde's aftermath or the Scoured
Reach's whole reason for being empty, and that's fine: not every new
location needs to be the biggest thing on the map.

**Placement on the world bible**: pure Long Quiet, pure Settlers, same
footing as every other present-day town - no ruin under it, no faction
of its own. Its neighbor, the Sunless Hollow, is natural rather than
built (see that dungeon's own bible) - wolves denning in a hollow needs
no Old-Kingdom-origin explanation the way a fallen garrison or waystation
would.

## Mood

Ambitious and unhurried at once - these are people testing an idea, not
fleeing a crisis. Compare directly against Windbreak Hold's "barely
holding on" register: Farrow's Stake isn't desperate, it's optimistic in
a measured way, the same tone `word_down_the_road`'s own resolution
already earned. The wolves are an obstacle to clear, not a threat
closing in on the camp itself.

## Structure overview

One level, matching every other Settler town's precedent.

**The Captain folds in, Windbreak Hold retires.** Windbreak Hold and
Farrow's Stake were both a single stationary questgiver plus two plain
villagers, with no `content_design_process.md` §0af treatment yet -
genuinely thin on their own. Rather than apply the road-network/
decoration pass to both separately, the two are consolidated: the
Captain (`windbreak_captain`, previously Windbreak Hold's own
questgiver) and their `reclaiming_the_windrest` quest move here, and
`windbreak_hold` retires as a dungeon-registry id entirely - its
overworld entrance reverts to the dunes that surround it, its own two
villagers (whose dialogue was specifically about wind and storms) don't
carry over, and its bible is deleted rather than archived. **This is a
deliberate, accepted loss, not an oversight**: Windbreak Hold's own
bible was the sole justification for the `dunes` hazard tile and
explicitly contrasted its "barely holding on" mood against this
settlement's "optimistic, unhurried" one - see its own tone notes for
what that contrast was protecting. The narrative bridge: the Captain's
people couldn't hold that ground alone and joined this camp's expansion
instead; the Captain personally hasn't let go of the debt at the
Windrest (see set piece 2 below and `data/quests.yaml`'s
`reclaiming_the_windrest`, rewritten this pass to drop every reference
to a home camp that no longer exists).

**First §0af pass otherwise**: a small road network (gate to a hub at
the surveyor's table, branches to both shelters), both stationary NPCs
get real, modest shelters ("new-built," per this settlement's own
`inspect_text` - not permanent halls), the surveyor's table itself
becomes a real `landmark` instead of just a line of flavor text, and the
"stakes already driven in a line running south" become an actual line
of `fence` decorations. Small footprint on purpose - 28x22, the
smallest of any settlement redone so far bar the Watch Post - this is a
fresh camp, not a padded canvas.

| Level | Name | Set pieces it holds |
|---|---|---|
| `level_01` | Farrow's Stake | The Scout, The Captain, The Survey Line |

## The named set pieces

### 1. The Scout

**`farrows_scout`** (new entity, `ai: villager`, `stationary: true`,
title only) - the one who actually walked the surveyed route and found
the den blocking it. Not an Elder or a Captain - a working title fitting
a camp this new, positioned near whatever passes for a planning table
(a map weighted down with stones, say).

*Questgiver*: gives `clearing_the_sunless_hollow` (`target_cull_entity_id:
wolf`, no preserve target - there's nothing else denned there worth
protecting, unlike Silversilk Caves) - a population clear, not a single
named kill. Deliberately a different trigger shape than Windbreak Hold's
kill-the-leader quest (already reused there from Broken Watch) - a wolf
pack has no single leader worth singling out narratively, and cull
already exists as a proven mechanism (§0o) rather than needing a new
one. No deadline - the spur isn't going anywhere, and nobody's
threatening the Stake itself.

*Dialogue direction*: practical and forward-looking - "good land doesn't
clear itself" is the right register, not fear or urgency.

### 2. The Captain

**`windbreak_captain`** (existing entity, `ai: villager`,
`stationary: true`, title only - "Captain," unchanged, matching
Windbreak Hold's own titles-only convention) - folded in from the now-
retired Windbreak Hold (see Structure overview above). Has a modest
shelter of their own here, matching this camp's "new-built" register,
not a rebuild of Windbreak Hold's own cruder, wind-battered one.

*Questgiver*: still gives `reclaiming_the_windrest` (kill
`windrest_captain` at `the_windrest`, then report back) - mechanically
untouched by the move, only its text was rewritten to drop every
reference to a home camp that no longer exists. No deadline, unchanged.

*Dialogue direction*: their existing per-spawn line ("The Windrest still
stands - real walls, a real roof...") never named Windbreak Hold and
needed no rewrite - it reads exactly the same here. New content written
for this move (the quest text itself) should sound like someone who's
found steadier footing, not someone still barely holding on - the
Captain settling an old debt from a position of relative stability, not
carrying Windbreak Hold's desperation into this camp's own register.

*Why it's here*: the fold-in's entire point - one settlement with two
real questgivers instead of two thin ones with one apiece.

### 3. The Survey Line

A plain villager positioned near a line of surveyor's stakes already
driven into the ground - physical evidence the route-planning is real,
not just talk, now a literal line of `fence` decorations running south
from the surveyor's table (see Structure overview). Ordinary texture,
not a named set piece of its own; exists mainly to help this small
roster clear the 75% unique-dialogue floor comfortably (four talkable
NPCs: the Scout, the Captain, plus two villagers - still 100% unique).

## Roster

Two stationary `villager`-AI entities: `farrows_scout` (unique catalog
id, original to this settlement) and `windbreak_captain` (unique
catalog id, folded in from the now-retired Windbreak Hold - see
Structure overview). Two plain `villager` spawns, each with its own
per-spawn `dialogue`. No `town_guard` - nothing about this location's
premise is defensive, same as every other unguarded Settler outpost in
the game.

## Tone notes for anyone (agent or human) revising this later

- No proper names - `Scout`/`Captain`, matching every other named NPC's
  titles-only discipline.
- Keep the mood optimistic, not desperate - including in how the
  Captain reads here. Their old home's "barely holding on" register
  doesn't belong in this camp; write them as someone who found steadier
  footing by joining a settlement that's actually working, not someone
  who dragged their old desperation along with them. If a line of new
  flavor text reads uncertain or exhausted, it's drifted into the wrong
  location's tone - this camp chose to be here, it isn't surviving
  despite itself.
- The wolves are wildlife with a den in the wrong place, not a menace
  with intent - same "practical obstacle" register the Sunless Hollow's
  own bible expands on.
