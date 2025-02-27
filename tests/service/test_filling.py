from datetime import date

import pytest

from starstamp.errors import NotFoundError, RuleViolationError
from starstamp.model.cylinder import CylinderKey
from starstamp.model.method import Method
from starstamp.model.service import NITROGEN, OXYGEN
from starstamp.model.units import Pressure
from starstamp.rules.filling import FillVerdict
from starstamp.service.filling import FillingService
from starstamp.service.requalify import RequalificationRequest, RequalificationService
from starstamp.store.db import Book

from ..support.factories import make_readings
from ..support.shop import DAY, SYSTEM

KEY = CylinderKey("NCI", "A4471")
FILLED = date(2024, 6, 20)


def requalify(book: Book) -> None:
    RequalificationService(book).perform(
        RequalificationRequest(
            key=KEY,
            day=DAY,
            technician_badge="JT7",
            method=Method.VOLUMETRIC,
            system_code=SYSTEM,
            readings=make_readings(),
        )
    )


def test_a_fill_on_a_cylinder_in_test(shop_book: Book) -> None:
    requalify(shop_book)
    outcome = FillingService(shop_book).record(
        KEY, NITROGEN, FILLED, "JT7", pressure=Pressure(2015)
    )
    assert outcome.judgement.is_within
    assert not outcome.overridden
    assert outcome.record.fill_id is not None


def test_a_cylinder_out_of_test_is_refused(shop_book: Book) -> None:
    with pytest.raises(RuleViolationError, match="may not be filled"):
        FillingService(shop_book).record(KEY, NITROGEN, FILLED, "JT7", pressure=Pressure(2015))


def test_a_refusal_can_be_recorded_deliberately(shop_book: Book) -> None:
    outcome = FillingService(shop_book).record(
        KEY, NITROGEN, FILLED, "JT7", pressure=Pressure(2015), override=True
    )
    assert outcome.overridden
    assert "recorded over a refusal" in outcome.describe()


def test_the_wrong_gas_is_refused(shop_book: Book) -> None:
    requalify(shop_book)
    with pytest.raises(RuleViolationError, match="valve fitted"):
        FillingService(shop_book).record(KEY, OXYGEN, FILLED, "JT7", pressure=Pressure(2015))


def test_the_plus_rating_from_the_bench_is_used(shop_book: Book) -> None:
    requalify(shop_book)
    outcome = FillingService(shop_book).record(
        KEY, NITROGEN, FILLED, "JT7", pressure=Pressure(2200)
    )
    assert outcome.judgement.is_within
    assert outcome.judgement.ceiling == Pressure(2217)


def test_an_overfill_is_recorded_as_one(shop_book: Book) -> None:
    requalify(shop_book)
    service = FillingService(shop_book)
    outcome = service.record(KEY, NITROGEN, FILLED, "JT7", pressure=Pressure(2400))
    assert outcome.judgement.verdict is FillVerdict.OVERFILLED
    assert len(service.overfills(date(2024, 6, 1), date(2024, 6, 30))) == 1
    assert "overfilled" in outcome.describe()


def test_a_hot_fill_is_judged_where_it_settles(shop_book: Book) -> None:
    requalify(shop_book)
    outcome = FillingService(shop_book).record(
        KEY, NITROGEN, FILLED, "JT7", pressure=Pressure(2400), temperature_f=120
    )
    assert outcome.judgement.is_within


def test_the_history_comes_back(shop_book: Book) -> None:
    requalify(shop_book)
    service = FillingService(shop_book)
    service.record(KEY, NITROGEN, FILLED, "JT7", pressure=Pressure(2015))
    service.record(KEY, NITROGEN, date(2024, 7, 1), "JT7", pressure=Pressure(1900))
    assert len(service.history(KEY)) == 2


def test_a_filler_who_is_not_on_the_bench(shop_book: Book) -> None:
    requalify(shop_book)
    with pytest.raises(NotFoundError, match="no technician ZZ9"):
        FillingService(shop_book).record(KEY, NITROGEN, FILLED, "zz9", pressure=Pressure(2015))
