"""A plain text table.

The bench terminal is eighty columns and there is no colour. Numbers line up
on the right because the shop reads down a column of expansions looking for
the one that is out of family, and a ragged column defeats that.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from starstamp.errors import ValidationError


def render_table(
    headers: Sequence[str],
    rows: Iterable[Sequence[str]],
    *,
    right: Sequence[int] = (),
) -> str:
    """Render a table with a rule under the headers."""
    body = [[str(cell) for cell in row] for row in rows]
    for row in body:
        if len(row) != len(headers):
            raise ValidationError(f"row has {len(row)} cells, headers have {len(headers)}")
    widths = [len(header) for header in headers]
    for row in body:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    right_set = set(right)

    def line(cells: Sequence[str]) -> str:
        parts = []
        for index, cell in enumerate(cells):
            if index in right_set:
                parts.append(cell.rjust(widths[index]))
            else:
                parts.append(cell.ljust(widths[index]))
        return "  ".join(parts).rstrip()

    out = [line(headers), "  ".join("-" * width for width in widths)]
    out.extend(line(row) for row in body)
    return "\n".join(out)


def render_pairs(pairs: Iterable[tuple[str, str]]) -> str:
    """A label and value block, for showing one record."""
    items = list(pairs)
    if not items:
        return ""
    width = max(len(label) for label, _ in items)
    return "\n".join(f"{label.ljust(width)}  {value}" for label, value in items)


def yes_no(value: bool) -> str:
    return "yes" if value else "no"


def dash(value: object | None) -> str:
    return "-" if value is None else str(value)


def plural(count: int, singular: str, plural_form: str | None = None) -> str:
    if count == 1:
        return f"{count} {singular}"
    return f"{count} {plural_form or singular + 's'}"
