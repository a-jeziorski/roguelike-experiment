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

**Correction: this "before" state isn't a dead end.**
`level_01_undisturbed`'s own `stairs_down` leads to a real, fully-built
`level_02_undisturbed.lvl` ("The Warren," before) - a denser, more
heavily-populated version of the Warren (roughly nine `cave_spider` and
three `giant_spider` spawns, no goblins) that its own `stairs_down` in
turn rejoins the main path at `level_03`. An earlier draft of this
document said the pre-conflict Upper Reaches had "no way down" and never
mentioned this level's existence at all - both wrong. The undisturbed
branch is a genuine, if unremarked-on, parallel path through the first
two floors: cave spiders at full population instead of a goblin-thinned
one, with no separate write-up of its own for the same reason
`level_01_undisturbed` doesn't get one - it's `level_02` minus the
conflict, not a new story, just one this document failed to actually
account for until now.

| Level | Name | Set pieces it holds |
|---|---|---|
| `level_01` | The Upper Reaches | The Territory Marker, The Outer Pickets, The Spider Dens |
| `level_02` | The Warren | The Heart of the Tribe, The Sealed Passage |
| `level_01_undisturbed` | The Upper Reaches (before) | Cave spider dens only - no goblins |
| `level_02_undisturbed` | The Warren (before) | **Undocumented until now** - see the correction note below |
| `level_03` | The Blind Reach | The Deep Population |
| `level_04` | The Broodmother's Hall | The Broodmother |
| `level_05` | The Elder's Den | The Elder Widow |

**Round 2** (`level_03`-`level_05`, added once a difficulty baseline
existed to build them against - see "The Depths" below): the goblins/
spiders conflict stays entirely above the Sealed Passage. Past it, the
mood, roster, and stakes all change completely - see below rather than
the set-piece framing above, which doesn't fit a different kind of
dungeon bolted onto the bottom of this one.

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
just retreated to whatever corners hadn't been claimed yet. One
`giant_spider` also holds a den here - unmentioned in an earlier draft
of this document, the same "bigger, further in" escalation the
Silversilk-depths bestiary uses deliberately elsewhere in this dungeon
(see "The Depths" below), just one early instance of it.

*Why denser, not harder*: no stat changes from `level_01`'s goblins - the
challenge scales through encounter frequency and the wider, more open
caverns letting more than one picket notice the player at once, not
through tougher monsters. Matches the established "novelty is structural,
not catalog growth" discipline wherever it applies cleanly.

### 5. The Sealed Passage (`level_02`) — **since reopened, see "The Depths" below**

At the level's farthest, most convoluted point - reached only by
threading nearly the whole warren - the caverns narrow at a rockfall old
enough that neither goblin nor spider sign showed any sign of having
touched it recently. A single goblin - the tribe's last, most committed
guard - is posted right at the fall itself, the one placement in the
dungeon that reads as deliberate rather than opportunistic: whatever's
down there, this particular goblin isn't interested in finding out
either, but it's standing between the player and the one part of its
territory it hasn't given up on watching.

*Why it was last, and why a wall instead of a door originally*: unlike
Sunken Mine's locked doors (which gate optional rewards), this used to
be written as a genuine dead end - no key opens a rockfall, no future
content implied to exist behind a specific unlockable barrier. It
existed purely to let `level_02` end on the dungeon's own terms rather
than trailing off, and to leave an honest, visible hook for whatever
eventually got built underneath. That "eventually" is now this pass -
the fall (legend symbol `Z`) is a real `stairs_down` into `level_03`,
with an updated description ("finally shifted enough to slip through")
rather than a landmark. The goblin guard, the rest of `level_02`'s
population, and everything above the fall are all unchanged - see "The
Depths" below for what's actually past it now.

The rockfall was originally a pure landmark, not a way out (now a real
`stairs_down`, per above). **Correction: there is no second exit.** An
earlier draft of this document described a second, narrow crack
elsewhere in the warren as an independent way out, distinct from the
fall - no such tile exists in the shipped level, which has exactly one
`stairs_up` (back to `level_01`) and the fall's own `stairs_down`
(`Z`, to `level_03`), same as every other level in this dungeon. That
pair already satisfies `requires_stairs_down`'s per-level enforcement on
its own; the second crack was never actually needed.

## Roster and balance, levels 1-2 (no new monsters here)

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

