"""Ten years of one cylinder, through the services in the order they happen.

Every other suite proves a layer works. This proves the layers agree with each
other over time, which is where the interesting failures are: a star granted
in 2024 has to still be the thing that decides a fill in 2032, and a
restatement in 2026 has to reach back and take it away.
"""

from __future__ import annotations

from datetime import date

import pytest

from starstamp.errors import RuleViolationError
from starstamp.model.calibration import Certificate, InstrumentKind
from starstamp.model.cylinder import CylinderKey, CylinderStatus
from starstamp.model.defect import DefectKind
from starstamp.model.disposal import DisposalMethod
from starstamp.model.event import Outcome
from starstamp.model.money import Money
from starstamp.model.pricing import PriceItem
from starstamp.model.repair import RepairKind
from starstamp.model.service import NITROGEN
from starstamp.model.units import Expansion, Pressure
from starstamp.reporting import life
from starstamp.service.billing import BillingService
from starstamp.service.disposal import DisposalService
from starstamp.service.filling import FillingService
from starstamp.service.notices import NoticeService
from starstamp.service.receiving import ReceivingService
from starstamp.service.repair import RepairService
from starstamp.service.restate import RestatementService
from starstamp.store.calibration import CalibrationRepository
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book
from starstamp.store.facility import FacilityRepository
from starstamp.store.pricing import PriceRepository

from ..support.factories import (
    make_certificate,
    make_check,
    make_observation,
    make_readings,
)
from ..support.requests import requalify
from ..support.shop import SYSTEM

KEY = CylinderKey("NCI", "A4471")
FIRST_TEST = date(2024, 6, 12)


@pytest.fixture
def priced(shop_book: Book) -> Book:
    prices = PriceRepository(shop_book.connection)
    for code, amount in (
        ("REQUAL_WJ", "14.50"),
        ("CONDEMN", "9.00"),
        ("HANDLING", "5.00"),
    ):
        prices.add(
            PriceItem(
                code=code,
                description=code.lower(),
                amount=Money.parse(amount),
                effective_from=date(2023, 1, 1),
            )
        )
    return shop_book


def open_a_day(book: Book, day: date) -> None:
    """Put the shop in a state where it could work on a later day.

    That means three things and the shop has to do all of them: renew its own
    number, certify the rig into that year, and run the start of day check.
    """
    FacilityRepository(book.connection).renew("A419", date(day.year + 1, 4, 30).isoformat())
    calibration = CalibrationRepository(book.connection)
    for instrument in InstrumentKind.ALL:
        calibration.add_certificate(make_certificate_for(instrument, day))
    calibration.record_check(make_check(day=day))


def make_certificate_for(instrument: str, day: date) -> Certificate:
    return make_certificate(
        instrument,
        serial=f"{instrument[:3].upper()}-{day.year}",
        issued_on=date(day.year, 1, 2),
        valid_until=date(day.year + 4, 1, 2),
    )


def test_a_cylinder_through_a_decade(priced: Book) -> None:
    receiving = ReceivingService(priced)
    cylinders = CylinderRepository(priced.connection)

    # It comes in on a lot, is requalified, and earns its star.
    receiving.receive("WELD1", date(2024, 6, 3), [KEY], promised_on=date(2024, 6, 28))
    first = requalify(priced)
    assert first.outcome is Outcome.PASS
    assert first.star.granted
    assert first.due is not None
    assert first.due.year == 2034

    # The lot goes back and the cylinder is filled.
    receiving.ready("L2024-0001")
    receiving.return_lot("L2024-0001", date(2024, 6, 20))
    assert cylinders.by_key(KEY).status is CylinderStatus.IN_SERVICE
    fill = FillingService(priced).record(
        KEY, NITROGEN, date(2024, 6, 25), "JT7", pressure=Pressure(2015)
    )
    assert fill.judgement.is_within

    # The month is billed.
    invoice = BillingService(priced).raise_invoice(
        "WELD1", date(2024, 6, 1), date(2024, 6, 30), date(2024, 7, 1)
    )
    assert invoice.total == Money.parse("19.50")

    # Eight years later the star is still what decides the fill.
    assert FillingService(priced).eligibility.decision(KEY, NITROGEN, date(2032, 1, 4)).allowed


def test_a_restatement_reaches_back_and_takes_the_star_away(priced: Book) -> None:
    requalify(priced)
    assert FillingService(priced).eligibility.decision(KEY, NITROGEN, date(2030, 1, 4)).allowed

    calibration = CalibrationRepository(priced.connection)
    certificate_id = calibration.id_of(SYSTEM, InstrumentKind.EXPANSION_SCALE, "EXP-1")
    RestatementService(priced).restate_certificate(
        certificate_id, date(2024, 6, 1), "the house restated the scale"
    )

    decision = FillingService(priced).eligibility.decision(KEY, NITROGEN, date(2030, 1, 4))
    assert not decision.allowed
    assert "no standing requalification" in decision.refusals


def test_a_hold_then_a_repair_then_a_pass(priced: Book) -> None:
    held = requalify(priced, observations=(make_observation(DefectKind.THREAD_DAMAGE),))
    assert held.outcome is Outcome.SUSPENDED
    cylinders = CylinderRepository(priced.connection)
    assert cylinders.by_key(KEY).status is CylinderStatus.AWAITING_REPAIR

    repair = RepairService(priced).perform(
        KEY, RepairKind.NECK_THREAD_REPAIR, date(2024, 6, 14), "JT7"
    )
    assert repair.cleared is not None
    assert repair.needs_requalification

    open_a_day(priced, date(2024, 6, 17))
    passed = requalify(priced, day=date(2024, 6, 17))
    assert passed.outcome is Outcome.PASS
    assert cylinders.by_key(KEY).status is CylinderStatus.IN_SERVICE


def test_the_end_of_a_cylinder(priced: Book) -> None:
    requalify(priced)
    open_a_day(priced, date(2034, 6, 12))
    condemned = requalify(
        priced,
        day=date(2034, 6, 12),
        readings=make_readings(
            total_expansion=Expansion.parse("100.0"),
            permanent_expansion=Expansion.parse("12.0"),
        ),
    )
    assert condemned.outcome is Outcome.CONDEMN

    letters = NoticeService(priced).draft_condemnations(date(2034, 6, 13))
    assert letters.count == 1
    disposal = DisposalService(priced).dispose(
        KEY, DisposalMethod.DRILLED, date(2034, 6, 20), "JT7", scrap_ticket="SC-77"
    )
    assert disposal.scrap_ticket == "SC-77"

    cylinders = CylinderRepository(priced.connection)
    assert cylinders.by_key(KEY).status is CylinderStatus.SCRAPPED
    timeline = life.build(priced, KEY)
    kinds = [entry.kind for entry in timeline.entries]
    assert kinds == ["test", "test", "notice", "disposal"]

    with pytest.raises(RuleViolationError):
        requalify(priced, day=date(2034, 6, 21))
