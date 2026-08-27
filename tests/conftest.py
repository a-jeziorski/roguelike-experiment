"""Shared pytest fixtures."""

import engine.combat
import pytest


@pytest.fixture(autouse=True)
def _deterministic_combat(monkeypatch):
    """Every existing test in this suite asserts exact, deterministic
    damage/message values - engine/combat.py's crit/dodge variance layer
    (COMBAT_VARIANCE_ENABLED) would make those flaky if left on by
    default. Off for every test unless a test explicitly re-enables it
    (see tests/test_engine.py's dedicated crit/dodge tests, which
    monkeypatch this back to True and pin `random.random` themselves for
    their own determinism)."""
    monkeypatch.setattr(engine.combat, "COMBAT_VARIANCE_ENABLED", False)
