-- Enough of a customer's details to put a letter in the post. The contact
-- column was doing all of this on its own, which is why half the accounts had
-- a phone number in it and the other half had a person's name.

ALTER TABLE owner_account ADD COLUMN address TEXT;
ALTER TABLE owner_account ADD COLUMN phone TEXT;
ALTER TABLE owner_account ADD COLUMN email TEXT;
ALTER TABLE owner_account ADD COLUMN note TEXT;
