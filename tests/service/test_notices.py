from datetime import date

from starstamp.model.cylinder import CylinderKey
from starstamp.model.defect import DefectKind
from starstamp.model.method import Method
from starstamp.model.notice import NoticeKind
from starstamp.service.notices import NoticeService
from starstamp.service.requalify import RequalificationRequest, RequalificationService
from starstamp.store.db import Book

from ..support.factories import make_cylinder, make_observation, make_readings
from ..support.shop import DAY, SYSTEM, stock

KEY = CylinderKey("NCI", "A4471")


def requalify(book: Book, key: CylinderKey = KEY, **changes: object) -> None:
    base: dict[str, object] = {
        "key": key,
        "day": DAY,
        "technician_badge": "JT7",
        "method": Method.VOLUMETRIC,
        "system_code": SYSTEM,
        "readings": make_readings(),
    }
    base.update(changes)
    RequalificationService(book).perform(RequalificationRequest(**base))  # type: ignore[arg-type]


def test_a_condemnation_produces_a_letter(shop_book: Book) -> None:
    requalify(shop_book, observations=(make_observation(DefectKind.BULGE),))
    drafted = NoticeService(shop_book).draft_condemnations(date(2024, 6, 13))
    assert drafted.count == 1
    notice = drafted.notices[0]
    assert notice.kind is NoticeKind.CONDEMNATION
    assert "may not be filled again" in notice.body
    assert "bulge" in notice.body
    assert notice.due_by() == date(2024, 7, 13)


def test_the_same_condemnation_is_not_written_about_twice(shop_book: Book) -> None:
    requalify(shop_book, observations=(make_observation(DefectKind.BULGE),))
    service = NoticeService(shop_book)
    service.draft_condemnations(date(2024, 6, 13))
    assert service.draft_condemnations(date(2024, 6, 20)).count == 0


def test_nothing_to_write(shop_book: Book) -> None:
    drafted = NoticeService(shop_book).draft_condemnations(DAY)
    assert drafted.count == 0
    assert drafted.describe() == "nothing to write"


def test_reminders_for_what_is_coming_due(shop_book: Book) -> None:
    requalify(shop_book)
    drafted = NoticeService(shop_book).draft_reminders(date(2034, 4, 1), 3)
    assert drafted.count == 1
    notice = drafted.of_kind(NoticeKind.DUE_SOON)[0]
    assert "falls due for requalification in 2034-06" in notice.body
    assert "2 months from now" in notice.body


def test_a_cylinder_already_out_of_test_gets_a_different_letter(shop_book: Book) -> None:
    requalify(shop_book)
    drafted = NoticeService(shop_book).draft_reminders(date(2035, 1, 1), 3)
    notice = drafted.of_kind(NoticeKind.OUT_OF_TEST)[0]
    assert "went out of test in 2034-06" in notice.body


def test_reminders_can_be_narrowed_to_an_account(shop_book: Book) -> None:
    requalify(shop_book)
    other = stock(shop_book, make_cylinder(key=CylinderKey("PST", "B12")))
    requalify(shop_book, other)
    service = NoticeService(shop_book)
    assert service.draft_reminders(date(2034, 4, 1), 3, owner_code="WELD1").count == 2


def test_sending_a_letter(shop_book: Book) -> None:
    requalify(shop_book, observations=(make_observation(DefectKind.BULGE),))
    service = NoticeService(shop_book)
    drafted = service.draft_condemnations(date(2024, 6, 13))
    notice = drafted.notices[0]
    assert notice.notice_id is not None
    sent = service.send(notice.notice_id, date(2024, 6, 14))
    assert sent.state.is_sent


def test_letters_the_shop_is_late_with(shop_book: Book) -> None:
    requalify(shop_book, observations=(make_observation(DefectKind.BULGE),))
    service = NoticeService(shop_book)
    service.draft_condemnations(date(2024, 6, 13))
    assert service.overdue_letters(date(2024, 7, 1)) == []
    late = service.overdue_letters(date(2024, 7, 20))
    assert len(late) == 1
    assert "not sent" in late[0].summary()


def test_a_sent_letter_is_never_late(shop_book: Book) -> None:
    requalify(shop_book, observations=(make_observation(DefectKind.BULGE),))
    service = NoticeService(shop_book)
    drafted = service.draft_condemnations(date(2024, 6, 13))
    notice_id = drafted.notices[0].notice_id
    assert notice_id is not None
    service.send(notice_id, date(2024, 6, 14))
    assert service.overdue_letters(date(2025, 1, 1)) == []


def test_the_drafted_summary(shop_book: Book) -> None:
    requalify(shop_book, observations=(make_observation(DefectKind.BULGE),))
    drafted = NoticeService(shop_book).draft_condemnations(date(2024, 6, 13))
    assert "1 notices drafted" in drafted.describe()
    assert "NCI/A4471 condemnation" in drafted.describe()
