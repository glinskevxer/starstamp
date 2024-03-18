-- Nothing in a visual inspection can be judged without the wall the pit was
-- measured into, and the first schema had nowhere to put it. It comes off the
-- manufacturer's data sheet or off an ultrasonic reading taken in the shop,
-- so it is nullable and the rules refuse rather than guess when it is absent.

ALTER TABLE cylinder ADD COLUMN nominal_wall_thousandths_in INTEGER;
ALTER TABLE cylinder ADD COLUMN wall_source TEXT;

CREATE TABLE wall_reading (
    id                     INTEGER PRIMARY KEY,
    cylinder_id            INTEGER NOT NULL REFERENCES cylinder(id),
    taken_on               TEXT NOT NULL,
    thousandths_in         INTEGER NOT NULL,
    source                 TEXT NOT NULL,
    note                   TEXT
);

CREATE INDEX wall_reading_by_cylinder ON wall_reading (cylinder_id, taken_on);
