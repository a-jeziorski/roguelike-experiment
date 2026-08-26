# Silversilk Caves — Dungeon Bible

*A design document for one dungeon, written the way a GM would key a
site for a tabletop session: what's actually here, why, and what the
player is meant to feel room to room. See `docs/world_history.md` for
the realm-level facts this dungeon has to agree with, and
`docs/content_design_process.md` for the mechanical authoring rules
(balance math, geometry variety, the three story surfaces). Written for
the Goblin Horde arc's Round 2: the dungeon the horde's dispersal
actually sent part of itself into, and the reference example
`content_design_process.md` §0o already names for the cull-while-
preserving trigger shape.*

## The pitch

Silversilk Caves is not built, occupied, or claimed by any faction this
world's history recognizes - it's older than the Old Kingdom, older than
the roads, a cave system threading beneath the mountains that has simply
always been there. What lives in it changes; the caves themselves don't.
For as long as Grey Valley Monastery has stood, its settlers have hunted
the upper reaches for cave spiders - food, and silk worth more than
almost anything else they can produce themselves. That arrangement held
for a generation, right up until the Goblin Horde broke apart passing
Wayford and a sizable splinter of it went looking for somewhere to make
a new home. They found these caves, moved into the upper levels the
Monastery depended on, and started doing to the resident cave spiders
exactly what the settlers used to do more carefully: killing them
indiscriminately, for food, for sport, for the simple reason that
anything sharing your den is a threat until it's dead. The settlers hire
the player to clear the goblins out. The catch is the one thing that
made this worth hiring for in the first place: the spiders have to
survive the clearing, or there's no hunting ground left to have saved.

**Placement on the world bible**: no era, no faction - a natural feature,
the one kind of location `world_history.md`'s existing scheme doesn't
have to stretch to accommodate, because nothing about a cave system
needs explaining in terms of the Kingdom or the Sundering. Its only tie
to the wider history is the *event* that populated it this pass: the
Goblin Horde's dispersal after Wayford, the same horde `wayford_arc.md`
already tracks, now with a second, quieter consequence downstream of the
first.

## Mood

Not dread, not tragedy - competition. Two things want the same den, and
only one of them is worth the player's sympathy. The goblins aren't
evil-for-its-own-sake any more than the sunken mine's rats were; they're
squatters doing what squatters do, the same "practical, not evil"
register `world_history.md` gives every Opportunist, even though these
particular squatters are monsters rather than people. The spiders aren't
innocent bystanders either - they bite, they'd hurt the player too if
cornered - just the *resource*, the reason this fight has a wrong way to
win it. Every room should read as lived-in-by-two-things-at-once: goblin
clutter (bones, crude blades, claimed sleeping hollows) encroaching on
spider sign (webbing, silk-wrapped husks, the dens themselves) rather
than one replacing the other cleanly.

The caves themselves should never feel built. No right angles, no rooms
you could put a name like "hall" or "chamber of" on the way Sunken Mine's
rooms earn names - just cavern after winding cavern, some wide enough to
lose the far wall in shadow, others barely wider than the player. If a
room reads like something a mining crew shaped on purpose, that's the
wrong instinct for this dungeon specifically.

## Structure overview

Two levels this pass - the *upper* reaches only, the ones the settlers
actually hunted and the goblins actually occupied. The bible-level scope
call from Round 1's planning holds: whatever lives deeper down (the
"genuinely dangerous creatures" the settlers always avoided) is
deliberately unbuilt, gestured at once and left there.

