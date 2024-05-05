from datetime import date

import pytest

from starstamp.errors import ConflictError, NotFoundError
from starstamp.model.cylinder import Cylinder, CylinderKey
from starstamp.model.dates import StampedMonth
from starstamp.model.defect import DefectKind, Observation
from starstamp.model.event import EventState, Outcome, RequalificationEvent
from starstamp.model.method import Method
from starstamp.model.service import NITROGEN
from starstamp.model.specification import parse_specification
from starstamp.model.testrecord import PressureReadings
from starstamp.model.units import Expansion, Pressure
from starstamp.rules.visual import Finding, VisualResult
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.events import EventRepository, pack_lines, unpack_lines
from starstamp.store.owners import OwnerRepository

KEY = CylinderKey.of("NCI", "A4471")
READINGS = PressureReadings(
    applied=Pressure(3358),
    hold_seconds=30,
    total_expansion=Expansion.parse("120.0"),
    permanent_expansion=Expansion.parse("6.0"),
)


@pytest.fixture
def stocked(cylinders: CylinderRepository, owners: OwnerRepository) -> CylinderRepository:
    cylinders.add(
        Cylinder(
            key=KEY,
            specification=parse_specification("DOT-3AA2015"),
            manufactured=StampedMonth(1998, 6),
            service=NITROGEN,
            owner_code="WELD1",
            rejection_elastic_expansion=Expansion.parse("125.0"),
        ),
        owners.id_of("WELD1"),
        date(2024, 3, 1),
    )
    return cylinders


def an_event(**changes: object) -> RequalificationEvent:
    base: dict[str, object] = {
        "cylinder": KEY,
        "performed_on": date(2024, 6, 12),
        "method": Method.VOLUMETRIC,
        "facility_rin": "A419",
        "technician_badge": "JT7",
        "outcome": Outcome.PASS,
        "system_code": "WJ-1",
        "readings": READINGS,
        "wall_thousandths_in": 220,
    }
    base.update(changes)
    return RequalificationEvent(**base)  # type: ignore[arg-type]


def test_lines_pack_and_unpack() -> None:
    assert pack_lines(("a", "b")) == "a\nb"
    assert unpack_lines("a\nb") == ("a", "b")
    assert unpack_lines("") == ()


def test_an_event_round_trips(book, stocked: CylinderRepository) -> None:  # type: ignore[no-untyped-def]
    events = EventRepository(book.connection)
    written = events.add(an_event(), stocked.id_of(KEY))
    assert written.event_id is not None
    read_back = events.by_id(written.event_id)
    assert read_back.method is Method.VOLUMETRIC
    assert read_back.readings is not None
    assert read_back.readings.permanent == Expansion.parse("6.0")
    assert read_back.cylinder == KEY
    assert read_back.wall_thousandths_in == 220


def test_a_proof_test_stores_without_expansion(book, stocked: CylinderRepository) -> None:  # type: ignore[no-untyped-def]
    events = EventRepository(book.connection)
    proof = an_event(
        method=Method.PROOF_PRESSURE,
        system_code=None,
        readings=PressureReadings(applied=Pressure(3358), hold_seconds=30),
    )
    written = events.add(proof, stocked.id_of(KEY))
    assert written.event_id is not None
    read_back = events.by_id(written.event_id)
    assert read_back.readings is not None
    assert not read_back.readings.has_expansion


def test_a_visual_stores_with_no_readings(book, stocked: CylinderRepository) -> None:  # type: ignore[no-untyped-def]
    events = EventRepository(book.connection)
    visual = an_event(method=Method.EXTERNAL_VISUAL, system_code=None, readings=None)
    written = events.add(visual, stocked.id_of(KEY))
    assert written.event_id is not None
    assert events.by_id(written.event_id).readings is None


