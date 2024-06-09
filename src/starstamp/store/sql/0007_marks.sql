-- The star and the plus were being worked out at the bench and thrown away.
-- The filling plant needs both of them years later and cannot recompute them,
-- because the readings that produced them are only half the input: the rest is
-- the state of the rig and the history on the day. So they get recorded.

ALTER TABLE requalification ADD COLUMN starred INTEGER NOT NULL DEFAULT 0;
ALTER TABLE requalification ADD COLUMN plus_rated INTEGER NOT NULL DEFAULT 0;
ALTER TABLE requalification ADD COLUMN star_refused TEXT NOT NULL DEFAULT '';
ALTER TABLE requalification ADD COLUMN plus_refused TEXT NOT NULL DEFAULT '';

CREATE INDEX requalification_by_mark ON requalification (starred, performed_on);
