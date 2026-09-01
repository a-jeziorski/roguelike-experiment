# The Drowned Waystation — Dungeon Bible

*A design document for one dungeon, written the way a GM would key a
site for a tabletop session: what's actually here, why, and what the
player is meant to feel room to room. See `docs/world_history.md` for
the realm-level facts this dungeon has to agree with and
`docs/content_design_process.md` for the mechanical authoring rules.
Written retroactively - this dungeon shipped in an earlier pass without
one - to give it the same grounding every other dungeon gets, plus one
light addition this pass makes: a second thing living in the flood.*

## The pitch

Per its own `dungeon.yaml`: an Old Kingdom road-station, built to shelter
travelers along the coastal messenger road - "nothing grand, nothing
magical, just a mundane waypoint doing a mundane job." The Sundering
didn't ruin it on purpose; the sea just came in where the road used to
run, and kept coming. Nobody defends this place and nobody squats in it
for its walls, the way Broken Watch's bandits do - there was no garrison
left to displace and nothing here worth moving in for. What's inside now
is what was already inside when the water rose, changed by however long
it's had to sit in standing water: **`drowned_wretch`**, whoever was
actually posted here, still going through motions that stopped meaning
anything a long time ago. Old Kingdom remnants, same category as Prison
Tower's roster, just wet instead of feral - people the institution left
behind, not monsters that moved in.

