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

`data/overworld/` is a directory (there is still exactly one overworld,
unlike dungeons - the directory holds an authoring-time split into cell
files, not a menu of alternatives) containing a `cells.lvl` manifest plus
one `.lvl` file per cell under `cells/`. `cells.lvl` uses the same
ASCII+legend idiom every `.lvl` file does, but each map character names a
whole rectangular cell (via its legend) rather than a single terrain
tile; every cell must share identical dimensions (currently 150x90) so
they tile into one seamless map with no visible seams or loading pauses
at cell boundaries - this is purely a content-authoring split, not a
runtime streaming system: `content/loader.py`'s `load_overworld` stitches
every cell into one ordinary `ParsedLevel` at load time, and nothing
downstream (`build_game_map`, `GameMap`, movement, FOV) is aware cells
exist at all. Splitting a large region into its own cell file keeps
individually-authored regions reviewable, and (planned future work) will
let a corrupted/devastated variant of a region be authored as a sibling
cell file. Each cell file reuses the ordinary `.lvl` ASCII+legend format,
loaded via `content/loader.py`'s `load_overworld`/`_parse_overworld_cell`
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

**Region bibles (`docs/region_bibles/`)** extend the same discipline one
level up, for a whole overworld cell rather than one dungeon - write one
before drawing a new cell's terrain, same as a dungeon bible before its
geometry. `northern_steppe.md` is the first; expect it to cover named
set pieces at region scale (corruption bands, reserved future-dungeon
landmarks, a road's route) rather than room-by-room set pieces.

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
dangerous to stand on, independent of any monster or quest. First use is
the Scoured Reach, the open, unforested, unsettled plains stretch in the
map's east-central expanse - `dunes` explains *why* that space reads as
empty on the overworld rather than leaving it unexplained, the same
"environmental storytelling" job `world_history.md` asks every location
to do.

**Shipped once as `storm_plain`, renamed to `dunes` after user
playtesting** - worth keeping as a cautionary note. "Storm" framed the
hazard as *weather*, an event that happens *to* a place; a player
correctly read that as abstract, since a permanent damage-over-time tile
doesn't behave like an intermittent storm, it behaves like a *terrain
condition*. `dunes` - loose, wind-scoured sand you're physically slogging
through - is the same mechanic wearing a name that matches what it
actually does. See "Grounding an abstract mechanic" in §4 below for the
general version of this lesson.

**Generalized for the Northern Steppe pass**: the mechanic isn't
`dunes`-specific - `Engine.ENVIRONMENTAL_HAZARD_MESSAGES` maps any number
of hazardous `TileType` kinds to the message logged when a turn ends on
one, and `_apply_environmental_hazard` looks up the player's current tile
kind in that dict rather than comparing against a single hardcoded
string. `ashen_plains`/`blighted_forest` (the Northern Steppe's corrupted
ground, standing in for `plains`/`forest` respectively) reuse the exact
same mechanic and the same `ENVIRONMENTAL_HAZARD_DAMAGE` - per the design
decision behind them, corruption is meant to be *the same danger as the
Scoured Reach's wind*, wearing the Visitor's story instead of its own;
only the flavor text differs per kind. Adding a future hazardous kind
means one new dict entry, nothing else.

**Mechanically**: `TILE_PASSABILITY` deliberately has no entry for
`dunes`/`ashen_plains`, falling through to their `(True, True)` default
(walkable, transparent) - identical to `plains`; `blighted_forest` does
get an entry, matching `forest`'s `(True, False)` (blocks sightlines,
since it's still visually a stand of trees, just dead ones). The danger
isn't crossing it, it's lingering on it: `Engine._apply_environmental_hazard`,
called every turn from `process_enemy_phase` (right after enemy AI,
before the player-death check, so a lethal turn on a hazard tile is
caught the same way a lethal hit already is), checks the player's
current tile kind directly and deals flat `ENVIRONMENTAL_HAZARD_DAMAGE`
with no defense mitigation - this isn't an attack, it has no attacker.
Checked by tile kind, not by `is_overworld`, so it isn't special-cased to
the overworld specifically; these kinds just don't appear anywhere else
today.

**Why `ENVIRONMENTAL_HAZARD_DAMAGE` is 2, not 1**: the overworld already
heals the player +1/hour unconditionally (`_advance_world_clock`, same
turn, right after this check runs). A hazard that merely matched the
passive heal would be invisible - net zero, no felt cost, no reason to
hurry. Set one above it on purpose so standing in the open is a small but
real net loss (-1 HP/turn) rather than a wash - felt over a real
crossing, but not so steep that a fresh, unprepared player dies outright
attempting a straight-line dash across a sheltered-pocket-to-sheltered-
pocket route. This is also why the Northern Steppe's corrupted ground is
authored as *patches within otherwise-ordinary terrain* rather than
painting the whole region hazardous - the same "narrow enough to cross in
one push" discipline the Scoured Reach follows, just repeated at several
points across a much larger map instead of once.

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

**Splitting the look from the mechanic**: `scoured_ground` (added for
`data/dungeons/visitor_band_ambush`) is the same ashen-grey look as
`ashen_plains` - identical `TILE_VISUALS` entry, identical sprite in
`data/sprites.yaml` - but deliberately left out of
`ENVIRONMENTAL_HAZARD_MESSAGES`, so it deals no damage at all. Useful
whenever a place should *read* as corrupted ground without actually
being hazardous - a monster encounter (or any other danger) already
covers that job, and stacking chip damage on top would just be two
separate threats competing for the same beat rather than one clear one.
The general pattern: a hazard tile kind and its message are two
independent facts (the kind drives rendering via `TILE_VISUALS`, the
dict entry drives the damage) - a new kind can borrow one without the
other by copying `TILE_VISUALS`'s values verbatim and simply never
adding a dict entry.

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

**A second bug, found by actually playing it rather than reading it**:
`Engine.restart()` rebuilds from `self.starting_level`, always set (at
Engine-construction time in `resolve_transition`) to
`dungeon.levels[dungeon.starting_level]` - the dungeon's own declared
default, unconditionally. For the razed mechanism that's correct by
construction: `starting_level` is always the pristine, undestroyed
level, exactly what a fresh run (which also resets `quest_log`, clearing
`destroyed_dungeon_ids`) should show. But `restart()` *also* resets the
clock to its own starting date - always before any `pre_arrival_until`
threshold - so for a pre-arrival dungeon the "what a fresh run sees"
level is the *pre-arrival* one, not `dungeon.starting_level` itself
(which, for Silversilk Caves, names the post-arrival, infested level).
Dying inside Silversilk Caves after day 67 and hitting restart
reproduced exactly this: goblins present, clock freshly reset to before
they'd arrived - the same class of inconsistency the razed mechanism
was careful to avoid, just introduced fresh by inverting which field
means "default." Fixed in `resolve_transition` by computing the
restart baseline as `dungeon.pre_arrival_starting_level` when one's
configured, falling back to `dungeon.starting_level` otherwise (every
other dungeon, unaffected). General lesson: whenever a "what does a
brand-new run see" baseline is hardcoded to one field, check that field
actually names the state a *freshly reset world clock* would produce -
don't assume "the dungeon's declared starting_level" and "pristine" are
the same thing once a mechanic can make them diverge.

## 0s. Balance-testing without a full playthrough (`DungeonDef.balance_reference_xp`, `tools/balance.py`, `testbuild`)

The Windrest bug (§2's "hits-to-kill" discipline applied correctly at
placement time, but the *fix* - adding `rusty_dagger`/`leather_armor`
pickups - was only found by actually dying to the Bandit Captain with an
unequipped character, see memory `feedback_full_cli_playthroughs_find_real_bugs`)
is exactly the kind of thing that shouldn't require a real death to catch.
The fix: let a tester spawn directly adjacent to any dungeon's entrance
with a hand-picked build - specific perks pre-learned, specific gear
pre-equipped - via `python tools/play_llm.py testbuild <dungeon_id> [--perk
...] [--weapon ...] [--armor ...] [--ranged ...] [--ammo N] [--gold N]
[--xp N] [--potions N]`, and see immediately how that build's XP-equivalent
compares to what the dungeon expects.

**Gear's XP-equivalent value is derived from existing perk pricing, not a
new per-item field.** `data/perks.yaml` already prices a flat stat bonus
in XP (`weapon_training_1`: 45 XP for +2 attack, and so on for defense/
ranged) - `tools/balance.py`'s `stat_point_rate(catalog, stat)` averages
`perk.xp_cost / bonus` across every perk pricing that one stat (today:
exactly one perk per stat, so the average is exact - a future tiered perk
with a different per-point rate would need this reconsidered, not just
averaged in blindly), `gear_xp_equivalent(catalog, item)` multiplies an
item's own equipment bonus by that rate, and `build_xp_total(catalog,
perk_ids, weapon_id, armor_id, ranged_id)` sums real perk `xp_cost` plus
each equipped item's derived value. A weapon's `attack_bonus` is "worth"
exactly what a perk granting the same attack would have cost - no second
pricing scheme for a content author to keep in sync by hand.

**`DungeonDef.balance_reference_xp`** (optional, `None` by default) is a
pure reference number - never enforced or auto-consumed, just what
`testbuild` prints its build's total against when set. It answers "roughly
how much XP-equivalent investment is a player expected to have by the time
they reasonably reach this dungeon" - and `0` is a legitimate, meaningful
answer, not just "not yet set": Silversilk Caves and Sunless Hollow both
set it explicitly to `0` because their own bibles already confirm
(hits-to-kill math, "no rebalancing needed") that they're tuned fair
against bare player baseline. The Windrest sets it to `68` - the derived
value of the exact `rusty_dagger` + `leather_armor` pair that turned its
real unwinnable fight fair - documenting the concrete finding this whole
feature exists to make instantly reproducible: `testbuild the_windrest`
with an empty build should come up short against `68`; carrying that pair
should clear it.

**Scope, deliberately narrow**: only populated for dungeons that actually
have hostile encounters to balance-test. Windbreak Hold, Farrow's Stake,
and Grey Valley Monastery (this pass's other three touched locations) are
pure settlements - every spawn in each is a peaceful, dialogue-only NPC
(checked directly against each `.lvl`'s entity legend) - so the field was
left unset there; a reference number with nothing to fight against would
be noise, not documentation. Don't populate this field reflexively for
every dungeon touched in a pass - check for a hostile roster first.

`testbuild` spawns the player *adjacent to*, never *on*, the dungeon's
entrance tile - the same "one step off, then walk in" shape `goto` already
needs against a coordinate identical to the player's own position (see the
module docstring's testing-friction notes) - so the tester's first ordinary
move naturally triggers entry, no dead-on-arrival special-case needed.
Perks are applied by calling the same `apply_perk_stat_bonus`/HP-bump logic
`Engine.learn_perk` uses for a live purchase, just without requiring an
adjacent Trainer first - deliberate: this exists to test a dungeon in
isolation, not to simulate legitimately reaching it.

## 0t. Status effects: a general framework (`poison`, `stun`, `weaken`)

Started as a poison-only, hardcoded field pair; generalized into a real
small framework once a second and third effect (stun, weaken) were added,
keeping poison's own observable behavior identical throughout. A landed
hit (damage > 0 after defense) from an entity with `EntityDef.inflicts_effect`
set afflicts the defender with that effect - `inflicts_potency` (meaningful
for poison/weaken only - see below) for `inflicts_duration` turns.
`EffectKind` (`content/schema.py`) is `"poison" | "stun" | "weaken"`, the
same "string constants + Literal, fails loudly on an unrecognized value at
content-load time" shape as `AIType`. `cave_spider`/`giant_spider` set
poison; `wraith` (stun) and `gray_ooze` (weaken) are the two bestiary-
expansion entries this framework's first pass added the *capability* to,
not yet placed in any dungeon - same "define now, place later" pattern
already used for the rest of the unplaced roster.

**Two clearly separate pieces of state**, matching the existing split
between an entity's static innate capabilities and its live combat state:

- **Attacker capability** (`Entity.inflicts_effect`/`inflicts_potency`/
  `inflicts_duration`, set once at spawn from the matching `EntityDef`
  fields, never mutated): "my bite inflicts kind X, potency Y, duration Z."
  `inflicts_effect`/`inflicts_duration` must be set together or not at all
  (the established "both or neither" validator shape); `inflicts_potency`
  is required for poison/weaken and *rejected* for stun (no intensity
  concept - an entity either can act or can't), enforced by a second
  validator keyed off `EffectKind`.
- **Victim's live affliction** (`Fighter.active_effects: dict[str,
  ActiveEffect]`, keyed by kind, `ActiveEffect(potency, turns_remaining)`):
  "I am currently afflicted by these effects, each ticking down
  independently." Lives on whichever `Fighter` (player's or a monster's)
  currently carries it - symmetric in principle, even though only the
  player is ever actually afflicted today, since nothing currently gives
  the player an on-hit attack of its own.

**Refresh per kind, not stack - and different kinds coexist.** A repeat
hit of the *same* kind overwrites that dict entry (`engine/combat.py`'s
`_apply_damage`, inside the existing `damage > 0` block - a fully-absorbed
hit correctly never afflicts, no extra guard needed); a *different* kind
lives in its own dict entry, ticking independently - a player can be
poisoned and weakened at once, and losing one doesn't touch the other.
"Currently affected by kind X" is dict-key membership, not a `>0` check on
a value inside it - `ActiveEffect` entries are deleted outright once
`turns_remaining` hits 0, never left inert.

**Same-turn tick for poison/weaken - stun is the deliberate exception.**
Poison damage and weaken's passive countdown both tick in
`Engine._tick_active_effects`, called from `process_enemy_phase` right
after `_apply_environmental_hazard` (all damage/duration-over-time
sources, grouped together, checked before the generic player-death gate),
NOT gated on `is_overworld`. Because that call happens strictly after
*both* places an effect could be freshly applied this same turn -
`process_player_action` (the player's own attack, earlier) and
`_handle_enemy_turns` (monster attacks, just above it) - **every
freshly-poisoned/weakened entity takes its first tick immediately, the
same turn as the bite**: `inflicts_duration=3` means 3 total ticks, the
first landing on the turn of the hit itself, not the turn after. Get this
backwards and a monster's whole roster's damage-over-time math (§2) will
be off by one tick per hit.

Stun is deliberately **excluded** from `_tick_active_effects` and
decremented instead at `Engine._consume_stun_turn`, called from exactly
the two places a stun actually *blocks* something -
`process_player_action` (the player's own turn) and `_perform_ai` (a
monster's) - the instant the block takes effect, not in the shared
end-of-turn sweep. This isn't an arbitrary inconsistency: poison/weaken's
*effect* (damage, a stat penalty) genuinely is the tick itself, so ticking
them at end-of-turn is correct and lets the same hit's damage-over-time
start immediately. Stun's effect (skipping a turn) happens at a different
point in the turn sequence entirely - if it decremented in the same
end-of-turn sweep, a `inflicts_duration=1` stun inflicted mid-turn (during
`_handle_enemy_turns`) would already be back at 0 and deleted by the time
that same call returns, *before* the afflicted entity's own next
`process_player_action`/`_perform_ai` check ever ran - meaning it would
never actually block anything. Decrementing at the block site instead
means a stun inflicted this turn blocks exactly `inflicts_duration` of the
afflicted entity's *own subsequent* turns, which is the only sensible
reading of "skip a turn."

**Killing via a poison tick calls `on_entity_death` directly**, unlike
`_apply_environmental_hazard`'s pattern (which only ever hits the player
and safely defers to `process_enemy_phase`'s own generic
`if not self.player.is_alive: on_entity_death(...)` check right after it).
`_tick_active_effects` must call it directly because it also has to
correctly kill a *monster* - nothing else in `process_enemy_phase` ever
calls `on_entity_death` on a non-player entity after `_handle_enemy_turns`
returns. This is safe from a double-call (re-logged death message,
re-awarded XP) only because `_tick_active_effects` snapshots
`game_map.entities` **fresh, at the top of its own call**, after
`_handle_enemy_turns` has already run: anything that died earlier the same
turn via `engine/combat.py`'s own direct `on_entity_death` call is already
gone (a dead monster: already removed from `game_map.entities`; a dead
player: the whole call is skipped, gated on `game_state == "playing"`).
Don't hoist that snapshot earlier in a future refactor without
re-verifying this invariant holds.

Expected total damage from one poisonous attacker's landed hit for hits-
to-kill math (§2) is `direct + potency * duration`, not just `direct` -
factor this in when placing or rebalancing any poisonous monster. A
weakening hit doesn't change the defender's own hits-to-kill directly, but
*does* reduce the defender's own damage output for `inflicts_duration`
turns - factor this into a multi-hit exchange's math the same way. Monster
effect state is never persisted across a save/load (`engine/save.py`'s
`SavedPlayer` only carries the *player's* `active_effects`) - consistent
with monster `Fighter` state beyond `(x, y, hp)` never being saved today;
acceptable since nothing afflicts a monster in this pass.

**The stun-lock trap - a real risk to design around, not a bug to fix
mechanically.** A stunning monster that lands a hit *every* turn it acts
can re-stun the player before their own previous stun's block ever lets
them act at all, live-verified: a wraith attacking every turn keeps the
player permanently stunned turn after turn, never landing a single swing
back, until it kills them outright. This is correct per spec (each landed
hit refreshes the affliction, same as poison/weaken), and it's the
well-known classic-roguelike "stun-lock" failure mode, not something to
solve by weakening the mechanic itself. Whoever places a stunning monster
in a real dungeon (`wraith` is capability-only, unplaced, as of this
writing) must design around it instead: keep `inflicts_duration` at 1 (already
the case), keep the monster's own hit rate/attack low enough relative to
player defense that consecutive landed hits aren't a near-certainty, and
avoid pairing a stunner with anything else that also wants the player's
attention in the same encounter - a solo, rare threat, not one two
monsters deep in a pack.

## 0u. Three new AI behaviors (`enrage`, `pack_hunter`, `regenerator`)

Three more `AIType` values, each a variant of `hostile_basic`'s ordinary
chase-and-attack with one extra mechanic layered on - same shape as
`sleeping_guard` (chase-and-attack gated on alert_radius) and `skittish`
(flee instead, gated on flee_hp_pct) already are. None are placed in any
dungeon yet - capability-only, same "define now, place later" pattern as
`wraith`/`gray_ooze` from §0t, deferred to the later bestiary-population
pass.

**`enrage`** - `Entity.is_enraged` (`engine/entity.py`) is a live property,
not stored state: true whenever `fighter.hp / fighter.max_hp <=
enrage_hp_pct` (default `DEFAULT_ENRAGE_HP_PCT = 0.3`). While true,
`effective_attack` adds `enrage_attack_bonus` (default
`DEFAULT_ENRAGE_ATTACK_BONUS = 2`). Being a live computation off current hp
(mirroring `_weaken_penalty`'s shape) rather than a one-time flag means it
correctly *un*-enrages if this entity is ever healed back above the
threshold - nothing does that today, but the property doesn't assume it
never will. `engine/combat.py`'s `_apply_damage` logs "fights with berserk
fury!" alongside the damage line whenever `attacker.is_enraged`, the same
place/shape as the crit message. The two engine-level defaults live in
`engine/entity.py` itself, not alongside `DEFAULT_FLEE_HP_PCT` etc. in
`engine/engine.py` - `effective_attack` needs the resolved bonus value, and
`engine/entity.py` can't import `engine/engine.py` (the dependency only
ever runs the other way).

**`pack_hunter`** - the one behavior that can't be a pure `Entity`
property, because "is an ally nearby" depends on the whole map's current
entity positions, which only `Engine` (holding `game_map`) has access to.
`Engine._has_nearby_ally` scans every other living, non-`PEACEFUL_AI_TYPES`
entity for one within `pack_radius` tiles (default
`DEFAULT_PACK_RADIUS = 3`); `_perform_ai`'s `AI_PACK_HUNTER` branch
recomputes this fresh every time the entity acts and writes the result into
`Entity.pack_bonus_active` (0, or `pack_attack_bonus` /
`DEFAULT_PACK_ATTACK_BONUS = 1`) *before* calling `_chase_and_attack` -
`effective_attack` just adds whatever's currently sitting there. This is
the same "Engine mutates a live field on Entity right before combat reads
it" shape `equipped_weapon`/`equipped_armor` already establish, not a new
pattern - `pack_bonus_active` starts at 0 for every entity and is only ever
written by the `AI_PACK_HUNTER` branch, so it's inert for everything else.
It can go briefly stale between this entity's own turns (recomputed, not
cleared, so it still reflects last turn's answer if read from anywhere
else) - harmless in practice, since nothing displays a monster's
`effective_attack` today (`engine/render.py` only ever shows the player's).
The bonus is flat and binary (any one ally in range vs. none), not scaled
by ally count - deliberately, so a pack_hunter placement can't snowball
into an unbounded stack just from grouping enough of them together.

**`regenerator`** - `Engine._regenerate`, called from `_perform_ai`'s
`AI_REGENERATOR` branch immediately before `_chase_and_attack`, heals
`regen_amount` (default `DEFAULT_REGEN_AMOUNT = 2`) HP per turn, capped at
`max_hp`, logging "regenerates N HP." Runs every turn this entity acts,
mid-fight or not - deliberately not gated on distance-to-player or combat
state, since the whole point is a race against sustained damage: a player
who can't out-pace the regen never finishes the fight, rather than just
taking longer to. For hits-to-kill math (§2), this means a `regenerator`'s
effective HP pool isn't just its `hp` stat - a slow, interrupted fight
against one effectively heals back some fraction of whatever damage
landed between engagements, so `regen_amount` needs to be small relative to
the player's expected per-turn damage output, or the fight simply can't be
won by attrition.

## 0v. Monster drops (`EntityDef.drop_item_id`/`drop_chance`)

There were no monster drops at all before this pass - a kill granted
`xp_reward` and nothing else. `Engine._maybe_drop_loot`, called from
`on_entity_death` right after the `xp_reward` check, rolls
`entity.drop_chance` and on success places one fresh `drop_item_id` on the
ground at the entity's own `(x, y)` - reusing `item_entity_from_def` +
`game_map.entities.append`, the exact shape `build_game_map`'s own
item-spawn loop already uses, so a drop is afterward just an ordinary
ground item: `PickupAction` picks it up like anything else, no special
casing anywhere else in the engine. No-ops entirely if the entity has no
drop configured, or `self.catalog is None` (a synthetic `Engine` built
without a catalog - same guard `complete_quest`'s `reward_item_id` branch
already uses).

**One item, one chance - deliberately not a weighted drop table.**
`EntityDef.drop_item_id`/`drop_chance` are a single optional pair, "both
or neither" validated the same shape as `inflicts_effect`/
`inflicts_duration` (§0t). Nothing in the current content roster needs
more than one possible drop per monster, and a single pair is trivial to
widen into a list later without touching what's already shipped -
premature to build the general case before anything needs it.
`content/loader.py` cross-references `drop_item_id` against the item
catalog (fails loudly on a typo, same `shop_inventory`/`trainer_perks`
precedent) and rejects it on a `PEACEFUL_AI_TYPES` entity, same reasoning
as `xp_reward`'s existing check - killing a villager is murder, not a
legitimate kill, and shouldn't reward the player either way.

**Wired onto real, already-placed monsters, not deferred like the last
two passes.** Unlike `enrage`/`pack_hunter`/`regenerator` (§0u) and
`stun`/`weaken` (§0t), which only touched still-unplaced bestiary entries,
drops were added directly to monsters already spawning in shipped
dungeons - `goblin`/`guard`/`crossbow_guard` (a conservative first-pass
25% chance of a `gold_pile`), `bandit` (30%, a hair more likely - it's
explicitly written as fighting for coin), and `bandit_captain`/
`windrest_captain` (guaranteed `gold_stash`, the bigger pile - a leader's
cut, not a coin flip). The mechanic itself needed nowhere placed to be
verified in isolation the way a new AI behavior or status effect does; a
drop's only observable effect is "an item appears," so wiring it onto
real content immediately is both the simplest way to exercise it and
actually delivers the gap the whole pass exists to close.

## 0w. Elite monster variants (`LegendEntry.elite`)

A stronger, more rewarding version of an ordinary catalog monster for one
specific placement - `{entity: orc, elite: true}` in a level's legend -
without a second, near-duplicate `EntityDef` per elite. `LegendEntry.elite`
(only meaningful alongside `entity`, validated the same "requires" shape as
`announce`/`description`) flows through `EntitySpawn.elite` into
`engine/game_map.py`'s `build_game_map`, which calls `_apply_elite_scaling`
on the just-built `Entity` before it's added to `game_map.entities`. This
is a **per-placement flag on the level file, not a property of the
monster type** - the same `wolf` catalog entry can be an ordinary spawn in
one room and an elite in another, unlike `enrage`/`pack_hunter`/
`inflicts_effect` (§0t/§0u), which are baked into the `EntityDef` itself
and apply to every spawn of that id everywhere.

**Scaling, and why each stat scales the way it does:**
- `max_hp`/`attack`/`xp_reward` scale by `ELITE_STAT_MULTIPLIER`/
  `ELITE_XP_MULTIPLIER` (both `2.0`), rounded up with `math.ceil` - the
  same "must always come out strictly higher, never accidentally
  identical at a low stat value" reasoning `engine/combat.py`'s crit
  multiplier already established (§2's balance methodology).
- `defense` gets a flat `ELITE_DEFENSE_BONUS` (`1`) instead of a
  multiplier - most of the roster has single-digit or zero base defense,
  where multiplying does nothing at all (`0 * 2.0 == 0`).
- `drop_chance` becomes guaranteed (`1.0`) **only if the base entity
  already has `drop_item_id` set** (§0v) - elite amplifies the existing
  drop system, it deliberately doesn't invent a separate elite-only loot
  table. An elite spawn of a monster with no drop configured still drops
  nothing.
- `name` gets an `"Elite "` prefix and `color` is brightened
  (`min(255, int(c * 1.4) + 20)` per channel) - the two-part signal that
  makes an elite readable as different at a glance: the name in every
  message/HUD line that already prints it, the color in the map view
  itself. This only affects the plain-glyph ASCII rendering path
  (`engine/render.py` reads `entity.color` directly) - a sprite-mode
  render keyed by `entity_id` would still show the base monster's sprite,
  since `entity_id` itself is unchanged (still `"goblin"`, not a distinct
  elite id). Acceptable for a first pass; revisit if/when sprite mode
  needs its own elite treatment.

**Rejected on a peaceful NPC**, same reasoning `xp_reward`/`drop_item_id`
already establish - checked at the legend/spawn level in `load_level`
(not `load_catalog`, since `elite` is a per-placement fact about a
specific level file, not a fact about the catalog entry itself).

## 0x. The trinket slot (`ItemDef.trinket_effect`/`trinket_bonus`)

A fourth equipment slot (`Entity.equipped_trinket`, alongside
`equipped_weapon`/`equipped_armor`/`equipped_ranged_weapon`) for a
passive, **non-flat-stat** item effect - a percentage-point rate bonus
instead of a flat attack/defense/ranged-attack number, which is what
distinguishes a trinket from ordinary gear. `TrinketEffectKind`
(`content/schema.py`) is `"crit_chance" | "dodge_chance" | "xp_gain"`,
the same "string constants + Literal" shape as `AIType`/`EffectKind`.
`ItemDef.trinket_effect`/`trinket_bonus` are "both or neither" (same
validator shape as `inflicts_effect`/`inflicts_duration`), and
`not_multiple_equipment_slots` now also rejects a trinket that also sets
`attack_bonus`/`defense_bonus`/`ranged_attack_bonus` - ambiguous which
slot it belongs in, same reasoning that validator already existed for.

**Where each effect kind is actually read** - deliberately not a single
shared code path, because a trinket's bonus is fundamentally about a
specific *moment*, not a standing stat:
- `crit_chance`/`dodge_chance`: read by `engine/combat.py`'s
  `_trinket_bonus(entity, kind)` at the exact point `_apply_damage` rolls
  `DODGE_CHANCE`/`CRIT_CHANCE` - `dodge_chance = DODGE_CHANCE +
  _trinket_bonus(defender, "dodge_chance")`,
  `crit_chance = CRIT_CHANCE + _trinket_bonus(attacker, "crit_chance")`.
  Correctly *inert* whenever `COMBAT_VARIANCE_ENABLED` is `False` (§2) -
  same "one flag turns off the whole mechanic" contract item 1 already
  established; a trinket boosting a disabled mechanic has nothing to
  boost.
- `xp_gain`: read directly by `Engine._award_xp` - the single funnel
  every XP source already routes through (kills, quest completion,
  landmark discovery), so an XP trinket boosts *all* of them alike, not
  just kills. `math.ceil`, not `round` - same "must always grant strictly
  more, never accidentally the same amount at a low XP value" reasoning
  as `combat.py`'s crit multiplier.

Neither path touches `effective_attack`/`effective_defense`/
`effective_ranged_attack` at all - that's the entire point of the
distinction from weapon/armor/ranged gear.

**Auto-equip-on-pickup, same UX contract as every other slot, but a
different comparison.** `PickupAction._equip` (weapon/armor/ranged)
compares one flat bonus number directly. A trinket can't be compared that
way across kinds - a crit-chance trinket and an XP-gain trinket aren't
fungible - so `_equip_trinket` only ever auto-swaps when the candidate
shares the *exact same* `trinket_effect` as whatever's currently equipped
and beats its `trinket_bonus`; a different kind (or the same kind but not
better) is left on the ground untouched, exactly the "not obviously
better, don't swap" outcome `_equip` already gives every other slot in
that situation.

**A known, deliberate gap: buying a trinket from a shop doesn't equip
it.** `Engine.buy_from_shop` has never routed through the
auto-equip-if-better logic at all, for *any* slot - it always drops a
purchase straight into `player.inventory`, same as it always has for
`rusty_dagger`/`leather_armor` before this pass. There is no manual
"equip from inventory" screen anywhere in the game, so a shop-bought
weapon/armor/ranged/trinket item is currently unusable once bought - a
real, pre-existing bug this pass surfaced but didn't fix (flagged
separately; out of scope for "add a slot"). Every trinket this pass ships
is therefore also placed as a real ground `item_spawn` (`lucky_charm` in
`forgotten_ruins/level_01.lvl`) so the mechanic is genuinely reachable in
play today, not just sellable-but-inert in a shop window.

`tools/balance.py`'s `gear_xp_equivalent`/`build_xp_total` (§0s)
deliberately don't account for a trinket's value - there's no real
playtesting data yet to calibrate "how much is +1% crit chance worth"
against a flat attack/defense point the way `stat_point_rate` already is
for the other three slots. Revisit once trinkets have shipped enough to
have real balance data behind them.

## 0y. Affix items (`ItemDef.affix_effect`/`affix_potency`/`affix_duration`/`affix_chance`)

A secondary status-effect proc on a weapon or armor item, sitting
alongside that item's ordinary `attack_bonus`/`defense_bonus` - reuses
`EffectKind`/`ActiveEffect`/`Fighter.active_effects` exactly as they
already work for a monster's `inflicts_effect` (§0t), rather than
inventing a second status-effect mechanism. The one genuinely new piece
is `affix_chance`: unlike a monster's bite, which always inflicts its
effect on a landed hit, an affix is a **probability** roll per hit -
without that, giving the player an always-on stun weapon would trivialize
combat outright (recall §0t's stun-lock write-up; an unconditional
player-side stun would just point that same failure mode at every
monster in the game instead of the other way around).

**Two triggers, not one, both fired from inside `_apply_damage`'s
existing `damage > 0` block** (same gate `attacker.inflicts_effect`
already uses):
- `engine/combat.py`'s `_maybe_apply_weapon_affix` - an **offensive**
  proc. Rolls `attacker.equipped_weapon.item.affix_chance`; on success,
  inflicts `affix_effect` on the **defender**. A venomous dagger poisons
  whatever it cuts.
- `_maybe_apply_armor_affix` - a **defensive/retaliation** proc, the
  mirror image. Rolls `defender.equipped_armor.item.affix_chance`; on
  success, inflicts `affix_effect` on the **attacker** instead - spiked
  armor doesn't protect the wearer from anything, it punishes whoever hit
  them. Both read from the item that's actually relevant to that role
  (`attacker.equipped_weapon` for the offensive one,
  `defender.equipped_armor` for the defensive one) - a weapon's affix
  never fires off a defender's turn, and vice versa.

**Schema validation, following two established shapes at once:**
`affix_effect`/`affix_duration`/`affix_chance` must all be set together or
not at all (a three-way extension of the "both or neither" shape
`inflicts_effect`/`inflicts_duration` already uses - `affix_chance` had
to join that group too, since an affix with no chance to fire, or a
chance with nothing to fire, are both meaningless). `affix_potency`
follows `inflicts_potency`'s own kind-dependent rule unchanged (required
for poison/weaken, rejected for stun). A new `affix_requires_weapon_or_armor`
validator additionally requires **exactly one** of `attack_bonus`/
`defense_bonus` to be set whenever `affix_effect` is - resolving which of
the two triggers above applies to this specific item, and rejecting an
affix on a trinket/ranged/potion item where neither trigger would ever
run.

**Deliberately not gated on `COMBAT_VARIANCE_ENABLED`.** That flag (§2) is
specifically the crit/dodge experiment's own kill switch, not a general
"anything probabilistic in combat" toggle - the status-effect framework
(§0t) already shipped with no such gate, and affixes are status effects
built on that same framework, not a new instance of the crit/dodge
mechanic. An affix's `random.random()` roll is its own independent event,
always live.

Ships two real affix items, each placed as a real ground `item_spawn` (not
just catalog-defined) so the mechanic is reachable in play today, same
"deliver a working example" precedent §0v/§0w/§0x already established:
`venomous_dagger` (poison, `forgotten_ruins/level_02a.lvl`) and
`thorned_plate` (weaken, `prison_tower/level_01.lvl`) - inherits the same
shop-purchase-doesn't-auto-equip gap §0x already flagged (out of scope
here too), which is exactly why both ship as ground pickups rather than
shop stock alone.

## 0z. Active-skill perks (`PerkDef.skill_effect` and the two rate-bonus perks)

`PerkDef` was originally exactly-one-of-four-flat-stat-bonuses, with a
docstring already anticipating "a perk needing a mechanic beyond a flat
stat bonus... isn't representable yet." This pass fills that gap with two
more perk shapes: a **passive rate bonus** (the permanent, perk-tree
version of a trinket's `crit_chance`/`dodge_chance`, §0x) and an **active
skill** (manually triggered, on a cooldown). A `PerkDef` is now exactly
one of three things - flat stat bonus, rate bonus, or active skill -
enforced by `exactly_one_bonus_or_skill`.

**Passive rate bonuses (`crit_chance_bonus`/`dodge_chance_bonus`,
`steady_aim`/`light_feet`)** fold permanently into
`Fighter.perk_crit_chance_bonus`/`perk_dodge_chance_bonus` via
`apply_perk_stat_bonus` (the same function that already folds
`ranged_attack_bonus` into `perk_ranged_attack_bonus` for the identical
"no base stat to bump" reason) - `Engine.learn_perk`'s existing call site
needed no changes at all. `engine/combat.py` adds both this and a
trinket's own bonus on top of the base `CRIT_CHANCE`/`DODGE_CHANCE`
additively - a perk and a matching trinket stack, same as any other
additive bonus in this project. Because `apply_perk_stat_bonus` already
runs in a loop over `learned_perk_ids` at save-restore time
(`engine/save.py`'s `_build_player`), these two bonuses are correctly
re-derived on load with **no save-format changes required** - the save
only needs to remember *which* perks were learned, same as every other
stat bonus.

**Active skills (`skill_effect`/`skill_cooldown_kind`/
`skill_cooldown_amount`, `second_wind`/`ground_pound`)** are triggered
manually via `engine/actions.py`'s `UseSkillAction(perk_id)` - a real,
turn-costing action reached through the normal `process_player_action`
path, same as `UseItemAction`, not a free action like Talk/Look.
`Engine.use_skill` validates the perk exists, is actually an active skill,
is learned, and isn't on cooldown, then applies one of two effects and
sets `entity.skill_cooldowns[perk_id] = perk.skill_cooldown_amount`:
- `SKILL_EFFECT_HEAL` (`second_wind`): restores `skill_heal_pct` of
  `max_hp`, capped at `max_hp` - `math.ceil`, not `round`, same
  "must always grant strictly more, never accidentally the same amount at
  a low value" reasoning as the crit multiplier and the XP trinket.
- `SKILL_EFFECT_AOE_DAMAGE` (`ground_pound`): strikes every
  non-peaceful, adjacent (8-directional) hostile entity via
  `resolve_skill_damage`, a public wrapper around the exact same
  `_apply_damage` pipeline `resolve_attack`/`resolve_ranged_attack` use -
  dodge, crit, and weapon-affix procs all apply to a Ground Pound hit
  exactly as they would to an ordinary swing. This is a deliberate
  emergent synergy (a venomous dagger's affix can trigger off a Ground
  Pound hit too), not a special case worth avoiding. The target filter is
  `fighter is not None and is_alive and ai not in PEACEFUL_AI_TYPES` -
  *not* also `ai is not None`, which would be both redundant (no item
  entity ever has a `Fighter` in the first place) and wrong (a real
  monster's own `ai` is never actually `None` in shipped content) - an
  early version of this filter had that extra, incorrect check, caught by
  its own tests using `ai=None` test-double monsters (this file's own
  "doesn't act on its own turn" convention) as legitimate Ground Pound
  targets.

**Two independent cooldown clocks, matching the user's own explicit
framing** ("a turn-based cooldown would be fine for a less powerful
skill... Second Wind on a turn timer would give the player unlimited
healing that bypasses the world clock"):
- `SKILL_COOLDOWN_TURNS` (`ground_pound`, 5 turns): ticked by
  `Engine._tick_skill_cooldowns("turns")`, called once per turn from
  `process_enemy_phase`, any turn anywhere - dungeon or overworld.
- `SKILL_COOLDOWN_HOURS` (`second_wind`, 24 hours): ticked by the same
  `_tick_skill_cooldowns("hours")`, but called only from
  `_advance_world_clock` - which itself only ever runs on an overworld
  turn (§0p/§2's own established invariant: the world clock is frozen
  inside any dungeon/settlement). A player camped inside a dungeon
  fighting the same encounter for 50 turns sees Second Wind's cooldown
  not move at all; only actually leaving to the overworld and taking
  turns there advances it - the literal "you'd have to leave the dungeon
  and rest" the skill's own flavor text describes, not a figure of
  speech. Both share one small helper (parameterized by cooldown kind)
  rather than two near-duplicate methods; entries reaching 0 are deleted
  outright, not left inert at 0 - same "membership is the state"
  convention `Fighter.active_effects` already established (§0t).

**Cooldown state is genuinely live, not re-derivable** - unlike the
passive rate bonuses above, `Entity.skill_cooldowns` depends on *when* a
skill was last used, which `learned_perk_ids` alone can't reconstruct, so
`SavedPlayer.skill_cooldowns` is saved directly rather than re-derived at
restore time.

**Fixed key bindings, not a hotbar.** `engine/input_handlers.py` binds
`W`/`K` directly to `UseSkillAction("second_wind")`/
`UseSkillAction("ground_pound")` - a deliberate, scope-bounded choice
given there are only two active skills so far, not a general "assign any
skill to any slot" system. `tools/play_llm.py` exposes the same
capability as a generic `skill <perk_id>` subcommand instead (since a CLI
has no fixed-key constraint), and both HUD renderers
(`engine/render.py`'s `render_hud`, `tools/play_llm.py`'s
`render_hud_text`) add one line listing every *learned* active skill with
its live cooldown status - omitted entirely for a player who hasn't
learned any yet, so the HUD stays quiet until it's relevant.

Both perks are taught by the two existing Trainer NPCs
(`millhaven_trainer`/`wayford_trainer`), alongside `steady_aim`/
`light_feet` - real, reachable content from the moment this shipped, the
same "don't just define capability, place it" precedent §0v/§0w/§0x
already established, verified end-to-end via `tools/play_llm.py`'s
`testbuild`/`skill` commands (Second Wind healing on demand, on a
24-hour cooldown that only moves on the overworld; Ground Pound clearing
a pack of adjacent monsters at once, back off cooldown five turns later).

## 0aa. Perk tiers (`PerkDef.requires_perk_id`)

A perk can gate its purchase behind an earlier one -
`requires_perk_id: toughness_1` on `toughness_2` means `Engine.learn_perk`
refuses to sell tier 2 until tier 1 is already in
`Entity.learned_perk_ids`. Orthogonal to *which* of the three perk shapes
(§0z) a tiered perk is - `requires_perk_id` only gates the purchase
moment, nothing about how the perk's own bonus applies once bought.

**Both tiers stay learned forever and simply stack** - a perk is never
unlearned or replaced (established well before this pass), so
`requires_perk_id` is purely a purchase gate, not an upgrade/replace
mechanic. `toughness_1` (+5 max HP) and `toughness_2` (+8 max HP) both
remain in `learned_perk_ids` once both are bought, for +13 total - there
is no single "current tier" to track, no removal of tier 1's bonus when
tier 2 is learned. This is why `learn_perk`'s prerequisite check is pure
`learned_perk_ids` membership, nothing about *which* Trainer taught it:
learning `toughness_1` from one NPC satisfies `toughness_2`'s requirement
at any other Trainer that happens to teach it too.

**Validated at three levels, matching the project's established "fail
loudly at content-load time" posture:**
- `content/loader.py` cross-references `requires_perk_id` against the
  full perk catalog once every `PerkDef` is loaded (schema.py alone can't
  do this - a single `PerkDef` has no visibility into the rest of the
  catalog, the same reason `trainer_perks`/`drop_item_id`/`shop_inventory`
  are all cross-checked in loader.py rather than schema.py). An unknown
  id and a perk requiring itself are both rejected directly.
- **Cycle detection**: `A requires B requires A` would make every perk in
  the cycle permanently unlearnable - each one forever waiting on the
  next. Walking each perk's own prerequisite chain and checking for a
  revisit catches this (and any longer cycle) before it ever ships,
  rather than leaving it as a live soft-lock a player could actually hit.
- `Engine.learn_perk` re-checks at the moment of purchase (not just at
  content-load time) - the actual gate a player experiences, returning
  `"You need to learn {prereq name} first."` the same "return + log"
  status-message convention every other `learn_perk`/`buy_from_shop`
  rejection already uses.

**The trainer screen shows *why* a tiered perk isn't purchasable yet**,
not just that it isn't: `render_trainer`'s per-perk tag checks
`requires_perk_id` before affordability (mirroring `learn_perk`'s own
check order) and, when unmet, shows `"(requires {prereq name})"` instead
of `"(can't afford)"` - a player staring at `toughness_2` with plenty of
XP would otherwise have no way to tell why the trainer keeps refusing it.

Ships one real tiered perk, `toughness_2` (requires `toughness_1`, both
taught by the existing Trainer NPCs) - proving the mechanism rather than
building out a full tree for every perk line, the same conservative,
one-clear-example scope every mechanic in this pass has shipped with.

## 0ab. Populating the bestiary (`giant_rat`/`kobold`/`kobold_shaman`/`orc`/`hobgoblin`/`giant_spider`)

The last gap this pass closes: several catalog monsters had real stats and
real mechanics (§0u/§0t) but no `{entity: ...}` spawn anywhere in any
level file - defined, never placed, invisible in actual play. A quick
audit (`grep -rl "entity: <id>" data/dungeons/`) found `wolf`/`wraith`/
`gray_ooze` already placed by an earlier worldgen pass (and placed well -
`wraith` in particular already sits as a solitary guardian, not paired
with anything else that wants the player's attention, exactly the
stun-lock caution §0t raised before this pass ever got to it). Six
remained genuinely unplaced: `giant_rat`, `kobold`, `kobold_shaman`,
`orc`, `hobgoblin`, `giant_spider`.

Each was placed once, into an existing level whose theme or roster
already fit it, rather than authoring new levels or a new dungeon -
populating the bestiary, not expanding the map:
- `giant_rat` (regenerator) - `broken_watch/level_01.lvl`, alongside the
  existing lone `rat` - "the big one" in an already-established vermin
  presence.
- `kobold` x2 + `kobold_shaman` x1 - `sunken_mine/level_01.lvl`, a new
  kobold warren in the mine's first level (already housed goblins/rats) -
  the shaman gives the melee pair ranged backup, matching `kobold`'s own
  "quick to pile in three-deep" flavor text.
- `orc` (enrage) - `sunken_mine/level_03.lvl` ("The Last Vein," the
  mine's sealed, terminal level), alone near the stairs down - the same
  "solitary guardian of the deepest reach" role `ogre` already plays in
  `forgotten_ruins`.
- `giant_spider` (poison) - `silver_mountain_caves/level_02.lvl`, a few
  tiles from one of the level's five existing `cave_spider`s - the
  literal "big cousin" of a monster already thoroughly present there.
  Poison's refresh-not-stack rule (§0t) means a player fighting near both
  at once never takes double poison damage from two different attackers
  landing hits - the mechanic already guards against exactly this
  clustering, nothing extra needed here.
- `hobgoblin` - `forgotten_ruins/level_02b.lvl` ("The Goblin Warren"),
  among its two existing `goblin`s - a commander for a warren that didn't
  have one, statted between `goblin` and `ogre` (hp 18 / attack 6 /
  defense 2) rather than at either extreme.

**Placement, not rebalancing** - each addition was checked against the
existing roster it joined (no stun-capable monster placed near another,
no cluster whose simultaneous burst damage would wildly exceed what that
dungeon's existing monsters already establish) but wasn't run through a
full formal hits-to-kill pass (§2) the way a from-scratch monster's own
stats already were when each mechanic shipped (§0t/§0u). Exact tuning
once these are played through for real is the natural next step, same
"conservative first pass, defer exact tuning" precedent this whole
project has followed since `cave_spider`'s own poison numbers.

Every new spawn verified via `content/loader.py`'s real `load_dungeon_registry`
(catches a malformed map row or unknown legend id immediately) and via a
live `tools/play_llm.py` session against real dungeon content - the same
verification bar every mechanic in this pass has been held to.

## 0ac. A second power band: the Northern Steppe bestiary (`ash_bound_husk` and five others)

Every monster before this pass (`0ab`'s batch included) was calibrated
against a player near baseline stats - `ogre`/`stone_sentinel`'s hp
28-30/attack 8/defense 3 is that whole era's ceiling. The Northern
Steppe (`docs/region_bibles/northern_steppe.md`) needed something a
thoroughly-Heartlands-geared player would still call "challenging," so
rather than nudge the existing ceiling up, this pass opened a **second,
explicitly higher power band** - six new entities, still capability-only
(not placed in any level yet, same discipline as `0ab`/`0u`/`0t`'s
unplaced batches), sized against a concrete **reference build** instead
of player baseline: roughly 300 XP spent on perks (both Toughness tiers
+ Weapon/Shield Training + both rate perks, `data/perks.yaml`) plus a
found mid-upper gear tier (a broadsword/bone_plate/orcish_bow
equivalent) - `tools/balance.py`'s `build_xp_total` against exactly that
perk list confirms the 300 XP figure and the derived effective stats
(~43 hp, ~12 melee attack, ~6-9 defense depending how optimized the
gear is). See `data/entities.yaml`'s own comment block above these six
entries for the full hits-to-kill table this was checked against, in
both directions, at both ends of that defense range - the same
discipline §2 asks for, just against a new baseline instead of the old
one.

**Three tiers, one per corruption band**, escalating in a different way
each time rather than just bigger numbers:
- Frayed Edge (challenging): `ash_bound_husk` (`pack_hunter` - a lone one
  is manageable, several aren't) and `bound_eye` (`ranged_basic` - a
  glass-cannon support threat, not a primary one).
- Cinder Marches (very dangerous): `stitched_vanguard` (`regenerator`,
  a genuinely sustained fight), `hollow_chanter` (`ranged_basic` +
  `weaken` - saps the player's own damage output mid-fight), and
  `bound_crawler` (`hostile_basic` + `poison` - added later, the
  roster's first poisoner; every other entity here reuses
  regenerator/weaken/pack_hunter/enrage/stun).
- Hollow Reach (extremely dangerous, deliberately matching the
  eventual necroship's own difficulty - see the region bible):
  `charnel_colossus` (`enrage` - a burst-damage common patrol, worse
  once it's already losing) and `excavation_warden` (`sleeping_guard` +
  `stun` - the highest defense in the game, an attritional fight rather
  than a fast one, made dangerous by the stun-lock risk (§0t) compounding
  over many rounds rather than by raw per-hit damage). `excavation_warden`
  is placed here on purpose: it's the concrete, mechanical reason the
  region's Elder Age dig sites aren't accessible yet, not just narration
  that they aren't.

**Sprites** (`data/sprites.yaml`) all draw from `rltiles` by name, no new
sheet needed: `kobold_zombie` (Husk), `unseen_horror` (Eye - reframed as
a torn-free, bound eye rather than literal bone, once the actual art
didn't match the first-draft "bone construct" concept - picking the
concept to fit an existing sprite, not forcing a sprite to fit an
already-fixed concept, same lesson as `docs/content_design_process.md`'s
"Grounding an abstract mechanic" note in §4), `ettin_zombie` (Vanguard -
its native two-headed silhouette already reads as "more than one body's
worth of parts" with zero recoloring needed), `mummy_priest` (Chanter),
`abomination_large4` (Colossus), and `barrow_wight` (Warden - the most
visually commanding option available, deliberately reserved for the
roster's single toughest entity). `demonic_crawler` (Bound Crawler,
added later) rounds out Cinder Marches - a genuinely alien insectoid
silhouette, picked specifically for this roster rather than the cave
bestiary it was first spotted alongside (see §0ae) precisely because it
reads as *wrong* rather than merely animal.

## 0ad. Visitor band ambush encounters (`Engine._maybe_trigger_visitor_band_encounter`)

The user's explicit ask, after `0ac` shipped a roster with nowhere to
appear yet: make `ashen_plains`/`blighted_forest` stand out from an
ordinary hazard tile like `dunes` by more than the shared chip damage -
a chance, each turn spent on one, to pull the player into a fight with a
band of the Visitor's creations. First built as a direct-spawn-onto-the-
overworld-map mechanic; the user clarified they meant something modeled
on `goblin_ambush` instead (`0g`) - pulled off the overworld into a
dedicated encounter dungeon, not monsters appearing where you stand.
Rebuilt on that model. The one genuinely new piece relative to
`goblin_ambush`: the trigger itself is tile-kind-and-chance (same
"checked by tile kind, not location" discipline `0p`'s hazard damage
already established), not quest-gated, and can fire repeatedly rather
than once per run - closer to a classic roguelike random encounter than
a scripted story beat, wearing `goblin_ambush`'s exact delivery
mechanism.

**The trigger, Engine-side**: `_maybe_trigger_visitor_band_encounter`,
called from `process_enemy_phase` right after `_apply_environmental_hazard`
(same turn, same `VISITOR_BAND_TILE_KINDS` check), rolls
`VISITOR_BAND_ENCOUNTER_CHANCE` (10%), gated on `is_overworld` (mirroring
`_due_encounter`'s own gate in `main.py`, since this drives the same
kind of cross-Engine handoff) and sets `wants_visitor_band_encounter` -
a mailbox flag, same shape as `wants_overworld`/`pending_dungeon_entry`.
This `Engine` has no access to the dungeon registry, so it can only
signal the intent; `main.py`'s `resolve_transition` is what actually
acts on it.

**The redirect, main.py-side**: `_redirect_into_visitor_band`, checked
first inside `resolve_transition`'s existing `is_overworld` block (ahead
of `_due_encounter`), departs the player onto
`VISITOR_BAND_AMBUSH_DUNGEON_ID` ("visitor_band_ambush," a real
dungeon-registry entry - `data/dungeons/visitor_band_ambush/`, an open
`plains` clearing ringed by `mountain` with gaps for `open_boundary` to
work, no fixed roster of its own; see its own dungeon bible). Picks a
band size and roster by the player's row at the moment of firing
(`roll_visitor_band`, `engine/engine.py` - the same three corruption
bands `0ac`'s roster was tiered against,
`HOLLOW_REACH_MAX_Y`/`CINDER_MARCHES_MAX_Y` thresholds against the
Northern Steppe's own local-y-equals-global-y coupling, documented
in-line same as `0p`'s own content-shape assumptions), places them on
walkable, unoccupied tiles near the arena's `player_start`
(`nearby_walkable_tiles`, `engine/game_map.py`) via `entity_from_def`
(also `engine/game_map.py` - extracted from `build_game_map`'s own
entity-spawn loop, a pure refactor verified against the full suite
before use, so a runtime-injected monster and a level-authored one build
an identical `Entity` from the same `EntityDef`).

**Never resumes a cached fight - always rebuilds fresh.** Every other
encounter dungeon (`goblin_ambush` included) caches its `Engine` in
`active_engines` and resumes it on a later visit, because the fight is
always the same one. This dungeon's roster is different every single
time it fires, so `_redirect_into_visitor_band` always builds a new
`Engine` and unconditionally overwrites whatever was previously cached
under that dungeon id - resuming a stale one would either replay a
finished fight or silently discard a freshly rolled band. Verified with
a dedicated test that fires the encounter twice and checks the second
`Engine` is a distinct instance with live (not already-killed) monsters.

**`excavation_warden` never rolls** - every band pool in
`roll_visitor_band` draws only from the other five ids, keeping the
Warden's Elder-Age-site placement meaningful rather than diluting it
into the ambient encounter pool (see `0ac`).

**Known limitation, accepted rather than solved**: a band's monsters are
appended directly to the arena's `GameMap.entities`, not through
`LevelDef.entity_spawns`, so they never populate `GameMap.entity_spawn_index` -
the only thing `engine/save.py`'s `capture_save`/`restore_save` actually
round-trips monster state through. Saving mid-ambush and reloading loses
the band entirely. Same "conservative first pass, document the gap"
precedent as monster status effects never persisting across a save/load
(`0t`) - see the dungeon's own bible for the full note.

## 0ae. A second endgame roster: Silversilk Caves' depths (`deep_spider` and four others)

`silver_mountain_caves`'s own bible flagged, from the day it shipped,
that "the genuinely dangerous creatures the settlers always avoided"
were deliberately left unbuilt past its Sealed Passage - a real hook,
noted rather than built, same discipline as every other "flag it, don't
build it" deferral in this project. `0ac`'s Northern Steppe bestiary
pass gave that hook something concrete to finally be built against: a
reusable "~300 XP + mid-upper gear" reference build
(~43 hp/12 melee attack/6-9 defense) for calibrating endgame-tier
monsters independent of any one region's own theme.

**A second, independent power band, not a shared roster.** Silversilk's
five new monsters (`deep_spider`, `blind_stalker`, `broodmother`,
`cave_lurker`, `elder_widow`) are calibrated against the exact same
reference build and the same three-tier escalation shape `0ac` used
(challenging -> very dangerous -> extremely dangerous/approaching Hollow
Reach), spread across three new levels (`level_03`-`level_05`) rather
than the Northern Steppe's random-encounter/dungeon-arrival split - but
share zero monster ids with the Northern Steppe roster. Two dungeons,
two thematically distinct rosters, one reusable difficulty ceiling.
`docs/dungeon_bibles/silver_mountain_caves.md`'s new "The Depths" section
has the full per-level breakdown and the hits-to-kill verification
(one-on-one combat sims with `COMBAT_VARIANCE_ENABLED` off, at both ends
of the reference build's defense range) - not repeated here.

**Deliberately not Elder Age or Visitor content.** `world_history.md`
already places this dungeon as "natural, no era or faction," and that
holds all the way to the bottom - the depths are dangerous because
they're ancient and undisturbed, not because anything corrupted or
built them. Keep it that way in any future revision: no Visitor
fingerprints, no Elder Age masonry, just something old that predates
every faction with a name.

**Sprites**: three of the five (`deep_spider`, `broodmother`,
`elder_widow`) are `recolor: true` on `giant_spider` - this dungeon's
own biggest available spider art, reused the same "one base sprite,
several recolors" way `guard`/`human` already are elsewhere in the
catalog, since Silversilk's whole identity is spiders and no third
distinct spider sprite exists in `rltiles`. `blind_stalker`
(`lurker_above`) and `cave_lurker` (`violet_fungus`) are the deliberate
exceptions, keeping the roster from reading as "the same monster three
times" despite the shared lineage.

**Level generation**: `level_03`-`level_05` are cellular-automata-carved
caves (the same organic-cave technique `0p` already names as this
dungeon's own precedent, without detailing it there) - random noise,
several wall/floor smoothing passes, largest-connected-component
extraction to guarantee full reachability, then entry/exit chosen to
maximize both graph distance and straight-line spread so each level is
a genuine full traversal rather than a short loop. Each level's climactic
chamber is a deliberately widened room (not left corridor-width) so the
solo boss encounter reads as a destination. No hand-carved chokepoint
before either boss - `0ab`'s/`0d`'s chokepoint reasoning is for
protecting the player from being surrounded by *several* monsters at
once, which doesn't apply to a solo encounter the way it did for
`level_01`'s Outer Pickets or `goblin_ambush`'s narrows.

## 0af. Settlement layout: designing a town that reads as a real place

Written after the user played three settlement regenerations (Millhaven,
twice, plus manual corrections of their own) and was still unsatisfied -
the previous fix (§0c's building-interior rule, plus a first and second
decoration pass on Millhaven) addressed *whether NPCs had houses* and
*whether decoration was composed rather than scattered*, but never
addressed the thing actually making these towns look wrong: the layout
itself has no structure. Research into real game-town design (urban
planning writers Konstantinos Dimopoulos and others, tabletop-RPG town
design) converged on a small set of principles this project's
settlement-authoring process never enforced. **This section governs any
settlement layout going forward - existing settlements should be brought
in line with it opportunistically, not all at once.**

**Draw the road network before placing a single building.** Every
settlement authored before this pass placed buildings first, wherever
there was open room, then decorated afterward - the road, if any, was an
afterthought connecting the gate to nothing in particular. Reverse the
order: draw a road network first - one main street from the gate, a hub
(the town square, below) it leads to, and branch paths reaching *every
building's actual door* - then place buildings against that network,
door facing the path that serves them. A building with no path to its
door reads as placed by an editor, not lived in.

**One town square, one real focal point.** Start from a single hub - a
well, a green, a landmark - and place civic buildings (the chief's
house, a notice board) touching it directly, the way "start from the
community center and work outward" describes. Everything else radiates
from that hub via the road network above, not scattered independently
across the map. A settlement with no identifiable "this is the middle of
town" moment has no square, no matter how much decoration surrounds it.

**Vary road width and give the network real branches, not one corridor.**
A single road bisecting the map top-to-bottom, touching nothing, is the
single biggest tell of an unplanned layout - it was Millhaven's actual
problem, not its decoration density. A main street can be a single
tile wide approaching the gate and widen into the square itself; side
streets branching off it to reach a commerce cluster, a residential
stretch, a training ground read as an actual network. Perfect
right-angle branches are an accepted limitation of this project's
rectilinear tile grid, not something to fight - the win here is
*branching and width variation*, not literal curves.

**Functional clustering, not even scattering.** Buildings and NPCs that
belong together (a shop and the mending yard beside it; several villagers
near the garden they tend) should sit near each other, forming a
legible district a player would describe in one phrase ("that's the
commerce corner"), rather than being spaced evenly across the whole
footprint so every quadrant has "some stuff" in it. A named set piece
that's meant to be tucked away or hard to stumble onto (Millhaven's
Debtor's House is the reference example) earns that by being *off* the
road network on purpose, not by being randomly far from everything else.

**Scale the footprint to the cast, not the other way around.** The
oversized-map, sparse-decoration failure mode from Millhaven's second
regeneration wasn't a decoration problem - the map was bigger than its
population justified, so no plausible amount of decoration would have
filled it without reading as clutter. Size a settlement's footprint
against its actual NPC/building count: compare against shipped
reference points (`farrows_stake` 20x11 for 3 NPCs and no real
buildings, `saltmarsh` 36x28 for 5 NPCs and 2 buildings, `northern_watch_post`
26x16 for 3 NPCs and one lean-to, `grey_valley_monastery` 40x34 for 4
NPCs and 2 buildings) and size up from there proportionally rather than
defaulting to a round, generous number. A settlement that's "still a bit
small" once every district has a real reason to exist is a better
outcome than one padded out to feel appropriately large.

**Every decorative structure needs a one-line reason, named in the
bible - not just "scenery."** An unentered `wall_block` cluster with no
description anywhere is exactly the "no function = believability
breaks" failure the research above calls out - it reads as an
unexplained rectangle, not a building. If a wall cluster is worth
placing at all, name what it is in the dungeon bible (a storehouse, an
unrebuilt ruin, a collapsed shed) even if the player can never enter it -
one sentence is enough, and it's the difference between "a place" and "a
map artifact." This tightens §0c's existing decoration-philosophy
instinct (every decoration belongs to something) to cover plain
`wall_block` geometry too, which had been getting a pass on it.

**Edge definition, where the setting supports it.** A treeline, a fence
line, or a change in ground texture marking where the settlement
actually ends (as opposed to the map's own border wall, which is a
rendering boundary, not a narrative one) helps a town read as a place
that stops somewhere on purpose. Not every settlement needs this - it
should follow from the bible's own pitch (a forested settlement earns a
treeline; an open plain doesn't need one invented) - but when the
setting supports it, use it.

**Visual QA needs an actual screenshot, not just an ASCII readout.**
Every settlement pass before this one was verified via `tools/preview.py`
(an ASCII dump) and the loader's spawn counts - both catch structural
errors (bad references, ragged rows) but neither one shows what the
*rendered sprite art* actually looks like, which is what "aesthetically
pleasing" is actually a claim about. Before calling a settlement
layout finished, capture a real screenshot: build a minimal headless
harness (`tcod.context.new` + `render_all` + `context.save_screenshot`,
following `main.py`'s own render setup) that loads the dungeon, marks
the whole map explored/visible (bypassing fog-of-war, since this is a
design-review render, not gameplay), and saves an image - two or more
screenshots, camera repositioned per shot, if the map is taller than
`VIEWPORT_HEIGHT`. Look at it before declaring the layout done.

## 0ag. Splitter - a death-triggered AI behavior (`slime`)

The first of a new round of AI behaviors, and the first one whose whole
effect happens at *death* rather than on the entity's own turn -
`AI_SPLITTER`'s turn-by-turn behavior is just `hostile_basic`'s
chase-and-attack; `Engine._maybe_split`, called from `on_entity_death`
right alongside `_maybe_drop_loot`, is the entire mechanic.
`EntityDef.split_count`/`split_hp_fraction` are "both or neither," same
shape as `drop_item_id`/`drop_chance`.

**Built entirely from two helpers that already existed** -
`engine/game_map.py`'s `entity_from_def` (already used by
`Engine._maybe_spawn_visitor_band`'s runtime encounter spawns, per §0ad)
and `nearby_walkable_tiles` (already used by the same feature to place a
band without landing on top of the player). `_maybe_split` calls
`entity_from_def(edef, x, y)` for each child instead of hand-listing every
field a monster spawn needs - a copy is built the same way a *real* spawn
would be, so it can never silently drift out of sync with what
`build_game_map`'s own spawn loop sets. This is the same "don't
re-implement, reuse the extraction" instinct `item_entity_from_def`
already established for items.

**Scales off the entity's own current `max_hp`, not the catalog base** -
`child_max_hp = ceil(entity.fighter.max_hp * split_hp_fraction)` reads
`entity.fighter.max_hp`, which already reflects any elite scaling (§0w)
applied at spawn time. An elite-scaled slime therefore splits into
elite-sized-fraction children automatically, with no elite-awareness
needed inside `_maybe_split` itself - the same "read the live value, not
the definition" principle `is_enraged`/`effective_attack` already follow.

**Splits exactly once, never cascades.** A spawned child carries
`can_split=False` (an `Entity`-level flag, defaulting `True`, set once at
spawn and never mutated except here) - without it, each child would
itself be `AI_SPLITTER` with its own `split_count`/`split_hp_fraction`
still set, and could split again on its own death, and so on, potentially
without bound. One level of splitting is the intended shape (kill the
slime, kill up to two smaller slimes, done) - a hits-to-kill accounting
for a splitter has to count every subsequent child's own hp too, not just
the original's, which is genuinely more total HP than the original alone
(here: 16 + 2×ceil(16×0.4) ≈ 16 + 14 = 30 hp worth of hits across the
whole encounter, not 16).

**Placement is opportunistic, not guaranteed** -
`nearby_walkable_tiles(self.game_map, entity.x, entity.y, entity.split_count, radius=1)`
returns however many free adjacent tiles actually exist (down to zero if
the slime died somewhere fully boxed in), and `_maybe_split` spawns
exactly that many, never more than requested and never erroring on fewer.
A slime killed in a cramped corridor might only produce one child, or
none at all, instead of the two `split_count` asks for - accepted as
correct, not a bug to guard against, since "however much room there
happens to be" is the honest answer to "where do the children go."

Ships one real example, `slime` (`data/entities.yaml`) - deliberately
*not* placed into a level yet, matching the original "define now, place
later" pattern the very first bestiary-expansion pass used (§0t), since
this round of AI behaviors is being built and reviewed one at a time
before any of them get placed into real dungeons.

## 0ah. Summoner - reinforcements instead of attacking (`bone_caller`)

The second AI behavior in this round, and the first whose whole point is
turning a fight into a race: `AI_SUMMONER` spends its own turn calling one
reinforcement instead of also attacking that turn, on a cooldown
(`EntityDef.summon_entity_id`/`summon_interval`, "both or neither," same
shape as `split_count`/`split_hp_fraction`), capped at
`summon_max_active` still-living summons at once (`summon_max_active` is
independently optional - `None` means no cap at all, a deliberate escape
hatch for a summoner that's meant to be an unwinnable war of attrition
unless it dies fast).

**A summon attempt replaces the turn's attack, it doesn't add to it** -
`_perform_ai`'s `AI_SUMMONER` branch only calls `_chase_and_attack` when
`_maybe_summon` returns `False` (not time yet, or nothing could actually
be summoned). This is a real design choice, not an incidental one: a
summoner that both attacked *and* periodically added reinforcements for
free would be strictly stronger than an ordinary attacker for the exact
same stat budget, with no real trade-off - "channeling a summon instead
of swinging" is what makes rushing it down before it's summoned twice a
meaningful player choice.

**`Entity.summon_cooldown`/`summoned_children` are live, per-entity
state** (defaulting `0`/`[]`, harmless and unread for anything that isn't
a summoner) - `summon_cooldown` counts down to the next attempt exactly
the way a status effect's `turns_remaining` counts down to expiry (§0t):
reaching `0` triggers an attempt and resets to `summon_interval`,
*whether or not that attempt actually produces a summon*. A summoner
blocked by its own cap, or with nowhere free to put a new arrival, tries
again after another full interval rather than immediately on the very
next turn - the same "no free retry" shape a failed roll gets everywhere
else in this project. `summoned_children` is a live list of this specific
summoner's own actual summons (not a global count of every copy of
`summon_entity_id` on the map), pruned of the dead each time the cap is
checked - two summoners of the same kind never starve each other's caps,
and a summon dying frees its own caller's slot immediately.

**Reuses the same two helpers `slime`'s Splitter did** (§0ag) -
`entity_from_def` (already used by both the map's own spawn loop and the
visitor-band encounter system, per §0ad) builds the summoned reinforcement
the same way a real level spawn would, and `nearby_walkable_tiles`
(radius 1) finds it somewhere to land, silently offering fewer results
(down to none) rather than erroring when the caller has nowhere free -
the summon attempt is simply skipped for that cycle, same as
`_maybe_split`'s own "spawn however many tiles actually exist" posture.

Ships one real example, `bone_caller` (`data/entities.yaml`) - deliberately
weak in melee (`attack: 2`, no defense) so it's meant to be rushed down,
not traded blows with - and summons `skeleton`, an entity that already
exists in the catalog rather than a new minion invented just for this.
Not yet placed into a level, same reasoning as `slime`.

## 0ai. Charger - a telegraphed lunge with a recovery window (`boar`)

The third AI behavior in this round, and the first whose whole point is a
single risky, high-commitment action rather than a steady per-turn
effect: `AI_CHARGER` covers several tiles in one turn to close a gap the
player would otherwise have time to react to, hits harder for it, then
is defenseless for exactly one turn afterward. `EntityDef.charge_range`/
`charge_attack_bonus` are independently optional, each with its own
engine-level fallback (`DEFAULT_CHARGE_RANGE`/`DEFAULT_CHARGE_ATTACK_BONUS`)
- the same "omit-friendly" convention `alert_radius`/`flee_hp_pct` already
established, not a "both or neither" pair, since either alone still means
something sensible on its own.

**A charge only triggers when the geometry actually reads as a charge** -
`_perform_ai`'s `AI_CHARGER` branch requires `distance > 1` (already
adjacent is just an ordinary attack, no lunge needed),
`distance <= charge_range`, *and* the player aligned in a straight line
(`dx == 0 or dy == 0 or abs(dx) == abs(dy)` - orthogonal or an exact
diagonal, not merely "roughly toward"). Get any of these wrong and the
entity falls through to plain `_chase_and_attack` instead - a charger
one tile off the diagonal, or one tile past its range, behaves exactly
like `hostile_basic` that turn, not like a broken charger.

**The lunge is built from the same `MovementAction` every ordinary step
already uses, just repeated** - `Engine._charge` steps once per tile
(`up to min(distance - 1, charge_range)` times), checking after each step
whether the entity's position actually changed. The instant a step
doesn't move it (a wall, another entity in the way - `MovementAction`
already no-ops safely on either), the charge stops right there: no
attack, no recovery penalty, just however much ground it managed to
cover before something got in the way. Only a charge that actually
*reaches* adjacent resolves an attack at all.

**The bonus damage is a value, not a stat mutation** - a landed charge
calls `resolve_skill_damage(self, entity, self.player,
entity.effective_attack + charge_attack_bonus, "charges into")`, the same
public, flat-damage-value entry point into the full `_apply_damage`
pipeline Ground Pound already uses (§0z) - dodge/crit/weapon-affix procs
all still apply to a charge's hit exactly as they would to an ordinary
one. This avoids the alternative of temporarily bumping
`entity.fighter.attack` and restoring it after, which would need to
survive `_apply_damage`'s own crit/message-logging path without leaking
the temporary value anywhere - reusing the existing "pass a flat damage
value in" seam is simpler and already proven correct.

**`Entity.charge_recovering` is the entire recovery mechanic** - a plain
bool, `True` for exactly one turn right after a landed charge, checked
*first* in the `AI_CHARGER` branch (before the alignment/range check
ever runs): a recovering charger skips its action outright and clears
the flag, the same "block the action, don't run the normal branch at
all" shape a stunned entity's own turn already takes (§0t), just
self-inflicted by the charge itself rather than an external affliction.

Ships one real example, `boar` (`data/entities.yaml`, `charge_range: 4`,
`charge_attack_bonus: 4` - roughly doubling its own `attack: 4` on a
landed hit) - not yet placed into a level, same reasoning as `slime`/
`bone_caller`. Verified end-to-end via direct `Engine`/`Entity`
construction: a lunge from range 3 correctly covers the gap and lands the
boosted hit, a wall placed partway correctly stops it short with no
attack and no recovery penalty, and a recovering boar correctly sits out
its very next turn before returning to normal behavior.

## 0aj. Territorial - won't chase past a radius from home (`cave_bear`)

The fourth AI behavior in this round, and the first that's about
*disengaging* rather than anything offensive: `AI_TERRITORIAL` behaves
exactly like `hostile_basic` while the player is within
`territory_radius` tiles of wherever it started, and breaks off the chase
to head back the instant it would step any farther out - even mid-pursuit,
even if the player is still visible and still running.

**"Home" is just "wherever this entity actually started existing," not a
separate concept needing its own configuration** - `Entity.home_x`/
`home_y` are captured once, directly from the `x`/`y` the constructor is
already given, for *every* entity, not only territorial ones (harmless
and unread for anything else). This is correct for every spawn path in
the codebase without any extra wiring: a real level spawn's home is its
authored position, and a runtime spawn (a Splitter's child, a Summoner's
minion, per §0ag/§0ah) has its own home at wherever *it* happened to
land - there's no special-casing needed for "what if this entity wasn't
placed by a level file."

**Checks the entity's own distance from home, not the player's distance
from home** - `_perform_ai`'s `AI_TERRITORIAL` branch computes
`home_distance = max(abs(entity.x - entity.home_x), abs(entity.y - entity.home_y))`
and only keeps chasing while `home_distance < territory_radius`
(`distance <= 1` always wins first, though - an adjacent attacker gets
fought back regardless of how far from home that fight is happening,
since refusing to defend itself mid-swing would read as broken, not
territorial). This is deliberately different from checking whether the
*player* is currently within radius of home: that would let a kiting
player drag the creature arbitrarily far by always staying just inside
the boundary from the creature's home, one step at a time. Measuring the
entity's own position instead gives it a hard, self-enforced leash no
kiting pattern can stretch.

**Disengaging is a real action, not a freeze** - `Engine._return_home`
steps one tile directly toward `(home_x, home_y)` per turn (the same
`step_x`/`step_y` shape `_flee`/`_chase_and_attack` already use), so a
bear dragged far out takes several turns to actually get back, same as
it took several turns to get pulled there - not a teleport. Once
actually home, it holds position rather than jittering in place; there's
no separate "resume guarding" animation or state, it simply waits until
`home_distance` drops back under `territory_radius` on its own (the
player wandering back within range) and resumes chasing exactly like
`hostile_basic` again.

Ships one real example, `cave_bear` (`data/entities.yaml`,
`territory_radius: 5`) - not yet placed into a level, same reasoning as
the other three behaviors in this round. Verified end-to-end via direct
`Engine`/`Entity` construction: chases normally well within its
territory, still fights back when already adjacent even after being
dragged far from home, and correctly turns back the instant it reaches
exactly `territory_radius` tiles out rather than taking one more step.

## 0ak. Ambusher - invisible until adjacent, then a guaranteed reveal-strike (`lurker`)

The fifth AI behavior in this round, and the first that's about
*concealment* rather than movement or damage timing: `AI_AMBUSHER` is
completely invisible - not drawn, not listed, not targetable by ranged
attacks - until the player steps adjacent to it, at which point it
reveals itself for good and lands one bonus-damage strike before
settling into ordinary `hostile_basic` behavior for the rest of the
fight.

**`Entity.hidden` needs no `EntityDef` field of its own** - it's derived
purely from `self.hidden = ai == AI_AMBUSHER` at construction, right
next to where `self.ai` is set. Every `lurker` (and any future ambusher)
starts hidden automatically; there's no way to author one that forgets
to hide, and no separate boolean to keep in sync with the AI type across
level files or the catalog.

**Being hidden had to mean hidden everywhere information could leak, not
just "not drawn on the map"** - a monster the player can't see but can
still shoot, or that still shows up in a debug listing, isn't actually
concealed. Six call sites got the same one-line exclusion:
`render.py`'s `render_entities` (skipped during the map draw) and
`describe_tile` (skipped when the player examines its tile);
`targeting.py`'s `is_valid_target` and `find_nearest_target` (a hidden
ambusher can't be hit by a ranged attack, nor auto-targeted at all, even
by something standing right next to it); and `tools/play_llm.py`'s own
three parallel surfaces - its map-draw loop (mirrors `render_entities`
exactly, since it doesn't call into `render.py` directly), the
`entities` debug command, and `goto <name>`'s candidate search. The
`entities` command is a deliberate judgment call: its whole premise
elsewhere is full map knowledge for debugging convenience, but letting
it print a hidden ambusher's name and position would make the concealment
untestable through the CLI tool this project actually plays through -
concealment needs to stay real even for the tool built to cheat with, or
"invisible" isn't really being verified at all.

**Stays motionless while hidden, not just invisible** - `_perform_ai`'s
`AI_AMBUSHER` branch takes no action whatsoever while `distance > 1`,
not even a step toward the player. A lurker that crept closer while
unseen would still be defeating "lying in wait" even though the render
layer hid it; true stillness is part of what an ambush actually is; only
once the player is adjacent does anything happen at all.

**The reveal replaces the turn's action, it doesn't add to it** - the
same "special action instead of a normal attack" principle Summoner's
`_maybe_summon` already established (§0ah): the instant `distance <= 1`,
`entity.hidden` clears permanently and the strike resolves via
`resolve_skill_damage(self, entity, self.player, entity.effective_attack
+ ambush_bonus, "ambushes")` - the same public, flat-damage-value entry
point Charger's landed lunge already uses (§0ai), so dodge/crit/weapon-
affix procs apply to an ambush strike exactly as they would to any other
hit. There's no separate "attack" call afterward for that turn; the
reveal *is* the attack.

Ships one real example, `lurker` (`data/entities.yaml`, `ambush_bonus:
6` against its own `attack: 5`, for an 11-damage opening strike) - not
yet placed into a level, same reasoning as the other four behaviors in
this round. Verified end-to-end via direct `Engine`/`Entity`/`GameMap`
construction: stays undrawn and untargetable while the player is two or
more tiles away and takes no action across several such turns, reveals
itself and lands the boosted hit the instant the player becomes
adjacent, and behaves like an ordinary visible `hostile_basic` monster
in every turn afterward.

## 0al. Scavenger - heals off a nearby ally's death (`vulture`)

The sixth AI behavior in this round, and the first whose trigger is
*another entity's* death rather than anything happening to itself:
`AI_SCAVENGER` fights exactly like `hostile_basic` on its own turns, but
whenever a nearby non-peaceful monster dies - killed by the player, by
each other, by anything - it heals a chunk of its own max_hp, capped at
max_hp, off the corpse. `EntityDef.scavenge_radius`/
`scavenge_heal_fraction` are independently optional, each with its own
engine-level fallback (`DEFAULT_SCAVENGE_RADIUS`/
`DEFAULT_SCAVENGE_HEAL_FRACTION`) - the same "omit-friendly" convention
`charge_range`/`charge_attack_bonus` already established, not a "both or
neither" pair.

**The trigger lives in `on_entity_death`, not `_perform_ai`** - unlike
every prior behavior in this round, a scavenger's own turn has nothing
special to do (`_perform_ai`'s `AI_SCAVENGER` branch is just
`_chase_and_attack`, identical to `AI_SPLITTER`'s own branch). The
actual mechanic, `Engine._scavenge_from_death`, is called once per
(non-player) death - right alongside `_maybe_split` - and scans, not
from the dying entity's own AI, but *from the death itself outward*:
every living scavenger anywhere on the map within its own
`scavenge_radius` of wherever the death happened heals, regardless of
whether that scavenger had anything to do with the kill. A vulture
doesn't need to be hunting, chasing, or even aware of a fight to profit
from it - it just needs to be close enough when the fight ends.

**"Ally" reuses `_has_nearby_ally`'s own definition, not a new one** - a
peaceful death (a villager or town guard) doesn't feed a scavenger,
gated by the same `PEACEFUL_AI_TYPES` exclusion `AI_PACK_HUNTER`'s own
nearby-ally check already established (§0v). This isn't really about
loyalty between monsters (a scavenger heals off *any* hostile monster's
death, not just its own kind) - it's the same boundary every other
"ally" concept in this project already draws: hostile creatures count,
the player and peaceful NPCs don't.

**The heal amount is computed off the scavenger's own current max_hp at
the moment of the kill, the same "read live state, don't cache it"
principle Splitter's child-sizing already established (§0ag)** - `min(
math.ceil(other.fighter.max_hp * fraction), other.fighter.max_hp -
other.fighter.hp)`, capped so a feeding never overheals, mirroring
`_regenerate`'s own capping logic (§0u) exactly. A scavenger already at
full HP is silently skipped (no heal, no log message) rather than
logging a zero-HP feeding, the same "don't narrate a no-op" posture
`_regenerate` takes at full health.

Ships one real example, `vulture` (`data/entities.yaml`,
`scavenge_radius: 6`, `scavenge_heal_fraction: 0.5` - half its own
`hp: 12` per feeding, out to 6 tiles) - not yet placed into a level,
same reasoning as the other five behaviors in this round. Verified
end-to-end via direct `Engine`/`Entity` construction against the real
catalog entry: heals the correct capped amount when a hostile ally dies
within radius, stays untouched when that death happens just outside its
radius, and correctly ignores a peaceful NPC's death entirely.

## 0am. Mimic - disguised as an item until picked at (`mimic_flask`)

The seventh AI behavior in this round, and the first whose disguise is
*visible*, not hidden - unlike `AI_AMBUSHER` (invisible outright),
`AI_MIMIC` is drawn every turn, in plain sight, exactly like an ordinary
ground item, and stays that way until the player actually tries to pick
it up. Only then does it reveal itself, bite for bonus damage, and fight
on like an ordinary `hostile_basic` monster from there.

**`Entity.mimicking` is derived purely from `ai`, the same shape as
`hidden`** - `self.mimicking = ai == AI_MIMIC`, no separate `EntityDef`
field, cleared for good (never re-disguises) the instant it's revealed.
But unlike `hidden`, nothing in `render.py`/`targeting.py` checks
`mimicking` at all - a mimic is never actually invisible, it's fully
rendered the whole time. The disguise is entirely in *what* gets
rendered: its own catalog-authored glyph/color/name/description simply
read like an item's (a vial, in `mimic_flask`'s case) from the moment
it's placed, nothing to toggle.

**Being visible-but-mislabeled needs `blocks_movement`/`render_priority`
to lie too, and both are set once at spawn, not derived in
`Entity.__init__`** - unlike every prior AI-derived field in this
project, `blocks_movement`/`render_priority` are ordinary constructor
params that `entity_from_def` (`engine/game_map.py`) has always hardcoded
to `True`/`RENDER_PRIORITY_ACTOR` for every monster spawn. A mimic needs
the opposite of both while disguised - non-blocking, so the player can
stand on its tile exactly like a real item; item-priority, so it sorts/
draws like one - so `entity_from_def` itself now branches on
`edef.ai == AI_MIMIC` for these two fields specifically, the one time
this round a behavior needed a change at the shared spawn-helper level
rather than purely in `Entity.__init__`. Both flip to their ordinary
monster values the instant it's revealed, so the ensuing fight works
exactly like any other monster's (the player can now actually bump-attack
it back).

**The trigger lives in `PickupAction`, not `_perform_ai`** - a disguised
mimic takes no action on its own turns at all (`_perform_ai`'s `AI_MIMIC`
branch no-ops while `mimicking`, the same "stays motionless" posture
`AI_AMBUSHER` already established), because the whole mechanic is a
response to something the *player* does, not a timer or a proximity
check. `engine/actions.py`'s `PickupAction.perform` now checks for a
disguised mimic at the acting entity's own tile *before* its existing
item-lookup loop (which would otherwise skip it silently, since
`candidate.item is None` for a mimic) - a hit calls `_reveal_mimic`
instead of collecting anything, and returns without ever reaching the
ordinary pickup logic below it.

**The disguise has to survive being looked at, not just walked past** -
`describe_tile`'s per-entity HP suffix (`engine/render.py`) and
`tools/play_llm.py`'s own `_entity_tag`/`entities`-command HP text both
now check `entity.mimicking` before showing anything a real item would
never have: an HP readout, or a "hostile" tag instead of "item." Skipping
this would have been a smaller, quieter version of Ambusher's own
information-leak problem (§0ak) - a player who merely *examines* a
suspicious vial, or glances at the CLI's own map legend, would see
"(HP: 14/14)" or "[hostile]" and the whole ruse would be spoiled before
they ever tried to pick anything up. `_entity_tag`'s fix is the more
consequential of the two, since `tools/play_llm.py`'s own 'walk'/'goto'
auto-attack-refusal logic (`_peek_step`) reads that same tag - a mimic
mistagged "hostile" would make the CLI's own movement helpers refuse to
step onto its tile at all, telegraphing danger the disguise is supposed
to hide.

**The reveal-strike reuses the same seam Charger/Ambusher's own do** -
`resolve_skill_damage(engine, mimic, entity, mimic.effective_attack +
bonus, "bites")`, so dodge/crit/weapon-affix procs apply exactly as they
would to any other hit. `Entity.just_revealed` (a plain bool, mirroring
`charge_recovering`'s shape exactly) stops the same turn's enemy phase
from also running an ordinary `_chase_and_attack` on top of the strike
PickupAction already resolved - without it, a player picking up a mimic
would take the reveal-bite *and* an unrelated second hit in the same
turn, breaking the "one special action replaces the turn, doesn't add to
it" principle every reveal-style behavior in this round has kept.
`mimic_bonus`'s own engine-level fallback, `DEFAULT_MIMIC_BONUS`, lives
in `engine/entity.py` rather than `engine/engine.py` - `engine/actions.py`
needs it too, and importing `engine/engine.py` from there would be
circular (`engine/engine.py` already imports `engine/actions.py`), the
same reasoning `AI_ENRAGE`'s own defaults are placed there for.

Ships one real example, `mimic_flask` (`data/entities.yaml`,
`mimic_bonus: 6` against its own `attack: 4`, disguised as a "Gleaming
Vial") - not yet placed into a level, same reasoning as the other six
behaviors in this round. Verified end-to-end via direct `Engine`/
`Entity`/`GameMap` construction against the real catalog entry: the
player can freely walk onto its tile while disguised, `describe_tile`
shows no HP for it until revealed, attempting to pick it up correctly
bites for the boosted amount and flips it to an ordinary blocking
monster, and `tools/play_llm.py`'s own `_entity_tag` correctly reads it
as `"item"` before the reveal and `"hostile"` after.

## 0an. The character screen: stats plus an assignable skill/potion hotbar

Not a new content behavior like the sixteen sections above it - a UI/engine
feature, replacing two things that had outgrown their original shape:
active skills were bound with a literal `if sym == KeySym.W: return
UseSkillAction("second_wind")` / `K` -> `"ground_pound"` pair in
`engine/input_handlers.py`, with a comment on `UseSkillAction` itself
admitting it wasn't "a scalable hotbar... since there are only two of them
so far"; potions had no quick-access at all, only a blind `c`-cycles-then-
`u`-drinks two-step. With more active-skill perks plausible soon, this was
the moment to fix both, and to give the player a real stat overview while
at it.

**Two new slot lists on `Entity`, not a new subsystem** -
`skill_slots: list[str | None]` (4 entries, keys 1-4) and
`potion_slots: list[str | None]` (3 entries, keys 5-7 - deliberately one
more than `POTION_KINDS` has entries today, same "room to grow" reasoning
as 4 skill slots for 2 current skills), both set unconditionally in
`Entity.__init__`, the same "lives on the surviving player Entity,
harmless on a monster" shape `selected_potion_kind`/`learned_perk_ids`
already use. `selected_potion_kind` itself wasn't touched - `UseItemAction`
still reads it; a potion-slot press just sets it first, then delegates.

**One validated assignment method per slot kind, shared by both front
ends** - `Engine.assign_skill_slot`/`assign_potion_slot` are the only
places `skill_slots`/`potion_slots` are ever mutated, whether the caller
is the graphical client's cycling UI or `tools/play_llm.py`'s direct
`bind_skill`/`bind_potion` commands. The one rule that keeps a hotbar with
more slots than filled values unambiguous: **assigning a value already
sitting in a different slot moves it there instead of allowing a
duplicate** - clearing the old slot as part of the same call, so a
duplicate is never even transiently possible. `learn_perk` calls
`assign_skill_slot` once, automatically, the moment a new `skill_effect`
perk is learned (into the first empty slot, if any) - the same "learn it,
it just works" experience the old hardcoded W/K pair gave for free, still
fully reassignable afterward. `tools/play_llm.py`'s `--testbuild` (which
learns perks by mutating `learned_perk_ids` directly, bypassing
`learn_perk` entirely) got the identical one-line auto-slot call for
parity, so a pre-built skill-perk testbuild character shows up correctly
hotbarred too.

**Three new Actions, one of them a thin delegate rather than duplicated
logic** - `UseSkillSlotAction(slot_index)` looks up the slot and calls
`Engine.use_skill` exactly like the old fixed `UseSkillAction("second_wind")`
did; `UsePotionSlotAction(slot_index)` sets `selected_potion_kind` to the
slot's kind and then calls `UseItemAction().perform(...)` directly, so a
slot press behaves identically to selecting that kind and pressing `u` in
one turn, with zero duplicated drink logic. `CharacterAction` opens the
screen - free, no-turn, the same shape `QuestLogAction` already
established. Both `UseSkillSlotAction`/`UsePotionSlotAction` still cost a
turn on an empty slot ("No skill bound to that slot." / "Nothing bound to
that slot.") - the same "the attempt itself is the cost" posture
`UseItemAction`'s own "nothing to drink" case already has, not a free
no-op.

**The graphical screen edits with one cursor, two axes** -
`run_character_mode` (main.py) is `run_trainer_mode`'s exact shape (no
gate function needed; reviewing your own stats needs no adjacent NPC),
except this screen has left/right in addition to up/down: up/down move a
single cursor across the 7 combined rows (skill slots first, then potion
slots), left/right cycle whichever row is currently selected to its next
candidate (`None` + every learned `skill_effect` perk, in catalog order,
for a skill row; `None` + every `POTION_KINDS` entry for a potion row).
Cycling only computes "what's next" - the mutation and its
move-not-duplicate rule live entirely in `Engine.assign_skill_slot`/
`assign_potion_slot`, so navigation logic can never drift out of sync with
what the CLI's direct-set commands enforce.

**A small, reusable extraction on the way**: `total_crit_chance`/
`total_dodge_chance` (`engine/combat.py`) pull the base+trinket+perk
formula `_apply_damage` already rolled inline into two public functions,
so the character screen (and its CLI mirror) can display the *exact*
number combat rolls against, not a separately maintained copy of the
formula - `_apply_damage` itself now calls them too, removing the
duplication rather than adding a third copy alongside it.

Ships no new content - this is pure engine/UI - but touches every layer
the ten AI behaviors above it didn't need to: `engine/entity.py` (the
slot fields), `engine/engine.py` (the two assignment methods,
`learn_perk`'s auto-slot call), `engine/actions.py` (three new Actions,
`CyclePotionKindAction` removed as dead weight once slots replace it),
`engine/input_handlers.py` (number-key bindings, `handle_character_event`),
`engine/render.py` (`render_character`, the HUD's skill/potion lines now
slot-driven), `main.py` (`run_character_mode`), `engine/save.py` (both
slot lists persisted, with the same defaults `Entity.__init__` uses so an
old save round-trips unchanged), and `tools/play_llm.py` (`character`/
`bind_skill`/`bind_potion`/`use_skill_slot`/`use_potion_slot` commands,
full parity with the graphical client). Verified via the full pytest
suite, a direct-construction script against the real catalog, and a full
CLI playthrough exercising every new command end-to-end (learn a skill,
watch it auto-slot, rebind it into a different slot with a swap rather
than a duplicate, drink/trigger by slot number, hit the empty-slot message
on a cleared one).

## 0ao. Session replay (`tools/replay.py`, `play_llm.py --record`)

Another pure tooling feature, same category as §0an - `tools/play_llm.py`
is stateless by design (one CLI command per invocation, persisted through
an ordinary `SaveGame` file), which is exactly what makes it usable for an
LLM to drive turn by turn, but it leaves nothing for a human to review
afterward: no history, and even if there were, the CLI only ever prints
plain ASCII glyphs, never the real sprite art `main.py`'s graphical client
draws. This adds an opt-in recorder plus a standalone viewer that watches
a recorded session back using the exact same rendering code the real game
uses. Human sessions are explicitly out of scope - a human playing through
`main.py` already has a real window and can just screen-record it.

**A state-snapshot recorder, not an action-replay one - the one design
decision this whole feature turns on.** The obviously-simpler-sounding
alternative - record just the list of commands, then re-run them through a
fresh `Engine` to reproduce the session - has a real correctness problem:
combat already has a deliberate randomness layer
(`engine/combat.py`'s `COMBAT_VARIANCE_ENABLED` dodge/crit rolls), and
enemy AI/hazard rolls are randomized too, so replaying the same commands
against a fresh engine would not reliably reproduce the same fight
outcomes - the "replay" could diverge from what actually happened. Instead,
each recorded frame captures the *actual resulting game state* via
`engine/save.py`'s already-tested `capture_save()` - the same serialization
the real Save action uses - so replaying never re-runs any game logic or
randomness at all; it only re-renders already-decided history. This also
means frames can be viewed in any order for free (jump back and forth,
restart from the middle) with zero extra bookkeeping, and the recorder adds
essentially no new state model - it reuses `SaveGame`/`capture_save`/
`restore_save` exactly as they already exist.

**The recording hook rides on the save write that already exists, rather
than a new command classification** - `tools/play_llm.py`'s new `--record
PATH` flag (opt-in, off by default, passed on every call the same
stateless way `--save` already is) appends one frame immediately after the
existing `capture_save`/`save_to_path` call in `main()`. Since a query
command (`character`/`quests`/`entities`/`inspect`) already returns before
that point today, it's automatically never recorded either - no new "is
this command worth recording" logic needed anywhere.

**Messages are captured and re-injected separately from the `SaveGame`
payload, on purpose** - `SaveGame` deliberately never persists the message
log (each CLI invocation gets a fresh one; that's correct for real
gameplay resumption). A replay frame still needs to show what happened on
that specific step, so `_append_replay_frame` captures
`engine.message_log.messages` directly at record time, independently of
`save.model_dump(mode="json")`, and `tools/replay.py`'s
`_build_engine_for_frame` overwrites the freshly-`restore_save`d engine's
message log with those recorded messages before rendering - otherwise
every replayed frame's log panel would be blank.

**One frame per turn actually executed, not one per CLI call - found by
actually watching a recorded session.** `walk`/`goto` are the only
commands that can span more than one turn in a single invocation
(`_execute_walk` in `tools/play_llm.py` runs a whole list of steps), and
the first version of this feature recorded exactly one frame per `main()`
call - so a 20-step `goto` showed up in the replay as a single instant
jump from the start tile to the end tile, not a walk. `_execute_walk` now
takes an `on_step` callback, invoked once per step that actually executes
(right alongside the existing end-of-command frame, which still fires
from `main()` afterward) - `main()` only builds one when `--record` is
set, so a non-recording run pays zero extra `capture_save` cost per step.

**The same real playtest surfaced a second, related bug: a level
transition mid-route made `_execute_walk`'s own summary note lie.** Its
final "Walked N/M step(s): (a, b) -> (c, d)" line was built from
`engine.player.x/y` *after* the loop - but if one of the steps entered a
new dungeon or the overworld, `engine` itself had already been replaced
by `resolve_transition` with a different level's own `Engine`, whose
(x, y) means nothing next to the *old* level's (a, b). The note looked
like an ordinary completed walk right up until you tried to plot the two
coordinates on the same map. `_execute_walk` now tracks whether the loop
actually stopped on a transition (`entered_new_area`, computed the same
turn `resolve_transition` reports a changed `active_key` - not inferred
by string-matching `stop_reason` after the fact) and reports that case on
its own terms: "Walked N/M step(s) from (a, b)." plus a separate "Entered
{level} at (c, d)." line, never blending the two coordinate spaces into
one misleading arrow.

**The viewer is deliberately its own small event loop, not an extension of
`engine/input_handlers.py`** - frame navigation (next/prev/play/pause)
isn't a gameplay concern, the same reasoning `tools/preview.py`/
`tools/balance.py` already have their own bespoke logic rather than
extending the core input layer. It reuses everything else outright:
`tools.play_llm.load_content()`, `main.py`'s own
`load_tileset()`/`load_sprite_manifest`/`apply_sprites()` bootstrap (so the
sprite art is pixel-identical to a real graphical session), and
`engine/render.py`'s `render_all` completely untouched - the console is
just 2 rows taller than `main.py`'s own, with those extra rows reserved for
the viewer's own "Frame N/M: `<command>`" caption, so nothing about the
real HUD/map/log layout has to change or know a replay is happening.
Autoplay reuses `tcod.event.wait(timeout=...)`'s own timeout parameter
rather than a manual poll/sleep loop: blocking indefinitely while paused
(no CPU spin for a keypress), returning after the configured per-frame
delay with an empty event list while playing - exactly the signal needed
to auto-advance one frame, stopping at the end rather than looping.

Ships no new gameplay content - pure tooling, same as §0s's `tools/
balance.py`. Verified via the full pytest suite (`load_frames`/
`clamp_index` in `tools/replay.py`, and the `--record` append's shape/
ordering/query-exclusion in `tools/play_llm.py`, both using `tmp_path` the
same way `tests/test_save.py`'s own round-trip tests already do), a real
CLI session recorded end-to-end (confirming the `.jsonl` grows one line
per mutating call and a query call adds nothing), a headless
reconstruction of every recorded frame through the exact real rendering
pipeline (`_build_engine_for_frame` + `render_all`, with real sprite
codepoints, no window) confirming nothing raises, and an actual windowed
launch of `tools/replay.py` confirming the SDL window opens and renders
without error. The per-step recording and coordinate-blending fixes above
came from an actual multi-hour playtest session driven through this exact
tool (534 recorded frames across three dungeons and two settlements,
including two real character deaths) - the single most effective way
either bug could have been found, since neither one is visible from
`_execute_walk`'s code alone, only from watching what it produces.

## 0ap. Water walking - a timed, dungeon-only terrain override (`water_walking_potion`, `deep_water`)

A new potion kind, drunk to cross otherwise-impassable standing water for
a limited number of turns - built alongside its own showcase dungeon, The
Weeping Cistern (`data/dungeons/weeping_cistern/`,
`docs/dungeon_bibles/weeping_cistern.md`, Northern Steppe's first combat
dungeon).

**`sea` needed a non-ocean sibling.** The obvious approach - just let the
potion override the existing `sea` tile - was rejected mid-design: `sea`
is specifically the overworld ocean, and almost no dungeon water is
actually seawater (Drowned Waystation already stretches the label for
coastal flooding; a landlocked cistern calling its water "sea" would be a
much starker mismatch). Rather than compound an existing naming
imprecision, a second tile kind, `deep_water`, was added to
`content/schema.py`'s `TileType`/`TILE_PASSABILITY` - identical
impassable-but-transparent behavior to `sea`, distinct label, and a
slightly different color in `engine/render.py`'s `TILE_KINDS` (murky
green-grey vs. `sea`'s clean ocean blue) reusing `sea`'s own sprite tile
in `data/sprites.yaml`, the same "one sprite, two recolored kinds"
precedent `scoured_ground`/`ashen_plains` already established. The
walkability override itself still accepts *either* kind
(`self.kinds[x, y] in ("sea", "deep_water")`) - the mechanic is "cross
standing water," and staying inclusive of the older label costs nothing
while covering any level still using it.

**Not `Fighter.active_effects`.** That system exists for combat-inflicted
afflictions, hooked into `_apply_damage`'s own inflict moment - the wrong
shape for a self-applied consumable buff with no combat interaction at
all. Water walking is instead a bespoke `Entity.water_walking_turns_
remaining: int`, following the exact "omit-friendly, harmless on a
monster" pattern `charge_recovering`/`summon_cooldown` already use, ticked
down once per turn from `Engine.process_enemy_phase` (same "any turn
anywhere" cadence `_tick_skill_cooldowns(SKILL_COOLDOWN_TURNS)` already
has) via a new small `_tick_water_walking`.

**The walkability hook**: `GameMap.is_walkable` gained an optional
`water_walking: bool = False` parameter rather than a parallel function,
so every existing call site is unaffected by the default.
`MovementAction.perform` computes the actual override once, right before
its `is_walkable` check: `entity is engine.player and not
engine.is_overworld and entity.water_walking_turns_remaining > 0` - the
`is_overworld` guard is the entire reason this can never be used to
bypass the real ocean, and it's structural (computed at the movement
check itself), not a refusal message. `tools/play_llm.py`'s own
`_peek_step`/`_bfs_path`/`_resolve_goto_target` needed the identical
threading for CLI parity (`walk`/`goto` must be able to path across water
while the buff is active, matching what a real keypress can already do).

**No overworld refusal message.** Unlike the Teleportation Potion's own
"You're already on the surface" guard, drinking Water Walking on the
overworld is allowed - it's simply inert there by construction, the same
"no explicit refusal, just a capped effect" precedent a Healing Potion at
full HP already sets.

**The softlock this design structurally avoids**: a there-and-back water
crossing (drink, cross, grab loot, cross back) risks the buff expiring
mid-return with the player standing on a `deep_water` tile with no
walkable neighbor - genuinely stuck, not just inconvenienced. The Weeping
Cistern's own Water Gate is deliberately **forward-only** instead: no
floor route back across the same water, so the far side has to supply its
own way out (a `stairs_down` with `next_level: null`, matching Drowned
Waystation `level_02`'s own convention for a dungeon's deepest level).
Any future water-walking content should keep this shape - a one-way gate,
never a round-trip over the same tiles - rather than relying on generous
duration alone to avoid stranding the player.

**Two real balance bugs, both caught by CLI playthroughs, not by hits-to-
kill math**: an early layout put two `drowned_wretch` in one open hall
with no chokepoints, letting both converge on the player at once (a
straight pile-on); the fix was splitting the level into rooms joined by
genuinely bent corridors (`Engine._perform_ai` only skips a monster whose
own tile isn't currently visible to the player, and `FOV_RADIUS` is 8, so
a long straight corridor lets the player see - and simultaneously aggro -
everything on it, and a 1-wide corridor open at both ends lets separate
monsters pincer the player from opposite sides, worse than an open room
since there's no way to back off and face only one). Separately, even
with that fixed, three back-to-back melee fights in a strictly linear,
no-rest dungeon (two on the entrance level, a third guarding the Water
Gate) cost far more cumulative HP for a fresh, unequipped character than
the flat per-monster math implied - fixed by cutting the Water Gate's
guard entirely, since the water crossing is this dungeon's intended
obstacle and a third attrition fight bolted onto it was redundant with
that, not additive. Neither issue was visible from `docs/dungeon_bibles/
weeping_cistern.md`'s own hits-to-kill arithmetic alone - both only
surfaced from actually playing the shipped level file turn by turn.

Ships new content alongside the mechanic (`data/dungeons/weeping_cistern/`,
one new item, one new tile kind) - verified via the full pytest suite
(schema/`ItemDef` validation, `is_walkable`'s override on both `sea` and
`deep_water`, `MovementAction`'s dungeon-only gate, the per-turn tick, a
`SavedPlayer.water_walking_turns_remaining` round-trip - an easy miss,
since `tools/play_llm.py` is a fresh process per command and silently
drops any live-state field never added to `engine/save.py`), `tools/
preview.py`'s full dungeon/overworld registry, and a real `tools/
play_llm.py` playthrough from a fresh character through both levels -
confirming water blocks movement without the potion, the crossing works
with it, and the buff is inert if drunk on the overworld.

## 0aq. Antidote - clears every active status effect at once (`antidote_potion`)

The first of a new round of consumable/active-skill ideas, and the
simplest one in it: `ItemDef.cures_effects` is a plain bool (no potency,
no duration - there's nothing to scale, it either clears
`Fighter.active_effects` right now or, already effect-free, does
nothing), threaded through `ItemEffect`/`item_entity_from_def` the exact
same three-step path `water_walking_duration` established in §0ap
(schema field, `ItemEffect` field, `potion_kind()` branch) - a new potion
kind is now a genuinely small, mechanical addition, not a design
decision each time.

**Needs no new persisted state at all - the first potion in this project
for which that's true.** `water_walking_duration` (§0ap) needed a new
`Entity.water_walking_turns_remaining` live-state field and a
`SavedPlayer` round-trip to go with it; Antidote just clears an
already-persisted dict (`Fighter.active_effects`, saved via
`SavedPlayer.active_effects` since long before this potion existed) and
walks away. `engine/save.py` needed zero changes.

**A real, if narrow, interaction found only by actually drinking one
while stunned:** `Engine.process_player_action` blocks a stunned
player's action outright (`EFFECT_STUN in
self.player.fighter.active_effects` skips `action.perform()` entirely,
same as a stunned monster's own `_perform_ai` turn) - meaning a stunned
player can never actually trigger `UseItemAction` to drink the antidote
that would cure that same stun, since the stun has to lapse on its own
before any action (drinking included) reaches `perform()` again.
`cures_effects` still clears stun along with poison/weaken when it *does*
run - correctness and forward-compatibility cost nothing here, and
nothing about this potion should assume today's "the player is the only
one who ever drinks a potion" is permanent - but the practical value is
entirely in clearing poison/weaken, which don't block acting the way
stun does. Worth knowing before reaching for this as "the stun cure";
it isn't one in practice, only on paper.

**No refusal, same as Healing's own precedent** - drinking with nothing
currently active still consumes the potion (`"You drink the Antidote,
but feel no different."`), the same "always consumes, sometimes a no-op"
shape a Healing Potion already has at full HP, rather than Teleport's
"refuses before consuming, nothing to gain here" shape (§0z-era). Cure
potions and "there's only one place this matters" potions read
differently enough that they shouldn't share a refusal convention just
because they're both potions.

