# The Elder Cairn — Dungeon Bible

*A design document for one dungeon, written the way a GM would key a
site for a tabletop session: what's actually here, why, and what the
player is meant to feel room to room. See `docs/world_history.md` for
the realm-level facts this dungeon has to agree with, and
`docs/content_design_process.md` for the mechanical authoring rules
(balance math, geometry variety, the three story surfaces). This
document is the missing middle layer between those two - the specific
story of *this* place, decided before any ASCII is drawn.*

`elder_cairn` shipped in an earlier pass with no bible of its own. This
document is that missing round of proper generation, written against
the dungeon exactly as it already exists (two levels, symmetric
radial geometry, `stone_sentinel` already in place twice) rather than
as a redesign - it names what's already there and adds one new set
piece, the Wraith's Deep Antechamber, rather than reworking anything
that shipped before.

## The pitch

The Elder Cairn is not a ruin. A ruin implies something failed - a roof
gave way, an office stopped sending inspectors, a garrison's chain of
command went quiet. Nothing here failed. The Cairn is doing exactly
what it has always done, uninterrupted by the Sundering or anything
before it, because whatever set it doing that didn't need a Kingdom, or
people, or continuity of any kind to keep doing it. That is the entire
horror of the place, and the entire mood: not decay, but an unbroken
watch nobody currently living gave the order for and nobody currently
living can call off.

