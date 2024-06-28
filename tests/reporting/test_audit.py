from datetime import date

from starstamp.model.cylinder import CylinderKey
from starstamp.model.method import Method
from starstamp.reporting import audit
from starstamp.service.requalify import RequalificationRequest, RequalificationService
from starstamp.service.restate import RestatementService
from starstamp.store.calibration import CalibrationRepository
from starstamp.store.db import Book

from ..support.factories import make_readings
from ..support.shop import DAY, SYSTEM

KEY = CylinderKey("NCI", "A4471")


def requalify(book: Book, day: date = DAY) -> None:
    RequalificationService(book).perform(
        RequalificationRequest(
            key=KEY,
            day=day,
            technician_badge="JT7",
            method=Method.VOLUMETRIC,
            system_code=SYSTEM,
            readings=make_readings(),
        )
    )


def test_a_packet_for_a_cylinder_with_nothing_on_it(shop_book: Book) -> None:
    packet = audit.build(shop_book, KEY)
    assert packet.packets == ()
    text = audit.render(packet)
    assert "no records of test" in text
    assert "DOT-3AA2015" in text


def test_a_packet_carries_the_evidence_for_the_day(shop_book: Book) -> None:
    requalify(shop_book)
    packet = audit.build(shop_book, KEY)
    assert len(packet.packets) == 1
    item = packet.packets[0]
    assert item.evidence_is_complete
    assert len(item.certificates) == 4
    assert item.check is not None


def test_the_packet_reads_like_paper(shop_book: Book) -> None:
    requalify(shop_book)
    text = audit.render(audit.build(shop_book, KEY), today=date(2026, 1, 4))
    assert "2024-06-12  volumetric" in text
    assert "readings: 3358 psig, held 30s" in text
    assert "calibrated_cylinder CAL-1" in text
    assert "expected 40.0 cc" in text
    assert "packet drawn 2026-01-04" in text
    assert "complete" in text


def test_evidence_is_read_for_the_test_date_not_today(shop_book: Book) -> None:
    requalify(shop_book)
    calibration = CalibrationRepository(shop_book.connection)
    shop_book.connection.execute(
        "UPDATE calibration_certificate SET issued_on = '2025-01-01',"
        " valid_until = '2030-01-01' WHERE instrument = 'expansion_scale'"
    )
    assert len(calibration.in_force(SYSTEM, date(2024, 6, 12))) == 3
    packet = audit.build(shop_book, KEY)
    assert len(packet.packets[0].certificates) == 3


def test_a_packet_flags_a_test_with_no_cover(shop_book: Book) -> None:
    requalify(shop_book)
    shop_book.connection.execute("DELETE FROM calibration_certificate")
    shop_book.connection.execute("DELETE FROM system_check")
    packet = audit.build(shop_book, KEY)
    assert packet.gaps
    assert "INCOMPLETE" in audit.render(packet)


def test_reversed_records_can_be_included(shop_book: Book) -> None:
    requalify(shop_book)
    calibration = CalibrationRepository(shop_book.connection)
    from starstamp.model.calibration import InstrumentKind

    certificate_id = calibration.id_of(SYSTEM, InstrumentKind.EXPANSION_SCALE, "EXP-1")
    RestatementService(shop_book).restate_certificate(certificate_id, date(2024, 6, 1), "restated")
    standing = audit.build(shop_book, KEY)
    everything = audit.build(shop_book, KEY, standing_only=False)
    assert len(standing.packets) == 1
    assert len(everything.packets) == 2
    assert "replacement" not in audit.render(standing)
