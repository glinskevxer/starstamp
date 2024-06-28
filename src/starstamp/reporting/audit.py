"""The packet an auditor asks for.

The hard part is not listing the records of test. It is showing, for each one,
the paperwork that was on the wall on the day it was performed rather than the
paperwork on the wall today. A rig recertified last month says nothing about a
test done two years ago, and a packet that shows the current certificate beside
an old test is worse than one that shows nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from starstamp.model.calibration import Certificate, SystemCheck
from starstamp.model.cylinder import Cylinder, CylinderKey
from starstamp.model.event import RequalificationEvent
from starstamp.store.calibration import CalibrationRepository
from starstamp.store.cylinders import CylinderRepository
from starstamp.store.db import Book
from starstamp.store.events import EventRepository
from starstamp.text.table import dash, render_pairs, render_table


@dataclass(frozen=True)
class EventPacket:
    """One record of test with the evidence behind it."""

    event: RequalificationEvent
    certificates: tuple[Certificate, ...]
    check: SystemCheck | None

    @property
    def evidence_is_complete(self) -> bool:
        """Whether the packet can show cover for the day the test was done."""
        if not self.event.method.is_pressure_test:
            return True
        if not self.certificates:
            return False
        return not (self.event.method.measures_expansion and self.check is None)


@dataclass(frozen=True)
class CylinderPacket:
    """Everything the book holds about one cylinder."""

    cylinder: Cylinder
    packets: tuple[EventPacket, ...]

    @property
    def gaps(self) -> tuple[EventPacket, ...]:
        return tuple(packet for packet in self.packets if not packet.evidence_is_complete)


def build(book: Book, key: CylinderKey, *, standing_only: bool = True) -> CylinderPacket:
    """Assemble the packet, reading each event's evidence for its own day."""
    cylinders = CylinderRepository(book.connection)
    events = EventRepository(book.connection)
    calibration = CalibrationRepository(book.connection)

    cylinder = cylinders.by_key(key)
    packets: list[EventPacket] = []
    for event in events.for_cylinder(key, standing_only=standing_only):
        certificates: tuple[Certificate, ...] = ()
        check: SystemCheck | None = None
        if event.system_code:
            certificates = tuple(calibration.in_force(event.system_code, event.performed_on))
            check = calibration.check_on(event.system_code, event.performed_on)
        packets.append(EventPacket(event, certificates, check))
    return CylinderPacket(cylinder, tuple(packets))


def render(packet: CylinderPacket, *, today: date | None = None) -> str:
    """Write the packet out the way it gets handed across a desk."""
    cylinder = packet.cylinder
    lines = [
        render_pairs(
            [
                ("cylinder", str(cylinder.key)),
                ("specification", str(cylinder.specification)),
                ("manufactured", cylinder.manufactured.long_form()),
                ("service", cylinder.service.name),
                ("owner", cylinder.owner_code),
                ("status", cylinder.status.value),
                ("marked ree", dash(cylinder.rejection_elastic_expansion)),
                ("wall", dash(cylinder.nominal_wall_thousandths_in)),
            ]
        ),
        "",
    ]
    if not packet.packets:
        lines.append("no records of test")
        return "\n".join(lines)

    lines.append(
        render_table(
            ["date", "method", "outcome", "rin", "tech", "marks", "evidence"],
            [
                [
                    item.event.performed_on.isoformat(),
                    item.event.method.label,
                    item.event.outcome.value,
                    item.event.facility_rin,
                    item.event.technician_badge,
                    item.event.marks,
                    "complete" if item.evidence_is_complete else "INCOMPLETE",
                ]
                for item in packet.packets
            ],
        )
    )
    for item in packet.packets:
        lines.append("")
        lines.append(f"{item.event.performed_on.isoformat()} {item.event.method.label}")
        if item.event.readings is not None:
            lines.append(f"  readings: {item.event.readings.describe()}")
        for certificate in item.certificates:
            lines.append(
                f"  {certificate.instrument} {certificate.serial}, "
                f"{certificate.issued_on} to {certificate.valid_until}, {certificate.issued_by}"
            )
        if item.check is not None:
            lines.append(f"  {item.check.describe()}")
        for reason in item.event.reasons:
            lines.append(f"  {reason}")
    if today is not None:
        lines.append("")
        lines.append(f"packet drawn {today.isoformat()}")
    return "\n".join(lines)
