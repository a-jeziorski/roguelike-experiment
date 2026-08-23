from engine.clock import STARTING_DAY, STARTING_HOUR, STARTING_YEAR, GameClock


def test_default_clock_starts_at_hour_0_day_50_year_87():
    clock = GameClock()
    assert clock.hour == STARTING_HOUR == 0
    assert clock.day == STARTING_DAY == 50
    assert clock.year == STARTING_YEAR == 87


def test_advance_hour_increments_hour():
    clock = GameClock(hour=5, day=50, year=87)
    clock.advance_hour()
    assert clock == GameClock(hour=6, day=50, year=87)


def test_advance_hour_rolls_over_at_day_boundary():
    clock = GameClock(hour=23, day=50, year=87)
    clock.advance_hour()
    assert clock == GameClock(hour=0, day=51, year=87)


def test_advance_hour_rolls_over_at_year_boundary():
    clock = GameClock(hour=23, day=365, year=87)
    clock.advance_hour()
    assert clock == GameClock(hour=0, day=1, year=88)


def test_format_for_hud_matches_expected_string():
    clock = GameClock(hour=3, day=51, year=87)
    assert clock.format_for_hud() == "Hour 3, Day 51, Year 87 P.S."


def test_reset_returns_to_starting_values_after_being_advanced():
    clock = GameClock()
    for _ in range(100):
        clock.advance_hour()
    assert clock != GameClock()

    clock.reset()
    assert clock == GameClock()


def test_plus_hours_within_the_same_day():
    clock = GameClock(hour=5, day=50, year=87)
    assert clock.plus_hours(3) == (87, 50, 8)


def test_plus_hours_crosses_a_day_boundary():
    clock = GameClock(hour=22, day=50, year=87)
    assert clock.plus_hours(3) == (87, 51, 1)


def test_plus_hours_crosses_a_year_boundary():
    clock = GameClock(hour=22, day=365, year=87)
    assert clock.plus_hours(3) == (88, 1, 1)


def test_plus_hours_does_not_mutate_the_clock():
    clock = GameClock(hour=5, day=50, year=87)
    clock.plus_hours(20)
    assert clock == GameClock(hour=5, day=50, year=87)