Ships one real example, `antidote_potion` (`data/items.yaml`,
`cures_effects: true`, `cost: 20`) - purchasable, not just found, unlike
the Water Walking Potion. Verified end-to-end via direct `Engine`/
`Entity` construction against the real catalog entry: clears a poison +
weaken combination in one drink, correctly no-ops (but still consumes)
with nothing active, and - the stun case above - confirmed a stunned
player's own turn never reaches the antidote's own logic at all.

## 0ar. Elixir of Vigor - a timed self-buff, and a new `BuffKind` namespace to hold it (`vigor_elixir`)

The first potion in this round that boosts the player rather than curing
or repositioning them, and it deliberately does **not** reuse
`Fighter.active_effects`/`EffectKind` to do it. That system exists for an
*attacker's* capability landing on a *target* (`EntityDef.inflicts_effect`,
a weapon/armor's `affix_effect`) - poison, stun, weaken all read as
something done *to* an entity. A self-drunk positive buff is the opposite
shape (done *to yourself*, *by* yourself), and folding it into the same
enum would let `inflicts_effect: vigor` type-check as a monster "inflicting"
strength on the player it just hit - backwards, and a bug waiting to
happen the type system should rule out rather than a comment warning
against.

So `content/schema.py` gets a parallel, structurally-identical pair:
`BUFF_VIGOR = "vigor"` / `BuffKind = Literal[BUFF_VIGOR]`, sitting next to
(not merged with) `EffectKind`. `ItemDef` gets `grants_buff: BuffKind |
None`, `buff_potency`/`buff_duration: int | None` (both `gt=0`, mirroring
`affix_potency`/`affix_duration`'s own field shape), with a
`grants_buff_potency_and_duration_together` validator enforcing the same
"all three or none" rule `affix_effect_duration_and_chance_together`
already established for weapon/armor affixes. `Fighter` gets a second
dict, `active_buffs: dict[str, ActiveEffect]` - same `ActiveEffect`
dataclass (potency/turns_remaining), same refresh-not-stack/membership-is-
the-state expiry convention as `active_effects`, but a genuinely separate
dict so nothing conflates the two namespaces at runtime either.

**Plumbing, in order:** `ItemEffect` gains the same three fields
(`grants_buff`/`buff_potency`/`buff_duration`), `item_entity_from_def`
passes them through, `potion_kind()` gets `if item.grants_buff ==
BUFF_VIGOR: return "vigor"`, and `POTION_KINDS` gains `"vigor"` -
identical shape to every prior potion in this round. `UseItemAction`'s new
`elif kind == "vigor":` branch writes `entity.fighter.active_buffs[
BUFF_VIGOR] = ActiveEffect(potency=..., turns_remaining=...)` straight
from the item's own fields (no derived math - the item defines its own
buff outright, same as Antidote clearing effects outright).