def test_findings_are_kept_beside_the_event(book, stocked: CylinderRepository) -> None:  # type: ignore[no-untyped-def]
    events = EventRepository(book.connection)
    observation = Observation(
        kind=DefectKind.ISOLATED_PITTING, depth_thousandths_in=12, note="near the foot"
    )
    finding = Finding(observation, VisualResult.PASS, "within 1/5 of the wall")
    written = events.add(an_event(), stocked.id_of(KEY), [finding])
    assert written.event_id is not None
    stored = events.observations(written.event_id)
    assert len(stored) == 1
    assert stored[0][0].kind is DefectKind.ISOLATED_PITTING
    assert stored[0][0].note == "near the foot"
    assert stored[0][1] is VisualResult.PASS


def test_history_is_in_order(book, stocked: CylinderRepository) -> None:  # type: ignore[no-untyped-def]
    events = EventRepository(book.connection)
    events.add(an_event(performed_on=date(2019, 5, 2)), stocked.id_of(KEY))
    events.add(an_event(performed_on=date(2024, 6, 12)), stocked.id_of(KEY))
    history = events.for_cylinder(KEY)
    assert [event.performed_on.year for event in history] == [2019, 2024]


def test_latest_pass_skips_condemnations_and_reversals(book, stocked: CylinderRepository) -> None:  # type: ignore[no-untyped-def]
    events = EventRepository(book.connection)
    events.add(an_event(performed_on=date(2019, 5, 2)), stocked.id_of(KEY))
    later = events.add(an_event(performed_on=date(2024, 6, 12)), stocked.id_of(KEY))
    assert later.event_id is not None
    latest = events.latest_pass(KEY)
    assert latest is not None
    assert latest.performed_on == date(2024, 6, 12)
    events.reverse(later.event_id, "rig out of calibration")
    still = events.latest_pass(KEY)
    assert still is not None
    assert still.performed_on == date(2019, 5, 2)


def test_no_pass_at_all(book, stocked: CylinderRepository) -> None:  # type: ignore[no-untyped-def]
    events = EventRepository(book.connection)
    assert events.latest_pass(KEY) is None


def test_a_reversal_is_recorded_once(book, stocked: CylinderRepository) -> None:  # type: ignore[no-untyped-def]
    events = EventRepository(book.connection)
    written = events.add(an_event(), stocked.id_of(KEY))
    assert written.event_id is not None
    reversed_event = events.reverse(written.event_id, "certificate restated")
    assert reversed_event.state is EventState.REVERSED
    assert "certificate restated" in reversed_event.notes
    with pytest.raises(ConflictError, match="already reversed"):
        events.reverse(written.event_id, "again")


def test_standing_only_leaves_out_reversals(book, stocked: CylinderRepository) -> None:  # type: ignore[no-untyped-def]
    events = EventRepository(book.connection)
    written = events.add(an_event(), stocked.id_of(KEY))
    assert written.event_id is not None
    events.reverse(written.event_id, "certificate restated")
    assert events.for_cylinder(KEY, standing_only=True) == []
    assert len(events.for_cylinder(KEY)) == 1
    with pytest.raises(NotFoundError, match="has been reversed"):
        events.require_standing(written.event_id)


def test_lookups_by_day_and_by_system(book, stocked: CylinderRepository) -> None:  # type: ignore[no-untyped-def]
    events = EventRepository(book.connection)
    events.add(an_event(performed_on=date(2024, 6, 12)), stocked.id_of(KEY))
    events.add(an_event(performed_on=date(2024, 6, 13), system_code="WJ-2"), stocked.id_of(KEY))
    assert len(events.on_day(date(2024, 6, 12))) == 1
    between = events.for_system_between("WJ-1", date(2024, 1, 1), date(2024, 12, 31))
    assert len(between) == 1
    assert events.count() == 2


def test_a_missing_record(book, stocked: CylinderRepository) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(NotFoundError, match="no record of test 99"):
        EventRepository(book.connection).by_id(99)
