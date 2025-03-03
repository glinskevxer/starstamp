-- The shop's own numbers, dated. A row is never edited: setting a value again
-- writes a new row, so a test from two years ago can still be read against the
-- tolerance that was in force when it was performed.

CREATE TABLE shop_setting (
    id             INTEGER PRIMARY KEY,
    name           TEXT NOT NULL,
    value          TEXT NOT NULL,
    effective_from TEXT NOT NULL,
    set_by         TEXT,
    UNIQUE (name, effective_from)
);

CREATE INDEX setting_by_name ON shop_setting (name, effective_from);
