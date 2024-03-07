import pytest

from starstamp.errors import ValidationError
from starstamp.model.defect import DefectKind, Observation, parse_thousandths


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("pitting", DefectKind.ISOLATED_PITTING),
        ("gouge", DefectKind.CUT_GOUGE_DIG),
        ("fire", DefectKind.FIRE_DAMAGE),
        ("arc burn", DefectKind.ARC_BURN),
        ("line-corrosion", DefectKind.LINE_CORROSION),
        ("threads", DefectKind.THREAD_DAMAGE),
    ],
)
def test_defect_shorthand(text: str, expected: DefectKind) -> None:
    assert DefectKind.parse(text) is expected


def test_unknown_defect() -> None:
    with pytest.raises(ValidationError, match="unknown defect"):
        DefectKind.parse("wobbly")


@pytest.mark.parametrize(
    ("text", "thousandths"),
    [("0.016", 16), ("0.1", 100), ("1", 1000), ("0.005", 5), ("2.125", 2125)],
)
def test_depths_read_into_thousandths(text: str, thousandths: int) -> None:
    assert parse_thousandths(text) == thousandths


@pytest.mark.parametrize("text", ["", "0.0165", "-0.016", "a lot"])
def test_bad_depths(text: str) -> None:
    with pytest.raises(ValidationError, match="three places"):
        parse_thousandths(text)


def test_a_measured_defect_needs_its_measurement() -> None:
    with pytest.raises(ValidationError, match="has to be measured"):
        Observation(kind=DefectKind.ISOLATED_PITTING)


def test_an_unmeasured_defect_refuses_a_depth() -> None:
    with pytest.raises(ValidationError, match="not something a depth gauge reads"):
        Observation(kind=DefectKind.FIRE_DAMAGE, depth_thousandths_in=10)


def test_zero_measurements_are_refused() -> None:
    with pytest.raises(ValidationError, match="depth of zero"):
        Observation(kind=DefectKind.DENT, depth_thousandths_in=0)
    with pytest.raises(ValidationError, match="length of zero"):
        Observation(kind=DefectKind.CUT_GOUGE_DIG, depth_thousandths_in=10, length_thousandths_in=0)


def test_depth_accessor_refuses_when_absent() -> None:
    observation = Observation(kind=DefectKind.CRACK, length_thousandths_in=500)
    with pytest.raises(ValidationError, match="carries no depth"):
        _ = observation.depth


def test_structural_split() -> None:
    assert DefectKind.BULGE.is_structural
    assert not DefectKind.THREAD_DAMAGE.is_structural
    assert not DefectKind.ILLEGIBLE_MARKING.is_structural


def test_which_defects_want_a_length() -> None:
    assert DefectKind.LINE_CORROSION.wants_a_length
    assert not DefectKind.GENERAL_CORROSION.wants_a_length


def test_describe_reads_like_the_inspector_wrote_it() -> None:
    observation = Observation(
        kind=DefectKind.CUT_GOUGE_DIG,
        depth_thousandths_in=16,
        length_thousandths_in=1250,
        note="lower third, opposite the seam",
    )
    assert observation.describe() == (
        "cut gouge dig, 0.016 in deep, 1.250 in long, lower third, opposite the seam"
    )


def test_describe_without_measurements() -> None:
    assert Observation(kind=DefectKind.LEAK).describe() == "leak"
