from datetime import date

from starstamp.model.cylinder import CylinderKey
from starstamp.model.defect import DefectKind
from starstamp.model.disposal import DisposalMethod
from starstamp.model.repair import RepairKind
from starstamp.reporting import life
from starstamp.service.disposal import DisposalService
from starstamp.service.notices import NoticeService
from starstamp.service.receiving import ReceivingService
from starstamp.service.repair import RepairService
from starstamp.store.db import Book

from ..support.factories import make_observation
from ..support.requests import requalify
from ..support.shop import DAY

KEY = CylinderKey("NCI", "A4471")


def test_a_cylinder_nothing_has_happened_to(shop_book: Book) -> None:
    built = life.build(shop_book, KEY)
    assert built.entries == ()
    assert built.first_seen is None
    assert "nothing has happened to it here" in life.render(built, DAY)


def test_the_timeline_puts_everything_in_order(shop_book: Book) -> None:
    ReceivingService(shop_book).receive("WELD1", date(2024, 6, 3), [KEY])
    requalify(shop_book, observations=(make_observation(DefectKind.THREAD_DAMAGE),))
    RepairService(shop_book).perform(KEY, RepairKind.NECK_THREAD_REPAIR, date(2024, 6, 14), "JT7")
    built = life.build(shop_book, KEY)
    kinds = [entry.kind for entry in built.entries]
    assert kinds == ["received", "test", "repair"]
    assert built.first_seen == date(2024, 6, 3)
    assert built.last_seen == date(2024, 6, 14)


def test_the_counts_by_kind(shop_book: Book) -> None:
    requalify(shop_book)
    RepairService(shop_book).perform(KEY, RepairKind.PAINTING, date(2024, 6, 14), "JT7")
    built = life.build(shop_book, KEY)
    assert built.kinds() == {"repair": 1, "test": 1}
    assert len(built.of_kind("test")) == 1


def test_a_condemnation_brings_the_notice_and_the_disposal(shop_book: Book) -> None:
    requalify(shop_book, observations=(make_observation(DefectKind.BULGE),))
    NoticeService(shop_book).draft_condemnations(date(2024, 6, 13))
    DisposalService(shop_book).dispose(KEY, DisposalMethod.DRILLED, date(2024, 6, 20), "JT7")
    built = life.build(shop_book, KEY)
    kinds = [entry.kind for entry in built.entries]
    assert kinds == ["test", "notice", "disposal"]
    assert "drilled" in built.entries[-1].detail


def test_wall_readings_land_on_the_timeline(shop_book: Book) -> None:
    from starstamp.store.cylinders import CylinderRepository

    CylinderRepository(shop_book.connection).record_wall(
        KEY, date(2024, 6, 11), 214, "ultrasonic sweep", None
    )
    built = life.build(shop_book, KEY)
    assert built.entries[0].kind == "wall"
    assert "0.214 in from ultrasonic sweep" in built.entries[0].detail


def test_a_returned_lot_shows_both_ends(shop_book: Book) -> None:
    service = ReceivingService(shop_book)
    service.receive("WELD1", date(2024, 6, 3), [KEY])
    requalify(shop_book)
    service.ready("L2024-0001")
    service.return_lot("L2024-0001", date(2024, 6, 20))
    kinds = [entry.kind for entry in life.build(shop_book, KEY).entries]
    assert kinds == ["received", "test", "returned"]


def test_a_reversed_record_still_shows(shop_book: Book) -> None:
    from starstamp.store.events import EventRepository

    requalify(shop_book)
    EventRepository(shop_book.connection).reverse(1, "rig out of calibration")
    built = life.build(shop_book, KEY)
    assert "[reversed]" in built.entries[0].detail


def test_rendering(shop_book: Book) -> None:
    requalify(shop_book)
    text = life.render(life.build(shop_book, KEY), date(2024, 6, 20))
    assert "NCI/A4471" in text
    assert "26 years" in text
    assert "volumetric pass" in text


def test_fills_land_on_the_timeline(shop_book: Book) -> None:
    from starstamp.model.service import NITROGEN
    from starstamp.model.units import Pressure
    from starstamp.service.filling import FillingService

    requalify(shop_book)
    FillingService(shop_book).record(
        KEY, NITROGEN, date(2024, 6, 25), "JT7", pressure=Pressure(2015)
    )
    built = life.build(shop_book, KEY)
    kinds = [entry.kind for entry in built.entries]
    assert kinds == ["test", "fill"]
    assert "nitrogen to 2015 psig" in built.entries[1].detail


def test_a_fill_by_weight_reads_as_a_weight(shop_book: Book) -> None:
    from starstamp.model.service import CARBON_DIOXIDE
    from starstamp.service.filling import FillingService
    from starstamp.store.cylinders import CylinderRepository

    requalify(shop_book)
    cylinders = CylinderRepository(shop_book.connection)
    cylinders.change_service(KEY, CARBON_DIOXIDE)
    cylinders.fit_valve(KEY, "320", date(2024, 6, 20))
    FillingService(shop_book).record(
        KEY, CARBON_DIOXIDE, date(2024, 6, 25), "JT7", weight_hundredths_lb=5000
    )
    built = life.build(shop_book, KEY)
    assert "50.00 lb" in built.entries[-1].detail


def test_a_transfer_lands_on_the_timeline(shop_book: Book) -> None:
    from starstamp.model.owner import OwnerAccount
    from starstamp.store.cylinders import CylinderRepository
    from starstamp.store.owners import OwnerRepository

    owners = OwnerRepository(shop_book.connection)
    owners.add(OwnerAccount(code="FIRE7", name="Sanpete Fire", opened_on=date(2020, 1, 1)))
    CylinderRepository(shop_book.connection).transfer(KEY, owners.id_of("FIRE7"), date(2024, 6, 25))
    built = life.build(shop_book, KEY)
    assert built.entries[-1].kind == "transfer"
    assert "WELD1 to FIRE7" in built.entries[-1].detail


def test_the_kinds_count_everything(shop_book: Book) -> None:
    from starstamp.model.service import NITROGEN
    from starstamp.model.units import Pressure
    from starstamp.service.filling import FillingService

    requalify(shop_book)
    FillingService(shop_book).record(
        KEY, NITROGEN, date(2024, 6, 25), "JT7", pressure=Pressure(2015)
    )
    assert life.build(shop_book, KEY).kinds() == {"fill": 1, "test": 1}


def test_measurements_land_on_the_timeline(shop_book: Book) -> None:
    from starstamp.store.cylinders import CylinderRepository

    CylinderRepository(shop_book.connection).measure(
        KEY, "tare", 11800, date(2024, 6, 11), "shop scale"
    )
    built = life.build(shop_book, KEY)
    assert built.entries[0].kind == "measured"
    assert "tare 11800 from shop scale" in built.entries[0].detail