**Placement on the world bible**: Elder Age, full stop - a standalone
site, explicitly *not* connected to Forgotten Ruins ("same era, no
shared location" per `world_history.md`'s roster). No Old Kingdom
involvement, no Sundering fingerprint, no human institution ever ran
this place or built on top of it. Per the bible's own instruction that
the Elder Age "should stay vague in future content" and that "older
than anything with a name" does more work than invented cosmology:
**nothing in this document explains what the Cairn is, what built it,
or what the wraith actually guards.** Every set piece below is written
to describe what's physically present and how it reads, never to
answer those questions. If a future revision is tempted to add a name,
a purpose, or an origin to any of this - that instinct belongs to a
different dungeon, not this one.

## Mood

Not dread exactly - dread implies something might happen. Here,
something already *is* happening, continuously, and has been since
before anyone could have written it down. The stonework confirms it on
sight: no mortar, no right angle, nothing that reads as *built* the way
a Kingdom wall is built. Grown, or something adjacent to grown. Every
named set piece below should make the player feel like a very late,
very brief interruption to a process that started long before them and
will continue long after, not like an intruder in someone's home.

## Structure overview

Two levels, unchanged in count from the current shipped dungeon - this
bible keeps the existing shape (a radial "approach" level, then a
symmetric "heart" level) and names what's in each rather than
restructuring either:

| Level | Name | Set pieces it holds |
|---|---|---|
| `level_01` | The Silent Approach | The Radial Approach, The Fallen Travelers' Gear |
| `level_02` | The Heart of the Cairn | The Twin Watch, The Heart Chamber, The Deep Antechamber |

## The named set pieces

### 1. The Radial Approach (`level_01`)

The Cairn's interior unfolds as a symmetric ring around a single central
chamber - four short arms meeting at a hub, the hub holding the way
down. There's no front door in any ordinary sense (per `dungeon.yaml`'s
own `inspect_text`: "no door that you can see - only an opening where
the stone simply stopped") and no corridor inside reads as a hallway
built to connect rooms a person needed to walk between. It reads as
architecture that radiates from a center, the way a growth pattern
would, not architecture laid out to a floor plan.

*Why it's first*: this is the dungeon's thesis statement, shown before
it's told, same discipline `sunken_mine.md` used for its Weighhouse -
except here the lesson is "nothing about this was built by hands you'd
recognize," not "here's what stopped." A `stone_sentinel` stands at the
hub, between the approach and the stairs down: the first proof the
place is still doing something, not just old.

### 2. The Fallen Travelers' Gear (`level_01`)

Scattered at the compass points of the outer ring: a sword, a stitch of
armor, a stoppered potion. None of it belongs to the Cairn or to
whatever the Cairn belongs to - it's ordinary traveler's gear, the kind
someone in the Long Quiet would carry on any dangerous road. Nobody
explains why it's here instead of with whoever carried it. Nobody
needs to.

*Why it's here, and why it stays unexplained*: this is deliberately the
one place this bible could have written a story - who they were, how
far they got, what found them - and doesn't. Leaving it silent is the
correct choice for this specific dungeon: an explained tragedy is
`sunken_mine`'s register (administrative, procedural, legible), and a
solved mystery is the wrong shape for a site the world bible insists
stay mysterious. The gear is real and usable - it's exactly the
equipment the player needs to survive the rest of the Cairn - but the
fiction never confirms it was left behind on purpose, by choice, or
by anyone who walked back out.

### 3. The Twin Watch (`level_02`)

Two `stone_sentinel`s, posted symmetrically at opposite ends of a single
long corridor, each guarding a shallow alcove: one holds a heavier suit
of armor, the other a healing draught. Neither watches the other -
each faces its own alcove, the same unhurried, patient posture the
species already carries in its catalog description ("posted... since
before anyone kept records. Slow. Patient. Still on duty"). The
symmetry is the point: this is not two individual guards with two
individual stories, it's one instruction, carried out twice, at both
ends of the same hall, exactly as precisely as the first time.

*Why it's here*: confirms the Cairn's watch isn't a single sentry that
happened to be posted at the entrance - it's systemic, repeated,
built into the place's shape at more than one point. Fighting through
both (or drawing them out one at a time down the long corridor between
them, which the geometry deliberately allows) is meant to feel like
proving the pattern, not like clearing two unrelated rooms.

### 4. The Heart Chamber (`level_02`)

Between the Twin Watch and the way deeper: a wide, bare, symmetric room
- the level's namesake. Nothing is staged here on purpose. After the
paired sentinels on one side and the Deep Antechamber on the other,
this room is a deliberate breath: confirmation that the Cairn's
symmetry holds even where nothing is currently defending it, and a
chance to use whatever was just won from the Twin Watch's alcoves
before what's next.

*Why an empty room is the right choice here*: per
`content_design_process.md`'s geometry-variety guidance, a single open
room is a legitimate, occasional "arena" beat rather than the default
template - this is that beat, used once, deliberately, in a dungeon
that otherwise favors radial arms and a flanked corridor. Staging
another fight here would make the Cairn read as wall-to-wall combat
instead of an occasional, patient watch.

### 5. The Deep Antechamber (`level_02`, new this pass)

A tighter, lower side-chamber the main ascent passes directly through,
between the Heart Chamber and the passage back up to the grey light.
Standing in it: `wraith` (`sleeping_guard`, alert radius 4) - a second
guardian, unrelated in *kind* to the stone sentinels but identical in
*character*: no motive on display, no dialogue, nothing that reads as a
creature so much as a standing instruction that happens to move. Its
own catalog description was written for exactly this placement: "a
shape the light won't quite settle on, guarding something that
predates whatever built the walls around it." Past it, deeper into the
antechamber, sits a single small stone set into the floor - smaller
than anything else in the Cairn, matching none of the masonry around
it, colder than the air. What it is, why it's there, and why something
is still watching it are not answered by this document, on purpose.

*Why it's here, structurally*: `stone_sentinel` is the Cairn's outer
watch - posted at the threshold (level_01's hub) and along the main
hall (level_02's Twin Watch). The wraith is something else again: not
posted at an entrance or a crossing, but wrapped directly around the
one object in the whole dungeon that isn't cairn-stone at all. It reads
as older and more specific than the sentinels precisely because it
isn't doing the sentinels' job (watching an approach) - it's doing a
narrower one (watching a single thing). Placing it last, past both the
first sentinel and the Twin Watch, and just before the only way out,
means a player who's made it this far has already been tested twice by
the time they meet it - this should read as the dungeon's second and
final guardian type, not a random encounter along the way.

*Why `sleeping_guard`, specifically*: unlike the sentinels (`hostile_basic`
- they simply are what they're posted to be, no ambiguity, no chance
to avoid them), the wraith gives the player a moment of agency the rest
of the Cairn doesn't: it doesn't move until approached within 4 tiles,
which means a player who arrives under-equipped can see it, back off,
and use whatever's left in inventory (a potion from the Fallen
Travelers' Gear, or from the Twin Watch's alcove) before committing,
rather than being forced into a fight the instant they round a corner.

## Roster and balance

Per the standaloneness of this site and the "no new monsters unless
they specifically fit" instinct already applied elsewhere in this
project, this pass adds exactly one new monster - `wraith`, pulled from
`data/entities.yaml`'s bestiary expansion specifically because its
existing catalog description was written as an almost-literal fit for
this dungeon. `stone_sentinel`'s two placements (level_01's hub, the
Twin Watch) are unchanged from what already shipped; documented here
for the first time rather than re-derived.

| Monster | hp/atk/def | AI | Where | Why here specifically |
|---|---|---|---|---|
| `stone_sentinel` | 30/5/3 | `hostile_basic` | `level_01` hub; `level_02` Twin Watch (x2) | The Cairn's outer, systemic watch - see set pieces 1 and 3. |
| `wraith` | 20/6/2 | `sleeping_guard`, alert radius 4 | `level_02` Deep Antechamber | The Cairn's second, narrower guardian - see set piece 5. |

**Hits-to-kill against player baseline (30 hp / 5 atk / 1 def), unchanged
math for `stone_sentinel`**: player deals `5-3=2`/hit (15 hits to kill);
sentinel deals `5-1=4`/hit (8 hits to kill the player). The hardest
single fight in `level_01` and, doubled, the backbone of the Twin
Watch's difficulty - already balanced as shipped, no changes this pass.

**Hits-to-kill for `wraith`, worked in both directions against plausible
gear at this point in the dungeon** (the player has had two chances to
gear up by the time they reach the Deep Antechamber: the Fallen
Travelers' Gear in `level_01` - `iron_sword` +4 attack, `leather_armor`
+1 defense, a `healing_potion` - and the Twin Watch's alcoves in
`level_02` - `bone_plate` +3 defense, a second `healing_potion`):

| Player gear | Player effective atk/def | Player dmg/hit -> hits to kill wraith | Wraith dmg/hit -> hits to kill player |
|---|---|---|---|
| None (base 5/1) | 5 / 1 | `5-2=3` -> 7 hits | `6-1=5` -> 6 hits |
| `iron_sword` + `leather_armor` | 9 / 2 | `9-2=7` -> 3 hits | `6-2=4` -> 8 hits |
| `iron_sword` + `bone_plate` | 9 / 4 | `9-2=7` -> 3 hits | `6-4=2` -> 15 hits |

A player who skipped every item in both levels (an unlikely but
possible worst case, given they'd have already fought a `stone_sentinel`
bare-handed twice to get this far) faces a genuinely dangerous,
close-run fight - 7 hits needed against 6 to lose, which is exactly why
`sleeping_guard` and its 4-tile alert radius are load-bearing here, not
cosmetic: that player can see the wraith before it sees them and choose
not to close the distance. Any player who picked up even one of the two
armor pieces on offer turns this into a safe, one-sided fight (8-15
hits before the wraith could kill them, versus 3 to kill it) - the
wraith is tuned to punish skipping gear, not to punish playing the
dungeon as designed.

## Tone notes for anyone (agent or human) revising this later

- **Never explain the Cairn.** Not what it is, not what built it, not
  what the wraith's stone actually does. Every other dungeon in this
  project earns its mood by explaining something (`sunken_mine`'s
  bureaucratic neglect, `broken_watch`'s opportunist squatters) - this
  one earns its mood by refusing to. If a revision adds a name, an
  origin, or a mechanism to anything here, it has drifted into
  Forgotten Ruins' register or invented new cosmology outright, either
  of which is wrong for this specific site.
- **No proper names, same discipline as everywhere else in this
  project** - the sentinels and the wraith are never individuals, only
  instances of "whatever's still doing its job."
- **Don't give the Cairn a connection to Forgotten Ruins.** Both are
  Elder Age; neither shares a location, a builder, or an explanation
  with the other, per `world_history.md`'s roster note. A future pass
  linking them by lore would contradict the world bible as written.
- Keep the Fallen Travelers' Gear exactly that - found, not given, not
  explained. If a future revision is tempted to add a note, a name tag,
  or any other object that explains who carried it, that's a different
  dungeon's tone.
