-- The index checker found nine references with nothing to look them up by.
-- Most of them are the columns that tie a row back to the record of test that
-- produced it, which is exactly the lookup an audit does over and over.

CREATE INDEX booking_by_lot ON booking (lot_id);
CREATE INDEX disposal_by_requalification ON disposal (requalification_id);
CREATE INDEX invoice_line_by_requalification ON invoice_line (requalification_id);
CREATE INDEX invoice_line_by_cylinder ON invoice_line (cylinder_id);
CREATE INDEX lot_line_by_requalification ON lot_line (requalification_id);
CREATE INDEX notice_by_requalification ON notice (requalification_id);
CREATE INDEX notice_by_cylinder ON notice (cylinder_id);
CREATE INDEX repair_by_cleared_event ON repair (clears_event_id);
CREATE INDEX requalification_by_reversal ON requalification (reverses_id);
