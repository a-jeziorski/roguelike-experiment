# The Forgotten Ruins — Dungeon Bible

*A design document for one dungeon, written the way a GM would key a
site for a tabletop session: what's actually here, why, and what the
player is meant to feel room to room. See `docs/world_history.md` for
the realm-level facts this dungeon has to agree with, and
`docs/content_design_process.md` for the mechanical authoring rules
(balance math, geometry variety, the three story surfaces). This
document is the missing middle layer between those two - the specific
story of *this* place, decided before any ASCII is drawn.*

This is the project's original dungeon, written before the per-dungeon
bible convention (`docs/content_design_process.md` §0d) existed at all -
this document is that missing round of proper generation, written after
the fact. It also folds in the one open item `content_design_process.md`
§3 has been carrying since the `prison_tower` geometry pass: `level_03`
and `level_05` were still the un-revisited single-open-room originals
that feedback was about. This pass fixes that - see set pieces 4 and 6
below for the revised geometry - without touching either level's
narrative beat, its entity roster, or (for `level_05`) its exact item
count.

## The pitch

Forgotten Ruins is one continuous descent under a single collapsed
manor: a mundane cellar giving way, a few rooms down, to something the
manor was never built to notice it was sitting on top of. Nothing about
the manor above explains what's beneath it - that's the point. The
Old Kingdom family who lived there built a perfectly ordinary cellar,
the same as any manor's, with no idea (or no admission) that older
stonework was already down there waiting.

**Placement on the world bible**: a genuine two-era site, and the
clearest place in the game where those two eras sit directly on top of
each other. `level_01` is Long Quiet-era present-day squatter decay
(mundane, explicable, no mystery). `level_02a`/`level_02b` are older
Old Kingdom-adjacent burial ruins - still explicable, just old.
`level_03` onward is where the ground actually changes: `world_history.md`
names "the deepest halls under Forgotten Ruins" as one of the Elder
Age's only two known remains in the whole setting. From `level_03` down,
the masonry should stop looking like anything the Old Kingdom or anyone
after it built - `world_history.md`'s explicit instruction to leave this
era vague applies most directly here of any dungeon in the game. Don't
over-explain it. A line about the stone looking grown instead of built
does more work than a paragraph of invented cosmology.

## Mood

A descent, literally and tonally: each level should feel a stratum
older than the one above it, the same way the world bible names the
Elder Age "the way you'd name a stratum of rock." `level_01` is dusty
and ordinary. By `level_03` the player should already sense the ground
has changed even before any text says so. `level_05` is the answer to
"what built all of this in the first place" - and per `world_history.md`,
that answer is deliberately withheld, not delivered. The dread down here
is atmospheric, not explained - the opposite instinct from Sunken Mine's
"dust, not dread" mundane bureaucratic tragedy.

## Structure overview

Six levels, branch-then-converge, unchanged in shape from how this
dungeon has always been built - this bible documents it for the first
time and revises two levels' geometry, not the overall arc:

| Level | Name | Beat | Set piece(s) |
|---|---|---|---|
| `level_01` | The Rotting Cellar | mundane decay, present-day squatters | 1. The Squatters' Cellar |
| `level_02a` | The Flooded Crypt | older burial ruins, path A | 2. The Standing Water |
| `level_02b` | The Goblin Warren | older burial ruins, path B | 3. The Claimed Crypt |
| `level_03` | The Sunless Throne | a seat of old power - looks like the end, isn't | 4. The Sunless Throne (revised) |
| `level_04` | The Elder Ossuary | older still, bone-filled | 5. The Ossuary Vault |
| `level_05` | The First Ruin | the true bottom, origin of everything above | 6. The Nameless Chamber (revised) |

## The named set pieces

### 1. The Squatters' Cellar (`level_01`)

An ordinary manor cellar - two rooms either side of a dividing wall,
a locked side-cellar behind a door - now home to whatever wandered in
after the manor above was abandoned: a rat nest in one corner, a goblin
that's clearly been living here a while, a stray dagger and a rusty key
nobody came back for. Nothing here is old in the Elder Age sense; it's
just neglected. This is the present-day baseline every level below is a
departure from.

*Why it's first*: establishes the mundane Long Quiet register before
the dungeon starts getting older underfoot. The locked side-cellar (a
`hunting_bow`/`arrows` cache) is the dungeon's first reward gate, off
the critical path per convention.

### 2. The Standing Water (`level_02a`)

The Flooded Crypt: groundwater has been seeping into this burial chamber
long enough that it now just reads as part of the architecture, not a
recent flood. Two skeletons stand in the damp - guardians in the loose
"old, grim magic" sense every skeleton in this world shares, not
anything specific to this room. A suit of `leather_armor` is the only
find here; no weapon.

*Why it's a weaker path, deliberately*: this is one half of the
branch's asymmetry (see Roster and balance below) - risk/reward, not a
mistake. A player who takes this path arrives at `level_03` under-armed
relative to the other branch, which is exactly why the fairness fix
lives at the convergence and past it, not here.

### 3. The Claimed Crypt (`level_02b`)

