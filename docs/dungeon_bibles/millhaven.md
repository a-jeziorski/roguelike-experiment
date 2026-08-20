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
*only* faction that ever gets the peaceful `villager` AI," per
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

One level, same as before this pass - Millhaven doesn't need multiple
floors or branching paths to earn its depth, just NPCs worth stopping
for:

| Level | Name | Set pieces it holds |
|---|---|---|
| `level_01` | Millhaven Green | The Gate-watch, The Well, The Mending Yard, The Chief's Doorstep |

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
infrastructure, still working.

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

A second `landmark` tile - tools laid out, nothing fancy, the closest
thing Millhaven has to a shop. This villager is the *one* allowed
slightly more informative dialogue in the whole roster.

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

*Dialogue*: *"Can't talk. This bread won't watch itself."*

*Why it's here*: per the brief - most villagers should be able to
simply greet, dismiss, or make small talk, and a town where everyone
stops what they're doing to chat with a stranger stops feeling like a
real place.

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

Not a hidden office - the chief stands right on the town's main road,
where their small house narrows the street on both sides. Visible,
central, unavoidable if you walk the green end to end. This is where
`Talk` completes the starting quest.

*Dialogue* (triggers completion): *"So you made it after all. I was
starting to think that warning was never coming - let's hear it, all
of it."*

*Why it's positioned this way*: the chief isn't hidden behind a
formality (a locked door, a waiting room) - Settlers don't have that
kind of authority structure left, or want it. Being reachable *is* the
job. The message itself is spoken, not written (`engine/quest.py`'s own
framing: word of a goblin horde migrating into the region, carried by
the player, "no letter, no proof") - deliberately verbal from the start,
so `Talk` completing it is the natural mechanism rather than a
retrofit. An earlier draft of this quest had the player carrying a
*sealed* letter that was somehow lost during capture, then "delivering"
it by talking - a real inconsistency (see this document's Tone notes
below) fixed by making the message verbal from the start.

## Roster (unchanged constraint: no new AI, no combat)

Six `villager`-AI entities total (five plain `villager` spawns, each
with its own per-spawn `dialogue`, plus one `village_chief` spawn) -
a modest increase from the original five, not a jump to Wayford's
scale. No monsters, no items beyond what already existed, no new
mechanics - every villager still just wanders at full health and flees
permanently the instant they're hurt, same as everywhere else in the
game. The `village_chief` catalog entry is mechanically identical to
`villager` (same hp/attack/defense/AI) - the only difference is
identity (glyph, name, per-spawn dialogue), matching the user's own
framing: "marked with a special symbol," not a different kind of
creature.

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
  that instinct belongs to Stonebridge, not here.
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
