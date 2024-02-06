-- The two things every other table hangs off: who owns a cylinder, and the
-- cylinder itself as it is marked.

CREATE TABLE owner_account (
    id           INTEGER PRIMARY KEY,
    code         TEXT NOT NULL UNIQUE,
    name         TEXT NOT NULL,
    contact      TEXT,
    terms_days   INTEGER NOT NULL DEFAULT 30,
    opened_on    TEXT NOT NULL,
    closed_on    TEXT
);

CREATE TABLE cylinder (
    id                     INTEGER PRIMARY KEY,
    serial                 TEXT NOT NULL,
    manufacturer_symbol    TEXT NOT NULL,
    spec_code              TEXT NOT NULL,
    spec_family            TEXT NOT NULL,
    service_pressure_psig  INTEGER,
    permit_number          TEXT,
    dom_year               INTEGER NOT NULL,
    dom_month              INTEGER NOT NULL,
    ree_tenths_cc          INTEGER,
    water_capacity_tenths_l INTEGER,
    tare_hundredths_lb     INTEGER,
    owner_id               INTEGER NOT NULL REFERENCES owner_account(id),
    status                 TEXT NOT NULL DEFAULT 'in_service',
    recorded_on            TEXT NOT NULL,
    UNIQUE (manufacturer_symbol, serial)
);

CREATE INDEX cylinder_by_owner ON cylinder (owner_id);
CREATE INDEX cylinder_by_status ON cylinder (status);
