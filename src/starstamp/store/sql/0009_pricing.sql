-- The price book, dated. A row is never edited: raising a price closes the old
-- row and opens a new one, so an invoice raised late still finds the price
-- that was in force on the day the work was done.

CREATE TABLE price_item (
    id               INTEGER PRIMARY KEY,
    code             TEXT NOT NULL,
    description      TEXT NOT NULL,
    cents            INTEGER NOT NULL,
    effective_from   TEXT NOT NULL,
    effective_until  TEXT,
    UNIQUE (code, effective_from)
);

CREATE INDEX price_by_code ON price_item (code, effective_from);

CREATE TABLE invoice (
    id            INTEGER PRIMARY KEY,
    number        TEXT NOT NULL UNIQUE,
    owner_id      INTEGER NOT NULL REFERENCES owner_account(id),
    raised_on     TEXT NOT NULL,
    due_on        TEXT NOT NULL,
    first_day     TEXT NOT NULL,
    last_day      TEXT NOT NULL,
    total_cents   INTEGER NOT NULL,
    settled_on    TEXT
);

CREATE INDEX invoice_by_owner ON invoice (owner_id, raised_on);

CREATE TABLE invoice_line (
    id                 INTEGER PRIMARY KEY,
    invoice_id         INTEGER NOT NULL REFERENCES invoice(id),
    code               TEXT NOT NULL,
    description        TEXT NOT NULL,
    performed_on       TEXT NOT NULL,
    cylinder_id        INTEGER REFERENCES cylinder(id),
    requalification_id INTEGER REFERENCES requalification(id),
    count              INTEGER NOT NULL DEFAULT 1,
    unit_cents         INTEGER NOT NULL,
    line_cents         INTEGER NOT NULL
);

CREATE INDEX invoice_line_by_invoice ON invoice_line (invoice_id);
