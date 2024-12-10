from datetime import date
from fractions import Fraction

from starstamp.model.event import Outcome
from starstamp.model.method import Method
from starstamp.reporting import technician
from starstamp.store.db import Book
from starstamp.store.facility import TechnicianRepository

from ..support.factories import make_event, make_technician


def a_comparison(*loads: tuple[str, int, int]) -> technician.Comparison:
    workloads = []
    for badge, passes, condemns in loads:
        events = [make_event(technician_badge=badge, starred=True) for _ in range(passes)]
        events += [
            make_event(
                technician_badge=badge,
                outcome=Outcome.CONDEMN,
                reasons=("leaked under pressure",),
            )
            for _ in range(condemns)
        ]
        workloads.append(technician.Workload(badge, badge.lower(), tuple(events)))
    return technician.Comparison(tuple(workloads))


def test_a_workload_counts_what_it_should() -> None:
    comparison = a_comparison(("JT7", 8, 2))
    workload = comparison.workloads[0]
    assert workload.performed == 10
    assert workload.decided == 10
    assert workload.condemned == 2
    assert workload.starred == 8
    assert workload.condemn_rate() == Fraction(20)


def test_a_suspension_is_not_decided() -> None:
    events = (
        make_event(),
        make_event(outcome=Outcome.SUSPENDED, reasons=("threads",)),
    )
    workload = technician.Workload("JT7", "Jesse", events)
    assert workload.performed == 2
    assert workload.decided == 1
    assert workload.condemn_rate() == 0


def test_the_shop_rate_is_across_everybody() -> None:
    comparison = a_comparison(("JT7", 8, 2), ("MR2", 6, 4))
    assert comparison.total_decided == 20
    assert comparison.shop_rate() == Fraction(30)


def test_an_outlier_needs_enough_work_behind_it() -> None:
    thin = a_comparison(("JT7", 9, 1), ("MR2", 1, 9))
    assert thin.outliers() == ()
    thick = a_comparison(("JT7", 30, 0), ("MR2", 15, 15))
    outliers = {workload.badge for workload, _ in thick.outliers()}
    assert outliers == {"JT7", "MR2"}


def test_the_description_says_which_way_it_runs() -> None:
    comparison = a_comparison(("JT7", 30, 0), ("MR2", 15, 15))
    described = comparison.describe()
    assert "shop condemn rate 25.0%" in described
    assert "JT7 is 25.0 points below" in described
    assert "MR2 is 25.0 points above" in described


def test_an_empty_window() -> None:
    comparison = technician.Comparison(())
    assert comparison.shop_rate() == 0
    assert "nobody did any work" in comparison.describe()
    assert technician.render(comparison) == comparison.describe()


def test_methods_and_busiest_day() -> None:
    events = (
        make_event(performed_on=date(2024, 6, 12)),
        make_event(performed_on=date(2024, 6, 12)),
        make_event(
            performed_on=date(2024, 6, 13),
            method=Method.EXTERNAL_VISUAL,
            readings=None,
            system_code=None,
        ),
    )
    workload = technician.Workload("JT7", "Jesse", events)
    assert workload.methods() == {"external visual": 1, "volumetric": 2}
    assert workload.busiest_day() == (date(2024, 6, 12), 2)
    assert technician.Workload("X", "y", ()).busiest_day() is None
    assert Method.PROOF_PRESSURE in technician.unused_by(workload)


def test_building_from_the_book(shop_book: Book) -> None:
    TechnicianRepository(shop_book.connection).add(make_technician(badge="MR2", name="Marisol"))
    comparison = technician.build(shop_book, date(2024, 1, 1), date(2024, 12, 31))
    assert comparison.workloads == ()


def test_rendering(shop_book: Book) -> None:
    text = technician.render(a_comparison(("JT7", 8, 2)))
    assert "JT7" in text
    assert "20.0%" in text
    assert technician.method_mix(a_comparison(("JT7", 1, 0))) == {"volumetric": 1}
