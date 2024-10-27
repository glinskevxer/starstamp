from datetime import date

from starstamp.model.cylinder import CylinderStatus
from starstamp.model.event import Outcome
from starstamp.model.method import Method
from starstamp.model.service import AMMONIA, ARGON, CARBON_DIOXIDE, NITROGEN, PROPANE
from starstamp.model.specification import parse_specification
from starstamp.rules.fill import decide

from ..support.factories import make_cylinder, make_event

DAY = date(2024, 6, 12)
LAST_PASS = make_event(performed_on=date(2022, 5, 4))


def test_a_cylinder_in_test_may_be_filled() -> None:
    decision = decide(make_cylinder(), NITROGEN, DAY, LAST_PASS)
    assert decision.allowed
    assert decision.max_pressure is not None
    assert decision.max_pressure.psig == 2015
    assert "may be filled with nitrogen to 2015 psig" in decision.describe()


def test_a_star_carries_it_further_out() -> None:
    old = make_event(performed_on=date(2016, 5, 4))
    assert not decide(make_cylinder(), NITROGEN, DAY, old).allowed
    assert decide(make_cylinder(), NITROGEN, DAY, old, starred=True).allowed


def test_out_of_test_is_not_terminal() -> None:
    old = make_event(performed_on=date(2016, 5, 4))
    decision = decide(make_cylinder(), NITROGEN, DAY, old)
    assert not decision.allowed
    assert not decision.terminal
    assert "out of test since 2021-05" in decision.describe()
    assert decision.describe().startswith("NCI/A4471 not today")


def test_a_condemned_cylinder_never_may() -> None:
    condemned = make_cylinder(status=CylinderStatus.CONDEMNED)
    decision = decide(condemned, NITROGEN, DAY, LAST_PASS)
    assert decision.terminal
    assert decision.describe().startswith("NCI/A4471 never")


def test_a_scrapped_or_lost_cylinder() -> None:
    for status in (CylinderStatus.SCRAPPED, CylinderStatus.LOST):
        decision = decide(make_cylinder(status=status), NITROGEN, DAY, LAST_PASS)
        assert decision.terminal


def test_a_cylinder_waiting_on_a_repair_is_only_held_up() -> None:
    waiting = make_cylinder(status=CylinderStatus.AWAITING_REPAIR)
    decision = decide(waiting, NITROGEN, DAY, LAST_PASS)
    assert not decision.allowed
    assert not decision.terminal
    assert "waiting on a repair" in decision.refusals[0]


def test_a_cylinder_with_no_requalification_at_all() -> None:
    decision = decide(make_cylinder(), NITROGEN, DAY, None)
    assert "no standing requalification" in decision.refusals
    assert decision.due is None


def test_a_condemning_event_is_not_a_pass() -> None:
    condemned = make_event(outcome=Outcome.CONDEMN, reasons=("leaked under pressure",))
    assert (
        "no standing requalification" in decide(make_cylinder(), NITROGEN, DAY, condemned).refusals
    )


def test_a_dedicated_cylinder_takes_only_its_own_gas() -> None:
    dedicated = make_cylinder(
        specification=parse_specification("DOT-4BA240"),
        service=PROPANE,
        rejection_elastic_expansion=None,
        valve_outlet="555",
    )
    assert decide(dedicated, PROPANE, DAY, LAST_PASS).allowed
    refusals = decide(dedicated, NITROGEN, DAY, LAST_PASS).refusals
    assert any("dedicated to propane" in reason for reason in refusals)


def test_a_gas_that_needs_a_dedicated_cylinder_cannot_go_in_a_shared_one() -> None:
    refusals = decide(make_cylinder(), AMMONIA, DAY, LAST_PASS).refusals
    assert any("needs a cylinder dedicated to it" in reason for reason in refusals)


def test_an_inert_gas_swap_is_fine() -> None:
    assert decide(make_cylinder(), ARGON, DAY, LAST_PASS).allowed


def test_the_plus_rating_lifts_the_ceiling() -> None:
    decision = decide(make_cylinder(), NITROGEN, DAY, LAST_PASS, plus=True)
    assert decision.max_pressure is not None
    assert decision.max_pressure.psig == 2217


def test_a_liquefied_gas_is_filled_by_density_not_pressure() -> None:
    fitted = make_cylinder(service=CARBON_DIOXIDE, valve_outlet="320")
    decision = decide(fitted, CARBON_DIOXIDE, DAY, LAST_PASS)
    assert decision.max_pressure is None
    assert decision.filling_density_percent is not None
    assert "50% filling density" in decision.describe()


def test_a_high_strength_cylinder_past_its_life() -> None:
    high = make_cylinder(specification=parse_specification("DOT-3HT1850"))
    decision = decide(high, NITROGEN, DAY, make_event(performed_on=date(2022, 5, 4)))
    assert decision.terminal
    assert any("service life" in reason for reason in decision.refusals)


def test_the_interval_follows_the_method_of_the_last_pass() -> None:
    dedicated = make_cylinder(
        specification=parse_specification("DOT-4BA240"),
        service=PROPANE,
        rejection_elastic_expansion=None,
        valve_outlet="555",
    )
    visual = make_event(
        performed_on=date(2018, 5, 4),
        method=Method.EXTERNAL_VISUAL,
        system_code=None,
        readings=None,
    )
    volumetric = make_event(performed_on=date(2018, 5, 4))
    assert not decide(dedicated, PROPANE, DAY, visual).allowed
    assert decide(dedicated, PROPANE, DAY, volumetric).allowed


def test_a_cylinder_with_the_wrong_valve_is_not_filled() -> None:
    cylinder = make_cylinder(valve_outlet="540", valve_installed_on=date(2019, 4, 1))
    decision = decide(cylinder, NITROGEN, DAY, LAST_PASS)
    assert not decision.allowed
    assert any("valve fitted is CGA 540" in reason for reason in decision.refusals)


def test_a_cylinder_with_no_valve_recorded_is_not_filled() -> None:
    cylinder = make_cylinder(valve_outlet=None, valve_installed_on=None)
    decision = decide(cylinder, NITROGEN, DAY, LAST_PASS)
    assert any("no valve outlet is recorded" in reason for reason in decision.refusals)


def test_the_valve_refusal_is_not_terminal() -> None:
    cylinder = make_cylinder(valve_outlet="540", valve_installed_on=date(2019, 4, 1))
    assert not decide(cylinder, NITROGEN, DAY, LAST_PASS).terminal
