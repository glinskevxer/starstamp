from datetime import date

import pytest

from starstamp.errors import RuleViolationError
from starstamp.model.cylinder import Cylinder, CylinderKey
from starstamp.model.dates import StampedMonth
from starstamp.model.method import Method
from starstamp.model.service import AMMONIA, NITROGEN, PROPANE
from starstamp.model.specification import parse_specification
from starstamp.model.units import Expansion
from starstamp.rules.interval import (
    due_month,
    interval_for,
    is_out_of_test,
    life_expired,
    life_limit,
    months_remaining,
)


def a_cylinder(**changes: object) -> Cylinder:
    base: dict[str, object] = {
        "key": CylinderKey.of("NCI", "A4471"),
        "specification": parse_specification("DOT-3AA2015"),
        "manufactured": StampedMonth(1998, 6),
        "service": NITROGEN,
        "owner_code": "WELD1",
        "rejection_elastic_expansion": Expansion.parse("125.0"),
    }
    base.update(changes)
    return Cylinder(**base)  # type: ignore[arg-type]


def welded(service: object = PROPANE) -> Cylinder:
    return a_cylinder(
        specification=parse_specification("DOT-4BA240"),
        service=service,
        rejection_elastic_expansion=None,
    )


def test_the_standard_interval_is_five_years() -> None:
    interval = interval_for(a_cylinder(), Method.VOLUMETRIC)
    assert interval.years == 5
    assert str(interval) == "5 years (the standard interval)"


def test_a_star_doubles_it() -> None:
    assert interval_for(a_cylinder(), Method.VOLUMETRIC, starred=True).years == 10


def test_a_star_cannot_rest_on_a_method_that_measures_nothing() -> None:
    with pytest.raises(RuleViolationError, match="takes none"):
        interval_for(welded(AMMONIA), Method.EXTERNAL_VISUAL, starred=True)


def test_the_method_sets_the_interval_in_a_dedicated_service() -> None:
    assert interval_for(welded(), Method.EXTERNAL_VISUAL).years == 5
    assert interval_for(welded(), Method.VOLUMETRIC).years == 12


def test_a_shared_service_welded_cylinder_gets_the_standard_five() -> None:
    assert interval_for(welded(NITROGEN), Method.VOLUMETRIC).years == 5


def test_high_strength_steel_runs_on_three() -> None:
    high = a_cylinder(specification=parse_specification("DOT-3HT1850"))
    assert interval_for(high, Method.VOLUMETRIC).years == 3
    with pytest.raises(RuleViolationError, match="never starred"):
        interval_for(high, Method.VOLUMETRIC, starred=True)


def test_acetylene_runs_on_ten() -> None:
    from starstamp.model.service import ACETYLENE

    acetylene = a_cylinder(
        specification=parse_specification("DOT-8AL"),
        service=ACETYLENE,
        rejection_elastic_expansion=None,
    )
    assert interval_for(acetylene, Method.ACETYLENE_VISUAL).years == 10
    with pytest.raises(RuleViolationError, match="a star rests on an expansion reading"):
        interval_for(acetylene, Method.ACETYLENE_VISUAL, starred=True)


def test_only_high_strength_steel_carries_a_life_limit() -> None:
    assert life_limit(a_cylinder()) is None
    high = a_cylinder(specification=parse_specification("DOT-3HT1850"))
    assert life_limit(high) == StampedMonth(2022, 6)


def test_life_expiry_reads_off_the_end_of_the_month() -> None:
    high = a_cylinder(specification=parse_specification("DOT-3HT1850"))
    assert not life_expired(high, date(2022, 6, 30))
    assert life_expired(high, date(2022, 7, 1))
    assert not life_expired(a_cylinder(), date(2099, 1, 1))


def test_due_months_follow_the_interval() -> None:
    marked = StampedMonth(2024, 6)
    assert due_month(a_cylinder(), marked, Method.VOLUMETRIC) == StampedMonth(2029, 6)
    assert due_month(a_cylinder(), marked, Method.VOLUMETRIC, starred=True) == StampedMonth(2034, 6)
    assert due_month(welded(), marked, Method.EXTERNAL_VISUAL) == StampedMonth(2029, 6)
    assert due_month(welded(), marked, Method.VOLUMETRIC) == StampedMonth(2036, 6)


def test_a_cylinder_is_in_test_to_the_end_of_the_month() -> None:
    due = StampedMonth(2029, 6)
    assert not is_out_of_test(due, date(2029, 6, 30))
    assert is_out_of_test(due, date(2029, 7, 1))


def test_months_remaining_goes_negative() -> None:
    due = StampedMonth(2029, 6)
    assert months_remaining(due, date(2029, 4, 3)) == 2
    assert months_remaining(due, date(2029, 6, 30)) == 0
    assert months_remaining(due, date(2029, 8, 1)) == -2
