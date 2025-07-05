# Command reference

Written by `python -m starstamp.tools.generate_cli_reference`. Do not edit it
by hand: the build regenerates it and compares.

Every command takes the group options first:

    starstamp --book shop.sqlite3 [--today YYYY-MM-DD] <command> ...

## Exit statuses

- `0` it worked
- `1` something went wrong that the shop has no name for
- `2` the input would not parse, or the domain forbids it
- `3` the book does not hold what was named
- `4` the book is in a state that refuses this
- `5` the regulations forbid it
- `6` the cylinder may not be filled
- `7` the check found a problem
- `8` the check found only warnings
- `9` the file itself is not sound
- `10` the doctor found something

## Commands

### `starstamp about`

Say whose shop this is, what is open, and what is in it.

  - `--json` print it for a script instead

### `starstamp account add`

Open an account.

  - `CODE` (argument)
  - `NAME` (argument)
  - `--contact` who to call about this account
  - `--address` the postal address, commas between lines
  - `--phone`
  - `--email`
  - `--terms` payment terms in days
  - `--opened` the day the account opened, YYYY-MM-DD

### `starstamp account close`

Close an account.

  - `CODE` (argument)
  - `--on` the day it closed, YYYY-MM-DD

### `starstamp account details`

Change how the shop reaches an account.

  - `CODE` (argument)
  - `--contact`
  - `--address` commas between lines
  - `--phone`
  - `--email`
  - `--note`

### `starstamp account letterhead`

Print an account as it goes at the top of a letter.

  - `CODE` (argument)

### `starstamp account list`

List the accounts on the books.

  - `--open-only` leave out accounts that have closed

### `starstamp account reopen`

Reopen a closed account.

  - `CODE` (argument)

### `starstamp account show`

Show one account.

  - `CODE` (argument)

### `starstamp account statement-date`

Say when an invoice raised on a day falls due under the account terms.

  - `CODE` (argument)
  - `INVOICED` (argument)

### `starstamp account unreachable`

Open accounts the shop could not post a condemnation notice to.

### `starstamp backup`

Copy the book safely, while it is in use.

  - `TARGET` (argument)
  - `--overwrite` replace a backup that is already there

### `starstamp book arrive`

Tie a booking to the lot that turned up against it.

  - `BOOKING_ID` (argument)
  - `LOT_NUMBER` (argument)

### `starstamp book cancel`

Cancel a booking and give the room back.

  - `BOOKING_ID` (argument)
  - `--note`

### `starstamp book day`

What is promised for a day, and what is left.

  - `--on` the day to read

### `starstamp book in`

Promise a day's work to an account.

  - `OWNER` (argument)
  - `CYLINDERS` (argument)
  - `--for` the day it is promised for
  - `--note`

### `starstamp book missed`

Bookings whose day has gone and whose cylinders never came.

  - `--on`

### `starstamp book offer`

The next days that could take a given number of cylinders.

  - `CYLINDERS` (argument)
  - `--from` the first day to look at
  - `--within` how many days ahead to look

### `starstamp book week`

The next seven days, with what is free on each.

  - `--from` the first day of the week to show

### `starstamp check`

Look for things in the book that cannot all be true.

  - `--on` the day to read it as of
  - `--warnings-are-fine` exit zero when only warnings are found
  - `--json` print it for a script instead

### `starstamp codes`

List what each exit status means, for whoever writes the batch file.

### `starstamp contract accounts`

Which accounts have anything agreed.

### `starstamp contract agree`

Agree a price with an account, closing whatever it replaces.

  - `OWNER` (argument)
  - `CODE` (argument)
  - `--price` a flat price for this code
  - `--discount` a percentage off the book instead
  - `--from` the day it starts

### `starstamp contract show`

What an account has agreed.

  - `OWNER` (argument)
  - `--on` the day to read it for
  - `--history` show closed terms too

### `starstamp cylinder age`

How old the fleet is, by decade of manufacture.

  - `--owner` only this account's cylinders

### `starstamp cylinder find`

