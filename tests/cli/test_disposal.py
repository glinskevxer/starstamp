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


def test_rendering_a_cylinder(condemned: Invoke) -> None:
    out = condemned(
        "scrap",
        "render",
        "NCI/A4471",
        "drill",
        "--tech",
        "jt7",
        "--witness",
        "mr2",
        "--ticket",
        "SC-4411",
        "--on",
        "2024-06-20",
    ).output
    assert "drilled by JT7" in out
    assert "ticket SC-4411" in out
    assert "scrapped" in condemned("cylinder", "show", "NCI/A4471").output


def test_a_cylinder_that_was_not_condemned(running_shop: Invoke) -> None:
    result = running_shop(
        "scrap", "render", "NCI/A4471", "drill", "--tech", "jt7", "--on", "2024-06-20", expect=5
    )
    assert "only a condemned cylinder" in result.output


def test_what_is_waiting(condemned: Invoke) -> None:
    out = condemned("scrap", "outstanding", "--on", "2024-06-20").output
    assert "condemned 2024-06-12" in out
    assert "due by 2024-07-12" in out
    assert "LATE" not in out
    late = condemned("scrap", "outstanding", "--on", "2024-07-20", "--late-only").output
    assert "LATE" in late


def test_nothing_waiting(running_shop: Invoke) -> None:
    assert "nothing waiting" in running_shop("scrap", "outstanding").output


def test_the_log(condemned: Invoke) -> None:
    assert (
        "nothing in that window"
        in condemned("scrap", "log", "--from", "2024-06-01", "--to", "2024-06-30").output
    )
    condemned("scrap", "render", "NCI/A4471", "crush", "--tech", "jt7", "--on", "2024-06-20")
    out = condemned("scrap", "log", "--from", "2024-06-01", "--to", "2024-06-30").output
    assert "crushed" in out
    assert "NCI/A4471" in out


def test_the_check_flags_a_cylinder_left_on_the_floor(condemned: Invoke) -> None:
    condemned("notice", "draft", "--on", "2024-06-13")
    condemned("notice", "send", "1", "--on", "2024-06-14")
    result = condemned("check", "--on", "2024-07-20", expect=7)
    assert "not rendered" in result.output