**A third, temporary level**: `level_01_undisturbed` - the same
`level_01` geometry with every goblin (and the Territory Marker, which
wouldn't exist yet) removed, cave spiders left exactly where they
already were. This is what the dungeon's entrance actually leads into
before the same day (87/67) `the_uninvited_tribe` becomes available -
see `content_design_process.md` §0r. Fixes a real bug: the tribe wasn't
supposed to be here yet on day 1, and for a while it was anyway. Not a
set piece of its own, no separate write-up below - it's `level_01` minus
the conflict, not a new story.

| Level | Name | Set pieces it holds |
|---|---|---|
| `level_01` | The Upper Reaches | The Territory Marker, The Outer Pickets, The Spider Dens |
| `level_02` | The Warren | The Heart of the Tribe, The Sealed Passage |
| `level_01_undisturbed` | The Upper Reaches (before) | Cave spider dens only - no goblins, no way down |

## The named set pieces

### 1. The Territory Marker (`level_01`)

A crude totem staked into the cave floor a short way past the entrance -
bone, rusted iron, and something dark dried into the binding - unmistakable
even to a player who's never seen one before as a claim being staked,
not decoration. This is the dungeon's thesis statement shown before it's
told, the same job the Weighhouse's tally board does for the Sunken Mine:
before the player meets a single goblin, they already know something has
moved in and is marking what it thinks it owns.

*Why it's first*: sets the "competition over a den," not "monster lair,"
frame immediately - the marker implies there was something here worth
marking, which is the spiders, even before the player's seen one.

### 2. The Outer Pickets (`level_01`)

Roughly nine goblins scattered loosely along the main route from the
entrance toward `level_02`'s stairs down - never clustered into a single
fight, always encountered a few at a time as the player works through the
winding caverns. These read as the tribe's outer edge: scouts and
opportunists who've claimed the approach rather than the tribe's actual
center. One is posted well off the main route, guarding the passage
down - the last thing between the upper caverns and the warren proper.

*Why light density here*: `level_01` is the approach, not the climax -
per `content_design_process.md`'s structural guidance, a level closer to
the dungeon's start can run a lighter, more transitional beat than the
one that follows it. Goblin (hp 12/atk 4/def 1, `hostile_basic`) needs
no rebalancing - already an established early/mid threat elsewhere in
the game; player baseline (30hp/5atk/1def) kills one in 3 hits, taking
roughly 3 damage back per hit landed.

### 3. The Spider Dens (`level_01`)

Four cave-spider dens tucked into distinctly peripheral pockets of the
cavern system - a corner past the entrance, a pocket on the far side of
the level, two more well off the main goblin route - each spatially
separated from where the pickets are posted. A player following the
obvious path through the caverns can go the entire level without ever
provoking a spider; finding one takes actually wandering into a den, not
bad luck on the main route.

*Why this matters mechanically*: cave spider (hp 7/atk 3/def 0,
`skittish`, `flee_hp_pct: 0.4`) drops to 2/7 hp on a single hit from the
player's baseline attack - below its flee threshold, so it bolts rather
than dying outright. Killing one takes a *second*, deliberate hit after
it's already fleeing. This is exactly the shape the preservation
mechanic needs: an accidental, incidental hit rarely kills a spider on
its own, so `target_preserve_tolerance: 5` is a real cushion against
genuine carelessness, not a trap sprung by one stray swing near a den a
player didn't mean to enter.

### 4. The Heart of the Tribe (`level_02`)

The tribe's actual camp, spread across `level_02`'s wider, more
interconnected caverns - roughly a dozen goblins, denser and more
clustered than the outer pickets, matching this level's role as the
dungeon's climax rather than its approach. This is where the totem
marker's claim actually lives: crude bedding, stolen and gnawed
materials, the visible bulk of the migration that broke off from the
larger horde. Cave spider dens persist here too - five of them, scattered
through side-pockets the same way `level_01`'s were, proof the spiders
never fully abandoned the caves even as the goblins spread through them,
just retreated to whatever corners hadn't been claimed yet.

*Why denser, not harder*: no stat changes from `level_01`'s goblins - the
challenge scales through encounter frequency and the wider, more open
caverns letting more than one picket notice the player at once, not
through tougher monsters. Matches the established "novelty is structural,
not catalog growth" discipline wherever it applies cleanly.

### 5. The Sealed Passage (`level_02`, climactic)

At the level's farthest, most convoluted point - reached only by
threading nearly the whole warren - the caverns narrow and the way down
is choked by a rockfall old enough that neither goblin nor spider
sign shows any sign of having touched it recently. This is the dungeon's
honest acknowledgment of what it isn't building yet: the "genuinely
dangerous creatures" the settlers always avoided are down there
somewhere, past this fall, and this pass doesn't go looking for them. A
single goblin - the tribe's last, most committed guard - is posted right
at the fall itself, the one placement in the dungeon that reads as
deliberate rather than opportunistic: whatever's down there, this
particular goblin isn't interested in finding out either, but it's
standing between the player and the one part of its territory it hasn't
given up on watching.

*Why it's last, and why it's a wall instead of a door*: unlike Sunken
Mine's locked doors (which gate optional rewards), this is a genuine
dead end - no key opens a rockfall, no future content is implied to
exist behind a specific unlockable barrier here. It exists purely to let
`level_02` end on the dungeon's own terms rather than trailing off, and
to leave an honest, visible hook for whatever eventually gets built
underneath this pass without committing to when or what.

The rockfall itself is a pure landmark, not a way out - every level in a
real dungeon needs its own way to leave (`requires_stairs_down`'s actual
enforcement is per-level, not merely "somewhere in the dungeon"), so
`level_02` also has a second, narrow crack elsewhere in the warren, cold
air bleeding through it from the surface: a way out that isn't the one
the player came in by, distinct from the Sealed Passage and placed well
clear of it. Two different ways this dungeon says "the caves keep
going" - one sealed, one open - without either one contradicting the
other.

## Roster and balance (no new monsters this pass)

Both `goblin` and `cave_spider` are pre-existing `data/entities.yaml`
catalog entries - the latter's own "not yet placed in any level" comment
confirms it was reserved for exactly this dungeon. No new monster type,
no stat changes to either.

| Monster | Where | Why here specifically |
|---|---|---|
| `goblin` (hp 12/atk 4/def 1, `hostile_basic`, xp 5) | `level_01`'s outer approach (~9), `level_02`'s camp (~11) plus one at the Sealed Passage | The migrated tribe itself - lighter and looser on the approach, denser and more territorial at its actual heart. |
| `cave_spider` (hp 7/atk 3/def 0, `skittish`, `flee_hp_pct: 0.4`, xp 3) | Peripheral dens on both levels (4 on `level_01`, 5 on `level_02`) | The resource the whole quest exists to protect - deliberately off the main goblin route on both levels, so avoiding them is a legible choice, not luck. |

Hits-to-kill against player baseline (30 hp/5 atk/1 def), unchanged from
every other placement of these two monsters: goblin dies in 3 hits and
deals roughly 3 damage per hit landed; cave spider drops below its own
flee threshold in a single hit (2/7 hp remaining) and needs a deliberate
follow-up to actually kill.

**Correction**: this section originally treated "fair at player baseline"
as the design target and left `balance_reference_xp` at `0` on that
basis. That's wrong - the only in-fiction route into Silversilk Caves is
well after the game's start (`pre_arrival_until_day: 67`, gated behind
the goblin horde dispersing near Wayford), so a player reasonably has
real investment (perks/gear) by the time they'd actually walk in here,
not a bare-baseline build. `balance_reference_xp` is now `120`, not `0`.
**The roster/potion numbers above have not yet been re-tested or
re-tuned against that figure** - `21` goblins across two levels, sized
for a 0-XP baseline, is very likely trivial at 120 XP investment. Run
`testbuild silver_mountain_caves` with a representative ~120 XP build
before trusting this section's placement counts; see
`docs/dungeon_bibles/sunless_hollow.md`'s own balance correction for the
shape this kind of pass takes.

Two `healing_potion`s per level (four total), placed along the main
route rather than inside any den - per the standing lesson that a real
combat level should never ship with zero recovery options, and
specifically *not* inside a spider den, where picking one up would
require walking straight into the one kind of encounter this dungeon
wants to stay optional.

## Tone notes for anyone (agent or human) revising this later

- No right angles, no named "rooms." If a description of a space in this
  dungeon reaches for architectural language ("hall," "gallery,"
  "chamber" in the structural sense Sunken Mine earns), that's the wrong
  register - "cavern," "hollow," "den," "pocket" instead.
- The goblins are squatters, not villains - practical, the same register
  `world_history.md` gives Opportunists, even though they're monsters
  rather than people and don't get that faction label. Nothing here
  should read as a grudge match.
- The spiders are a resource, not a threat to sell as dangerous. Their
  flavor text should lean toward "quick, easily missed, easy to leave
  alone" rather than "menacing" - the tension is entirely in the
  player's own restraint, not in the spiders being scary.
- The Sealed Passage is a hook, not a cliffhanger demanding a sequel -
  write it so it reads as complete and honest on its own, not as an
  unresolved thread the player should feel cheated by.
