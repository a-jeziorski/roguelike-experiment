"""Quest tracking: this module owns the *mechanics* of a quest - the four
trigger shapes a quest can complete via (dungeon arrival, Talk, killing a
specific catalog entity, delivering a specific catalog item to its
questgiver) and what each one actually checks - not any one quest's specific
content. The quests themselves (names, flavor text, deadlines, which
NPC/item/dungeon each targets, rewards) are authored in data/quests.yaml,
validated as QuestDef (content/schema.py) by content/loader.py's
load_quests, and turned into live Quest/QuestLog state by this module's own
quest_from_def/create_quest_log - the same "content/schema.py defines the
raw shape, engine/ converts it to runtime state" split already used for
monsters (EntityDef -> Entity) and items (ItemDef -> item Entity).

Not a scripting engine - quests complete via four hardcoded trigger shapes
(dungeon arrival, Talk, killing a specific catalog entity, delivering a
specific catalog item to its questgiver) that Engine/main.py call into (see
Engine.on_entity_death, Engine.talk_to_adjacent, main.py's
resolve_transition), and fail via one (clock deadline, see
Engine._check_quest_deadlines). Three reward shapes exist, not mutually
exclusive: granting an item straight into inventory (reward_item_id),
gold straight into the player's gold stat (reward_gold_amount), and a
permanent discount at one specific shop (reward_shop_discount_pct, scoped
by reward_shop_discount_entity_id - see QuestLog.shop_discount_pct) - see
Engine.complete_quest.

Three of the four trigger shapes - fetch (target_item_id), kill
(target_kill_entity_id), and dungeon arrival (target_dungeon_id) - are
deliberately two steps, not one, all in the same shape: the deed itself
(picking up the item - an ordinary pickup, see PickupAction, which has no
special case for it; killing the target; arriving in the dungeon) only
*records* that it happened (QuestLog.record_entity_killed/
record_dungeon_arrival, both unconditional, regardless of any quest's
status) - none of the three completes anything by itself. The quest only
completes when the player then talks to questgiver_entity_id *while still
holding the item* (QuestLog.check_delivery), *after the kill-target's
already been recorded dead* (QuestLog.check_kill_report), or *after the
dungeon's already been recorded visited* (QuestLog.check_dungeon_report) -
all three called from Engine.talk_to_adjacent alongside check_questgiver/
check_talked_to. Splitting the deed from the report this way is what
leaves room for any of them to be interrupted before it's reported - a
deadline expiring first (already supported generically by
check_deadlines/deadline_year/deadline_day, just not set on any quest
using this shape yet), the fetch item being lost some other way - none of
which exists yet, but the two-step shape is what would make it possible
without a redesign. The only trigger shape that stays single-step is Talk
(target_entity_id, QuestLog.check_talked_to) - there's no separate "deed"
to split from the report when talking *is* the deed. One exception across
all three two-step shapes: if a quest's target was already recorded
dead/visited *before* the quest was ever granted, check_questgiver jumps
straight to "completed" the moment it's granted (talking to the
questgiver is itself the report, so there's no separate step to wait
for) - see already_done_message.

Quest.status is the per-quest lifecycle ("not_given" -> "in_progress" ->
"completed"/"failed"). QuestLog.active_quest_id is a separate, single-quest
concept: which one in-progress quest is currently pinned to the HUD - see
Engine.talk_to_adjacent's auto-pin-on-grant and main.py's quest log screen for
where it changes.

The quest log screen's detail pane doesn't just show the static
`description` forever, either - Quest.current_description resolves it
against the quest's actual progress: `completed_description`/
`failed_description` once the quest is terminal, or - while still
in_progress - `carrying_item_description` for a fetch quest whose target
item is actually in the player's inventory (not yet delivered),
`target_dead_description` for a kill quest whose target has actually been
recorded dead (not yet reported), or `target_visited_description` for a
dungeon-arrival quest whose target dungeon has actually been recorded
visited (not yet reported). Any override left unset ("") just falls back
to `description` - main.py's run_quest_log_mode calls this once per frame
and hands the resolved string to render_quest_log, which never computes
it itself (render stays pure display, same split as Engine.shop_price/
render_shop)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from content.schema import QuestStatus, WorldConsequence
from engine.clock import GameClock

if TYPE_CHECKING:
    from content.schema import QuestDef
    from engine.entity import Entity


@dataclass
class Quest:
    id: str
    name: str
    description: str
    completion_message: str
    # Only meaningful alongside a deadline - a no-deadline quest never fails,
    # so it can leave this at the default "".
    failure_message: str = ""
    # A quest completes via exactly one of four hardcoded trigger shapes:
    # arriving in a dungeon (target_dungeon_id, checked in
    # QuestLog.check_dungeon_report) then reporting it to questgiver_entity_id,
    # talking to a specific NPC (target_entity_id, checked in
    # Engine.talk_to_adjacent - the one single-step shape), killing a specific
    # catalog entity (target_kill_entity_id, checked in
    # QuestLog.check_kill_report) then reporting it to questgiver_entity_id,
    # or delivering a specific catalog item to questgiver_entity_id
    # (target_item_id, checked in QuestLog.check_delivery) - arriving/
    # picking the item up/killing the target is an ordinary event with no
    # special handling by itself; only talking to the questgiver afterward
    # completes the quest (and, for a fetch quest, removes the item from
    # inventory). All optional so any one shape - or none, for a quest with
    # no completion trigger yet - is valid.
    target_dungeon_id: str | None = None
    target_entity_id: str | None = None
    target_kill_entity_id: str | None = None
    target_item_id: str | None = None
    # None means no deadline - check_deadlines/format_for_hud both skip a
    # quest with no deadline_day rather than crash on it.
    deadline_year: int | None = None
    deadline_day: int | None = None
    # If set, this quest starts "not_given" and is granted by talking to the
    # matching catalog entity id (see QuestLog.check_questgiver) instead of
    # being given at game start.
    questgiver_entity_id: str | None = None
    # Another quest's id that must be "completed" before QuestLog.check_questgiver
    # will ever grant this one - the general form of a quest chain. None
    # means no prerequisite. See check_questgiver's docstring for what
    # happens while the prerequisite is unmet or ends "failed" instead.
    requires_quest_id: str | None = None
    given_message: str = ""
    # Shown instead of given_message if the kill-target was already recorded
    # dead (see killed_entity_ids) or the target dungeon already recorded
    # visited (see visited_dungeon_ids) at the moment this quest is granted.
    already_done_message: str = ""
    # Once this quest is "completed", every subsequent Talk to
    # questgiver_entity_id/target_entity_id says the matching line below
    # instead of their original spoken line - see QuestLog.followup_dialogue
    # - so an NPC doesn't keep asking for (or waiting on) something already
    # done. "" means no override: the NPC keeps saying their normal
    # Entity.dialogue line even after completion. Both can be set on the
    # same quest if questgiver_entity_id and target_entity_id are different
    # NPCs who each need their own line to change.
    questgiver_done_dialogue: str = ""
    target_done_dialogue: str = ""
    # Catalog item id granted to the player on completion, or None for no
    # reward - see Engine.complete_quest.
    reward_item_id: str | None = None
    # Gold added straight to the player's gold stat on completion, or None
    # for no reward - see Engine.complete_quest. Simpler than reward_item_id:
    # no catalog lookup, just entity.gold += this.
    reward_gold_amount: int | None = None
    # A permanent fraction off everything sold by reward_shop_discount_entity_id's
    # shop, unlocked on completion (e.g. 0.2 for 20% off) - see
    # QuestLog.shop_discount_pct / Engine.shop_price. A quest can set this
    # instead of, or alongside, reward_item_id/reward_gold_amount - none of
    # the three reward shapes are mutually exclusive.
    reward_shop_discount_pct: float | None = None
    # Which shopkeeper's shop reward_shop_discount_pct applies to - a
    # catalog entity id with a non-empty shop_inventory, e.g. "shopkeeper"
    # for Millhaven's. Always set together with reward_shop_discount_pct
    # (content/loader.py enforces this) - the discount is scoped to one
    # specific shop, not every shop in the game.
    reward_shop_discount_entity_id: str | None = None
    status: QuestStatus = "not_given"
    # Quest log pane overrides for current_description below - see each
    # field's docstring on content.schema.QuestDef, which this mirrors
    # exactly (content/loader.py's load_quests is what actually validates
    # them; this is just where they land at runtime).
    carrying_item_description: str = ""
    target_dead_description: str = ""
    target_visited_description: str = ""
    completed_description: str = ""
    failed_description: str = ""
    # Every consequence applied the moment this quest's deadline passes -
    # see content.schema.QuestDef.on_fail and Engine._apply_world_consequences.
    # Empty (the default) means an ordinary deadline failure with no
    # further consequence.
    on_fail: list[WorldConsequence] = field(default_factory=list)
    # This quest can never be completed once this dungeon has been
    # destroyed - see QuestLog.void_by_dungeon. None means this quest is
    # unaffected by any dungeon's destruction.
    voided_by_dungeon_id: str | None = None

    def __post_init__(self) -> None:
        # Not a dataclass field on purpose - stays out of __eq__/repr, so
        # `Quest(...) == Quest(...)` still only compares the fields above.
        # QuestLog.reset() uses this to send each quest back to *its own*
        # starting state (not-given quests stay not-given) rather than a
        # single hardcoded value.
        self.initial_status = self.status

    def format_for_hud(self) -> str:
        if self.status == "in_progress":
            if self.deadline_day is None:
                return f"Quest: {self.name} - active"
            return f"Quest: {self.name} - active (by Day {self.deadline_day})"
        return f"Quest: {self.name} - {self.status}"

    def current_description(
        self, inventory: list["Entity"], killed_entity_ids: set[str], visited_dungeon_ids: set[str],
    ) -> str:
        """What the quest log screen shows for this quest right now -
        richer than the static pitch `description` alone, so a quest that
        actually progresses (or ends) reads that way in the log, not just
        via the HUD's one-line status tag. Falls back to `description` at
        any stage with no dedicated override, so an unwritten override
        just means "nothing new to say yet," never a blank pane.

        Checked in this order: completed and failed are terminal and take
        priority over everything else; carrying_item_description only
        applies mid-flight, to a fetch quest (target_item_id) whose target
        item is actually in `inventory` right now (matched by
        Entity.entity_id, same predicate QuestLog.check_delivery uses) -
        not yet delivered; target_dead_description is the same idea for a
        kill quest (target_kill_entity_id) whose target is actually in
        `killed_entity_ids` (same predicate QuestLog.check_kill_report
        uses) - killed, but not yet reported; target_visited_description is
        the same idea again for a dungeon-arrival quest (target_dungeon_id)
        whose target is actually in `visited_dungeon_ids` (same predicate
        QuestLog.check_dungeon_report uses) - visited, but not yet
        reported. All three are still "in_progress" at this point, but
        worth saying differently than the original pitch."""
        if self.status == "completed":
            return self.completed_description or self.description
        if self.status == "failed":
            return self.failed_description or self.description
        if (
            self.status == "in_progress"
            and self.target_item_id is not None
            and self.carrying_item_description
            and any(it.entity_id == self.target_item_id for it in inventory)
        ):
            return self.carrying_item_description
        if (
            self.status == "in_progress"
            and self.target_kill_entity_id is not None
            and self.target_dead_description
            and self.target_kill_entity_id in killed_entity_ids
        ):
            return self.target_dead_description
        if (
            self.status == "in_progress"
            and self.target_dungeon_id is not None
            and self.target_visited_description
            and self.target_dungeon_id in visited_dungeon_ids
        ):
            return self.target_visited_description
        return self.description


@dataclass
class QuestLog:
    """One instance is shared by every Engine in the game (see main.py) -
    same "one object, referenced everywhere" pattern as GameClock. Only
    main.py's real quest_log (via create_quest_log, built from
    data/quests.yaml) is ever populated; bare Engine(...) construction (e.g.
    in tests) gets a fresh empty QuestLog()."""

    quests: dict[str, Quest] = field(default_factory=dict)
    # Which in-progress quest's name/deadline the HUD shows - see
    # Quest docstring above. None means nothing is pinned.
    active_quest_id: str | None = None
    # Every catalog entity id that has ever died, across the whole run -
    # unconditional, not scoped to any quest's lifetime, which is what makes
    # "already killed before the quest was ever given" detectable (see
    # check_questgiver). Only correct for a catalog id that spawns exactly
    # once in the entire game (true today for "warden") - a kill-quest
    # targeting a commonly-spawned type like "rat" would incorrectly
    # complete the instant *any* rat anywhere died.
    killed_entity_ids: set[str] = field(default_factory=set)
    # Every dungeon id the player has ever arrived in, across the whole run -
    # same shape and same reasoning as killed_entity_ids, just for
    # target_dungeon_id quests instead of target_kill_entity_id ones. No
    # analogous "only correct for a single spawn" caveat - a dungeon either
    # has been entered or it hasn't, there's no multiplicity concern.
    visited_dungeon_ids: set[str] = field(default_factory=set)
    # Every EncounterDef id (data/encounters.yaml) that has already fired,
    # across the whole run - same shape and reasoning as killed_entity_ids/
    # visited_dungeon_ids, so an overworld encounter never re-triggers on a
    # later departure once it's already happened once. See
    # record_encounter_triggered and main.py's _due_encounter.
    triggered_encounter_ids: set[str] = field(default_factory=set)
    # EncounterDef id -> the (year, day, hour) it becomes eligible to fire
    # (see GameClock.plus_hours), for an encounter that's been armed
    # (main.py's _armable_encounter matched) but hasn't fired yet. A stale
    # entry - its gate quest's status having since changed away from
    # gate_quest_status - is never removed here; quest status transitions
    # are one-way in this codebase (not_given -> in_progress ->
    # completed/failed, never back), so a stale due-time can never
    # incorrectly resurrect, and main.py's _due_encounter re-checks the
    # gate quest's live status at fire time regardless. See arm_encounter.
    armed_encounters: dict[str, tuple[int, int, int]] = field(default_factory=dict)
    # Every dungeon id ever destroyed via Engine.destroy_dungeon, across the
    # whole run - same shape and reasoning as visited_dungeon_ids/
    # triggered_encounter_ids. engine/save.py persists this so a reloaded
    # save re-applies the destruction to the freshly rebuilt overworld
    # GameMap (see restore_save) rather than silently un-razing it.
    destroyed_dungeon_ids: set[str] = field(default_factory=set)
    # Every flag name ever set via a WorldConsequence(set_flag=...) firing,
    # across the whole run - same shape and reasoning as
    # destroyed_dungeon_ids. Read back by Entity.flag_dialogue/
    # Engine.talk_to_adjacent (see content.schema.FlagDialogue) - the
    # first, and so far only, thing that reacts to it.
    world_flags: set[str] = field(default_factory=set)

    def active_quest(self) -> Quest | None:
        return self.quests.get(self.active_quest_id) if self.active_quest_id else None

    def set_active_quest(self, quest_id: str) -> None:
        self.active_quest_id = quest_id

    def check_deadlines(self, clock: GameClock) -> list[Quest]:
        """Called every overworld hour (Engine._check_quest_deadlines).
        Marks overdue in-progress quests 'failed' and returns only the ones
        that just changed - guarded on status == "in_progress" so an
        already-terminal quest is never re-flagged, and a quest with no
        deadline is skipped entirely (it can never fail this way)."""
        changed = []
        for quest in self.quests.values():
            if quest.status != "in_progress" or quest.deadline_year is None:
                continue
            if (clock.year, clock.day) > (quest.deadline_year, quest.deadline_day):
                quest.status = "failed"
                changed.append(quest)
        return changed

    def void_by_dungeon(self, dungeon_id: str) -> list[tuple[Quest, bool]]:
        """Called from Engine.destroy_dungeon the moment a dungeon is
        razed. Force-fails every not_given/in_progress quest whose
        voided_by_dungeon_id matches - its questgiver or completion target
        lived there and is gone now. An already-terminal quest
        (completed/failed) is left untouched, same re-fire guard as
        check_deadlines. Returns (quest, was_in_progress) pairs - captured
        *before* the status flip - so the caller can tell a quest the
        player actually knew about (in_progress, worth a failure_message)
        apart from one they never received (not_given, silent - announcing
        the failure of a quest never given would be confusing)."""
        changed = []
        for quest in self.quests.values():
            if quest.voided_by_dungeon_id != dungeon_id or quest.status not in ("not_given", "in_progress"):
                continue
            was_in_progress = quest.status == "in_progress"
            quest.status = "failed"
            changed.append((quest, was_in_progress))
        return changed

    def record_dungeon_arrival(self, dungeon_id: str) -> None:
        """Called from main.py's resolve_transition for every dungeon
        arrival, regardless of whether any quest currently cares - see
        visited_dungeon_ids above for why this must be unconditional. Same
        role as record_entity_killed, for the dungeon-arrival trigger shape:
        purely a memory of where the player's been, for check_questgiver's
        retroactive "already done" detection and check_dungeon_report's "has
        the player actually been there yet" check. Never completes a quest
        directly - arriving alone doesn't finish a dungeon-arrival quest,
        same two-step shape as a fetch quest's pickup vs. delivery or a kill
        quest's kill vs. report."""
        self.visited_dungeon_ids.add(dungeon_id)

    def record_encounter_triggered(self, encounter_id: str) -> None:
        """Called from main.py's _due_encounter/resolve_transition the
        moment an overworld encounter actually fires - unconditional, same
        reasoning as record_dungeon_arrival/record_entity_killed. Purely a
        memory of "this has already happened," so _due_encounter/
        _armable_encounter never redirect into the same encounter twice."""
        self.triggered_encounter_ids.add(encounter_id)

    def arm_encounter(self, encounter_id: str, due: tuple[int, int, int]) -> None:
        """Called from main.py's resolve_transition when _armable_encounter
        matches - starts (or restarts) encounter_id's delay timer, due at
        the given (year, day, hour). Unconditionally overwrites any
        existing due-time: re-departing the trigger dungeon before an
        already-armed timer fires restarts the countdown from that later
        departure, rather than continuing the original one - "counted from
        your most recent departure," not the first ever."""
        self.armed_encounters[encounter_id] = due

    def check_talked_to(self, entity_id: str) -> list[Quest]:
        """Called whenever the player talks to an NPC (Engine.talk_to_adjacent).
        Marks matching in-progress quests 'completed', same re-fire guard as
        above (re-talking to an already-completed target NPC is a no-op)."""
        changed = []
        for quest in self.quests.values():
            if quest.status != "in_progress":
                continue
            if quest.target_entity_id == entity_id:
                quest.status = "completed"
                changed.append(quest)
        return changed

    def check_questgiver(self, entity_id: str) -> list[Quest]:
        """Called whenever the player talks to an NPC (Engine.talk_to_adjacent),
        alongside check_talked_to. Grants matching not-given quests - if the
        quest's kill-target has already been recorded dead
        (killed_entity_ids) or its target dungeon already recorded visited
        (visited_dungeon_ids), it jumps straight to 'completed' instead of
        'in_progress', so the caller can tell the two outcomes apart by
        checking the returned quest's status and log the right message
        (given_message vs already_done_message). A fetch quest has no
        equivalent retroactive check - see check_delivery's docstring.

        A quest with requires_quest_id set is silently skipped (not added to
        `changed` at all - the NPC just says their normal line) unless that
        prerequisite quest's own status is exactly 'completed'. If the
        prerequisite instead ends 'failed' (e.g. a missed deadline), this
        quest stays 'not_given' forever - correct here, not a bug to route
        around: nothing was actually accomplished for the questgiver to
        follow up on. Because this runs before check_talked_to/check_delivery/
        check_kill_report/check_dungeon_report within the same
        talk_to_adjacent call, a quest can't grant its own chained follow-up
        in the same Talk that completes it - the player needs to talk to the
        questgiver again afterward, same one-Talk lag as followup_dialogue's
        done-dialogue switch."""
        changed = []
        for quest in self.quests.values():
            if quest.status != "not_given":
                continue
            if quest.questgiver_entity_id != entity_id:
                continue
            if quest.requires_quest_id is not None:
                prereq = self.quests.get(quest.requires_quest_id)
                if prereq is None or prereq.status != "completed":
                    continue
            already_done = (
                quest.target_kill_entity_id in self.killed_entity_ids
                or quest.target_dungeon_id in self.visited_dungeon_ids
            )
            quest.status = "completed" if already_done else "in_progress"
            changed.append(quest)
        return changed

    def followup_dialogue(self, entity_id: str) -> str | None:
        """The line entity_id should say on Talk *instead of* their normal
        Entity.dialogue, if any quest they're involved in (as questgiver or
        as the Talk-completion target) is already completed and set a
        matching done-dialogue - see Quest.questgiver_done_dialogue/
        target_done_dialogue. Returns None (use the NPC's normal line) if no
        such quest exists yet, which is also the case for every Talk before
        completion - so the same NPC naturally acts as normal first, then
        switches over permanently once the relevant quest is done.

        Iterates in *reverse* data/quests.yaml file order, so when the same
        NPC is involved in more than one quest with a done-dialogue, the
        later-defined quest wins - e.g. the Village Chief is target_entity_id
        for goblin_warning and, once that's completed, questgiver_entity_id
        for its requires_quest_id-gated follow-up defined after it in the
        file; without reversing, he'd stay stuck on goblin_warning's line
        forever even once the follow-up also completes. This is only
        *guaranteed* correct when actual completion order matches file
        order - true for a requires_quest_id chain by construction, since the
        prerequisite must complete first - but not for two unrelated quests
        that just happen to share an NPC (e.g. wayford_road_warden is
        questgiver for clearing_the_watch_road, defined earlier, and target
        for this same follow-up, defined later: if a player completes the
        kill quest *after* the unrelated warning chain, he'll still show the
        warning line, not the kill-quest one). Accepted as a known scope
        limit - a real fix needs per-quest completion timestamps, more
        machinery than this cosmetic case justifies."""
        for quest in reversed(list(self.quests.values())):
            if quest.status != "completed":
                continue
            if quest.questgiver_entity_id == entity_id and quest.questgiver_done_dialogue:
                return quest.questgiver_done_dialogue
            if quest.target_entity_id == entity_id and quest.target_done_dialogue:
                return quest.target_done_dialogue
        return None

    def check_delivery(self, entity_id: str, inventory: list[Entity]) -> list[Quest]:
        """Called whenever the player talks to an NPC (Engine.talk_to_adjacent),
        alongside check_questgiver/check_talked_to. Completes an in-progress
        fetch quest only if BOTH entity_id matches its questgiver_entity_id
        AND the player is actually still carrying the target item
        (matched by Entity.entity_id in `inventory`) - picking the item up
        alone never completes anything (see PickupAction, which has no
        special case for a fetch-quest item; it's just an ordinary pickup).
        Does not itself remove the delivered item from inventory - that's
        Engine.talk_to_adjacent's job, once it knows which quest(s) this
        returned, since QuestLog has no business reaching into player state
        directly. This two-step design leaves room for a delivery to be
        interrupted later (a deadline, the item being lost) without needing
        a redesign - same reasoning as check_kill_report's kill-then-report
        shape below."""
        changed = []
        for quest in self.quests.values():
            if quest.status != "in_progress" or quest.target_item_id is None:
                continue
            if quest.questgiver_entity_id != entity_id:
                continue
            if not any(it.entity_id == quest.target_item_id for it in inventory):
                continue
            quest.status = "completed"
            changed.append(quest)
        return changed

    def check_kill_report(self, entity_id: str) -> list[Quest]:
        """Called whenever the player talks to an NPC (Engine.talk_to_adjacent),
        alongside check_questgiver/check_talked_to/check_delivery. Completes
        an in-progress kill quest only if BOTH entity_id matches its
        questgiver_entity_id AND its target has actually been recorded dead
        (killed_entity_ids) - killing the target alone never completes
        anything anymore (see record_entity_killed, which only records the
        death, unconditionally, regardless of any quest's status). Mirrors
        check_delivery's fetch-quest shape exactly, just checking
        killed_entity_ids instead of inventory. Doesn't apply to a quest
        granted *after* its target already died - check_questgiver handles
        that case by jumping straight to "completed" at grant time, since
        talking to the questgiver in that scenario is itself the report."""
        changed = []
        for quest in self.quests.values():
            if quest.status != "in_progress" or quest.target_kill_entity_id is None:
                continue
            if quest.questgiver_entity_id != entity_id:
                continue
            if quest.target_kill_entity_id not in self.killed_entity_ids:
                continue
            quest.status = "completed"
            changed.append(quest)
        return changed

    def check_dungeon_report(self, entity_id: str) -> list[Quest]:
        """Called whenever the player talks to an NPC (Engine.talk_to_adjacent),
        alongside check_questgiver/check_talked_to/check_delivery/
        check_kill_report. Completes an in-progress dungeon-arrival quest
        only if BOTH entity_id matches its questgiver_entity_id AND its
        target dungeon has actually been recorded visited
        (visited_dungeon_ids) - arriving there alone never completes
        anything anymore (see record_dungeon_arrival, which only records the
        visit, unconditionally, regardless of any quest's status). Mirrors
        check_kill_report exactly, just checking visited_dungeon_ids instead
        of killed_entity_ids. Doesn't apply to a quest granted *after* its
        target dungeon was already visited - check_questgiver handles that
        case by jumping straight to "completed" at grant time, since talking
        to the questgiver in that scenario is itself the report."""
        changed = []
        for quest in self.quests.values():
            if quest.status != "in_progress" or quest.target_dungeon_id is None:
                continue
            if quest.questgiver_entity_id != entity_id:
                continue
            if quest.target_dungeon_id not in self.visited_dungeon_ids:
                continue
            quest.status = "completed"
            changed.append(quest)
        return changed

    def shop_discount_pct(self, shopkeeper_entity_id: str) -> float:
        """The largest permanent discount unlocked at shopkeeper_entity_id's
        shop specifically by any completed quest, or 0.0 if none - a
        discount quest whose reward_shop_discount_entity_id names a
        *different* shopkeeper never counts here, so completing Millhaven's
        discount quest doesn't quietly discount Wayford's shop too (or vice
        versa). Multiple discount-granting quests for the *same* shop
        wouldn't stack - whichever single discount is largest wins."""
        discounts = [
            q.reward_shop_discount_pct for q in self.quests.values()
            if q.status == "completed"
            and q.reward_shop_discount_pct
            and q.reward_shop_discount_entity_id == shopkeeper_entity_id
        ]
        return max(discounts, default=0.0)

    def record_entity_killed(self, entity_id: str) -> None:
        """Called from Engine.on_entity_death for every non-player death,
        regardless of whether any quest currently cares - see
        killed_entity_ids above for why this must be unconditional. Purely a
        memory of what's died now, for two different callers: check_questgiver's
        retroactive "already done" detection when a kill quest is granted
        after its target already died, and check_kill_report's "has the
        target actually died yet" check when the player reports back to a
        kill quest's questgiver. Never completes a quest directly - killing
        the target alone doesn't finish a kill quest, same two-step shape as
        a fetch quest's pickup vs. delivery."""
        self.killed_entity_ids.add(entity_id)

    def reset(self) -> None:
        """Every quest back to its own starting status (not-given quests
        stay not-given, already-given quests go back to in-progress), the
        active pin recomputed, and killed_entity_ids/visited_dungeon_ids/
        triggered_encounter_ids/armed_encounters/destroyed_dungeon_ids/
        world_flags cleared. Engine.restart()
        calls this, since a restart is meant to be a clean slate for
        shared/global state, not just the current dungeon's local state
        (see GameClock.reset()) - a restart should re-arm any in-flight
        encounter timer from scratch, not resume a stale countdown.

        Note: killed_entity_ids/visited_dungeon_ids/triggered_encounter_ids
        are shared/global, but Engine.restart() only rebuilds the *current*
        Engine's map - a dungeon whose Engine isn't the one restarting (e.g.
        Prison Tower, if the player died elsewhere after killing the Warden
        there) keeps its cached, Warden-less map even though this clears the
        record of that kill. Same applies to an already-triggered
        goblin_ambush Engine: clearing triggered_encounter_ids here means the
        *next* qualifying departure from Millhaven redirects into it again,
        but active_engines["goblin_ambush"] isn't evicted, so it resumes
        whatever state that map was left in (goblins already dead, if the
        player cleared it before) rather than rebuilding fresh - consistent
        with this same pre-existing class of dungeon-state desync (see
        Engine.restart's docstring), not something this feature introduces -
        destroyed_dungeon_ids joins that same class: clearing it here
        doesn't un-raze an already-mutated overworld GameMap unless the
        overworld happens to be the Engine actually restarting."""
        for quest in self.quests.values():
            quest.status = quest.initial_status
        self.killed_entity_ids = set()
        self.visited_dungeon_ids = set()
        self.triggered_encounter_ids = set()
        self.armed_encounters = {}
        self.destroyed_dungeon_ids = set()
        self.world_flags = set()
        self.active_quest_id = next(
            (q.id for q in self.quests.values() if q.initial_status == "in_progress"), None
        )


