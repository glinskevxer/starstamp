import pytest

from starstamp.cli.remark import parse_evidence, parse_mark
from starstamp.errors import ValidationError
from starstamp.model.marking import Evidence, MarkKind

from .conftest import DAY, Invoke


def requalify(shop: Invoke) -> None:
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
    )


def test_marks_parse() -> None:
    mark = parse_mark("tare=TW 117.5")
    assert mark.kind is MarkKind.TARE_WEIGHT
    assert mark.reads == "TW 117.5"
    assert parse_mark("spec=DOT-3AA2015").kind is MarkKind.SPECIFICATION


@pytest.mark.parametrize("text", ["tare", "=x", "wobble=1"])
def test_bad_marks(text: str) -> None:
    with pytest.raises(ValidationError):
        parse_mark(text)


def test_evidence_parses() -> None:
    assert parse_evidence("ours") is Evidence.OUR_RECORDS
    assert parse_evidence("owner") is Evidence.OWNER_DECLARATION
    assert parse_evidence("manufacturer letter") is Evidence.MANUFACTURER_LETTER
    with pytest.raises(ValidationError, match="evidence is one of"):
        parse_evidence("hearsay")


def test_stamping_a_mark(running_shop: Invoke) -> None:
    requalify(running_shop)
    out = running_shop(
        "remark",
        "stamp",
        "NCI/A4471",
        "--mark",
        "tare=TW 117.5",
        "--from",
        "ours",
        "--tech",
        "jt7",
        "--on",
        "2024-06-14",
    ).output
    assert "re-marked under A419" in out
    assert "on 1 records of ours" in out


def test_a_mark_the_shop_cannot_support(running_shop: Invoke) -> None:
    result = running_shop(
        "remark",
        "stamp",
        "NCI/A4471",
        "--mark",
        "serial=A4471",
        "--from",
        "owner",
        "--tech",
        "jt7",
        "--on",
        "2024-06-14",
        expect=5,
    )
    assert "not evidence for the serial" in result.output


def test_the_history(running_shop: Invoke) -> None:
    assert "never been re-marked" in running_shop("remark", "history", "NCI/A4471").output
    requalify(running_shop)
    running_shop(
        "remark",
        "stamp",
        "NCI/A4471",
        "--mark",
        "tare=TW 117.5",
        "--from",
        "ours",
        "--tech",
        "jt7",
        "--on",
        "2024-06-14",
    )
    out = running_shop("remark", "history", "NCI/A4471").output
    assert "tare weight TW 117.5" in out
    assert "our records" in out


def test_what_could_be_restored(running_shop: Invoke) -> None:
    out = running_shop("remark", "available", "NCI/A4471").output
    assert "0 standing records of test here" in out
    assert "DOT-3AA2015" in out
    assert "A4471" in out


def test_the_remarking_lands_on_the_life(running_shop: Invoke) -> None:
    requalify(running_shop)
    running_shop(
        "remark",
        "stamp",
        "NCI/A4471",
        "--mark",
        "tare=TW 117.5",
        "--from",
        "ours",
        "--tech",
        "jt7",
        "--on",
        "2024-06-14",
    )
    assert "remark" in running_shop("cylinder", "life", "NCI/A4471").output
