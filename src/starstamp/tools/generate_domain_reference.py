"""Collect the reasoning out of the rules and write it down in one place.

Every module under rules/ opens by saying what it decides and why it decides
it that way, and those paragraphs are the most valuable prose in the
repository: they are what a new requalifier reads to understand why the
package refuses something. Scattered across twelve files they get read once.

This gathers them into docs/domain.md, and the build checks the file matches,
so the reference cannot drift from the code it was written beside.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

RULES = Path("src/starstamp/rules")
MODEL = Path("src/starstamp/model")
TARGET = Path("docs/domain.md")

HEADER = """# What decides what

Written by `python -m starstamp.tools.generate_domain_reference` from the
module docstrings under `src/starstamp/rules` and `src/starstamp/model`. Do
not edit it by hand.

"""


@dataclass(frozen=True)
class Section:
    """One module's opening paragraphs."""

    name: str
    summary: str
    body: str

    def render(self) -> str:
        lines = [f"## {self.name}", "", self.summary]
        if self.body:
            lines.extend(["", self.body])
        return "\n".join(lines)


def _split(docstring: str) -> tuple[str, str]:
    parts = docstring.strip().split("\n\n", 1)
    summary = parts[0].strip().replace("\n", " ")
    body = parts[1].strip() if len(parts) > 1 else ""
    return summary, body


def sections(directory: Path) -> list[Section]:
    found: list[Section] = []
    for path in sorted(directory.glob("*.py")):
        if path.name == "__init__.py":
            continue
        docstring = ast.get_docstring(ast.parse(path.read_text()))
        if not docstring:
            continue
        summary, body = _split(docstring)
        found.append(Section(f"{directory.name}/{path.name}", summary, body))
    return found


def render() -> str:
    parts = [HEADER.rstrip()]
    for directory, heading in ((RULES, "The rules"), (MODEL, "The vocabulary")):
        parts.append(f"\n# {heading}\n")
        for section in sections(directory):
            parts.append(section.render())
            parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def run(argv: list[str] | None = None) -> int:
    arguments = argv or []
    check_only = "--check" in arguments
    target = TARGET
    for item in arguments:
        if not item.startswith("--"):
            target = Path(item)

    text = render()
    if check_only:
        if not target.exists():
            print(f"{target} is not there; run the generator", file=sys.stderr)
            return 1
        if target.read_text() != text:
            print(f"{target} is out of date; run the generator", file=sys.stderr)
            return 1
        print(f"{target} is current")
        return 0

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, newline="\n")
    counted = len(sections(RULES)) + len(sections(MODEL))
    print(f"wrote {target}, {counted} modules")
    return 0


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:]))
