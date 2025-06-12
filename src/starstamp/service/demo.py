"""A shop with a month of work in it, for somebody looking at this cold.

Not a fixture and not test data. It is what a real small shop's book looks
like a month in: two accounts, a bench, one rig, forty cylinders of mixed
specification and age, a lot that went out and one still open, a handful of
condemnations, and the paperwork that goes with them.

The point is that every report in the package has something to say about it.
A demo where nothing was ever condemned makes half of them print "nothing".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from starstamp.model.calibration import Certificate, InstrumentKind, SystemCheck
from starstamp.model.cylinder import Cylinder, CylinderKey
from starstamp.model.dates import StampedMonth
from starstamp.model.defect import DefectKind, Observation
from starstamp.model.facility import Facility, Technician
from starstamp.model.method import Method
from starstamp.model.money import Money
from starstamp.model.owner import OwnerAccount
from starstamp.model.pricing import PriceItem
from starstamp.model.service import ARGON, CARBON_DIOXIDE, NITROGEN, OXYGEN, PROPANE
from starstamp.model.specification import parse_specification
from starstamp.model.testrecord import PressureReadings
from starstamp.model.units import Expansion
from starstamp.rules.method_matrix import required_test_pressure
from starstamp.service.notices import NoticeService
from starstamp.service.receiving import ReceivingService
from starstamp.service.requalify import RequalificationRequest, RequalificationService
from starstamp.store.calibration import CalibrationRepository
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book
from starstamp.store.facility import FacilityRepository, TechnicianRepository
from starstamp.store.owners import OwnerRepository
from starstamp.store.pricing import PriceRepository

SERVICES = (NITROGEN, ARGON, OXYGEN, CARBON_DIOXIDE, PROPANE)
SPECS = ("DOT-3AA2015", "DOT-3AL3000", "DOT-3AA2265", "DOT-4BA240")
VALVES = {"N2": "580", "AR": "580", "O2": "540", "CO2": "320", "LPG": "555"}


@dataclass(frozen=True)
class DemoResult:
    """What the seeding put in."""

    cylinders: int
    tested: int
    condemned: int

    def describe(self) -> str:
        return (
            f"seeded {self.cylinders} cylinders, {self.tested} requalified, "
            f"{self.condemned} condemned"
        )


def _cylinder(index: int, owner_code: str) -> Cylinder:
    service = SERVICES[index % len(SERVICES)]
    spec_text = SPECS[index % len(SPECS)]
    if service is PROPANE:
        spec_text = "DOT-4BA240"
    spec = parse_specification(spec_text)
    seamless = spec.is_seamless
    return Cylinder(
        key=CylinderKey("NCI", f"D{index:04d}"),
        specification=spec,
        manufactured=StampedMonth(1986 + (index * 3) % 34, 1 + index % 12),
        service=service,
        owner_code=owner_code,
        rejection_elastic_expansion=Expansion(1200 + index * 3) if seamless else None,
        water_capacity_tenths_l=430,
        tare_hundredths_lb=11750,
        nominal_wall_thousandths_in=220 if seamless else 87,
        wall_source="manufacturer data sheet",
        valve_outlet=VALVES[service.code],
        valve_installed_on=date(2019, 4, 1),
    )


def seed(book: Book, today: date, *, cylinders: int = 40) -> DemoResult:
    """Fill an empty book with a month of a small shop's work."""
    owners = OwnerRepository(book.connection)
    owners.add(
        OwnerAccount(
            code="WELD1",
            name="Cascade Welding Supply",
            opened_on=date(2019, 4, 1),
            contact="Ruth Alvarez",
            address="1400 S Gladiola St, Salt Lake City UT 84104",
            phone="801 555 0134",
        )
    )
    owners.add(
        OwnerAccount(
            code="FIRE7",
            name="Sanpete County Fire District",
            opened_on=date(2021, 2, 15),
            address="55 W Main St, Manti UT 84642",
            terms_days=45,
        )
    )

    FacilityRepository(book.connection).add(
        Facility(
            rin="A419",
            name="Wasatch Cylinder Service",
            approved_from=today - timedelta(days=900),
            approved_until=today + timedelta(days=900),
            methods=frozenset(Method),
            address="2210 S 900 W, Salt Lake City UT",
        )
    )
    technicians = TechnicianRepository(book.connection)
    technicians.add(
        Technician(
            badge="JT7",
            name="Jesse Tovar",
            methods=frozenset(Method),
            qualified_from=today - timedelta(days=800),
        )
    )
    technicians.add(
        Technician(
            badge="MR2",
            name="Marisol Reyes",
            methods=frozenset({Method.VOLUMETRIC, Method.EXTERNAL_VISUAL}),
            qualified_from=today - timedelta(days=400),
        )
    )

    calibration = CalibrationRepository(book.connection)
    for instrument in InstrumentKind.ALL:
        calibration.add_certificate(_certificate(instrument, today))

    prices = PriceRepository(book.connection)
    for code, amount, description in (
        ("REQUAL_WJ", "14.50", "water jacket requalification"),
        ("REQUAL_VISUAL", "6.00", "external visual requalification"),
        ("CONDEMN", "9.00", "condemnation and disposal"),
        ("HANDLING", "5.00", "lot handling"),
        ("STORAGE", "0.25", "storage per cylinder day"),
        ("VALVE", "18.00", "valve replacement"),
    ):
        prices.add(
            PriceItem(
                code=code,
                description=description,
                amount=Money.parse(amount),
                effective_from=today - timedelta(days=700),
            )
        )

    repository = CylinderRepository(book.connection)
    keys: list[CylinderKey] = []
    for index in range(cylinders):
        owner_code = "WELD1" if index % 4 else "FIRE7"
        cylinder = _cylinder(index, owner_code)
        repository.add(cylinder, owners.id_of(owner_code), today - timedelta(days=60))
        keys.append(cylinder.key)

    receiving = ReceivingService(book)
    first_lot = receiving.receive(
        "WELD1",
        today - timedelta(days=20),
        [key for index, key in enumerate(keys) if index % 4 and index < 20],
        promised_on=today - timedelta(days=5),
        carrier="Mountain Freight",
    )

    tested, condemned = _run_the_bench(book, keys, today)
    if all(line.is_settled for line in first_lot.lines):
        receiving.ready(first_lot.lot.number)
        receiving.return_lot(first_lot.lot.number, today - timedelta(days=3))
    NoticeService(book).draft_condemnations(today)
    return DemoResult(cylinders=len(keys), tested=tested, condemned=condemned)