Find cylinders by whatever you happen to know about them.

  - `--owner` one account
  - `--status` one status
  - `--service` one gas
  - `--spec` one specification code, 3AA
  - `--maker` one manufacturer symbol
  - `--made-before` made before this month, YYYY-MM
  - `--made-after` made after this month, YYYY-MM
  - `--limit` stop after this many

### `starstamp cylinder import`

Take a customer's cylinder list into the book.

  - `PATH` (argument)
  - `--owner` the account the list belongs to
  - `--on` the day they came on the books
  - `--write` actually write them; without this it is a dry run

### `starstamp cylinder life`

Everything the book holds about one cylinder, in order.

  - `KEY` (argument)
  - `--only` one kind of entry: test, repair, notice, wall

### `starstamp cylinder list`

List cylinders.

  - `--owner` only this account's cylinders
  - `--status` only cylinders in this status

### `starstamp cylinder owners`

Who has owned a cylinder.

  - `KEY` (argument)

### `starstamp cylinder register`

Take a cylinder onto the books from its marks.

  - `KEY` (argument)
  - `--owner` the account code the cylinder belongs to
  - `--spec` the specification marking, DOT-3AA2015
  - `--dom` date of manufacture as stamped, 06-98
  - `--service` the gas it is in
  - `--ree` rejection elastic expansion in cc, if marked
  - `--water-capacity` water capacity in litres
  - `--tare` tare weight in pounds
  - `--wall` nominal wall in inches, 0.220
  - `--wall-source`
  - `--valve` the CGA outlet fitted, 580
  - `--on` the day it was taken on, YYYY-MM-DD

### `starstamp cylinder service`

Put a cylinder into another gas. The valve comes off with the old one.

  - `KEY` (argument)
  - `GAS` (argument)

### `starstamp cylinder show`

Show one cylinder as the book holds it.

  - `KEY` (argument)

### `starstamp cylinder status`

Move a cylinder between statuses.

  - `KEY` (argument)
  - `STATUS_TEXT` (argument)

### `starstamp cylinder template`

Print a blank cylinder list for a customer to fill in.

  - `--rows` how many example rows to print

### `starstamp cylinder transfer`

Move a cylinder to another account.

  - `KEY` (argument)
  - `OWNER` (argument)
  - `--on` the day it changed hands
  - `--note` why, or what paperwork covers it

### `starstamp cylinder valve`

Record the valve fitted, or say which one the gas calls for.

  - `KEY` (argument)
  - `OUTLET` (argument)
  - `--on` the day it was fitted

### `starstamp cylinder wall`

Record a wall thickness reading.

  - `KEY` (argument)
  - `INCHES` (argument)
  - `--source`
  - `--note`
  - `--on` the day it was measured, YYYY-MM-DD

### `starstamp demo`

Fill an empty book with a month of a small shop's work.

  - `--cylinders` how many to put on the books

### `starstamp doctor`

Run every check there is, and say what each one found.

  - `--on` the day to read the records as of

### `starstamp export cylinders`

Every cylinder on the books.

  - `--owner` only this account's cylinders
  - `--out`

### `starstamp export invoices`

Every invoice line for an account.

  - `OWNER` (argument)
  - `--out`

### `starstamp export records`

Records of test in a window.

  - `--from` first day, YYYY-MM-DD
  - `--to` last day, YYYY-MM-DD
  - `--out`

### `starstamp facility add`

Record the shop's approval.

  - `RIN` (argument)
  - `NAME` (argument)
  - `--from` the day the RIN was issued
  - `--until` the day it expires
  - `--methods` comma separated, volumetric,proof,visual
  - `--address`

### `starstamp facility renew`

Move a RIN's expiry out.

  - `RIN` (argument)
  - `UNTIL` (argument)

### `starstamp facility show`

Show the shop's approval and what it covers.

  - `--rin`

### `starstamp fill check`

Say whether a cylinder may be filled, and to what.

  - `KEY` (argument)
  - `--gas` the gas going in, if it is not what it holds now
  - `--on` the day of the fill
  - `--json` print it for a script instead

### `starstamp fill due`

List cylinders falling due, soonest first.

  - `--within` months ahead to look
  - `--owner` only this account's cylinders
  - `--on` the day to count from

