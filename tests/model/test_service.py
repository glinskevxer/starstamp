import pytest

from starstamp.errors import ValidationError
from starstamp.model.service import (
    ACETYLENE,
    AMMONIA,
    CHLORINE,
    NITROGEN,
    OXYGEN,
    Hazard,
    all_services,
    lookup_service,
)


def test_lookup_is_forgiving_about_shape() -> None:
    assert lookup_service(" co2 ") is lookup_service("CO2")
    assert lookup_service("ar-co2") is lookup_service("ARCO2")


def test_lookup_refuses_a_gas_the_book_does_not_know() -> None:
    with pytest.raises(ValidationError, match="unknown gas service"):
        lookup_service("krypton")


def test_the_refusal_lists_what_is_known() -> None:
    with pytest.raises(ValidationError, match="C2H2"):
        lookup_service("krypton")


def test_dry_service_excludes_the_corrosives() -> None:
    assert NITROGEN.is_dry_service
    assert OXYGEN.is_dry_service
    assert not AMMONIA.is_dry_service
    assert not CHLORINE.is_dry_service


def test_interior_inspection_follows_the_hazard() -> None:
    assert not NITROGEN.needs_interior_inspection
    assert AMMONIA.needs_interior_inspection
    assert CHLORINE.needs_interior_inspection


def test_acetylene_is_dissolved_and_never_gets_an_interval() -> None:
    assert ACETYLENE.dissolved
    assert not ACETYLENE.interval_eligible
    assert ACETYLENE.requires_dedicated_cylinder


def test_hazards_are_assigned() -> None:
    assert OXYGEN.hazard is Hazard.OXIDIZER
    assert ACETYLENE.hazard is Hazard.FLAMMABLE
    assert CHLORINE.hazard is Hazard.TOXIC


def test_every_catalogued_service_round_trips() -> None:
    for service in all_services():
        assert lookup_service(service.code) is service


def test_catalogue_is_not_tiny() -> None:
    assert len(all_services()) >= 18


def test_name_is_the_text_form() -> None:
    assert str(OXYGEN) == "oxygen"