**The bonus itself:** a new `Entity._vigor_bonus` property, shaped exactly
like `_weaken_penalty` (reads `fighter.active_buffs.get(BUFF_VIGOR)`,
returns its potency or 0) but *added* rather than subtracted - into both
`effective_attack` **and** `effective_defense`. This is the one place
Vigor's shape genuinely differs from weaken: weaken only ever touched
`effective_attack`/`effective_ranged_attack` (`effective_defense` has no
`_weaken_penalty` term at all - defense was never weaken's target), but
Vigor is pitched as an all-around strength buff, so it lands on both
offense and defense deliberately, not by accident of copying weaken's
exact site list.

**Ticking:** a new `Engine._tick_active_buffs()`, shaped like
`_tick_active_effects()` minus the on-tick damage branch (a buff never
does anything *on* the tick itself, purely passive while active via
`_vigor_bonus`) - same "first tick lands the same turn it's granted"
cadence, confirmed by a live-verify script showing `buff_duration=10`
reads back as `turns_remaining=9` immediately after drinking within the
same `process_turn` call. Called from `process_enemy_phase` right after
`_tick_active_effects()`, so it ticks once per turn anywhere (dungeon or
overworld) - a buff has no "only matters underground" restriction the way
water-walking does, so there's no `is_overworld` gating anywhere in this
potion's logic.

**Display and persistence, both extended rather than duplicated:**
`engine/render.py`'s `_render_active_effects` (despite its name, now the
shared HUD-line renderer for *both* dicts) grew a second loop over
`fighter.active_buffs` against a new `_BUFF_HUD_LABELS` dict
(`"VIGOR: +N attack/defense (M turn(s) left)"`) - all three of its call
sites (`render_hud`/look/target frames) picked this up for free.
`tools/play_llm.py`'s own parallel HUD-text copy got the identical
extension, per this project's standing "own implementation, not reaching
into render.py's console internals" convention. `engine/save.py`'s
`SavedPlayer` gained `active_buffs: dict[str, SavedActiveEffect]`,
reusing `SavedActiveEffect` as-is (same potency/turns_remaining shape as
`active_effects` already saves) rather than a new model - `capture_save`/
`_build_player` both round-trip it the same way `active_effects` already
does, and an old save missing the field defaults to `{}` via pydantic
(verified with a test mirroring `test_restore_save_defaults_active_effects
_for_an_old_format_save` exactly).