### `starstamp fill log`

What has been put into cylinders.

  - `KEY` (argument)
  - `--from` first day of the window
  - `--to` last day of the window
  - `--overfills` only the overfills

### `starstamp fill record`

Record a fill, refusing the ones the shop should not do.

  - `KEY` (argument)
  - `--gas` the gas going in, if not what it holds
  - `--by` the badge of whoever filled it
  - `--to` the pressure reached, psig
  - `--weight` the weight put in, pounds, for a liquefied gas
  - `--at` degrees F at the fill
  - `--on`
  - `--note`
  - `--anyway` record a fill the shop would have refused

### `starstamp init`

Create the book, or bring an existing one up to the current schema.

### `starstamp invoice aging`

Who owes what, and for how long.

  - `--on` the day to age it at

### `starstamp invoice draft`

Show what an account owes without raising anything.

  - `OWNER` (argument)
  - `--month` the month to bill, YYYY-MM
  - `--from`
  - `--to`

### `starstamp invoice outstanding`

Everything unpaid, oldest due date first.

### `starstamp invoice raise`

Raise an invoice for an account.

  - `OWNER` (argument)
  - `--month` the month to bill, YYYY-MM
  - `--from`
  - `--to`

### `starstamp invoice settle`

Mark an invoice paid.

  - `NUMBER` (argument)
  - `--on`

### `starstamp invoice show`

Show one invoice.

  - `NUMBER` (argument)

### `starstamp invoice statement`

The statement an account gets at the end of the month.

  - `OWNER` (argument)
  - `--month` the month to state, YYYY-MM
  - `--from`
  - `--to`

### `starstamp lot add`

Put more cylinders on a lot that is already open.

  - `NUMBER` (argument)
  - `KEYS` (argument)
  - `--on`

### `starstamp lot history`

Every lot an account has sent in.

  - `OWNER` (argument)

### `starstamp lot open`

Every lot still in the shop.

### `starstamp lot ready`

Say a lot is finished and ready to go back.

  - `NUMBER` (argument)

### `starstamp lot receive`

Book a delivery in.

  - `OWNER` (argument)
  - `KEYS` (argument)
  - `--on` the day it arrived
  - `--promised` the day it was promised back
  - `--carrier`
  - `--note`

### `starstamp lot return`

Send a lot back to its owner.

  - `NUMBER` (argument)
  - `--on`

### `starstamp lot show`

Show a lot and everything on it.

  - `NUMBER` (argument)

### `starstamp lot storage`

Lots that have been in the way longer than the free period.

  - `--on` the day to count to
  - `--owner` only this account

### `starstamp lot uncollected`

Lots that are ready and that nobody has come for.

  - `--on` the day to read it for
  - `--write` write to the accounts that are overdue

### `starstamp notice draft`

Draft everything the shop owes.

  - `--reminders` also draft due and out of test reminders
  - `--within` months ahead for reminders
  - `--owner` only this account
  - `--on`

### `starstamp notice late`

Condemnation letters the shop is past the deadline on.

  - `--on`

### `starstamp notice list`

What has been written and what has gone out.

  - `--owner` only this account
  - `--unsent` only the ones still to go out

### `starstamp notice send`

Mark a letter as gone out.

  - `NOTICE_ID` (argument)
  - `--on`

### `starstamp notice show`

Print one letter.

  - `NOTICE_ID` (argument)

### `starstamp price list`

What the shop charges.

  - `--on` the day to read prices for
  - `--history` show every price for one code

### `starstamp price set`

Open a new price, closing whatever it replaces.

  - `CODE` (argument)
  - `AMOUNT` (argument)
  - `--from` the day it starts, YYYY-MM-DD
  - `--description`

### `starstamp repair do`

Book a repair.

  - `KEY` (argument)
  - `KIND` (argument)
  - `--tech` who did it
  - `--on` the day it was done
  - `--parts` what went in, for a valve change
  - `--note`
  - `--rin` the number it was done under, where one is needed

### `starstamp repair held`

Every cylinder sitting under a suspension.

### `starstamp repair history`

Every repair on a cylinder.

  - `KEY` (argument)

