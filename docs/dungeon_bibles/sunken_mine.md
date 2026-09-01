# The Sunken Mine — Dungeon Bible

*A design document for one dungeon, written the way a GM would key a
site for a tabletop session: what's actually here, why, and what the
player is meant to feel room to room. See `docs/world_history.md` for
the realm-level facts this dungeon has to agree with, and
`docs/content_design_process.md` for the mechanical authoring rules
(balance math, geometry variety, the three story surfaces). This
document is the missing middle layer between those two - the specific
story of *this* place, decided before any ASCII is drawn.*

## The pitch

The Sunken Mine is not a monster lair that happens to look like a mine.
It's a workplace where the workday never technically ended. Nothing
supernatural stopped it - no curse, no Elder Age intrusion, nothing the
Old Kingdom went looking for and shouldn't have found. The roof just
started coming down, on a schedule nobody was around to notice, because
the office that used to inspect the shoring stopped sending inspectors
the week everything else stopped too. The tragedy here is bureaucratic,
not mystical: a quota that was never finished, a night shift that never
clocked out, and thirty-odd years of rock settling into the shape their
absence left.

**Placement on the world bible**: squarely Old Kingdom-era in origin
(a mundane institutional site - ore, timber, a ledger of quotas, per
`world_history.md`'s explicit instruction that Old Kingdom sites default
to ordinary purpose, nothing magical about the architecture), and
squarely Long Quiet-era in its present state - one of the sites the
bible names outright as "Old Kingdom infrastructure squatted by whoever
got there first," vermin arriving before people did. Nothing in this
dungeon should read as mysterious in the Elder-Age sense; if a room
feels like it needs an unexplained force behind it, that's the wrong
instinct for this site specifically - the explanation is always
administrative neglect, never magic.

## Mood

Dust, not dread. This is a place that failed slowly and left paperwork
behind. The scares are practical (is that support beam going to hold,
is something living in that side-tunnel) rather than eerie. Every named
set piece below should be legible as "here's what mining work actually
looked like the day it stopped," not as a puzzle box or a shrine.

## Structure overview

Three levels, matching the existing dungeon's shape and difficulty
curve - this bible reworks *what's in* each level, not the level count
or overall length:

| Level | Name | Set pieces it holds |
|---|---|---|
| `level_01` | The Weighhouse Shaft | The Weighhouse |
| `level_02` | The Foreman's Gallery | The Foreman's Office, The Flooded Sump |
| `level_03` | The Last Vein | The Vermin Warren, The Blocked Face |

## The five named set pieces

### 1. The Weighhouse (`level_01`)

The first real room past the entrance shaft: a wide chamber built around
a stone weighing-counter, where every cart of ore got logged before it
went to the surface. The counter's still standing. So is the pan of
the scale, tipped and rusted at an angle, with a scatter of undersized
stones still sitting in it - somebody's idea of a joke, or somebody
caught mid-theft, on a day that stopped mattering before anyone found
out which. A chalk tally board on the wall behind the counter has one
column of hatch-marks that just... stops, a third of the way down that
day's quota.

*Why it's first*: this is the dungeon's thesis statement, shown before
it's told. A player who reads the counter and the tally board should
already understand the whole dungeon's tragedy before meeting a single
named threat - even with a `kobold`/`kobold_shaman` trio actually staged
in this same room (see the Populating the Bestiary note below; an
earlier draft of this document said nothing should be fighting here, but
that was written before this pass added them), the landmarks themselves
still read first, since the fight is what's *in* the room, not what the
room's own two set pieces are about.

### 2. The Foreman's Office (`level_02`)

A small, low-ceilinged room off the main gallery, its door still locked
- not because anything valuable was ever behind it, but because locking
up at the end of a shift was just what a foreman did, and nobody was
left to unlock it after. Inside: a desk, a strongbox, and the mine's
actual iron sword - not a monster's weapon, the *foreman's* sidearm,
issued for exactly the kind of trouble this mine never used to have. A
ledger on the desk, open to its last page, records a normal day's
quotas right up until the final entry, which trails off mid-sentence.

*Why it's a locked reward, not a fight*: per the established convention,
locked doors gate rewards, not paths - this room should never be
mandatory, and finding it should feel like reading someone's last
moment rather than winning a fight. No monster is stationed inside it.
The tension is entirely in the ledger's handwriting getting worse
toward the end, not in anything that can hurt the player.

### 3. The Flooded Sump (`level_02`)

