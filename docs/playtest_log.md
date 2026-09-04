# Playtest log

Findings from periodic testing sessions driven through `tools/play_llm.py`
(see its module docstring and `docs/content_design_process.md` §0ao for why
it's a state-snapshot recorder, not an action-replay one). Each session is
appended below in chronological order. Replays are saved under `saves/`
(gitignored - local artifacts only) with a `playtest_<timestamp>.jsonl` name
per session so consecutive sessions don't clobber each other, and also
mirrored to `saves/latest_session.jsonl` (the standing one-off-recording
convention, so a session looking for "the most recent test recording"
without a timestamp still finds it there). Watch either back with
`python tools/replay.py saves/<file>.jsonl`.

Read this before trusting a CLI-only bug report against a monster: see
§2026-09-04's first finding before concluding a monster-targeted skill is
broken from a multi-command `play_llm.py` session.

## Summary of open findings (updated after each session)

Ranked roughly by how actionable/impactful they are. All still open -
flagged per this repo's convention, not fixed here. See each session below
for full detail; memory files (`[[name]]`) carry the same content for
future sessions to build on.

**High-value content gaps** (engine mechanics all verified correct - as of
session 13, literally every one of the 20 brainstorm items has been
individually live-confirmed working via `play_llm.py` - the gap is purely
that nothing places this content anywhere reachable):
1. [[project_perks_unreachable_in_content]] - all 10 of the newest active-
   skill perks are taught by zero trainers. Likely the single biggest gap
   found across every session so far.
2. [[project_potions_unreachable_in_content]] - 9 of 11 potions are placed
   in zero shops/dungeons.
3. [[project_gear_unreachable_in_content]] - 7 mid/high-tier weapons and
   armor pieces, same pattern.

Together: of the "10 potions + 10 perks" brainstorm this repo's own memory
once described as fully shipped, a real player can currently reach exactly
1 of 20 items without a debug tool.

**Real bugs, smaller scope:**
- [[project_a_warning_worth_carrying_ungated]] - a quest fires without its
  narrative prerequisite; likely a one-line `requires_quest_id` fix.
- `forgotten_ruins`' `level_02a`/`level_02b` branch-fairness gap
  (pre-existing finding, [[bible_reconciliation_sweep_findings]]) - live-
  played in session 15 and confirmed worse than the static finding
  suggested: the disadvantaged branch's opening room is also a genuinely
  dangerous twin-flank fight, and killed a `testbuild` character playing
  it as intended (no weapon, default potions).
- `pin`/`QuestLog.set_active_quest` has no id validation and silently
  blanks the quest HUD line on a bad id (session 9) - not reachable by a
  real player (the graphical client only pins from a closed menu), but a
  trap for any other direct API caller, `play_llm.py` sessions included.

**Rendering issues** (all confirmed real, all currently latent/not-yet-
manifested in any shipped level - see
[[project_glyph_collisions_and_phase_through_render_gap]] for the full,
growing list): item/terrain, entity/entity, and entity/terrain glyph
collisions across `data/items.yaml`/`data/entities.yaml`; Phase Through
hides an overlapped monster from the map view.

**Testing-methodology lessons** (not game bugs - read before a future
session misreads `play_llm.py` output the same way):
- [[feedback_cli_monster_effects_dont_survive_calls]] - a monster's status
  effects don't survive between separate CLI calls, which can look
  exactly like a broken skill.
- [[feedback_repeated_message_text_not_stale_evidence]] - identical-
  looking repeated combat messages across calls aren't proof of stale
  state; the same event can legitimately recur with the same wording.

**Thoroughly tested and confirmed working, no issues found:** the five
newest skills' core mechanics (session 1), shop/`buy`, trainer/`learn`,
ranged `fire` (session 3), death/`restart` (session 5), trinket bonuses
(session 5), poison combat incl. the damage-gate on armor blocking it
(session 7), Rusty Key pickup/HUD (session 8), the full quest turn-in
flow (session 9), and **all 9 potions + all 10 perks** from
[[project_potions_unreachable_in_content]]/[[project_perks_unreachable_in_content]]
(potions: Vigor/Swiftness session 4, Antidote/Clarity session 10,
Sure-Footing/Second Sight/Shadows/Smoke Bomb session 11, Ironroot session
12; perks: Marked for Death/Phase Through/Vengeful Strike/War Horn/
Bloodletter session 1, Blink Strike/Riposte Stance/Root the Ground/Chain
Lash/Guard Break session 13) - every one of the 20 mechanically correct,
none placed anywhere a real player could ever find them.

## 2026-09-04 - new skills smoke test (Weeping Cistern, Broken Watch)

Replay: `saves/playtest_20260904_080125.jsonl` (110 frames).

Focus: the five most recently added active-skill perks (`mark_for_death`,
`phase_through`, `vengeful_strike`, `war_horn`, `bloodletter`, plus
`guard_break` for comparison) - the least playtested content at the time of
this session. Played an unequipped-build character (`testbuild`, standard
iron_sword/chain_mail loadout) through The Weeping Cistern's two levels,
then a second `testbuild` run into Broken Watch's Outer Yard for a denser
monster room.

### Finding 1 - CLI cross-call testing gap for monster-side status effects (not a gameplay bug)

**Symptom observed live:** Cast `mark_for_death` on a Drowned Wretch (11 HP,
0 defense), then in a *separate* `attack` call landed a hit for exactly 9
damage (= my ATK 9 - its DEF 0) instead of the expected 11 (+2 mark bonus).
Looked exactly like Marked for Death's damage bonus silently not applying.
Same shape with `war_horn`: cast on an adjacent Rat, then in the next
(separate) `wait` call the Rat neither fled nor attacked, as if the fear
effect had evaporated.

**Root cause:** `engine/save.py`'s `capture_save`/`_build_player` only
persists the *player's* `active_effects`/`active_buffs` across a save/reload
- monster `Fighter` state beyond `(x, y, hp)` is deliberately never saved
(see the comment at `engine/save.py:190-193`, consistent with
`SavedLevelState`'s `alive_entity_spawns` shape). `tools/play_llm.py` reloads
the whole engine from the save file on *every single command*, so any status
effect a skill inflicts on a monster (Marked, Frightened, Exposed) is
correctly applied within that one call, then silently gone by the time the
next separate CLI command reloads state - even though its `turns_remaining`
hadn't run out yet.

**Confirmed not a real gameplay bug:** in ordinary play (`main.py`), the
`Engine` stays resident in memory across turns and only round-trips through
`save.py` on an explicit save action, so this never bites a real player.
Verified the underlying mechanics are correct with a live, no-reload engine:
`tests/test_engine.py::test_marked_effect_adds_bonus_damage_from_any_attacker_not_just_the_caster`
and the whole `war_horn`/`frightened` test group
(`test_frightened_monster_flees_instead_of_attacking_when_adjacent`, etc.)
all pass - 8/8 and 26/26 respectively across all six skills tested here.

**Why this matters for future testing:** a multi-command `play_llm.py`
session is the wrong tool to verify a monster-targeted, multi-turn status
effect (Marked for Death, Guard Break's Exposed, War Horn's Frightened).
Only the *single* skill-use call (which still runs one full enemy-AI phase)
shows a real result; anything checked in a later, separate call has already
lost the effect. Cross-check those against `tests/test_engine.py` instead,
or accept CLI verification only for what resolves within one call (a direct
damage skill, a player self-buff like Phase Through, an immediate
AI-response check right after casting).

**Suggested follow-up (not fixed here):** either call this out explicitly in
`tools/play_llm.py`'s module docstring/`--help`, or extend
`SavedLevelState`/`alive_entity_spawns` to round-trip monster
`active_effects` for testing fidelity. Flagging rather than fixing, per
`docs/content_design_process.md`'s convention for out-of-scope findings.

### Finding 2 - item glyphs collide with terrain glyphs (and each other), breaking the legend

`engine/render.py`'s `TILE_VISUALS` and `data/items.yaml` don't share a
glyph namespace. Confirmed collisions:

| Glyph | Item | Terrain kind |
|---|---|---|
| `<` | Chain Mail | `stairs_up` |
| `~` | Water Walking Potion, Scholar's Pendant | `sea` / `deep_water` |
| `+` | Orcish Bow | `door` |
| `;` | Crossbow | `ashen_plains` / `scoured_ground` |
| `'` | Lucky Charm | `landmark` |
| `^` | Shadow Cloak Pin | `mountain` |

Also two items collide with each other: Road Ledger and Waystation Manifest
both use `=`.

**Reproduced live:** in The Flooded Vault (Weeping Cistern level 2), a
6-tile pond of `deep_water` plus one real Water Walking Potion all render as
`~`. `tools/play_llm.py`'s legend is built as `{glyph: entity.glyph}` keyed
purely by character (`_render_map_region` in `tools/play_llm.py`), so it
printed `~: Water Walking Potion (item)` as the *only* explanation for the
whole pond - actively mislabeling five deep-water hazard tiles as an item.
`inspect`/`entities` gave the correct picture, but the map+legend view alone
was actively wrong, not just ambiguous.

This also affects the graphical client's tile grid (`grid[sy][sx] =
entity.glyph` overwrites the terrain glyph at that cell in both renderers),
though color/sprite art likely keeps it visually distinguishable there in a
way plain ASCII can't - didn't verify the graphical side this session.

**Suggested follow-up:** either keep item glyphs disjoint from
`TILE_VISUALS`'s terrain set (and from each other), or make
`tools/play_llm.py`'s legend-building distinguish terrain from entities
instead of overwriting by shared character.

### Finding 3 - Phase Through parks the player on a living monster's tile, hiding it from the map entirely

Cast Phase Through, then `move`d directly onto an adjacent Rat's tile - the
move succeeded (as designed: "walk straight through anything blocking your
path"), landing the player exactly on the Rat's square. Confirmed via
`entities` that the Rat was still alive at that same `(x, y)` as the player.
But `look`'s map view showed only `@` at that tile - the Rat's glyph
`entities: e for entity in sorted(game_map.entities, ...)` in
`tools/play_llm.py`'s `_render_map_region` only ever writes one glyph per
grid cell, so the later-priority entity (the player) fully overwrote the
Rat's `r`. The Rat remained alive, attacking, and listed in `entities` -
just invisible on the map/`look` output for as long as the two share a tile.

Two entities normally can never occupy the same tile in this game (movement
refuses into anything occupied) - Phase Through is the one mechanic that
creates this situation, so it's the only place this rendering gap can
surface. Likely reproduces in the graphical client too, for the same
one-glyph-per-cell reason, though not verified here.

### Positive confirmations (mechanics correctly implemented)

- **Bloodletter** reads its actual post-defense hit, not a fixed heal: hit a
  Gray Ooze (ATK 9 - DEF 1) for 8 damage, healed exactly 4 (half, per
  `skill_bloodletter_heal_divisor: 2`) - confirms the "reads its own
  attack's real outcome" design intent.
- **Phase Through** genuinely lets the player walk through a blocking
  hostile entity (see Finding 3 - the walk-through itself works; only the
  *rendering* of the resulting overlap is the bug).
- All six skills' full unit-test coverage passes (26/26 across
  `mark_for_death`, `phase_through`, `vengeful_strike`, `war_horn`,
  `bloodletter`, `guard_break` in `tests/test_engine.py`), confirming
  damage math, range/targeting, cooldowns, and AI overrides are all correct
  at the mechanism level - the gaps found this session are rendering/testing-
  tool issues, not engine logic bugs.
- Weeping Cistern's monster roster (1 Drowned Wretch + 1 Gray Ooze on level
  1, zero on level 2) matches memory's note that the roster was
  intentionally lightened after prior playtesting - not a bug, just noted
  for context since it meant this session had to switch dungeons (Broken
  Watch) to get a denser room for War Horn's AoE.

### Minor / low-priority

- `goto <item name>` paths to the tile *adjacent* to the item (the same
  convention used for NPCs, where standing on them isn't possible), not onto
  it - so `pickup` right after a `goto <item>` reliably fails with "There is
  nothing here to pick up." Correct for `goto <npc>`, awkward for items
  (which you actually need to stand on). Minor CLI ergonomics gap, not
  called out in `play_llm.py --help`'s `goto` description.
- The Flooded Vault's second exit stair (`e`, `next_level: null`, no
  `description`/`announce`) drops you straight back to the overworld with
  only the generic "You enter The Sundered Realm" message - no flavor text,
  unlike most other dungeons' `next_level: null` exits which have a custom
  `description` + `announce: true`. Confirmed this is the intended exit
  mechanic (not a bug - `next_level: null` is the established convention
  used by ~15 other dungeons), just missing the usual flavor polish.

## 2026-09-04 (2) - Northern Steppe recon hook (The Watch Post)

Replay: `saves/playtest_20260904_084812.jsonl` (23 frames).

Focus: `northern_watch_post` - per memory the current end of the main story
chain, not yet playtested via the CLI. `testbuild` into the dungeon
(deliberately "no hostile roster" per its own `dungeon.yaml` description),
talked to its NPCs, and checked the quest wiring `docs/region_bibles/
northern_steppe.md` describes for this location.

### Finding - `a_warning_worth_carrying` has no prerequisite gate, unlike its sibling quest

Talking to the Sentry immediately granted **A Warning Worth Carrying**
(`questgiver_entity_id: watch_post_sentry` in `data/quests.yaml`) even
though **Word from the North** - the quest that's supposed to actually send
the player here (`target_dungeon_id: northern_watch_post`, itself gated
`requires_quest_id: spreading_the_warning`) - had never been given or
completed. Confirmed via `quests`: `word_from_the_north` doesn't even
appear in the log, while `a_warning_worth_carrying` shows as active,
carrying dialogue ("The Sentry's watched this road long enough to know
Millhaven's closer to whatever's coming...") that presupposes context
(the horde, the ash-scarred land north of here) the player was never given.

Checked `data/quests.yaml`: of every quest in the file, only two use
`requires_quest_id` at all (`a_wall_worth_holding`→`goblin_warning` and
`word_from_the_north`→`spreading_the_warning`) - `a_warning_worth_carrying`
has no such field, so simply talking to the Sentry grants it regardless of
prior quest state. The region bible is explicit that the intended path is
"Reached via `word_from_the_north` ... and `a_warning_worth_carrying`" (a
sequential pair), so this looks like a real gap rather than an intentional
ungated NPC.

**How reachable is this normally (not via `testbuild`)?** Checked
`data/overworld/cells.lvl` and `cells/northern_steppe.lvl` for any
flag/quest-conditional gating on the overworld connection or the dungeon
entrance tile itself - found none (no `flag`/`gate`/`require` references at
all), consistent with how every other dungeon entrance in this game works
(a static, always-walkable tile). So this isn't purely a `testbuild`
artifact: a player who physically walks to the Northern Steppe before ever
picking up `spreading_the_warning` could reach the Sentry and pick up this
quest out of order in real, non-`testbuild` play too - just a much less
likely path than the intended one, since reaching the region at all
presumes a lot of prior travel. Didn't fully verify there's no *other*
soft gate (e.g. distance/danger alone discouraging early arrival) beyond
what's checked here.

**Suggested follow-up (not fixed here):** add
`requires_quest_id: word_from_the_north` (or `spreading_the_warning`) to
`a_warning_worth_carrying` in `data/quests.yaml`, matching how its sibling
quest is already gated - one-line fix if confirmed worth making.

### Finding - hostile/peaceful entity glyph collisions exist at the data level, but none currently ship together

Ran the same glyph-collision check from the previous session's Finding 2
against `data/entities.yaml` (65 entity defs) instead of items. Found
several *hostile vs. peaceful* pairs sharing a glyph: `villager`
(peaceful) / `vulture` (hostile) both `v`; `bandit` (hostile) /
`millhaven_debtor` (peaceful) both `b`; `drowned_wretch` (hostile) /
`millhaven_trainer` (peaceful) both `d`; `wolf` (hostile) /
`grey_valley_weaver` (peaceful) both `w`; `warden` (hostile) /
`saltmarsh_witch` (peaceful) both `W`; plus a three-way collision on `c`
and `s`. Unlike the item/terrain collisions found last session, **none of
these actually co-occur in any single shipped dungeon level** - checked
every `.lvl` file each colliding id appears in and confirmed no overlap
(e.g. `vulture` only ever spawns in `broken_watch/level_01`, `villager`
never does). So this doesn't manifest as a live bug in anything currently
shipped - it's a latent risk for whoever places new content later (a new
level combining, say, wolves and a villager NPC would silently create the
exact "can't tell hostile from peaceful by glyph alone" problem already
seen with items). Noting it now so it's on record before it bites a future
level, not because it's broken today.

### Positive confirmations

- The Watch Post's `dungeon.yaml` claim ("no hostile roster here at all")
  checked out: `entities` listed only a Sentry and two Villagers, all
  peaceful.
- The Sentry NPC has a proper small building (matches
  [[feedback_stationary_npcs_need_buildings]] - nothing standing exposed in
  open plains here).

## 2026-09-04 (3) - shop, trainer, and ranged combat

Replay: `saves/playtest_20260904_092328.jsonl` (55 frames).

Focus: `buy`, `learn`, and `fire` - three core CLI commands none of the
first two sessions had exercised. Used Millhaven's Shopkeeper and Old
Drillmaster trainer for the first two, then a fresh `testbuild` into Broken
Watch with a Hunting Bow equipped for ranged combat against its existing
monster roster.

### Positive confirmations - all three systems work correctly

- **`buy healing_potion`** at Millhaven's Shopkeeper: charged exactly 25
  gold (100 → 75), added the potion. Refuses cleanly ("The shop is
  unavailable.") when not actually adjacent to a shopkeeper.
- **`learn ground_pound`** at the Old Drillmaster: deducted exactly the
  perk's `xp_cost: 50` (110 → 60 XP), auto-bound it to an empty skill slot,
  confirmed via `character`.
- **`fire 6 11`** (Hunting Bow, `ranged_attack_bonus: 3`) on a 6 HP/0 DEF
  Rat: dealt exactly 8 damage (base ranged 5 + bow's 3), killed it,
  consumed exactly 1 arrow (10 → 9 ammo shown in the HUD). Firing at a
  target beyond range/LOS refused cleanly with "No clear target there.",
  no turn spent.

### Minor - `goto` won't route around a single blocking peaceful NPC

Asked `goto shopkeeper` from across Millhaven's square; it announced a
16-step path, then immediately reported "Stopped early: blocked by Town
Guard (peaceful) at (24, 4)" at step 0/16 - the geometrically shortest path
ran straight through the guard's tile, and `goto` gave up entirely rather
than trying an alternate route, even though sidestepping one tile and
re-issuing the same `goto` succeeded immediately. Consistent with
`tools/play_llm.py --help`'s documented "never treats a blocking entity as
safe" rule (so refusing outright is correct/safe behavior, not a bug), but
the help text doesn't mention that a single stray peaceful NPC on the
direct line can require a manual sidestep-and-retry. Minor CLI ergonomics
note, not a functional bug.

### Supplementary glyph-collision data point

`town_guard`'s glyph `T` also collides with the `forest` terrain kind's `T`
(see the running list in [[project_glyph_collisions_and_phase_through_render_gap]]).
Checked Millhaven/Stonebridge/Wayford's level files (every dungeon that
spawns a `town_guard`) for `forest` tiles - none currently use any, so like
the `entities.yaml` collisions from the previous session, this one is
latent/unshipped rather than live. Recording it there rather than starting
a fourth separate note for the same pattern.

## 2026-09-04 (4) - the 20 items nobody can ever reach

Replay: `saves/playtest_20260904_095843.jsonl` (7 frames) - short, since the
headline finding here is a content-placement gap discovered by reading
`data/items.yaml` and grepping content, not by playing through a level. A
hand-edited save (`saves/potion_test.json`, not part of the recorded replay
sequence) was used afterward to confirm the drinking mechanics themselves
still work correctly once a potion is actually in inventory.

Focus: potions. Only Healing, Teleportation, and Water Walking had been
exercised by any session so far (out of 11 total `*_potion`/`*_elixir`/
`*_draught`/smoke bomb/bezoar items in `data/items.yaml`).

### Finding - 9 of the game's 11 potions are placed nowhere in shipped content

`data/items.yaml` fully defines Antidote, Elixir of Vigor, Draught of
Swiftness, Vial of Shadows, Bottled Second Sight, Sure-Footing Draught,
Smoke Bomb, Bezoar of Clarity, and Ironroot Draught - each with a real
mechanical effect (`grants_buff`, `cures_effects`, `reveals_map`,
`resets_skill_cooldowns`) and their own flavor text. Grepped every
`data/dungeons/*/levels/*.lvl` for `item: <id>` and every entity's
`shop_inventory:` in `data/entities.yaml` for all nine: **zero matches, for
any of them.** No dungeon floor drop, no shop stock, no quest reward
anywhere in the repo. Only Healing Potion, Teleportation Potion, and Water
Walking Potion are actually placeable/obtainable - the other 9 are complete,
tested, and entirely unreachable by a real player.

This directly narrows [[potions_perks_brainstorm_complete]] - "shipped"
there evidently meant "defined in `data/items.yaml` with working engine
mechanics," not "placed anywhere a player can find them." The engine side
genuinely is fine (see below); this is purely a missing-content gap, likely
the single highest-value thing to fix out of everything found across these
four sessions - potions are core kit and 9 of 11 might as well not exist.

### Finding - all 10 of the newest perks are also unteachable by any trainer (bigger than the potions gap)

Following the same thread: checked whether the six skills from sessions 1
and the other four from the same "brainstorm" batch (Blink Strike, Riposte
Stance, Root the Ground, Chain Lash, plus Guard Break/Marked for Death/
Phase Through/Vengeful Strike/War Horn/Bloodletter - 10 total) are
learnable in real play. `data/entities.yaml` has exactly two trainer NPCs,
`millhaven_trainer` and `wayford_trainer`, and both teach the *identical*
9-perk list (`toughness_1`, `toughness_2`, `weapon_training_1`,
`shield_training_1`, `marksman_training_1`, `steady_aim`, `light_feet`,
`second_wind`, `ground_pound`) - an entirely different, older set. None of
the 10 newer perks appear in either trainer's list, or anywhere else
(`learn_perk` via the `learn` action is the only non-debug way to gain a
perk; checked `data/quests.yaml`/`engine/engine.py` for any other grant
path - none). So of the whole 20-item "10 potions + 10 perks" brainstorm
this repo's memory describes as fully shipped, a real player can currently
reach **1 of 20** (just Water Walking Potion) without a debug tool. Every
skill tested live in session 1 of this log (Marked for Death, Phase
Through, Vengeful Strike, War Horn, Bloodletter) was only reachable there
via `testbuild --perk`.

### Positive confirmations - drinking mechanics work correctly once obtainable

Hand-edited a save file's inventory to add three of the nine
otherwise-unreachable potions, then drank them live through
`tools/play_llm.py` to confirm the CLI path (not just the unit tests) works:

- **Elixir of Vigor**: Attack 9→12, Defense 2→5 (+3 to *both*, matching
  `buff_potency: 3`). Initially looked like a bug (defense changing from an
  "attack" elixir), but `engine/entity.py`'s `_vigor_bonus` docstring
  confirms this is deliberate - vigor is a combined attack+defense buff, not
  attack-only. Worth remembering so a future session doesn't re-flag this.
- **Draught of Swiftness**: drank cleanly, correct flavor message. Didn't
  fully verify the free-action mechanic live (would need a monster nearby
  to observe a turn not costing the enemy a move) - the underlying
  `_consume_haste_action` logic already has dedicated unit test coverage,
  didn't re-derive it here.
- Both potions' `use_potion_slot`/`bind_potion` plumbing worked exactly like
  the already-tested Healing/Water Walking potions.

### Supplementary glyph-collision data point

8 of these 9 unreachable potions (everything except Water Walking, which
already collides with `deep_water`/`sea`) share glyph `!` with Healing
Potion too - 9 items on one symbol, the largest collision found across all
four sessions. Checked every level placing 2+ `!`-glyph items for whether
any two are actually *different* potion types (vs. two copies of the same
one) - none are: every multi-potion level only ever places duplicate
Healing Potions. So even this, the widest collision found, is currently
latent rather than live - noted in
[[project_glyph_collisions_and_phase_through_render_gap]] rather than a new
entry. If the content gap above ever gets fixed by scattering these potions
into real levels, this collision stops being theoretical fast.

## 2026-09-04 (5) - death and restart

Replay: `saves/playtest_20260904_103315.jsonl` (17 frames), using a
dedicated hand-edited save (`saves/death_test.json`, HP set to 1 to force a
quick, controlled death rather than grinding one out).

Focus: the death → `restart` flow, never exercised by any prior session,
and with real history here - [[feedback_restart_resets_global_state]]
documents an earlier bug where restart left stale shared state behind.
Wanted to confirm that fix still holds.

### Positive confirmations - death/restart is clean, no bugs found

- Dying (a Rat's hit dropped HP 1→0 mid-`goto`) correctly set `game_state`
  to dead: HUD showed `YOU HAVE DIED. Use 'restart' to play again.`, and
  further commands (`wait`) silently no-op rather than erroring or
  corrupting state.
- `restart` after death gave a genuinely clean slate: HP 30/30, gold 0, XP
  0, no weapon/armor/trinket, no learned perks, hotbar slots back to
  defaults (Healing/Teleport/empty) - matches
  [[feedback_restart_resets_global_state]]'s fix, still holding.
- Calling `restart` again while *alive* (with real, non-fresh state - HP
  damaged to 27/30 from live combat, non-spawn position) changed nothing:
  HP and position both carried forward unchanged. `restart --help` says
  "Only works once dead," and this confirms it's actually enforced, just
  as a silent no-op rather than an explicit refusal message - the same
  quiet-no-op pattern already seen with `wait` while dead. Worth noting
  only because my first pass at this test was inconclusive (compared two
  identical fresh-spawn states and couldn't tell if `restart` had silently
  done nothing or genuinely re-run) - a future session re-checking this
  should compare against *live, non-fresh* state like this one did, not
  two resets in a row.
- `restart`'s reset position/level was the debug dungeon (`broken_watch`,
  wherever `testbuild` was pointed), not the true game's canonical intro -
  confirmed this is correct, not a bug: `testbuild` builds its own Engine
  with `starting_level` set to whatever dungeon was requested, and
  `restart()` always returns to *that* Engine's own `starting_level` by
  design (see `Engine.restart`'s docstring) - exactly the right behavior
  for a debug/balance-testing session (keep testing the same dungeon after
  dying), not something a real player would ever see.

### Bonus check - trinket bonus math

Equipped Lucky Charm (`trinket_bonus: 0.1` on `crit_chance`) via
`testbuild --trinket lucky_charm`: `character` showed Crit chance 10%→20%,
correct.

## 2026-09-04 (6) - reachability audit: everything else unreferenced

No replay - this session extended the previous one's "grep every level/shop
for references" method from potions/perks to the whole entity and item
catalog, rather than playing a live session. Wrote a script cross-
referencing every `data/entities.yaml`/`data/items.yaml` id against every
`entity:`/`item:` in `data/dungeons/*/levels/*.lvl` plus every
`shop_inventory:`/`trainer_perks:` list.

### False-positive check, worth recording as a methodology note

The raw script flagged 13 "unreferenced" entities. Before treating any of
them like the potions/perks finding, checked each one - most turned out to
already be accounted for, just not by static level placement:

- **6 are placed dynamically, not statically**: `ash_bound_husk`,
  `bound_eye`, `stitched_vanguard`, `hollow_chanter`, `bound_crawler`,
  `charnel_colossus` are all spawned by `engine/engine.py`'s
  `FRAYED_EDGE_BAND`/`CINDER_MARCHES_BAND`/`HOLLOW_REACH_BAND` random-
  encounter tables (the `visitor_band_ambush` mechanism -
  [[northern_steppe_bestiary]] already documents this), which a level-file
  grep can never see. A grep-only reachability check has this blind spot -
  worth remembering before repeating this kind of audit.
- **6 more (`slime`, `bone_caller`, `boar`, `cave_bear`, `lurker`,
  `mimic_flask`) plus `excavation_warden`** are genuinely unplaced, but
  that's already fully documented, intentional, in-progress work -
  `docs/content_design_process.md` §0ag-§0am walks through each one as
  "define now, place later," one new AI behavior showcased at a time,
  reviewed before placement. Not a new finding; correctly flagged by the
  script, correctly *not* worth reporting as a bug.

### Finding - 7 mid/high-tier weapons and armor pieces are also unreferenced, and this one doesn't look intentional

`broadsword` (atk+5), `battle_axe` (atk+6), `war_hammer` (atk+7),
`studded_leather_armor` (def+2), `orcish_bow`, `crossbow`, and `elder_bow`
all appear in `data/items.yaml` with real stats but zero placements in any
dungeon level or shop - same pattern as the potions/perks finding, and
unlike the monster list above, **nothing documents these as deliberately
staged**. The only mention of any of them in `docs/content_design_process.md`
is as a hypothetical "mid-upper gear tier" used to calibrate the Northern
Steppe bestiary's target stats, not as content actually meant to ship.
None of the seven have a `cost` field, consistent with being intended as
dungeon floor loot (like the already-placed `iron_sword`/`chain_mail`,
which also lack `cost`) rather than shop stock - so the natural fix
location is scattering them into higher-tier dungeons' item placements,
the same shape as the potions fix.

This sits alongside [[project_potions_unreachable_in_content]] and
[[project_perks_unreachable_in_content]] as a third instance of the same
underlying pattern: a fair amount of this game's implemented content never
made it into actual level/shop placement. Recorded as its own memory
([[project_gear_unreachable_in_content]]) rather than folded into the
potions one, since it's items.yaml but a different category (equipment,
not consumables) with a different likely fix location (dungeon loot
tables, not necessarily shops).

## 2026-09-04 (7) - poison combat, and a near-miss false bug report

Replay: `saves/playtest_20260904_114020.jsonl` (90 frames), Silver Mountain
Caves (Silversilk Caves) - a dungeon no prior session had entered, chosen
specifically to reach `cave_spider`, the only early-game monster that
inflicts poison.

### Positive confirmation - poison only lands on damage, and expires correctly

Confirmed `combat.py`'s `if damage > 0:` gate: a Cave Spider bite fully
absorbed by Chain Mail ("hits Player but does no damage") correctly applies
*no* poison - armor stopping the bite stops the venom too. Only once a
weaker build let the bite land for real damage did poison actually apply,
with the documented "first tick lands the same turn as the hit" behavior
(`Cave Spider hits Player for 2 damage.` → `Player is poisoned!` →
`Player writhes from poison, taking 1 damage.`, all in one exchange).

### A near-miss: I almost reported a false bug here

Standing adjacent to the spider and calling `wait` repeatedly, HP kept
dropping by 3/turn while the HUD's `POISONED: ... (2 turn(s) left)` line
and the "Recent messages" text looked *frozen* - same "2 turns left", same
three combat lines, call after call. Read literally, that looks exactly
like the [[feedback_cli_monster_effects_dont_survive_calls]] pattern from
session 1: HP draining from something the log isn't explaining. Almost
wrote this up as a new instance of that bug.

Before doing so, reproduced it in a minimal in-memory script (bypassing
`play_llm.py`/save-reload entirely, using the same `make_open_map`/
`make_player`/`make_monster` helpers `tests/test_engine.py` uses) - and it
reproduced identically, which immediately ruled out a save/reload issue.
Printing the actual message list (not just eyeballing repeated-looking CLI
text) showed the truth: **every turn genuinely does log a fresh
`Cave Spider hits Player...` / `Player is poisoned!` / `Player writhes...`
triplet** - it's not stale, it's real, new, identical-looking text each
time. Because the spider hits me *every* turn I stand there, and
`_inflict_effect` unconditionally re-applies (refreshes, per its own
"never stacks" contract) the full 3-turn poison duration on every
successful bite, poison's `turns_remaining` never gets a chance to
actually reach 0 - it's re-topped-up to 3, ticks once to 2, forever, for
as long as I keep standing next to the spider taking free hits. Correct,
intentional refresh-not-stack semantics working exactly as designed - not
a bug, just a genuinely nasty (accurately nasty) "don't melee a poisonous
enemy indefinitely" lesson.

**Process lesson for future sessions**: identical-looking repeated message
text in `play_llm.py`'s "Recent messages" tail is *not* evidence of stale
state on its own - the same event can legitimately recur turn after turn
with the exact same wording. Before concluding something is frozen/stale
(the way [[feedback_cli_monster_effects_dont_survive_calls]] genuinely
was), check the actual message *count*/sequence across calls, or better,
reproduce in a minimal in-memory script the way `tests/test_engine.py`
does - it's fast, and it's the only way to fully rule out a save/reload
artifact versus a real behavioral loop.

## 2026-09-04 (8) - Prison Tower: keys, locked doors, and a real close call

Replay: `saves/playtest_20260904_121924.jsonl` (73 frames) - Prison Tower,
untouched by any prior session, chosen specifically to reach one of the
game's six `door: rusty_key` locked-door placements.

### Positive confirmation - key pickup and the "Keys: N" HUD counter

Picked up a Rusty Key on level 2 (The Guard Barracks); the HUD's
`Keys: 1` counter updated correctly and stayed accurate through several
subsequent fights.

### Investigation - a `goto` call skipped the locked door entirely, and why that's correct

Aimed `goto 17 10` (a rough guess at "near the door") to head toward level
2's exit; it ended up two levels deeper (into "The Lower Cellblock," level
3) without ever logging `engine/actions.py`'s
`"You use the {key} to unlock the door."` message, and the key was still
in inventory afterward, unconsumed - looked at first like the door/key
mechanic was silently bypassed or broken.

Reading `data/dungeons/prison_tower/levels/level_02.lvl`'s full map
explained it cleanly: the locked door only gates a *dead-end* side room
(iron sword, chest, barrel - optional loot), not the path to the stairs
down, which sit behind a separate, ordinary (non-locked) opening on the
level's south side. My guessed coordinate happened to route through that
legitimate southern passage, never touching the locked door at all - so
no unlock ever should have fired. Confirmed the actual unlock+consume
mechanic is correctly implemented via
`tests/test_engine.py::test_locked_door_unlocks_and_consumes_matching_key`
(passes) rather than re-verifying live, since the character was down to
5/30 HP by this point and backtracking through two already-cleared levels
to deliberately walk into the door wasn't worth the death risk for a
mechanic already covered by a real, targeted test.

### A genuine close call, not a bug

HP dropped from 30 to 5 over three real fights (a Guard hitting for 3 a
turn, a Crossbow Guard sniping from range, a second Guard) with zero
healing potions on hand (`testbuild`'s default). Every individual exchange
resolved correctly (damage math, crits, dodges all consistent with what
prior sessions already verified) - this was just a legitimately dangerous
dungeon crawl on thin resources, the kind of risk/reward tension
[[feedback_retreat_to_heal_is_a_balance_lever]] already documents as
intended. Stopped the session here rather than pushing a 5-HP character
further, same judgment call a real player would make.

## 2026-09-04 (9) - quest turn-in, and pin's missing validation

Replay: `saves/playtest_20260904_125555.jsonl` (22 frames), Millhaven -
finally turning in `goblin_warning`, active since the very first session
but never actually delivered to its target NPC until now.

### Positive confirmation - the full quest turn-in flow works correctly

`talk`ing to the Village Chief (the quest's `target_entity_id`) with
`goblin_warning` active correctly fired the completion dialogue, awarded
the documented 15 XP, and flipped the quest to `completed` with its
`completed_description` flavor text - all exactly as designed, confirmed
via `quests`.

### Finding - `pin` has no input validation and silently blanks the quest HUD line

`pin not_a_real_quest` produced no error, but the HUD's `Quest: ...` line
- present a moment earlier as `Quest: The Goblin Warning - completed` -
vanished entirely afterward. Confirmed the cause precisely: re-issuing
`pin goblin_warning` immediately restored the line. Root cause in
`engine/quest.py`: `QuestLog.set_active_quest(quest_id)` is
`self.active_quest_id = quest_id` with zero validation that the id exists
in `self.quests`; `active_quest()` then does `self.quests.get(...)`,
returning `None` for a bad id, and the HUD apparently only renders the
line when that lookup succeeds.

**Not reachable by a real player**: `main.py:303` only ever calls
`set_active_quest(quests[selected].id)` from an actual index into the
player's own displayed quest list (`engine/input_handlers.py`'s pin
menu) - always a real id, never a free-text string. So this is purely a
`tools/play_llm.py`-and-beyond-only edge case, since the CLI's `pin`
takes a raw string for testing convenience where the real game only
offers a closed menu.

**Still worth a note**: this means `QuestLog` trusts its caller completely
for a valid id, which is fine for the one real caller today but is a trap
for any other direct API user - including a `play_llm.py` testing session
that fat-fingers a quest id and gets a silently blanked HUD instead of an
error, which could itself be misread as "the quest system broke" rather
than "bad input." A cheap improvement, if anyone's touching this code
later: have `pin`/`set_active_quest` refuse an unknown id with a clear
message instead of accepting anything.

## 2026-09-04 (10) - the last two untested potions

Replay: `saves/playtest_20260904_132918.jsonl` (30 frames), using a
hand-edited save (`saves/potion_test2.json`) to reach Antidote and Bezoar
of Clarity - the two [[project_potions_unreachable_in_content]] potions
session 4 hadn't yet drunk live. Both confirmed working correctly.

- **Antidote** (`cures_effects: true`): drunk while poisoned (2 turns
  left) - `"You drink the Antidote and the afflictions lift."`, and the
  HUD's `POISONED: ...` line disappeared immediately. (Got re-poisoned the
  very same turn by the adjacent spider's counter-attack - drinking still
  costs a turn, so an adjacent enemy still gets to act. Not a bug, just a
  positioning lesson: retreat before curing, don't cure while still being
  bitten.)
- **Bezoar of Clarity** (`resets_skill_cooldowns: true`): put Marked for
  Death on its 10-turn cooldown, drank the Bezoar -
  `"...your mind sharpens - every skill feels ready again."` - and the
  skill HUD line immediately flipped from `9t` back to `ready`.

With this, 4 of the 9 potions from [[project_potions_unreachable_in_content]]
have now been live-verified through `play_llm.py` (Vigor, Swiftness from
session 4; Antidote, Clarity here) despite none of them being reachable in
actual shipped content - the remaining five (Vial of Shadows, Bottled
Second Sight, Sure-Footing Draught, Smoke Bomb, Ironroot Draught, the last
of which was injected in session 4 but never actually drunk there) are
still only covered by `tests/test_engine.py`'s generic `ItemEffect`-based
tests, not a live CLI drink.

## 2026-09-04 (11) - four more potions confirmed, one holdout remains

Replay: `saves/playtest_20260904_140214.jsonl` (74 frames). Same
hand-injection technique as sessions 4/10, aimed at the four potions
session 10 left untested. All four confirmed working correctly.

- **Sure-Footing Draught** (hazard immunity): stepped onto `ashen_plains`
  unbuffed first - `"Ash-choked ground scrapes at exposed skin..."`, net
  -1 HP (the documented `-2` hazard damage partially offset by
  `_advance_world_clock`'s own `+1`/hour passive heal). Drank the potion
  *while standing on the hazard tile* and took zero damage that same turn
  (net +1, just the passive heal) - the buff blocks the hazard starting
  immediately, not just from the next tile onward.
- **Bottled Second Sight** (instant map reveal): refused cleanly on the
  overworld (`"There's too much ground out here for any vision to take
  in."` - a real, deliberate refusal path in `engine/actions.py`, not a
  bug), then correctly revealed all of Silver Mountain Caves' level 1 in
  one `map` call once drunk inside the dungeon.
- **Vial of Shadows**: drank cleanly (`"...fade into the shadows."`);
  didn't isolate the detection-radius mechanic itself from CLI black-box
  testing (that's already covered by `tests/test_engine.py`'s generic
  buff tests), just confirmed the drink and grant work.
- **Smoke Bomb**: used while adjacent to a Cave Spider - teleported 5
  tiles away instantly (`(7, 20) → (12, 20)`) and granted the HUD's
  `SHADOWED: unseen from a distance (2 turn(s) left)` buff in the same
  action, exactly as documented (`local_teleport` + `grants_buff:
  shadowed` together).

**One holdout**: Ironroot Draught (stun immunity) needs the game's only
two stun-inflicting monsters, `wraith` (Elder Cairn level 2) or
`excavation_warden` (still unplaced per [[northern_steppe_bestiary]]).
Spent real time trying to reach the Elder Cairn entrance via `testbuild`
and couldn't find the actual entrance tile from the spawn position within
a reasonable number of moves - stopped rather than keep burning turns on
navigation. Left for a future session: `testbuild elder_cairn`, then
`map`/`entities` immediately to actually orient before moving, rather than
guessing directions blind the way this session did.

## 2026-09-04 (12) - Ironroot Draught, the last potion, confirmed

Replay: `saves/playtest_20260904_144009.jsonl` (40 frames). Picked up
session 11's holdout: `testbuild elder_cairn`, immediately checked `map`
this time instead of guessing directions - the entrance was one tile
south, found and entered in a single move.

Fought through to Elder Cairn's `wraith` (level 2, "The Heart of the
Cairn") - a `sleeping_guard` that doesn't attack until alerted, giving a
clean window to drink Ironroot *before* it woke up. Once it did:
`"You drink the Ironroot Draught and your stance sets like rooted
stone."`, then `Wraith hits Player for 6 damage. Critical hit!` followed
immediately by `"Player shrugs off the stun."` - the exact
`engine/combat.py::_inflict_effect` stun-immunity path, confirmed live.

**With this, all 9 potions from [[project_potions_unreachable_in_content]]
have now been live-verified through `play_llm.py`** across sessions 4, 10,
11, and 12 - every one of them mechanically correct, none of them placed
anywhere a real player could ever find them. Stopped the session at 12/30
HP (two Stone Sentinels fought through to get here) rather than push
further, same judgment call as session 8.

## 2026-09-04 (13) - the last four perks, and Guard Break, both checklists closed

Replay: `saves/playtest_20260904_151418.jsonl` (27 frames), Broken Watch.
Session 1 live-tested 5 of the 10 [[project_perks_unreachable_in_content]]
perks (`mark_for_death`, `phase_through`, `vengeful_strike`, `war_horn`,
`bloodletter`); this session closes out the remaining five
(`blink_strike`, `riposte_stance`, `root_ground`, `chain_lash`,
`guard_break`) via `testbuild --perk`. All five confirmed correct.

- **Blink Strike**: targeted a Rat 4 tiles away - position jumped from
  `(2, 13)` to `(7, 12)` (adjacent to where the Rat had been) in the same
  action that landed the hit. A real teleport-then-attack, not a
  disguised ranged attack.
- **Chain Lash**: hit 2 of 3 nearby hostiles in one cast (`Player lashes
  Giant Rat for 3 damage.` / `Player lashes Bandit for 2 damage.`,
  damage correctly reduced by each target's own defense) - the third
  (a Vulture) was out of the 4-tile chain range, consistent with "up to
  3 hits," not guaranteed 3.
- **Riposte Stance**: every hit landed on the player for its 5-turn
  duration triggered a full counter-attack, confirmed against two
  different attackers in the same turn (`Player answers with a riposte!`
  followed by a real damage hit, twice, once per attacker) - correctly
  killed both a Giant Rat and a Bandit over the following turns via
  counters alone.
- **Root the Ground**: cast with a Vulture sitting exactly 3 tiles away
  (in range, not adjacent) - `"Vulture is rooted in place!"`, and
  confirmed via `entities` that its position genuinely didn't change over
  the following turn despite two nearby kills (its own AI's usual
  approach-and-scavenge trigger), unlike its normal behavior.
- **Guard Break**: `"Bandit's guard is broken!"` fired correctly alongside
  the direct damage hit, matching session 1's existing coverage of the
  Exposed debuff.

**With this, all 10 perks from [[project_perks_unreachable_in_content]]
are also now live-verified** - combined with session 12's potions, every
one of the 20 "brainstorm" items ([[potions_perks_brainstorm_complete]])
has now had its actual in-game mechanic confirmed correct via
`play_llm.py`, despite none of them being reachable by a real player
without a debug tool. Both checklists this whole playtest effort's two
biggest findings implied are now closed.

## 2026-09-04 (14) - Sunken Mine: a clean crawl, and a locked-door pattern confirmed

Replay: `saves/playtest_20260904_154816.jsonl` (76 frames) - the first
session in a while to just play a fresh, previously-unvisited dungeon
rather than chase a specific mechanic. No bugs found; everything below is
a positive confirmation or a design-pattern note.

### Positive confirmations

- Cleared a good spread of Sunken Mine's roster (Kobold, Kobold Shaman,
  Rat, Goblin) across both explored levels with no combat-math surprises -
  damage, dodges, and crits all matched expected formulas throughout.
- The `ranged_basic` Kobold Shaman correctly falls back to a normal melee
  `"hits"` (not `"shoots"`) once already adjacent, rather than trying to
  fire point-blank - sensible behavior, confirmed by the verb in the
  combat log matching `engine/combat.py`'s `resolve_attack`/
  `resolve_ranged_attack` split.
- An item and a monster can occupy the same tile before the monster's
  killed (a Rat sitting exactly on a Rusty Key) - picking it up after
  killing the Rat worked cleanly once standing on the tile.

### Design pattern, not a bug: locked doors keep gating side rooms, not the main path

Tried a second time (after session 8's Prison Tower) to deliberately walk
into a locked door and watch the unlock fire live. Failed again the same
way: `goto`/`walk` toward the door's approximate coordinates ended up
finding the dungeon's actual stairs-down route instead, past a locked door
this level's map shows guarding a different, dead-end-looking side room.
Two dungeons in a row, same shape - reinforces session 8's conclusion that
this is a deliberate content convention (locked doors gate optional loot,
never the critical path), not something worth re-chasing a third time.
The mechanism itself stays covered by
`tests/test_engine.py::test_locked_door_unlocks_and_consumes_matching_key`.

### Note to self

Misread a goblin's actual direction relative to the player twice in a row
(assumed "south" from the map glyph layout without rechecking `entities`'
exact coordinates first) - wasted two `attack` calls hitting a wall while
the goblin got free hits in. No game bug; just a reminder to check
`entities`/`Position` before an `attack <direction>` call rather than
eyeballing the ASCII map, especially right after a `goto` that may have
landed at an unexpected angle.

## 2026-09-04 (15) - Forgotten Ruins: the branch-fairness gap has real teeth, and a real death

Replay: `saves/playtest_20260904_162347.jsonl` (68 frames). Picked up an
existing, previously-*static*-only finding:
[[bible_reconciliation_sweep_findings]] flagged (2026-08-30, never played
out) that `forgotten_ruins`' `level_02a` branch leaves the player without
the `iron_sword` the sibling `level_02b` branch hands out directly, with
the "fairness" compensation (an `iron_sword` on `level_04`) sitting behind
an optional locked door - not actually guaranteed. Wanted to see what that
actually feels like to play, not just read in the data.

Confirmed the data is unchanged (`level_02a` has no `iron_sword`;
`level_02b` does; `level_04`'s copy is still behind `door: rusty_key`).
Then deliberately took the disadvantaged `level_02a` branch with a
`testbuild` character carrying no weapon (base ATK 5), to play the exact
scenario the bible's fairness claim is about.

**level_02a's opening room killed the character.** Two `sleeping_guard`
Skeletons (16 HP, ATK 5/DEF 2 each) flank the first corridor from both
sides - waking both at once sandwiches the player with no way to retreat
that breaks adjacency from both simultaneously (Chebyshev/diagonal
adjacency means a single step off the corridor's centerline is still
adjacent to whichever skeleton is on that side). Burned both healing
potions just surviving the opening exchanges, killed one skeleton at 1 HP
remaining, and died to the second's counter-hit at 2 HP. `restart` worked
cleanly afterward (same [[feedback_restart_resets_global_state]] flow
session 5 already confirmed).

**Why this matters beyond confirming the door/key claim**: this wasn't
just "the disadvantaged branch is missing a nice weapon upgrade" - it's
measurably *harder* too (a genuinely dangerous, hard-to-escape twin-flank
opening, fought here with less than the intended kit). The branch that's
supposed to be fairness-compensated is both worse-equipped *and* a rougher
fight, which is a stronger version of the concern the existing memory
already flagged. Not fixing this here, per the existing "left unfixed by
user choice" note on that memory - just adding a live data point that
sharpens the case if this ever gets revisited.
