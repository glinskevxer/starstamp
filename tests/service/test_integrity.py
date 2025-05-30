from datetime import date

from starstamp.model.cylinder import CylinderKey, CylinderStatus
from starstamp.model.defect import DefectKind
from starstamp.service.integrity import IntegrityService, Severity
from starstamp.service.notices import NoticeService
from starstamp.service.receiving import ReceivingService
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book

from ..support.factories import make_observation
from ..support.requests import requalify
from ..support.shop import DAY

KEY = CylinderKey("NCI", "A4471")


def test_a_clean_book(shop_book: Book) -> None:
    report = IntegrityService(shop_book).run(DAY)
    assert report.is_clean
    assert "nothing to answer for" in report.describe()
    assert report.checked == 1


def test_a_condemnation_with_no_letter_is_a_warning(shop_book: Book) -> None:
    requalify(shop_book, observations=(make_observation(DefectKind.BULGE),))
    report = IntegrityService(shop_book).run(DAY)
    assert not report.is_clean
    assert report.problems == ()
    assert "has not been written to" in report.findings[0].detail


def test_the_warning_goes_away_once_the_letter_is_drafted(shop_book: Book) -> None:
    requalify(shop_book, observations=(make_observation(DefectKind.BULGE),))
    NoticeService(shop_book).draft_condemnations(DAY)
    assert IntegrityService(shop_book).run(DAY).is_clean


def test_a_condemned_cylinder_that_reads_in_service(shop_book: Book) -> None:
    requalify(shop_book, observations=(make_observation(DefectKind.BULGE),))
    NoticeService(shop_book).draft_condemnations(DAY)
    shop_book.connection.execute("UPDATE cylinder SET status = 'in_service'")
    report = IntegrityService(shop_book).run(DAY)
    assert report.problems
    assert "was condemned but reads in_service" in report.problems[0].detail


def test_a_cylinder_that_reads_condemned_with_no_record(shop_book: Book) -> None:
    CylinderRepository(shop_book.connection).set_status(KEY, CylinderStatus.CONDEMNED)
    report = IntegrityService(shop_book).run(DAY)
    assert report.findings[0].severity is Severity.WARNING
    assert "no condemning record" in report.findings[0].detail


def test_a_pass_after_a_condemnation(shop_book: Book) -> None:
    requalify(shop_book, observations=(make_observation(DefectKind.BULGE),))
    NoticeService(shop_book).draft_condemnations(DAY)
    shop_book.connection.execute("UPDATE cylinder SET status = 'in_service'")
    requalify(shop_book, day=date(2024, 6, 12))
    report = IntegrityService(shop_book).run(DAY)
    details = " ".join(finding.detail for finding in report.problems)
    assert "after being condemned" in details


def test_a_record_with_no_certificate_behind_it(shop_book: Book) -> None:
    requalify(shop_book)
    shop_book.connection.execute("UPDATE calibration_certificate SET system_code = 'WJ-9'")
    report = IntegrityService(shop_book).run(DAY)
    assert report.problems
    assert "certificate on file" in report.problems[0].detail


def test_a_lot_line_settled_against_a_reversal(shop_book: Book) -> None:
    ReceivingService(shop_book).receive("WELD1", date(2024, 6, 3), [KEY])
    requalify(shop_book)
    IntegrityService(shop_book).events.reverse(1, "rig out of calibration")
    report = IntegrityService(shop_book).run(DAY)
    details = " ".join(finding.detail for finding in report.problems)
    assert "which was reversed" in details


def test_a_book_behind_the_code(shop_book: Book) -> None:
    shop_book.connection.execute("DELETE FROM schema_migration WHERE number > 4")
    report = IntegrityService(shop_book).run(DAY)
    assert "schema is at 4" in report.problems[0].detail
    assert "problems" in report.describe()


def test_a_letter_past_its_deadline_is_a_problem(shop_book: Book) -> None:
    requalify(shop_book, observations=(make_observation(DefectKind.BULGE),))
    NoticeService(shop_book).draft_condemnations(DAY)
    assert IntegrityService(shop_book).run(date(2024, 7, 1)).is_clean
    report = IntegrityService(shop_book).run(date(2024, 7, 20))
    assert report.problems
    assert "should have been written to by 2024-07-12" in report.problems[0].detail


def test_a_test_recorded_by_somebody_who_had_lapsed(shop_book: Book) -> None:
    from starstamp.store.facility import TechnicianRepository

    requalify(shop_book)
    TechnicianRepository(shop_book.connection).renew("JT7", date(2024, 1, 1))
    report = IntegrityService(shop_book).run(DAY)
    assert report.problems
    assert "was not signed off for volumetric on 2024-06-12" in report.problems[0].detail


def test_a_badge_that_is_not_on_the_bench_is_a_warning(shop_book: Book) -> None:
    requalify(shop_book)
    shop_book.connection.execute("DELETE FROM technician")
    report = IntegrityService(shop_book).run(DAY)
    assert report.problems == ()
    assert "not on the bench" in report.findings[0].detail


def test_an_account_with_cylinders_here_and_no_address(shop_book: Book) -> None:
    from starstamp.store.cylinders import CylinderRepository

    shop_book.connection.execute("UPDATE owner_account SET address = NULL")
    CylinderRepository(shop_book.connection).set_status(KEY, CylinderStatus.IN_SHOP)
    report = IntegrityService(shop_book).run(DAY)
    assert "no address or email on file" in report.findings[0].detail
    assert report.problems == ()


def test_an_account_with_an_address_is_fine(shop_book: Book) -> None:
    from starstamp.store.cylinders import CylinderRepository

    CylinderRepository(shop_book.connection).set_status(KEY, CylinderStatus.IN_SHOP)
    assert IntegrityService(shop_book).run(DAY).is_clean


def test_an_account_with_nothing_here_is_not_flagged(shop_book: Book) -> None:
    assert IntegrityService(shop_book).run(DAY).is_clean
