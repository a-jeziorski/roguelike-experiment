# The Visitor — Main Storyline (Draft)

*This is a draft, not a locked design - names are tentative (marked
where relevant) and several mechanical questions are explicitly left
open at the end rather than papered over. It sits one level above
`docs/dungeon_bibles/`/`docs/quest_bibles/`: those document one place or
one connected quest arc each; this documents the campaign spine those
eventually hang off. Read `docs/world_history.md` first - this storyline
has to agree with it, not repeat or override it - and
`docs/content_design_process.md` for how any of this eventually becomes
real content.*

## Premise

The Sundered Realm is invaded. Not by an army, and not by anything from
its own history - by **The Visitor** (tentative name), a being projected
into this plane of existence from another, drawn by the ripples the
Sundering itself sent out across whatever the Elder Age actually was.
The Visitor is a scholar - specifically, a scholar of death as a
multiversal constant - and has taken it upon itself to study the
Sundering and the Elder Age that preceded it. It intends to solve a
mystery. Solving it is destroying the Sundered Realm.

The Visitor is amoral, not malicious - the same "ordinary institutional
appetite" register `world_history.md` already assigns the Old Kingdom's
own reach for Elder Age power before the Sundering. It takes no more
interest in the people living here than a researcher takes in the ants
disturbed by a dig site. It is immensely powerful and, for all practical
purposes in this story, immortal - but not invulnerable. It can be
banished from this plane. Nothing currently standing in the Sundered
Realm is capable of that alone; the story's job is to make that
capability something the player can assemble, not something they
already have.

**Placement on the world bible**: this is a Long Quiet-era event
layered on top of everything `world_history.md` already established -
it doesn't retcon the Old Kingdom, the Sundering, or any existing
dungeon's own history. It *does* mean the Visitor is now excavating
Elder Age sites already in the game (Forgotten Ruins, the Elder Cairn) -
treat this as the same sites getting a second, present-day visitor, not
new lore about what they are. The Elder Age itself must stay exactly as
vague as `world_history.md` already insists: the Visitor is chasing an
answer, but the game should never actually hand the player - or the
audience - that answer in full. What the player can do is *deny it to
the Visitor*, not *learn it*.

## The Visitor's methods

- **Necromancy at scale.** Simple undead (skeletons, zombies) drawn from
  whoever and whatever the Visitor's arrival kills, used as expendable
  labor to excavate and scour Elder Age ruins.
- **Necrocrafts.** Amalgamations of many creatures' remains, reshaped for
  a specific purpose - stronger, stranger, and more deliberately built
  than a raised corpse. The Visitor's own mobile base of operations - a
  massive, magically-floating airship/flagship (tentative: "the
  necroship") - is itself one of these, not a separate vehicle.
- **Regional, not global, presence.** The Visitor can only control its
  creations at a substantial but *limited* range, so it studies one
  region at a time - months in one place, then a sudden, disruptive
  relocation. What it leaves behind: barren, corrupted land (plants dead,
  the ground unable to support life), shambling leftover undead with no
  further purpose once the Visitor moves on, and freshly excavated Elder
  Age ruins.

## Inciting incident (already shipped, reinterpreted)

The goblin horde already fleeing south toward Wayford
(`goblin_warning`/`spreading_the_warning`/`goblin_ambush`, all shipped)
is the player's first sign of the Visitor, not an unrelated goblin
migration - the horde is fleeing the region the Visitor and its
necroship have just occupied to the north. This needs no rework of
existing content, only reframing: the existing quests/encounter already
work exactly as a first sign would need to.

## Structure: the player explores while the clock runs

The Visitor's presence is best modeled as a **long-running master quest
with its own deadline** - mechanically the same primitive `on_fail`/
`tighten_deadline` already are, just at campaign scope instead of a
single town's. While it ticks, the player explores, takes on ordinary
quests, and gradually learns more about the Visitor and its motives -
through scholars, mages, and other NPCs, none of them as wise or
powerful as the Visitor itself, each offering a partial read on what's
happening and what might be done about it. Eventually the player gets a
real choice of response. All three endings below are framed as: *what
happens when the master deadline resolves, and what the player did
before it did.*

## The three endings (names tentative)

### 1. Avoidance

The player runs the clock. The Visitor completes its research and
departs on its own terms - but not before passing through most of the
game's regions, leaving each one devastated in its wake. Most settler
enclaves are destroyed; survivors are left to contend with the
leftover, purposeless undead. Side-quest chains completed along the way
can *lessen* this ending's severity (fewer regions hit as hard, a
specific settlement spared, a specific group of survivors given a
fighting chance) without preventing it outright - a glimmer of hope, not
a rescue.

### 2. Bargain

With help gathered from scholarly NPCs, the player assembles enough of
the Sundering's mystery to *trade* it - not to solve it outright and not
in a way the game ever narrates as a definitive answer, just enough
fragments/artifacts to satisfy the Visitor's actual curiosity before it
finishes independently. The player confronts the Visitor aboard its
flagship and offers the trade in exchange for immediate departure. The
Visitor agrees - it had no intention of staying regardless - and then
either kills or spares the player character depending on their standing
with it. Mechanically: a long fetch/knowledge quest chain that must
complete *before* the master deadline lapses.

### 3. Avenge

