-- The fill log. The temperature is on the row because without it the pressure
-- reading cannot be read back, and the verdict is stored rather than derived
-- because the ceiling depended on a plus rating the cylinder may since have
-- lost.

CREATE TABLE fill (
    id                   INTEGER PRIMARY KEY,
    cylinder_id          INTEGER NOT NULL REFERENCES cylinder(id),
    service_code         TEXT NOT NULL,
    filled_on            TEXT NOT NULL,
    filler_badge         TEXT NOT NULL,
    pressure_psig        INTEGER,
    weight_hundredths_lb INTEGER,
    temperature_f        INTEGER NOT NULL DEFAULT 70,
    settled_psig         INTEGER,
    ceiling_psig         INTEGER,
    verdict              TEXT NOT NULL,
    note                 TEXT
);

CREATE INDEX fill_by_cylinder ON fill (cylinder_id, filled_on);
CREATE INDEX fill_by_day ON fill (filled_on);
CREATE INDEX fill_by_verdict ON fill (verdict, filled_on);
