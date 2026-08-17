# Content Design Process

How dungeon content gets designed for this project, captured from the
"dungeon deepening" pass that extended `level_03` into `level_04`/`level_05`
and reframed the whole run as one narrative arc. Read this before authoring
new levels or retuning existing ones.

## 1. Narrative framing

Settle the throughline **before** drawing any map. The engine only exposes
two story surfaces to the player: a level's `name` (shown in the HUD) and an
entity/item's `description` (shown in look mode, `engine/render.py`
`describe_tile`). Everything narrative has to work through those two fields
- there's no separate lore/dialogue system, and there shouldn't be one added
just to tell a story (see `flee_hp_pct` gotcha below for what happens when
content assumes mechanics the engine doesn't have).

Current arc, as a worked example - one continuous descent through
progressively older ruins beneath a manor's basement:

| Level | Name | Beat |
|---|---|---|
| `level_01` | The Rotting Cellar | mundane decay, present-day squatters |
| `level_02a` | The Flooded Crypt | older burial ruins, path A |
| `level_02b` | The Goblin Warren | older burial ruins, path B |
| `level_03` | The Sunless Throne | a seat of old power - looks like the end, isn't |
| `level_04` | The Elder Ossuary | older still, bone-filled |
| `level_05` | The First Ruin | the true bottom, origin of everything above |

Each name alone should signal escalating age/depth even out of context. If a
new level's name doesn't obviously slot into the arc, the arc needs
revisiting before the level does.

## 2. Balance methodology

Damage is `max(0, attacker.effective_attack - defender.effective_defense)`
(`engine/combat.py`). Player baseline is `PLAYER_MAX_HP`/`PLAYER_ATTACK`/
`PLAYER_DEFENSE` in `engine/game_map.py` (30/5/1 as of this writing).
`effective_attack`/`effective_defense` (`engine/entity.py`) add the
equipped weapon's `attack_bonus` / equipped armor's `defense_bonus` on top
of that baseline - equipment is one weapon and one armor slot, swap-if-
better (picking up a worse item leaves it on the ground; a better one
replaces and drops the old one), not a stack. Potions (`heal_amount`) are
consumed on use, not equipped. Current tiers: weapons `rusty_dagger` (+2),
`iron_sword` (+4); armor `leather_armor` (+1), `bone_plate` (+3) - mirror
this two-tier shape for any new equipment rather than inventing a third
tier casually, to keep the gear curve legible.

A ranged weapon is a *third*, independent slot (`equipped_ranged_weapon`,
`effective_ranged_attack`) - carried alongside a melee weapon, not instead
of one - and its ammo (`is_ammo`/`quantity` on the item) is a separate
consumable resource from everything above, tracked as a stack rather than
one entity per shot. `hunting_bow` (+3, range 5) is the only ranged weapon
so far; if more are added, keep them to the same two-tier discipline as
melee/armor. Ranged weapons change encounter design more than a straight
stat bump would: they let the player soften or kill a target *before*
melee range, which specifically undercuts `sleeping_guard`'s whole premise
(the guard never gets to wake up and close the distance) and reduces
`skittish`'s flee window (no need to chase a fleeing target down at all).
Account for this when placing guard/skittish encounters near or after a
point in the dungeon where the player likely has a bow equipped.

**Work out hits-to-kill in both directions** before placing a monster:
`player_attack - monster.defense` and `monster.attack - player.defense`,
against current `data/entities.yaml` stats. This is what caught the ogre
being a ~14-hit slog at base stats (`8` attack, `3` defense, `28` hp) - not
a bug, but it means the ogre should never be the *first* though fight a
player can reach without a weapon upgrade already in hand.

**Check gear fairness across branching paths specifically.** Two branches
that never reconverge can each be internally balanced and still create a
problem: `level_02a` (Flooded Crypt) offers no weapon at all, only a potion,
while `level_02b` (Goblin Warren) has the `iron_sword`. That's a fine
risk/reward asymmetry between two *parallel* paths - but both eventually
funnel into the same `level_03` -> `level_04` -> `level_05` continuation, so
a player who took 02a would otherwise never see a weapon upgrade before the
endgame. Fix used here: place a second `iron_sword` in `level_04`, past the
convergence point, rather than editing the branches (which would have
erased the intentional asymmetry). General rule: **audit item availability
at every point where paths reconverge**, not just within each branch.

**The flee-threshold gotcha** (see memory `balance_flee_hp_threshold`):
`skittish` monsters only check `hp/max_hp <= flee_hp_pct` on their own turn,
*after* the player's hit that round has already landed. If `max_hp` is low
enough that one hit can drop the monster straight through the threshold to
0, the flee behavior is dead content - it never triggers. Give any
`skittish` monster enough `max_hp` to survive at least one expected player
hit with room below that to spare before `flee_hp_pct` kicks in.

## 3. Structural design

- **Linear vs. branching**: a branch should represent a real choice (see
  02a/02b) - two distinct encounters/tones, not the same content twice with
  reskinned monsters. Converge branches back to a shared level rather than
  running parallel chains indefinitely; use the convergence point to correct
  any fairness gap the branches created (see balance methodology above).
- **AI variety as a pacing tool, not decoration** (`content/schema.py`
  `AIType`, dispatch in `engine/engine.py` `_perform_ai`):
  - `hostile_basic` - a straightforward combat encounter, use for anything
    meant to just be fought.
  - `sleeping_guard` - rewards caution/careful movement; use where the level
    wants the player to feel like they're *sneaking* rather than clearing.
  - `skittish` - rewards controlled, deliberate aggression and punishes
    overkill; use for weak/numerous creatures where a chase would be more
    interesting than a guaranteed kill.
- **Locked doors/keys are reward gates, not path gates**: place them off the
  critical path, guarding a bonus item, so a level is always completable
  without finding the key. Every door/key pair used so far follows this
  (`level_01`, `level_04`).
- **Geometry variety, not just encounter variety** (playtest feedback on the
  6-level dungeon): `level_03` and `level_05` are a single open room each -
  noticeably less interesting than the multi-room `level_01`/`02a`/`02b`/
  `04` layouts, which force sequential encounters and give monsters
  somewhere to be a sleeping guard *around a corner* rather than just
  standing in an open field. A single open room is fine as an occasional
  "arena" beat but shouldn't be the default template - favor multiple
  connected rooms, corridors, and chokepoints even for "boss room" levels
  (e.g. an antechamber before the room with the real fight, an L-shaped or
  multi-chamber throne room instead of one rectangle). Treat "single open
  room" as a deliberate, occasional choice, not the fallback when a level
  needs to feel big.

## 4. Authoring checklist

1. **Layout**: reuse proven row geometry from an existing `data/levels/*.lvl`
   file - copying known-good rows and only substituting symbols at specific
   positions avoids the width-mismatch mistakes hand-drawing a grid from
   scratch invites. Default to multi-room/corridor composition (per the
   geometry-variety note above); reach for a single open room only when the
   level specifically wants an "arena" beat, not as the easy default.
2. **Placements**: exactly one `player_start`, at least one `stairs_down`,
   monsters (with AI chosen deliberately per the pacing guidance above),
   items (checked against the balance methodology above).
3. **Flavor text**: level `name` and every entity/item `description` fit
   the narrative arc - these are the only things the player actually reads.
4. **Validate**: `python tools/preview.py data/levels` - reviews the whole
   dungeon's rendering, stairway destinations, and door/key pairings at
   once, and is how loader validation errors (bad references, ragged rows,
   missing stairs) get caught before anything runs.
5. **Test and playtest**: `pytest`, then `python main.py` to actually feel
   out pacing and difficulty - the math in step 2 is a sanity check, not a
   substitute for playing it.
