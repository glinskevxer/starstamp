-- What became of a condemned cylinder. The condemning record of test is on the
-- row because the clock for rendering it starts there, and an auditor reading
-- the disposal wants the condemnation without a second lookup.

CREATE TABLE disposal (
    id                 INTEGER PRIMARY KEY,
    cylinder_id        INTEGER NOT NULL REFERENCES cylinder(id),
    requalification_id INTEGER REFERENCES requalification(id),
    method             TEXT NOT NULL,
    performed_on       TEXT NOT NULL,
    condemned_on       TEXT NOT NULL,
    technician_badge   TEXT NOT NULL,
    witness_badge      TEXT,
    scrap_ticket       TEXT,
    returned_to_owner  INTEGER NOT NULL DEFAULT 0,
    note               TEXT,
    UNIQUE (cylinder_id)
);

CREATE INDEX disposal_by_day ON disposal (performed_on);
