# Goblin Ambush — Dungeon Bible

*A short site key for `data/dungeons/goblin_ambush/`, per the mandatory
per-dungeon-bible convention (`docs/content_design_process.md` §0d) - no
exception for a small map. Read `docs/content_design_process.md` §2 (balance
methodology) before touching the level - this dungeon's whole reason for
existing is one deliberately placed fight, so the geometry has to earn it.*

## The pitch

Not a real place - a scripted overworld encounter (`data/encounters.yaml`),
reached only by leaving Millhaven for the overworld while `spreading_the_warning`
(`data/quests.yaml`) is `in_progress`, never by walking to it. Doesn't fire
the instant the player steps outside the gate - `warning_ambush`'s
`delay_hours: 3` means it only catches up with them after 3 hours of actual
overworld travel (see `main.py`'s `_armable_encounter`/`_due_encounter`),
so it reads as the goblins intercepting them partway down the road, not an
ambush waiting at Millhaven's own doorstep. The player has just taken the
Village Chief's warning out onto the road toward Wayford;
this is the goblin horde (the same one `goblin_warning`/`spreading_the_warning`
have been building up narratively) making its first real appearance -
opportunistic raiders trying to intercept the message before it reaches
Wayford's Road Warden, not an organized ambush party with a plan beyond
"jump whoever's on this stretch of road." Practical, not cinematic - matches
this project's established tone for every other goblin/bandit encounter so
far (`sunken_mine.md`, `wayford_arc.md`'s bandits).

Fleeable, not a lock: per the user's explicit choice, the player can leave
at any time, win or not - originally via a single terminal `stairs_up`
tile, since generalized into the first real use of `open_boundary`
(`content/schema.py`'s `LevelDef.open_boundary`, `docs/content_design_process.md`
§0h): the whole map perimeter is walkable `forest`, not a wall ring, so
walking off *any* edge leaves - a stairway in the middle of a forest
clearing never made sense, and a single-tile-only exit felt like a trap
door rather than the open ground it's meant to be. This isn't a
"boss fight," it's a real but fair first taste of danger during overworld
travel.

## The one set piece: The Narrows

**Corrected description - an earlier draft of this document described a
felled-log chokepoint that was never actually built.** What ships today,
and what this section now describes, is a single open clearing: no
internal walls, no forced single-file gap, nothing separating
`player_start` from the goblins but open ground. The level keeps the
name "The Narrows" (`data/dungeons/goblin_ambush/levels/level_01.lvl`'s
own `name` field) even though nothing in the level is narrow - read that
as the goblins' own name for the spot (maybe there used to be a felled-
log choke here and it's since rotted or been cleared), not as a
description this document should keep asserting is still true.

- **The clearing**: a 17x13 rectangle of `plains`, ringed by `forest` on
  every side (see Terrain below), with no interior geometry of any kind.
  `player_start` sits roughly in the lower third; all 3 `goblin` spawns
  (hp 12/atk 4/def 1, unmodified) sit clustered near the top, 7-8 tiles
  away - the player has open ground to close, or to retreat across, in
  every direction.
- **What this means for the fight `docs/content_design_process.md` §2
  actually describes**: that section's chokepoint guidance ("a first
  multi-monster fight needs a chokepoint so the player doesn't get
  surrounded") does not apply to this level as shipped - there is no
  chokepoint here to hold. A player who closes the distance risks
  meeting some or all of the 3 goblins at once rather than one or two at
  the choke, which the hits-to-kill math below was originally written
  assuming wouldn't happen. This is worth revisiting as an actual level
  change (adding the felled-log partition this document used to
  describe) rather than something this bible can fix by description
  alone - flagged here, not silently corrected into "working as
  intended."
- Per the unchanged balance math: the player kills one goblin in 3 hits
  (`5 - 1 = 4` dmg/hit, `12 / 4 = 3`) and takes 3 dmg/hit taken
  (`4 - 1 = 3`) per goblin actually landing hits - multiply by however
  many of the 3 actually reach the player at once, since nothing in the
  level's own geometry limits that number.

## Terrain

Outdoor (`plains` interior + `forest` perimeter, no dungeon `floor`/
interior, no interior `wall` of any kind) - same tile vocabulary
Millhaven/Wayford already established is valid on any dungeon level, not
exclusive to settlements (`docs/content_design_process.md` §0c). `forest`
(walkable, blocks line of sight per `TILE_PASSABILITY`) rings the whole
map rather than a wall - it both reads as "the trees keep going past
what's mapped" and is the actual walkable ring `open_boundary` needs to
let the player reach an edge at all.

## Explicitly out of scope

- No loot, no reward item - the point is the fight and the road continuing
  safely, not treasure. `spreading_the_warning` itself stays reward-less,
  unchanged.
- No second level, no `stairs_down` - `requires_stairs_down: false`, same
  shape as a settlement (one level, no deeper progression), even though
  this isn't peaceful.
- No overworld `dungeon_entrance` tile anywhere targets this dungeon -
  deliberate; it's only reachable through the `EncounterDef` trigger.
- No `stairs_up` tile anymore either - superseded by `open_boundary: true`
  (see the pitch section above); kept as historical context only in case a
  future dungeon ever wants a single explicit exit *alongside* an open
  boundary (this one doesn't need both).
