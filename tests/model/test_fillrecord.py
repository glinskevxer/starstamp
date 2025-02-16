from datetime import date

import pytest

from starstamp.errors import ValidationError
from starstamp.model.fillrecord import FillRecord
from starstamp.model.service import CARBON_DIOXIDE, NITROGEN
from starstamp.model.units import Pressure

DAY = date(2024, 6, 20)


def a_fill(**changes: object) -> FillRecord:
    base: dict[str, object] = {
        "cylinder_key": "NCI/A4471",
        "service": NITROGEN,
        "filled_on": DAY,
        "filler_badge": "MR2",
        "pressure": Pressure(2015),
    }
    base.update(changes)
    return FillRecord(**base)  # type: ignore[arg-type]


def test_a_fill_is_measured_one_way_or_the_other() -> None:
    with pytest.raises(ValidationError, match="one of them"):
        a_fill(pressure=None)
    with pytest.raises(ValidationError, match="one of them"):
        a_fill(weight_hundredths_lb=5000)


def test_a_liquefied_gas_goes_in_by_weight() -> None:
    with pytest.raises(ValidationError, match="filled by weight"):
        a_fill(service=CARBON_DIOXIDE)
    filled = a_fill(service=CARBON_DIOXIDE, pressure=None, weight_hundredths_lb=5000)
    assert filled.is_by_weight


def test_a_compressed_gas_goes_in_to_a_pressure() -> None:
    with pytest.raises(ValidationError, match="filled to a pressure"):
        a_fill(pressure=None, weight_hundredths_lb=5000)


def test_a_weight_of_nothing() -> None:
    with pytest.raises(ValidationError, match="not a fill"):
        a_fill(service=CARBON_DIOXIDE, pressure=None, weight_hundredths_lb=0)


def test_a_temperature_nobody_read() -> None:
    with pytest.raises(ValidationError, match="not a reading"):
        a_fill(temperature_f=200)


def test_a_fill_at_seventy_settles_where_it_is() -> None:
    assert a_fill().settled_pressure() == Pressure(2015)


def test_a_warm_cylinder_settles_lower() -> None:
    warm = a_fill(pressure=Pressure(2200), temperature_f=110)
    assert warm.settled_pressure().psig == 2046


def test_a_cold_cylinder_settles_higher() -> None:
    cold = a_fill(pressure=Pressure(1900), temperature_f=40)
    assert cold.settled_pressure().psig == 2014


def test_a_fill_by_weight_has_no_settled_pressure() -> None:
    filled = a_fill(service=CARBON_DIOXIDE, pressure=None, weight_hundredths_lb=5000)
    with pytest.raises(ValidationError, match="no settled pressure"):
        filled.settled_pressure()


def test_describing_a_fill() -> None:
    assert a_fill().describe() == "2024-06-20 NCI/A4471 nitrogen 2015 psig at 70F"
    warm = a_fill(pressure=Pressure(2200), temperature_f=110, note="fast fill")
    assert "2046 psig settled" in warm.describe()
    assert "(fast fill)" in warm.describe()
    by_weight = a_fill(service=CARBON_DIOXIDE, pressure=None, weight_hundredths_lb=5000)
    assert "50.00 lb" in by_weight.describe()