Ships one real example, `vigor_elixir` (`data/items.yaml`, `grants_buff:
vigor`, `buff_potency: 3`, `buff_duration: 10`, `cost: 40` - priced above
Antidote's 20 and below a trinket's 60-75 for a permanent smaller bonus,
reflecting that +3/+3 for 10 turns is a bigger but temporary swing).
Verified end-to-end via direct `Engine`/`Entity` construction against the
real catalog entry: `effective_attack`/`effective_defense` both jump by
exactly 3 on drinking, the HUD line renders correctly (including through
`tools/play_llm.py`'s `render_hud_text`), and the buff expires cleanly
back to base stats after its full duration ticks down - no floor-clamping
or negative-potency edge case exists here the way `_weaken_penalty`
guards against, since a buff's potency is always additive and never drives
`effective_attack`'s `max(0, ...)` floor into play.

## 0as. Draught of Swiftness - a burst of genuinely free player actions (`swiftness_draught`)

The second `BuffKind` (§0ar's namespace, `BUFF_HASTE = "haste"`), and the
first buff whose mechanic isn't a stat number at all - "extra action per
turn" from the original brainstorm, read literally: for a few actions, the
world simply doesn't get a turn back. No monster moves, no hazard fires,
no effect/cooldown/water-walking ticks, no world clock advances - the
player's own action is the only thing that happens.

**The core mechanism:** a new `Engine._skip_enemy_phase` flag, set by
`process_player_action` (via a new `_consume_haste_action()` helper)
immediately before `action.perform()` runs, and read-and-cleared at the
very top of `process_enemy_phase`. When set, `process_enemy_phase` still
updates FOV (the player may have moved) but returns before touching
anything else - `_handle_enemy_turns`, `_apply_environmental_hazard`,
every tick method, the world clock, all skipped outright for that one
call. Both of Engine's callers (`process_turn` for tests/AI-only code,
and `main.py`'s animated `process_player_action`/`process_enemy_phase`
split) already call the two methods back to back unconditionally, so
neither needed to change - the skip is entirely internal to
`process_enemy_phase` deciding to no-op.

**Why the checkpoint is *before* `action.perform()`, not after (unlike
`_consume_stun_turn`, which fires at the moment a block actually takes
effect):** checking pre-action state means haste isn't active yet at the
moment `UseItemAction` itself is checked, so *drinking* the potion still
costs a normal turn - a hostile monster gets to swing back on that same
turn, confirmed by a live-verify script (26 hp, down from 30, right after
the drink). Only the actions that follow are free. This was a deliberate
choice over the alternative (checking post-action, which would make the
drinking turn itself free too) - drinking should read as spending your
turn to prepare, not as the first free swing.

**Why haste needed its own ticking path, separate from `_tick_active_buffs`
(§0ar):** that method only runs as part of `process_enemy_phase` - which a
hasted action skips entirely - so a buff ticked there would never
count down while it's actually paying for something. `_consume_haste_action`
decrements `turns_remaining` itself, at the exact moment a free action is
granted, then reports `True`/`False` for whether this turn should skip the
enemy phase. The reverse bug bit first, though: **`_tick_active_buffs`
still runs normally on the drinking turn itself** (haste isn't active
during that check, so nothing is skipped) and would happily tick the
freshly-granted haste buff down as "just another buff" alongside vigor -
a real double-decrement caught by
`test_use_item_action_haste_drinking_itself_costs_a_normal_turn` (haste
read back as 2 remaining instead of 3 on first run). Fixed by excluding
`BUFF_HASTE` from `_tick_active_buffs` outright, the same way
`_tick_active_effects` already excludes `EFFECT_STUN` for the analogous
reason (a different subsystem owns that kind's countdown).

**A stunned turn never spends a haste charge either** - `process_player_action`'s
stun branch returns before `_consume_haste_action` is ever reached, so a
player frozen by stun doesn't also burn down a buff that couldn't have
helped them act anyway. Verified directly
(`test_stunned_player_does_not_consume_a_haste_charge`).

**Schema shape - a second split off `_EFFECT_KINDS_WITH_POTENCY`'s own
precedent:** haste has no intensity concept (an action is either free or
it isn't, same reasoning `EFFECT_STUN` already established for
afflictions), so `ItemDef`'s single `grants_buff_potency_and_duration_together`
validator (§0ar) was split into two, mirroring
`affix_effect_duration_and_chance_together`/`affix_potency_matches_effect_kind`'s
own two-validator shape exactly: `grants_buff_and_duration_together`
(grants_buff + buff_duration required together) and
`buff_potency_matches_buff_kind` (potency required only for kinds in the
new `_BUFF_KINDS_WITH_POTENCY = (BUFF_VIGOR,)` tuple, rejected otherwise).
`vigor_elixir`'s own existing data needed no changes - vigor still
requires potency, only its *validator path* changed shape.

Ships one real example, `swiftness_draught` (`data/items.yaml`,
`grants_buff: haste`, `buff_duration: 3`, no `buff_potency`, `cost: 55` -
priced above Elixir of Vigor's 40, reflecting that three fully
consequence-free actions is a stronger burst than a ten-turn stat bump).
Verified end-to-end via direct `Engine`/`Entity` construction against the
real catalog entry, with a hostile monster standing adjacent throughout:
the drink itself costs a normal turn (monster attacks, hp drops), the
next three actions are completely free (hp untouched, monster never
moves), and the fourth action resumes normal turn economy in full -
monster attack and a concurrently-active poison tick both firing again in
the same turn, confirming nothing about the world's own clock quietly
stayed frozen past haste's actual expiry.

## 0at. Vial of Shadows - undetectable from a distance, not from melee (`shadow_vial`)

The third `BuffKind` (§0ar/§0as's namespace), and by far the smallest
diff of the three: a single choke point in `_perform_ai`, right after the
existing stun check and the `dx`/`dy`/`distance` computation, before any
AI-type dispatch:

```python
if distance > 1 and BUFF_SHADOWED in self.player.fighter.active_buffs:
    return
```

That one `if` covers every AI branch below it uniformly -
`hostile_basic`, `ranged_basic`, `sleeping_guard`, `pack_hunter`,
`regenerator`, `splitter`, `enrage`, `territorial`, `ambusher`,
`town_guard`, `villager`, `skittish` - without threading a check into
each one individually, the same "one gate at the top" shape the existing
FOV check (`if not self.game_map.visible[...]: return`) and stun check
already establish for this method. `distance > 1` is the entire design:
shadowed conceals from anything not already adjacent, but does nothing
once something is standing right next to the player - confirmed live with
a hostile monster starting two tiles out (drinks the potion, monster
never closes the distance or attacks for the buff's full duration) versus
one already adjacent (drinks it, gets hit anyway, same turn). This is a
deliberate scope limit distinguishing it from the still-unbuilt Smoke
Bomb (an "escape + aggro break" tool, next round's list) - Shadows is for
slipping *past* threats at range, not escaping ones already on top of
you.

**Naming, not mechanics, was the one real hazard here:** `AI_AMBUSHER`
monsters already have `Entity.hidden`, an unrelated per-monster "lying in
wait" flag checked by this exact same `_perform_ai` method a few branches
down. Calling the new buff kind
`"hidden"` would have made `entity.hidden` (a monster's own state) and
`"hidden" in player.fighter.active_buffs` (the player's) sit side by side
in the same function reading like the same concept - so it's
`BUFF_SHADOWED = "shadowed"` instead, textually distinct even though both
ultimately mean "can't currently be seen." No functional interaction
between the two: an ambusher already `hidden=True` and lying in wait
stays exactly that regardless of whether the player is shadowed (the
choke point returns before the AI dispatch reaches the ambusher branch
either way, at distance > 1); at distance <= 1 neither flag matters to
the other.

**No intensity concept, same as haste** (§0as) - `_BUFF_KINDS_WITH_POTENCY`
stays `(BUFF_VIGOR,)` unchanged, `buff_potency_matches_buff_kind` rejects
one for shadowed the same way it already rejects one for haste, and
`shadow_vial` sets no `buff_potency` in its own data.

**Ticked the ordinary way, unlike haste - the one respect in which this
buff is closer to vigor than to its `_perform_ai`-gating sibling:**
shadowed doesn't grant free actions or skip any part of the world's own
turn, it just adds one extra condition to whether a monster notices the
player, so `_tick_active_buffs` handles its countdown exactly like
vigor's (once per turn, in `process_enemy_phase`) with no special-casing
needed in that method at all - only `BUFF_HASTE` is excluded there.
Consequently there's no "drinking costs a normal turn" carve-out either:
unlike haste (whose `_consume_haste_action` deliberately checks
*pre*-action state so the drink itself isn't free), shadowed takes effect
immediately within the same turn it's drunk, since `UseItemAction` runs
during `process_player_action`, strictly before `_handle_enemy_turns`
checks the buff later that same `process_enemy_phase` call - confirmed
live: a monster two tiles out at the moment of drinking never gets a turn
even on that first turn.

Ships one real example, `shadow_vial` (`data/items.yaml`, `grants_buff:
shadowed`, `buff_duration: 8`, no `buff_potency`, `cost: 45`). Verified
end-to-end via direct `Engine`/`Entity` construction against the real
catalog entry, with a hostile monster two tiles out: the monster never
moves or attacks for the full 8-turn duration (confirmed turn by turn),
then closes the distance and lands a hit exactly once the buff is fully
expired - and a second, separate scenario confirming an already-adjacent
monster attacks straight through the buff, undisturbed.

## 0au. Bottled Second Sight - an instant map reveal, deliberately not a `BuffKind` (`bottled_second_sight`)

The fourth new potion in this round, and the first that isn't a timed
effect at all - a plain `ItemDef.reveals_map: bool` flag, same shape as
`cures_effects` (§0aq): it either does its one thing right now or it
doesn't, nothing to tick down, nothing living in `Fighter.active_buffs`.
Drinking it does two things in the same instant: `game_map.explored[:, :]
= True` (every tile of the *current* level, permanently - the same array
`update_fov` already ORs into on every ordinary turn, so this needed no
new persisted state; `engine/save.py`'s existing coordinate-list
serialization of `explored` handles a fully-True array exactly like any
other), and a one-time message-log summary of every creature currently on
the level (`fighter is not None and ai is not None`, grouped by name with
a naive `+"s"` pluralization - "2 Goblins, 1 Villager" - matching the
"there's no existing pluralization helper in this codebase" reality
rather than inventing one for a single flavor line).

**Why not model this as a buff at all**, given the last three potions
all were one: there's nothing here that decays. The map, once explored,
stays explored the same way walking there manually would leave it -
there's no "un-reveal" moment for `_tick_active_buffs` to manage, and the
creature summary is a one-off glimpse, not an ongoing detection effect
(unlike, say, a hypothetical "see monsters through walls for N turns"
potion, which *would* need a buff and a real change to `render.py`'s
FOV-gated entity draw check). Modeling a one-shot effect as a buff with
`buff_duration=1` would have been technically possible but pointlessly
indirect - `is_teleport`/`cures_effects` already established "plain flag,
no BuffKind" as the right shape for anything that just happens once, and
this is squarely that.

**Dungeon-only, refused on the overworld before consuming - `is_teleport`'s
exact refusal shape** (`if kind == "second_sight" and engine.is_overworld:
... return`, no consumption), for a reason specific to this potion rather
than copied wholesale: the overworld is one large stitched `GameMap`
(`docs/region_bibles`' own "overworld cell grid" convention), so `explored
[:, :] = True` there would reveal the *entire game world* in one drink -
an effect an order of magnitude larger than what any level-scoped potion
in this project does, and worth a hard no rather than a smaller,
quietly-inconsistent radius limit.

Ships one real example, `bottled_second_sight` (`data/items.yaml`,
`reveals_map: true`, `cost: 50`, no `buff_duration`/`buff_potency` fields
at all). Verified end-to-end via direct `Engine`/`Entity` construction
against the real catalog entry on a 20x20 map: a corner tile 17 tiles
from the player (`FOV_RADIUS` is 8, so nowhere near reachable by ordinary
FOV) reads `explored=False` before drinking and `True` immediately after,
the creature summary correctly names a distant goblin, and a second,
separate overworld-Engine construction confirms the refusal fires and the
potion stays in inventory, unconsumed.

## 0av. Sure-Footing Draught - full immunity to terrain hazard damage (`sure_footing_draught`)

The fourth `BuffKind` (§0ar/§0as/§0at's namespace), and mechanically the
simplest of the four: a single early-return guard added to the top of the
existing `Engine._apply_environmental_hazard` (the method behind the
Scoured Reach's dunes and the Northern Steppe's `ashen_plains`/
`blighted_forest` chip damage, §0p) -

```python
if BUFF_SURE_FOOTED in self.player.fighter.active_buffs:
    return
```

- placed before the tile-kind lookup, so it skips the message log entry
*and* the damage together: the terrain simply doesn't register as
hazardous while the buff is active, not "still hurts, just less." No new
choke point needed elsewhere - `_apply_environmental_hazard` was already
the single call site for this mechanic (`process_enemy_phase`, once per
turn, regardless of `is_overworld`), so extending it in place was enough.

**Ticked the ordinary way, same as vigor and shadowed** - `sure_footed`
needs no entry in `_tick_active_buffs`'s `BUFF_HASTE` exclusion (§0as),
since it doesn't skip any part of the world's own turn, just makes one
specific per-turn effect inert while active. No intensity concept either
(hazardous ground either hurts or it doesn't, same reasoning `BUFF_HASTE`/
`BUFF_SHADOWED` already established), so `buff_potency` is rejected for
it via the existing `buff_potency_matches_buff_kind` split (§0as) with no
further changes needed there - `_BUFF_KINDS_WITH_POTENCY` still names
only `BUFF_VIGOR`.

**Deliberately scoped to hazard damage only, not the Northern Steppe's
Visitor-band random-encounter roll** (`_maybe_trigger_visitor_band_encounter`,
`VISITOR_BAND_ENCOUNTER_CHANCE`) - a related but separate mechanic that
also fires per-turn on `ashen_plains`/`blighted_forest`. Sure-Footing
Draught is a terrain-damage counter, not an aggro/encounter-avoidance
tool; folding encounter suppression into it would have blurred the line
this round's items have otherwise kept clean (compare Vial of Shadows'
own explicit "not the Smoke Bomb's job" scope note, §0at) and would make
a single cheap consumable trivialize a piece of overworld tension that's
meant to matter. A future item can own that distinction on its own terms
if the brainstorm list calls for one.

Ships one real example, `sure_footing_draught` (`data/items.yaml`,
`grants_buff: sure_footed`, `buff_duration: 15`, no `buff_potency`,
`cost: 35`). Verified end-to-end via direct `Engine`/`Entity` construction
against the real catalog entry, standing on a `dunes` tile throughout: one
turn without the buff confirms ordinary hazard damage still applies
(30 -> 29), drinking immediately stops it for that same turn (`_apply_
environmental_hazard` runs after `process_player_action` within the same
turn, same immediate-effect timing Vial of Shadows already established),
14 further turns confirm zero damage for the buff's full duration, and
the turn immediately following its expiry shows hazard damage resuming
exactly on schedule.

## 0aw. Smoke Bomb - the melee escape Vial of Shadows explicitly left for later (`smoke_bomb`)

Closes the scope gap §0at's own docs flagged when Vial of Shadows shipped:
"a deliberate scope limit distinguishing it from the still-unbuilt Smoke
Bomb (an 'escape + aggro break' tool)... Shadows is for slipping past
threats at range, not escaping ones already on top of you." This is that
tool, and it's built almost entirely out of two mechanisms this round
already has, combined on one item rather than inventing a third: an
instant short-range relocation (new) plus a brief `BUFF_SHADOWED` window
(reused as-is from §0at) to keep whatever was adjacent from immediately
closing the distance again.

**The relocation, `ItemDef.local_teleport: bool`** - a plain flag like
`is_teleport`, but deliberately not named the same or unified with it:
`is_teleport` leaves the level entirely (`engine.wants_overworld = True`,
resolved by `main.py`); `local_teleport` moves the player to a random
walkable, unoccupied tile within `SMOKE_BOMB_TELEPORT_RADIUS` (5) of their
current position on the *same* map, using the exact `nearby_walkable_tiles`
helper `main.py`'s own Visitor-band-ambush placement already relies on -
just centered on the player instead of an ambush arena. `UseItemAction`
computes the candidate destination *before* removing the item from
inventory (mirroring `teleport`/`second_sight`'s own pre-consumption
refusal checks), so a boxed-in player with no valid nearby tile (verified
with a literal 1x1 `GameMap`) gets `"The smoke has nowhere to carry you."`
and keeps the bomb, unconsumed - the same "refuse before consuming, not a
disappointing no-op" shape `is_teleport`'s overworld refusal already
established, chosen here because a smoke bomb that goes nowhere achieved
literally nothing, same reasoning as that refusal.

**The one real wrinkle: `potion_kind` classification.** `smoke_bomb`
also sets `grants_buff: shadowed` on itself (reusing shadowed rather than
building a redundant "close-range concealment" buff from scratch), which
means `potion_kind()`'s existing `if item.grants_buff == BUFF_SHADOWED:
return "shadowed"` branch would have silently swallowed every smoke bomb
into the *same* hotbar slot as a plain Vial of Shadows - two genuinely
different items competing for one `POTION_KINDS` entry, unable to be
carried side by side. Fixed by checking `item.local_teleport` **first**,
before any `grants_buff` branch, so `local_teleport=True` always wins
classification regardless of what buff the item also grants underneath -
confirmed with a dedicated test constructing both an `ItemEffect` with
just `grants_buff=shadowed` and one with `local_teleport=True,
grants_buff=shadowed` side by side, asserting they resolve to different
kinds.

**Nothing new needed in `_tick_active_buffs`, HUD labels, or
`engine/save.py`** - the granted buff is a real `BUFF_SHADOWED` entry,
indistinguishable at the data level from one Vial of Shadows itself
grants, so every mechanism §0at already built (the `_perform_ai` choke
point, the `"SHADOWED: ..."` HUD line in both `render.py` and
`play_llm.py`, the generic `active_buffs` save round-trip) picks it up
for free - confirmed live rather than assumed, since the HUD line
rendered correctly in the verification script below with zero new render
code written this round.

Ships one real example, `smoke_bomb` (`data/items.yaml`, `local_teleport:
true`, `grants_buff: shadowed`, `buff_duration: 3`, `cost: 40` - a short
shadowed window on purpose, just long enough to put distance behind you,
not a general-purpose stealth tool at Vial of Shadows' own 8-turn scale).
Verified end-to-end via direct `Engine`/`Entity` construction against the
real catalog entry: the player relocates to a new tile within the
configured radius, the shadowed buff appears correctly on the HUD, and a
1x1-map construction confirms the refusal path leaves the bomb
unconsumed and the player exactly where they started.

## 0ax. Bezoar of Clarity - clears every skill cooldown at once (`bezoar_of_clarity`)

The ninth of this round's original ten-item potion brainstorm (potion #7,
Water Walking, was already built before this round began; Ironroot
Draught is the one still left), and a near-exact structural repeat of
Antidote (§0aq) - the same "plain flag, clears a dict, always consumes,
sometimes a no-op" shape, just aimed at `Entity.skill_cooldowns` instead
of `Fighter.active_effects`.
`ItemDef.resets_skill_cooldowns: bool`, `ItemEffect.resets_skill_cooldowns`,
a `potion_kind()` branch, and one `UseItemAction` elif branch
(`had_cooldowns = bool(entity.skill_cooldowns); entity.skill_cooldowns.clear()`)
- the exact same four-step shape Antidote already established, right down
to reusing its identical "but feel no different" fallback message for the
no-op case.

**Needs no new persisted state, same as Antidote's own §0aq note** -
`Entity.skill_cooldowns` has been a genuine `SavedPlayer` field since
skills themselves shipped, long before this potion existed
(`engine/save.py`'s `capture_save`/`_build_player` already round-trip it
verbatim). `engine/save.py` needed zero changes, and no render/HUD work
either - there's no buff to display, just a dict that's suddenly empty.

**No dungeon/overworld distinction, unlike most of this round's other
potions** - skill cooldowns aren't tied to terrain or location the way
water-walking, sure-footing, or the map-scale second sight are, so there
was no refusal case to design at all: it either has something to clear or
it doesn't, everywhere, always.

Ships one real example, `bezoar_of_clarity` (`data/items.yaml`,
`resets_skill_cooldowns: true`, `cost: 50` - priced at the round's upper
end, on par with Bottled Second Sight, since clearing every cooldown at
once is a strictly stronger effect than any single active-skill perk's
own cooldown reduction would be). Verified end-to-end via direct
`Engine`/`Entity` construction against the real catalog entry: two
independent cooldowns (arbitrary perk-id keys, since none of this round's
active perks are built yet - `skill_cooldowns` only cares about the
dict shape, not catalog membership) both clear in one drink, and a
separate no-cooldowns case confirms the potion still consumes with the
same graceful no-op message Antidote already uses.

Nine of the original ten potions are now shipped: Water Walking (an
earlier session), Antidote (§0aq), Elixir of Vigor (§0ar), Draught of
Swiftness (§0as), Vial of Shadows (§0at), Bottled Second Sight (§0au),
Sure-Footing Draught (§0av), Smoke Bomb (§0aw), and Bezoar of Clarity
here. One potion remains before the ten active perks begin: Ironroot
Draught (stun/knockback immunity).

## 0ay. Ironroot Draught - full stun immunity, and no knockback because none exists (`ironroot_draught`)

The tenth and final potion of this round's original brainstorm. The
fifth `BuffKind` (`BUFF_IRONROOT`), same no-potency shape as haste/
shadowed/sure_footed - a stun either lands or it doesn't, nothing to
scale.

**Scoped down from the brainstorm's own framing before writing any
code.** The original pitch was "stun/knockback immunity," but this
engine has no knockback mechanic at all - nothing anywhere displaces an
entity against its will (confirmed by grepping the whole codebase for
"knockback" and finding only planning notes, no implementation). Building
immunity to a mechanic that doesn't exist would be immunity to nothing,
so this ships as stun immunity only, documented here as a deliberate
scope cut rather than a silent omission - the same "don't build
unrequested mechanics" restraint Sure-Footing Draught's own encounter-
avoidance scope note already established (§0av). If a knockback mechanic
is ever added, Ironroot Draught is the natural place to extend, not a
reason to add one preemptively.

**The choke point required touching combat.py's structure, not just
adding a new site** - unlike every hazard/detection gate so far (a single
`if` at the top of one method), stun can currently reach the player
through three separate call sites in `engine/combat.py`: `_apply_damage`'s
`attacker.inflicts_effect` block (a monster's innate stun attack - the
only one with real shipped content behind it, e.g. `wraith`/
`excavation_warden`), `_maybe_apply_weapon_affix` (an attacker's weapon
affix landing on the defender), and `_maybe_apply_armor_affix` (a
defender's armor affix striking back at the attacker). All three
duplicated the identical `target.fighter.active_effects[kind] =
ActiveEffect(...)` + inflict-message shape. Rather than pasting the same
immunity check into three places, this round factored that shared tail
into a new `_inflict_effect(engine, target, kind, potency, duration)`
helper - a real, in-place refactor of pre-existing code, not just new
code alongside it - and the immunity check lives in exactly that one
function:

```python
if kind == EFFECT_STUN and target.fighter is not None and BUFF_IRONROOT in target.fighter.active_buffs:
    engine.message_log.add(f"{target.name} shrugs off the stun.", category="combat")
    return
```

Checked against `target.fighter.active_buffs` directly rather than
`target is engine.player` - `active_buffs` is already a per-Fighter dict
with no player-only assumption baked in anywhere else in this codebase
(`_tick_active_buffs` iterates every entity on the map), so there was no
reason for this one check to special-case "the player" when "whichever
fighter has the buff" is both simpler and already the correct general
rule. Nothing about the refactor changed behavior for poison, weaken, or
any existing affix interaction - confirmed by the full suite passing
unchanged immediately after the refactor, before any ironroot-specific
code or tests were added at all.

**A distinct "resisted" message, not silence** - `"{name} shrugs off the
stun."` fires in place of the normal `"{name} is stunned!"` line, so a
player watching the log can tell the potion is actively doing something
each time it blocks a hit, the same "don't let a working effect look like
nothing happened" reasoning Antidote's own no-op message follows.

Ships one real example, `ironroot_draught` (`data/items.yaml`,
`grants_buff: ironroot`, `buff_duration: 20`, no `buff_potency`,
`cost: 35`). Verified end-to-end via direct `Engine`/`Entity`/catalog
construction against a real shipped monster (`wraith`, whose own
`inflicts_effect: stun` is unrelated placeholder data no test had to
invent): three full turns of live combat against it with the buff active
never once landed a stun, logging "shrugs off the stun" every time the
attack connected, and a companion test confirms ironroot leaves poison
completely untouched - the immunity is stun-specific, not a general
"can't be afflicted" flag.

**This completes all ten potions from the original brainstorm** - Water
Walking (an earlier session), Antidote (§0aq), Elixir of Vigor (§0ar),
Draught of Swiftness (§0as), Vial of Shadows (§0at), Bottled Second Sight
(§0au), Sure-Footing Draught (§0av), Smoke Bomb (§0aw), Bezoar of Clarity
(§0ax), and Ironroot Draught here. The ten active perks - Blink Strike,
Riposte Stance, Root the Ground, Chain Lash, Guard Break, Marked for
Death, Phase Through, Vengeful Strike, War Horn, Bloodletter - are next.

## 0az. Blink Strike - a third active-skill effect kind, and the first that targets (`blink_strike` perk)

The first of ten active perks from the same brainstorm the potions round
just finished, and the third `SkillEffectKind` alongside the existing
`"heal"` (Second Wind) and `"aoe_damage"` (Ground Pound) - a new
`SKILL_EFFECT_BLINK_STRIKE = "blink_strike"`, `PerkDef.
skill_blink_strike_range: int`, and the same two-validator shape
(`skill_fields_set_together`/`skill_effect_matches_payload`) every prior
skill kind already established, extended rather than replaced.

**The one genuinely new capability this round needed: picking a specific
target.** Both existing skills are untargeted - heal always affects the
caster, aoe_damage always hits whatever's already adjacent. Blink Strike
is the first active skill in this project that has to *choose* an enemy
to act on, and there's no player-facing targeting UI for active skills
today (unlike `FireAction`'s own aim-mode cursor for ranged attacks).
Rather than building that UI layer just for one perk, the skill picks its
own target automatically - the nearest hostile within
`skill_blink_strike_range` (Chebyshev distance, same metric every other
range check in this project already uses), ties broken by
`game_map.entities` order rather than randomly (deterministic, and an
exact-distance tie is rare enough that either candidate is an equally
reasonable pick regardless). This mirrors aoe_damage's own "automatic,
not manually aimed" precedent rather than inventing a new interaction
pattern - a future perk that genuinely needs the player to choose *which*
of several valid targets would be the first one to justify building real
skill-targeting UI, and this isn't that perk.

**The mechanic itself is two reused primitives stitched together, not new
combat math:** `Engine.use_skill`'s new branch finds the nearest qualifying
target, then calls `nearby_walkable_tiles(game_map, target.x, target.y,
count=1, radius=1)` - the exact same helper Smoke Bomb's own relocation
already relies on (§0aw), just centered on the target instead of the
player and shrunk to a single adjacent tile - to find a landing spot, then
relocates the player there directly (`entity.x, entity.y = landing`,
`MovementAction`'s own assignment shape) and calls `resolve_attack(self,
attacker=entity, defender=target)` - the *ordinary* melee attack function,
using `effective_attack` and the full dodge/crit/weapon-affix/
inflicts-effect pipeline, not a flat skill-damage number like
`resolve_skill_damage` (aoe_damage's own choice). This is a deliberate
difference in flavor from Ground Pound: Blink Strike isn't extra damage,
it's guaranteed melee range against something you couldn't otherwise
reach yet - whatever you'd normally hit it for, you hit it for here too.

**Whiffs still cost the cooldown, matching aoe_damage's own "wasted
attempt" precedent exactly** - both failure cases (nothing in range;
something in range but boxed in with no free adjacent tile, verified with
a monster walled in on all eight sides) still consume
`skill_cooldown_amount` and the turn, logging a distinct message
(`"There's nothing within range to blink to."` /
`"There's nowhere to land beside {name}."`) rather than refunding the
attempt - triggering the skill is the commitment, not a preview.

**Restructured `use_skill`'s own control flow slightly** while adding
this: the previous version had only `if skill_effect == HEAL: ... return`
followed by an *implicit* trailing block assumed to be aoe_damage (fine
with two kinds, ambiguous with three) - now `aoe_damage` gets its own
explicit `if` block too, with `blink_strike` as the trailing case. Purely
a readability change; the full suite passed unchanged with this
restructuring alone, before any blink_strike-specific code existed.

**Deliberately not added to either trainer's `trainer_perks` list yet**
(`millhaven_trainer`/`wayford_trainer` in `data/entities.yaml`, both
currently identical master lists) - same scope boundary already
established for every potion this round: the mechanic ships fully
implemented and tested against the real catalog, but *placing* new
content into the world (which NPC teaches it, at what price relative to
the existing lineup) is being treated as a separate, later pass, not
bundled into landing the mechanic itself.

Ships one real example, `blink_strike` (`data/perks.yaml`, `skill_effect:
blink_strike`, `skill_blink_strike_range: 5`, `skill_cooldown_kind: turns`,
`skill_cooldown_amount: 6`, `xp_cost: 55`). Verified end-to-end via direct
`Engine`/`Entity`/catalog construction: a goblin 4 tiles away is correctly
targeted, the player relocates to land exactly adjacent to it, the attack
lands using the player's real `effective_attack`, the skill hotbar
displays "Blink Strike: 6t" afterward, and separate tests confirm nearest-
target selection among multiple candidates, peaceful-NPC exclusion, an
out-of-range refusal, a kill case (XP awarded, entity removed), and the
boxed-in landing failure.

## 0ba. Riposte Stance - a skill that grants a BuffKind, and a new combat choke point (`riposte_stance` perk)

The second active perk, the fourth `SkillEffectKind` (`riposte_stance`),
and the sixth `BuffKind` (`BUFF_RIPOSTE`) - but the first time a *skill*,
not an item, has granted one. Nothing about `BuffKind`/`Fighter.
active_buffs` was ever actually potion-specific (§0ar's own docstring
already frames it as "a timed condition on a Fighter"), so
`Engine.use_skill`'s new branch just writes `entity.fighter.active_buffs[
BUFF_RIPOSTE] = ActiveEffect(...)` directly, the same construction
`UseItemAction` uses for vigor/haste/shadowed/sure_footed/ironroot - no
new plumbing needed to let a skill be the one setting it. Ticked the
ordinary way by `_tick_active_buffs`, same as every buff except haste.

**The actual mechanic lives entirely in `engine/combat.py`, not in
`use_skill`** - a new `_maybe_riposte(engine, attacker, defender)`,
called from `_apply_damage`'s `if damage > 0:` block right after
`_maybe_apply_weapon_affix`/`_maybe_apply_armor_affix`, the same "a hit
landed" trigger those two already use. Where an armor affix retaliates
with a status-effect proc, `_maybe_riposte` retaliates with a real
counter-attack - `resolve_attack(engine, attacker=defender, defender=
attacker)`, using the holder's own `effective_attack` and the *full*
dodge/crit/weapon-affix/inflicts-effect pipeline (a countered monster can
itself be poisoned by the counter, dodge it, etc. - nothing here is a
scaled-down "skill damage" number, it's an ordinary attack that happens
to trigger reactively instead of on the player's own turn). This is the
same "reuse the real combat resolution, don't invent a parallel one"
discipline Blink Strike's own docstring already established (§0az),
applied to a *reactive* trigger instead of a manually-initiated one.

**Scoped by the buff check alone, no `is engine.player` special-case** -
`BUFF_RIPOSTE` is granted exclusively by a learned active skill, and only
the player can ever learn perks, so `_maybe_riposte`'s guard (`defender.
fighter is not None and BUFF_RIPOSTE in defender.fighter.active_buffs`)
naturally never fires for a monster defender in shipped content, without
needing to say so explicitly - the same reasoning `_inflict_effect`'s own
Ironroot check already follows (§0ay). A defensive `attacker.is_alive`
guard sits alongside it for robustness (an attacker somehow already dead
by the time its own hit resolves shouldn't get counter-attacked), though
nothing in the current single-hit resolution order can actually trigger
that path - kept anyway since the cost of the check is one comparison,
and the alternative (a `None`/dead-entity call into `resolve_attack`)
would be a real, if currently unreachable, bug.

**`use_skill`'s fourth branch needed no restructuring this time** -
Blink Strike's own addition (§0az) already converted every branch to an
explicit `if`, so Riposte Stance slots in as one more, cleanly, with
nothing implicit left to trip over.

**Deliberately not added to either trainer's `trainer_perks` list yet**,
same scope boundary every item in this round has followed since Blink
Strike (§0az) - the mechanic ships fully implemented and tested; placing
new content into the world is a separate, later pass.

Ships one real example, `riposte_stance` (`data/perks.yaml`,
`skill_effect: riposte_stance`, `skill_riposte_duration: 5`,
`skill_cooldown_kind: turns`, `skill_cooldown_amount: 10`, `xp_cost: 60`
- a longer cooldown than duration on purpose, so the stance is never
permanently up). Verified end-to-end via direct `Engine`/`Entity`
construction against the real catalog entry, with a live hostile monster
attacking the player turn by turn: the monster's own hit still lands in
full (riposte doesn't grant any extra defense, only retaliation), the
counter fires in the same turn using the player's real `effective_attack`,
a 0-damage hit confirms no riposte fires when nothing actually landed,
and a low-hp attacker confirms the counter can kill and award XP through
the normal death pipeline - no special-casing needed there either, since
`resolve_attack`'s own `_apply_damage` call already handles it.

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

**Combat variance (crit/dodge)**: `engine/combat.py`'s `COMBAT_VARIANCE_ENABLED`
(default `True`) layers a `DODGE_CHANCE` (10%, prevents all damage and any
on-hit effect - poison, etc. - outright) and a `CRIT_CHANCE`/`CRIT_MULTIPLIER`
(10% for 1.5x, rounded up) on top of the deterministic formula below,
symmetrically for attacker and defender, player or monster. This is a
deliberate, explicitly reversible experiment - the whole formula was fully
deterministic before it and may go back to being so - so it's gated
behind that one module constant rather than woven through the damage math
inline: flip it to `False` to restore the original formula exactly, no
other changes needed. Every existing (and future) test that asserts exact
damage/message values relies on `tests/conftest.py`'s autouse fixture,
which forces it off for the whole suite by default - a test that
specifically needs to exercise crit/dodge must re-enable it itself
(`monkeypatch.setattr(engine.combat, "COMBAT_VARIANCE_ENABLED", True)`)
and pin `random.random` for its own determinism, same as any other
randomness-dependent test in this project (see the villager-wander tests
for the established pattern). Because both rolls share one `random.random()`
call per hit, a test forcing a *crit* still needs the dodge roll to land
on the non-dodge side first - sequence the mock's return values
accordingly (`iter([0.99, 0.0]).__next__`), not a single constant.
Hits-to-kill math elsewhere in this section is written against the
*deterministic* formula - treat `DODGE_CHANCE`/`CRIT_CHANCE` as adding
symmetric texture around that baseline, not something to re-derive every
placement's arithmetic against.

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
player can reach without a weapon upgrade already in hand. For a quicker
check than a full playthrough, `testbuild` (§0s) spawns a hand-picked
build directly at a dungeon's entrance and reports its XP-equivalent
against `DungeonDef.balance_reference_xp`, when set. For a poisonous
monster (§0t), the defender's expected total damage per landed hit is
`direct + potency * duration`, not just `direct` - include it in this math.

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

**Retreat-to-heal as a deliberate balance lever, not just a fallback.**
`Engine._advance_world_clock`'s passive heal (+1 hp/hour) only runs while
`is_overworld` is true - a dungeon or settlement never ticks the clock or
heals the player on its own (see the method's own docstring). That means
"walk back to the entrance and wait on the overworld a while" is always a
real, working recovery option, and it's never free: those hours come off
whatever quest deadline is running on the *same* clock elsewhere (`by Day
N` deadlines, §0j) - a genuine time-vs-safety trade, not busywork. This
justifies sizing a dungeon's total hostile roster *above* what a single
clean push can absorb, deliberately, as long as (a) the level's geometry
lets a hurt player actually disengage and retreat rather than getting
cornered, and (b) at least one recovery item exists before the point a
retreat becomes necessary, so the choice is "fight on a little longer or
pay the time cost," not "there was never a choice." Sunless Hollow's
6-wolf den (down from an original, too-punishing 7 - see its bible's
"Correction" note) was tuned around exactly this: a `testbuild`-verified
~40 XP build clears it, but only by using both its potions and taking two
separate retreat-and-heal trips (~50 game-hours total). Don't reach for
"add more potions until a single push clears cleanly" as the default fix
for an overtuned dungeon - check whether retreat-to-heal is the intended
lever first.

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
   "arena" beat, not as the easy default. **For a settlement specifically,
   follow §0af**: road network drawn first, one town square, buildings
   placed against the network with doors facing their path, footprint
   scaled to the actual cast size - not the combat-dungeon geometry advice
   above, which is about room/corridor variety, not settlement structure.
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
