from datetime import date
from fractions import Fraction

import pytest

from starstamp.errors import NotFoundError, ValidationError
from starstamp.model.settings import (
    CAPACITY_PER_RIG,
    CHECK_TOLERANCE,
    MINIMUM_HOLD,
    Setting,
    Settings,
    check_value,
    known_settings,
)

DAY = date(2024, 6, 12)


def test_the_shop_sets_a_short_list() -> None:
    assert len(known_settings()) == 4
    assert CAPACITY_PER_RIG in known_settings()


def test_an_unknown_setting_lists_the_ones_there_are() -> None:
    with pytest.raises(ValidationError, match="the shop sets"):
        check_value("wobble", "3")


def test_whole_numbers_are_checked_against_their_range() -> None:
    assert check_value(CAPACITY_PER_RIG, " 40 ") == "40"
    with pytest.raises(ValidationError, match="runs from 1 to 500"):
        check_value(CAPACITY_PER_RIG, "900")
    with pytest.raises(ValidationError, match="whole number"):
        check_value(CAPACITY_PER_RIG, "forty")


def test_the_hold_time_has_a_floor() -> None:
    with pytest.raises(ValidationError, match="runs from 30 to 600"):
        check_value(MINIMUM_HOLD, "10")


def test_the_tolerance_takes_a_fraction() -> None:
    assert check_value(CHECK_TOLERANCE, "3/2") == "3/2"
    assert check_value(CHECK_TOLERANCE, "2") == "2"
    with pytest.raises(ValidationError, match="above zero"):
        check_value(CHECK_TOLERANCE, "0")
    with pytest.raises(ValidationError, match="is a number"):
        check_value(CHECK_TOLERANCE, "loose")


def test_a_setting_reads_as_a_number() -> None:
    setting = Setting(CAPACITY_PER_RIG, "40", DAY)
    assert setting.as_int() == 40
    assert Setting(CHECK_TOLERANCE, "3/2", DAY).as_fraction() == Fraction(3, 2)
    assert str(setting) == "capacity_per_rig = 40 from 2024-06-12"


def test_an_unset_setting_falls_back_to_the_default() -> None:
    assert Settings().integer(CAPACITY_PER_RIG, DAY) == 24
    assert Settings().fraction(CHECK_TOLERANCE, DAY) == Fraction(1)


def test_the_value_in_force_is_the_latest_one_before_the_day() -> None:
    settings = Settings(
        (
            Setting(CAPACITY_PER_RIG, "30", date(2023, 1, 1)),
            Setting(CAPACITY_PER_RIG, "40", date(2024, 1, 1)),
        )
    )
    assert settings.integer(CAPACITY_PER_RIG, date(2023, 6, 1)) == 30
    assert settings.integer(CAPACITY_PER_RIG, date(2024, 6, 1)) == 40
    assert settings.integer(CAPACITY_PER_RIG, date(2022, 6, 1)) == 24


def test_asking_for_something_that_is_not_a_setting() -> None:
    with pytest.raises(NotFoundError, match="no such setting"):
        Settings().on("wobble", DAY)


def test_reading_them_all_for_a_day() -> None:
    settings = Settings((Setting(CAPACITY_PER_RIG, "40", date(2024, 1, 1)),))
    current = settings.current(DAY)
    assert current[CAPACITY_PER_RIG] == "40"
    assert current[MINIMUM_HOLD] == "30"
