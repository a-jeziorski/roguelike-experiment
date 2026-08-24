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
still alive. Two towns, two independent quests, the same single
`bandit_captain` spawn at Broken Watch - killing him in time answers
both.

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

| Level | Name | Set pieces it holds |
|---|---|---|
| `level_01` | Stonebridge Ward | The Gate, The Lookout Nook, The Well, The Wall-Check Pair, The Watch |

## The named set pieces

### 1. The Gate

Unchanged in premise from the original shipped version - a single barred
gate, the only way in or out, with a short stub of road leading through
it before the town's plains terrain takes over (`player_start_tile:
road`, matching the terrain the player actually starts on). Everything
else in the bible orbits this one entrance, same "the wall is the town's
whole personality" logic the pitch establishes.

### 2. The Lookout Nook

A small enclosed post built directly into the gatehouse wall - an
arrow-slit landmark (`L`, already present in the original layout) with a
real, walled-in interior behind it now, instead of the landmark standing
alone in the open field. **`stonebridge_lookout`** (new entity,
`ai: villager`, `stationary: true`, title only per the project's naming
discipline) stands inside it, findable in exactly this one spot every
time - matching the precedent every other questgiver in the game
follows (`wayford_road_warden`'s post, Millhaven's chief).

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

### 4. The Wall-Check Pair

Two villagers, positioned together near the original layout's interior
wall clusters, both talking about the *maintenance* of the wall
specifically (checked every year before winter; the gate barred the
instant the sun sets, no exceptions for anyone still on the road) - the
"planned for, not panicked" competence the mood section calls for, made
audible instead of just implied by the `dungeon.yaml` description.

### 5. The Watch

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
