# starstamp

Records for a DOT cylinder requalification shop.

A requalification facility takes in compressed gas cylinders, inspects them,
pressure tests the ones that are due, stamps the ones that pass and condemns
the ones that fail. Every one of those steps has to be defensible five years
later when an auditor asks why a particular cylinder went back into service.

This is the book the shop keeps. One SQLite file, one command line.

## Running it

    pip install -e ".[dev]"
    starstamp --book shop.sqlite3 init
    starstamp --book shop.sqlite3 demo        # a month of a small shop's work

Then look at it:

    starstamp --book shop.sqlite3 about
    starstamp --book shop.sqlite3 report close
    starstamp --book shop.sqlite3 report bench
    starstamp --book shop.sqlite3 doctor

Every command is listed in [docs/cli.md](docs/cli.md), which is generated from
the commands themselves and checked in the build.

## A day at the bench

    starstamp --book shop.sqlite3 rig check WJ-1 40.0 40.1
    starstamp --book shop.sqlite3 requal run NCI/A4471 --tech JT7 --system WJ-1 \
      --applied 3358 --total 110.0 --permanent 2.0
    starstamp --book shop.sqlite3 fill check NCI/A4471

The second of those refuses unless the first happened. That is the shape of
most of this package: the decisions are layered, and each one is made from
what an earlier one produced.

## What decides what

    the spec stamped on the crown   decides which methods are legal
    the method                      decides which measurements exist
    the rig's certificates          decide whether the readings count
    the visual inspection           decides whether it reaches the rig
    the readings and the history    decide whether it earns a star
    the star                        decides the interval
    the interval                    decides whether a fill is legal today

None of these is a preference. A proof pressure test takes no expansion
reading, so the rejection elastic expansion marked on the cylinder is not a
criterion for it at all; a cylinder tested under a lapsed certificate is not
requalified whatever its numbers say.

## How the code is laid out

    src/starstamp/
      model/      value objects and the domain vocabulary
      rules/      the decisions, each pure and testable on its own
      service/    use cases: the order the rules are asked in
      store/      sqlite, migrations, repositories
      reporting/  audit packs, throughput, invoices, forecasts
      cli/        click groups, one per aggregate
      tools/      the checks the build runs against this repository
    tests/        mirrors the source tree, at the repository root

## Arithmetic

No floats anywhere in a decision. Expansion is stored in tenths of a cubic
centimetre, pressure in whole psi, money in cents, and every ratio is an exact
`Fraction`. A permanent expansion of ten percent of total is the line between
a cylinder that goes back in service and one that gets a hole drilled in it,
and binary floating point puts cylinders on the wrong side of that line.

## Records are never edited

A record of test is evidence. When one turns out to rest on something that
moved, it is reversed and a replacement is written beside it, and both stay in
the book. That is true of a mistyped reading and of a calibration certificate
the calibration house restated two years later.

## The build

Eight jobs: lint, types, tests on 3.12 and 3.13, a coverage floor, the
migrations applied to a scratch book, an index check, the installed console
script driven through a day's work, and the package build. A separate weekly
job audits the pinned dependencies.

Run the same gate locally with `pytest -q`, `ruff check .`, `mypy`, and
`python -m starstamp.tools.check_migrations`.
