-- The weighing that stands in for a pressure test on an acetylene cylinder.
-- One row per record of test, because the whole examination is one weighing
-- and four looks.

CREATE TABLE acetylene_exam (
    requalification_id      INTEGER PRIMARY KEY REFERENCES requalification(id),
    tare_now_hundredths_lb  INTEGER NOT NULL,
    marked_hundredths_lb    INTEGER NOT NULL,
    fuse_plugs_sound        INTEGER NOT NULL DEFAULT 1,
    mass_settled            INTEGER NOT NULL DEFAULT 0,
    shell_sound             INTEGER NOT NULL DEFAULT 1,
    cap_sound               INTEGER NOT NULL DEFAULT 1,
    note                    TEXT
);
