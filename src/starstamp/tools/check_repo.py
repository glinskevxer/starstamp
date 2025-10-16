"""The house rules this repository keeps, checked mechanically.

Four of them, all of which have been broken here at least once:

Every module says what it is for in its first line. A module with no docstring
is one somebody added in a hurry, and this package's docstrings are where the
domain reasoning lives.

No markers left behind. A TODO in a shop's records system is a decision
somebody deferred and nobody came back to.

Every source package has a matching test package. It does not check that every
module is tested, which would be a lie dressed as a number; it checks that a
whole area of the code has not appeared with no tests beside it at all.

Every file a generator writes is declared as generated. An undeclared one is
counted as though somebody typed it, which skews what the host reports the
repository is written in, and it reads in review as hand work. The rule finds
the generators rather than naming their outputs, so a third one cannot be
added without either the declaration or a deliberate decision to skip it.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

SOURCE = Path("src/starstamp")
TESTS = Path("tests")
TOOLS = SOURCE / "tools"
ATTRIBUTES = Path(".gitattributes")
MARKERS = ("TODO", "FIXME", "XXX", "HACK")
EXEMPT_FROM_TESTS = {"starstamp", "cli", "text", "tools"}


@dataclass(frozen=True)
class Complaint:
    """One house rule, broken once."""

    rule: str
    where: str
    detail: str

    def __str__(self) -> str:
        return f"{self.rule}: {self.where}: {self.detail}"


def modules(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.py") if "__pycache__" not in str(path))


def missing_docstrings(root: Path = SOURCE) -> list[Complaint]:
    found: list[Complaint] = []
    for path in modules(root):
        if path.name == "__init__.py" and path.read_text().strip() == "":
            continue
        tree = ast.parse(path.read_text())
        if not ast.get_docstring(tree):
            found.append(Complaint("docstring", str(path), "no module docstring"))
    return found


def leftover_markers(roots: tuple[Path, ...] = (SOURCE, TESTS)) -> list[Complaint]:
    found: list[Complaint] = []
    for root in roots:
        for path in modules(root):
            for number, line in enumerate(path.read_text().splitlines(), start=1):
                for marker in MARKERS:
                    if f"{marker}:" in line or f"# {marker}" in line:
                        found.append(Complaint("marker", f"{path}:{number}", line.strip()))
    return found


def packages_without_tests(source: Path = SOURCE, tests: Path = TESTS) -> list[Complaint]:
    found: list[Complaint] = []
    for path in sorted(source.iterdir()):
        if not path.is_dir() or path.name.startswith("_"):
            continue
        if path.name in EXEMPT_FROM_TESTS:
            continue
        if not (tests / path.name).is_dir():
            found.append(Complaint("tests", str(path), f"no tests/{path.name} beside it"))
    return found


def generated_files(tools: Path = TOOLS) -> list[str]:
    """The path each generator writes, read off the generator itself.

    Read rather than imported: this runs over whatever directory it is given,
    and a checker that imports the thing it is checking can be fooled by an
    import that does work of its own.
    """
    targets: list[str] = []
    for path in sorted(tools.glob("generate_*.py")):
        tree = ast.parse(path.read_text())
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            names = [n.id for n in node.targets if isinstance(n, ast.Name)]
            if "TARGET" not in names:
                continue
            value = node.value
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                targets.append(value.value)
            elif isinstance(value, ast.Call) and value.args:
                first = value.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    targets.append(first.value)
    return targets


def declarations(attributes: Path = ATTRIBUTES) -> dict[str, str]:
    """Read .gitattributes as a mapping of path to the attributes set on it."""
    found: dict[str, str] = {}
    if not attributes.exists():
        return found
    for line in attributes.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        pattern, _, rest = stripped.partition(" ")
        found[pattern] = rest.strip()
    return found


def undeclared_generated_files(
    tools: Path = TOOLS, attributes: Path = ATTRIBUTES
) -> list[Complaint]:
    found: list[Complaint] = []
    declared = declarations(attributes)
    for target in generated_files(tools):
        if "linguist-generated=true" not in declared.get(target, ""):
            found.append(
                Complaint("generated", target, "not declared linguist-generated in .gitattributes")
            )
    return found


def run(argv: list[str] | None = None) -> int:
    _ = argv
    complaints = (
        missing_docstrings()
        + leftover_markers()
        + packages_without_tests()
        + undeclared_generated_files()
    )
    counted = len(modules(SOURCE)) + len(modules(TESTS))
    print(f"{counted} modules checked")
    for complaint in complaints:
        print(f"problem: {complaint}", file=sys.stderr)
    return 1 if complaints else 0


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:]))
