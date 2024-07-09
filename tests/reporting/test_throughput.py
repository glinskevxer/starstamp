from datetime import date
from fractions import Fraction

from starstamp.model.event import Outcome, RequalificationEvent
from starstamp.model.method import Method
from starstamp.reporting import throughput
from starstamp.store.db import Book

from ..support.factories import make_event


def events() -> list[RequalificationEvent]:
    return [
        make_event(performed_on=date(2024, 6, 12), starred=True),
        make_event(performed_on=date(2024, 6, 13)),
        make_event(
            performed_on=date(2024, 6, 14),
            outcome=Outcome.CONDEMN,
            reasons=("leaked under pressure, at 3358 psig",),
        ),
        make_event(
            performed_on=date(2024, 7, 2),
            outcome=Outcome.SUSPENDED,
            reasons=("thread damage has to be put right",),
        ),
        make_event(
            performed_on=date(2024, 7, 3),
            method=Method.EXTERNAL_VISUAL,
            system_code=None,
            readings=None,
            outcome=Outcome.CONDEMN,
            reasons=("bulge",),
            technician_badge="MR2",
        ),
    ]


def test_a_suspension_is_not_a_survivor() -> None:
    tally = throughput.overall(events())
    assert tally.total == 5
    assert tally.decided == 4
    assert tally.condemn_rate == Fraction(50)


def test_an_empty_window_has_no_rate() -> None:
    assert throughput.overall([]).condemn_rate == 0


def test_months_come_out_in_order() -> None:
    tallies = throughput.by_month(events())
    assert [tally.label for tally in tallies] == ["2024-06", "2024-07"]
    assert tallies[0].passed == 2
    assert tallies[1].condemned == 1


def test_by_method_and_by_technician() -> None:
    methods = {tally.label: tally for tally in throughput.by_method(events())}
    assert methods["volumetric"].total == 4
    assert methods["external visual"].condemned == 1
    people = {tally.label: tally for tally in throughput.by_technician(events())}
    assert people["JT7"].total == 4
    assert people["MR2"].condemned == 1


def test_reasons_come_back_commonest_first() -> None:
    reasons = throughput.condemning_reasons(events())
    assert reasons[0][0] == "bulge"
    assert dict(reasons)["leaked under pressure"] == 1


def test_the_starred_share_is_of_passes_not_of_everything() -> None:
    assert throughput.starred_share(events()) == Fraction(50)
    assert throughput.starred_share([]) == 0


def test_rendering_a_table() -> None:
    text = throughput.render(throughput.by_month(events()), "month")
    assert "month" in text
    assert "2024-06" in text
    assert "33.3%" in text
    assert "nothing in the window" in throughput.render([], "month")


def test_the_summary_reads_as_prose() -> None:
    text = throughput.render_summary(events())
    assert "5 records, 2 passed, 2 condemned, 1 suspended" in text
    assert "condemn rate 50.0%" in text
    assert "50.0% of passes earned a star" in text
    assert "2 x " not in text
    assert "methods used: external visual, volumetric" in text


def test_what_the_shop_never_used() -> None:
    unused = throughput.unused_methods(events())
    assert Method.PROOF_PRESSURE in unused
    assert Method.VOLUMETRIC not in unused


def test_reading_a_window_out_of_the_book(shop_book: Book) -> None:
    found = throughput.standing_between(shop_book, date(2024, 1, 1), date(2024, 12, 31))
    assert found == []
