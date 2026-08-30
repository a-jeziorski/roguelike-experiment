# Millhaven — Dungeon Bible

*A design document for one location, written the way a GM would key a
site for a tabletop session: what's actually here, why, and what the
player is meant to feel room to room. See `docs/world_history.md` for
the realm-level facts this location has to agree with, and
`docs/content_design_process.md` for the mechanical authoring rules
(the three story surfaces, the `landmark` tile kind). This document is
the missing middle layer between those two - the specific story of
*this* place, decided before any ASCII is drawn.*

## The pitch

Millhaven is the plainest kind of good news this world has left: a
handful of people who decided, on their own, to stay put and keep a
green mowed instead of scattering or squatting in whatever the Kingdom
left behind. It isn't defended by a wall that means anything, isn't
sitting on top of anything old or dangerous, isn't waiting for anyone.
It's just a town, doing the ordinary work of being a town - a well
that gets used, a yard where things get mended instead of replaced,
someone whose word still carries enough weight that people fetch them
when a stranger shows up at the gate. Wayford's own description already
calls Millhaven "one quiet green behind a low wall" - the smaller,
earlier-stage version of the same project. This pass doesn't outgrow
that; it just proves the green has people in it worth stopping for.

**Placement on the world bible**: pure Long Quiet, pure Settlers - "the
*only* faction that ever gets a peaceful-by-default AI type (`villager`,
who never fights back at all; `town_guard`, who will if provoked)," per
`world_history.md`. No Old Kingdom ruin under it, no Elder Age anything
nearby, no faction tension at its gate (that's Stonebridge's job).
Millhaven's whole point is being the *unremarkable* success story -
proof the Long Quiet isn't only garrisons gone feral and bandits in
watchtowers, it's also just people, managing.

## Mood

Ordinary and a little tired, not grim. Nobody here is in danger and
nobody's pretending otherwise - the tension this pass adds is entirely
narrative and off to one side (the player's own unfinished errand),
never environmental. Most conversations should cost the player nothing
and reveal nothing; one or two should reward paying attention without
ever turning into a briefing.

## Structure overview

Still one level - Millhaven doesn't need multiple floors or branching
paths to earn its depth, just room to breathe. This is the green's
second regeneration: 22x15 to 44x46 gave the Chief and Shopkeeper their
first real houses; this pass regenerates it again, larger still
(60x60), because two more residents were always overdue for the same
treatment. `millhaven_trainer` (Old Drillmaster) and `millhaven_debtor`
have been `stationary: true` since they were first authored - the same
"always findable in one exact spot" premise the Chief's and
Shopkeeper's houses were built to answer - but stood in the open on
bare plains the whole time, a gap that only became obvious once
decorations made every *other* building's interior feel lived-in by
comparison. This pass closes it: four real building interiors now, one
per stationary resident, plus room for outdoor decoration to actually
read as composed - a tended garden, a treeline, doorstep landscaping -
rather than whatever happened to fit on the nearest open plains tile.
Nothing about the town's identity changes - same gate, same well, same
cast, same errand - only its scale, its building count, and how
deliberately its dressing reads.

**A decoration philosophy**, stated plainly since it wasn't followed
carefully enough the first time: an outdoor decoration is never placed
alone. It belongs to something - a garden bed someone actually tends, a
treeline breaking the wind along one wall, bushes landscaping a
building's own doorstep - and it says something about whoever it's
near. The Chief's doorstep gets bushes; the Debtor's doesn't, on
purpose (see set piece 10) - a garden nobody's kept up is a truer tell
than another line of dialogue about owing coin. A `fence` marks
something it's actually fencing (a garden edge, the guard's post),
never sitting by itself in open plains. If a placement can't say which
of these it belongs to, it doesn't go in.

