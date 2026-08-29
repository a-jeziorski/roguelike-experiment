# The Sundered Realm: A History

This is the shared backstory every dungeon, town, and monster in this
project draws from. It is not simulated - there is no day-by-day
chronicle, no procedurally-generated succession of rulers - it is
*authored*, in the way a game bible is authored: enough structure that
independently-written content stays consistent with it, and vague enough
in the right places (especially the Elder Age) to leave room for what
hasn't been written yet.

Read this before authoring new content. Every new `dungeon.yaml`
`description` should be gettable from this document in one or two moves:
which era does this place belong to, and how does it relate to the
Sundering?

## Overview

The Sundered Realm was not always sundered. A kingdom once held the roads,
the towers, the mines, from the coast to the mountains - one authority,
one law, one set of guards standing watch over one set of prisoners. That
kingdom broke. What's left is the wreckage: garrisons nobody recalled,
manors abandoned mid-meal, roads that still run somewhere but no longer
run *to* anywhere in particular. People still live here. They just live
smaller than they used to.

## Eras

### 1. The Elder Age (deep past, mostly unknown)

Before the Kingdom, before the roads, something else was here. Nobody now
living knows what to call it - no name for it survives, so it's simply
"the Elder Age" the way you'd name a stratum of rock. Its handful of known
remains (the deepest halls under Forgotten Ruins; a standing monument
elsewhere on the map, see the Elder Cairn) don't resemble Kingdom
stonework at all: no mortar, no right angles insisted upon, a masonry
style that looks grown rather than built. Whatever built it is gone. What
it left behind isn't inert.

This era should stay vague in future content. It's the one thread in this
document meant to still be mysterious after the fact - don't over-explain
it in flavor text. A line like "older than anything with a name" does
more work than a paragraph of invented cosmology.

### 2. The Old Kingdom (the more recent, documented past)

A real, ordinary, administrative civilization: it built roads because
roads are useful, it built a prison because prisons are useful, it built a
manor's cellar without much curiosity about what was already under the
foundation. This is the era Prison Tower belongs to (a functioning
justice system implies a functioning state), the era that laid the road
network still visible on the overworld map today, and the era that built
on top of - not into - whatever the Elder Age left buried.

The Old Kingdom is the "normal" baseline every present-day ruin is a
departure from. When authoring a new Old Kingdom site, default to
*mundane* institutional purpose - a garrison, a waystation, a mine, a
tollhouse - rather than anything overtly magical. The magic (such as it
is) belongs to the Elder Age and to the Sundering, not to the Kingdom's
own architecture.

### 3. The Sundering (the cataclysm)

The specific, singular event that ends the Old Kingdom and starts the
present. The Kingdom, in its late and confident years, went looking for
whatever power the Elder Age had left underground - not out of malice,
more out of the ordinary institutional appetite that built the roads and
the prison in the first place. It found something it couldn't administer.
The result wasn't a single battle or a single villain: it was a
fracture - the Kingdom's regions cut off from each other, its authority
gone patchy and then gone, its garrisons and manors and mines left to
whoever or whatever was still standing in them when the lines of
communication went quiet.

Keep the Sundering itself off-screen. No dungeon should be "the site of
the Sundering" - it's a background event every present-day location is
downstream of, not a place you visit. Its fingerprints show up as: things
that used to be connected now aren't (the sea having crept into the
Drowned Waystation), things that used to have people now don't (Prison
Tower's absent chain of command), and the Elder Age's sites now behaving
like something disturbed rather than something merely old.

### 4. The Long Quiet (the present day)

Roughly a human lifetime-and-then-some after the Sundering. There is no
king, no capital, no messenger road that reliably reaches anywhere. What
there is: a few institutions still standing but gone feral (Prison
Tower - its garrison and prisoners left to sort out their own hierarchy
with nobody to answer to), Old Kingdom infrastructure squatted by whoever
got there first (a border watchtower now a bandit camp), and small,
deliberate pockets of ordinary life rebuilding on their own terms
(Millhaven, and the other present-day towns). This is the era of every new
town, and of any dungeon whose "monster" is really just people who moved
into a ruin (bandits, not undead).

## Key factions

- **The Old Kingdom's remnants.** Not a faction so much as a leftover
  shape - guards, wardens, and prisoners who kept doing their old jobs (or
  their old grudges) with no one left to report to. Prison Tower's roster.
- **The Elder Age.** Effectively extinct. What guards its sites now isn't
  a people, it's whatever was left running: constructs, not survivors. No
  dialogue, no motive beyond an old and simple instruction outlasting
  everyone who gave it.
- **Opportunists.** New this pass: people who didn't build the Kingdom's
  infrastructure but moved into the parts of it nobody was left to defend.
  Bandits holding a watchtower are this faction's clearest example -
  practical, not evil, just taking what an empty garrison offers.
  Human, hostile, but not otherworldly.
- **Settlers.** Present-day people choosing to rebuild something small and
  stable rather than scavenge or squat. Millhaven and the new towns. This
  is the *only* faction that ever gets a peaceful-by-default AI type
  (`villager`, who never fights back at all; `town_guard`, who will if
  provoked) - if a location's people are armed and hostile on sight,
  they're opportunists or Kingdom remnants instead, and they get a combat
  AI type from the start.

## Geography

