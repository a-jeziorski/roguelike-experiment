# The Northern Steppe — Region Bible

*A design document for one overworld region, written the same way a
dungeon bible keys one location - what's actually here, why, and what
the player is meant to feel crossing it - except scaled up to a whole
`data/overworld/cells/*.lvl` cell rather than one dungeon. See
`docs/world_history.md` for the realm-level facts this region has to
agree with, `docs/main_story.md` for the Visitor arc this region is the
first piece of, and `docs/content_design_process.md` §0b (overworld
cells) and §0p (environmental hazard tiles) for the mechanical rules
this document leans on. This is region bibles' first use - the
convention mirrors the per-dungeon bible discipline (decide the named
set pieces before any ASCII is drawn), adapted for something the size of
a whole cell rather than one building.*

## The pitch

The goblin horde that broke apart near Wayford came from somewhere. The
Northern Steppe is that somewhere - a stretch of open country connected
directly north of the Heartlands cell, sharing its climate and its
terrain vocabulary (plains, forest, mountain, road), because until
recently it *was* more Heartlands: the same kind of country, just far
enough from any of the map's present-day towns that nobody down south
ever had reason to go looking. What's different now is what's moved in.
The Visitor - see `docs/main_story.md` - has been here for months,
studying whatever drew it to this specific stretch of ground, and the
land is visibly, extensively dying around whatever it's doing.

This region ships with **no dungeons this pass** - it's overworld
content only, an answer to "what's north of the mountains, and why did
the goblins run." The three future dungeons this bible reserves space
for (a settler outpost, the goblins' abandoned homeland, and the Elder
Age site(s) that drew the Visitor here) are marked as `landmark` tiles,
not `dungeon_entrance` tiles - real content for a later pass, per the
user's explicit instruction. The player-facing quest hook that sends
someone here at all ("we will begin work on this hook shortly") is
likewise out of scope for this pass.

**Placement on the world bible**: the Northern Steppe isn't a new
faction or era - it's the *same* Heartlands climate and the *same*
Long Quiet present day, just further along the Visitor's own timeline.
Nothing here retcons `world_history.md`; it extends the map north the
way that document's own Geography section already anticipated ("more
open plains/forest to the north"), then applies the Visitor's corruption
on top of that otherwise-ordinary ground. The Elder Age sites reserved
here stay exactly as vague as the rest of that era - a landmark
description, nothing more, per the standing rule that the Elder Age is
meant to still be mysterious after the fact.

## Mood

Two things happening in the same space, in tension: this is still
recognizably *the same country* as the Heartlands - the same open
plains, the same patchy forest, a mountain spine that's clearly a
continuation of the one the player already knows - and it is being
actively, visibly ruined. The mood should read as loss, not horror.
Nothing here is a monster-movie wasteland; it's a place that was fine a
season ago and now isn't, which is a harder, sadder note to hit and the
one `docs/main_story.md`'s tone notes explicitly ask for ("every
region's devastation should read as a cost, not a spectacle"). The
corruption gets worse the further north the player goes, which should
feel like walking toward the source of a smell rather than crossing a
line into a different game.

## Structure overview

One overworld cell (`data/overworld/cells/northern_steppe.lvl`, 150x90,
stitched north of `heartlands.lvl` via `data/overworld/cells.lvl`'s 1x2
grid), divided into three corruption bands, south to north:

| Band | Rows (local y) | Corruption density | What's there |
|---|---|---|---|
| The Frayed Edge | 60-89 (nearest the Heartlands seam) | Light - a handful of small scars | The Watch Post (future settler outpost) |
| The Cinder Marches | 30-59 | Moderate - visibly spreading | The Goblin Camp (future goblin homeland) |
| The Hollow Reach | 0-29 (northernmost) | Heavy - the epicenter | Two Elder Age excavation sites |

The mountain spine along the west continues Heartlands' own
northeast-to-southwest range (per `world_history.md`'s Geography
section), thickening and curling further east as it goes north - the
same range, just more of it, the way a mountain range actually behaves
rather than stopping conveniently at a cell boundary. A single road
traces the goblins' flight path, from a point on the Heartlands seam up
into the Cinder Marches, ending at their abandoned camp - the route
survives even though nothing currently walks it in the other direction.

## The named set pieces

### 1. The Watch Post

