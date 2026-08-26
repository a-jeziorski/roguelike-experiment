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

| Level | Name | Set pieces it holds |
|---|---|---|
| `level_01` | Farrow's Stake | The Scout, The Survey Line |

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

### 2. The Survey Line

A plain villager positioned near a line of surveyor's stakes already
driven into the ground - physical evidence the route-planning is real,
not just talk. Ordinary texture, not a named set piece of its own;
exists mainly to help this small roster clear the 75% unique-dialogue
floor comfortably (three talkable NPCs: the Scout plus two villagers).

## Roster

One new stationary `villager`-AI entity (`farrows_scout`, unique catalog
id). Two plain `villager` spawns, each with its own per-spawn `dialogue`.
No `town_guard` - same reasoning as Windbreak Hold, nothing about this
location's premise is defensive.

## Tone notes for anyone (agent or human) revising this later

- No proper names - `Scout`, matching every other named NPC's
  titles-only discipline.
- Keep the mood optimistic, not desperate. If a line of flavor text
  reads like Windbreak Hold's "barely holding on" register, it's drifted
  into the wrong location's tone - this camp chose to be here, it isn't
  surviving despite itself.
- The wolves are wildlife with a den in the wrong place, not a menace
  with intent - same "practical obstacle" register the Sunless Hollow's
  own bible expands on.
