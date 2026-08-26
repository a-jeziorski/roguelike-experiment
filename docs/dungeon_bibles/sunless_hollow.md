# The Sunless Hollow — Dungeon Bible

*A design document for one dungeon, written the way a GM would key a
site for a tabletop session: what's actually here, why, and what the
player is meant to feel room to room. See `docs/world_history.md` for
the realm-level facts this dungeon has to agree with,
`docs/content_design_process.md` §0q (the new `dark` level flag this
dungeon exists to use), and `docs/dungeon_bibles/farrows_stake.md` for
the settlement whose cull quest targets this dungeon's wolves.*

## The pitch

Not every dangerous place has a history. The Sunless Hollow is exactly
what its name says: a natural depression deep enough and steep-walled
enough that direct sunlight never really reaches its floor, no ruin
underneath it, nothing the Old Kingdom ever built here, nothing the
Sundering did to it. It was always like this. A wolf pack denned in it
long before Farrow's Stake existed to care, and would go on denning in
it indefinitely if the surveyed spur route didn't happen to run straight
past the entrance. This is the smallest kind of conflict in the game so
far: not a crisis, not an occupation, just a den in the wrong place at
the wrong time for somebody else's plans.

**Placement on the world bible**: no era, no faction - natural, the same
category `silver_mountain_caves.md` already established for a location
that predates the Kingdom entirely and needs no institutional backstory.
Unlike Silversilk Caves, there's no resource here worth protecting and
no second species in the balance - just wolves, denning where wolves
would.

## Mood

Close and disorienting rather than dreadful. The darkness (`dark: true`,
see below) should read as ordinary physical fact - a hollow steep enough
that light doesn't reach its floor - not as anything uncanny. The tension
is entirely practical: something could already be closer than it looks.

## Structure overview

One level - a single den, not a sprawling warren. Matches Farrow's
Stake's own modest, practical-obstacle framing rather than treating this
as a major dungeon in its own right.

| Level | Name | Set pieces it holds |
|---|---|---|
| `level_01` | The Sunless Hollow | The Hollow's Rim, The Den |

## The named set pieces

### 1. The Hollow's Rim

The entrance - where the ground actually drops away into the depression,
the last point normal daylight reaches before the level's `dark: true`
flag takes over. A single, brief line of flavor text marking that
transition is worth more here than any elaborate description: the
player should understand *why* their vision just shrank without needing
a mechanic explained to them.

*Why it's first*: the dungeon's whole thesis in one threshold - the same
job Windbreak Hold's Windbreak Wall does for its own hazard, just at the
opposite end (entering danger, not escaping it).

### 2. The Den

The hollow's floor and walls, natural rather than built - packed earth,
old bones, claw-worn hollows in the dirt where wolves have bedded down
across who knows how many seasons. This is the dungeon's entire
population center; every wolf lives here, no separate "boss" chamber the
way Broken Watch or the Windrest builds toward one. Clearing this level
*is* the quest - `clearing_the_sunless_hollow`'s cull target
(`target_cull_entity_id: wolf`) needs every wolf here dead, not one
named leader.

*Why no climactic final room*: a wolf pack has no hierarchy worth
staging a final confrontation around - the correct shape here is
"clear the den," flat and total, not "fight your way to the one that
matters." Matches the cull trigger's own population-check design (§0o)
better than a single-target kill would have.

## Roster and balance (one existing, previously unplaced monster)

`wolf` (hp 14/atk 5/def 1, `hostile_basic`, xp 5) - already in
`data/entities.yaml`, not yet placed in any level before this pass. No
new monster type, no stat changes.

| Monster | Where | Why here specifically |
|---|---|---|
| `wolf` | Throughout The Den | The pack itself - straightforward `hostile_basic` fights, no gimmick. The `dark: true` flag (not a monster stat) is what makes this level distinct from an ordinary wolf encounter elsewhere. |

Hits-to-kill against player baseline (30 hp/5 atk/1 def): wolf dies in 4
hits and deals 4 damage per hit landed - an established early/mid
tier, no rebalancing needed. A `healing_potion` sits near the Hollow's
Rim, before the darkness starts - a "brace yourself" placement matching
every other dungeon's own convention, positioned specifically before
visibility shrinks rather than somewhere the player might miss it in
the dark.

## Tone notes for anyone (agent or human) revising this later

- The darkness is physical, not supernatural. If a description reaches
  for "unnatural" or "wrong," that's the Elder Cairn's job, not this
  dungeon's - a steep hollow blocking sunlight needs no more explanation
  than that.
- The wolves are wildlife, not villains - a den in an inconvenient spot,
  not a menace with intent. Nothing here should read as a grudge or a
  crisis; it's the smallest, most practical conflict in the game so far.
- Keep this dungeon small. Its whole design intent is "the least
  dramatic possible obstacle, made to feel dangerous through reduced
  visibility rather than scale" - resist the urge to add a second level
  or a named threat.
