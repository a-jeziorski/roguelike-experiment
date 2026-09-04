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
