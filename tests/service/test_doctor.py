from datetime import date

from starstamp.model.cylinder import CylinderKey
from starstamp.model.defect import DefectKind
from starstamp.model.method import Method
from starstamp.service.doctor import Doctor
from starstamp.service.requalify import RequalificationRequest, RequalificationService
from starstamp.store.db import Book

from ..support.factories import make_observation, make_readings
from ..support.shop import DAY, SYSTEM

KEY = CylinderKey("NCI", "A4471")


def test_a_healthy_book_passes_everything(shop_book: Book) -> None:
    report = Doctor(shop_book).run(DAY)
    assert report.is_clean
    assert [result.name for result in report.results] == ["schema", "file", "records"]
    assert "nothing to answer for" in report.describe()


def test_a_book_behind_the_code_fails_the_schema_check(shop_book: Book) -> None:
    shop_book.connection.execute("DELETE FROM schema_migration WHERE number > 3")
    report = Doctor(shop_book).run(DAY)
    assert not report.is_clean
    names = [result.name for result in report.failures]
    assert "schema" in names
    assert "migrations to apply" in report.results[0].detail


def test_a_warning_does_not_fail_the_records_check(shop_book: Book) -> None:
    RequalificationService(shop_book).perform(
        RequalificationRequest(
            key=KEY,
            day=DAY,
            technician_badge="JT7",
            method=Method.VOLUMETRIC,
            system_code=SYSTEM,
            readings=make_readings(),
            observations=(make_observation(DefectKind.BULGE),),
        )
    )
    report = Doctor(shop_book).run(DAY)
    records = report.results[-1]
    assert records.passed
    assert "1 warnings" in records.detail


def test_a_real_problem_fails_it(shop_book: Book) -> None:
    shop_book.connection.execute("PRAGMA foreign_keys = OFF")
    shop_book.connection.execute(
        "INSERT INTO lot (number, owner_id, received_on) VALUES ('L2024-0009', 999, '2024-06-03')"
    )
    report = Doctor(shop_book).run(DAY)
    assert not report.is_clean
    assert "file" in [result.name for result in report.failures]


def test_every_check_says_something(shop_book: Book) -> None:
    report = Doctor(shop_book).run(DAY)
    for result in report.results:
        assert result.detail
        assert str(result).startswith("ok  ")


def test_the_records_check_names_the_first_problem(shop_book: Book) -> None:
    from starstamp.model.cylinder import CylinderStatus
    from starstamp.store.cylinders import CylinderRepository

    CylinderRepository(shop_book.connection).set_status(KEY, CylinderStatus.CONDEMNED)
    report = Doctor(shop_book).run(date(2024, 6, 20))
    assert "no condemning record" in report.results[-1].detail
