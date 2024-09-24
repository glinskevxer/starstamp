-- Letters to owners. A condemnation notice is the one the regulator cares
-- about, and the sent date is the part that matters, so it is a column rather
-- than a note.

CREATE TABLE notice (
    id                 INTEGER PRIMARY KEY,
    owner_id           INTEGER NOT NULL REFERENCES owner_account(id),
    cylinder_id        INTEGER NOT NULL REFERENCES cylinder(id),
    kind               TEXT NOT NULL,
    raised_on          TEXT NOT NULL,
    body               TEXT NOT NULL,
    state              TEXT NOT NULL DEFAULT 'drafted',
    sent_on            TEXT,
    requalification_id INTEGER REFERENCES requalification(id)
);

CREATE INDEX notice_by_owner ON notice (owner_id, raised_on);
CREATE INDEX notice_by_state ON notice (state, kind);
