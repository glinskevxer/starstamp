from datetime import date

from starstamp.model.fillrecord import FillRecord
from starstamp.model.service import CARBON_DIOXIDE, NITROGEN
from starstamp.model.specification import parse_specification
from starstamp.model.units import Pressure
from starstamp.rules.filling import FillVerdict, ceiling_for, judge

from ..support.factories import make_cylinder

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


def test_a_fill_to_the_marking_is_within() -> None:
    judgement = judge(make_cylinder(), a_fill())
    assert judgement.is_within
    assert judgement.describe() == "within"


def test_a_one_percent_overshoot_is_tolerated() -> None:
    assert judge(make_cylinder(), a_fill(pressure=Pressure(2035))).is_within


def test_a_real_overfill_is_caught() -> None:
    judgement = judge(make_cylinder(), a_fill(pressure=Pressure(2200)))
    assert judgement.verdict is FillVerdict.OVERFILLED
    assert judgement.verdict.is_a_problem
    assert "settles at 2200 psig against a ceiling of 2015 psig" in judgement.describe()


def test_the_temperature_decides_which_it_is() -> None:
    hot = a_fill(pressure=Pressure(2170), temperature_f=110)
    assert judge(make_cylinder(), hot).is_within
    cold = a_fill(pressure=Pressure(2200), temperature_f=40)
    assert judge(make_cylinder(), cold).verdict is FillVerdict.OVERFILLED


def test_a_plus_rating_lifts_the_ceiling() -> None:
    fill = a_fill(pressure=Pressure(2200))
    assert judge(make_cylinder(), fill, plus=True).is_within
    assert ceiling_for(make_cylinder(), plus=True) == Pressure(2217)


def test_a_half_empty_cylinder_reads_as_underfilled() -> None:
    judgement = judge(make_cylinder(), a_fill(pressure=Pressure(900)))
    assert judgement.verdict is FillVerdict.UNDERFILLED
    assert not judgement.verdict.is_a_problem
    assert "under half of" in judgement.describe()


def test_a_fill_by_weight_is_not_judged_on_pressure() -> None:
    fill = a_fill(service=CARBON_DIOXIDE, pressure=None, weight_hundredths_lb=5000)
    judgement = judge(make_cylinder(service=CARBON_DIOXIDE, valve_outlet="320"), fill)
    assert judgement.is_within
    assert judgement.settled is None


def test_a_cylinder_with_no_marked_pressure() -> None:
    from starstamp.model.service import ACETYLENE

    acetylene = make_cylinder(
        specification=parse_specification("DOT-8AL"),
        service=ACETYLENE,
        rejection_elastic_expansion=None,
        valve_outlet="510",
    )
    judgement = judge(acetylene, a_fill())
    assert judgement.is_within
    assert judgement.ceiling is None
    assert "no service pressure to judge against" in judgement.describe()
