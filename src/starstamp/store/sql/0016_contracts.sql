-- Negotiated prices. A row is closed and a new one opened the same way the
-- price book works, so an old invoice can still be explained.

CREATE TABLE contract_term (
    id                   INTEGER PRIMARY KEY,
    owner_id             INTEGER NOT NULL REFERENCES owner_account(id),
    code                 TEXT NOT NULL,
    cents                INTEGER,
    discount_numerator   INTEGER,
    discount_denominator INTEGER,
    effective_from       TEXT NOT NULL,
    effective_until      TEXT,
    UNIQUE (owner_id, code, effective_from)
);

CREATE INDEX contract_by_owner ON contract_term (owner_id, code, effective_from);
