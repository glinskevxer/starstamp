from datetime import date

import pytest

from starstamp.errors import NotFoundError
from starstamp.model.cylinder import CylinderKey
from starstamp.model.fillrecord import FillRecord
from starstamp.model.service import CARBON_DIOXIDE, NITROGEN
from starstamp.model.units import Pressure
from starstamp.rules.filling import FillVerdict
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book
from starstamp.store.fills import FillRepository
from starstamp.store.owners import OwnerRepository

from ..support.factories import make_cylinder

KEY = CylinderKey("NCI", "A4471")
DAY = date(2024, 6, 20)


@pytest.fixture
def fills(book: Book, owners: OwnerRepository, cylinders: CylinderRepository) -> FillRepository:
    cylinders.add(make_cylinder(key=KEY), owners.id_of("WELD1"), date(2024, 1, 2))
    return FillRepository(book.connection)


def a_fill(**changes: object) -> FillRecord:
    base: dict[str, object] = {
        "cylinder_key": str(KEY),
        "service": NITROGEN,
        "filled_on": DAY,
        "filler_badge": "MR2",
        "pressure": Pressure(2015),
    }
    base.update(changes)
    return FillRecord(**base)  # type: ignore[arg-type]


def test_a_fill_round_trips(fills: FillRepository, cylinders: CylinderRepository) -> None:
    written = fills.add(
        a_fill(temperature_f=95, note="fast fill"),
        cylinders.id_of(KEY),
        FillVerdict.WITHIN,
        Pressure(1919),
        Pressure(2015),
    )
    assert written.fill_id is not None
    read_back = fills.by_id(written.fill_id)
    assert read_back.temperature_f == 95
    assert read_back.note == "fast fill"
    assert read_back.cylinder_key == "NCI/A4471"
    assert fills.verdict_of(written.fill_id) is FillVerdict.WITHIN


def test_a_fill_by_weight(fills: FillRepository, cylinders: CylinderRepository) -> None:
    written = fills.add(
        a_fill(service=CARBON_DIOXIDE, pressure=None, weight_hundredths_lb=5000),
        cylinders.id_of(KEY),
        FillVerdict.WITHIN,
        None,
        None,
    )
    assert written.fill_id is not None
    assert fills.by_id(written.fill_id).is_by_weight


def test_history_and_the_last_fill(fills: FillRepository, cylinders: CylinderRepository) -> None:
    assert fills.last_fill(KEY) is None
    fills.add(a_fill(), cylinders.id_of(KEY), FillVerdict.WITHIN, Pressure(2015), Pressure(2015))
    fills.add(
        a_fill(filled_on=date(2024, 7, 1), pressure=Pressure(1900)),
        cylinders.id_of(KEY),
        FillVerdict.WITHIN,
        Pressure(1900),
        Pressure(2015),
    )
    assert len(fills.for_cylinder(KEY)) == 2
    last = fills.last_fill(KEY)
    assert last is not None
    assert last.filled_on == date(2024, 7, 1)
    assert fills.count() == 2


def test_windows_and_overfills(fills: FillRepository, cylinders: CylinderRepository) -> None:
    fills.add(a_fill(), cylinders.id_of(KEY), FillVerdict.WITHIN, Pressure(2015), Pressure(2015))
    fills.add(
        a_fill(pressure=Pressure(2400)),
        cylinders.id_of(KEY),
        FillVerdict.OVERFILLED,
        Pressure(2400),
        Pressure(2015),
    )
    assert len(fills.between(date(2024, 6, 1), date(2024, 6, 30))) == 2
    assert len(fills.overfills(date(2024, 6, 1), date(2024, 6, 30))) == 1
    assert fills.overfills(date(2024, 7, 1), date(2024, 7, 31)) == []


def test_a_missing_fill(fills: FillRepository) -> None:
    with pytest.raises(NotFoundError, match="no fill 99"):
        fills.by_id(99)
