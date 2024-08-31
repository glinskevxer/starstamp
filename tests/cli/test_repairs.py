from .conftest import Invoke
from .test_endtoend import DAY, running_shop  # noqa: F401


def requalify(shop: Invoke, *extra: str, expect: int = 0) -> None:
    shop(
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
        *extra,
        expect=expect,
    )


def test_ordinary_work(running_shop: Invoke) -> None:  # noqa: F811
    out = running_shop(
        "repair", "do", "NCI/A4471", "paint", "--tech", "jt7", "--on", "2024-06-14"
    ).output
    assert "painting" in out
    assert "requalify before filling" not in out


def test_work_on_the_metal_sends_it_back(running_shop: Invoke) -> None:  # noqa: F811
    out = running_shop(
        "repair", "do", "NCI/A4471", "heat treat", "--tech", "jt7", "--on", "2024-06-14"
    ).output
    assert "requalify before filling" in out


def test_a_repair_the_cylinder_does_not_take(running_shop: Invoke) -> None:  # noqa: F811
    result = running_shop(
        "repair", "do", "NCI/A4471", "weld", "--tech", "jt7", "--on", "2024-06-14", expect=5
    )
    assert "condemns it" in result.output


def test_clearing_a_hold(running_shop: Invoke) -> None:  # noqa: F811
    requalify(running_shop, "--defect", "threads")
    assert "NCI/A4471" in running_shop("repair", "held").output
    out = running_shop(
        "repair", "do", "NCI/A4471", "threads", "--tech", "jt7", "--on", "2024-06-14"
    ).output
    assert "clears the hold from 2024-06-12" in out
    assert "nothing held" in running_shop("repair", "held").output


def test_the_history(running_shop: Invoke) -> None:  # noqa: F811
    assert "no repairs on NCI/A4471" in running_shop("repair", "history", "NCI/A4471").output
    running_shop(
        "repair",
        "do",
        "NCI/A4471",
        "valve",
        "--tech",
        "jt7",
        "--on",
        "2024-06-14",
        "--parts",
        "CGA 580 brass",
    )
    out = running_shop("repair", "history", "NCI/A4471").output
    assert "valve replacement" in out
    assert "CGA 580 brass" in out


def test_a_valve_change_without_the_valve(running_shop: Invoke) -> None:  # noqa: F811
    running_shop(
        "repair", "do", "NCI/A4471", "valve", "--tech", "jt7", "--on", "2024-06-14", expect=2
    )


def test_the_options_for_a_cylinder(running_shop: Invoke) -> None:  # noqa: F811
    out = running_shop("repair", "options", "NCI/A4471").output
    assert "DOT-3AA2015" in out
    assert "heat treatment" in out
    assert "weld repair" not in out


def test_the_options_name_a_hold(running_shop: Invoke) -> None:  # noqa: F811
    requalify(running_shop, "--defect", "threads")
    assert "held since 2024-06-12" in running_shop("repair", "options", "NCI/A4471").output
