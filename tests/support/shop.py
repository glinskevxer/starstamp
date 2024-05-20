"""A book with a shop in it: one account, one RIN, one bench, one rig."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest

from starstamp.model.calibration import InstrumentKind
from starstamp.model.cylinder import Cylinder, CylinderKey
from starstamp.store.calibration import CalibrationRepository
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book, open_book
from starstamp.store.facility import FacilityRepository, TechnicianRepository
from starstamp.store.migrations import migrate
from starstamp.store.owners import OwnerRepository

from .factories import (
    make_certificate,
    make_check,
    make_cylinder,
    make_facility,
    make_owner,
    make_technician,
)

DAY = date(2024, 6, 12)
SYSTEM = "WJ-1"


@pytest.fixture
def shop_book(tmp_path: Path) -> Iterator[Book]:
    handle = open_book(tmp_path / "shop.sqlite3")
    with handle:
        migrate(handle.connection)
        owners = OwnerRepository(handle.connection)
        owners.add(make_owner())
        FacilityRepository(handle.connection).add(make_facility())
        TechnicianRepository(handle.connection).add(make_technician())
        calibration = CalibrationRepository(handle.connection)
        for instrument in InstrumentKind.ALL:
            calibration.add_certificate(
                make_certificate(instrument, serial=f"{instrument[:3].upper()}-1")
            )
        calibration.record_check(make_check())
        CylinderRepository(handle.connection).add(
            make_cylinder(nominal_wall_thousandths_in=220, wall_source="data sheet"),
            owners.id_of("WELD1"),
            date(2024, 1, 2),
        )
        yield handle


def stock(book: Book, cylinder: Cylinder) -> CylinderKey:
    """Put another cylinder on the books belonging to the same account."""
    owners = OwnerRepository(book.connection)
    CylinderRepository(book.connection).add(cylinder, owners.id_of("WELD1"), date(2024, 1, 2))
    return cylinder.key


def a_wet_cylinder(book: Book, key: CylinderKey) -> CylinderKey:
    from starstamp.model.service import AMMONIA
    from starstamp.model.specification import parse_specification

    return stock(
        book,
        make_cylinder(
            key=key,
            specification=parse_specification("DOT-4BA240"),
            service=AMMONIA,
            rejection_elastic_expansion=None,
            nominal_wall_thousandths_in=87,
            wall_source="data sheet",
        ),
    )
