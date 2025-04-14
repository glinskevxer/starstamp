"""Writing an audit pack to a directory.

An inspector arrives, asks for a period, and expects to be handed something
they can read without the shop standing over them. That means files: one
packet per cylinder tested, the records of test as a spreadsheet, and an index
that says what is in the pack and what the shop believes about it.

The index is the part worth care. It says how many packets are complete and
names the ones that are not, because a pack that quietly leaves out the
awkward cylinders is worse than no pack at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from starstamp.model.cylinder import CylinderKey
from starstamp.model.event import RequalificationEvent
from starstamp.reporting import audit, export, throughput
from starstamp.store.db import Book


@dataclass(frozen=True)
class PackResult:
    """What was written, and what the shop should know about it."""

    directory: Path
    files: tuple[Path, ...]
    cylinders: int
    incomplete: tuple[str, ...]

    @property
    def is_complete(self) -> bool:
        return not self.incomplete

    def describe(self) -> str:
        line = f"{len(self.files)} files for {self.cylinders} cylinders in {self.directory}"
        if self.incomplete:
            line = f"{line}; {len(self.incomplete)} packets are missing evidence"
        return line


def _safe_name(key: CylinderKey) -> str:
    return f"{key.manufacturer_symbol}-{key.serial}".replace("/", "-")


def write(book: Book, directory: Path, first: date, last: date, today: date) -> PackResult:
    """Write the pack, one file per cylinder plus the spreadsheets."""
    directory.mkdir(parents=True, exist_ok=True)
    events = throughput.standing_between(book, first, last)
    keys = sorted({event.cylinder for event in events}, key=str)

    written: list[Path] = []
    incomplete: list[str] = []
    packets = directory / "packets"
    packets.mkdir(exist_ok=True)
    for key in keys:
        packet = audit.build(book, key)
        if packet.gaps:
            incomplete.append(str(key))
        path = packets / f"{_safe_name(key)}.txt"
        path.write_text(audit.render(packet, today=today), newline="\n")
        written.append(path)

    records = directory / "records-of-test.csv"
    records.write_text(export.events_csv(book, first, last), newline="\n")
    written.append(records)

    cylinders = directory / "cylinders.csv"
    cylinders.write_text(export.cylinders_csv(book), newline="\n")
    written.append(cylinders)

    index = directory / "index.txt"
    index.write_text(_index(first, last, today, keys, incomplete, events), newline="\n")
    written.append(index)

    return PackResult(directory, tuple(written), len(keys), tuple(incomplete))


def _index(
    first: date,
    last: date,
    today: date,
    keys: list[CylinderKey],
    incomplete: list[str],
    events: list[RequalificationEvent],
) -> str:
    lines = [
        "audit pack",
        f"period {first.isoformat()} to {last.isoformat()}",
        f"drawn {today.isoformat()}",
        "",
        throughput.render_summary(events),
        "",
        f"{len(keys)} cylinders, one packet each, under packets/",
        "records-of-test.csv holds every record in the period",
        "cylinders.csv holds every cylinder on the books",
    ]
    if incomplete:
        lines.append("")
        lines.append("packets missing evidence for the day of the test:")
        lines.extend(f"  {name}" for name in incomplete)
    return "\n".join(lines) + "\n"
