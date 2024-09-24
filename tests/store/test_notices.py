from datetime import date

import pytest

from starstamp.errors import ConflictError, NotFoundError
from starstamp.model.cylinder import CylinderKey
from starstamp.model.notice import Notice, NoticeKind
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book
from starstamp.store.notices import NoticeRepository
from starstamp.store.owners import OwnerRepository

from ..support.factories import make_cylinder

KEY = CylinderKey("NCI", "A4471")
RAISED = date(2024, 6, 12)


@pytest.fixture
def notices(book: Book, owners: OwnerRepository, cylinders: CylinderRepository) -> NoticeRepository:
    cylinders.add(make_cylinder(key=KEY), owners.id_of("WELD1"), date(2024, 1, 2))
    return NoticeRepository(book.connection)


def a_notice(**changes: object) -> Notice:
    base: dict[str, object] = {
        "owner_code": "WELD1",
        "cylinder_key": str(KEY),
        "kind": NoticeKind.DUE_SOON,
        "raised_on": RAISED,
        "body": "your cylinder falls due in June",
    }
    base.update(changes)
    return Notice(**base)  # type: ignore[arg-type]


def test_a_notice_round_trips(
    notices: NoticeRepository, owners: OwnerRepository, cylinders: CylinderRepository
) -> None:
    written = notices.add(a_notice(), owners.id_of("WELD1"), cylinders.id_of(KEY))
    assert written.notice_id is not None
    read_back = notices.by_id(written.notice_id)
    assert read_back.owner_code == "WELD1"
    assert read_back.cylinder_key == "NCI/A4471"
    assert read_back.kind is NoticeKind.DUE_SOON


def test_sending_a_notice(
    notices: NoticeRepository, owners: OwnerRepository, cylinders: CylinderRepository
) -> None:
    written = notices.add(a_notice(), owners.id_of("WELD1"), cylinders.id_of(KEY))
    assert written.notice_id is not None
    sent = notices.send(written.notice_id, date(2024, 6, 14))
    assert sent.state.is_sent
    assert sent.sent_on == date(2024, 6, 14)
    with pytest.raises(ConflictError, match="went out on"):
        notices.send(written.notice_id, date(2024, 6, 15))


def test_sending_before_drafting(
    notices: NoticeRepository, owners: OwnerRepository, cylinders: CylinderRepository
) -> None:
    written = notices.add(a_notice(), owners.id_of("WELD1"), cylinders.id_of(KEY))
    assert written.notice_id is not None
    with pytest.raises(ConflictError, match="was drafted on"):
        notices.send(written.notice_id, date(2024, 6, 1))


def test_listings(
    notices: NoticeRepository, owners: OwnerRepository, cylinders: CylinderRepository
) -> None:
    first = notices.add(a_notice(), owners.id_of("WELD1"), cylinders.id_of(KEY))
    notices.add(
        a_notice(kind=NoticeKind.OUT_OF_TEST, raised_on=date(2024, 7, 1)),
        owners.id_of("WELD1"),
        cylinders.id_of(KEY),
    )
    assert len(notices.for_owner("weld1")) == 2
    assert len(notices.unsent()) == 2
    assert first.notice_id is not None
    notices.send(first.notice_id, date(2024, 6, 14))
    assert len(notices.unsent()) == 1
    assert notices.count() == 2


def test_notices_against_a_record_of_test(notices: NoticeRepository) -> None:
    assert notices.for_event(4) == []


def test_a_missing_notice(notices: NoticeRepository) -> None:
    with pytest.raises(NotFoundError, match="no notice 99"):
        notices.by_id(99)
