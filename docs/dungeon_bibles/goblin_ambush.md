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

Fleeable, not a lock: per the user's explicit choice, the exit works exactly
like any other dungeon's terminal stairway - reachable and usable at any
time, win or not. This isn't a "boss fight," it's a real but fair first
taste of danger during overworld travel.

## The one set piece: The Narrows

A stand of trees just off the road, felled and dragged into a single
choke - not a fortification, just enough deadwood piled between two thicker
trunks to force anyone coming through into single file. The goblins picked
the spot for exactly that reason: whoever's carrying word to Wayford has to
funnel through it, and three goblins holding the clearing on the far side
outnumber whatever gets through one at a time.

- **The road-side clearing** (south, around `player_start`): where the
  player lands, and where the terminal exit sits right next to
  `player_start` - reachable the instant the ambush starts, no walking
  required to flee. Open ground, nothing else here; this is "still safe,"
  the moment before the choke.
- **The narrows** (the single-tile gap in the felled-log wall, row 6):
  the entire mechanical point of this map. `docs/content_design_process.md`
  §2 is explicit that a first multi-monster fight needs a chokepoint so the
  player doesn't get surrounded - this *is* that chokepoint, made
  diegetic (felled trees, not a game-y invisible wall) rather than just a
  corridor shape for its own sake.
- **The goblin clearing** (north): where all 3 `goblin` spawns (hp
  12/atk 4/def 1, unmodified - no reason to reinvent the stat block for a
  first appearance) wait, spread across the clearing rather than clustered
  on the gap - so even a goblin that hears the player coming has to cross
  open ground to reach the narrows, giving the player at most one, maybe
  two attackers at the choke itself rather than three at once. Per the
  balance math (`docs/content_design_process.md` §2): the player kills one
  goblin in 3 hits (`5 - 1 = 4` dmg/hit, `12 / 4 = 3`) and takes 3 dmg/hit
  taken (`4 - 1 = 3`) - a real fight at the choke, not a formality, but
  never a 3-on-1 pile-on if the player holds the gap rather than pushing
  into the clearing.

## Terrain

Outdoor (`plains` + `wall`, no dungeon `floor`/interior) - same tile
vocabulary Millhaven/Wayford already established is valid on any dungeon
level, not exclusive to settlements (`docs/content_design_process.md` §0c).
The felled-log "wall" tiles get a `description` override rather than
reading as a generic dungeon wall in look mode.

## Explicitly out of scope

- No loot, no reward item - the point is the fight and the road continuing
  safely, not treasure. `spreading_the_warning` itself stays reward-less,
  unchanged.
- No second level, no `stairs_down` - `requires_stairs_down: false`, same
  shape as a settlement (one level, one terminal exit), even though this
  isn't peaceful.
- No overworld `dungeon_entrance` tile anywhere targets this dungeon -
  deliberate; it's only reachable through the `EncounterDef` trigger.
