from datetime import date

import pytest

from starstamp.errors import ValidationError
from starstamp.model.notice import Notice, NoticeKind, NoticeState

RAISED = date(2024, 6, 12)


def a_notice(**changes: object) -> Notice:
    base: dict[str, object] = {
        "owner_code": "WELD1",
        "cylinder_key": "NCI/A4471",
        "kind": NoticeKind.CONDEMNATION,
        "raised_on": RAISED,
        "body": "your cylinder has been condemned",
        "event_id": 1,
    }
    base.update(changes)
    return Notice(**base)  # type: ignore[arg-type]


def test_an_empty_notice() -> None:
    with pytest.raises(ValidationError, match="not a notice"):
        a_notice(body="   ")


def test_the_state_and_the_date_have_to_agree() -> None:
    with pytest.raises(ValidationError, match="have to agree"):
        a_notice(state=NoticeState.SENT)
    with pytest.raises(ValidationError, match="have to agree"):
        a_notice(sent_on=date(2024, 6, 14))
    sent = a_notice(state=NoticeState.SENT, sent_on=date(2024, 6, 14))
    assert sent.state.is_sent


def test_a_notice_cannot_go_out_before_it_was_drafted() -> None:
    with pytest.raises(ValidationError, match="before it was drafted"):
        a_notice(state=NoticeState.SENT, sent_on=date(2024, 6, 1))


def test_a_condemnation_notice_names_the_record() -> None:
    with pytest.raises(ValidationError, match="name the record of test"):
        a_notice(event_id=None)


def test_only_a_condemnation_has_a_deadline() -> None:
    assert a_notice().due_by() == date(2024, 7, 12)
    reminder = a_notice(kind=NoticeKind.DUE_SOON, event_id=None)
    assert reminder.due_by() is None
    assert reminder.days_left(RAISED) is None
    assert not reminder.is_late(date(2030, 1, 1))


def test_lateness_stops_once_it_is_sent() -> None:
    notice = a_notice()
    assert not notice.is_late(date(2024, 7, 12))
    assert notice.is_late(date(2024, 7, 13))
    assert notice.days_left(date(2024, 7, 2)) == 10
    sent = a_notice(state=NoticeState.SENT, sent_on=date(2024, 6, 14))
    assert not sent.is_late(date(2030, 1, 1))


def test_which_notices_are_required() -> None:
    assert NoticeKind.CONDEMNATION.is_required
    assert not NoticeKind.DUE_SOON.is_required
    assert NoticeKind.HELD_FOR_REPAIR.label == "held for repair"


def test_summaries() -> None:
    assert a_notice().summary().endswith("condemnation, not sent")
    sent = a_notice(state=NoticeState.SENT, sent_on=date(2024, 6, 14))
    assert sent.summary().endswith("sent 2024-06-14")
