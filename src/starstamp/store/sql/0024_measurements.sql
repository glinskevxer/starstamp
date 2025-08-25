-- Measurements read off a cylinder after it was taken on the books. The tare
-- weight and the water capacity get re-read when a stamping is hard to make
-- out, and the reading that was used at the time is worth keeping: an
-- acetylene cylinder condemned on weight was condemned against one of these.

CREATE TABLE measurement (
    id           INTEGER PRIMARY KEY,
    cylinder_id  INTEGER NOT NULL REFERENCES cylinder(id),
    taken_on     TEXT NOT NULL,
    kind         TEXT NOT NULL,
    value        INTEGER NOT NULL,
    source       TEXT NOT NULL,
    note         TEXT
);

CREATE INDEX measurement_by_cylinder ON measurement (cylinder_id, taken_on);
CREATE INDEX measurement_by_kind ON measurement (kind, taken_on);
