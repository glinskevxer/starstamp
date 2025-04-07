"""Typed builders for the bench's own request, and a shorthand for running it.

Nine test modules had grown the same dictionary based builder with a cast on
the end. They drifted: three of them defaulted the system code differently,
which meant a test could pass for the wrong reason. This is the one builder,
and it takes real keyword arguments so that a wrong field is a type error.
"""

from __future__ import annotations

from datetime import date

from starstamp.model.acetylene import AcetyleneExam
from starstamp.model.cylinder import CylinderKey
from starstamp.model.defect import Observation
from starstamp.model.method import Method
from starstamp.model.testrecord import PressureReadings
from starstamp.model.ultrasonic import Scan
from starstamp.service.requalify import (
    RequalificationRequest,
    RequalificationResult,
    RequalificationService,
)
from starstamp.store.db import Book

from .factories import make_readings
from .shop import DAY, SYSTEM

DEFAULT_KEY = CylinderKey("NCI", "A4471")


def make_request(
    *,
    key: CylinderKey = DEFAULT_KEY,
    day: date = DAY,
    technician_badge: str = "JT7",
    method: Method | None = Method.VOLUMETRIC,
    system_code: str | None = SYSTEM,
    observations: tuple[Observation, ...] = (),
    readings: PressureReadings | None = None,
    scan: Scan | None = None,
    acetylene: AcetyleneExam | None = None,
    facility_rin: str | None = None,
    with_readings: bool = True,
) -> RequalificationRequest:
    """The request the bench hands in, with the shop fixture's defaults."""
    if readings is None and with_readings and method is not None and method.is_pressure_test:
        readings = make_readings()
    return RequalificationRequest(
        key=key,
        day=day,
        technician_badge=technician_badge,
        method=method,
        system_code=system_code,
        observations=observations,
        readings=readings,
        scan=scan,
        acetylene=acetylene,
        facility_rin=facility_rin,
    )


def requalify(book: Book, **changes: object) -> RequalificationResult:
    """Put a cylinder through the bench with everything defaulted."""
    return RequalificationService(book).perform(make_request(**changes))  # type: ignore[arg-type]
