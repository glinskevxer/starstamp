from datetime import date
from fractions import Fraction

import pytest

from starstamp.errors import RuleViolationError
from starstamp.model.calibration import Certificate, InstrumentKind
from starstamp.model.method import Method
from starstamp.model.units import Expansion
from starstamp.rules.validity import assess, needs_daily_check, required_instruments

from ..support.factories import make_certificate, make_check

DAY = date(2024, 6, 12)
SYSTEM = "WJ-1"


def full_set() -> list[Certificate]:
    return [
        make_certificate(instrument, serial=f"{instrument[:2].upper()}-1")
        for instrument in InstrumentKind.ALL
    ]


def test_which_instruments_each_method_leans_on() -> None:
    assert required_instruments(Method.VOLUMETRIC) == frozenset(
        {
            InstrumentKind.CALIBRATED_CYLINDER,
            InstrumentKind.PRESSURE_INDICATOR,
            InstrumentKind.EXPANSION_SCALE,
        }
    )
    assert required_instruments(Method.PROOF_PRESSURE) == frozenset(
        {InstrumentKind.PRESSURE_INDICATOR}
    )
    assert required_instruments(Method.EXTERNAL_VISUAL) == frozenset()


def test_only_the_expansion_methods_need_a_daily_check() -> None:
    assert needs_daily_check(Method.VOLUMETRIC)
    assert needs_daily_check(Method.DIRECT_EXPANSION)
    assert not needs_daily_check(Method.PROOF_PRESSURE)


def test_a_rig_in_calibration_is_valid() -> None:
    validity = assess(Method.VOLUMETRIC, DAY, SYSTEM, full_set(), make_check())
    assert validity.is_valid
    assert validity.describe() == "WJ-1 in calibration on 2024-06-12"
    assert validity.require() is validity


def test_a_missing_certificate_is_named() -> None:
    partial = [make_certificate(InstrumentKind.PRESSURE_INDICATOR)]
    validity = assess(Method.VOLUMETRIC, DAY, SYSTEM, partial, make_check())
    assert not validity.is_valid
    assert "no calibrated_cylinder certificate on file" in validity.faults
    assert "no expansion_scale certificate on file" in validity.faults


def test_an_expired_certificate_says_when_it_expired() -> None:
    certificates = full_set()
    certificates[0] = make_certificate(
        InstrumentKind.CALIBRATED_CYLINDER, valid_until=date(2024, 6, 11)
    )
    validity = assess(Method.VOLUMETRIC, DAY, SYSTEM, certificates, make_check())
    assert "calibrated_cylinder certificate expired 2024-06-11" in validity.faults


def test_a_certificate_issued_after_the_test() -> None:
    certificates = full_set()
    certificates[1] = make_certificate(
        InstrumentKind.PRESSURE_INDICATOR,
        issued_on=date(2024, 7, 1),
        valid_until=date(2029, 7, 1),
    )
    validity = assess(Method.VOLUMETRIC, DAY, SYSTEM, certificates, make_check())
    assert "pressure_indicator certificate not issued until 2024-07-01" in validity.faults


def test_a_proof_pressure_test_ignores_the_expansion_instruments() -> None:
    only_gauge = [make_certificate(InstrumentKind.PRESSURE_INDICATOR)]
    assert assess(Method.PROOF_PRESSURE, DAY, SYSTEM, only_gauge, None).is_valid


def test_a_visual_needs_no_rig_at_all() -> None:
    assert assess(Method.EXTERNAL_VISUAL, DAY, SYSTEM, [], None).is_valid


def test_a_missing_daily_check_invalidates_a_volumetric_test() -> None:
    validity = assess(Method.VOLUMETRIC, DAY, SYSTEM, full_set(), None)
    assert validity.faults == ("no start of day check",)


def test_yesterdays_check_does_not_carry_over() -> None:
    stale = make_check(day=date(2024, 6, 11))
    validity = assess(Method.VOLUMETRIC, DAY, SYSTEM, full_set(), stale)
    assert "start of day check is dated 2024-06-11" in validity.faults


def test_another_rigs_check_does_not_count() -> None:
    other = make_check(system_code="WJ-2")
    validity = assess(Method.VOLUMETRIC, DAY, SYSTEM, full_set(), other)
    assert "start of day check belongs to WJ-2" in validity.faults


def test_a_check_out_of_tolerance_invalidates_the_day() -> None:
    off = make_check(observed=Expansion.parse("39.0"))
    validity = assess(Method.VOLUMETRIC, DAY, SYSTEM, full_set(), off)
    assert "start of day check off by -2.50%" in validity.faults


def test_the_same_readings_are_valid_under_a_wider_tolerance() -> None:
    off = make_check(observed=Expansion.parse("39.0"), tolerance_percent=Fraction(3))
    assert assess(Method.VOLUMETRIC, DAY, SYSTEM, full_set(), off).is_valid


def test_every_fault_is_reported_not_just_the_first() -> None:
    validity = assess(Method.VOLUMETRIC, DAY, SYSTEM, [], None)
    assert len(validity.faults) == 4


def test_requiring_a_bad_rig_raises_with_all_of_it() -> None:
    validity = assess(Method.VOLUMETRIC, DAY, SYSTEM, [], None)
    with pytest.raises(RuleViolationError) as caught:
        validity.require()
    message = str(caught.value)
    assert "was not fit to requalify on 2024-06-12" in message
    assert "no start of day check" in message
    assert "180.205" in message


def test_certificates_from_another_system_do_not_count() -> None:
    elsewhere = [
        make_certificate(instrument, system_code="WJ-2") for instrument in InstrumentKind.ALL
    ]
    validity = assess(Method.VOLUMETRIC, DAY, SYSTEM, elsewhere, make_check())
    assert len(validity.faults) == 3
