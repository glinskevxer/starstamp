import pytest

from starstamp.errors import ValidationError
from starstamp.model.service import all_services
from starstamp.model.valve import (
    CGA_350,
    CGA_540,
    CGA_580,
    Thread,
    all_outlets,
    outlet_for_service,
    parse_outlet,
)


@pytest.mark.parametrize("text", ["540", "CGA540", "cga 540", " CGA-540 "])
def test_outlets_parse(text: str) -> None:
    assert parse_outlet(text) is CGA_540


def test_an_outlet_the_shop_does_not_stock() -> None:
    with pytest.raises(ValidationError, match="the shop stocks"):
        parse_outlet("CGA 999")


def test_junk() -> None:
    with pytest.raises(ValidationError, match="a CGA number"):
        parse_outlet("brass one")


def test_flammable_service_is_left_hand_threaded() -> None:
    assert CGA_350.thread is Thread.LEFT_HAND
    assert CGA_540.thread is Thread.RIGHT_HAND
    assert Thread.LEFT_HAND.label == "left hand"


def test_the_inert_gases_share_an_outlet() -> None:
    assert outlet_for_service("N2") is CGA_580
    assert outlet_for_service("ar") is CGA_580
    assert outlet_for_service("HE") is CGA_580


def test_oxygen_and_medical_oxygen_do_not() -> None:
    assert outlet_for_service("O2") is not outlet_for_service("O2M")


def test_every_catalogued_gas_has_an_outlet() -> None:
    for service in all_services():
        assert outlet_for_service(service.code)


def test_a_gas_with_no_assignment() -> None:
    with pytest.raises(ValidationError, match="no valve outlet is assigned"):
        outlet_for_service("KR")


def test_the_outlets_are_listed() -> None:
    assert len(all_outlets()) >= 12
    assert str(CGA_580) == "CGA 580"
    assert "inert" in CGA_580.description
