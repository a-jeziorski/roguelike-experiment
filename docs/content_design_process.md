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
*shared and map-wide* (`GameMap.guards_hostile`, armed by
`GameMap.trigger_guard_hostility` - called from `engine/combat.py` the
instant the player attacks *any* `PEACEFUL_AI_TYPES` entity anywhere on the
current map, villager or town_guard - and checked, not owned, by every
`AI_TOWN_GUARD` entity on that map). A town guard who was never personally
touched still turns hostile the moment anyone provokes the town, and -
unlike a fleeing villager - fights back (`Engine._chase_and_attack`, same
primitive `AI_HOSTILE_BASIC` uses) once triggered.

That hostility isn't permanent by default: `guards_hostile` clears itself
`GameMap.HOSTILITY_COOLDOWN_DAYS` (7) after the *most recent* provocation
(`GameMap.hostility_expires_at`, compared against `Engine.clock` - since
the world clock only advances while the player is standing on the
overworld itself (§0j), the cooldown only actually counts down while the
player is out there, not idling inside the provoked settlement itself) -
a second provocation while the first cooldown is still running
overwrites it with a fresh window rather than stacking, same "most recent
wins" convention `QuestLog.arm_encounter` already uses for a re-armed
encounter timer. The one exception: if a `PEACEFUL_AI_TYPES` entity is
actually *killed* on that map (`Engine.on_entity_death` ->
`GameMap.mark_peaceful_npc_murdered`), hostility there never expires again
- intimidation is forgivable on a clock, murder isn't. Use `town_guard`
where a settlement needs a real deterrent against violence, not just NPCs
who run away from it.

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

A quest completes via exactly one of five trigger shapes, picked by which
single field is set (`QuestDef` rejects setting more than one):

| Trigger field | Fires when | Checked in |
|---|---|---|
| `target_dungeon_id` | player talks to `questgiver_entity_id` *after* arriving in that dungeon (any time - see `visited_dungeon_ids`) | `Engine.talk_to_adjacent` -> `QuestLog.check_dungeon_report` |
| `target_entity_id` | player talks to that catalog entity | `Engine.talk_to_adjacent` -> `QuestLog.check_talked_to` |
| `target_kill_entity_id` | player talks to `questgiver_entity_id` *after* that catalog entity has died (anywhere, any time - see `killed_entity_ids`) | `Engine.talk_to_adjacent` -> `QuestLog.check_kill_report` |
| `target_item_id` | player talks to `questgiver_entity_id` *while holding* a matching item | `Engine.talk_to_adjacent` -> `QuestLog.check_delivery` |
| `target_intimidate_entity_id` | player talks to `questgiver_entity_id` *after* attacking (not killing) that peaceful catalog entity (see `intimidated_entity_ids`) - see §0l for the full shape, including its unique immediate-failure path | `Engine.talk_to_adjacent` -> `QuestLog.check_intimidate_report` |

None is valid too, for a quest with no completion trigger authored yet.
The dungeon-arrival, kill, fetch, and intimidate shapes are all
deliberately two steps, not one: the deed itself (arriving, the kill, the
pickup, the hit) only records that it happened
(`QuestLog.record_dungeon_arrival`/`record_entity_killed`/
`record_entity_intimidated`, or an ordinary `PickupAction` with no special
case) - only reporting back to `questgiver_entity_id` actually completes
the quest and, for a fetch quest, removes the item from inventory. Talk
(`target_entity_id`) is the one trigger that stays single-step - talking
*is* the deed, there's nothing to split it from. One exception across all
four two-step shapes: if the target was already dead/visited/intimidated
*before* the quest was ever granted, `check_questgiver` jumps straight to
"completed" the moment it's granted (talking to the questgiver in that
case is itself the report) - see `already_done_message`. Intimidate has no
symmetric retroactive *failure* case (target already dead before the
quest is granted) - see §0l.

`questgiver_entity_id` is a separate concept from the trigger: setting it
means the quest starts `starting_status: not_given` and is granted by
*talking* to that NPC (`QuestLog.check_questgiver`), rather than being
live from game start (`starting_status: in_progress`, no questgiver
needed - see `goblin_warning`). A `target_item_id` (fetch),
`target_kill_entity_id` (kill), `target_dungeon_id` (dungeon-arrival), or
`target_intimidate_entity_id` (intimidate) quest always needs a
`questgiver_entity_id` too - all four only ever complete by talking to
that NPC - and `load_quests` rejects any of them missing it, along with a
`not_given` quest missing one (nothing else can ever grant it) and a bad
entity/item/dungeon reference. `deadline_year`/`deadline_day` must be set
together or not at all.

