"""In-game calendar time: a flat hour counter that rolls into day/year
boundaries. No day/night cycle, no seasons/months - kept deliberately simple,
a foundation for future quest/dynamic-world features rather than a full
calendar simulation."""

from __future__ import annotations

from dataclasses import dataclass

HOURS_PER_DAY = 24
DAYS_PER_YEAR = 365

STARTING_YEAR = 87
STARTING_DAY = 50
STARTING_HOUR = 0


@dataclass
class GameClock:
    """One instance is shared by every Engine in the game (see main.py) - the
    same "one object, referenced everywhere" pattern Engine already uses for
    the player entity across dungeon/overworld transitions. Only the overworld
    ever calls advance_hour() (see Engine._advance_world_clock); dungeons and
    settlements leave it untouched."""

    year: int = STARTING_YEAR
    day: int = STARTING_DAY
    hour: int = STARTING_HOUR

    def advance_hour(self) -> None:
        self.hour += 1
        if self.hour >= HOURS_PER_DAY:
            self.hour = 0
            self.day += 1
            if self.day > DAYS_PER_YEAR:
                self.day = 1
                self.year += 1

    def reset(self) -> None:
        self.year = STARTING_YEAR
        self.day = STARTING_DAY
        self.hour = STARTING_HOUR

    def format_for_hud(self) -> str:
        return f"Hour {self.hour}, Day {self.day}, Year {self.year} P.S."
