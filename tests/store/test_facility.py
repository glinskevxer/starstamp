from datetime import date

import pytest

from starstamp.errors import ConflictError, NotFoundError
from starstamp.model.facility import Facility, Technician
from starstamp.model.method import Method
from starstamp.store.db import Book
from starstamp.store.facility import (
    FacilityRepository,
    TechnicianRepository,
    pack_methods,
    unpack_methods,
)

METHODS = frozenset({Method.VOLUMETRIC, Method.EXTERNAL_VISUAL})


def a_facility(rin: str = "A419") -> Facility:
    return Facility(
        rin=rin,
        name="Wasatch Cylinder Service",
        approved_from=date(2021, 5, 1),
        approved_until=date(2026, 4, 30),
        methods=METHODS,
        address="1400 S Gladiola St",
    )


def test_methods_pack_and_unpack() -> None:
    assert pack_methods(METHODS) == "external_visual,volumetric"
    assert unpack_methods("external_visual,volumetric") == METHODS
    assert unpack_methods("") == frozenset()


def test_facility_round_trip(book: Book) -> None:
    repository = FacilityRepository(book.connection)
    repository.add(a_facility())
    found = repository.by_rin("a419")
    assert found.name == "Wasatch Cylinder Service"
    assert found.methods == METHODS
    assert found.address == "1400 S Gladiola St"


def test_duplicate_rin(book: Book) -> None:
    repository = FacilityRepository(book.connection)
    repository.add(a_facility())
    with pytest.raises(ConflictError, match="already recorded"):
        repository.add(a_facility())


def test_only_needs_exactly_one(book: Book) -> None:
    repository = FacilityRepository(book.connection)
    with pytest.raises(ConflictError, match="no facility recorded"):
        repository.only()
    repository.add(a_facility())
    assert repository.only().rin == "A419"
    repository.add(a_facility("B420"))
    with pytest.raises(ConflictError, match="more than one RIN"):
        repository.only()


def test_missing_facility(book: Book) -> None:
    with pytest.raises(NotFoundError, match="no facility A419"):
        FacilityRepository(book.connection).by_rin("A419")


def test_renewal_moves_the_expiry(book: Book) -> None:
    repository = FacilityRepository(book.connection)
    repository.add(a_facility())
    renewed = repository.renew("A419", "2031-04-30")
    assert renewed.approved_until == date(2031, 4, 30)


def test_technicians_round_trip(book: Book) -> None:
    repository = TechnicianRepository(book.connection)
    repository.add(
        Technician(
            badge="JT7",
            name="Jesse Tovar",
            methods=METHODS,
            qualified_from=date(2022, 3, 1),
        )
    )
    repository.add(
        Technician(
            badge="MR2",
            name="Marisol Reyes",
            methods=frozenset({Method.VOLUMETRIC}),
            qualified_from=date(2023, 1, 9),
            qualified_until=date(2025, 1, 9),
        )
    )
    assert [item.badge for item in repository.all()] == ["JT7", "MR2"]
    assert repository.by_badge("jt7").name == "Jesse Tovar"
    assert repository.by_badge("MR2").qualified_until == date(2025, 1, 9)
    assert len(repository.qualified_for(Method.EXTERNAL_VISUAL)) == 1
    assert len(repository.qualified_for(Method.VOLUMETRIC)) == 2


def test_duplicate_badge(book: Book) -> None:
    repository = TechnicianRepository(book.connection)
    technician = Technician(
        badge="JT7", name="Jesse Tovar", methods=METHODS, qualified_from=date(2022, 3, 1)
    )
    repository.add(technician)
    with pytest.raises(ConflictError, match="already on the bench"):
        repository.add(technician)


def test_renewing_a_sign_off(book: Book) -> None:
    repository = TechnicianRepository(book.connection)
    repository.add(
        Technician(
            badge="JT7",
            name="Jesse Tovar",
            methods=METHODS,
            qualified_from=date(2022, 3, 1),
            qualified_until=date(2024, 3, 1),
        )
    )
    renewed = repository.renew("jt7", date(2027, 3, 1))
    assert renewed.qualified_until == date(2027, 3, 1)
    forever = repository.renew("JT7", None)
    assert forever.qualified_until is None


def test_signing_somebody_off_for_another_method(book: Book) -> None:
    repository = TechnicianRepository(book.connection)
    repository.add(
        Technician(
            badge="JT7",
            name="Jesse Tovar",
            methods=frozenset({Method.VOLUMETRIC}),
            qualified_from=date(2022, 3, 1),
        )
    )
    updated = repository.add_method("JT7", Method.ULTRASONIC)
    assert updated.methods == frozenset({Method.VOLUMETRIC, Method.ULTRASONIC})
    again = repository.add_method("JT7", Method.ULTRASONIC)
    assert len(again.methods) == 2


def test_who_is_lapsing(book: Book) -> None:
    repository = TechnicianRepository(book.connection)
    repository.add(
        Technician(
            badge="JT7",
            name="Jesse",
            methods=METHODS,
            qualified_from=date(2022, 3, 1),
            qualified_until=date(2024, 7, 1),
        )
    )
    repository.add(
        Technician(
            badge="MR2",
            name="Marisol",
            methods=METHODS,
            qualified_from=date(2022, 3, 1),
            qualified_until=date(2024, 1, 1),
        )
    )
    assert [item.badge for item in repository.lapsing_within(date(2024, 6, 12), 60)] == ["JT7"]
    assert [item.badge for item in repository.lapsed_on(date(2024, 6, 12))] == ["MR2"]
