# The Wayford Arc — Quest Bible

*A design document for one connected group of quests, written the way
`docs/dungeon_bibles/` documents key a single site - except this one's
site is the connective tissue between three locations, not a room. Read
`docs/world_history.md` for the realm-level facts this arc has to agree
with and `docs/content_design_process.md` for the mechanical rules. This
document is the contract that Wayford's and Broken Watch's own dungeon
bibles (written next, informed by this one) both have to honor - every
shared catalog id either of them needs is named here first, so neither
bible invents its half of a connection independently.*

## The pitch

Millhaven holds its ground. Wayford wants more than that. It's the
largest Settler town, sitting on a real crossroads - "three or four old
Kingdom roads still meet" there already, per its own `dungeon.yaml`. This
arc is Wayford trying to make that literally true again: not just
surviving at a crossroads, but *acting* like one - chasing the safety,
the records, and the contact needed to actually use the roads it sits on.
Three questgivers, three different facets of that one ambition:

- **Security** - the roads aren't safe to use if something's raiding them.
- **Record-keeping** - the roads aren't useful if nobody remembers where
  they go.
- **Contact** - the roads aren't a network if the far end never hears
  from you.

None of this is heroic in a chosen-one sense. It's the same "ordinary
institutional appetite" `world_history.md` already assigns the Old
Kingdom, now inherited by a town trying to rebuild the function, not the
uniform. Keep every quest's tone practical and municipal, not epic.

