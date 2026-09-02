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

`wolf` (hp 14/atk 5/def 1, `pack_hunter` - `pack_radius: 3`,
`pack_attack_bonus: 2`, xp 5) - already in `data/entities.yaml`, not yet
placed in any level before this pass. No new monster type, no stat
changes. **Correction: an earlier draft of this section called this
`hostile_basic`, "no gimmick" - wrong.** Wolves are `pack_hunter`, and
that mechanic is the actual reason the den reads as dangerous, not
incidental: any wolf within `pack_radius` of another live wolf hits for
`atk + pack_attack_bonus` (7, not the base 5) instead of its plain stat
line, so the den's real bite scales with how many wolves are still alive
and close together, not just their base attack.

| Monster | Where | Why here specifically |
|---|---|---|
| `wolf` | Throughout The Den (6, after a balance pass - see below) | The pack itself - `pack_hunter` is exactly the mechanic this set piece needs: a den reads as a *pack*, not six identical solo fights, because wolves near each other actually hit harder together. The `dark: true` flag (not a monster stat) is what makes this level distinct from an ordinary wolf encounter elsewhere. |

Hits-to-kill against player baseline (30 hp/5 atk/1 def): wolf dies in 4
hits; a lone wolf deals 4 damage per hit landed, rising to 6/hit
(`atk 7 - def 1`) once another wolf is within `pack_radius` - which the
den's own layout makes the common case, not the exception. **This
dungeon's earlier framing - "no rebalancing needed" at player baseline -
was wrong**: the only
in-fiction route to `clearing_the_sunless_hollow` runs through
Farrow's Stake well after the game's start, by which point
`balance_reference_xp: 40` is the actual expected investment, not 0.
A `testbuild sunless_hollow --perk toughness_1` run (see
`tools/balance.py`, `docs/content_design_process.md` §0s) against the
original 7-wolf/1-potion layout burned 74% of the player's HP pool on
just the *first two* wolves - killing "the whole den" (all of them,
per the cull quest) in one uninterrupted push was never realistic.

**The fix keeps the pack dangerous rather than shrinking the fight to
fit a single push.** Passive healing only happens on the overworld
(`Engine._advance_world_clock`, gated on `is_overworld` - a dungeon
never ticks the clock or heals the player on its own), so retreating to
the entrance and waiting out real game-hours to top up HP is already a
real, working strategy, and it costs something concrete: hours spent
healing are hours off whatever deadline is running on another quest
sharing the same clock (`goblin_warning`'s own `by Day 57` was still
live throughout balance-testing). That's the intended lever here, not
raw survivability - a genuine time-vs-safety trade the pack should be
just hard enough to force. Two changes, both modest: the wolf originally
guarding the entrance's one `healing_potion` (an ambush on the player's
only guaranteed recovery item, not a meaningful choice) was removed,
dropping the den to 6 wolves; a second `healing_potion` was added partway
through (near the second named cluster, not at the entrance), so the
player has one assisted top-up before the retreat-and-heal loop becomes
necessary. A full `toughness_1`-build clearance (6 wolves, both potions
used) still took two separate retreat-to-heal trips (~50 game-hours
total) and ended the last fight at 3/35 HP - genuinely tense, always
survivable with reasonable play. Don't re-inflate the wolf count or strip
the two potions without re-running `testbuild` against the current
`balance_reference_xp` first.

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

## Decoration pass

No content variety - the balance here is testbuild-verified down to the
exact wolf count and potion placement (see above), and the tone notes
already warn against adding a second level or a named threat; a new
monster or item would need the whole balance section re-run for no
narrative gain. Decoration stays to a light scatter of `bones` only -
already named in the pitch's own text ("packed earth, old bones,
claw-worn hollows") - nothing else fits a natural den with no ruin
underneath it and nothing built here (no `barrel`/`crate`/`table` kit;
there was never anyone here to bring any of that in).

One authoring note for anyone extending the scratchpad's
`render_millhaven.py`-style toolkit to a level with the `dark: true`
header flag: the generic renderer's hardcoded `id:`/`name:` header
lines don't know about it, so a top-level flag like this one gets
silently dropped on render and has to be added back by hand during the
header fix-up step. Caught here before install; `sunless_hollow` is
still the only dungeon using the flag, so no shared-script fix was
needed, but the next one won't get this warning for free.

Verification: re-validated via the real content loader (confirmed
`dark: true` survived the header fix-up, entity/item/decoration/stairs
counts all unchanged), full `pytest -q` (1373 passed), `tools/preview.py
data/dungeons` full registry, `main.py` smoke-launch, and a screenshot
via the scratchpad's `screenshot_dungeon.py` harness.