**Re-tested against that figure - the roster holds up, no count/placement
changes needed.** `testbuild silver_mountain_caves --perk toughness_1
--perk weapon_training_1 --perk shield_training_1 --potions 2` (130
XP-equivalent, `+10` over the 120 reference - a clean "three early perks"
build with no gear, close enough to representative) was walked through
both levels via real CLI moves (`walk`/`goto`/`attack`), fully clearing
every goblin and cave spider on both levels rather than only the ones
blocking a direct path - deliberately the harder, more thorough case than
the bible's own "avoid the dens" advice requires. At ATK 7/DEF 3, each
goblin now dies in 2 hits (was 3 at bare baseline) and lands roughly 1
damage per hit back (was ~3) - individually easier than the baseline
math in this section describes, but the *volume* still adds up: HP ran
from 35 down to a low of 14/35 (40%) mid-`level_02`, before settling at
17/35 (49%) once every goblin and spider on both levels was dead. Four
`healing_potion`s were found along the route (2/level, as designed) plus
the 2 the build carried in; only 1 was ever drunk, leaving 3 unused at
the end - **no retreat-to-heal trip was ever needed**, unlike Sunless
Hollow's wolves. Read together: a full, deliberately-thorough clear costs
a real chunk of the HP pool without requiring the retreat-and-heal lever,
comfortably inside the "accomplishable but not trivially so" bar - the
`21` goblins/`9` cave spiders and `4` potions stay as authored, no
count/placement changes made this pass.

**One real finding, not about density**: at this build's ATK 7, a single
melee hit deals exactly 7 damage - enough to kill a cave spider (`hp: 7`)
outright rather than dropping it to 2/7 and triggering `flee_hp_pct: 0.4`
the way the baseline math above describes. Every spider encountered this
playthrough died in one hit; none ever fled. This doesn't break combat
(spiders were never a real threat either way - their `atk 3` fully
absorbs into this build's `def 3` for 0 damage, so poison never triggered
either), but it does shift the cull-while-preserving mechanic's risk
profile: an *incidental* hit near a den, which the bible's `flee_hp_pct`
reasoning assumes only wounds a spider, now outright kills one at this
investment level. `target_preserve_tolerance: 5` (on `the_uninvited_tribe`,
against 9 spiders total across both levels) still comfortably absorbs a
handful of accidental one-shot kills, so this isn't a broken quest - just
worth knowing if a future pass touches `cave_spider.hp` or the tolerance
value: they're now more load-bearing against each other than the original
"wounds, doesn't kill" framing assumed.

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
- The Sealed Passage was a hook, not a cliffhanger demanding a sequel -
  written to read as complete and honest on its own at the time, not as
  an unresolved thread the player should have felt cheated by. It's
  reopened now (see "The Depths" below), which is the payoff that
  approach was always meant to earn, not a retcon of it.
- Past the fall, the tone changes on purpose (see "The Depths" below) -
  don't backfill goblin/spider competition framing onto `level_03`
  onward. It's a different, colder register: not two things fighting
  over a den, just something old that was never anyone's to contest.

## The Depths (`level_03`-`level_05`)

Everything above this point in the document describes the dungeon as it
shipped in Round 1. This section is Round 2 - built once
`docs/content_design_process.md`'s Northern Steppe bestiary pass had
established a concrete "~300 XP + mid-upper gear" reference build for
endgame-tier monsters (§0ac), giving this dungeon's own long-flagged
"genuinely dangerous creatures" hook something real to be calibrated
against. Same reference build, same tiering discipline, an independent
roster - Silversilk's depths are not the Northern Steppe's, just built
to the same difficulty ceiling.

### The pitch, past the fall

Nothing here competes with anything else for territory. No goblins made
it this far, no spider den claims this ground - whatever's down here
has simply always been the last, oldest thing in this cave system,
undisturbed since long before the Old Kingdom, let alone before a
goblin tribe or a monastery's hunting parties existed to avoid it. The
mood shifts from "competition" (Round 1) to something closer to
dread-of-scale: every level down is colder, quieter, and less lit than
the one before, and every creature in it reads as *older* rather than
*stronger-for-its-own-sake*. This is deliberately **not** Elder Age or
Visitor content - `world_history.md` already places Silversilk Caves as
"natural, no era or faction," and that stays true all the way to the
bottom. The depths are dangerous because they're ancient and
undisturbed, not because anything built or corrupted them.

**Escalation, matching the Northern Steppe's own three-tier shape**
(`docs/content_design_process.md` §0ac) but reusing none of its roster:

