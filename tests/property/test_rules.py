"""Properties the rules have to hold whatever the readings are.

These are the statements that would still be true if every number in the
package changed: a colder cylinder settles higher, a longer interval never
falls due sooner, a deeper pit is never more acceptable than a shallower one.
Each of them has an obvious implementation that gets it wrong at one end.
"""

from __future__ import annotations

from datetime import date, timedelta

from hypothesis import assume, given
from hypothesis import strategies as st

from starstamp.model.defect import DefectKind, Observation
from starstamp.model.fillrecord import FillRecord
from starstamp.model.method import Method
from starstamp.model.service import NITROGEN
from starstamp.model.specification import parse_specification
from starstamp.model.units import Expansion, Pressure
from starstamp.rules.filling import judge
from starstamp.rules.interval import due_month, is_out_of_test
from starstamp.rules.pressure_test import Verdict, evaluate
from starstamp.rules.visual import VisualResult
from starstamp.rules.visual import judge as judge_defect

from ..support.factories import make_cylinder, make_readings

STEEL = parse_specification("DOT-3AA2015")
DAY = date(2024, 6, 20)

psi = st.integers(min_value=500, max_value=3000)
temperatures = st.integers(min_value=-40, max_value=140)
depths = st.integers(min_value=1, max_value=200)


def a_fill(pressure: int, temperature: int) -> FillRecord:
    return FillRecord(
        cylinder_key="NCI/A4471",
        service=NITROGEN,
        filled_on=DAY,
        filler_badge="MR2",
        pressure=Pressure(pressure),
        temperature_f=temperature,
    )


@given(pressure=psi, temperature=temperatures)
def test_a_colder_cylinder_settles_no_lower(pressure: int, temperature: int) -> None:
    assume(temperature > -40)
    warmer = a_fill(pressure, temperature).settled_pressure()
    colder = a_fill(pressure, temperature - 1).settled_pressure()
    assert colder >= warmer


@given(pressure=psi)
def test_a_fill_at_seventy_settles_where_it_was(pressure: int) -> None:
    assert a_fill(pressure, 70).settled_pressure() == Pressure(pressure)


@given(pressure=psi, temperature=temperatures)
def test_the_verdict_follows_the_settled_pressure(pressure: int, temperature: int) -> None:
    cylinder = make_cylinder()
    judgement = judge(cylinder, a_fill(pressure, temperature))
    settled = a_fill(pressure, temperature).settled_pressure()
    ceiling = cylinder.specification.service_pressure
    assert ceiling is not None
    if settled.psig > ceiling.psig * 2:
        assert judgement.verdict.is_a_problem


@given(depth=depths, wall=st.integers(min_value=100, max_value=400))
def test_a_deeper_pit_is_never_more_acceptable(depth: int, wall: int) -> None:
    shallow = judge_defect(
        Observation(kind=DefectKind.ISOLATED_PITTING, depth_thousandths_in=depth),
        STEEL,
        wall,
    )
    deeper = judge_defect(
        Observation(kind=DefectKind.ISOLATED_PITTING, depth_thousandths_in=depth + 1),
        STEEL,
        wall,
    )
    order = {VisualResult.PASS: 0, VisualResult.REPAIR: 1, VisualResult.CONDEMN: 2}
    assert order[deeper.result] >= order[shallow.result]


@given(
    total=st.integers(min_value=100, max_value=2000),
    permanent=st.integers(min_value=0, max_value=2000),
)
def test_more_permanent_expansion_is_never_better(total: int, permanent: int) -> None:
    assume(permanent + 1 <= total)
    cylinder = make_cylinder(rejection_elastic_expansion=Expansion(100_000))
    readings = make_readings(
        total_expansion=Expansion(total), permanent_expansion=Expansion(permanent)
    )
    worse = make_readings(
        total_expansion=Expansion(total), permanent_expansion=Expansion(permanent + 1)
    )
    first = evaluate(cylinder, Method.VOLUMETRIC, readings)
    second = evaluate(cylinder, Method.VOLUMETRIC, worse)
    if first.verdict is Verdict.CONDEMN:
        assert second.verdict is Verdict.CONDEMN


@given(
    year=st.integers(min_value=1990, max_value=2060),
    month=st.integers(min_value=1, max_value=12),
)
def test_a_star_never_falls_due_sooner(year: int, month: int) -> None:
    from starstamp.model.dates import StampedMonth

    marked = StampedMonth(year, month)
    cylinder = make_cylinder()
    plain = due_month(cylinder, marked, Method.VOLUMETRIC)
    starred = due_month(cylinder, marked, Method.VOLUMETRIC, starred=True)
    assert starred >= plain


@given(
    year=st.integers(min_value=1990, max_value=2060),
    month=st.integers(min_value=1, max_value=12),
    offset=st.integers(min_value=0, max_value=400),
)
def test_out_of_test_only_ever_becomes_true(year: int, month: int, offset: int) -> None:
    from starstamp.model.dates import StampedMonth

    due = StampedMonth(year, month)
    day = due.last_day() + timedelta(days=offset)
    later = day + timedelta(days=1)
    if is_out_of_test(due, day):
        assert is_out_of_test(due, later)
