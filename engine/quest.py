"""Minimal quest tracking: currently a single hardcoded starting quest (see
create_starting_quest_log), laying the groundwork for quest-givers and
multiple quests later. Not a scripting engine - quests complete/fail via two
hardcoded trigger shapes (dungeon arrival, clock deadline) that Engine calls
into each turn (see Engine._check_quest_deadlines and main.py's
resolve_transition)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from engine.clock import GameClock

QuestStatus = Literal["active", "completed", "failed"]

SEALED_MESSAGE_ID = "sealed_message"
SEALED_MESSAGE_DEADLINE_YEAR = 87
SEALED_MESSAGE_DEADLINE_DAY = 57
SEALED_MESSAGE_TARGET_DUNGEON = "millhaven"


@dataclass
class Quest:
    id: str
    name: str
    description: str
    completion_message: str
    failure_message: str
    deadline_year: int
    deadline_day: int
    target_dungeon_id: str
    status: QuestStatus = "active"

    def format_for_hud(self) -> str:
        if self.status == "active":
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

    def check_deadlines(self, clock: GameClock) -> list[Quest]:
        """Called every overworld hour (Engine._check_quest_deadlines).
        Marks overdue active quests 'failed' and returns only the ones that
        just changed - guarded on status == "active" so an already-terminal
        quest is never re-flagged (otherwise a failed quest would re-print
        its failure message every overworld turn for the rest of the game)."""
        changed = []
        for quest in self.quests.values():
            if quest.status != "active":
                continue
            if (clock.year, clock.day) > (quest.deadline_year, quest.deadline_day):
                quest.status = "failed"
                changed.append(quest)
        return changed

    def check_dungeon_arrival(self, dungeon_id: str) -> list[Quest]:
        """Called whenever the player arrives in a dungeon (main.py's
        resolve_transition). Marks matching active quests 'completed', same
        re-fire guard as above (a settlement like Millhaven is revisitable)."""
        changed = []
        for quest in self.quests.values():
            if quest.status != "active":
                continue
            if quest.target_dungeon_id == dungeon_id:
                quest.status = "completed"
                changed.append(quest)
        return changed

    def reset(self) -> None:
        """All quests back to 'active' - Engine.restart() calls this, since
        a restart is meant to be a clean slate for shared/global state, not
        just the current dungeon's local state (see GameClock.reset())."""
        for quest in self.quests.values():
            quest.status = "active"


def create_starting_quest_log() -> QuestLog:
    quest = Quest(
        id=SEALED_MESSAGE_ID,
        name="The Sealed Message",
        description=(
            "Before your capture, you were tasked with delivering a sealed "
            "message to Millhaven. You still carry the charge, if not the "
            "letter itself - whatever it said, and whoever it was for, will "
            "have to wait until you get there."
        ),
        completion_message="You have reached Millhaven. The sealed message can finally be delivered.",
        failure_message="The deadline for the sealed message has passed. No point delivering it anymore.",
        deadline_year=SEALED_MESSAGE_DEADLINE_YEAR,
        deadline_day=SEALED_MESSAGE_DEADLINE_DAY,
        target_dungeon_id=SEALED_MESSAGE_TARGET_DUNGEON,
    )
    return QuestLog(quests={quest.id: quest})
