-- Calibration certificates and the start of day checks. Both are evidence
-- rather than configuration: a certificate that was in force in 2022 stays in
-- the book after it is superseded, because an event from 2022 rests on it.

CREATE TABLE calibration_certificate (
    id           INTEGER PRIMARY KEY,
    system_code  TEXT NOT NULL,
    instrument   TEXT NOT NULL,
    serial       TEXT NOT NULL,
    issued_on    TEXT NOT NULL,
    valid_until  TEXT NOT NULL,
    issued_by    TEXT NOT NULL,
    standard     TEXT NOT NULL DEFAULT 'NIST traceable',
    superseded   INTEGER NOT NULL DEFAULT 0,
    note         TEXT
);

CREATE INDEX certificate_by_system ON calibration_certificate (system_code, instrument, issued_on);

CREATE TABLE system_check (
    id                INTEGER PRIMARY KEY,
    system_code       TEXT NOT NULL,
    checked_on        TEXT NOT NULL,
    expected_tenths_cc INTEGER NOT NULL,
    observed_tenths_cc INTEGER NOT NULL,
    tolerance_numerator INTEGER NOT NULL DEFAULT 1,
    tolerance_denominator INTEGER NOT NULL DEFAULT 1,
    technician_badge  TEXT,
    UNIQUE (system_code, checked_on)
);
