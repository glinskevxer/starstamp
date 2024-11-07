-- Ultrasonic readings hang off the record of test the same way findings do.
-- They are kept point by point rather than as a minimum, because the auditor
-- asks where the thin spot was and the shop asks whether it is moving.

CREATE TABLE ultrasonic_reading (
    id                 INTEGER PRIMARY KEY,
    requalification_id INTEGER NOT NULL REFERENCES requalification(id),
    band               TEXT NOT NULL,
    position_index     INTEGER NOT NULL,
    thousandths_in     INTEGER NOT NULL,
    UNIQUE (requalification_id, band, position_index)
);

CREATE INDEX ultrasonic_by_requalification ON ultrasonic_reading (requalification_id);