The established "home region" - the mountain spine running roughly
northeast-to-southwest, the sea along the southern/eastern coast, the
single Old Kingdom road threading the mountain gap between Prison Tower
and the southern lowlands - stays exactly where it already is; this pass
grows the map outward from it rather than redrawing it. The expansion
adds: more coastline to the east (room for the Drowned Waystation and a
fishing hamlet to feel genuinely coastal, not just "near a pond"), a
second minor terrain feature - a drier hill/badlands stretch to the west,
distinct from the existing forest and mountain - giving the bandit
watchtower and its border town somewhere visually distinct to sit, and
more open plains/forest to the north for the crossroads town and the
Elder Cairn's isolation to read as real distance from anything else.

A third terrain feature, added alongside Windbreak Hold/The Windrest:
the Scoured Reach, a wide stretch of open plains in the map's
east-central expanse, farmed by the Old Kingdom and scoured down to
loose dune sand by a wind that's never fully settled since. Distinct
from the drier western hill/badlands (that's dry, stable ground; this is
actively shifting sand) - the map's first location built around an
environmental hazard tile (`dunes`, see
`docs/content_design_process.md` §0p) rather than a monster or a ruin.
The hazard is the ground itself, not a passing storm - a permanent
terrain condition, not weather.

A fourth expansion, connected north of the Heartlands cell rather than
grown outward within it (see `docs/content_design_process.md` §0b, the
overworld cell-grid): the Northern Steppe, the same plains/forest/
mountain climate as the Heartlands, extensively corrupted by the
Visitor's months-long presence (see `docs/main_story.md`) - the
homeland the goblin horde fled. See
`docs/region_bibles/northern_steppe.md` for the region's full design.
It now has its first real inhabited location - the Watch Post
(`northern_watch_post`, a small settlement of survivors who stayed
behind), reached via `word_from_the_north`/`a_warning_worth_carrying`
(`data/quests.yaml`) - three further locations (the goblin homeland, two
Elder Age sites) are still reserved as `landmark` tiles rather than
built.

## Current roster

As of the "Populating the Sundered Realm" pass, the Goblin Horde arc,
the Scoured Reach pass, and the Farrow's Stake pass, sixteen locations
are shipped. Each is placed here for quick cross-reference - see
`data/dungeons/<id>/dungeon.yaml` for its actual
`description`/`inspect_text`.

- **The Old Kingdom's remnants**: `prison_tower`.
- **The Elder Age**: `forgotten_ruins` (buried beneath an Old Kingdom
  manor), `elder_cairn` (a standalone site, unrelated to Forgotten Ruins -
  same era, no shared location).
- **Opportunists**: `broken_watch` (a fallen Old Kingdom garrison),
  `the_windrest` (a fallen Old Kingdom waystation, held for its shelter
  rather than any strategic value).
- **Fallen Old Kingdom infrastructure, present-day squatters**:
  `drowned_waystation` (flooded by the Sundering), `sunken_mine`
  (collapsed, reuses the existing monster roster rather than adding new
  ones).
- **Settlers**: `millhaven`, `wayford` (the largest, a crossroads hub),
  `stonebridge` (fortified, near `broken_watch`), `saltmarsh` (coastal,
  near `drowned_waystation`), `grey_valley_monastery` (settlers occupying
  the ruins of an Old Kingdom monastery, isolated in the forested Grey
  Valley, reliant on hunting the neighboring caves), `windbreak_hold` (a
  season-old camp on the Scoured Reach, sheltering behind a salvaged
  windbreak wall since the real shelter, `the_windrest`, is occupied),
  `farrows_stake` (a fledgling camp staking open plains south of the
  mountains, surveying a new trade spur off the road already proven safe
  to Millhaven).
- **Natural, no era or faction**: `silver_mountain_caves` (a cave system
  that predates the Kingdom entirely - never built, just always there.
  Home to its own wildlife, cave spiders that Grey Valley Monastery hunts
  for food and silk; presently also host to a goblin tribe that migrated
  in after the Goblin Horde broke apart near Wayford, cutting the
  settlers off from their hunting grounds), `sunless_hollow` (a natural,
  sunlight-starved depression south of the mountains, denned by wolves
  since long before Farrow's Stake existed to care - the map's first use
  of the `dark` level flag, see `docs/content_design_process.md` §0q).

New monster types introduced this pass, all in `data/entities.yaml`:
`bandit`/`bandit_captain` (Opportunists), `drowned_wretch` (Drowned
Waystation), `stone_sentinel` (the Elder Cairn's tank archetype - the
first monster whose defense rivals its attack).

## Authoring convention

When writing a new `dungeon.yaml`, its `description` should - in prose,
not a new field - make it placeable on this document:

- Which era is this? (Elder Age / Old Kingdom-now-fallen / a Long Quiet
  settlement)
- If it's a fallen Old Kingdom site: what was its original mundane
  purpose, and who or what is there *now* instead?
- If it's a Long Quiet settlement: what does it represent about people
  choosing to rebuild, as opposed to just surviving?

This is a discipline, not a mechanism - there's no schema field for "era,"
no lore-codex UI showing it to the player. It's what keeps independently
authored content (including anything a subagent writes without seeing the
others) reading as one history instead of unrelated set-pieces. See
`docs/content_design_process.md` for how this feeds into the actual
level-authoring checklist.
