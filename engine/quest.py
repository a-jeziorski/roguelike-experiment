"""Quest tracking: a handful of hardcoded quests (see create_starting_quest_log),
some given from the start, some granted by talking to a questgiver NPC while
they're still "not_given". Not a scripting engine - quests complete via three
hardcoded trigger shapes (dungeon arrival, Talk, killing a specific catalog
entity) that Engine/main.py call into (see Engine.on_entity_death,
Engine.talk_to_adjacent, main.py's resolve_transition), and fail via one
(clock deadline, see Engine._check_quest_deadlines).

Quest.status is the per-quest lifecycle ("not_given" -> "in_progress" ->
"completed"/"failed"). QuestLog.active_quest_id is a separate, single-quest
concept: which one in-progress quest is currently pinned to the HUD - see
Engine.talk_to_adjacent's auto-pin-on-grant and main.py's quest log screen for
where it changes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from engine.clock import GameClock

QuestStatus = Literal["not_given", "in_progress", "completed", "failed"]

GOBLIN_WARNING_ID = "goblin_warning"
GOBLIN_WARNING_DEADLINE_YEAR = 87
GOBLIN_WARNING_DEADLINE_DAY = 57
GOBLIN_WARNING_TARGET_ENTITY = "village_chief"

KILL_THE_WARDEN_ID = "kill_the_warden"
KILL_THE_WARDEN_QUESTGIVER = "escaped_prisoner"
KILL_THE_WARDEN_TARGET = "warden"
KILL_THE_WARDEN_REWARD = "healing_potion"


@dataclass
class Quest:
    id: str
    name: str
    description: str
    completion_message: str
    # Only meaningful alongside a deadline - a no-deadline quest never fails,
    # so it can leave this at the default "".
    failure_message: str = ""
    # A quest completes via exactly one of three hardcoded trigger shapes:
    # arriving in a dungeon (target_dungeon_id, checked in main.py's
    # resolve_transition), talking to a specific NPC (target_entity_id,
    # checked in Engine.talk_to_adjacent), or killing a specific catalog
    # entity (target_kill_entity_id, checked in Engine.on_entity_death). All
    # optional so any one shape - or none, for a quest with no completion
    # trigger yet - is valid.
    target_dungeon_id: str | None = None
    target_entity_id: str | None = None
    target_kill_entity_id: str | None = None
    # None means no deadline - check_deadlines/format_for_hud both skip a
    # quest with no deadline_day rather than crash on it.
    deadline_year: int | None = None
    deadline_day: int | None = None
    # If set, this quest starts "not_given" and is granted by talking to the
    # matching catalog entity id (see QuestLog.check_questgiver) instead of
    # being given at game start.
    questgiver_entity_id: str | None = None
    given_message: str = ""
    # Shown instead of given_message if the kill-target was already recorded
    # dead (see killed_entity_ids) at the moment this quest is granted.
    already_done_message: str = ""
    # Catalog item id granted to the player on completion, or None for no
    # reward - see Engine.complete_quest.
    reward_item_id: str | None = None
    status: QuestStatus = "not_given"

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


@dataclass
class QuestLog:
    """One instance is shared by every Engine in the game (see main.py) -
    same "one object, referenced everywhere" pattern as GameClock. Only
    main.py's real quest_log (via create_starting_quest_log) is ever
    populated; bare Engine(...) construction (e.g. in tests) gets a fresh
    empty QuestLog()."""

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

    def check_dungeon_arrival(self, dungeon_id: str) -> list[Quest]:
        """Called whenever the player arrives in a dungeon (main.py's
        resolve_transition). Marks matching in-progress quests 'completed',
        same re-fire guard as above (a settlement like Millhaven is
        revisitable)."""
        changed = []
        for quest in self.quests.values():
            if quest.status != "in_progress":
                continue
            if quest.target_dungeon_id == dungeon_id:
                quest.status = "completed"
                changed.append(quest)
        return changed

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
        quest's kill-target has already been recorded dead (killed_entity_ids),
        it jumps straight to 'completed' instead of 'in_progress', so the
        caller can tell the two outcomes apart by checking the returned
        quest's status and log the right message (given_message vs
        already_done_message)."""
        changed = []
        for quest in self.quests.values():
            if quest.status != "not_given":
                continue
            if quest.questgiver_entity_id != entity_id:
                continue
            if quest.target_kill_entity_id in self.killed_entity_ids:
                quest.status = "completed"
            else:
                quest.status = "in_progress"
            changed.append(quest)
        return changed

    def record_entity_killed(self, entity_id: str) -> list[Quest]:
        """Called from Engine.on_entity_death for every non-player death,
        regardless of whether any quest currently cares - see
        killed_entity_ids above for why this must be unconditional."""
        self.killed_entity_ids.add(entity_id)
        changed = []
        for quest in self.quests.values():
            if quest.status != "in_progress":
                continue
            if quest.target_kill_entity_id == entity_id:
                quest.status = "completed"
                changed.append(quest)
        return changed

    def reset(self) -> None:
        """Every quest back to its own starting status (not-given quests
        stay not-given, already-given quests go back to in-progress), the
        active pin recomputed, and killed_entity_ids cleared. Engine.restart()
        calls this, since a restart is meant to be a clean slate for
        shared/global state, not just the current dungeon's local state (see
        GameClock.reset()).

        Note: killed_entity_ids is shared/global, but Engine.restart() only
        rebuilds the *current* Engine's map - a dungeon whose Engine isn't
        the one restarting (e.g. Prison Tower, if the player died elsewhere
        after killing the Warden there) keeps its cached, Warden-less map even
        though this clears the record of that kill. A real fix would mean
        widening restart()'s scope to every cached Engine, which is out of
        scope here - this is a narrow, pre-existing class of dungeon-state
        desync (see Engine.restart's docstring), not something this feature
        introduces."""
        for quest in self.quests.values():
            quest.status = quest.initial_status
        self.killed_entity_ids = set()
        self.active_quest_id = next(
            (q.id for q in self.quests.values() if q.initial_status == "in_progress"), None
        )


