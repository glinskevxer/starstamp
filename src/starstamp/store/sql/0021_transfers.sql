-- Who owned a cylinder, and when. The cylinder row carries the owner it has
-- now; this carries the rest, because a condemnation notice five years later
-- has to go to whoever owned it at the time of the test, not to whoever owns
-- it today.

CREATE TABLE ownership_transfer (
    id            INTEGER PRIMARY KEY,
    cylinder_id   INTEGER NOT NULL REFERENCES cylinder(id),
    from_owner_id INTEGER REFERENCES owner_account(id),
    to_owner_id   INTEGER NOT NULL REFERENCES owner_account(id),
    moved_on      TEXT NOT NULL,
    note          TEXT
);

CREATE INDEX transfer_by_cylinder ON ownership_transfer (cylinder_id, moved_on);
CREATE INDEX transfer_by_from ON ownership_transfer (from_owner_id);
CREATE INDEX transfer_by_to ON ownership_transfer (to_owner_id);
