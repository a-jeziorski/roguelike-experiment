# Stonebridge — Dungeon Bible

*A design document for one location, written the way a GM would key a
site for a tabletop session: what's actually here, why, and what the
player is meant to feel room to room. See `docs/world_history.md` for
the realm-level facts this location has to agree with and
`docs/content_design_process.md` for the mechanical authoring rules.
Written for this pass: Stonebridge shipped in an earlier round with no
bible of its own, and `docs/dungeon_bibles/wayford.md` explicitly left
its tension unaddressed ("that's still Stonebridge's job, not this
town's"). This document is that job.*

## The pitch

Stonebridge's own `dungeon.yaml` already says the shape of it: a Long
Quiet settlement that chose to rebuild within sight of the
bandit-held Broken Watch rather than move downroad and pretend it isn't
there. Where Millhaven proved people could just decide to stay put, and
Wayford proved a settled town could start reaching back out toward the
rest of the map, Stonebridge is the third position in that same
progression: staying put *on purpose, in spite of a known threat*, not
because the threat hasn't found them yet. Nothing here is looking for a
fight; everything here is built assuming one might come anyway - the
gate barred, the wall manned, a lookout posted toward the hills.

This pass makes that tension real instead of only textural.
`clearing_the_watch_road` (Wayford's own kill-quest against
`bandit_captain`) already exists and already matters to the road west -
but nobody in *Stonebridge itself* had a stake in it, or a way to notice
if it went unanswered. This pass gives Stonebridge its own questgiver,
its own version of that same danger, and its own consequence if it's
ignored: `a_wall_worth_holding`, which sets the world flag
`stonebridge_raided` (not a dungeon destruction - Stonebridge survives
either way, changed, not erased) if the deadline passes with the captain
still alive. Two towns, two quests, the same single `bandit_captain`
spawn at Broken Watch - killing him in time answers both. Not fully
independent, though: `spreading_the_warning`'s own `on_fail` carries a
`tighten_deadline` aimed at `a_wall_worth_holding` (`data/quests.yaml`,
`docs/content_design_process.md` §0j) - if Wayford falls first, word of
it presses in on Stonebridge's own window too. One more way an
unanswered threat elsewhere shortens the time this one has left.

**Placement on the world bible**: pure Long Quiet, pure Settlers, same
footing as Millhaven and Wayford - no Old Kingdom ruin under it, no
faction of its own. The only thing that makes Stonebridge different from
its two Settler siblings is proximity to a real, already-established
Opportunist threat (Broken Watch) and a town that organizes its whole
posture around that fact.

## Mood

Watchful, not frightened. Nobody in Stonebridge is panicking - this is a
town that has *planned* for the hills, not one caught off guard by them.
The tension should read as competence under a standing threat, the same
"practical, not evil" register the world bible already gives the
Opportunists on the other side of it. If `stonebridge_raided` ever fires,
the aftermath should read as a real, costly event the town survived and
is still standing after - grim, specific, never apocalyptic (that
register belongs to Wayford's `on_fail_destroy_dungeon_id`, which this
consequence deliberately doesn't reach for).

## Structure overview

One level, matching Millhaven's and Wayford's own precedent - Stonebridge
doesn't need multiple floors to earn its depth, just real geometry
instead of one open field with obstacles in it (the original shipped
layout was closer to the latter than the former; this pass fixes that
alongside adding the new cast).

**Second pass, applying `content_design_process.md` §0af.** The first
pass's own prose got ahead of the actual level file - it described "a
real, walled-in interior" for the Lookout's Nook and wall clusters with
identity, but what shipped was a one-tile niche on bare plains flanked
by wall characters, and unlabeled `wall_block`s with no road reaching
any of it. This pass builds what the bible already claimed: the
Lookout's Nook is a real small room now, built directly into the
gatehouse band flanking the gate itself, with its own door onto the
entrance corridor; a road network runs from the gate down to a plaza
at the well (this town's other named landmark, and its natural civic
hub); and one of the wall clusters becomes **The Granary** (see set
piece 4) - the exact structure the already-shipped `stonebridge_raided`
flavor text ("lost the granary and two houses") was naming without ever
showing it. Resized 25x17 to 32x28 for the 7-entity cast and its one
real building - modest growth, this is a working town, not a padded one.
Decoration stays practical throughout (barrels/crates at the Granary,
fence marking a boundary, herb_clump texture) - nothing ornamental for
its own sake, matching a town "built assuming one might come anyway,"
not one dressing itself up.

| Level | Name | Set pieces it holds |
|---|---|---|
| `level_01` | Stonebridge Ward | The Gate, The Lookout Nook, The Well, The Granary, The Wall-Check Pair, The Watch |

## The named set pieces

### 1. The Gate

Unchanged in premise from the original shipped version - a single barred
gate, the only way in or out, with a short stub of road leading through
it before the town's plains terrain takes over (`player_start_tile:
road`, matching the terrain the player actually starts on). Everything
else in the bible orbits this one entrance, same "the wall is the town's
whole personality" logic the pitch establishes.

### 2. The Lookout Nook

A small enclosed post built directly into the gatehouse band flanking
the gate itself - an arrow-slit landmark and a real walled room with its
own door onto the entrance corridor (second pass; the first pass wrote
this set piece before the level file actually had it - see Structure
overview). **`stonebridge_lookout`** (new entity, `ai: villager`,
`stationary: true`, title only per the project's naming discipline)
stands inside it, findable in exactly this one spot every time -
matching the precedent every other questgiver in the game follows
(`wayford_road_warden`'s post, Millhaven's chief).

*Questgiver*: gives `a_wall_worth_holding` (kill `bandit_captain`,
deadline-gated, `on_fail: [{set_flag: stonebridge_raided}]` - see
`docs/content_design_process.md` §0e/§0j for the mechanism). Reuses the
exact same single `bandit_captain` spawn at Broken Watch that
`clearing_the_watch_road` already targets - safe by construction, since
`QuestLog.check_kill_report` matches by catalog id in
`killed_entity_ids`, not by which quest asked for the kill first; one
dead captain answers both towns' quests independently.

*Dialogue direction*: watches specifically for **fire**, not for bandits
in the abstract - "which fires are cookfires and which ones aren't" is
the Lookout's whole professional competence in one line. Practical and
observational, never panicked; this is someone good at their one job.

*Flag reaction*: if `stonebridge_raided` fires, the Lookout's own line
changes in place (see `content_design_process.md` §0k) - grim but not
broken. They were on watch when it happened and say so plainly, without
self-pity or excuse.

### 3. The Well

Unchanged landmark from the original layout - the town's other physical
anchor besides the gate, iron-bound, "hands used to hauling under more
than water." One nearby villager carries this pass's second flag
reaction: `wayford_razed` (news of a *different* town's fall reaching
Stonebridge secondhand, by trader) - deliberately not about their own
danger, to show the reactive-world mechanism reaches further than just
the two towns directly involved in any one consequence.

### 4. The Granary

A `wall_block` cluster (purely decorative, no new mechanics - same
technique every other settlement pass uses) that finally gives
`stonebridge_raided`'s already-shipped flavor text something to point
at: "lost the granary and two houses before the guard turned them
back" named a structure that, until this pass, the player could never
actually see. Barrels and a crate sit just outside, making "granary"
legible at a glance rather than only asserted in this document. A
second, smaller wall cluster elsewhere reads as ordinary houses -
practical, checked-every-winter upkeep, not a second named set piece of
its own.

### 5. The Wall-Check Pair

Two villagers, positioned together near the Granary, both talking about
the *maintenance* of the wall specifically (checked every year before
winter; the gate barred the instant the sun sets, no exceptions for
anyone still on the road) - the "planned for, not panicked" competence
the mood section calls for, made audible instead of just implied by the
`dungeon.yaml` description.

### 6. The Watch

One `town_guard`-AI spawn (reusing the existing catalog entity, same
precedent as Wayford's) - `dungeon.yaml` already promises a "wall
manned," and the original shipped layout had no guard entity to make
that literally true. Fixed this pass. Positioned near the town's other
practical anchor (the healing potion, the fifth villager) rather than
at the gate itself, since the gate is already covered by the Lookout's
post above it.

## Roster

One new stationary `villager`-AI entity (`stonebridge_lookout`, unique
catalog id per the same load-bearing reasoning `wayford.md` documents -
`entity_id` is the global key `QuestLog.check_questgiver` matches
against, so reusing an existing id here would cross-wire Stonebridge's
quest with whichever other town owns that id). One reused `town_guard`
spawn (safe to reuse - no quest ever targets it by id). Five numbered
`villager` spawns, every one with its own per-spawn `dialogue` -
Stonebridge's talkable cast (five villagers, the guard, the Lookout: 7
total) lands at 100% unique dialogue, comfortably clearing the 75% floor
`content_design_process.md` §1 requires and matching Wayford's own choice
to clear it fully rather than lean on the floor.

Two `flag_dialogue` reactions live on this roster (`content_design_process.md`
§0k): `stonebridge_lookout` and one plain villager react to
`stonebridge_raided`; a second plain villager reacts to `wayford_razed`.
Both are additive - normal dialogue keeps showing until either flag is
actually set.

## Tone notes for anyone (agent or human) revising this later

- No proper names - `Lookout`, matching `Road Warden`/`Town Clerk`/
  `Caravan Master`/`Village Chief`'s existing titles-only discipline.
- Keep `stonebridge_raided` non-apocalyptic in every line that
  references it - Stonebridge survives this. It's a real, costly event
  (a granary, a couple of houses, per the shipped flavor text), not a
  Wayford-style total loss. Don't let flavor text drift toward "the town
  is gone" register; that confuses this consequence with a dungeon
  destruction, which this deliberately isn't.
- `bandit_captain` must keep spawning **exactly once in the whole game**
  (currently true - Broken Watch's `level_03`, per `docs/quest_bibles/wayford_arc.md`).
  This is load-bearing for *two* quests now, not one - anyone revising
  Broken Watch needs to know both `clearing_the_watch_road` and
  `a_wall_worth_holding` depend on that single spawn staying single.
- The Lookout and the Road Warden are colleagues in spirit (both worried
  about the same stretch of road, from opposite ends of it) but never
  need to reference each other directly in dialogue - their only real
  connection is the shared `bandit_captain` target and, if things go
  wrong, the Road Warden's own `flag_dialogue` reaction to
  `stonebridge_raided` (see `data/dungeons/wayford/levels/level_01.lvl`).
