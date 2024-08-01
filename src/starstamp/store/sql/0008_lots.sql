-- Receiving. A lot belongs to one account and holds the cylinders that came in
-- on one delivery; the line is where a cylinder's fate on that visit is
-- written down, including the record of test that settled it.

CREATE TABLE lot (
    id            INTEGER PRIMARY KEY,
    number        TEXT NOT NULL UNIQUE,
    owner_id      INTEGER NOT NULL REFERENCES owner_account(id),
    received_on   TEXT NOT NULL,
    promised_on   TEXT,
    status        TEXT NOT NULL DEFAULT 'received',
    carrier       TEXT,
    note          TEXT,
    returned_on   TEXT
);

CREATE INDEX lot_by_owner ON lot (owner_id, received_on);
CREATE INDEX lot_by_status ON lot (status);

CREATE TABLE lot_line (
    id                 INTEGER PRIMARY KEY,
    lot_id             INTEGER NOT NULL REFERENCES lot(id),
    cylinder_id        INTEGER NOT NULL REFERENCES cylinder(id),
    added_on           TEXT NOT NULL,
    disposition        TEXT,
    requalification_id INTEGER REFERENCES requalification(id),
    UNIQUE (lot_id, cylinder_id)
);

CREATE INDEX lot_line_by_cylinder ON lot_line (cylinder_id);
