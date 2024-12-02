from datetime import date

import pytest

from starstamp.errors import ValidationError
from starstamp.model.disposal import Disposal, DisposalMethod

CONDEMNED = date(2024, 6, 12)


def a_disposal(**changes: object) -> Disposal:
    base: dict[str, object] = {
        "cylinder_key": "NCI/A4471",
        "method": DisposalMethod.DRILLED,
        "performed_on": date(2024, 6, 20),
        "technician_badge": "JT7",
        "condemned_on": CONDEMNED,
    }
    base.update(changes)
    return Disposal(**base)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("drill", DisposalMethod.DRILLED),
        ("neck", DisposalMethod.NECK_CUT),
        ("crush", DisposalMethod.CRUSHED),
        ("saw", DisposalMethod.SAWN),
        ("hold", DisposalMethod.HELD_FOR_OWNER),
    ],
)
def test_disposal_shorthand(text: str, expected: DisposalMethod) -> None:
    assert DisposalMethod.parse(text) is expected


def test_an_unknown_disposal() -> None:
    with pytest.raises(ValidationError, match="the shop does"):
        DisposalMethod.parse("recycled")


def test_holding_does_not_render_it() -> None:
    assert DisposalMethod.DRILLED.renders_it_useless
    assert not DisposalMethod.HELD_FOR_OWNER.renders_it_useless
    assert DisposalMethod.NECK_CUT.label == "neck cut"


def test_a_disposal_before_the_condemnation() -> None:
    with pytest.raises(ValidationError, match="before it was condemned"):
        a_disposal(performed_on=date(2024, 6, 1))


def test_a_cylinder_going_home_has_to_be_rendered() -> None:
    with pytest.raises(ValidationError, match="has to be rendered first"):
        a_disposal(method=DisposalMethod.HELD_FOR_OWNER, returned_to_owner=True)
    assert a_disposal(returned_to_owner=True).returned_to_owner


def test_a_witness_is_somebody_else() -> None:
    with pytest.raises(ValidationError, match="somebody else"):
        a_disposal(witness_badge="JT7")
    assert a_disposal(witness_badge="MR2").witness_badge == "MR2"


def test_the_clock_runs_from_the_condemnation() -> None:
    assert a_disposal().due_by == date(2024, 7, 12)
    assert not a_disposal().is_late
    assert a_disposal(performed_on=date(2024, 7, 13)).is_late
    assert a_disposal(performed_on=date(2024, 7, 13)).days_taken == 31


def test_holding_a_cylinder_is_never_late() -> None:
    held = a_disposal(method=DisposalMethod.HELD_FOR_OWNER, performed_on=date(2025, 1, 1))
    assert not held.is_late


def test_summaries() -> None:
    line = a_disposal(witness_badge="MR2", scrap_ticket="SC-4411", returned_to_owner=True).summary()
    assert "drilled by JT7" in line
    assert "witnessed by MR2" in line
    assert "ticket SC-4411" in line
    assert "returned to the owner" in line
    assert "days after condemnation" in a_disposal(performed_on=date(2024, 7, 20)).summary()