def _certificate(instrument: str, today: date) -> Certificate:
    return Certificate(
        system_code="WJ-1",
        instrument=instrument,
        serial=f"{instrument[:3].upper()}-4471",
        issued_on=today - timedelta(days=400),
        valid_until=today + timedelta(days=1400),
        issued_by="Rocky Mountain Calibration",
    )


def _run_the_bench(book: Book, keys: list[CylinderKey], today: date) -> tuple[int, int]:
    """Put a fortnight of cylinders across the bench, most of which pass."""
    calibration = CalibrationRepository(book.connection)
    service = RequalificationService(book)
    tested = 0
    condemned = 0
    for index, key in enumerate(keys[:24]):
        day = today - timedelta(days=14 - index // 2)
        if calibration.check_on("WJ-1", day) is None:
            calibration.record_check(_check(day))
        cylinder = CylinderRepository(book.connection).by_key(key)
        readings, observations = _readings_for(index, cylinder)
        result = service.perform(
            RequalificationRequest(
                key=key,
                day=day,
                technician_badge="JT7" if index % 3 else "MR2",
                method=Method.VOLUMETRIC,
                system_code="WJ-1",
                observations=observations,
                readings=readings,
            )
        )
        tested += 1
        if result.event.is_condemnation:
            condemned += 1
    return tested, condemned


def _check(day: date) -> SystemCheck:
    return SystemCheck(
        system_code="WJ-1",
        day=day,
        expected=Expansion(400),
        observed=Expansion(401),
        technician_badge="JT7",
    )


def _readings_for(
    index: int, cylinder: Cylinder
) -> tuple[PressureReadings, tuple[Observation, ...]]:
    marked = cylinder.rejection_elastic_expansion
    total = Expansion((marked.tenths_cc - 100) if marked else 900)
    permanent = Expansion(total.tenths_cc // 40)
    if index % 11 == 10:
        permanent = Expansion(total.tenths_cc // 5)
    observations: list[Observation] = []
    if cylinder.service.needs_interior_inspection:
        # A gas that can rust a cylinder from the inside has to have been
        # looked at from the inside, so the demo records that reading.
        observations.append(Observation(kind=DefectKind.INTERIOR_CORROSION, depth_thousandths_in=4))
    if index % 13 == 12:
        observations.append(Observation(kind=DefectKind.BULGE))
    return (
        PressureReadings(
            applied=required_test_pressure(cylinder.specification),
            hold_seconds=30,
            total_expansion=total,
            permanent_expansion=permanent,
        ),
        tuple(observations),
    )