The player confronts and defeats the Visitor, banishing it outright.
Deliberately the longest path of the three - not a raw stat grind, but a
sequence of specific problems the Visitor's own nature poses, each
solved with the help of a different NPC or organization (subverting a
chosen-one framing: no single faction, including the player, can do this
alone):

- **Reaching it at all.** The flagship floats; nothing in the setting
  currently flies. The leading idea: recover and reactivate a
  still-functioning Elder Age flying construct from an existing ruin
  (Forgotten Ruins or the Elder Cairn) - consistent with the world
  bible's existing "the Elder Age left things behind that still function"
  precedent (`stone_sentinel`, "still on duty"), and answered with an
  artifact rather than an explanation, preserving the Elder Age's
  mystery instead of spending it.
- **Something capable of hurting an immortal.** A different
  organization's contribution - a weapon, a rite, a substance - TBD.
- **Knowledge of how banishment actually works.** A third contribution -
  likely the scholarly NPCs mentioned above, or a faction distinct from
  them.

The tradeoff against Bargain is explicit and intentional: a more
definitive resolution, bought with more time for the Visitor to do
damage while the player prepares. Avenge should take meaningfully longer
than Bargain to become available.

## Mechanical grounding (from design discussion, not yet built)

Kept here so the eventual implementation plan starts from an accurate
picture of what's genuinely new versus what already exists:

**Already buildable with existing primitives:**
- The master timeline itself - a quest with a deadline; Bargain/Avenge
  are quest chains racing to complete before its `on_fail` fires
  Avoidance.
- Gating the flagship's entrance on possessing the flight artifact - the
  same mechanic a locked door already uses (`requires_key`), applied to
  a `dungeon_entrance` instead.
- Distributing Avenge across several organizations, each contributing
  one piece - the same shape as Wayford's three-questgiver arc, just
  aimed at one finale instead of one town's own ambition.

**Genuinely new, needing their own design pass:**
- **Region-scale overworld corruption** - **built (2026-09-05), see
  `docs/visitor_corruption.md` for the full design.** A programmatic
  kind-remap table (`plains -> ashen_plains`, `forest -> blighted_forest`,
  `road -> ashen_road`), spread outward from a per-region epicenter with
  a growing, organically-irregular radius (`engine/game_map.py`'s
  `apply_corruption_radius`) - the cheaper, less-bespoke option this
  bullet originally left open, chosen over hand-authoring alternate
  terrain per region. Generalizes `Engine.destroy_dungeon`'s single-tile
  mutation pattern to many tiles at once, exactly as this bullet
  anticipated. Shipped against the Northern Steppe: a 4-phase timeline
  razes the Watch Post and uncovers both of the region's reserved Elder
  Age landmarks (`elder_dig_site_a`/`elder_dig_site_b`, both full
  5-level dungeons) as the Visitor's occupation there runs its course.
- **A real endgame confrontation mechanic.** "Immeasurably powerful,
  barely beatable" needs more than a large stat block - a multi-phase
  fight, environmental hazards, or a non-combat ritual/banishment
  sequence. Not designed yet.
- **The Avenge power curve.** Player stats are fixed constants today;
  only gear scales, on an explicit two-tier discipline the balance
  methodology actively warns against exceeding. If Avenge needs to feel
  meaningfully harder-won than Bargain, this needs either a real
  progression system (XP/leveling, floated once, never built) or a
  deliberate new gear tier - a decision, not an accretion.
- **Multi-prerequisite quests.** `QuestDef.requires_quest_id` only takes
  one prerequisite today. Avenge's "several organizations must all have
  contributed" structure needs a quest to wait on more than one
  predecessor - a small, natural extension (`requires_quest_ids: list`)
  flagged now rather than discovered mid-implementation.

## Tone notes

- No chosen-one framing. The player is the one connecting several
  ordinary factions' contributions, not uniquely destined - matches the
  "ordinary institutional appetite" register used everywhere else in
  this world, including for the Visitor itself.
- The Elder Age stays vague *even in Bargain's premise* - the player
  gathers enough to trade, never enough that the game spells out the
  true answer to the player or the audience.
- The Visitor is not evil in a cartoonish sense - keep flavor text
  describing it (and its remaining dialogue, if any) clinical and
  curious, never gloating or sadistic. Its devastation is a side effect
  of its actual goal, not the goal itself - same discipline already used
  for the Old Kingdom's own reach for Elder Age power before the
  Sundering.
- Every region's devastation should read as a *cost*, not a spectacle -
  matching the restraint already used for `stonebridge_raided` (a real,
  named cost - a granary, some houses - never an apocalyptic wipe unless
  that's specifically the point, per Wayford's `destroy_dungeon`
  precedent).

## Open questions (not yet decided)

- Does the master deadline advance visibly to the player (some
  in-fiction signal of "how much time is left"), or is it meant to be
  inferred from world state and dialogue only, matching this project's
  minimal-HUD, no-hand-holding convention elsewhere?
- What, specifically, does "a weapon capable of harming an immortal"
  turn out to be, and which organization provides it?
- Which NPCs/organizations exist to deliver the scholarly
  Visitor-explaining content mid-game, and are any of them new, or drawn
  from towns already in the game?
- Exact shape of the final confrontation (combat, ritual, hybrid) - not
  yet chosen.