| Tier | Level | Danger | New entity(ies) |
|---|---|---|---|
| Challenging | `level_03`, The Blind Reach | First sign something bigger than cave spiders lives here | `deep_spider`, `blind_stalker` |
| Very dangerous | `level_04`, The Broodmother's Hall | A named, solo climactic threat plus denser ambient population | `broodmother`, `cave_lurker` |
| Extremely dangerous, approaching Hollow Reach | `level_05`, The Elder's Den | The dungeon's true apex, solo-placed | `elder_widow` |

**Why spiders stay the throughline, mostly**: `deep_spider`/`broodmother`/
`elder_widow` are all reskinned-and-recolored escalations of the same
lineage `cave_spider`/`giant_spider` already established (all three
share `giant_spider`'s sprite, recolored - the biggest spider art
available, same "one base sprite, several recolors" precedent
`guard`/`human` already use elsewhere in the catalog) - Silversilk's own
name and identity are spiders, so the depths escalate that identity
rather than replacing it. `blind_stalker` (`lurker_above`) and
`cave_lurker` (`violet_fungus`) are the deliberate exceptions, keeping
the roster from reading as "just bigger spiders three times over."

### The Deep Population (`level_03`)

Four `deep_spider` (hp 30/atk 13/def 2, poison - `giant_spider`'s own
shape scaled up a tier) and three `blind_stalker` (hp 28/atk 13/def 2,
`sleeping_guard` with a tight `alert_radius: 2` - no eyes, relies on the
player getting close rather than a wide passive sense) spread through
the level's long, winding route, never clustered - the same "scattered,
not piled" discipline `level_01`'s Outer Pickets already established,
just at a much higher stat tier. Two `healing_potion`s along the route.
This is the player's first real sign the "genuinely dangerous creatures"
warning wasn't idle - individually survivable, but nothing here is a
formality the way a `level_01` goblin still is by this point in a real
playthrough.

### The Broodmother (`level_04`, climactic)

A single `broodmother` (hp 42/atk 18/def 4, `regenerator`,
`regen_amount: 4`) holds the level's one large chamber at its farthest
point - deliberately mirroring the Northern Steppe's own
`stitched_vanguard` numbers exactly (both are "sustained regenerating
melee" tier-two threats; reusing the same figures wasn't an accident,
it's the same design decision arrived at twice). Two `cave_lurker`
(hp 28/atk 16/def 2, `ranged_basic` + `weaken`) are posted nearer her
den, backing her up at range - the only place in the dungeon two
different mechanics (sustained melee + ranged debuff) threaten the
player in the same encounter, intentionally, since this is the level
built to feel like the floor actually dropped. Three more `deep_spider`
patrol the approach, denser than `level_03`'s. Two `healing_potion`s and
one `banded_mail` (the strongest defense in the game, `defense_bonus: 6`) -
a real, earned reward for whatever it cost to reach her.

### The Elder Widow (`level_05`, the dungeon's end)

The single hardest fight in Silversilk Caves, alone in the largest room
in the dungeon: `elder_widow` (hp 55/atk 20/def 7, `enrage` +
`inflicts_effect: poison` at potency 4/duration 4). Raw stats sit close
to the Northern Steppe's own `charnel_colossus` (its nearest equivalent
in danger), with poison layered on top as a distinct flavor neither
Colossus nor `excavation_warden` carry - this is deliberately not a
reskin of either, just built to the same ceiling. A thinned-out ambient
population (two `deep_spider`, two `blind_stalker`, one `cave_lurker`)
gives the approach real texture without ever competing with her for the
player's attention - she is placed alone in her den on purpose, the
same "solo, rare, nothing else drawing attention in the same encounter"
discipline `excavation_warden`'s own stun-lock caution already
established for a different reason. Two `healing_potion`s on the
approach; nothing in the den itself - what's earned here is surviving
her, not a pile of loot.