**Quest chains**: `requires_quest_id` names another quest's id that must be
`completed` before this one is ever granted by `QuestLog.check_questgiver` -
a `not_given` quest with it set is silently withheld (the questgiver's
normal line plays, nothing else happens) until the prerequisite completes,
and stays withheld forever if the prerequisite instead ends `failed` (a
missed deadline never gets a second chance at whatever it was gating). Only
meaningful alongside `questgiver_entity_id` (`load_quests` rejects it
without one), and `load_quests` also rejects an unknown or self-referencing
id. Granting the chained quest needs a Talk *after* the one that completes
its prerequisite, never the same one - `check_questgiver` runs before
`check_talked_to`/`check_delivery`/`check_kill_report`/`check_dungeon_report`
inside `Engine.talk_to_adjacent`, so the prerequisite's status hasn't
flipped yet within that same call. See `spreading_the_warning` for the
first real chain (gated on `goblin_warning`), and note the
`QuestLog.followup_dialogue` consequence it surfaced: once an NPC is
involved in two quests with done-dialogue lines, `followup_dialogue`
prefers the later-defined one in `data/quests.yaml` - correct for an
actual chain (completion order is forced to match file order), only a
heuristic for two unrelated quests sharing an NPC coincidentally (see that
method's own docstring for the scope limit).

Reward is any combination of `reward_item_id` (grants a catalog item
straight into inventory), `reward_gold_amount` (adds straight to the
player's gold stat - the correct way to reward gold from a quest; don't
reach for `reward_item_id` pointed at a `gold_amount` item, which bypasses
`PickupAction._collect_gold` and would sit inert in inventory instead -
see `ItemDef.gold_amount`'s own comment in `content/schema.py`), and
`reward_shop_discount_pct` (a permanent fraction off everything sold by
one specific shop, e.g. `0.2` for 20% off - see `Engine.shop_price`), or
none at all. `reward_shop_discount_pct` always needs
`reward_shop_discount_entity_id` set alongside it - the catalog entity id
of the shopkeeper this discount applies to (`load_quests` rejects one
without the other, and rejects an entity id with no `shop_inventory`) -
so completing a discount quest never silently discounts every shop in the
game, only the one it names. No shipped quest currently combines more
than one reward shape, but nothing stops it.

Which quest is pinned to the HUD at game start is whichever comes first,
in `data/quests.yaml`'s key order, with `starting_status: in_progress` -
today only `goblin_warning` starts that way, so this can't yet surprise
anyone, but a second in-progress starting quest would make file order the
(silent) tiebreaker. Don't reorder `quests.yaml` casually once more than
one quest starts `in_progress`.

**The quest log's detail pane isn't stuck on `description` forever.**
`Quest.current_description` (`engine/quest.py`) resolves what to actually
show against the quest's live progress, and five optional overrides let
content say more as a quest moves along - any left unset ("") just keeps
showing `description` at that stage:

| Override | Shown when |
|---|---|
| `completed_description` | `status == "completed"` - a summary of what happened and what was earned, not just the original pitch |
| `failed_description` | `status == "failed"` - only meaningful alongside a deadline, `voided_by_dungeon_id`, or `target_intimidate_entity_id`, since those are the only ways a quest ever fails; `load_quests` rejects it otherwise |
| `carrying_item_description` | a fetch quest (`target_item_id`), still `in_progress`, while the target item is actually in the player's inventory (not yet delivered) - only meaningful alongside `target_item_id`; `load_quests` rejects it otherwise |
| `target_dead_description` | a kill quest (`target_kill_entity_id`), still `in_progress`, while the target's actually been recorded dead (not yet reported) - only meaningful alongside `target_kill_entity_id`; `load_quests` rejects it otherwise |
| `target_visited_description` | a dungeon-arrival quest (`target_dungeon_id`), still `in_progress`, while the target dungeon's actually been recorded visited (not yet reported) - only meaningful alongside `target_dungeon_id`; `load_quests` rejects it otherwise |
| `target_intimidated_description` | an intimidate quest (`target_intimidate_entity_id`), still `in_progress`, while the target's actually been recorded intimidated (not yet reported) - only meaningful alongside `target_intimidate_entity_id`; `load_quests` rejects it otherwise; see §0l |

Write these whenever a quest's premise would otherwise go stale in the
log - `fetch_fungus` is the fullest fetch example (starting pitch ->
`carrying_item_description` once the fungus is picked up ->
`completed_description` naming the discount once delivered),
`kill_the_warden`/`clearing_the_watch_road` are the kill-quest equivalent
(starting pitch -> `target_dead_description` once the kill lands ->
`completed_description` once reported), and `word_down_the_road` is the
dungeon-arrival equivalent (starting pitch -> `target_visited_description`
once Millhaven's been reached -> `completed_description` once reported).

## 0f. Shops are content too (`EntityDef.shop_inventory`)

Unlike quests, a shop doesn't need its own content type - it's entirely a
property of the NPC selling things. Any catalog entity in
`data/entities.yaml` with a non-empty `shop_inventory` (a list of item
ids) is a shopkeeper: `Engine.adjacent_shopkeeper` finds whichever one is
next to the player by that field, not by any hardcoded catalog id, so a
new town's own shopkeeper (its own entity, its own stock) works with no
engine change. `load_catalog` validates every `shop_inventory` entry the
same way a level's legend gets validated: each item id must exist in
`data/items.yaml` and have `cost` set (a shop item with no cost would
silently sell for free), and `shop_inventory` is only meaningful on a
peaceful NPC (`ai: villager` or `town_guard`) - `PEACEFUL_AI_TYPES` is the
only set of AI types `adjacent_shopkeeper` ever scans, so a hostile
monster with a `shop_inventory` would be dead content, and is rejected as
such. Price itself still lives on `ItemDef.cost`, not on the shopkeeper -
a fact about the item, not about any one seller, so multiple shopkeepers
selling the same item charge the same base price. A completed
`reward_shop_discount_pct` quest only modulates that price at the one
shopkeeper named by its `reward_shop_discount_entity_id` (see
`QuestLog.shop_discount_pct`, keyed by `Entity.entity_id`) - a discount
quest scoped to one shop never affects any other shop's prices, per the
quests section above.

## 0g. Overworld encounters are content too (`data/encounters.yaml`)

A scripted event that pulls the player off the overworld map into a
dedicated combat encounter, gated on quest progress - `EncounterDef`
(`content/schema.py`), loaded by `content/loader.py`'s `load_encounters`
the same collect-all-errors way as every other content type. One field
shape:

```yaml
warning_ambush:
  trigger_dungeon_id: millhaven      # must depart THIS dungeon for the overworld
  gate_quest_id: spreading_the_warning
  gate_quest_status: in_progress     # default - the quest's live status must equal this
  encounter_dungeon_id: goblin_ambush  # a real dungeon-registry entry to redirect into
  delay_hours: 3                     # default - overworld hours after arming before it fires
  encounter_message: "Goblins break from the treeline ahead..."  # optional - logged when it fires
```

`gate_quest_id`/`gate_quest_status` are deliberately **not** named
`requires_quest_id`/`requires_quest_status` despite the surface similarity
to `QuestDef.requires_quest_id` (the quest-chain prerequisite, above) -
that field means "must be `completed`, checked once at grant time"; an
encounter's gate means "must currently equal this status, checked on every
departure from `trigger_dungeon_id`" - different enough semantics that
sharing the name would mislead a future reader. `load_encounters` requires
(not just optionally cross-checks, unlike `load_quests`' `known_dungeon_ids`)
that `trigger_dungeon_id`/`encounter_dungeon_id` are both real dungeon ids
and `gate_quest_id` is a real quest id - an encounter that could never fire
is worth catching at content-load time.

`encounter_dungeon_id` is a real dungeon-registry entry, loaded and
validated exactly like any other dungeon (`load_dungeon_registry` has no
"must be reachable from the overworld" requirement) - it's just
**deliberately never pointed at by any overworld `dungeon_entrance` tile**,
so the only way in is through the trigger.

Firing is a two-step arm-then-fire sequence, not instant - `main.py`'s
`resolve_transition`/`_armable_encounter`/`_due_encounter` do the work:
departing `trigger_dungeon_id` with the gate quest at `gate_quest_status`
*arms* a `delay_hours`-long timer (`QuestLog.armed_encounters`/
`arm_encounter`), and the player is only actually redirected into
`encounter_dungeon_id` once that many hours have elapsed **on the
overworld specifically** - `Engine.process_enemy_phase` only ever advances
`GameClock` while `is_overworld` is true, so time spent inside a different
dungeon in between doesn't count toward the delay. Re-departing
`trigger_dungeon_id` before an armed timer fires restarts the countdown
from that later departure ("counted from your most recent departure," not
the first ever one) - `arm_encounter` always overwrites the due-time.
`_redirect_into_encounter` uses the player's *current* overworld position
at fire time (not wherever they originally entered from) for
`Engine.overworld_return_position`, since they may have walked anywhere
during the delay - fleeing the encounter later returns them to wherever
the ambush actually caught up with them, not back at the entrance they
left through. `QuestLog.triggered_encounter_ids` (same shape as
`killed_entity_ids`/`visited_dungeon_ids`) ensures an encounter only ever
fires once per run, checked by both `_armable_encounter` (never re-arms)
and `_due_encounter` (never fires an already-triggered id even if some
stale armed-entry lingers). `encounter_message`, if set, is logged right
after firing - the generic "You enter `<level_name>`." line every dungeon
arrival gets doesn't explain *why* the player was just pulled off the
overworld, so an encounter worth noticing should say so explicitly rather
than leaving the player to infer an ambush from context.

Nothing about the encounter dungeon itself is special content-wise - it's
authored exactly like any other dungeon (per-dungeon bible first, §0d, no
exception for a small map), and per the user's explicit choice for
`goblin_ambush`, an encounter isn't a lock: it's leavable at any time, win
or not - originally via a terminal `stairs_up` tile, since generalized into
`open_boundary` (§0h below), which reads better for an outdoor clearing
than a stairway ever did. See that dungeon's own bible for the
chokepoint-geometry reasoning (§2's balance methodology applies to an
encounter exactly as it would to any other first multi-monster fight).

## 0h. Open-boundary levels (`LevelDef.open_boundary`)

For an outdoor level where a stairway tile would read wrong - there's no
literal staircase in a forest clearing - `open_boundary: true` makes every
edge of the level's map a valid way to leave, the way a real patch of
wilderness would just continue past what's actually drawn, instead of
needing one specific tile. `content/loader.py`'s `load_level` propagates it
from `LevelDef` into `ParsedLevel`, `engine/game_map.py`'s `build_game_map`
copies it onto the runtime `GameMap`, and `engine/actions.py`'s
`MovementAction` checks it the moment the player's destination falls
outside `GameMap.in_bounds` (previously indistinguishable from "walked into
a wall," which returned False from `is_walkable` either way) - calling
`Engine.on_player_reach_map_edge`, the open-area equivalent of
`on_player_reach_stairs(None, ...)`: same `wants_overworld` mailbox
`main.py`'s `resolve_transition` already consumes generically, so nothing
in `main.py` needed to change for this to work, including composing for
free with an overworld encounter's `overworld_return_position`.

Authoring one needs no new legend syntax: just don't wall in the
perimeter - leave the outermost ring of tiles as ordinary walkable terrain
(`plains`/`forest`, whichever fits the scene) instead of `wall`, and the
grid's own edge becomes the exit. `load_level` enforces two things about
this: `open_boundary: true` still needs *some* way to reach an edge (a
level with `open_boundary: true` but a fully-walled perimeter is rejected
as dead content, the same "shop item with no cost" class of check as
elsewhere in this loader), and `open_boundary` counts as satisfying the
existing "a `requires_stairs_down: false` level needs some way to leave"
soft-lock check on its own - a level can have `open_boundary: true` and
zero stairs and still be valid content. `open_boundary_message` (optional,
falls back to a generic engine default - `_DEFAULT_OPEN_BOUNDARY_MESSAGE`,
`engine/engine.py`) is logged the moment the player actually leaves, same
role as `EncounterDef.encounter_message` above: explain what just happened
rather than leaving a bare, unexplained transition.

`goblin_ambush` is the reference example - see its own dungeon bible for
how the chokepoint geometry stays intact (the internal wall partition is
unaffected; only the *outer* perimeter opened up) and why `player_start`
sits a couple tiles inboard of the now-open edge rather than directly
against it.

## 0i. Player-start terrain (`LevelDef.player_start_tile`)

`engine/game_map.py`'s `build_game_map` never lets a live `player_start`
kind reach the runtime `GameMap` - it always substitutes something
walkable, defaulting to `floor`. That default is fine for an indoor
dungeon where `floor` is already the ambient ground everywhere, but reads
as a visible seam on an outdoor or terrain-textured level: a town square
authored in `plains`, or a gate corridor authored in `road`, gets one
mismatched `floor` tile sitting exactly where the player starts, which
becomes obvious the moment they step off it.

`player_start_tile: <kind>` on the level file overrides the substitution -
set it to whatever terrain kind actually surrounds the `player_start`
symbol on the map (`plains` for an open clearing/town square, `road` for a
gate, `forest`, etc.). `content/schema.py` rejects anything unwalkable
(`wall`/`door`/`mountain`/`sea`) or special-purpose
(`stairs_down`/`stairs_up`/`dungeon_entrance`/`player_start` itself) at
load time, the same "fail loudly at content-load time" posture as every
other cross-checked field here. Every outdoor/settlement level authored so
far (`goblin_ambush`, the overworld, and every town's `level_01`) sets
this; a plain indoor dungeon floor can leave it at the default.

## 0j. Timed world consequences (`QuestDef.on_fail` / `voided_by_dungeon_id`)

A quest deadline (`QuestDef.deadline_year`/`deadline_day`,
`QuestLog.check_deadlines`) can do more than log a failure message: set
`on_fail: [<WorldConsequence>, ...]` on the quest, and missing the
deadline fires every consequence in that list, in order, the instant it's
crossed (`Engine._apply_world_consequences`, called from
`Engine._check_quest_deadlines`). `on_fail` is a *list* specifically so one
missed deadline can trigger more than one consequence - e.g. razing a
dungeon and separately recording a flag - rather than being limited to a
single effect. Each entry is a `WorldConsequence` (`content/schema.py`)
with exactly one of three actions set (validated - a `WorldConsequence`
with more than one, or none, is rejected at load time):

- `destroy_dungeon_id: <dungeon_id>` - razes that dungeon's overworld
  entrance (see `Engine.destroy_dungeon`, `engine/game_map.py`'s
  `apply_dungeon_destruction`). The target dungeon's own manifest
  describes what's left: `DungeonDef.ruined_tile`/`ruined_description`
  (both-or-neither, validated) replace its entrance tile and look-mode
  text, the same way `inspect_text` already describes it intact - pick
  `ruined_tile` to match whatever terrain the entrance already sits
  against on the overworld map (same reasoning as `player_start_tile`
  above), not a generic default. `content/loader.py` cross-checks that
  any dungeon named by an `on_fail` entry's `destroy_dungeon_id` actually
  has `ruined_tile` set, so a wired-up consequence with no authored ruins
  content fails at load time rather than silently doing nothing in play.
- `set_flag: <name>` - records that name, permanently, in
  `QuestLog.world_flags`. It exists so a consequence can record "something
  happened" without also having to be a dungeon destruction. Flag-
  conditional dialogue (`FlagDialogue`, §0k below) is the first thing that
  reads `world_flags` back - shop and level variants remain future work.
- `tighten_deadline: {quest_id: <id>, new_day: <day>}` - shortens
  *another* quest's own `deadline_day` (`Engine._tighten_deadline`), never
  extends it (a `new_day` later than the target's current deadline is a
  silent no-op). Works even if the target quest is still `not_given` - a
  tightened deadline is waiting for the player the moment it's granted,
  whether or not they've engaged with it yet. This is the one action that
  reaches into a *different* quest's own clock - `destroy_dungeon_id`/
  `set_flag` above only ever affect the failing quest's own target.
  `content/loader.py` rejects a `tighten_deadline` that targets its own
  quest, an unknown quest id, or a quest with no `deadline_year` set at
  all (same "nothing to shorten" logic as the no-deadline check below) -
  checked against the whole raw YAML file up front (the same trick
  `requires_quest_id` already uses), so it doesn't matter which quest is
  defined first in the file.

`content/loader.py` also rejects `on_fail` set with no `deadline_year` -
`QuestLog.check_deadlines` is `on_fail`'s only trigger, so a quest with
neither could never fire any of its consequences, whether it's a
`destroy_dungeon_id` or a `set_flag`.

Any *other* quest whose questgiver or completion target lives in a
dungeon a `destroy_dungeon_id` consequence might raze should set
`voided_by_dungeon_id: <dungeon_id>` - the moment the dungeon is razed,
`QuestLog.void_by_dungeon` force-fails every matching `not_given`/
`in_progress` quest (that NPC is gone; the quest can never be completed).
This is a separate, orthogonal mechanism from `on_fail` - it's the
"reacts to a destruction" side, regardless of which quest's `on_fail`
caused it, and doesn't fire for a `set_flag` consequence. A quest the
player already knew about (`in_progress`) gets its `failure_message`
logged; one they never received (`not_given`) fails silently -
announcing the failure of a quest the player was never given would be
confusing. `failed_description` is normally only valid alongside a real
deadline, but a `voided_by_dungeon_id` quest is exempt from that check
(it fails via a different trigger entirely) - see the loosened
`failed_description_requires_a_deadline_or_voiding_dungeon` validator.

Two invariants worth knowing before touching this: the world clock only
advances while the player is standing on the overworld itself
(`Engine._advance_world_clock`, gated on `is_overworld`), so a deadline
can only ever be crossed - and its `on_fail` list fired - while the
overworld Engine is active; the player can never be standing inside a
dungeon that a `destroy_dungeon_id` consequence is about to raze. And a
live destruction only mutates that run's in-memory overworld `GameMap` -
`engine/save.py` separately persists `QuestLog.destroyed_dungeon_ids` and
reapplies every entry to the freshly-rebuilt overworld map on
`restore_save`, or a save made after a razing would silently un-raze it
on reload. `world_flags` needs no such reapplication - it's plain
persisted state with no map-mutation side effect to redo.

`spreading_the_warning`/Wayford is the reference example: it requires its
own prerequisite quest (`goblin_warning`) to be `completed` first
(`requires_quest_id`), which has an earlier deadline of its own - a
player who finishes that prerequisite right at its deadline has *less*
than the nominal window left to also beat `spreading_the_warning`'s
deadline. Treated as an intended difficulty curve (cutting the first
warning close costs you on the second), not a bug to route around.

`spreading_the_warning`'s `on_fail` also carries a `tighten_deadline`
targeting `a_wall_worth_holding` (Stonebridge's independent kill quest
against the same `bandit_captain` at Broken Watch): if Wayford's own
deadline (day 64) lapses, Stonebridge's own deadline (day 70) is pulled
in to day 66 - a 6-day window collapsed to roughly 2. This is the
"a threat ignored in one region strengthens a threat elsewhere" case -
deliberately one-directional (Stonebridge's own failure does not tighten
Wayford's deadline in return, since there's no narrative reason for that
direction yet and this isn't a "for symmetry" feature). `engine/save.py`'s
`SavedQuestLogState.deadline_days` persists whichever deadline a quest is
actually holding right now, since `tighten_deadline` is the first thing
that ever mutates `deadline_day` at runtime - a save made after this
fires and then reloaded must keep showing day 66, not silently revert to
the authored day 70.

## 0k. Flag-conditional dialogue (`FlagDialogue` / `LegendEntry.flag_dialogue`)

A `set_flag` consequence (§0j) is inert on its own - `FlagDialogue` is
what lets content actually react to it. An `{entity: ...}` legend spawn
may carry `flag_dialogue: [{flag: <name>, line: <text>}, ...]` (both
fields required - a `FlagDialogue` only ever does one thing, unlike
`WorldConsequence`, so there's no "exactly one of" validator needed).
Checked in author list order at Talk time (`Engine.talk_to_adjacent`),
first matching flag wins, against whatever is currently in
`QuestLog.world_flags` - not baked in when the map is built, since a flag
can be set while the player is already standing on that map.

The full dialogue-resolution priority, highest first:
1. `flag_dialogue` - a matching entry in `QuestLog.world_flags`.
2. `QuestLog.followup_dialogue` - a completed quest's
   `questgiver_done_dialogue`/`target_done_dialogue` naming this NPC.
3. `Entity.dialogue` - the spawn's own per-placement line (or the
   catalog `EntityDef.dialogue` fallback if the spawn set none).
4. `_DEFAULT_TALK_LINE`.

A world-flag reaction deliberately outranks a completed quest's followup
line: it means something happened in the world *after* that quest
resolved, which supersedes whatever thank-you chatter would otherwise
show. `village_chief`/Millhaven is the reference example -
`data/dungeons/millhaven/levels/level_01.lvl`'s `"V"` legend entry reacts
to `wayford_razed` (set by `spreading_the_warning`'s `on_fail`, §0j) even
though the Chief's `followup_dialogue` line from the already-completed
`goblin_warning` quest would otherwise be active - the flag line wins.

Unlike `dialogue`, `flag_dialogue` has **no catalog-level fallback** on
`EntityDef` - it's spawn-only by design, since a world-flag reaction is
about *this specific placement*, not a generic trait of the monster/NPC
type (`engine/game_map.py`'s `build_game_map` has a comment on this at the
`Entity(...)` construction site).

`main.py`'s `_check_flag_dialogue_references_known_flags` cross-checks
every `flag_dialogue` entry across every dungeon's every level against the
full set of flags any quest's `on_fail` can ever set
(`WorldConsequence.set_flag`) - same "fail loudly at content-load time"
posture, same paired-registry-can't-check-itself-alone reasoning, as
`_check_destroyable_dungeons_have_ruin_content` above. The overworld is
never checked - `load_overworld` hardcodes `entity_spawns=[]`
unconditionally, since NPCs have no meaning there.

`flag_dialogue` needs no `engine/save.py` changes - it's static per-spawn
authored content, reconstructed fresh by `build_game_map` on every load
exactly like `dialogue` already is, unlike `world_flags` itself (which
*is* runtime-mutable state and is what M1 persists).

## 0l. Intimidate-and-report quests (`target_intimidate_entity_id`)

The fifth quest trigger shape, and the first one built directly on top of
another player-facing mechanic rather than an ordinary game event: the
attack-confirmation prompt that already guards against *accidentally*
attacking a peaceful NPC (`Engine.would_attack_peaceful_npc`). Since
attacking a peaceful NPC is now always a deliberate choice, it's a natural
quest verb in its own right - "rough someone up, don't kill them."

Same two-step record/report pattern as the kill, fetch, and
dungeon-arrival shapes: attacking a peaceful catalog entity (recorded
unconditionally by `engine/combat.py`'s `_apply_damage`, in
`QuestLog.intimidated_entity_ids`, via `record_entity_intimidated`) never
completes anything by itself - only reporting back to
`questgiver_entity_id` afterward does (`QuestLog.check_intimidate_report`,
called from `Engine.talk_to_adjacent` alongside every other report check).
`target_intimidated_description` overrides the quest log pane once the
target's been hit but not yet reported, mirroring `target_dead_description`
exactly.

Where it diverges: an intimidate quest can also fail, and it's the only
trigger shape in this codebase that fails from an *action* instead of a
clock or a dungeon's destruction. If the target dies from the hit (or a
later one) instead of surviving it, `QuestLog.fail_intimidate_by_death`
force-fails the quest **immediately**, from `Engine.on_entity_death` - it
doesn't wait for the player's next report the way a missed deadline or a
razed dungeon's `void_by_dungeon` effectively do at their own trigger
points. A killed target can never be "intimidated" per the quest's own
premise, so there's nothing to wait for. `content/schema.py`'s
`failed_description_requires_a_deadline_or_voiding_dungeon` validator
accepts `target_intimidate_entity_id` as a third valid reason to set
`failed_description`, alongside a deadline and `voided_by_dungeon_id`.

The "consequence" for attacking the target - guards in that settlement
turning hostile - needs **no new wiring at all**. It's the existing
`GameMap.guards_hostile` state, already armed by the same `_apply_damage`
condition that now also calls `record_entity_intimidated`, and already
read by every `town_guard`'s AI (`_perform_ai`'s `AI_TOWN_GUARD` branch) on
that same map. Authoring an intimidate quest doesn't require touching
guard behavior at all - the consequence is automatic the moment the deed
happens, quest or no quest, and self-resolves after
`GameMap.HOSTILITY_COOLDOWN_DAYS` (see §0c) unless the intimidation goes
wrong and the target dies - which, for an intimidate quest, also
force-fails it (above), so a permanently hostile Millhaven and a failed
quest arrive together, not as two independent surprises.

`content/loader.py`'s `load_quests` additionally requires
`target_intimidate_entity_id` to name a catalog entity whose `ai` is in
`PEACEFUL_AI_TYPES` - `_apply_damage` only ever records an intimidation
against a peaceful defender, so a hostile target could never complete
this quest, and the content-load-time check catches that mistake instead
of shipping a quest that can never be finished. `a_debt_worth_collecting`
(`data/quests.yaml`) is the reference example: the Wayford Provisioner
sends the player to rough up `millhaven_debtor` in Millhaven, not kill
them - killing the debtor instead force-fails the quest and leaves
Millhaven's guards hostile with nothing collected.

## 0m. Walkable ruins: a real before/after settlement (`ruined_starting_level`)

Until now, `destroy_dungeon_id` (§0j) only sealed a razed dungeon's
overworld entrance - the interior was never seen again. `DungeonDef.ruined_starting_level`
(optional, independent of `ruined_tile`/`ruined_description`) names a
level id the entrance leads into instead, once destroyed - the town stays
walkable, with a real authored "after" interior. `docs/dungeon_bibles/wayford.md`'s
"After: the Razing" section is the reference example: `spreading_the_warning`'s
`on_fail` still fires `destroy_dungeon_id: wayford`, but Wayford's
`dungeon.yaml` also sets `ruined_starting_level: level_01_ruins`, so the
gate stays enterable and now leads to `level_01_ruins.lvl` instead of
`level_01.lvl`.

**Same footprint, changed population** is the authoring convention this
establishes for any future before/after settlement: copy the "before"
level's ASCII map verbatim into the "after" file (a plain file copy, then
edit only `id`/`name`/the legend - never hand-retype the map block; a
single mistyped row silently produces a non-rectangular map or a shifted
layout that's easy to miss on review) so a returning player recognizes
the same walls and rooms, and only the legend changes: which NPCs survive
(kept as the exact same catalog id - no new "aftermath variant" entity
needed unless their mechanics genuinely change), which don't (simply
absent from the new legend), and which former set pieces become landmarks
describing their ruined state instead.

**The `Engine.current_level_id` gotcha.** `Engine.__init__` derives
`current_level_id` from `starting_level.id` by default - correct for
every ordinary fresh dungeon visit, where the level actually being shown
*is* the dungeon's nominal starting level. A razed dungeon's fresh-entry
Engine breaks that assumption on purpose: it needs to show the *ruins*
level while `starting_level` itself stays the *pristine* one (so
`Engine.restart()` - which also resets `quest_log`, un-razing the
dungeon - rebuilds the intact town, not the ruins). Any code path that
constructs an `Engine` landing the player somewhere other than
`starting_level`'s own level must pass `current_level_id` explicitly -
today that's `main.py`'s `resolve_transition` (the fresh-entry-after-razing
case) and `engine/save.py`'s `restore_save` (resuming a save made inside
the ruins). Getting this wrong doesn't just mis-render once - since
`current_level_id` also drives `SavedPlace.current_level_id`
(`engine/save.py`'s `_capture_place`), a save made in the ruins would
silently regress back to the pristine level on reload.

**Re-entry after razing needs its own staleness check**, separate from
the ordinary "resume the cached engine" path every other dungeon re-entry
already uses: a player who visited *before* the razing may still have a
cached pre-razing `Engine` in `active_engines`, showing the old level -
naively reusing it after the dungeon is razed would silently show the
intact town again. `resolve_transition` only forces a rebuild when the
cached engine is *still on the dungeon's own pristine `starting_level`*
after a razing that has a `ruined_starting_level` - deliberately narrower
than "any level mismatch," so a player resuming genuinely deeper in an
unrelated multi-level dungeon never has their progress discarded by an
unrelated destruction elsewhere.

## 0n. Time-gated availability (`available_after_year`/`available_after_day`)

The simplest of the reactive-world mechanisms: `QuestDef.available_after_year`/
`available_after_day` (both set together or not at all, same shape as
`deadline_year`/`deadline_day`) is a pure calendar floor -
`QuestLog.check_questgiver` silently withholds the quest (same "NPC just
says their normal line" treatment `requires_quest_id` already gets) until
the clock reaches that date, checked with the same `(clock.year,
clock.day)` tuple-comparison idiom `QuestLog.check_deadlines` already
uses for the opposite direction (a floor instead of a ceiling).

**Independent of every other gate.** `requires_quest_id` (gated on another
quest's completion) and `available_after_year`/`day` (gated on the clock)
can both be set on the same quest - both must be satisfied, checked as
two separate early-`continue`s in the same loop. Neither is gated on
`on_fail`/a deadline lapsing: this is a *floor*, not a *consequence* -
content whose availability follows the world clock itself, independent of
whether any particular quest succeeded or failed. The reference use case
is the goblin horde's aftermath: the tribe disperses 3 days after
`spreading_the_warning`'s own deadline (day 64 -> day 67), regardless of
whether that warning made it to Wayford in time - a warning delivered on
schedule doesn't turn the horde back, it only lets the town prepare, so
tying the aftermath quest to `spreading_the_warning`'s *outcome* would
have been wrong; tying it to the clock alone is correct.

**Needs `Engine.talk_to_adjacent` to thread `self.clock` through** -
`check_questgiver` reads it but never advances it (only the overworld
Engine's own turn processing ever calls `GameClock.advance_hour`), so this
is a read-only dependency, not a new place the clock can move from.

## 0o. Cull-while-preserving (`target_cull_entity_id`/`target_preserve_entity_id`)

The sixth quest trigger shape: clear every member of one species from a
dungeon while another species survives. Same two-step "record the deed,
complete only on report" pattern as every other trigger, but "the deed"
here (whether a species is fully cleared) can't be recorded the way a
kill/intimidate/fetch quest's single-target deed can, and needs its own
explanation.

**Why "cleared" is a population check, not a kill count.** `killed_entity_ids`
(the kill-quest mechanism) is a boolean set, correct only for a catalog id
that spawns exactly once in the whole game (see its own docstring caveat)
- a cull target is typically a whole tribe, many spawns of the same
catalog id. Rather than authoring a hand-typed total on the quest (which
can silently drift out of sync the moment a level file's roster changes),
`Engine._entity_type_cleared_from_dungeon(entity_id)` checks the *live*
population instead: for every level in the dungeon (`self.levels`, always
fully known regardless of visitation), a visited level's `GameMap` is
scanned for survivors, and an *unvisited* level's spawns are read straight
from its static `ParsedLevel.entity_spawns` and assumed still alive (they
can't have been killed without being visited) - so the check is correct
whether or not the player has actually reached every level yet, with no
number to keep in sync anywhere.

**Recorded at kill-time, not computed at report-time** - the same class of
subtlety as `0m`'s `current_level_id` gotcha. The questgiver is typically
reported to from a *different* Engine (the settlement) than the one the
kill happened on (the dungeon), which has no visibility into that
dungeon's levels by the time the player gets back to report. So
`Engine.on_entity_death` checks `_entity_type_cleared_from_dungeon` and
writes the result into `QuestLog.cleared_species_ids` immediately, while
still on the dungeon's own Engine - `QuestLog.check_cull_report` (called
later, possibly from anywhere) just reads that boolean back, mirroring
`check_kill_report`'s shape exactly. Gated on a live quest actually
targeting that species first (`any(q.target_cull_entity_id == entity_id
...)`), since the whole-dungeon scan isn't free and every other kill in
the game would otherwise trigger it for nothing.

**Preservation failure is a threshold, not zero-tolerance** - `QuestLog.entity_kill_counts`
(a plain counter, incremented unconditionally by `record_entity_killed`
for every death, the same "record regardless of whether any quest cares"
philosophy as `killed_entity_ids`) is compared against
`target_preserve_tolerance` in `QuestLog.fail_cull_by_preservation_loss`,
called from `Engine.on_entity_death` immediately - same
action-triggered-failure timing as `target_intimidate_entity_id`'s
`fail_intimidate_by_death` (§0l), just with a threshold instead of always
zero. `target_preserve_tolerance: 0` (the default) reproduces the
intimidate quest's exact zero-tolerance bar if a future quest wants it;
the reference example (Silversilk Caves' goblins vs. cave spiders) uses a
tolerance of 5.

**A real bug this mechanism shipped with, found only once real content
exercised it**: `_entity_type_cleared_from_dungeon` trusts
`Engine.visited_maps` to hold the live `GameMap` for every level the
player has actually been on, falling back to a level's static,
never-updated `entity_spawns` otherwise. `Engine.__init__` caches the
dungeon's *entry* level into `visited_maps` immediately, but
`on_player_reach_stairs` (moving between levels within the same dungeon)
only cached the level being *left*, not the one just *arrived on* - so a
species cleared entirely by killing its last member on a non-entry level,
without ever backing out of that level first, silently failed to
register as cleared. Round 1's own test coverage happened not to exercise
that exact order (finishing on the entry level, or always visiting-then-
leaving before the last kill), so it shipped unnoticed until Silversilk
Caves' real two-level layout was played through end-to-end. Fixed by
caching the arrived-on level immediately in `on_player_reach_stairs`, the
same way `__init__` already does for the first one. Worth remembering for
any future multi-level mechanic that reads `visited_maps`: the *current*
level is only guaranteed to be in there because of this fix, not because
it's obviously implied by "currently active."

## 0p. Environmental hazard tiles (`dunes`, `Engine._apply_environmental_hazard`)

A tile-kind-driven mechanic, not a quest trigger: some ground is simply
dangerous to stand on, independent of any monster or quest. First (and
so far only) use is the Scoured Reach, the open, unforested, unsettled
plains stretch in the map's east-central expanse - `dunes` explains
*why* that space reads as empty on the overworld rather than leaving it
unexplained, the same "environmental storytelling" job `world_history.md`
asks every location to do.

**Shipped once as `storm_plain`, renamed to `dunes` after user
playtesting** - worth keeping as a cautionary note. "Storm" framed the
hazard as *weather*, an event that happens *to* a place; a player
correctly read that as abstract, since a permanent damage-over-time tile
doesn't behave like an intermittent storm, it behaves like a *terrain
condition*. `dunes` - loose, wind-scoured sand you're physically slogging
through - is the same mechanic wearing a name that matches what it
actually does. See "Grounding an abstract mechanic" in §4 below for the
general version of this lesson.

**Mechanically**: `TILE_PASSABILITY` deliberately has no entry for
`dunes`, falling through to its `(True, True)` default (walkable,
transparent) - identical to `plains`. The danger isn't crossing it, it's
lingering on it: `Engine._apply_environmental_hazard`, called every turn
from `process_enemy_phase` (right after enemy AI, before the player-death
check, so a lethal turn on the dunes is caught the same way a lethal hit
already is), checks the player's current tile kind directly and deals
flat `DUNE_DAMAGE` with no defense mitigation - this isn't an attack, it
has no attacker. Checked by tile kind, not by `is_overworld`, so it isn't
special-cased to the overworld specifically; `dunes` just doesn't appear
anywhere else today.

**Why `DUNE_DAMAGE` is 2, not 1**: the overworld already heals the
player +1/hour unconditionally (`_advance_world_clock`, same turn,
right after this check runs). A hazard that merely matched the passive
heal would be invisible - net zero, no felt cost, no reason to hurry.
Set one above it on purpose so standing in the open is a small but real
net loss (-1 HP/turn) rather than a wash - felt over a real crossing,
but not so steep that a fresh, unprepared player dies outright
attempting a straight-line dash across a sheltered-pocket-to-sheltered-
pocket route.

**Monsters are unaffected** - `_apply_environmental_hazard` only ever
checks `self.player`. Whatever lives in a hazardous area is written as
already adapted to it (same reasoning a skittish monster never flees a
terrain hazard the way it flees low HP); nothing currently needs a
monster to take hazard damage, and the check would need to iterate every
entity on the map each turn if one ever did.

**A deliberately unbuilt hook, noted rather than built**: some kind of
protective item/equipment slot that suppresses this damage (goggles or a
wrap against the grit, say) would be a natural next step for a location
built around this hazard, but isn't needed for a first pass where the
hazardous stretch is narrow enough to cross in one push - same "flag it,
don't build it" discipline as Silversilk Caves' lower levels.

**The overworld region's own shape was a second, separate problem**: it
shipped as a hand-edited rectangle - a hard, straight-edged box of
`dunes` tiles dropped onto the map, immediately readable as authored
rather than natural. Fixed by generating the region's boundary with the
same cellular-automata blob technique already used for organic dungeon
geometry (Silversilk Caves, the Sunless Hollow - see the caves' own
bibles), just applied to a *terrain patch* on the overworld instead of a
*cavern* underground. Any future large-area overworld terrain edit
(a badlands stretch, a bog, a burned tract) should default to this same
technique - a rectangle or a hand-drawn blob-by-eye both read as
obviously artificial at the zoomed-out overworld scale in a way they
might not inside a cramped dungeon room.

## 0q. Dark levels (`LevelDef.dark`, `GameMap.fov_radius`)

A second, much smaller environmental mechanic, first used for the Sunless
Hollow (a natural wolf den where sunlight genuinely doesn't reach). One
new `LevelDef` field, `dark: bool = False`, threaded through
`ParsedLevel.dark` (`content/loader.py`, same shape as `open_boundary`'s
own threading) to `GameMap.fov_radius` (`build_game_map` sets it to
`DARK_FOV_RADIUS` instead of the normal `FOV_RADIUS`, both constants in
`engine/game_map.py`) - `GameMap.update_fov` reads `self.fov_radius`
instead of the module constant directly, so every existing call site
needed no changes at all.

**Deliberately the smallest possible mechanic, not a new system.** No new
item, no new action, no "light source" inventory slot - just a level-wide
constant swapped at load time. `dunes` (§0p) is the template for
what a *bigger* environmental mechanic looks like (a per-turn Engine
check, numeric tuning against the passive heal); this one is the
template for the other end of that spectrum - genuinely useful, genuinely
new-feeling to the player, and roughly a five-line change once the
existing `open_boundary` field showed exactly where every wire needed to
run.

**Why it's dangerous without touching monster AI at all**: `hostile_basic`
already only acts on a turn where `self.game_map.visible[entity.x,
entity.y]` is true (see `Engine._perform_ai`) - a monster "wakes up" the
instant it's inside the *player's* visible area, not on some separate
detection radius of its own. Shrinking that visible area doesn't change
when a monster notices the player; it changes when the player notices
the monster. The whole effect is reduced reaction time, achieved without
writing a single new line of AI logic - `dark` only ever needed to touch
FOV plumbing.

**Not a difficulty slider for ordinary rooms.** Reach for this only when
a level's own premise genuinely explains the dark (underground, sealed,
no light source ever reached it) - see the Sunless Hollow's own name,
chosen specifically to make the mechanic self-explanatory before a
player reads a single line of flavor text about it.

## 0r. Scheduled dungeon population (`DungeonDef.pre_arrival_starting_level`)

A bug, not a planned mechanic - caught by the user directly reviewing
shipped content, not by any test: Silversilk Caves' goblins were placed
in `level_01`/`level_02` unconditionally, even though the dungeon's own
bible and `the_uninvited_tribe`'s `available_after_year: 87`/
`available_after_day: 67` both say the tribe only migrates in *after*
the Goblin Horde disperses near Wayford. A player who walked in on day
50 (the game's own start date) found a fully goblin-infested cave before
the horde had even reached Wayford yet - the dungeon's content didn't
agree with the story built around it.

**The fix is the mirror image of `ruined_starting_level` (§0m)**: instead
of "normal, then a quest ruins it," this is "reduced, then a scheduled
date populates it" - calendar-driven, independent of any quest's pass/
fail, same "pure calendar floor" shape as `available_after_year`/`day`
(§0n). `starting_level` never changes meaning - it's always the
dungeon's normal, eventual state. `pre_arrival_starting_level` (+
`pre_arrival_until_year`/`day`, set together or not at all) is the
temporary substitute shown only before that date. For Silversilk Caves:
`level_01_undisturbed` is the *same cave geometry* as `level_01` with
every goblin (and the territory-marker totem, which wouldn't make sense
yet) removed, cave spiders left exactly as they were - the settlers were
already hunting here before any of this started - and its `>` tile
changed from `{stairs_down: level_02}` to a terminal
`{stairs_down: null}` (nothing to reach yet, so nothing down that path).
Reusing the parent level's own geometry rather than drawing a new map
keeps the "before" state honest: it's the same place, just not yet
contested.

**`main.py`'s `resolve_transition` picks `entry_level_id` the same way
it already picks between `starting_level`/`ruined_starting_level`** -
`arrived = (clock.year, clock.day) >= (pre_arrival_until_year, until_day)`
(or always `True` if `pre_arrival_starting_level` isn't configured),
`entry_level_id = starting_level if arrived else pre_arrival_starting_level`
(razed still wins over both, for a dungeon that somehow sets all three -
none does today). `needs_rebuild`'s condition was generalized to a
single, direction-agnostic check covering *both* mechanisms: force a
rebuild whenever a cached engine's `current_level_id` is one of the two
starting-level candidates (razed or pre-arrival) but not the currently-
correct one - checked both ways, since `Engine.restart()` resets the
clock backward as easily as normal play moves it forward, and a stale
cache needs to resolve in either direction. A player resuming genuine
mid-dungeon progress (`current_level_id` is neither candidate, e.g.
`level_02`) is never force-rebuilt - same "resume exactly where they
left" guarantee `ruined_starting_level` already promised.

**Why this needs no dynamic entity injection.** The tempting-looking
alternative - keep one level file, gate individual goblin spawns behind
a per-spawn calendar check evaluated at `build_game_map` time - breaks
the moment `Engine.visited_maps` caches the built `GameMap` (see §0o's
own caching bug write-up): a level built before the date would cache
permanently goblin-free, with no mechanism to ever repopulate it short
of re-deriving `_entity_type_cleared_from_dungeon`-style logic for
*arrival* instead of *clearing*. Swapping which whole level id is
entered, the same lever `ruined_starting_level` already pulls, sidesteps
that entirely - the cache invalidates itself the same way a razed
dungeon's does, verified by mirroring that mechanism's own test pair
(`test_resolve_transition_enters_wayfords_ruins_after_it_is_razed` /
`..._rebuilds_to_the_normal_level_once_the_date_arrives...`).

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
much to say"). **Treat that fallback as a safety net, not the bulk of a
shipped settlement's cast** - it exists so a stray, never-quite-authored
spawn still says *something* sensible, not so most of a town's villagers
can lean on one repeated line. **At least 75% of the villager/town_guard
spawns in a settlement need their own per-spawn `dialogue`** (a distinct
legend symbol per unique line, since `dialogue` lives on the legend entry
- see `data/dungeons/millhaven/levels/level_01.lvl` for the pattern: five
plain villagers, five distinct symbols, five distinct lines). This is a
floor, not a target to undershoot - 100% unique is fine and was in fact
the fix applied to Wayford - but it's no longer a hard requirement for
every single spawn: a player who hears the same one or two lines from an
occasional NPC in a big town doesn't read it as broken the way a whole
cast repeating one line does, and a firm 100%-or-nothing rule turned out
to read as more rigid than the actual problem called for. (History: the
100%-with-no-exceptions version of this rule was written after Wayford's
first regeneration shipped twelve anonymous villagers all silently
sharing the one catalog-default line - caught only once the user played
it and noticed the town felt thinner than Millhaven's. Relaxed to 75%
after the user felt the original fix over-corrected; a future pass may
add several distinct *fallback* lines, rotated rather than one repeated
default, to raise the ceiling on the un-authored remainder without
requiring every spawn to be individually written - not built yet.) Most
lines should still cost the player nothing to skip (per Millhaven's own
tone notes - see `docs/dungeon_bibles/millhaven.md`), but a few per
settlement should carry something real: a nudge toward a questgiver the
player might otherwise miss, or a piece of world/local texture. A tile's
custom `description`, when set, always wins over its kind's default and
over a `dungeon_entrance`'s dungeon-level `inspect_text` (0b) - most
specific wins.

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

**Give every `announce`-worthy `description` the flag, don't leave it as a
manual-Look-only secret.** `LegendEntry.announce` (paired with
`description`) auto-logs a tile's flavor text to the message log the
first time it enters the player's field of view, once ever
(`GameMap.newly_seen_tile_announcements`, `Engine._log_newly_seen_tile_announcements`
- called after every `update_fov`). The `landmark`-visibility fix above
solves "the player didn't know to look here"; `announce` solves "the
player saw it but never actually read it." Default every landmark and
every other description-bearing tile to `announce: true` unless there's a
specific reason to gate it behind a deliberate Look. `content/loader.py`
rejects `announce: true` with no `description` set - nothing to announce.
Persisted across save/reload (`engine/save.py`'s
`SavedLevelState.announced_tiles`), so a reload never re-announces a tile
the player already saw announced.

**The one real exception, caught the hard way**: never set `announce: true`
on a legend symbol painted across *many* map cells sharing one description
- a `sea`/`mountain` terrain hazard, a `wall` segment forming a whole
boundary. Each cell is tracked (and fires) independently
(`GameMap.auto_announce_tiles` is coordinate-keyed), so a multi-tile
hazard logs the *same* line once per distinct coordinate as different
parts of it enter FOV - `goblin_ambush`'s felled-tree wall (the entire
perimeter, one symbol) and every dungeon's `sea`/`mountain` pool
originally shipped with `announce: true` in this pass and had to be
reverted once a test walking near one surfaced a dozen repeats of the
same line. `announce: true` is for a tile placed *once* - a landmark, a
gate, a single item - keep `description` (still shown in look mode) on a
multi-tile hazard, just not `announce`.

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

**XP economy** (`EntityDef.xp_reward`, `QuestDef.reward_xp_amount`,
`data/perks.yaml`, see `Engine._award_xp`/`Engine.learn_perk`): XP is a
pure spendable currency for Trainer-taught Perks, not a level-up bar - no
formula ties it to combat balance above, so these numbers were established
fresh rather than derived. Convention this pass set: a monster's
`xp_reward` scales with its `hp` tier (roughly 3 XP for a weak
skirmisher around hp 6-9, up to 14-15 XP for a boss-tier monster like the
ogre or stone sentinel at hp 28-30 - see `data/entities.yaml` for the full
tiering); a quest's `reward_xp_amount` runs somewhat higher per completion
(15-25 XP), since a quest represents more total investment than one kill.
A perk's `xp_cost` should be reachable after a modest handful of early
kills plus roughly one quest - not a single kill, not a full dungeon clear
- `data/perks.yaml`'s starting tier (40-45 XP) was picked against these
numbers with that target in mind. Only a hostile (non-`PEACEFUL_AI_TYPES`)
entity may ever set `xp_reward` - `content/loader.py`'s `load_catalog`
rejects it otherwise, so a villager/town_guard can never be XP-farmed.

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
   **For a settlement specifically, at least 75% of its `AI_VILLAGER`/
   `AI_TOWN_GUARD` spawns need their own per-spawn `dialogue` (see §1)** -
   a floor, not a per-town judgment call; 100% is fine but no longer
   required. For a combat dungeon, where villager-type spawns are rare or
   absent, a per-spawn `dialogue` is still worth considering for any named
   set piece built around one, but nothing there forces it. Every
   description-bearing legend entry (landmarks especially) should also get
   `announce: true` (see §1) unless there's a specific reason to withhold
   it behind a manual Look instead.
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

## 5. Worldbuilding quality checks (added after the Scoured Reach pass)

The Windbreak Hold/The Windrest pass shipped, passed every automated
check, and still had the most worldbuilding problems of any location so
far - caught only by a human reading and playing the actual content, not
by anything mechanical. None of these are covered by `tools/preview.py`
or `pytest`; they need a deliberate read-through pass of their own
before calling a location finished.

- **Grounding an abstract mechanic.** A new hazard/mechanic needs a name
  and flavor text that describe a *concrete, physically recognizable*
  thing, not an abstract effect or an event. "Storm" named a
  damage-over-time tile after *weather* - something that happens *to* a
  place, intermittently - when the tile itself is a permanent *terrain
  condition* (dune sand, always there, always costly to cross). The
  mismatch read as abstract even though the mechanic itself (flat chip
  damage per turn) was sound. Ask, before naming anything: if a player
  had to picture standing on this tile, what would they actually see?
  If the honest answer is "an effect" rather than "a place," the naming
  hasn't found its concrete anchor yet. See §0p's own retrospective note
  for the specific fix (`storm_plain` → `dunes`).
- **Organic shape for any large-area overworld edit.** A rectangle (or a
  hand-drawn blob-by-eye) reads as obviously authored at the overworld's
  zoomed-out scale, the same way a perfectly rectangular room would
  inside a natural cave. Any terrain patch bigger than a few tiles -
  a hazard region, a biome boundary, anything that isn't a single
  building's footprint - should get the same cellular-automata blob
  treatment already used for organic dungeon geometry (see
  `docs/dungeon_bibles/silver_mountain_caves.md`/`sunless_hollow.md`),
  just run once over the overworld map instead of a cavern.
- **Cross-check names/titles across everything shipped in the same
  pass**, not just within one dungeon. `windbreak_captain` ("Captain")
  and `windrest_captain` (originally "Windrest Captain") sat one quest
  apart - a friendly questgiver sending the player to kill someone with
  a near-identical title, at a near-identically-named neighboring
  location. Neither dungeon's own bible caught it, because each was
  reviewed in isolation; the collision only exists across the pair.
  Before finishing a multi-location pass, list every NPC's *display*
  `name` (not just catalog id) side by side and check that a player
  moving between the locations wouldn't confuse any two of them.
