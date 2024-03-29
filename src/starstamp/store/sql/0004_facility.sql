-- The shop's own identification number and the people on the bench. Both
-- carry the methods they are approved for, because the approval is what makes
-- a test a requalification rather than a pressure check.

CREATE TABLE facility (
    id              INTEGER PRIMARY KEY,
    rin             TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    address         TEXT,
    approved_from   TEXT NOT NULL,
    approved_until  TEXT NOT NULL,
    methods         TEXT NOT NULL
);

CREATE TABLE technician (
    id               INTEGER PRIMARY KEY,
    badge            TEXT NOT NULL UNIQUE,
    name             TEXT NOT NULL,
    methods          TEXT NOT NULL,
    qualified_from   TEXT NOT NULL,
    qualified_until  TEXT
);

CREATE INDEX technician_by_name ON technician (name);
