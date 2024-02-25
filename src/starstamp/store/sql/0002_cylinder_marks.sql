-- The first schema wrote the spec back as a code plus a pressure and lost the
-- form it was stamped in, which the record of test has to reproduce exactly.
-- Keep the marking as read, and record the gas the cylinder is in.

ALTER TABLE cylinder ADD COLUMN spec_marking TEXT NOT NULL DEFAULT '';
ALTER TABLE cylinder ADD COLUMN service_code TEXT NOT NULL DEFAULT 'N2';

UPDATE cylinder
   SET spec_marking = 'DOT-' || spec_code || COALESCE(service_pressure_psig, '')
 WHERE spec_marking = '';

CREATE INDEX cylinder_by_service ON cylinder (service_code);
