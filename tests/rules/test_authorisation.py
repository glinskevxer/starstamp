from datetime import date

import pytest

from starstamp.errors import RuleViolationError
from starstamp.model.cylinder import CylinderStatus
from starstamp.model.method import Method
from starstamp.model.service import AMMONIA
from starstamp.model.specification import parse_specification
from starstamp.rules.authorisation import authorise, available_methods, choose_method

from ..support.factories import make_cylinder, make_facility, make_technician

DAY = date(2024, 6, 12)


def test_a_cleared_method_comes_back_with_everything_that_cleared_it() -> None:
    cleared = authorise(make_cylinder(), make_facility(), make_technician(), Method.VOLUMETRIC, DAY)
    assert cleared.method is Method.VOLUMETRIC
    assert str(cleared) == "volumetric on NCI/A4471 by JT7 under A419 on 2024-06-12"


def test_the_cylinder_is_asked_first() -> None:
    with pytest.raises(RuleViolationError, match="not permitted"):
        authorise(make_cylinder(), make_facility(), make_technician(), Method.PROOF_PRESSURE, DAY)


def test_a_condemned_cylinder_stops_everything() -> None:
    condemned = make_cylinder(status=CylinderStatus.CONDEMNED)
    with pytest.raises(RuleViolationError, match="takes no requalification"):
        authorise(condemned, make_facility(), make_technician(), Method.VOLUMETRIC, DAY)


def test_an_expired_rin_says_how_long_ago() -> None:
    lapsed = make_facility(approved_until=date(2024, 6, 1))
    with pytest.raises(RuleViolationError, match="lapsed 11 days ago"):
        authorise(make_cylinder(), lapsed, make_technician(), Method.VOLUMETRIC, DAY)


def test_a_rin_that_has_not_started_yet() -> None:
    future = make_facility(approved_from=date(2025, 1, 1), approved_until=date(2030, 1, 1))
    with pytest.raises(RuleViolationError, match="not in force until 2025-01-01"):
        authorise(make_cylinder(), future, make_technician(), Method.VOLUMETRIC, DAY)


def test_a_shop_not_approved_for_the_method_lists_what_it_holds() -> None:
    narrow = make_facility(methods=frozenset({Method.EXTERNAL_VISUAL}))
    with pytest.raises(RuleViolationError, match="it holds external_visual"):
        authorise(make_cylinder(), narrow, make_technician(), Method.VOLUMETRIC, DAY)


def test_a_technician_who_was_not_signed_off_that_day() -> None:
    lapsed = make_technician(qualified_until=date(2024, 1, 1))
    with pytest.raises(RuleViolationError, match="not signed off on 2024-06-12"):
        authorise(make_cylinder(), make_facility(), lapsed, Method.VOLUMETRIC, DAY)


def test_a_technician_not_signed_off_for_this_method() -> None:
    narrow = make_technician(methods=frozenset({Method.EXTERNAL_VISUAL}))
    with pytest.raises(RuleViolationError, match="JT7 is not signed off for volumetric"):
        authorise(make_cylinder(), make_facility(), narrow, Method.VOLUMETRIC, DAY)


def test_available_methods_is_the_intersection() -> None:
    facility = make_facility(methods=frozenset({Method.VOLUMETRIC, Method.PROOF_PRESSURE}))
    technician = make_technician(methods=frozenset({Method.VOLUMETRIC, Method.ULTRASONIC}))
    assert available_methods(make_cylinder(), facility, technician, DAY) == frozenset(
        {Method.VOLUMETRIC}
    )


def test_available_methods_empties_out_when_an_approval_has_lapsed() -> None:
    lapsed = make_facility(approved_until=date(2024, 1, 1))
    assert available_methods(make_cylinder(), lapsed, make_technician(), DAY) == frozenset()


def test_choose_prefers_the_volumetric_test() -> None:
    assert (
        choose_method(make_cylinder(), make_facility(), make_technician(), DAY) is Method.VOLUMETRIC
    )


def test_choose_falls_back_through_the_order() -> None:
    facility = make_facility(methods=frozenset({Method.DIRECT_EXPANSION, Method.EXTERNAL_VISUAL}))
    assert (
        choose_method(make_cylinder(), facility, make_technician(), DAY) is Method.DIRECT_EXPANSION
    )


def test_choose_on_a_welded_cylinder_in_a_dedicated_service() -> None:
    welded = make_cylinder(
        specification=parse_specification("DOT-4BA240"),
        service=AMMONIA,
        rejection_elastic_expansion=None,
    )
    facility = make_facility(methods=frozenset({Method.EXTERNAL_VISUAL}))
    technician = make_technician(methods=frozenset({Method.EXTERNAL_VISUAL}))
    assert choose_method(welded, facility, technician, DAY) is Method.EXTERNAL_VISUAL


def test_choose_refuses_when_nothing_lines_up() -> None:
    facility = make_facility(methods=frozenset({Method.ACETYLENE_VISUAL}))
    with pytest.raises(RuleViolationError, match="nothing A419 and JT7 hold"):
        choose_method(make_cylinder(), facility, make_technician(), DAY)