**Verified**: one-on-one combat simulations (`COMBAT_VARIANCE_ENABLED`
off, for determinism) against a "moderate" reference build
(atk 12/def 6/hp 43) and an "optimistic" one (atk 14/def 9/hp 43, per
`docs/content_design_process.md` §0ac's own two-point range) confirm
`deep_spider`/`blind_stalker`/`cave_lurker` are clean, winnable 1v1s at
both ends of that range; `broodmother` and `elder_widow` both kill an
unmitigated reference build in a straight toe-to-toe slugfest with no
retreat, potions, or dodge - by design, matching `stitched_vanguard`'s
and `charnel_colossus`'s own already-accepted precedent at (near-)
identical stats. Real play has dodge/crit variance, potions, and the
established retreat-to-heal lever available; a bare stand-and-trade
fight against either was never meant to be winnable on its own.

### Terrain, levels 3-5

Generated via the same cellular-automata cave-carving technique named
(but not detailed) in §0p's own "second, separate problem" note -
organic, fully-connected caverns, no hand-drawn right angles, matching
`level_01`/`level_02`'s own "no named rooms" discipline exactly. Each
level's exit chamber is deliberately widened into a real room (radius
3/5/6 respectively, growing with the climax's importance) rather than
staying corridor-width, so the Broodmother's hall and the Elder's den
both read as a destination, not just the far end of a corridor. No
chokepoint was hand-carved before either climactic fight, unlike
`goblin_ambush`'s narrows - both are solo encounters, so the anti-swarm
reasoning a chokepoint exists for doesn't apply the way it does to
`level_01`'s Outer Pickets or `level_02`'s denser camp.

## Decoration pass

All seven level files were bare `floor` caverns - zero decorations
anywhere. No new `DecorationKind` and no content/roster changes on any
level - both the Round 1 balance section (testbuild-verified against
`balance_reference_xp: 120`, "no count/placement changes made this
pass") and Round 2's combat simulations already treat every level's
population as settled; decoration doesn't touch it. Every placement
also stays off `floor`-with-furniture entirely - the tone notes above
are explicit that these caves should "never feel built," so nothing
from the `table`/`chair`/`bed`/`chest`/`bookshelf`/`fireplace`/`barrel`/
`crate` side of the kit appears anywhere in this dungeon.

Three existing kinds do the whole job, each with a direct line back to
the Mood section's own imagery ("goblin clutter (bones, crude blades,
claimed sleeping hollows) encroaching on spider sign (webbing,
silk-wrapped husks, the dens themselves)"):

- **`bones`** - goblin clutter, placed near a sampling of `goblin`
  spawns on `level_01`/`level_02` only (the two levels goblins actually
  occupy). Never on the *_undisturbed variants or past the Sealed
  Passage, where no goblin ever set foot.
- **`cobwebs`** - spider webbing, placed near every spider-lineage
  monster on every level, including `deep_spider`/`broodmother`/
  `elder_widow` in the depths - per the bible's own "why spiders stay
  the throughline" note, these are still spiders under the escalation,
  and the webbing says so at a glance. Deliberately *not* placed near
  `blind_stalker`/`cave_lurker`, the two non-spider exceptions the
  roster is built around - giving them webbing too would blur the exact
  distinction that section exists to draw.
- **`rubble`** - general cave debris, scattered through open floor on
  every level with no particular concentration - natural rockfall
  litter, matching the Sealed Passage's own rockfall already
  established as this dungeon's one recurring geological feature.

Verification: all seven levels re-validated via the real content loader
(entity/item/decoration/stairs counts per level matched the bible's own
documented rosters exactly - `level_01` 9 goblins/4 spiders, `level_02`
12 goblins/5 `cave_spider`/1 `giant_spider`, `level_03` 4 `deep_spider`/
3 `blind_stalker`, `level_04` 3 `deep_spider`/2 `cave_lurker`/1
`broodmother`, `level_05` 2 `deep_spider`/2 `blind_stalker`/1
`cave_lurker`/1 `elder_widow`), full `pytest -q` (1447 passed),
`tools/preview.py data/dungeons` full registry, `main.py` smoke-launch,
and a screenshot of each level via the scratchpad's
`screenshot_dungeon.py` harness.

**Two pre-existing stairs bugs found during validation, unrelated to
decoration and not fixed as part of this pass** (flagged separately):
`level_01_undisturbed`'s own entrance stairs (`<`) read
`stairs_up: level_01_undisturbed` instead of `stairs_up: null` - since
this is the dungeon's `pre_arrival_starting_level`
(`data/dungeons/silver_mountain_caves/dungeon.yaml`), that entrance
should be a terminal exit to the overworld, exactly like `level_01`'s
own entrance, not a self-referencing loop back into a freshly-rebuilt
copy of itself. And `level_02_undisturbed`'s own stairs up
(`<`) read `stairs_up: level_01` instead of `stairs_up:
level_01_undisturbed` - walking up from the pre-arrival second level
currently drops the player into the post-arrival, goblin-populated
first level instead of the undisturbed one they actually came from.