A handful of purely decorative, unentered wall clusters (matching
Wayford's own "several distinct clusters of houses and storehouses")
are scattered through the residential stretches so the larger footprint
reads as a real town, not a big empty field with dots in it - six now
(three symmetric pairs, up from two), pure scenery, no new mechanics,
same technique already shipped in Wayford.

The gate itself also gets its own icon this pass - previously the same
shared staircase sprite every `stairs_up` tile in the game uses (a cave
fissure in Silver Mountain Caves looked identical to Millhaven's town
gate). A small new per-coordinate sprite-override mechanism
(`LegendEntry.tile_sprite`, `data/sprites.yaml`'s `tile_sprite_overrides`
section) lets this one placement use an actual gate/archway icon without
touching any other dungeon's stairways.

**A third pass, one revision later**: the second regeneration fixed
*placement* (nothing scattered, everything composed) but not *coverage*
- 60x60 of green with only a handful of clusters in it still reads
mostly empty. The fix isn't to make Millhaven less ordinary; it's to
make its ordinariness more specific. A small burying ground (set piece
12), a tilled plot that gives the dismissive villager's own line
something to stand next to (set piece 4), and a practice range behind
the Trainer's hall (set piece 9) are all exactly as unremarkable as
everything else here - that's what keeps them in tone, not what makes
them worth skipping. The well, the notice board, and the mending yard
also drop the one shared `landmark` sprite every point of interest in
the game uses and get their own icon each, the same `tile_sprite`
mechanism the gate uses above - a landmark is supposed to read as
distinct from ordinary ground; sharing one glyph across three of them
undercut that.

| Level | Name | Set pieces it holds |
|---|---|---|
| `level_01` | Millhaven Green | The Gate-watch, The Well, The Mending Yard, A dismissive villager, A nudge villager, The Chief's Doorstep, The Escaped Prisoner, The Shopkeeper, The Trainer's Drill Hall, The Debtor's House, The Town Guard, The Burying Ground |

## The named set pieces

### 1. The Gate-watch

Just inside the gate, close enough to the road to notice who comes
through it. Not a guard post - Millhaven doesn't have those - just
someone who happens to end up near the gate often enough that they're
the town's de facto first impression.

*Dialogue*: *"Don't get many strangers through that gate. Mind you're
not still on the road come dark."*

*Why it's first*: sets the tone immediately - wary in the mildest
possible way, no threat implied, just an ordinary person noticing an
unordinary thing (a stranger) and saying so plainly.

### 2. The Well

A `landmark` tile (matching Stonebridge's well precedent) with a
villager posted beside it - the town's actual, unglamorous
infrastructure, still working. The new communal garden patch (see the
decoration philosophy above) sits near enough to the well to read as
the same "someone still tends this" idiom, without crowding the
landmark itself.

*Landmark description*: *"The town well, its rope re-tied more times
than anyone remembers whose turn it was to fix it."*

*Dialogue*: *"Well's held up better than most things built before the
Sundering. Can't say the same for my back, hauling from it every
morning."*

*Why it's here*: the one place a Sundering-era detail gets worked in
naturally, through an ordinary complaint about a bad back rather than
a history lesson - exactly the kind of throwaway grounding the world
bible's voice model calls for.

### 3. The Mending Yard

A second `landmark` tile - tools laid out, nothing fancy. An informal
exchange of favors and borrowed tools, not a transaction - nobody's
charging, nobody's paying. The shop sits nearby (see set piece 8), and
the two are meant to coexist rather than compete: the Mending Yard is
what people still do for each other without coin changing hands; the
shop is the one place coin still works at all. This villager is the
*one plain villager* allowed slightly more informative dialogue.

*Landmark description*: *"A mending yard - a cobbler's last, a
whetstone, tools laid out for whoever needs them next. Nobody's
charging for the use, not anymore."*

*Dialogue*: *"Trade's thinner than it used to be. A cart came through
most weeks, once. Now we make do with what's already here."*

*Why it's the informative one*: still one line, still concrete (a cart,
a schedule that used to exist), and it's about *Millhaven's* situation
specifically, not a recitation of realm history - the difference
between texture and infodump.

### 4. A dismissive villager

Mid-chore, wants to be left to it. Not rude, just unavailable - the
explicit reminder that not every NPC owes the player their attention.
A tilled plot sits right beside her as of this pass - not a new set
piece of its own, just the reason "this bread won't watch itself" was
ever true to begin with, made visible instead of only stated.

*Dialogue*: *"Can't talk. This bread won't watch itself."*

*Why it's here*: per the brief - most villagers should be able to
simply greet, dismiss, or make small talk, and a town where everyone
stops what they're doing to chat with a stranger stops feeling like a
real place. The plot beside her is the same instinct applied to scenery
- a line only costs the player nothing to skip if it was never asking
to be taken on faith in the first place.

### 5. A nudge villager

Ordinary small talk, but the one line doing double duty: pointing the
player toward the chief without the game needing a quest marker or
waypoint system to do it.

*Dialogue*: *"Chief's been asking after any travelers. You'd best go
say hello."*

*Why it's here*: keeps the quest discoverable through the same
mechanism as everything else in this game - a line of text, not a UI
element - consistent with "there's no separate lore/dialogue system"
from `content_design_process.md`.

### 6. The Chief's Doorstep

A real one-room house, positioned so the "doorstep" framing still
holds: right at the green's center, beside the well, door facing the
road - impossible to miss walking the green end to end. Not a hidden
office behind a formality (a locked door, a waiting room) - Settlers
don't have that kind of authority structure left, or want one. Four
walls change where the chief stands, not how reachable they are. This
is where `Talk` completes the starting quest. Furnished plainly - a
hearth, a table, a shelf, a chair or two - a room someone actually
receives visitors in, not a monument to the office.

The doorstep also carries an actual `landmark` tile (the notice board),
one tile outside the doorway - the same "ordinary communal fixture"
idiom as the Well/Mending Yard (set pieces 2/3), *not* a quest marker
or waypoint icon. It doesn't replace the nudge villager's spoken hint
(set piece 5) as the primary way a player learns to look for the chief
- it's a second, redundant cue for a player who's exploring on foot
rather than talking to everyone.

*Dialogue* (triggers completion): *"So you made it after all. I was
starting to think that warning was never coming - let's hear it, all
of it."*

*Why it's positioned this way*: being reachable *is* the job, house or
no house - see the Roster section for why the chief now holds that one
spot (`stationary`) instead of wandering off it. The message itself is
spoken, not written (`data/quests.yaml`'s own framing: word of a goblin
horde migrating into the region, carried by the player, "no letter, no
proof") - deliberately verbal from the start, so `Talk` completing it
is the natural mechanism rather than a retrofit. An earlier draft of
this quest had the player carrying a *sealed* letter that was somehow
lost during capture, then "delivering" it by talking - a real
inconsistency (see this document's Tone notes below) fixed by making
the message verbal from the start.

*Follow-up quest*: once `goblin_warning` is completed, the Chief has a
second ask (`spreading_the_warning`, `data/quests.yaml`) - carry the
same warning on to Wayford, gated on the first quest via
`requires_quest_id` so it's only ever offered after the player has
actually delivered here. Same verbal framing, no letter this time
either. Granting it needs a Talk *after* the one that completes
`goblin_warning` (`QuestLog.check_questgiver` runs before
`QuestLog.check_talked_to` within one Talk, so a quest can't chain into
its own follow-up in the same turn it completes) - the Chief's spoken
line on that first return visit is still `goblin_warning`'s own
`target_done_dialogue` ("The warning's out now..."), with the new
quest's `given_message` following as a second, separate log line right
after it.

### 7. The Escaped Prisoner

Tucked into the green's southern stretch, off to one side rather than
astride the main road - unlike the Chief, this NPC doesn't need to be
unavoidable, since the quest they offer is a sidequest, not the thing
the player came to Millhaven for.

*Dialogue*: *"Made it out of that tower same as you, more or less.
Warden ever come looking for me, or is he still up there thinking he
runs the place?"*

*Why it's here*: the first questgiver in the game - talking to them
grants "An Old Debt" (kill the Warden of Prison Tower), no deadline.
Deliberately paired with the player's own escape: this NPC made the
same trip through Prison Tower, so the premise passes the same
knowledge-provenance check the Chief's quest does (see the Tone note
below) - they're asking a favor of someone they know shares the
context, not reporting something they were never present for. If the
Warden already died during the player's own escape, talking to this
NPC completes the quest immediately instead of granting it, and says
so explicitly rather than pretending the favor is still owed.

### 8. The Shopkeeper

Has a real house of their own, built right beside the Mending Yard with
its door facing that landmark directly - walk from one to the other in
a couple of steps, keeping the two set pieces literally as well as
narratively "read together" (see set piece 3). Furnished like an actual
place of business, not a home: two chests of stock behind the counter,
a table serving as the counter itself, one chair for whoever's waiting
on a slow day - no bed here. If the shopkeeper sleeps elsewhere, that's
someone else's business, not this one's to explain. Doesn't sell much:
one Healing Potion, priced at what coin is actually still worth here -
25 gold is a real ask, not a formality, given how little of it exists
to find.

*Dialogue*: *"Coin still spends here, same as it always did. Rare
enough these days that I don't ask where it came from."*

*Why it's here*: this is the payoff the gold system was built toward -
the first, and so far only, place in the game any collected gold
becomes useful again. Ties directly into the framing established in
`docs/dungeon_bibles/prison_tower.md`'s "Why there's gold here at all":
every gold placement so far has been inert, already-possessed coin
nobody's spent in a generation. This is where that changes, in one
specific and modest way - not a return of a functioning economy, just
one person still willing to trade.

The shopkeeper is also this game's second questgiver, offering "A
Standing Request": a Pale Fungus that only grows in the Sunken Mine's
Flooded Sump (see `docs/dungeon_bibles/sunken_mine.md`'s set piece 3).
Proof of concept for a fourth quest-completion shape - delivering a
specific item back to whoever asked for it, rather than talking,
killing, or arriving somewhere - and a second reward shape: not another
item, but a permanent 20% discount on everything in this shop (Healing
Potion 25 -> 20 gold).

Fetching it is deliberately two steps, not one. Picking up the fungus
in the mine is an entirely ordinary pickup - it goes into inventory
like anything else, no special handling at all. The quest only
completes back here, talking to the shopkeeper *while still carrying
it* - which is what removes it from inventory and grants the discount.
Splitting the fetch from the delivery this way is the whole point: it
leaves room for the delivery to be interrupted before it happens - a
deadline expiring on the way back, the item being lost some other way
- neither of which exists on this quest yet, but the two-step shape is
what would make either possible without redesigning it later. No
retroactive "already had it" detection, unlike the Warden's kill-quest
- picking up the fungus before this quest is even granted just leaves
it sitting in inventory as an inert curio, a deliberately unhandled
edge case rather than one this pass needed to solve.

### 9. The Trainer's Drill Hall

A one-room hall - table, chair, a shelf of old drill records - not
fancy, just functional, matching a man who spent his working life
running other people through the same routines until they stuck.
`millhaven_trainer` (catalog id; "Old Drillmaster" on screen) has been
`stationary: true` since the perk-training system shipped, the same
"always findable here" premise the Chief's and Shopkeeper's houses
exist to answer - it just never got a building to match. This pass
gives it one.

*Dialogue*: *"Killing things and surviving quests teaches a body
plenty, if it's paying attention. I can put what you've picked up to
better use than instinct alone would."*

*Why it's here*: no quest ties to this NPC at all - purely a
gameplay-mechanic resident (teaches perks via `data/entities.yaml`'s
`trainer_perks`), so the hall exists to answer "where would a retired
drillmaster actually be," not to gate anything. Deliberately spare - a
working room, not a monument to a career that's mostly over. (A
weapon-rack decoration was considered and rejected - the only available
sprite is wall-mounted art with an opaque background, wrong for this
project's floor-standing decoration model. The room's plainness carries
the idea instead.)

A short practice range sits behind the hall as of this pass - a few
standing targets and a low fence marking the firing line, nothing more
built-out than that. "Used to drill Kingdom levies" reads differently
once there's somewhere on the green that shows it rather than just
saying it.

### 10. The Debtor's House

The smallest, plainest interior in town, on purpose: a bed and a single
chair, nothing else - no hearth, no shelf, no landscaping outside the
door (see the decoration philosophy above). `millhaven_debtor` has also
been `stationary: true` since it was authored, and is the intimidate-
target of Wayford's `a_debt_worth_collecting` - the debtor needs to
stay findable and alive, not necessarily comfortable. Tucked off to the
side of the green, away from the well and the road's main traffic, the
way someone avoiding a conversation about money would actually place
themselves.

*Dialogue*: *"I know what I owe, and I know who to. Tell them I'm good
for it - just not yet."*

*Why it's here*: the bare interior is doing narrative work the
dialogue alone doesn't - "hoping the debt would be forgotten" reads
very differently once the player can see the room it's happening in.

### 11. The Town Guard

Stands near the gate and the main road running down from it toward the
well - not tucked into a doorway or off to one side, just planted
where it's visible from most of the green. Doesn't look for trouble,
doesn't need to: Millhaven hasn't had any. A short fence marks the post
without enclosing it - it's a watch spot, not a building.

*Dialogue*: *"Keep the peace and we've got no trouble between us."*

*Why it's here*: the first `AI_TOWN_GUARD` in the game - peaceful by
default like every other villager on this green, but not mechanically
identical to one. Attack anyone peaceful anywhere on the green -
another villager, or the guard directly - and the guard turns hostile
for good, for the rest of that visit. The line above is doing double
duty: ordinary small talk on a first read, a plain statement of the
mechanic on a second one. Placed centrally and visibly on purpose - a
deterrent works by being seen, not discovered by accident in a corner.

### 12. The Burying Ground

A small, quiet cluster of grave markers tucked into a corner of the
green, away from the road and the well's own traffic. No names, no
epitaphs - consistent with the rest of this town, nobody here has an
invented name to carve. People die of age and hard winters in the Long
Quiet, same as anywhere; Millhaven having a place for that is exactly
as unremarkable as everything else about it, not a reason to feel
uneasy about the town.

*Why it's here*: the clearest example of this pass's whole point - a
concrete detail doesn't have to be dramatic to be worth naming. A
burying ground is about as ordinary as a settlement gets, and naming it
plainly is what keeps it in Millhaven's register rather than nudging
toward Stonebridge's.

## Roster

Fourteen peaceful-by-default entities total on this green: thirteen
`villager`-AI (eight plain `villager` spawns each with its own
per-spawn `dialogue`, one `village_chief` spawn, one `escaped_prisoner`
spawn, one `shopkeeper` spawn, one `millhaven_trainer` spawn, and one
`millhaven_debtor` spawn) plus one `town_guard`-AI (`AI_TOWN_GUARD`, a
distinct AI type from `villager` - see set piece 11). Three of the
eight plain villagers are new this pass, added for the larger footprint
- matching Wayford's own lesson that a bigger town needs more than its
old cast to avoid reading as thinner, not richer. Each has its own
unique dialogue (one near the new garden patch, one along the
treeline, one general presence in the green's southern stretch),
keeping the whole roster at 100% unique villager lines - comfortably
clear of `content_design_process.md` §1's 75% floor.

No combat *unless the player starts it*: every `villager`-AI entity
here still wanders at full health and flees permanently the instant
it's personally hurt, same as everywhere else in the game, and the
`town_guard` wanders too until the player attacks any peaceful NPC on
this map, at which point it fights back permanently for that visit.
Five mechanics beyond plain dialogue live on this roster: the
questgiver (a quest that starts hidden until granted via `Talk` -
`escaped_prisoner` uses this for a kill-quest, `shopkeeper` uses the
same mechanism for a fetch-quest, see set piece 8), the shopkeeper's
buy screen (a nested UI, opened with a separate key while adjacent,
entirely independent of `Talk` - talking to the shopkeeper gets
ordinary dialogue like any other villager), the shopkeeper's permanent
discount pricing (unlocked by completing "A Standing Request" -
`Engine.shop_price` reads this off the quest log live, so every future
visit to the shop reflects it automatically), the town guard's
map-wide hostility trigger (see set piece 11 - this is the one entity
on this roster that is *not* mechanically identical to `villager`,
since "identity, not a different kind of creature" only holds for NPCs
that share `villager`'s actual behavior, and this one deliberately
doesn't), and `stationary` (`village_chief`/`shopkeeper`/
`millhaven_trainer`/`millhaven_debtor` only): holds position instead of
wandering while undamaged, still flees normally once hurt. Used for
exactly these four and no one else, on purpose - they're the only four
NPCs whose whole premise depends on being findable in one specific spot
(now a specific *room*, for all four) every time, where every plain
villager and the escaped prisoner are fine wandering their own patch
of green.

## Tone notes for anyone (agent or human) revising this later

- No proper names. Nothing in this project has an invented personal
  name yet (guards, the warden, all titles) - Millhaven's villagers and
  chief stay nameless too. Individuality comes from what they say, not
  a name tag.
- Most lines should cost the player nothing to skip. If every villager
  in this file feels essential to read, that's a sign the roster has
  drifted from "greet, dismiss, small talk" toward infodump - the
  Mending Yard villager is deliberately the *only* one with anything
  resembling information content.
- Keep the tension entirely in the player's own errand, never in the
  town itself. Millhaven should never need a reason to feel uneasy -
  that instinct belongs to Stonebridge, not here. A bigger footprint is
  not license to converge toward Wayford's more established tone -
  Wayford's own bible calls that contrast (Millhaven humbler, "just
  getting by," even at a larger size) deliberate.
- **A quest's premise has to actually grant the player character access
  to whatever they're meant to convey.** The original version of this
  quest had the player carrying a *sealed letter* - meaning, by
  definition, they were never privy to its contents - that was then lost
  during capture, but completed by having them tell the chief what it
  said. Two compounding errors, not one: no object left to hand over,
  and no way to have known the contents even with the letter still in
  hand. This isn't a rule about `Talk` specifically - a delivery quest
  handing over an intact sealed letter via `Talk` would be entirely
  fine. The actual check: does the player character canonically *know*
  or *possess* what the quest has them convey? Sealed/written means
  carried unopened, handed over intact, never narrated; spoken or
  witnessed directly means they genuinely know it and can convey it
  however the fiction calls for. Applies beyond Millhaven - run this
  check whenever a quest's premise and its completion beat are being
  written together, not just at the "does this line sound right" stage.