### `starstamp repair options`

What this cylinder may legally have done to it.

  - `KEY` (argument)

### `starstamp report bench`

The work sheet: what is in the shop and what each one needs.

  - `--on` the day to make the sheet for

### `starstamp report close`

The month end pack: work, money and what is coming.

  - `--month` the month to close, YYYY-MM

### `starstamp report condemnations`

What was condemned, and what those cylinders had in common.

  - `--from` first day of the window
  - `--to` last day of the window

### `starstamp report cycle`

How long lots take to get through the shop.

  - `--from` first day of the window
  - `--to` last day of the window

### `starstamp report day`

Everything that happened on one day.

  - `--on` the day to read, YYYY-MM-DD
  - `--tests-only` only the records of test

### `starstamp report fleet`

One account's cylinders, taken together.

  - `OWNER` (argument)
  - `--within` months ahead to list
  - `--on` the day to read it for

### `starstamp report floor`

What of an account's is in the shop right now.

  - `OWNER` (argument)

### `starstamp report forecast`

What is coming, from the due dates already in the book.

  - `--months` how far ahead to look
  - `--on` the day to count from
  - `--json` print it for a script instead

### `starstamp report gas`

The fleet and the work, cut by what is in the cylinders.

  - `--from` first day of the window
  - `--to` last day of the window

### `starstamp report ownership`

Cylinders that changed hands in a window.

  - `--from` first day of the window
  - `--to` last day of the window

### `starstamp report pack`

Write an audit pack to a directory: a packet per cylinder and the sheets.

  - `DIRECTORY` (argument)
  - `--from` first day of the period
  - `--to` last day of the period

### `starstamp report packet`

The audit packet for one cylinder.

  - `KEY` (argument)
  - `--all` include reversed records

### `starstamp report rig`

How the test systems are doing.

  - `SYSTEM_CODE` (argument)
  - `--from` first day of the window
  - `--to` last day of the window

### `starstamp report technicians`

What each person got through, and who sits away from the middle.

  - `--from` first day of the window
  - `--to` last day of the window

### `starstamp report throughput`

What the shop got through in a window.

  - `--from` first day, YYYY-MM-DD
  - `--to` last day, YYYY-MM-DD
  - `--by`

### `starstamp report unbilled`

Work the shop has done and not charged for.

  - `--on` the day to count up to

### `starstamp report worklist`

Everything the shop owes somebody, on one list.

  - `--on` the day to read it for
  - `--due-within` months ahead for due dates

### `starstamp requal batch`

Enter a day's bench sheet in one go.

  - `PATH` (argument)
  - `--tech` the badge of whoever did the work
  - `--system` the test system used
  - `--on` the day of the sheet
  - `--method`

### `starstamp requal due`

What is coming due, and the method the shop would use on each.

  - `--within` months ahead to look
  - `--owner` only this account
  - `--tech` whose sign off to plan against
  - `--on`

### `starstamp requal history`

Show every record of test for a cylinder.

  - `KEY` (argument)
  - `--all` include reversed records

### `starstamp requal run`

Requalify a cylinder and write the record of test.

  - `KEY` (argument)
  - `--tech` the badge of whoever did the work
  - `--method` leave out to let the shop choose
  - `--system` the test system used
  - `--on` the day of the test, YYYY-MM-DD
  - `--applied` the pressure reached, psig
  - `--hold` hold time in seconds
  - `--total` total expansion in cc
  - `--permanent` permanent expansion in cc
  - `--leaked` the cylinder leaked under pressure
  - `--distorted` the cylinder took a visible set
  - `--defect` kind:depth:length:note, repeat for each condition found
  - `--scan` ultrasonic readings, M1:0.215,M2:0.214 and so on
  - `--tare` the weight on the scale now, in pounds
  - `--plugs-bad` the fusible plugs are unsound
  - `--mass-settled` the porous mass has settled
  - `--shell-bad` the shell is unsound
  - `--cap-bad` the cap is unsound
  - `--rin` name the RIN when the book holds more than one

### `starstamp requal sheet`

Print a blank bench sheet.

  - `--rows` how many example rows