The Goblin Warren: the same tier of burial ruin as `level_02a`, but
occupied rather than merely flooded - goblins have moved into an older
crypt the same unceremonious way they moved into the cellar above,
claiming space rather than understanding what it originally was. The
mine's... rather, the crypt's actual find here is an `iron_sword`,
sitting where whoever built this crypt would recognize it least.

*Why it's the stronger path*: the branch's other half - a real choice
between two distinct tones (a quiet, damp, guarded crypt vs. an occupied
one with a real fight and a real reward), not the same room reskinned.

### 4. The Sunless Throne (`level_03`) — revised geometry

**Before this pass**: a single 24x11 open room - player start at one
end, a skeleton loose in the middle distance, an ogre standing near the
stairs down, one healing potion. Functionally fine, but exactly the
"single open room" `content_design_process.md` §3 flagged: nothing to
turn a corner around, nothing to feel like it's sneaking past.

**After this pass**: three connected spaces instead of one rectangle,
built the same way `prison_tower`'s levels demonstrate the fix (a narrow
chokepoint, a room broken up by interior pillars instead of a bare
rectangle):

- **The Antechamber** - a small enclosed room where the player arrives
  (from either `level_02a` or `level_02b` - `forgotten_ruins` has no
  `stairs_up` anywhere, so every hop always lands at `player_start`
  regardless of which branch was taken). Bare, low-ceilinged, clearly a
  waiting room for whoever used to be granted an audience here. Its only
  exit is a single one-tile gap in its east wall - the level's
  chokepoint.
