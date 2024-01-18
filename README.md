# starstamp

Records for a DOT cylinder requalification shop.

A requalification facility takes in compressed gas cylinders, inspects them,
pressure tests the ones that are due, stamps the ones that pass and condemns
the ones that fail. Every one of those steps has to be defensible five years
later when an auditor asks why a particular cylinder was put back in service.

This is the book the shop keeps. One SQLite file, one command line.

## Running it

    pip install -e ".[dev]"
    starstamp --book shop.sqlite3 init

## Why the arithmetic looks the way it does

Expansion readings are stored in tenths of a cubic centimetre and pressures in
whole psi, both as integers. A permanent expansion of ten percent of total is
the line between a cylinder that goes back in service and one that gets a hole
drilled in it, and floating point puts cylinders on the wrong side of that line.
