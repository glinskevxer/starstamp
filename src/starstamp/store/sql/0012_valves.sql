-- The valve in the cylinder. It is not part of the cylinder's marking and it
-- changes several times over a cylinder's life, but the filling plant cannot
-- answer its own question without it, so the book carries the one fitted now
-- and the day it went in.

ALTER TABLE cylinder ADD COLUMN valve_outlet TEXT;
ALTER TABLE cylinder ADD COLUMN valve_installed_on TEXT;

CREATE INDEX cylinder_by_valve ON cylinder (valve_outlet);