- **The Sunless Throne Hall** - the real room, reached only through that
  gap. Two interior pillar-blocks break up what would otherwise be one
  bare rectangle (the `prison_tower` Gatehouse's own fix, reused here).
  The skeleton (`sleeping_guard`) is stationed just past the entrance,
  tucked beside the first pillar rather than standing dead-center in the
  doorway - the "sleeping guard around a corner" beat this pass exists
  to deliver. A `landmark` tile marks the throne itself, deeper in the
  hall: a stone seat too large for anything that still walks upright,
  worn smooth along the arms by whatever last sat in it. The ogre
  (`hostile_basic`) is stationed there, guarding it the way an animal
  guards a den rather than the way a guard guards a post - it has no
  idea what the seat once was. A healing potion sits on the approach to
  it, the dungeon's usual "brace yourself" beat before a harder fight.
- **The passage beyond** - past the throne, a short continuation leads
  to the stairs down to `level_04`, still inside the same hall. This is
  the "looks like the end, isn't" beat made structural, not just
  narrated: the room that reads as the dungeon's climax - a throne, a
  guardian, a dead end - turns out to have more dungeon leading out the
  far side of it.

Entity/item composition is unchanged from before this pass (one
skeleton, one ogre, one healing potion, one terminal-to-`level_04`
stairway) - only the shape changed, per the brief to revise geometry,
not story. No new monster type was needed; the existing skeleton/ogre
pairing already tells this room's story once it has a corner to hide
behind and a throne to stand around.

### 5. The Ossuary Vault (`level_04`)

Bone-filled halls, older again - already multi-room, already carries
this dungeon's fairness fix for the `02a`/`02b` branch (a second
`iron_sword`, placed here specifically because both branches converge at
`level_03` and funnel through here on the way to the true bottom - see
`content_design_process.md` §2's "audit item availability at every point
where paths reconverge"). A locked door gates a `bone_plate` reward, off
the critical path per convention. This pass didn't touch `level_04` -
documented here only so the fairness fix is visible in one place
alongside the branch it corrects for.

### 6. The Nameless Chamber (`level_05`) — revised geometry

**Before this pass**: the dungeon's other single 24x11 open room -
same shape problem as `level_03`, at the worst possible place to leave
unfixed, since this is the level meant to feel like "the origin of
everything above."

**After this pass**: three irregular, non-rectangular spaces connected
by a winding (not straight) passage - deliberately rougher-edged than
`level_03`'s revision, since this is the one level in the whole dungeon
that's supposed to read as Elder Age architecture itself, not Old
Kingdom stonework built on top of it. `world_history.md`'s note that
Elder Age masonry "looks grown rather than built, no right angles
insisted upon" is the literal geometry brief for this room: every
chamber here has at least one notched-off corner instead of a clean
90-degree turn.

- **The Vestibule** - where the player arrives (again always at
  `player_start`, regardless of path taken to get here). Irregular,
  corners softened, nothing dangerous staged in it - let it breathe
  before the passage narrows.
- **The winding passage** - bends twice rather than running straight,
  specifically so nothing in the next room is visible from the
  Vestibule. A healing potion sits partway down it, the last "brace
  yourself" beat before both remaining threats.
- **The Watching Dark** - a small nook off the passage's second bend
  where the skeleton (`sleeping_guard`) waits, out of the direct
  sightline from the Vestibule - the same "around a corner" beat as
  `level_03`, adapted to this level's rougher, less architectural shape.
- **The Nameless Chamber proper** - the origin room itself, also
  corner-notched rather than rectangular. A second `landmark` tile marks
  the thing this whole dungeon has been descending toward: a seam in the
  stone where construction stops looking built and starts looking grown
  - no join, no mortar, no edge the eye can find, and - the one
  concession to this era's "not inert" quality per `world_history.md` -
  faintly warm, though nothing here should be. No further explanation is
  given, on purpose. The ogre (`hostile_basic`) stands at it, the second
  healing potion sits near the approach, and the terminal stairs down
  (`>`, no further destination - reaching it ends the dungeon) sit just
  past both.

Entity/item composition is unchanged from before this pass: one ogre,
one skeleton, two healing potions, one terminal stairway - only the
shape and the addition of the `landmark` tile changed. `tests/test_loader.py`'s
`test_level_05_content` already asserted exactly this composition; it
needed no update, since the intentional content it describes didn't
change, only the room around it.

## Roster and balance (unchanged - existing roster, documented here for
## the first time)

| Monster | Where | Why here specifically |
|---|---|---|
| `rat` (hp 6/atk 2/def 0, skittish) | `level_01`, `level_04` | Background vermin, present from the mundane top of the dungeon to the bone-filled depths - the one creature unbothered by which era's stonework it's standing in. |
| `goblin` (hp 12/atk 4/def 1, hostile_basic) | `level_01`, `level_02b` | Present-day squatters, claiming space in both the cellar above and the crypt below it the same unceremonious way. |
| `skeleton` (hp 16/atk 5/def 2, sleeping_guard) | `level_02a` (x2), `level_03`, `level_04` (x2 with `skeleton_archer`) | This dungeon's most-used guardian type - "old, grim magic," per its own catalog description, doing the same thing at every depth. Its `sleeping_guard` AI is exactly why it reads as "guarding" a crypt or a throne without needing a motive spelled out. |
| `skeleton_archer` (hp 12/atk 4/def 1, ranged_basic) | `level_04` | Keeps distance in the ossuary's more open bone-hall, a ranged counterpoint to the melee skeletons stationed nearby. |
| `ogre` (hp 28/atk 8/def 3, hostile_basic) | `level_03`, `level_05` | The dungeon's heaviest single fight, used twice - once at the convergence (`level_03`), once at the true bottom (`level_05`). Both placements come late enough that a player has had a real chance at `iron_sword`/`leather_armor` first (see the branch fairness note above), consistent with `content_design_process.md` §2's warning that the ogre "should never be the first fight a player can reach without a weapon upgrade already in hand." |

Hits-to-kill against player baseline (30 hp / 5 atk / 1 def), unchanged
stats (no rebalancing this pass - the revision is geometry only): rat
dies in 3 hits, deals 1/hit; goblin dies in 4 hits, deals 3/hit; skeleton
dies in 6 hits, deals 4/hit; skeleton archer dies in 5 hits, deals 3/hit
at range; ogre dies in 14 hits (5 with an `iron_sword` equipped, `8-1=7`
per hit taken without armor, `5-1=4` with `leather_armor`) - exactly the
"~14-hit slog at base stats" the balance methodology calls out by name,
which is why both ogre placements in this dungeon sit past a point where
gear is obtainable, never before it.

**Branch fairness, restated for this document**: `level_02a` (potion +
`leather_armor`, no weapon) and `level_02b` (`iron_sword`) are an
intentional risk/reward asymmetry between two parallel paths that both
funnel into `level_03`. The existing fix - a second `iron_sword` in
`level_04`, past the convergence - was already in place before this pass
and is unchanged by it; this document just names it for the first time.
Revising `level_03`'s geometry didn't touch item placement on either
branch or at the convergence itself, so the audit still holds.

**No `skittish` monsters appear in the revised levels** (`level_03`'s
skeleton is `sleeping_guard`, its ogre and both `level_05` monsters are
`hostile_basic`/`sleeping_guard`), so the flee-threshold gotcha
(`docs/content_design_process.md` §2) doesn't apply to anything touched
this pass. `level_01`'s `rat` is the only `skittish` spawn in this
dungeon, unaffected by this revision.

**No door/key pair was added or changed this pass.** `level_01` and
`level_04` keep their existing reward-gated doors; `level_03` and
`level_05` have none, before or after.

## Tone notes for anyone (agent or human) revising this later

- Keep the era boundary sharp: `level_01`/`level_02a`/`level_02b` are
  explicable, mundane, and eventually going to be understood by anyone
  who looks hard enough. `level_03` onward should never fully resolve
  into an explanation - the Elder Age stays "older than anything with a
  name," per `world_history.md`'s own instruction, all the way to the
  bottom.
- `level_05`'s new `landmark` description is written to gesture, not
  explain. If a future revision is tempted to add a paragraph clarifying
  what the seam in the stone actually is or was, that's the wrong
  instinct for this dungeon specifically - under-explaining is the
  point here in a way it isn't anywhere else in the game.
- Both revised levels keep the exact entity/item roster they shipped
  with before this pass. If a future pass wants to add a new monster
  (e.g. `giant_spider` from the entities.yaml bestiary expansion) to
  either level, that's a legitimate future option the process doc
  explicitly allows for - but it wasn't needed this pass, since the
  existing skeleton/ogre pairing already told both rooms' stories once
  they had real geometry to do it in.