A low point in the gallery where groundwater has been pooling, unpumped,
since the Sundering cut this mine off from whatever office used to keep
the pumps running. This is a *small, single obstacle* - one room, one
detour - not a flooded dungeon in miniature (that's the Drowned
Waystation's whole premise; here it should read as one bad spot in an
otherwise dry mine, not a second theme bolted on). A narrow dry ledge
skirts the standing water; taking it is slower and puts the player
closer to whatever's nesting nearby (see the Vermin Warren, one level
down - a goblin using the sump's noise as cover to jump anyone
picking their way along the ledge is the intended read of that
encounter).

*Why it's here, mechanically*: the dungeon's one deliberate "go around,
don't go through" beat, matching the Sunken Mine's original brief
(geometric novelty over new monsters) without duplicating the Drowned
Waystation's dungeon-wide flooding conceit.

A pale fungus grows on the ledge itself - the kind of thing that only
takes hold where standing water's gone untouched for years, which this
spot has in spades. It's the target of Millhaven's "A Standing Request"
(see `docs/dungeon_bibles/millhaven.md`'s set piece 8): the shopkeeper
wants it, for reasons the game never explains. Picking it up here is
an entirely ordinary pickup - it travels back in inventory like
anything else - the quest itself only completes once it's actually
handed over in Millhaven. First item in the game with no `ItemEffect`
at all - it's not equipment, not a potion, not currency, just a quest
target that happens to live in the one room already built around
"something's been sitting here undisturbed."

### 4. The Vermin Warren (`level_03`)

A wider, irregular chamber where the tunnel roof partially gave way
years ago and was never cleared - and where, in the years since,
something has been *living* in the rubble instead of digging it out.
Stolen mining tools, gnawed timber, a nest built from things that used
to belong to someone else. This is the "vermin first, then squatters"
line from `world_history.md` made literal and visible in one room:
rats nested here first, and the goblins who moved in afterward never
bothered clearing them out, just claimed the drier corners for
themselves. The two aren't cooperating so much as coexisting.

*Why it's a warren, not an ambush*: this should read as a lived-in den,
not a guarded vault - multiple weaker threats sharing a cluttered space,
rewarding a player who fights at the doorway instead of wading in.
Matches `skittish`'s existing design intent (rats break off and flee
once hurt, rather than everyone fighting to the death) - the goblins are
the ones actually defending the space.

### 5. The Blocked Face (`level_03`, climactic)

The end of the line: the actual rock face the mine was cutting toward
on its last working day, now sealed behind a fall of rock nobody ever
came back to clear. A pick is still lodged in the wall at chest height,
exactly where it was swung and left. And at the foot of that wall,
motionless until approached - `skeleton` (`sleeping_guard`), the miner
who was standing there when the shoring gave. Nothing supernatural
raised these bones; the same "old, grim magic" already established for
every skeleton in this world (see the entity's own catalog description)
is presumed to be doing here exactly what it does everywhere else -
this is not a unique haunting, just an ordinary skeleton in an
unusually specific, unusually sad place. `sleeping_guard` is the
correct AI choice on craft grounds too, not just theme: it's the one
type that lets a room stay silent and undisturbed until the player
commits to it, which is exactly the beat this room needs.

*Why it's last*: the dungeon's emotional and mechanical climax in one
beat - the single toughest fight in the dungeon, in the one room that
finally answers "what happened to the people who worked here." The
terminal `stairs_down` sits just past this room, so leaving the dungeon
means walking away from that answer, not past it.

## Roster and balance (unchanged constraint: reuse the existing catalog)

Per the original brief, this dungeon introduced **no new monsters** at
the time this document was first written - its novelty was meant to be
structural and narrative, not catalog growth. **That claim no longer
holds**: a later pass added a `kobold`/`kobold_shaman` trio to the
Weighhouse (see set piece 1 above) and an `orc` to the
Blocked Face (see set piece 5 below), neither reconciled into this
section until now. It still holds for items only in the narrower sense
below - the item *types* this section documents were the only ones
added on top of the original three-monster roster; monsters were a
separate, later addition. A
later pass added `gold_pile`/`gold_stash` (a new collectible-currency
item type, not specific to this dungeon) in three places, each reusing
lore already written into this document rather than inventing new
set pieces:

| Placement | Where specifically | Why here |
|---|---|---|
| `gold_pile` | The Weighhouse (`level_01`), near the counter | Coin dropped or forgotten the day the tally stopped - the same "nobody came back" beat the counter and tally board already tell. |
| `gold_stash` | The Foreman's Office (`level_02`) | This document already establishes "a desk, a strongbox" in that room - this is that strongbox's contents, made concrete. A wage payout that was due the day everything else stopped too. |
| `gold_pile` | The Vermin Warren (`level_03`), by the nest | The nest is already described as "things that used to belong to someone else" - scavenged coin is that line made literal. |

None of this dungeon's monsters or their stats changed to accommodate
gold - it's inert, already-possessed coin (no functioning economy
survives in the Long Quiet, per `world_history.md`), not a reward tied
to any fight. See `docs/dungeon_bibles/prison_tower.md`'s "Why there's
gold here at all" for the fuller framing shared across both dungeons.