A landmark (not yet a dungeon) in the Frayed Edge, near the road, close
enough to the Heartlands border that whoever kept this post could
plausibly still be alive to carry a warning south. **Reserved for**: a
settler town or similar outpost whose questgiver sends the player back
south with a fresh warning to Millhaven - the next link in the chain
`spreading_the_warning`/`a_wall_worth_holding` already built. Its
current landmark description ("a hastily-abandoned watch post... left in
a hurry, heading south") is deliberately ambiguous about whether anyone
is still there - that's a decision for whoever builds the real dungeon.

### 2. The Goblin Camp

A landmark in the Cinder Marches, at the road's northern end, sitting in
moderate corruption - abandoned, not besieged; the horde left before the
land here got as bad as the Hollow Reach. **Reserved for**: the goblins'
actual homeland, explaining *why* they fled south into the Heartlands in
the first place (encroaching corruption, not opportunistic raiding -
recontextualizing the already-shipped horde as refugees, per
`docs/main_story.md`'s reframing of the inciting incident). Placed
mid-region rather than at the epicenter on purpose: the goblins ran from
a *worsening* situation, they weren't living at the source of it.

### 3 & 4. The Elder Age Sites

Two landmarks deep in the Hollow Reach, spread apart rather than
adjacent - "some Elder Age sites," plural, per the user's brief, not one
site with two entrances. Both sit in near-total corruption and are
explicitly **not necessarily accessible yet** ("perhaps more time must
be spent on excavations," matching `docs/main_story.md`'s established
Visitor behavior of spending months studying one site before moving on).
Their descriptions stay in the same register as every other Elder Age
mention in this project - a shape too deliberate to be natural, evidence
of recent digging, nothing explained beyond that.

## Roster

The overworld cell itself still ships with zero entities, zero items,
and zero dungeon entrances - purely terrain, exactly as the schema
already permits (`load_overworld` only ever produces empty
`entity_spawns`/`item_spawns`/`doors`/`stairs` for every cell, cells or
no cells). Nothing is actually spawned anywhere in the Northern Steppe
yet.

The Visitor's creations - the monster roster this region's eventual
dungeons and any overworld encounters will draw on - are designed and
in `data/entities.yaml` (see the "The Visitor's creations" block at the
end of that file, and `docs/content_design_process.md` §2 for the
hits-to-kill math they were checked against), same "define now, place
later" discipline the rest of the bestiary follows. Six entities across
three tiers matching this bible's corruption bands:

| Tier / Band | Entity | Role |
|---|---|---|
| Frayed Edge (challenging) | `ash_bound_husk` | Crude melee, dangerous in packs (`pack_hunter`) |
| Frayed Edge (challenging) | `bound_eye` | Ranged support, dies fast once reached |
| Cinder Marches (very dangerous) | `stitched_vanguard` | Melee, self-repairing (`regenerator`) |
| Cinder Marches (very dangerous) | `hollow_chanter` | Ranged, saps the player's own attack (`weaken`) |
| Hollow Reach (extremely dangerous) | `charnel_colossus` | Common patrol, burst damage, worse enraged below 30% hp |
| Hollow Reach (extremely dangerous) | `excavation_warden` | Reserved specifically for the Elder Age sites - the highest defense in the game and a stun on every landed hit; a long, attritional, genuinely-meant-to-deter-you fight |

`excavation_warden` is the mechanical answer to "perhaps more time must
be spent on excavations" above - it isn't just narration that the sites
aren't accessible yet, it's a specific, very hard guardian standing at
each one.

## Mechanical notes

- **Corrupted terrain**: two new `TileType` values, `ashen_plains`
  (replaces `plains`) and `blighted_forest` (replaces `forest`), both
  reusing the exact same chip-damage hazard mechanic as `dunes` (see
  `docs/content_design_process.md` §0p) - same `ENVIRONMENTAL_HAZARD_DAMAGE`,
  different flavor text. `blighted_forest` additionally blocks
  line-of-sight like ordinary `forest` does (dead trees still stand in
  the way); `ashen_plains` stays walkable/transparent like `dunes`.
- **Not a uniform hazard field**: per the "narrow enough to cross in one
  push" discipline the Scoured Reach already established, the corruption
  is authored as organic patches (denser heading north) rather than
  painting the whole region hazardous - a player can thread a path
  through the Frayed Edge and most of the Cinder Marches without ever
  standing on a hazard tile if they're careful, and should expect real
  chip damage crossing deep into the Hollow Reach.
- **Not a "region corruption swap" mechanic**: `docs/main_story.md`
  flags a still-undecided future mechanic where an existing region's
  terrain bulk-transforms when the Visitor arrives or leaves. This
  region does not build that - it's hand-authored as a single static
  snapshot of already-corrupted land, since the premise is that the
  player arrives after the Visitor has already been here for months.
  That open design question is unaffected by this pass either way.
- **No player_start, no dungeon_entrance tiles**: validated by the
  overworld's whole-world checks (exactly one player_start and at least
  one dungeon_entrance across *all* cells combined) - Heartlands still
  supplies both, so this cell can safely have zero of either.

## Tone notes for anyone (agent or human) revising this later

- Corruption reads as a wound, not a biome. Avoid language that makes it
  sound exotic or cool ("eldritch," "otherworldly blight") - the Visitor
  is a scholar doing damage as a side effect, not a demon lord marking
  its territory, per `docs/main_story.md`'s explicit "not cartoonishly
  evil" note.
- Keep the Elder Age sites' descriptions as unexplained as every other
  Elder Age mention in this project. The player should be able to deny
  the Visitor this place, not learn what it actually is.
- If a future pass builds the real dungeons here, the corruption bands'
  boundaries (the row ranges above) are guidance, not a hard fence -
  shift a landmark a few tiles to fit real geometry rather than treating
  this document's numbers as load-bearing.