### `starstamp requal show`

Show one record of test in full.

  - `EVENT_ID` (argument)

### `starstamp restate certificate`

Shorten a certificate and pull the work it no longer covers.

  - `SYSTEM_CODE` (argument)
  - `INSTRUMENT` (argument)
  - `SERIAL` (argument)
  - `CORRECTED_UNTIL` (argument)
  - `--reason` what the calibration house said
  - `--dry-run` show what would be pulled and write nothing

### `starstamp restate correct`

Reverse a record and rewrite it with the numbers it should have had.

  - `EVENT_ID` (argument)
  - `--reason` what was written down wrong
  - `--applied` the corrected pressure, psig
  - `--total` the corrected total expansion
  - `--permanent` the corrected permanent expansion
  - `--hold` hold time in seconds
  - `--tech` the badge it should have been against
  - `--system` the rig it should have been

### `starstamp restate reverse`

Reverse a single record of test.

  - `EVENT_ID` (argument)
  - `--reason` why the record is being pulled

### `starstamp restate window`

List the standing records a rig produced between two days.

  - `SYSTEM_CODE` (argument)
  - `FIRST` (argument)
  - `LAST` (argument)

### `starstamp restore`

Put a backup back in place of the book.

  - `SOURCE` (argument)
  - `--overwrite` replace the book that is there

### `starstamp rig certify`

File a calibration certificate.

  - `SYSTEM_CODE` (argument)
  - `INSTRUMENT` (argument)
  - `--serial` the instrument's serial number
  - `--issued` the day the certificate was issued
  - `--until` the day it expires
  - `--by` the calibration house
  - `--standard`

### `starstamp rig check`

Record the start of day run of the calibrated cylinder.

  - `SYSTEM_CODE` (argument)
  - `EXPECTED` (argument)
  - `OBSERVED` (argument)
  - `--on` the day of the check
  - `--tech` who ran it

### `starstamp rig status`

Say whether a rig was fit to test on a day.

  - `SYSTEM_CODE` (argument)
  - `--on` the day to read it for

### `starstamp scrap log`

Everything dealt with in a window.

  - `--from` first day of the window
  - `--to` last day of the window

### `starstamp scrap outstanding`

Condemned cylinders nobody has dealt with.

  - `--on`
  - `--late-only` only the ones past the deadline

### `starstamp scrap render`

Render a condemned cylinder incapable of holding pressure.

  - `KEY` (argument)
  - `METHOD` (argument)
  - `--tech` who did it
  - `--witness` who watched
  - `--ticket` the scrap yard's ticket number
  - `--return-to-owner` the owner asked for it back
  - `--note`
  - `--on`

### `starstamp setting history`

Every value a setting has had.

  - `NAME` (argument)

### `starstamp setting list`

What the shop is working to.

  - `--on` the day to read them for

### `starstamp setting set`

Set a value from a day, leaving what came before it alone.

  - `NAME` (argument)
  - `VALUE` (argument)
  - `--from` the day it takes effect
  - `--by` who set it

### `starstamp stats`

Count what is in the book.

  - `--json` print it for a script instead

### `starstamp tech add`

Sign somebody off.

  - `BADGE` (argument)
  - `NAME` (argument)
  - `--methods` comma separated methods they are signed off for
  - `--from` the day they were signed off
  - `--until` the day it lapses, if it does

### `starstamp tech lapsing`

Sign offs that are about to run out, and any that already have.

  - `--within` days ahead to look
  - `--on`

### `starstamp tech list`

Who is on the bench and what they hold.

### `starstamp tech renew`

Move somebody's sign off out.

  - `BADGE` (argument)
  - `--until` the new end date, or leave it out for no end

### `starstamp tech show`

One person: what they hold and what they have been doing.

  - `BADGE` (argument)
  - `--from` first day of the window
  - `--to` last day of the window

### `starstamp tech sign-off`

Sign somebody off for one more method.

  - `BADGE` (argument)
  - `METHOD` (argument)

### `starstamp vacuum`

Rebuild the file and give back the space deletes left behind.

### `starstamp verify`

Ask the file whether it is sound.

_123 commands._