def quest_from_def(qdef: "QuestDef") -> Quest:
    """One QuestDef in, one runtime Quest out - mirrors
    engine/game_map.py's item_entity_from_def (one ItemDef in, one Entity
    out, no map context needed)."""
    return Quest(
        id=qdef.id, name=qdef.name, description=qdef.description,
        completion_message=qdef.completion_message, failure_message=qdef.failure_message,
        target_dungeon_id=qdef.target_dungeon_id, target_entity_id=qdef.target_entity_id,
        target_kill_entity_id=qdef.target_kill_entity_id, target_item_id=qdef.target_item_id,
        deadline_year=qdef.deadline_year, deadline_day=qdef.deadline_day,
        questgiver_entity_id=qdef.questgiver_entity_id, requires_quest_id=qdef.requires_quest_id,
        given_message=qdef.given_message,
        already_done_message=qdef.already_done_message,
        questgiver_done_dialogue=qdef.questgiver_done_dialogue,
        target_done_dialogue=qdef.target_done_dialogue,
        reward_item_id=qdef.reward_item_id, reward_gold_amount=qdef.reward_gold_amount,
        reward_shop_discount_pct=qdef.reward_shop_discount_pct,
        reward_shop_discount_entity_id=qdef.reward_shop_discount_entity_id,
        status=qdef.starting_status,
        carrying_item_description=qdef.carrying_item_description,
        target_dead_description=qdef.target_dead_description,
        target_visited_description=qdef.target_visited_description,
        completed_description=qdef.completed_description,
        failed_description=qdef.failed_description,
        on_fail=list(qdef.on_fail),
        voided_by_dungeon_id=qdef.voided_by_dungeon_id,
    )


def create_quest_log(quest_defs: dict[str, "QuestDef"]) -> QuestLog:
    """Builds the real QuestLog main.py hands to every Engine, from
    data/quests.yaml (via content.loader.load_quests). Which quest starts
    pinned to the HUD is whichever comes first, in quest_defs' (i.e.
    quests.yaml's) key order, with starting_status: in_progress - same
    one-liner QuestLog.reset() already uses to recompute this after a
    restart. Only one quest starts in_progress today, so this can't yet
    produce a surprising pin - but a second in-progress starting quest would
    make YAML key order the tiebreaker, silently, so don't reorder
    quests.yaml casually (see tests/test_quest_loader.py, which pins this
    behavior explicitly)."""
    quests = {qid: quest_from_def(qdef) for qid, qdef in quest_defs.items()}
    active_quest_id = next(
        (q.id for q in quests.values() if q.initial_status == "in_progress"), None
    )
    return QuestLog(quests=quests, active_quest_id=active_quest_id)
