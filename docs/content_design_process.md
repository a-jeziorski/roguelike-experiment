# Content Design Process

How dungeon content gets designed for this project, captured from the
"dungeon deepening" pass that extended `level_03` into `level_04`/`level_05`
and reframed the whole run as one narrative arc, and extended again when the
project moved from one dungeon to a multi-dungeon system. Read this before
authoring new levels or retuning existing ones.

## 0. Multiple dungeons

Content is organized as one or more independent *dungeons*, not a single
global level pool - built this way specifically so the overworld (below)
could enumerate and cross between them. Each dungeon is a directory under
`data/dungeons/`:

```
data/dungeons/<dungeon_id>/
  dungeon.yaml       # id, name, starting_level, description
  levels/
    level_01.lvl
    ...
```

`content/loader.py` has three layers, matching this structure:
- `load_levels(levels_dir, catalog)` - loads and cross-validates one
  directory of `.lvl` files (a dungeon's own internal stairway references).
- `load_dungeon(dungeon_dir, catalog)` - one dungeon: its manifest plus
  `load_levels` on its `levels/` subdirectory, checking `starting_level`
  actually exists among them.
- `load_dungeon_registry(dungeons_dir, catalog)` - discovers and loads
  every dungeon under `data/dungeons/`, rejecting duplicate ids. This is
  what `main.py` calls at startup, and what a future overworld/dungeon-select
  screen would enumerate.

**The monster/item catalog (`data/entities.yaml`/`data/items.yaml`) is
global, not per-dungeon** - a deliberate simplification, not an oversight.
A dungeon references catalog ids the same way a level does; nothing yet
needs a dungeon-exclusive monster/item badly enough to justify per-dungeon
catalogs and the id-namespacing that would require. Reuse generic items
freely across dungeons (`rusty_key`/`healing_potion` work equally in a ruin
or a prison); keep flavor text that names one dungeon's setting specifically
(`bone_plate`'s "ossuary" description) out of the others, or write it more
generically if it needs to travel.

Level ids only need to be unique *within* a dungeon - `load_levels`
validates that scope, not across dungeons, so two dungeons can both have a
`level_01` with no conflict; they're never loaded together.

**Shipped dungeons (10, as of the "Populating the Sundered Realm" pass)**:

Combat dungeons:
- `prison_tower` - the current default starting dungeon (`main.py`'s
  `STARTING_DUNGEON_ID`); Old Kingdom remnants gone feral.
- `forgotten_ruins` - the original run, kept intact; Elder Age halls buried
  beneath an Old Kingdom manor.
- `broken_watch` - an Old Kingdom border garrison squatted by Opportunist
  bandits; fortified-compound geometry.
- `drowned_waystation` - a flooded Old Kingdom road-station; `sea` tiles
  mixed into dungeon rooms force route-around detours.
- `elder_cairn` - a standalone, deliberately vague Elder Age monument;
  sparse, symmetric geometry, `stone_sentinel`'s tank archetype.
- `sunken_mine` - a collapsed Old Kingdom mine; genuine winding-tunnel maze
  geometry, reuses the existing rat/goblin/skeleton roster with no new
  monsters.

Settlements (`requires_stairs_down: false`, peaceful-AI-only (`villager`/
`town_guard`), per 0c below):
- `millhaven` - the original settlement, a small waypoint green.
- `wayford` - a larger crossroads hub town, several building clusters.
- `stonebridge` - a fortified border town near `broken_watch`; tension
  lives entirely in flavor text, not mechanics.
- `saltmarsh` - a small coastal fishing hamlet near `drowned_waystation`.

This roster (and the world bible it's built from, `docs/world_history.md`)
came out of dispatching seven parallel subagents - one per new
dungeon/town - each briefed with the world bible and this document, and
scoped to write only inside its own `data/dungeons/<id>/` directory (see
that document's "Authoring convention" section for how independently-
authored content stayed consistent without the agents seeing each other's
work).

## 0b. The overworld

`data/overworld.lvl` is a single standalone file (not a directory - there is
exactly one overworld, unlike dungeons) reusing the ordinary `.lvl`
ASCII+legend format, loaded via `content/loader.py`'s `load_overworld`
rather than `load_level`. It has its own, smaller tile vocabulary -
`mountain`/`sea`/`forest`/`road`/`plains`/`town` terrain plus
`dungeon_entrance` tiles (`{dungeon_entrance: forgotten_ruins}`) - and
deliberately cannot contain the things a dungeon level can (entities, items,
doors, stairs): there is no combat or itemization on the overworld, and
`dungeon_entrance` is the only interactive tile, leading into a dungeon's
`starting_level` the same way stepping into the game does at a fresh run's
start. Symmetrically, a dungeon leaves *to* the overworld via a terminal
`stairs_down` (finishing it normally) or terminal `stairs_up` (retreating
early, placed near the entrance level's `player_start`) - both just mean
"leave this dungeon," differing only in flavor text.

Reuses the engine wholesale rather than a parallel system: `GameMap`/
`Engine`'s fog-of-war (`explored`/`visible`), the scrolling camera, and
walkable/transparent collision are exactly what a large hand-authored world
map needs, and "no combat" falls out for free from an entity-less map - the
turn loop's enemy-AI pass is already a no-op with nothing to iterate.
Terrain passability lives in `engine/game_map.py`'s `TILE_PASSABILITY`
table (kind -> walkable/transparent); a kind absent from it defaults to
ordinary open ground, so most new terrain needs no entry there at all -
only the exceptions (`mountain`, `sea`, `forest`) do.

Each dungeon (and the overworld) gets at most one live `Engine`, created on
first visit and cached thereafter in `main.py`'s `active_engines`, so
leaving a dungeon and returning later - via the overworld or directly -
resumes it exactly as left (dead monsters, picked-up items, explored
tiles), the same guarantee `visited_maps` already gives *within* one
dungeon, just one level up. Arrival is matched automatically on the
dungeon-to-overworld direction (land on whichever overworld tile's
`dungeon_entrance` targets the dungeon just left) and needs no matching at
all on the reverse direction (re-entering a dungeon just resumes wherever
the player last stood in it).

## 0c. Non-combat outdoor dungeons

A settlement (`data/dungeons/millhaven/`) is a "dungeon" only in the
registry sense - a `data/dungeons/<id>/` entry, entered/exited exactly like
Prison Tower or Forgotten Ruins. Nothing in `main.py`/`engine/engine.py`
needs to know or care what kind of place it is: `resolve_transition`, the
`wants_overworld`/`pending_dungeon_entry` mailbox flags, and
`depart_player`/`arrive_player` are all fully generic over any dungeon-
registry entry. Two things make it "peaceful" instead of a normal dungeon,
both content-only:

- `dungeon.yaml` sets `requires_stairs_down: false`. Every real dungeon
  keeps the default (`true`), which requires at least one `stairs_down`
  somewhere so a level always either goes deeper or is a deliberate
  ending. A settlement has no "deeper" - it only ever needs a single
  terminal `stairs_up` near `player_start` to leave. This is per-*dungeon*
  (the manifest), not per-level - `content/loader.py` threads it from
  `load_dungeon` through `load_levels` down to the one place it's actually
  checked in `load_level`. Setting it `false` still requires *some*
  stairway to exist (a level with none at all is rejected as a soft-lock -
  nothing would ever let the player leave); it only removes the
  `stairs_down`-specifically requirement.
- Its levels use outdoor terrain (`plains`/`road`, plus `wall` for building
  exteriors) instead of dungeon `wall`/`floor`, and spawn `villager`/
  `town_guard`-AI entities instead of monsters. Nothing about the loader
  restricts which `TileType`s can appear in an ordinary dungeon level - the
  overworld's terrain kinds were never exclusive to `load_overworld`, so
  this needed no schema change at all. Real building *interiors* were
  originally out of scope for a first pass; Millhaven's regeneration
  established the pattern once a real need showed up (giving the chief and
  shopkeeper an actual house each) - a small `wall`-bordered box with
  `floor`-kind interior and a single `floor`-kind gap in the perimeter as
  the doorway. Use `floor`, never `door`, for an ordinary house entrance:
  `door` (per its `LegendEntry` shorthand) always requires a key item to
  open, which is correct for a dungeon reward gate and wrong for someone's
  own front door.

`inspect_text` in `dungeon.yaml` (see 0b) is functionally load-bearing here,
not just polish: without it, inspecting the entrance falls back to
`"An entrance leading underground."`, which reads wrong for a town.

**`AI_VILLAGER`** (`content/schema.py`/`engine/engine.py` `_perform_ai`):
never fights back - no branch of it ever calls `resolve_attack`. While at
full HP it wanders (`Engine._wander`, untargeted random movement, unlike
every other AI type which moves at/away from the player); the moment it's
taken any damage at all (`fighter.hp < fighter.max_hp`), it flees and keeps
fleeing permanently. Contrast with `AI_SKITTISH`, which flees only *below*
a configurable `flee_hp_pct` threshold and otherwise fights normally -
skittish is "cowardly," villager is "never a combatant in the first
place." Don't reach for skittish when what's wanted is a true
non-combatant. The optional `stationary: bool` field (`EntityDef`, plain
bool default `False` - not the nullable-with-engine-fallback shape
`alert_radius`/`flee_hp_pct`/`ranged_range` use, since there's no fallback
constant for it) holds a villager in place instead of wandering while
undamaged; it still flees normally once hurt. Use it for an NPC whose
premise depends on being findable in one specific spot every time (a
shopkeeper, a chief - see Millhaven) rather than one who's fine wandering
their own patch of ground.

**`AI_TOWN_GUARD`** (`content/schema.py`/`engine/engine.py` `_perform_ai`):
also never *initiates* violence - like `AI_VILLAGER`, it just wanders while
peaceful. The difference is what governs the switch, and how far it
reaches: `AI_VILLAGER`'s flee trigger is *personal* (`fighter.hp <
max_hp`, checked per-entity); `AI_TOWN_GUARD`'s hostility trigger is
*shared and map-wide* (`GameMap.player_attacked_peaceful_npc`, set by
`engine/combat.py` the instant the player attacks *any* `PEACEFUL_AI_TYPES`
entity anywhere on the current map - villager or town_guard - and checked,
not owned, by every `AI_TOWN_GUARD` entity on that map). A town guard who
was never personally touched still turns hostile the moment anyone
provokes the town, and - unlike a fleeing villager - fights back
(`Engine._chase_and_attack`, same primitive `AI_HOSTILE_BASIC` uses) once
triggered, permanently for that map's lifetime. Use `town_guard` where a
settlement needs a real deterrent against violence, not just NPCs who run
away from it.

## 0d. Per-dungeon bibles (`docs/dungeon_bibles/`)

Feedback on the seven-subagent batch (see [[sundered_realm_worldgen_pass_one]]
memory) was that the results felt mechanically correct but thin - most
rooms read as "a room with N monsters" rather than as a specific place.
The working theory: `docs/world_history.md` is realm-level (which era,
which faction) and this document is mechanical (balance math, geometry
rules) - neither one forces anyone, agent or human, to decide what's
*actually in a given room* before drawing it. `docs/dungeon_bibles/`
holds the missing middle layer: one short document per dungeon, written
like a tabletop GM's site key, naming 3-5 specific set pieces (what's
physically there, why, what it's meant to make the player feel) before
any ASCII is drawn. `sunken_mine.md` was the first - rewritten from a
monster dungeon's own bible - and `millhaven.md` proved the same shape
works for a peaceful settlement too (set pieces there are NPC placements
and `landmark` tiles rather than monster encounters). No longer a trial:
**write the bible before touching a level's content**, whether authoring
new or revising existing, and fold it into the authoring checklist
(§4) below.

## 0e. Quests are content too (`data/quests.yaml`)

Quests follow the same "engine defines the shape, `data/` fills it in"
split as monsters and items: `content/schema.py`'s `QuestDef` is the raw
authored shape (validated field-by-field, and cross-referenced against the
catalog/dungeon registry by `content/loader.py`'s `load_quests`);
`engine/quest.py` owns the actual mechanics - what each trigger checks,
when a quest is granted, what a reward does - and turns a validated
`QuestDef` into a live `Quest` via `quest_from_def`/`create_quest_log`.
Adding a new quest never means touching `engine/quest.py` - it means
adding an entry to `data/quests.yaml`.

A quest completes via exactly one of four trigger shapes, picked by which
single field is set (`QuestDef` rejects setting more than one):

| Trigger field | Fires when | Checked in |
|---|---|---|
| `target_dungeon_id` | player arrives in that dungeon | `main.py`'s `resolve_transition` -> `QuestLog.check_dungeon_arrival` |
| `target_entity_id` | player talks to that catalog entity | `Engine.talk_to_adjacent` -> `QuestLog.check_talked_to` |
| `target_kill_entity_id` | that catalog entity dies (anywhere, any time - see `killed_entity_ids`) | `Engine.on_entity_death` -> `QuestLog.record_entity_killed` |
| `target_item_id` | player talks to `questgiver_entity_id` *while holding* a matching item | `Engine.talk_to_adjacent` -> `QuestLog.check_delivery` |

None is valid too, for a quest with no completion trigger authored yet.

`questgiver_entity_id` is a separate concept from the trigger: setting it
means the quest starts `starting_status: not_given` and is granted by
*talking* to that NPC (`QuestLog.check_questgiver`), rather than being
live from game start (`starting_status: in_progress`, no questgiver
needed - see `goblin_warning`). A `target_item_id` (fetch) quest always
needs a `questgiver_entity_id` too - delivery only ever completes by
talking to that NPC while holding the item - and `load_quests` rejects a
fetch quest missing one, along with a `not_given` quest missing one
(nothing else can ever grant it) and a bad entity/item/dungeon reference.
`deadline_year`/`deadline_day` must be set together or not at all.

Reward is `reward_item_id` (grants a catalog item straight into
inventory), `reward_shop_discount_pct` (a permanent fraction off
everything in the Millhaven shop, e.g. `0.2` for 20% off - see
`Engine.shop_price`), both, or neither.

Which quest is pinned to the HUD at game start is whichever comes first,
in `data/quests.yaml`'s key order, with `starting_status: in_progress` -
today only `goblin_warning` starts that way, so this can't yet surprise
anyone, but a second in-progress starting quest would make file order the
(silent) tiebreaker. Don't reorder `quests.yaml` casually once more than
one quest starts `in_progress`.

## 1. Narrative framing

Settle the throughline **before** drawing any map. The engine exposes four
story surfaces to the player: a level's `name` (shown in the HUD), an
entity/item's `description`, a per-legend-entry `description` that
overrides a *tile*'s generic look-mode text (e.g. `{stairs_up: null,
description: "The town gate, leading back out onto the road."}` instead of
the default "Stairs leading up."), and - for an `{entity: ...}` spawn
specifically - a per-spawn `dialogue`, what the `Talk` action shows for
*that one placement* (`{entity: villager, dialogue: "Well's held up better
than most things built before the Sundering."}`), distinct from
`description` on the same mapping (which is still the *tile's* look-mode
override, not the entity's - easy to conflate, see `content/schema.py`'s
`LegendEntry` docstring). The first three are shown in look mode via
`engine/render.py` `describe_tile`; `dialogue` is shown by pressing `T`
next to the NPC (`Engine.talk_to_adjacent`) - still no separate lore/
dialogue *tree* or branching-conversation system, and there shouldn't be
one added just to tell a story (see `flee_hp_pct` gotcha below for what
happens when content assumes mechanics the engine doesn't have); `dialogue`
is one more flat line per NPC, same discipline as everything else here. A
villager with no per-spawn `dialogue` falls back to its catalog type's own
default (`EntityDef.dialogue` - `villager`'s is a generic "they don't have
much to say," so an un-authored NPC elsewhere in the game still says
*something* sensible rather than nothing). A tile's custom `description`,
when set, always wins over its kind's default and over a
`dungeon_entrance`'s dungeon-level `inspect_text` (0b) - most specific
wins.

**For a walkable point of interest, use `tile: landmark`, never
`tile: floor` (or `road`/`plains`/etc.) with a `description` bolted on.**
A `floor`-kind tile with a custom description still *renders* identically
to every other floor tile - nothing tells the player to stop and look, so
the flavor is invisible until they happen to step on that exact cell.
`landmark` (`engine/render.py` `TILE_VISUALS`) renders with its own
apostrophe glyph and a muted color distinct from both plain floor and the
saturated entity/item glyphs, specifically so a point of interest is
visible on the map before it's read. First added after playtesting the
Sunken Mine's bible-driven set pieces (the weighing counter, the ledger)
turned out invisible under `tile: floor`.

**A quest's premise has to actually grant the player character access to
whatever they're meant to convey - independent of which action triggers
completion.** The starting quest originally had the player carrying a
*sealed letter* (meaning, by definition, they were never privy to its
contents) that was then lost during capture, but completed by having them
*tell* the chief what it said - two compounding errors, not one: no
object to hand over, and no way to have known the contents even if they
still had it. Shipped once before being caught in review and rewritten
into a warning the player was told directly, not sealed
(`docs/dungeon_bibles/millhaven.md`'s Tone notes has the full story). The
lesson isn't "`Talk`-completed quests need verbal content and
dungeon-arrival ones need physical content" - a delivery quest completing
via `Talk` (handing over an intact letter, say) is entirely fine. The
actual check: does the player character canonically *know* or *possess*
what the quest has them convey? A sealed/written document means they
carry it unopened and hand it over intact, never narrating what's inside;
something spoken or witnessed directly means they genuinely know it and
can convey it however the fiction calls for. Run this check whenever a
quest's premise and its completion beat are being written together, not
just at the "does this line sound right" stage.

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

A second worked example, `prison_tower` - framed to fit the engine as it
exists (only a `stairs_down` tile type exists, there's no "climb up", and
adding one would be an engine change, not a content one) by making the
descent itself the escape - start deep/high in solitary, descend through
less-secure floors toward the exit:

| Level | Name | Beat |
|---|---|---|
| `level_01` | The Solitary Cell | starting cell, already broken open |
| `level_02` | The Guard Barracks | guards, a reward-gated armory |
| `level_03` | The Lower Cellblock | feral prisoners, vermin, resupply |
| `level_04` | The Gatehouse | the warden, then freedom (terminal) |

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
  (`level_01`, `level_04`). `content/loader.py` validates this mechanically
  now, not just by convention: `load_level` rejects a door if every tile
  next to it is already reachable from `player_start` without a key
  (8-directional, matching the player's actual corner-cutting diagonal
  movement - a route that's only reachable by cutting a corner still
  counts as a bypass). Caught a real bug this way in an earlier revision of
  `sunken_mine/level_01`, where a side corridor accidentally reconnected to
  the far side of a locked door one tile past it. If a *long detour*
  around a door is ever wanted as a deliberate design (a shortcut-door
  pattern, distinct from every reward gate used so far), this check would
  need to be relaxed for that specific case - it currently assumes every
  door fully encloses what's behind it, matching every door in this
  project to date.
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
  needs to feel big. First applied throughout `prison_tower` (a narrow
  cell-exit corridor forcing a chokepoint, a reward room reachable only
  through a locked door, a four-cell cellblock, a gatehouse broken up by
  interior pillars instead of one bare rectangle) - `forgotten_ruins`'
  `level_03`/`level_05` are still the un-revisited single-open-room
  originals this feedback was about; a future pass through that dungeon
  specifically should fix them the same way.

- **Level size is no longer console-bound**: rendering goes through a
  scrolling camera viewport (`engine/render.py` `compute_camera`,
  `VIEWPORT_WIDTH`/`VIEWPORT_HEIGHT`) that follows the player and clamps at
  the map's edges, with the HUD/message log anchored at a fixed row below
  it. A level can be wider or taller than the console now - the viewport
  scrolls to it - so row width no longer needs to target a specific console
  size, just whatever the layout actually needs. (Small levels render
  exactly as before: the camera never scrolls for a map no bigger than the
  viewport.)

- **Stairs can now go both ways** (`content/schema.py`/`content/loader.py`
  `stairs_up`, arrival matching in `engine/engine.py`
  `Engine._arrival_position`): a level can place a `{stairs_up: level_id}`
  tile alongside its `stairs_down` ones. Revisiting a level via either
  direction is the *same* `GameMap` (dead monsters stay dead, picked-up
  items stay gone, unlocked doors stay unlocked, explored tiles stay
  explored) - not a fresh respawn, so a `stairs_up` genuinely means "go
  back," not "reset." Arrival position is matched automatically: entering a
  level from level X lands the player on whichever of that level's
  stairways (up or down) targets X back, not on `player_start` - so a
  level only needs *one* stairway per neighboring level, authored in
  whichever direction fits the fiction (the loader rejects two stairways
  to the same destination as ambiguous). `player_start` still matters for
  the dungeon's own starting level and as the fallback when no return
  stairway exists. Not every `stairs_down` needs a matching `stairs_up` -
  a deliberate one-way level is still a legitimate choice - but when a
  return trip makes narrative sense (backtracking to a hub, escaping back
  the way you came), it's now cheap: one legend entry, no other content
  changes. First used in `prison_tower/level_02`, which added a
  `stairs_up` back to `level_01`.

## 4. Authoring checklist

0. **Bible**: write (or, for a revision, re-read) that dungeon's
   `docs/dungeon_bibles/<id>.md` before touching any `.lvl` file - see 0d.
   3-5 named set pieces, tied explicitly to `world_history.md`'s eras/
   factions, decided before any ASCII is drawn.
1. **Layout**: reuse proven row geometry from an existing
   `data/dungeons/*/levels/*.lvl` file, or build new rows programmatically
   (concatenate segments of known length, assert the total is 24 before
   writing the file - this is what caught every width mistake made while
   authoring `prison_tower`, faster than hand-counting characters). Default
   to multi-room/corridor composition (per the geometry-variety note above);
   reach for a single open room only when the level specifically wants an
   "arena" beat, not as the easy default.
2. **Placements**: exactly one `player_start`, at least one `stairs_down`,
   monsters (with AI chosen deliberately per the pacing guidance above),
   items (checked against the balance methodology above).
3. **Flavor text**: level `name` and every entity/item `description` fit
   the narrative arc - these are the only things the player actually reads.
   For an `AI_VILLAGER` NPC specifically, also consider a per-spawn
   `dialogue` (see §1) - not every villager needs one, but a named set
   piece built around one probably does.
4. **Validate**: `python tools/preview.py data/dungeons` - reviews every
   shipped dungeon's rendering, stairway destinations, and door/key pairings
   at once (or point it at one `data/dungeons/<id>` while iterating on a
   single dungeon), and is how loader validation errors (bad references,
   ragged rows, missing stairs) get caught before anything runs.
5. **Test and playtest**: `pytest`, then `python main.py` to actually feel
   out pacing and difficulty - the math in step 2 is a sanity check, not a
   substitute for playing it. `main.py` always starts
   `STARTING_DUNGEON_ID`; edit that constant (or use `load_dungeon_registry`
   directly) to playtest a dungeon that isn't the current default.
