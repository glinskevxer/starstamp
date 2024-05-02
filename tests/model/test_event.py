from datetime import date

import pytest

from starstamp.errors import ValidationError
from starstamp.model.cylinder import CylinderKey
from starstamp.model.dates import StampedMonth
from starstamp.model.event import EventState, Outcome, RequalificationEvent
from starstamp.model.method import Method
from starstamp.model.testrecord import PressureReadings
from starstamp.model.units import Expansion, Pressure

KEY = CylinderKey.of("NCI", "A4471")
DAY = date(2024, 6, 12)
READINGS = PressureReadings(
    applied=Pressure(3358),
    hold_seconds=30,
    total_expansion=Expansion.parse("120.0"),
    permanent_expansion=Expansion.parse("6.0"),
)


def an_event(**changes: object) -> RequalificationEvent:
    base: dict[str, object] = {
        "cylinder": KEY,
        "performed_on": DAY,
        "method": Method.VOLUMETRIC,
        "facility_rin": "A419",
        "technician_badge": "JT7",
        "outcome": Outcome.PASS,
        "system_code": "WJ-1",
        "readings": READINGS,
    }
    base.update(changes)
    return RequalificationEvent(**base)  # type: ignore[arg-type]


def test_a_pass_may_be_marked() -> None:
    event = an_event()
    assert event.may_be_marked
    assert event.marked_month == StampedMonth(2024, 6)
    assert not event.is_condemnation


def test_a_condemnation_has_to_say_why() -> None:
    with pytest.raises(ValidationError, match="has to say why"):
        an_event(outcome=Outcome.CONDEMN)


def test_a_condemnation_is_never_marked() -> None:
    event = an_event(outcome=Outcome.CONDEMN, reasons=("leaked under pressure",))
    assert not event.may_be_marked
    assert event.is_condemnation


def test_a_pressure_test_carries_readings() -> None:
    with pytest.raises(ValidationError, match="carry the rig's readings"):
        an_event(readings=None)


def test_a_visual_never_does() -> None:
    with pytest.raises(ValidationError, match="never put the cylinder on a rig"):
        an_event(method=Method.EXTERNAL_VISUAL, system_code=None)


def test_a_water_jacket_test_names_its_system() -> None:
    with pytest.raises(ValidationError, match="name the test system"):
        an_event(system_code=None)


def test_a_direct_expansion_test_needs_no_jacket() -> None:
    event = an_event(method=Method.DIRECT_EXPANSION, system_code=None)
    assert event.system_code is None


def test_a_reversed_event_is_no_longer_markable() -> None:
    event = an_event().reversed_by("calibration certificate restated")
    assert event.state is EventState.REVERSED
    assert not event.state.stands
    assert not event.may_be_marked
    assert "calibration certificate restated" in event.notes


def test_an_event_is_only_reversed_once() -> None:
    event = an_event().reversed_by("first")
    with pytest.raises(ValidationError, match="already been reversed"):
        event.reversed_by("second")


def test_a_replacement_names_what_it_replaces() -> None:
    with pytest.raises(ValidationError, match="name the event it replaces"):
        an_event(state=EventState.REPLACEMENT)
    replacement = an_event(state=EventState.REPLACEMENT, reverses=7)
    assert replacement.reverses == 7


def test_only_a_replacement_names_one() -> None:
    with pytest.raises(ValidationError, match="only a replacement"):
        an_event(reverses=7)


def test_ids_are_attached_after_writing() -> None:
    assert an_event().with_id(12).event_id == 12


def test_summaries_read_like_a_log_line() -> None:
    assert an_event().summary() == "2024-06-12 NCI/A4471 volumetric pass"
    condemned = an_event(outcome=Outcome.CONDEMN, reasons=("leaked under pressure",))
    assert condemned.summary().endswith("condemn: leaked under pressure")
    reversed_event = an_event().reversed_by("rig out of calibration")
    assert "[reversed]" in reversed_event.summary()


def test_a_suspended_event_is_not_a_pass() -> None:
    suspended = an_event(outcome=Outcome.SUSPENDED, reasons=("valve threads damaged",))
    assert not suspended.may_be_marked
    assert not suspended.is_condemnation