**Placement on the world bible**: purely Long Quiet-era, Settler-faction
work - no new eras, no new factions. The arc's only work is connective:
Wayford (Settlers) reaching toward Broken Watch (Opportunists, already
established as "practical, not evil, just taking what an empty garrison
offers" - keep that framing; the bandits are an obstacle, not villains)
and toward Millhaven (Settlers).

## The three questgivers (new Wayford entities)

All three: `ai: villager`, `stationary: true` (matches `escaped_prisoner`/
`village_chief`/`shopkeeper`'s existing precedent for a questgiver who
needs to be findable in one specific spot every time), placed in Wayford's
rebuilt level_01 per its own bible (written next). Titles, not personal
names - matches every existing named NPC in the game (`Warden`, `Village
Chief`, `Escaped Prisoner`, `Shopkeeper`).

| Catalog id | Title | Facet | Gives |
|---|---|---|---|
| `wayford_road_warden` | Road Warden | Security | kill quest |
| `wayford_clerk` | Town Clerk | Record-keeping | fetch quest |
| `wayford_caravan_master` | Caravan Master | Contact | dungeon-arrival quest |

## The three quests

### 1. Clearing the Watch Road (kill, Wayford → Broken Watch)

- **Questgiver**: `wayford_road_warden`.
- **Trigger**: `target_kill_entity_id: bandit_captain`.
- **Premise**: raids on the road west have a leader, not just numbers -
  the Road Warden wants that leadership gone, not every bandit at Broken
  Watch (an achievable, practical goal, not "clear the dungeon").
- **Reward**: `reward_item_id` - a solid reward-tier item (exact pick at
  authoring time; a weapon or armor upgrade fits "you did real,
  dangerous work" better than a potion). No shop-discount reward here -
  see the note below.
- **Constraint on Broken Watch's bible**: `bandit_captain` is the kill
  target, reusing the existing catalog entity exactly the way
  `kill_the_warden` reuses `warden` rather than minting a near-duplicate.
  This only works correctly (per `QuestLog.killed_entity_ids`'
  documented constraint) if `bandit_captain` keeps spawning **exactly
  once in the whole game** - confirmed true today (one spawn, in
  `level_03`, "The Captain's Watch") and must stay true when Broken
  Watch's level is rebuilt. Whoever revises Broken Watch: the captain's
  spawn is load-bearing for this quest, not just a stat block - keep it
  as the single, climactic encounter that room's name already implies.

### 2. A Record Worth Keeping (fetch, Broken Watch → Wayford)

- **Questgiver**: `wayford_clerk`.
- **Trigger**: `target_item_id: road_ledger` (new item, no `ItemEffect`
  fields - a pure quest item, mirrors `pale_fungus` exactly).
- **Premise**: an old route ledger from the garrison's own records -
  which roads and waystations the Kingdom actually maintained. The
  bandits never valued it; it's just been sitting wherever the garrison's
  paperwork ended up. This is why it should be placed in an *early or
  mid* room of the rebuilt Broken Watch (the Outer Yard or the Barracks),
  not guarded by the captain - contrast with quest 1's climactic target,
  and matches this arc's "administrative debris nobody cared about" tone
  (the same aesthetic `sunken_mine.md` already established for Old
  Kingdom institutional decay).
- **Reward**: `reward_gold_amount: 30`, not `reward_shop_discount_pct` -
  deliberately (see the shop-discount note below for why). Originally
  shipped as `reward_item_id: hunting_bow`; changed to gold once the user
  asked for a proper gold-reward mechanism (`reward_gold_amount`, added
  to `QuestDef`/`Quest`/`Engine.complete_quest`) - a cleaner fit for a
  quest whose questgiver's own dialogue was already building toward a
  monetary-worth punchline ("worth more... and I mean that literally").
- **Constraint on Broken Watch's bible**: needs one room-appropriate
  placement for `road_ledger`, described as found/discarded rather than
  guarded or displayed.

### 3. Word Down the Road (dungeon arrival, Wayford → Millhaven)

- **Questgiver**: `wayford_caravan_master`.
- **Trigger**: `target_dungeon_id: millhaven` - this trigger shape has
  never been used by real shipped content before (only exercised in
  tests); this is its first real outing. **Update after the user's own
  follow-up request**: dungeon-arrival quests are now two-step, matching
  the kill and fetch triggers exactly - arriving at Millhaven only
  records the visit (`QuestLog.record_dungeon_arrival`); the quest only
  completes once the player reports back to the Caravan Master
  (`QuestLog.check_dungeon_report`). This wasn't the original design (see
  the note this replaces, below) but is the more consistent one, and the
  one actually shipped.
- **Premise**: the Caravan Master wants proof the road to Millhaven is
  still passable before committing an actual caravan to it - the trip
  itself doesn't need a fetch or a fight, but telling the Caravan Master
  about it in person does still require coming back to Wayford. This
  quest requires **zero changes to Millhaven's own content** - the
  target is the dungeon itself, not anything inside it.
  `completion_message` should land on "the road holds" / "safe passage
  confirmed," not anything about what's inside Millhaven.
- **Reward**: none - matches `goblin_warning`'s existing "no mechanical
  reward, just narrative closure" shape. This quest is about Wayford's
  ambition paying off in premise, not in loot.

*(Superseded design note, kept for context rather than deleted: the
original version of this quest completed the instant the player arrived
at Millhaven, with no return trip - deliberately, on the reasoning that
"arriving is the proof, nothing to report." The user later asked for the
return-trip requirement anyway, for consistency with the kill and fetch
quests, and it shipped as described above.)*

## Formerly a known quirk, now fixed: shop discounts are per-shop

`Engine.shop_price` used to apply `QuestLog.shop_discount_pct()` - the
single largest discount from any completed discount-granting quest - to
**every** shop in the game, not just the one tied to the quest that
unlocked it. That was fine when Millhaven's was the only shop in
existence; it stopped being fine the moment Wayford's shop existed too,
since completing either town's discount quest would then quietly
discount the *other* town's shop as well. This arc originally avoided
stepping on the bug rather than fixing it (neither new quest here grants
`reward_shop_discount_pct` - see quest 2's Reward note above), but the
user later asked for the underlying mechanism fixed directly.

**Fix, as shipped**: `reward_shop_discount_pct` now always pairs with a
new field, `reward_shop_discount_entity_id` - the catalog entity id of
the one shopkeeper the discount applies to (validated by `load_quests`:
must exist, must have a non-empty `shop_inventory`). `QuestLog.
shop_discount_pct` takes that entity id as a parameter and only counts a
completed quest's discount if it's scoped to that same shopkeeper;
`Engine.shop_price` now takes the adjacent `shopkeeper` entity as a
parameter so it can key the lookup correctly. `fetch_fungus` (Millhaven's
only discount quest) was updated with `reward_shop_discount_entity_id:
shopkeeper`, so its behavior is unchanged in practice - the fix only
matters once a second shop exists to leak into, which Wayford's
`wayford_provisioner` now does. If a future quest ever wants to discount
Wayford's shop instead, it sets `reward_shop_discount_entity_id:
wayford_provisioner` and the two stay independent.

## Wayford's own cast (not part of the quest arc, but decided here so
## the shared-catalog-id ledger below is complete)

Per the user's ask ("talkable NPCs, Guards and a Shopkeeper with his own
inventory"), Wayford's bible (written next) also needs:

- **`wayford_provisioner`** - Wayford's shopkeeper. Deliberately not
  named "Shopkeeper" (that id is Millhaven's, and reusing it would be a
  real bug, not just a flavor collision - see the id-collision warning
  below) - "Provisioner" reads as a bigger, more established operation
  than Millhaven's one-room shop, matching Wayford's size.
  `shop_inventory` broader than Millhaven's single-item stock; exact
  list decided at authoring time.
- **One or two `town_guard`-AI spawns**, reusing the existing
  `town_guard` catalog entity (id already shared/generic, unlike the
  three questgivers above, since no quest ever targets it by id - safe
  to reuse). Its current `description` ("Keeps the peace on Millhaven's
  green...") is Millhaven-specific text on a now-shared catalog entry -
  needs a one-line genericization pass (drop the place name) before
  Wayford's bible spawns it, so look-mode reads correctly in both towns.
  Per-spawn `dialogue` overrides can still give each town's guard(s)
  their own line without touching the shared catalog default.
- **Several named, dialogued villagers** replacing the current 14
  anonymous `{entity: villager}` spawns - exact count and named set
  pieces are Wayford's bible's job, not this document's.

## Shared catalog id ledger (the actual contract)

Every id either dungeon bible must honor. New entries in **bold**.

| Id | Kind | Lives in | Notes |
|---|---|---|---|
| **`wayford_road_warden`** | entity | Wayford | questgiver, quest 1; also, from outside this arc, the Talk-completion target of `spreading_the_warning` (`data/quests.yaml`) - the Village Chief's Millhaven-originated goblin-warning chain, added in a later pass. Not this arc's content, but touches this arc's NPC, so noted here to keep this ledger an accurate map of everything that reaches him. |
| **`wayford_clerk`** | entity | Wayford | questgiver, quest 2 |
| **`wayford_caravan_master`** | entity | Wayford | questgiver, quest 3 |
| **`wayford_provisioner`** | entity | Wayford | shopkeeper, not part of the arc |
| **`road_ledger`** | item | Broken Watch (placed) / Wayford (delivered) | fetch target, quest 2 |
| `bandit_captain` | entity | Broken Watch | **existing** - kill target, quest 1; must stay single-spawn |
| `town_guard` | entity | Wayford (reused) | **existing** - description needs genericizing |
| `millhaven` | dungeon | - | arrival target, quest 3; no content changes needed |

## Explicitly out of scope this pass

- Stonebridge (mentioned only as flavor/geography - "the road toward
  Broken Watch/Stonebridge" - not touched, not required to exist for
  any trigger).
- Sunken Mine (the user offered it as an alternative to Millhaven for
  quest 3; Millhaven was chosen since it has NPCs to make "the road
  holds" land as a real place, not an empty ruin - see quest 3's premise).
- Per-shopkeeper shop discounts - originally out of scope, see the note
  above; shipped as a follow-up once the user asked for the underlying
  global-discount bug fixed directly. (Gold rewards were a similar
  originally-out-of-scope-then-shipped-as-a-follow-up case - see quest
  2's updated Reward note.)
- Any change to `bandit`/`bandit_captain` stats/balance - reused as-is.