Placements below use the existing monster roster with intent, rather
than scattering the same three monster types evenly:

| Monster | Where | Why here specifically |
|---|---|---|
| `rat` (hp 6/atk 2/def 0, skittish) | level_01 x2 (Weighhouse door approach, near the stairs down), level_02 x1 (Foreman's Gallery entrance), level_03 x2 (Vermin Warren) | Background vermin; the "arrived first" half of the warren's story, seeded early on every level before it. |
| `goblin` (hp 12/atk 4/def 1, hostile_basic) | level_01 x2 (guarding the locked-door key), level_02 x3 (gallery approaches, the sump ledge), level_03 x2 (Vermin Warren) | The mine's actual squatters; the one guarding the sump ledge is the dungeon's only "ambush" beat. |
| `kobold` (hp 8/atk 3/def 0, hostile_basic) x2, `kobold_shaman` (hp 9/atk 3/def 0, `ranged_basic`, range 4) x1 | level_01, the Weighhouse itself | Added in a later pass, staged directly in the set piece 1 room (see the note there) - a real fight in the same room as the dungeon's own "thesis statement" landmarks, not staged at its edges the way the rats are. |
| `skeleton` (hp 16/atk 5/def 2, sleeping_guard) | The Blocked Face only (`level_03`) | Used exactly once - see set piece 5. Every other skeleton in the game is a generic guard; this is the one place its `sleeping_guard` behavior is load-bearing to the story, not just to pacing. |
| `orc` (hp 15/atk 5/def 1, `enrage`) | The Blocked Face, alongside the skeleton (`level_03`) | Also added in a later pass, unreconciled into this document until now - the actual hardest single fight at the Blocked Face is now this pairing, not the skeleton alone (see below). |

Hits-to-kill against player baseline (30 hp / 5 atk / 1 def), no stats
touched: rat dies in 3 hits and deals 1/hit; goblin dies in 4 hits and
deals 3/hit; kobold dies in 2 hits and deals 2/hit (its shaman variant
the same, from range); skeleton dies in 6 hits and deals 4/hit; orc
dies in 4 hits and deals 4/hit, tougher once `enrage` kicks in under
30% hp. **The Blocked Face's actual difficulty is the skeleton and the
orc fought together**, not the skeleton alone as an earlier draft of
this document claimed - the room's toughest-single-fight framing still
holds, it just needs both monsters' math, not one.

Items stay close to the original placement, reframed with intent: a
`rusty_dagger` early (level_01, unguarded - a spare pick-hook nobody
thought worth locking up), a `teleportation_potion` in the Weighhouse
itself (level_01, unreconciled into this document until now), a
`rusty_key` unlocking `leather_armor` in a weighhouse locker (level_01),
a second `rusty_key` unlocking the Foreman's Office and its `iron_sword`
(level_02, see set piece 2), `hunting_bow`+`arrows` found loose in the
gallery (level_02), and a `healing_potion` each on level_02 (near the
sump) and level_03 (before the Vermin Warren) - the second one
specifically positioned as a "brace yourself" beat ahead of the warren
and the climax beyond it.

## Tone notes for anyone (agent or human) revising this later

- Keep it mundane. If a description reaches for "unnatural" or
  "wrong," that's the Elder Cairn's job, not this dungeon's.
- Every named room should be legible as a real place a real mining
  operation would have had - a weighhouse, a foreman's office, a flooded
  low point, a rubble-choked side tunnel, a dead-end face. Nothing here
  should require inventing new lore to explain.
- The tragedy is procedural, not personal-villain-shaped: nobody did
  this to the mine. The Sundering simply stopped the office that used
  to check on it, and gravity did the rest.
