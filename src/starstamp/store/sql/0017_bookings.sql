-- Work promised for a day. The lot number lands on the row when the cylinders
-- actually turn up, which is how the shop finds the bookings nobody honoured.

CREATE TABLE booking (
    id          INTEGER PRIMARY KEY,
    owner_id    INTEGER NOT NULL REFERENCES owner_account(id),
    booked_for  TEXT NOT NULL,
    booked_on   TEXT NOT NULL,
    cylinders   INTEGER NOT NULL,
    state       TEXT NOT NULL DEFAULT 'booked',
    lot_id      INTEGER REFERENCES lot(id),
    note        TEXT
);

CREATE INDEX booking_by_day ON booking (booked_for, state);
CREATE INDEX booking_by_owner ON booking (owner_id, booked_for);
