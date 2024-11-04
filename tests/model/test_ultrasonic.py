import pytest

from starstamp.errors import ValidationError
from starstamp.model.ultrasonic import Band, Position, Reading, Scan


def a_scan(*pairs: tuple[str, int]) -> Scan:
    return Scan(tuple(Reading(Position.parse(name), value) for name, value in pairs))


def test_positions_parse() -> None:
    position = Position.parse("m3")
    assert position.band is Band.MIDDLE
    assert position.index == 3
    assert str(position) == "M3"


@pytest.mark.parametrize("text", ["", "3", "MM3", "M0", "M99"])
def test_bad_positions(text: str) -> None:
    with pytest.raises(ValidationError):
        Position.parse(text)


def test_an_unknown_band_lists_the_ones_there_are() -> None:
    with pytest.raises(ValidationError, match="the bands are"):
        Position.parse("Z3")


def test_band_labels() -> None:
    assert Band.SHOULDER.label == "shoulder"
    assert Band.BASE.label == "base"


def test_a_reading_of_nothing() -> None:
    with pytest.raises(ValidationError, match="recorded as 0"):
        Reading(Position.parse("M1"), 0)


def test_reading_text() -> None:
    assert str(Reading(Position.parse("M1"), 214)) == "M1 0.214 in"


def test_a_scan_will_not_take_a_position_twice() -> None:
    with pytest.raises(ValidationError, match="recorded twice"):
        a_scan(("M1", 214), ("M1", 213))


def test_the_thinnest_point() -> None:
    scan = a_scan(("M1", 214), ("M2", 208), ("L1", 220))
    assert scan.thinnest.thousandths_in == 208
    assert scan.count == 3
    assert scan.bands == frozenset({Band.MIDDLE, Band.LOWER})


def test_an_empty_scan_has_no_thinnest_point() -> None:
    with pytest.raises(ValidationError, match="empty scan"):
        _ = Scan(()).thinnest


def test_readings_below_a_floor() -> None:
    scan = a_scan(("M1", 214), ("M2", 208), ("L1", 220))
    assert len(scan.below(210)) == 1
    assert scan.below(200) == ()


def test_describing_a_scan() -> None:
    scan = a_scan(("M1", 214), ("L1", 208))
    assert scan.describe() == "2 points across 2 bands, thinnest L1 0.208 in"
    assert Scan(()).describe() == "no readings"
