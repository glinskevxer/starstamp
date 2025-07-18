-- Marks restored to a cylinder. One row per re-marking, one row per mark, so
-- that a later reader can see what was restored rather than only that
-- something was.

CREATE TABLE remarking (
    id               INTEGER PRIMARY KEY,
    cylinder_id      INTEGER NOT NULL REFERENCES cylinder(id),
    marked_on        TEXT NOT NULL,
    facility_rin     TEXT NOT NULL,
    technician_badge TEXT NOT NULL,
    evidence         TEXT NOT NULL,
    note             TEXT
);

CREATE INDEX remarking_by_cylinder ON remarking (cylinder_id, marked_on);

CREATE TABLE remarking_mark (
    id            INTEGER PRIMARY KEY,
    remarking_id  INTEGER NOT NULL REFERENCES remarking(id),
    kind          TEXT NOT NULL,
    reads         TEXT NOT NULL,
    UNIQUE (remarking_id, kind)
);

CREATE INDEX remarking_mark_by_remarking ON remarking_mark (remarking_id);
