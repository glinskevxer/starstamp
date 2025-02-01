import pytest

from .conftest import DAY, Invoke


@pytest.fixture
def condemned(running_shop: Invoke) -> Invoke:
    running_shop(
        "requal",
        "run",
        "NCI/A4471",
        "--tech",
        "jt7",
        "--system",
        "WJ-1",
        "--on",
        DAY,
        "--applied",
        "3358",
        "--total",
        "110.0",
        "--permanent",
        "2.0",
        "--defect",
        "bulge",
    )
    return running_shop


def test_drafting_a_condemnation_letter(condemned: Invoke) -> None:
    out = condemned("notice", "draft", "--on", "2024-06-13").output
    assert "1 notices drafted" in out
    assert "NCI/A4471 condemnation" in out


def test_reading_the_letter(condemned: Invoke) -> None:
    condemned("notice", "draft", "--on", "2024-06-13")
    out = condemned("notice", "show", "1").output
    assert "To: WELD1" in out
    assert "may not be filled again" in out
    assert "bulge" in out


def test_listing_and_sending(condemned: Invoke) -> None:
    condemned("notice", "draft", "--on", "2024-06-13")
    listed = condemned("notice", "list").output
    assert "condemnation" in listed
    assert "2024-07-13" in listed
    assert "sent 2024-06-14" in condemned("notice", "send", "1", "--on", "2024-06-14").output
    assert "no notices" in condemned("notice", "list", "--unsent").output


def test_nothing_to_draft(running_shop: Invoke) -> None:
    assert "nothing to write" in running_shop("notice", "draft").output


def test_late_letters(condemned: Invoke) -> None:
    condemned("notice", "draft", "--on", "2024-06-13")
    assert "nothing late" in condemned("--today", "2024-07-01", "notice", "late").output
    late = condemned("--today", "2024-07-20", "notice", "late").output
    assert "NCI/A4471 condemnation, not sent" in late


def test_reminders(running_shop: Invoke) -> None:
    running_shop(
        "requal",
        "run",
        "NCI/A4471",
        "--tech",
        "jt7",
        "--system",
        "WJ-1",
        "--on",
        DAY,
        "--applied",
        "3358",
        "--total",
        "110.0",
        "--permanent",
        "2.0",
    )
    out = running_shop(
        "notice", "draft", "--reminders", "--within", "3", "--on", "2034-04-01"
    ).output
    assert "due soon" in out


def test_listing_by_owner(condemned: Invoke) -> None:
    condemned("notice", "draft", "--on", "2024-06-13")
    condemned("notice", "send", "1", "--on", "2024-06-14")
    assert "condemnation" in condemned("notice", "list", "--owner", "weld1").output
