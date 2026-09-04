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
