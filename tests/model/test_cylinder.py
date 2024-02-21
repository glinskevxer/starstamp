import pytest

from starstamp.errors import ValidationError
from starstamp.model.cylinder import (
    Cylinder,
    CylinderKey,
    CylinderStatus,
    normalise_serial,
    normalise_symbol,
)
from starstamp.model.dates import StampedMonth
from starstamp.model.service import ACETYLENE, NITROGEN, OXYGEN
from starstamp.model.specification import parse_specification
from starstamp.model.units import Expansion


def a_cylinder(**changes: object) -> Cylinder:
    base = {
        "key": CylinderKey.of("NCI", "A4471"),
        "specification": parse_specification("DOT-3AA2015"),
        "manufactured": StampedMonth(1998, 6),
        "service": NITROGEN,
        "owner_code": "WELD1",
        "rejection_elastic_expansion": Expansion.parse("31.2"),
    }
    base.update(changes)
    return Cylinder(**base)  # type: ignore[arg-type]


def test_serial_is_normalised() -> None:
    assert normalise_serial(" a44 71 ") == "A4471"
    assert normalise_symbol("nci") == "NCI"


@pytest.mark.parametrize("text", ["", "-A123", "A" * 21, "A/123"])
def test_bad_serials_are_refused(text: str) -> None:
    with pytest.raises(ValidationError):
        normalise_serial(text)


@pytest.mark.parametrize("text", ["", "1NCI", "N" * 11])
def test_bad_symbols_are_refused(text: str) -> None:
    with pytest.raises(ValidationError):
        normalise_symbol(text)


def test_key_parses_the_shorthand() -> None:
    assert CylinderKey.parse("nci/a4471") == CylinderKey("NCI", "A4471")
    assert str(CylinderKey.parse("NCI/A4471")) == "NCI/A4471"


def test_key_needs_both_halves() -> None:
    with pytest.raises(ValidationError, match="SYMBOL/SERIAL"):
        CylinderKey.parse("A4471")


def test_two_makers_can_share_a_serial() -> None:
    assert CylinderKey.of("NCI", "A4471") != CylinderKey.of("PST", "A4471")


def test_status_predicates() -> None:
    assert CylinderStatus.CONDEMNED.is_terminal
    assert not CylinderStatus.CONDEMNED.accepts_work
    assert CylinderStatus.IN_SHOP.accepts_work
    assert not CylinderStatus.IN_SHOP.is_terminal


def test_a_condemned_cylinder_does_not_come_back() -> None:
    condemned = a_cylinder(status=CylinderStatus.CONDEMNED)
    with pytest.raises(ValidationError, match="does not come back"):
        condemned.with_status(CylinderStatus.IN_SERVICE)


def test_status_moves_otherwise() -> None:
    moved = a_cylinder().with_status(CylinderStatus.IN_SHOP)
    assert moved.status is CylinderStatus.IN_SHOP
    assert moved.key == a_cylinder().key


def test_seamless_cylinders_carry_a_ree() -> None:
    assert a_cylinder().carries_ree
    assert a_cylinder().require_ree() == Expansion.parse("31.2")


def test_a_missing_ree_is_a_refusal_not_a_zero() -> None:
    bare = a_cylinder(rejection_elastic_expansion=None)
    with pytest.raises(ValidationError, match="no marked rejection"):
        bare.require_ree()


def test_welded_cylinders_are_not_marked_with_a_ree() -> None:
    welded = a_cylinder(
        specification=parse_specification("DOT-4BA240"),
        rejection_elastic_expansion=None,
    )
    assert not welded.carries_ree


def test_acetylene_belongs_in_an_acetylene_cylinder() -> None:
    with pytest.raises(ValidationError, match="acetylene cylinder"):
        a_cylinder(service=ACETYLENE)


def test_recorded_measurements_must_be_positive() -> None:
    with pytest.raises(ValidationError, match="water capacity"):
        a_cylinder(water_capacity_tenths_l=0)
    with pytest.raises(ValidationError, match="tare weight"):
        a_cylinder(tare_hundredths_lb=-1)


def test_service_pressure_comes_from_the_spec() -> None:
    cylinder = a_cylinder(service=OXYGEN)
    assert cylinder.service_pressure is not None
    assert cylinder.service_pressure.psig == 2015


def test_text_form_names_all_three() -> None:
    assert str(a_cylinder()) == "NCI/A4471 DOT-3AA2015 nitrogen"
