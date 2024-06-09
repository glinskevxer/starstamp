"""Typed builders for the objects the tests need over and over.

Every test module had grown its own dictionary based builder with a cast on
the end, which meant none of them type checked and each one drifted. These
take real keyword arguments, so a builder call that names a field that does
not exist fails the type check rather than at run time.
"""

from __future__ import annotations

from datetime import date
from fractions import Fraction

from starstamp.model.calibration import Certificate, InstrumentKind, SystemCheck
from starstamp.model.cylinder import Cylinder, CylinderKey, CylinderStatus
from starstamp.model.dates import StampedMonth
from starstamp.model.defect import DefectKind, Observation
from starstamp.model.event import EventState, Outcome, RequalificationEvent
from starstamp.model.facility import Facility, Technician
from starstamp.model.method import Method
from starstamp.model.owner import OwnerAccount
from starstamp.model.service import NITROGEN, GasService
from starstamp.model.specification import Specification, parse_specification
from starstamp.model.testrecord import PressureReadings
from starstamp.model.units import Expansion, Pressure

DEFAULT_KEY = CylinderKey("NCI", "A4471")
DEFAULT_DAY = date(2024, 6, 12)
ALL_METHODS = frozenset(Method)
DEFAULT_DOM = StampedMonth(1998, 6)
DEFAULT_REE = Expansion(1250)
DEFAULT_APPLIED = Pressure(3358)
DEFAULT_TOTAL = Expansion(1100)
DEFAULT_PERMANENT = Expansion(20)
CHECK_EXPECTED = Expansion(400)
CHECK_OBSERVED = Expansion(401)
ONE_PERCENT = Fraction(1)


def make_cylinder(
    *,
    key: CylinderKey = DEFAULT_KEY,
    specification: Specification | None = None,
    manufactured: StampedMonth = DEFAULT_DOM,
    service: GasService = NITROGEN,
    owner_code: str = "WELD1",
    status: CylinderStatus = CylinderStatus.IN_SERVICE,
    rejection_elastic_expansion: Expansion | None = DEFAULT_REE,
    water_capacity_tenths_l: int | None = None,
    tare_hundredths_lb: int | None = None,
    nominal_wall_thousandths_in: int | None = None,
    wall_source: str | None = None,
) -> Cylinder:
    return Cylinder(
        key=key,
        specification=specification or parse_specification("DOT-3AA2015"),
        manufactured=manufactured,
        service=service,
        owner_code=owner_code,
        status=status,
        rejection_elastic_expansion=rejection_elastic_expansion,
        water_capacity_tenths_l=water_capacity_tenths_l,
        tare_hundredths_lb=tare_hundredths_lb,
        nominal_wall_thousandths_in=nominal_wall_thousandths_in,
        wall_source=wall_source,
    )


def make_readings(
    *,
    applied: Pressure = DEFAULT_APPLIED,
    hold_seconds: int = 30,
    total_expansion: Expansion | None = DEFAULT_TOTAL,
    permanent_expansion: Expansion | None = DEFAULT_PERMANENT,
    leaked: bool = False,
    distorted: bool = False,
) -> PressureReadings:
    return PressureReadings(
        applied=applied,
        hold_seconds=hold_seconds,
        total_expansion=total_expansion,
        permanent_expansion=permanent_expansion,
        leaked=leaked,
        distorted=distorted,
    )


def make_facility(
    *,
    rin: str = "A419",
    name: str = "Wasatch Cylinder Service",
    approved_from: date = date(2021, 5, 1),
    approved_until: date = date(2026, 4, 30),
    methods: frozenset[Method] = ALL_METHODS,
    address: str | None = None,
) -> Facility:
    return Facility(
        rin=rin,
        name=name,
        approved_from=approved_from,
        approved_until=approved_until,
        methods=methods,
        address=address,
    )


def make_technician(
    *,
    badge: str = "JT7",
    name: str = "Jesse Tovar",
    methods: frozenset[Method] = ALL_METHODS,
    qualified_from: date = date(2022, 3, 1),
    qualified_until: date | None = None,
) -> Technician:
    return Technician(
        badge=badge,
        name=name,
        methods=methods,
        qualified_from=qualified_from,
        qualified_until=qualified_until,
    )


def make_owner(
    *,
    code: str = "WELD1",
    name: str = "Cascade Welding Supply",
    opened_on: date = date(2019, 4, 1),
    contact: str | None = None,
    terms_days: int = 30,
    closed_on: date | None = None,
) -> OwnerAccount:
    return OwnerAccount(
        code=code,
        name=name,
        opened_on=opened_on,
        contact=contact,
        terms_days=terms_days,
        closed_on=closed_on,
    )


def make_observation(
    kind: DefectKind,
    *,
    depth_thousandths_in: int | None = None,
    length_thousandths_in: int | None = None,
    note: str | None = None,
) -> Observation:
    return Observation(
        kind=kind,
        depth_thousandths_in=depth_thousandths_in,
        length_thousandths_in=length_thousandths_in,
        note=note,
    )


def make_certificate(
    instrument: str = InstrumentKind.CALIBRATED_CYLINDER,
    *,
    system_code: str = "WJ-1",
    serial: str = "CC-88012",
    issued_on: date = date(2024, 1, 15),
    valid_until: date = date(2029, 1, 15),
    issued_by: str = "Rocky Mountain Calibration",
) -> Certificate:
    return Certificate(
        system_code=system_code,
        instrument=instrument,
        serial=serial,
        issued_on=issued_on,
        valid_until=valid_until,
        issued_by=issued_by,
    )


def make_check(
    *,
    system_code: str = "WJ-1",
    day: date = DEFAULT_DAY,
    expected: Expansion = CHECK_EXPECTED,
    observed: Expansion = CHECK_OBSERVED,
    tolerance_percent: Fraction = ONE_PERCENT,
) -> SystemCheck:
    return SystemCheck(
        system_code=system_code,
        day=day,
        expected=expected,
        observed=observed,
        tolerance_percent=tolerance_percent,
    )


def make_event(
    *,
    cylinder: CylinderKey = DEFAULT_KEY,
    performed_on: date = DEFAULT_DAY,
    method: Method = Method.VOLUMETRIC,
    facility_rin: str = "A419",
    technician_badge: str = "JT7",
    outcome: Outcome = Outcome.PASS,
    reasons: tuple[str, ...] = (),
    system_code: str | None = "WJ-1",
    readings: PressureReadings | None = None,
    wall_thousandths_in: int | None = 220,
    state: EventState = EventState.RECORDED,
    starred: bool = False,
    plus_rated: bool = False,
    reverses: int | None = None,
) -> RequalificationEvent:
    if readings is None and method.is_pressure_test:
        readings = make_readings()
    return RequalificationEvent(
        cylinder=cylinder,
        performed_on=performed_on,
        method=method,
        facility_rin=facility_rin,
        technician_badge=technician_badge,
        outcome=outcome,
        reasons=reasons,
        system_code=system_code,
        readings=readings,
        wall_thousandths_in=wall_thousandths_in,
        state=state,
        starred=starred,
        plus_rated=plus_rated,
        reverses=reverses,
    )
