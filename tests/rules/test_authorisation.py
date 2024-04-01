from datetime import date

import pytest

from starstamp.errors import RuleViolationError
from starstamp.model.cylinder import Cylinder, CylinderKey, CylinderStatus
from starstamp.model.dates import StampedMonth
from starstamp.model.facility import Facility, Technician
from starstamp.model.method import Method
from starstamp.model.service import AMMONIA, NITROGEN
from starstamp.model.specification import parse_specification
from starstamp.model.units import Expansion
from starstamp.rules.authorisation import authorise, available_methods, choose_method

DAY = date(2024, 6, 12)
ALL_METHODS = frozenset(Method)


def a_cylinder(**changes: object) -> Cylinder:
    base: dict[str, object] = {
        "key": CylinderKey.of("NCI", "A4471"),
        "specification": parse_specification("DOT-3AA2015"),
        "manufactured": StampedMonth(1998, 6),
        "service": NITROGEN,
        "owner_code": "WELD1",
        "rejection_elastic_expansion": Expansion.parse("31.2"),
    }
    base.update(changes)
    return Cylinder(**base)  # type: ignore[arg-type]


def a_facility(**changes: object) -> Facility:
    base: dict[str, object] = {
        "rin": "A419",
        "name": "Wasatch Cylinder Service",
        "approved_from": date(2021, 5, 1),
        "approved_until": date(2026, 4, 30),
        "methods": ALL_METHODS,
    }
    base.update(changes)
    return Facility(**base)  # type: ignore[arg-type]


def a_technician(**changes: object) -> Technician:
    base: dict[str, object] = {
        "badge": "JT7",
        "name": "Jesse Tovar",
        "methods": ALL_METHODS,
        "qualified_from": date(2022, 3, 1),
    }
    base.update(changes)
    return Technician(**base)  # type: ignore[arg-type]


def test_a_cleared_method_comes_back_with_everything_that_cleared_it() -> None:
    cleared = authorise(a_cylinder(), a_facility(), a_technician(), Method.VOLUMETRIC, DAY)
    assert cleared.method is Method.VOLUMETRIC
    assert str(cleared) == "volumetric on NCI/A4471 by JT7 under A419 on 2024-06-12"


def test_the_cylinder_is_asked_first() -> None:
    with pytest.raises(RuleViolationError, match="not permitted"):
        authorise(a_cylinder(), a_facility(), a_technician(), Method.PROOF_PRESSURE, DAY)


def test_a_condemned_cylinder_stops_everything() -> None:
    condemned = a_cylinder(status=CylinderStatus.CONDEMNED)
    with pytest.raises(RuleViolationError, match="takes no requalification"):
        authorise(condemned, a_facility(), a_technician(), Method.VOLUMETRIC, DAY)


def test_an_expired_rin_says_how_long_ago() -> None:
    lapsed = a_facility(approved_until=date(2024, 6, 1))
    with pytest.raises(RuleViolationError, match="lapsed 11 days ago"):
        authorise(a_cylinder(), lapsed, a_technician(), Method.VOLUMETRIC, DAY)


def test_a_rin_that_has_not_started_yet() -> None:
    future = a_facility(approved_from=date(2025, 1, 1), approved_until=date(2030, 1, 1))
    with pytest.raises(RuleViolationError, match="not in force until 2025-01-01"):
        authorise(a_cylinder(), future, a_technician(), Method.VOLUMETRIC, DAY)


def test_a_shop_not_approved_for_the_method_lists_what_it_holds() -> None:
    narrow = a_facility(methods=frozenset({Method.EXTERNAL_VISUAL}))
    with pytest.raises(RuleViolationError, match="it holds external_visual"):
        authorise(a_cylinder(), narrow, a_technician(), Method.VOLUMETRIC, DAY)


def test_a_technician_who_was_not_signed_off_that_day() -> None:
    lapsed = a_technician(qualified_until=date(2024, 1, 1))
    with pytest.raises(RuleViolationError, match="not signed off on 2024-06-12"):
        authorise(a_cylinder(), a_facility(), lapsed, Method.VOLUMETRIC, DAY)


def test_a_technician_not_signed_off_for_this_method() -> None:
    narrow = a_technician(methods=frozenset({Method.EXTERNAL_VISUAL}))
    with pytest.raises(RuleViolationError, match="JT7 is not signed off for volumetric"):
        authorise(a_cylinder(), a_facility(), narrow, Method.VOLUMETRIC, DAY)


def test_available_methods_is_the_intersection() -> None:
    facility = a_facility(methods=frozenset({Method.VOLUMETRIC, Method.PROOF_PRESSURE}))
    technician = a_technician(methods=frozenset({Method.VOLUMETRIC, Method.ULTRASONIC}))
    assert available_methods(a_cylinder(), facility, technician, DAY) == frozenset(
        {Method.VOLUMETRIC}
    )


def test_available_methods_empties_out_when_an_approval_has_lapsed() -> None:
    lapsed = a_facility(approved_until=date(2024, 1, 1))
    assert available_methods(a_cylinder(), lapsed, a_technician(), DAY) == frozenset()


def test_choose_prefers_the_volumetric_test() -> None:
    assert choose_method(a_cylinder(), a_facility(), a_technician(), DAY) is Method.VOLUMETRIC


def test_choose_falls_back_through_the_order() -> None:
    facility = a_facility(methods=frozenset({Method.DIRECT_EXPANSION, Method.EXTERNAL_VISUAL}))
    assert choose_method(a_cylinder(), facility, a_technician(), DAY) is Method.DIRECT_EXPANSION


def test_choose_on_a_welded_cylinder_in_a_dedicated_service() -> None:
    welded = a_cylinder(
        specification=parse_specification("DOT-4BA240"),
        service=AMMONIA,
        rejection_elastic_expansion=None,
    )
    facility = a_facility(methods=frozenset({Method.EXTERNAL_VISUAL}))
    technician = a_technician(methods=frozenset({Method.EXTERNAL_VISUAL}))
    assert choose_method(welded, facility, technician, DAY) is Method.EXTERNAL_VISUAL


def test_choose_refuses_when_nothing_lines_up() -> None:
    facility = a_facility(methods=frozenset({Method.ACETYLENE_VISUAL}))
    with pytest.raises(RuleViolationError, match="nothing A419 and JT7 hold"):
        choose_method(a_cylinder(), facility, a_technician(), DAY)
