-- Repairs. A repair is not a requalification and does not live in the same
-- table, but the two are read together often enough that the cylinder id is
-- the index both of them hang off.

CREATE TABLE repair (
    id                INTEGER PRIMARY KEY,
    cylinder_id       INTEGER NOT NULL REFERENCES cylinder(id),
    kind              TEXT NOT NULL,
    performed_on      TEXT NOT NULL,
    technician_badge  TEXT NOT NULL,
    facility_rin      TEXT,
    parts             TEXT,
    note              TEXT,
    clears_event_id   INTEGER REFERENCES requalification(id),
    recorded_at       TEXT NOT NULL
);

CREATE INDEX repair_by_cylinder ON repair (cylinder_id, performed_on);
CREATE INDEX repair_by_kind ON repair (kind, performed_on);
