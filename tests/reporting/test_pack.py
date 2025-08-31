from datetime import date
from pathlib import Path

from starstamp.model.cylinder import CylinderKey
from starstamp.reporting import pack
from starstamp.store.db import Book

from ..support.factories import make_cylinder
from ..support.requests import requalify
from ..support.shop import stock

FIRST = date(2024, 6, 1)
LAST = date(2024, 6, 30)
TODAY = date(2024, 7, 1)


def test_a_pack_from_a_quiet_period(shop_book: Book, tmp_path: Path) -> None:
    result = pack.write(shop_book, tmp_path / "pack", FIRST, LAST, TODAY)
    assert result.cylinders == 0
    assert result.is_complete
    assert (tmp_path / "pack" / "index.txt").exists()
    assert "0 cylinders" in result.describe()


def test_a_packet_per_cylinder(shop_book: Book, tmp_path: Path) -> None:
    other = stock(shop_book, make_cylinder(key=CylinderKey("PST", "B12")))
    requalify(shop_book)
    requalify(shop_book, key=other)
    result = pack.write(shop_book, tmp_path / "pack", FIRST, LAST, TODAY)
    assert result.cylinders == 2
    packets = sorted((tmp_path / "pack" / "packets").glob("*.txt"))
    assert [path.name for path in packets] == ["NCI-A4471.txt", "PST-B12.txt"]
    assert "DOT-3AA2015" in packets[0].read_text()


def test_the_spreadsheets_are_there(shop_book: Book, tmp_path: Path) -> None:
    requalify(shop_book)
    pack.write(shop_book, tmp_path / "pack", FIRST, LAST, TODAY)
    records = (tmp_path / "pack" / "records-of-test.csv").read_text()
    assert "NCI/A4471" in records
    assert "volumetric" in records
    assert "cylinder,manufacturer" in (tmp_path / "pack" / "cylinders.csv").read_text()


def test_the_index_says_what_is_in_the_pack(shop_book: Book, tmp_path: Path) -> None:
    requalify(shop_book)
    pack.write(shop_book, tmp_path / "pack", FIRST, LAST, TODAY)
    index = (tmp_path / "pack" / "index.txt").read_text()
    assert "period 2024-06-01 to 2024-06-30" in index
    assert "drawn 2024-07-01" in index
    assert "1 records, 1 passed" in index
    assert "1 cylinders, one packet each" in index


def test_the_index_names_the_packets_with_gaps(shop_book: Book, tmp_path: Path) -> None:
    requalify(shop_book)
    shop_book.connection.execute("DELETE FROM calibration_certificate")
    result = pack.write(shop_book, tmp_path / "pack", FIRST, LAST, TODAY)
    assert not result.is_complete
    assert result.incomplete == ("NCI/A4471",)
    index = (tmp_path / "pack" / "index.txt").read_text()
    assert "packets missing evidence" in index
    assert "missing evidence" in result.describe()


def test_writing_twice_over_the_same_directory(shop_book: Book, tmp_path: Path) -> None:
    requalify(shop_book)
    pack.write(shop_book, tmp_path / "pack", FIRST, LAST, TODAY)
    result = pack.write(shop_book, tmp_path / "pack", FIRST, LAST, TODAY)
    assert result.cylinders == 1


def test_a_pack_for_one_account(shop_book: Book, tmp_path: Path) -> None:
    from starstamp.model.owner import OwnerAccount
    from starstamp.store.cylinders import CylinderRepository
    from starstamp.store.owners import OwnerRepository

    owners = OwnerRepository(shop_book.connection)
    owners.add(OwnerAccount(code="FIRE7", name="Sanpete Fire", opened_on=date(2020, 1, 1)))
    other = stock(shop_book, make_cylinder(key=CylinderKey("PST", "B12")))
    CylinderRepository(shop_book.connection).transfer(
        other, owners.id_of("FIRE7"), date(2024, 6, 1)
    )
    requalify(shop_book)
    requalify(shop_book, key=other)

    result = pack.write(shop_book, tmp_path / "pack", FIRST, LAST, TODAY, owner_code="WELD1")
    assert result.cylinders == 1
    packets = sorted((tmp_path / "pack" / "packets").glob("*.txt"))
    assert [path.name for path in packets] == ["NCI-A4471.txt"]
    index = (tmp_path / "pack" / "index.txt").read_text()
    assert "audit pack for WELD1" in index
    records = (tmp_path / "pack" / "records-of-test.csv").read_text()
    assert "PST/B12" not in records
    assert "NCI/A4471" in records


def test_the_cylinder_sheet_is_narrowed_too(shop_book: Book, tmp_path: Path) -> None:
    requalify(shop_book)
    pack.write(shop_book, tmp_path / "pack", FIRST, LAST, TODAY, owner_code="WELD1")
    listing = (tmp_path / "pack" / "cylinders.csv").read_text()
    assert "NCI/A4471" in listing