**Placement on the world bible**: Old Kingdom in origin, present-day
"fallen infrastructure, present-day squatters" per the world bible's own
roster line - except the squatter here isn't a person who chose this
place, it's what didn't leave when everyone who could have already had.
No Opportunist framing (nobody's "holding" this place on purpose) and no
Elder Age framing (nothing here predates the Kingdom) - purely a Sundering
scar on an otherwise mundane building.

## Mood

Waterlogged and abandoned-mid-routine, not haunted. The dread is
environmental before it's ever creature-based: `sea` tiles cut through
both levels as real obstacles, not backdrop, forcing the player to route
around standing water the same way `content_design_process.md`
identifies this dungeon's whole geometry gimmick ("sea tiles mixed into
dungeon rooms force route-around detours"). Everything here was left
exactly where it was the day the water won - a locked locker nobody came
back to unlock, paperwork nobody came back to file.

## Structure overview

Two levels, unchanged from the current shipped dungeon - a ground floor
giving way to a fully flooded cellar underneath it, the water getting
worse, not better, the deeper the player goes:

| Level | Name | Set pieces it holds |
|---|---|---|
| `level_01` | The Flooded Common Room | The Common Room, The Watch-Keeper's Locker |
| `level_02` | The Sunken Cellar | The Cellar Flood, The Silt-Choked Corner (new this pass) |

## The named set pieces

### 1. The Common Room (`level_01`)

The waystation's original public room - where a traveler would have
waited out a stop before continuing down the coastal road. Half of it is
still recognizable floor; the other half is now `sea`, matching
`dungeon.yaml`'s "half-flooded" description exactly. `drowned_wretch`
still occupies it, moving through whatever pattern being "posted here"
used to mean.

*Why it's first*: establishes the whole dungeon's central image - a
mundane room, doing a mundane job, now half-underwater - before the
player has to solve a single route-around puzzle.

### 2. The Watch-Keeper's Locker (`level_01`)

A locked door (`rusty_key`) guarding `leather_armor` - the waystation's
own gear locker, exactly the kind of reward-gate the balance methodology
calls for (off the critical path, guarding a bonus item, never blocking
progress). Whoever was posted here kept their own gear locked up out of
habit, same as any institution; nobody's come back for the key since.

### 3. The Cellar Flood (`level_02`)

Worse than upstairs, not better - the deeper level is the more flooded
one, a long channel of standing floor threading through a much larger
`sea` pool than `level_01`'s. `bone_plate` sits mid-channel, guarded by
a `drowned_wretch` right beside it; two more hold separate ground -
one in the side room past the flood with the `waystation_manifest`, one
on the dry southern corridor closer to the stairs down. Three on this
level alone, not the single "second" wretch an earlier draft of this
document implied - this is the dungeon's structural climax, and the
population reflects it: the most water, the most guarded crossing,
before the terminal stairs.

### 4. The Silt-Choked Corner (`level_02`, new this pass)

A second thing has moved into the flood since whatever originally
happened here - not a person, not Old Kingdom remnant, just something
formless that found standing water it liked. `gray_ooze` (from the
bestiary expansion in `data/entities.yaml` - "formless, patient, and
indifferent to the difference between stone and flesh") sits further
down the same floor channel as the Cellar Flood's `bone_plate`, past the
channel's own `drowned_wretch`. Placed here specifically because the flooded-crypt
aesthetic already fits it better than any other shipped dungeon - this
isn't Old Kingdom and isn't a person at all, just the water having sat
long enough for something else to claim a corner of it.

*Balance*: hp 16 / attack 4 / defense 1. Against player baseline (30/5/1)
it takes 4 hits to kill; unarmored, it deals 3/hit (survivable at full
health), and drops to 2/hit against a player who's already found
`level_01`'s `leather_armor` - correctly gated behind that reward without
requiring it.

A `waystation_manifest` (new item, pure flavor - no `ItemEffect` fields,
mirrors `road_ledger`/`pale_fungus`) sits in the same dry side-room as the
terminal stairs: old Kingdom shipping paperwork, water-damaged but
partly legible. Nothing in this dungeon currently needs it delivered
anywhere - it exists so a future quest (elsewhere) has a concrete object
to point at when it wants to reference this specific place.

## Roster and balance

| Monster | Where | Why here specifically |
|---|---|---|
| `drowned_wretch` (hp 11/atk 4/def 0, hostile_basic) | `level_01` x2, `level_02` x3 | The waystation's own leftover posting - Old Kingdom remnant, not an intruder. Deals 4/hit unarmored, dies in 3 hits - a straightforward fight, matching a place with no tactical intent behind it. |
| `gray_ooze` (hp 16/atk 4/def 1, hostile_basic) | `level_02` only | See set piece 4 - the one thing here that isn't a leftover person. |

## Tone notes for anyone (agent or human) revising this later

- `drowned_wretch` is a person the institution left behind, not a
  monster that moved in on purpose - keep any new flavor text in that
  register (routine, not menace) rather than drifting toward Broken
  Watch's deliberate-occupation framing or Prison Tower's still-believes-
  in-the-job framing. It doesn't believe in anything anymore; it just
  hasn't stopped.
- `gray_ooze` is the one exception to "everything here is a leftover
  person" - keep it wordless and motiveless in any flavor text, same
  restraint the world bible asks for around the Elder Age, even though
  this isn't Elder Age. It's not confused, angry, or guarding anything;
  it's just there.
- Don't invent a reason the sea "should" recede or a fix "in progress" -
  per `world_history.md`, the Sundering's damage stays permanent scenery,
  not a problem anyone in-world is working on.

## Decoration and content-variety pass

Before this pass, both levels were bare `floor`/`sea` with zero
decorations anywhere. One new `DecorationKind` was added, `kelp`
(`rltiles` name `kelp_frond`) - a dried kelp strand for floor near the
sea tiles, reinforcing "the water's been here a while" without a
bespoke flood-debris sprite. Three other candidates
(`green_mold`/`brown_mold`/`fungus`) were visually inspected and
rejected as too creature-like (blob/mushroom silhouettes, easily
mistaken for a monster at a glance); `coral` was rejected as too
vividly tropical for this dungeon's washed-out mood.

No new monster type - the roster stays exactly `drowned_wretch` +
`gray_ooze`. This dungeon's own tone notes are unusually explicit that
its entire population is "leftover people" plus one deliberate
exception, and a third creature type would blur that restraint rather
than serve it. In the same audit, `level_01`'s actual `drowned_wretch`
count turned out to be two, not the one the roster table previously
claimed - corrected above; the shipped level file was already right,
only the documentation was stale.

- **`level_01` (The Flooded Common Room)**: a `table`+`chair` near the
  entrance (what this room was actually for - a traveler's waiting
  spot), `kelp` at four points along the sea's edge, `rubble` further
  in, a `chest` and more `rubble` in the Watch-Keeper's Locker. Content:
  one `gold_pile` - a traveler's dropped coin, left exactly where it
  fell the day the water won, fitting "everything here is exactly where
  it was" better than looted treasure would (nobody's been back to take
  it).
- **`level_02` (The Sunken Cellar)**: `kelp` at six points along the
  flood channel's dry edges, a `chest` at the entrance and another by
  the `waystation_manifest`, `table`+`chair` in the dry side room,
  `rubble` in its corner. No item or roster changes - this level is
  already the dungeon's most populated and its structural climax; more
  content here would crowd a level whose whole design is "narrow dry
  ground, most of it taken by water."

The scratchpad's shared `render_millhaven.py` helper was also fixed
this pass: it previously gave every `tile`+`description` cell (a sea
pool, most commonly) its own unique legend symbol instead of reusing
one per identical spec, which ran the symbol pool dry on `level_02`'s
~80-cell flood before a single decoration could be added. It now reuses
a symbol for any extras entry without an `entity`/`item`/`door` key,
the same way it already reused symbols for decoration-only cells.

Verification: both levels re-validated via the real content loader
(entity/item/decoration/door/stairs/tile-description counts - 25 sea
descriptions on `level_01`, 82 on `level_02`, both preserved intact),
full `pytest -q` (1373 passed, no existing test asserted this dungeon's
exact counts), `tools/preview.py data/dungeons` full registry, `main.py`
smoke-launch, and a screenshot of each level via the scratchpad's
`screenshot_dungeon.py` harness.
