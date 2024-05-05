-- The record of test. Rows here are append only: a row is reversed and
-- replaced, never updated, apart from the state column that says so.

CREATE TABLE requalification (
    id                    INTEGER PRIMARY KEY,
    cylinder_id           INTEGER NOT NULL REFERENCES cylinder(id),
    performed_on          TEXT NOT NULL,
    method                TEXT NOT NULL,
    facility_rin          TEXT NOT NULL,
    technician_badge      TEXT NOT NULL,
    system_code           TEXT,
    outcome               TEXT NOT NULL,
    reasons               TEXT NOT NULL DEFAULT '',
    notes                 TEXT NOT NULL DEFAULT '',
    applied_psig          INTEGER,
    hold_seconds          INTEGER,
    total_tenths_cc       INTEGER,
    permanent_tenths_cc   INTEGER,
    leaked                INTEGER NOT NULL DEFAULT 0,
    distorted             INTEGER NOT NULL DEFAULT 0,
    wall_thousandths_in   INTEGER,
    state                 TEXT NOT NULL DEFAULT 'recorded',
    reverses_id           INTEGER REFERENCES requalification(id),
    recorded_at           TEXT NOT NULL
);

CREATE INDEX requalification_by_cylinder ON requalification (cylinder_id, performed_on);
CREATE INDEX requalification_by_day ON requalification (performed_on);
CREATE INDEX requalification_by_system ON requalification (system_code, performed_on);

CREATE TABLE requalification_finding (
    id                    INTEGER PRIMARY KEY,
    requalification_id    INTEGER NOT NULL REFERENCES requalification(id),
    kind                  TEXT NOT NULL,
    depth_thousandths_in  INTEGER,
    length_thousandths_in INTEGER,
    result                TEXT NOT NULL,
    reason                TEXT NOT NULL,
    note                  TEXT
);

CREATE INDEX finding_by_requalification ON requalification_finding (requalification_id);