def create_starting_quest_log() -> QuestLog:
    goblin_warning = Quest(
        id=GOBLIN_WARNING_ID,
        name="The Goblin Warning",
        description=(
            "Before your capture, you were carrying word to Millhaven: a "
            "goblin horde is migrating into the region, and the town needs "
            "warning before it arrives. No letter, no proof - just what "
            "you were told, and who you can get to listen."
        ),
        completion_message="The warning is passed on - what Millhaven does with it now isn't yours to carry anymore.",
        failure_message="The deadline for the warning has passed. Whatever time Millhaven had to prepare, it's gone now.",
        deadline_year=GOBLIN_WARNING_DEADLINE_YEAR,
        deadline_day=GOBLIN_WARNING_DEADLINE_DAY,
        target_entity_id=GOBLIN_WARNING_TARGET_ENTITY,
        status="in_progress",
    )
    kill_the_warden = Quest(
        id=KILL_THE_WARDEN_ID,
        name="An Old Debt",
        description=(
            "Another prisoner who made it out asked you for a favor: the "
            "Warden of Prison Tower doesn't get to just walk away from what "
            "he did there. Whether he's already paid for it or not is "
            "something you'd know better than they would."
        ),
        completion_message="The Warden is dead. Whatever he did to the people under him, he won't do it to anyone else now.",
        given_message="New quest: An Old Debt - if the Warden of Prison Tower is still alive, he won't be for long if you have anything to say about it.",
        already_done_message="You tell them it's already done - the Warden didn't survive your escape. They go quiet for a moment. 'Good,' they say, finally. 'Good.'",
        questgiver_entity_id=KILL_THE_WARDEN_QUESTGIVER,
        target_kill_entity_id=KILL_THE_WARDEN_TARGET,
        reward_item_id=KILL_THE_WARDEN_REWARD,
    )
    return QuestLog(
        quests={goblin_warning.id: goblin_warning, kill_the_warden.id: kill_the_warden},
        active_quest_id=GOBLIN_WARNING_ID,
    )
