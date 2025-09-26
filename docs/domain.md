# What decides what

Written by `python -m starstamp.tools.generate_domain_reference` from the
module docstrings under `src/starstamp/rules` and `src/starstamp/model`. Do
not edit it by hand.

# The rules

## rules/abandonment.py

Cylinders nobody has come back for.

Every shop has a corner of them: lots finished eighteen months ago whose
owner has stopped answering, cylinders left behind when a customer went out of
business. The shop cannot fill them, cannot sell them and cannot legally throw
them away without trying to give them back first.

The rule the shop can defend is a sequence rather than a date: the lot has to
have been ready for long enough, the owner has to have been written to, and a
further period has to have passed since that letter. Each step is checked
here; none of them is assumed from the one before.

## rules/acetylene.py

Judging an acetylene cylinder.

The criterion is the cylinder's own marked tare weight, which makes this the
same shape of rule as the ultrasonic one: the number a cylinder is held to
came off the cylinder, and a cylinder without that mark cannot be examined
here at all. The refusal for a missing mark is not a condemnation, because a
shop that condemns everything it cannot read is throwing away good steel.

Weight gain is treated separately from weight loss and is not a pass. A
cylinder heavier than its mark has taken on water, and water in an acetylene
cylinder is worse than a light one.

## rules/authorisation.py

Whether this shop, this person and this cylinder can do this today.

Three independent narrowings meet here and none of them subsumes the others.
The cylinder decides which methods exist for it, the facility's approval
decides which of those the shop may perform, and the technician's sign off
decides which of those this person may perform. A method that survives all
three is the only kind that produces a requalification.

The order the checks run in is the order the refusals are useful in. A method
the cylinder never takes is an error in the work order; a method the shop is
not approved for is a scheduling problem; a method the person is not signed
off for is a matter of who picks the cylinder up. Reporting the last of those
when the first is also true sends the wrong person looking.

## rules/fill.py

Whether a cylinder may be filled today, and how far.

This is the question the filling plant asks and the one the whole book exists
to answer. It consumes everything the bench decided: the interval came from
the method, the star came from the readings, the plus came from a tighter
reading of the same numbers, and the gas the cylinder is dedicated to came off
its marks. None of that is recomputed here.

Two refusals are worth keeping apart. A cylinder that is out of test may be
filled again as soon as it is requalified. A cylinder that is condemned never
may. The plant treats those differently and so does this.

## rules/filling.py

Judging a fill after the fact.

The rule that matters is not the gauge reading. It is the pressure the
cylinder will sit at once it has cooled to seventy, because that is the number
the service pressure marking is about. A cylinder filled to 2500 psi at 110
degrees is inside its marking; the same reading at 40 degrees is an overfill,
and the two are indistinguishable without the temperature.

## rules/interval.py

How long a requalification is good for, and when the next one falls due.

The interval is not a property of the cylinder. It is decided by the cylinder,
the gas, and the method that was actually used, and the last of those is the
one shops get wrong. A propane cylinder given an external visual is good for
five years; the same cylinder given a volumetric test on the same day is good
for twelve. Reading the interval off the specification alone puts seven years
on a cylinder that has not earned them.

A star is the other lever. It is not recorded here, only consumed: the star
rules decide whether one may be stamped, and this module turns that answer
into a due date.

## rules/marks.py

The two marks a cylinder can earn beyond the date and the RIN.

A star gets stamped after the requalification date and means the cylinder is
on a ten year interval instead of five. A plus sign means it may be filled ten
percent over its marked service pressure. Neither is a reward for passing.
Both are conclusions drawn from readings the other rules already produced, and
both are refused the moment any one of their conditions is missing.

This is the part of the shop where the composition bites hardest. A star needs
an expansion reading, so it needs a method that takes one, so it needs a
specification that permits that method and a rig that was in calibration on
the day. Every one of those decisions was made somewhere else, and all this
module does is refuse to draw the conclusion when one of them went the other
way.

## rules/method_matrix.py

Which methods a cylinder may be requalified by, and at what pressure.

Two decisions live here and they are not independent. The specification says
which methods are on the table, the gas narrows that further, and the
specification then decides the multiplier that turns service pressure into
test pressure. A shop that gets the multiplier from the method instead of the
specification will test a welded cylinder to five thirds and pass a cylinder
that should have failed.

## rules/pressure_test.py

The criteria a cylinder is held to on the rig.

Which criteria apply is decided by the method, and the method was decided by
the specification. A proof pressure test is judged on whether the cylinder
leaked or took a set; a volumetric test is judged on two numbers and the
cylinder's own marked limit. Neither set of criteria means anything applied to
the other kind of test, and the shop that applies the ten percent rule to a
proof test will pass every one of them.

The rejection elastic expansion is the clearest case. It is stamped on the
cylinder by its maker, it is the largest elastic expansion the cylinder may
show and still be sound, and it is a criterion only when the method actually
measures elastic expansion. A welded cylinder carries no REE at all.

## rules/remarking.py

Whether a cylinder may be re-marked, and from what.

The rule that matters is about evidence rather than about skill. A requalifier
may restore a mark it can show was there; it may not decide what a cylinder is.
So the shop's own records are the best evidence, an owner's declaration is
weaker and is not enough on its own for the marks that say what the cylinder
is, and nothing at all is never enough.

The identity marks are the sharp case. Restoring a serial from the shop's own
record of test is restoring; restoring one from a customer's say so is
inventing a cylinder, and the shop that does it has made two cylinders with
the same serial somewhere in the country.

## rules/repair.py

Which repairs a cylinder may have done to it.

The specification decides this and the decision is not symmetric. A welded
cylinder may be repaired by welding, because welding is how it was made. A
seamless cylinder may not, at any temperature, by anybody: an arc struck on a
seamless cylinder condemns it, and the shop that welds a bracket onto one has
destroyed it rather than repaired it.

Heat treatment runs the other way. Seamless steel can be normalised and put
back in service; high strength steel cannot, which is the reason its whole
service life is shorter.

## rules/storage.py

Charging for cylinders left in the shop.

A shop with four hundred square feet of floor cannot store a customer's
cylinders indefinitely, and the ones that sit longest are almost always the
ones somebody has stopped answering the phone about. So the free period is a
shop setting, the clock runs from the day the lot came in, and the charge is a
daily rate out of the price book like anything else.

The clock stops when the lot goes back, not when the work finished. A lot the
shop finished in a week and the customer collected in July was in the way for
all of June.

## rules/ultrasonic.py

Judging an ultrasonic examination.

The criterion is the cylinder's minimum design wall, which is a share of the
nominal wall its maker built it to rather than a number anybody measures. So
an ultrasonic examination cannot be judged at all on a cylinder whose wall the
book does not carry, and the refusal for that is deliberately different from a
condemnation: one means the shop cannot say, and the other means the cylinder
is finished.

The exam also has to be an exam. Six points across three bands is the floor,
because a scan that only looked at the mid barrel will pass a cylinder that is
thin at the base every time.

## rules/validity.py

Whether a set of readings counts as a requalification at all.

This is the rule that decides what the other rules are allowed to look at. A
permanent expansion of eight percent is a pass under a calibrated rig and
nothing at all under a rig whose certificate lapsed the week before, and the
numbers are identical in both cases. So validity is settled before any
criterion is applied to a reading, and an invalid event can never carry a
mark no matter how good it looks.

The method decides which instruments have to be in date. A proof pressure test
needs the pressure indicator and nothing else, because it takes no expansion
reading, and holding it to the expansion scale's certificate would fail tests
for want of an instrument they never used.

## rules/valve.py

Whether the valve in the cylinder is the one the gas calls for.

The connection is the interlock, so this is a filling rule rather than a
requalification rule: a cylinder with the wrong valve is sound, requalified
and perfectly legal to own. It is only illegal to fill.

## rules/visual.py

Turning what the inspector measured into a verdict.

The limits are fractions of the cylinder's nominal wall, so nothing here can
be decided without knowing the wall. That is deliberate: the same sixteen
thousandth pit is nothing on a heavy walled 3AA and most of the way through a
thin walled 4BA, and a shop that carries one table of absolute depths will
condemn good cylinders and pass bad ones.

Two of the rules read another measurement to decide which limit applies.
Corrosion in a line is held to a much tighter fraction than a pit, but only
once it runs three inches or more, so its length decides which limit its depth
is compared against. A dent is compared against its own width rather than
against the wall at all.


# The vocabulary

## model/acetylene.py

What an acetylene cylinder's examination records.

An acetylene cylinder is not a pressure vessel with gas in it. It is a shell
packed with a porous mass, soaked in acetone, with the gas dissolved in the
acetone. None of that can be pressure tested, so the examination is a weighing
and a look: the mass and the acetone together are most of the cylinder's tare
weight, and a cylinder that has lost weight has lost acetone, which leaves gas
pockets where there should be none.

## model/booking.py

Work promised to a customer for a particular day.

The shop can put a certain number of cylinders across the bench in a day and
no more, and the number is not a guess: it is the number of test systems times
what one rig gets through. Booking is therefore about capacity rather than
about a calendar, and a booking that would take the day past capacity is
refused rather than accepted and apologised for later.

## model/calibration.py

The test system, and the paperwork that says its readings mean anything.

A water jacket rig is three instruments that all have to be in date at once:
the calibrated cylinder that the jacket is proved against, the pressure
indicator that says the cylinder reached test pressure, and the expansion
scale or burette that the reading is taken off. Each carries a certificate
with an expiry, and the shop runs the calibrated cylinder through the rig at
the start of every day it tests.

The daily check is the one that catches a rig going out between certificates,
which is the failure that actually happens. A certificate expiring is caught
by a calendar; a jacket with air trapped in it is caught by a known cylinder
reading three percent low.

## model/contract.py

What a particular account pays, when it is not what everybody pays.

A distributor sending four hundred cylinders a year negotiates, and what they
negotiate is one of two things: a flat price for a charge code, or a discount
off the book. Both are dated the same way the price book is, because an
invoice raised late still has to bill the agreement that was in force when the
work was done.

## model/cylinder.py

The cylinder as the shop knows it: what is stamped on it, plus where it is.

Everything on a cylinder that matters is stamped into the metal, and the
stamping is the only record that travels with it. The book holds a
transcription of those marks and nothing else about the cylinder's
construction, because anything the book invented would be a guess about a
piece of steel somebody else made in 1974.

## model/dates.py

Dates as the shop writes them.

Two calendars meet here. Requalification marks carry a month and a year and
nothing finer, because that is all there is room to stamp into the shoulder of
a cylinder. Everything else the shop does happens on a particular day. Mixing
the two is how a cylinder gets filled a month after it went out of test, so
they are separate types.

## model/defect.py

What the inspector writes down when a cylinder comes across the bench.

An observation is a measurement, not a verdict. Whether a sixteen thousandth
deep pit condemns a cylinder depends on how thick its wall was to begin with
and what it is made of, and neither of those is known here. So this module
records what was seen and leaves the deciding to the rules.

## model/disposal.py

What becomes of a cylinder after it is condemned.

A condemned cylinder is worth money as scrap and is lethal if it goes back
into service, which is why the regulation is not about paperwork: the shop has
to render it incapable of holding pressure. Drilling it, cutting the neck off
or crushing it all count. Putting a sticker on it does not.

The owner can ask for it back, and they are entitled to it, rendered.

## model/event.py

A requalification, as it goes into the record.

The event is what an auditor reads. It carries the cylinder, the day, the
method, who did it under whose number, what the rig read, what the inspector
found, and the verdict that came out of all of it. It also carries whether it
still stands, because the one thing a record of test must never do is change
after the fact.

## model/facility.py

Who is allowed to do the work, and what they are allowed to do.

A requalification is only a requalification if the facility that performed it
held an identification number for that method on that day, and if the person
who performed it was signed off for it. Both of those expire, and both of them
narrow the method matrix further than the cylinder does.

## model/fillrecord.py

What actually went into a cylinder.

A filling record is not a requalification and the shop is not required to keep
one, which is exactly why it is worth keeping: the cylinders that come back
condemned are disproportionately the ones somebody filled hot and topped up
cold, and without a fill log there is no way to show that.

## model/invoice.py

An invoice, as the shop raises it.

Every line names the work it came from: the day, the cylinder and the record
of test. A customer who queries a line gets the record of test back, which is
the only answer worth giving.

## model/lot.py

Cylinders arrive in lots and leave in lots.

A distributor drops forty cylinders on a Tuesday and wants them back by the
end of the month. Nothing in the requalification rules cares about that, and
everything about running the shop does: the promise date is what the front
counter answers the phone with, and the lot is what a condemned cylinder has
to be explained against.

## model/marking.py

Restoring marks a cylinder has worn off.

Twenty years of being dragged across a truck bed takes the stamping off a
cylinder's shoulder, and a cylinder whose marks cannot be read cannot be
filled. It can be re-marked, but only with what was there before: the
requalifier is restoring a record, not making one, and the difference is the
whole of the regulation.

So a re-marking names what it restored and what it restored it from. Nothing
here invents a specification.

## model/method.py

How a cylinder is requalified.

The method is not a preference. It decides which measurements the record of
test must carry, and a record that carries the wrong ones is not a record at
all. Everything downstream branches on this enum rather than on the presence
or absence of a reading.

## model/money.py

Money, in whole cents and nothing else.

A requalification is fourteen dollars and a lot is forty cylinders, so the
arithmetic is small. It is also the arithmetic a customer checks with a
calculator, and a total that is a cent out because it went through a float is
a phone call the shop does not need.

## model/notice.py

What the shop has to tell the owner, and when it told them.

Condemning somebody else's property is the one thing a requalification shop
does that it cannot do quietly. The owner has to be told, in writing, and the
shop has to be able to show later that it was. A notice is therefore a record
in its own right rather than a flag on the condemnation.

## model/owner.py

The customer whose cylinders these are.

A requalification shop almost never owns the cylinders on its floor. Every
cylinder belongs to a distributor, a fire district or a welding shop, and the
account is what the invoice and the condemnation notice both hang off.

## model/pricing.py

What the shop charges, and when it started charging it.

A price is dated for the same reason a calibration certificate is: an invoice
raised today for work done in March has to carry March's price. Nothing here
looks up "the current price" without being told which day it means.

## model/repair.py

Work done to a cylinder that is not a requalification.

A repair is what happens between a suspended requalification and the one that
follows it. Some repairs are ordinary shop work and some of them are only
legal on certain cylinders at all, which is why the kind is an enum rather
than a note in a text field.

## model/service.py

What the cylinder is filled with, and what that costs it.

Service is not a label. It decides whether the inside of the cylinder is
allowed to be wet, whether a ten year interval is on the table at all, and
whether the shop is even permitted to open the valve indoors. The catalogue is
small on purpose: a shop that takes in a gas it has no entry for should have to
add it deliberately.

## model/settings.py

The handful of numbers a shop is allowed to set for itself.

Most of what this package does is fixed by regulation and none of that belongs
here. What does belong here is the shop's own arrangements: how much one rig
gets through in a day, how tight it holds its start of day check, how long it
holds a cylinder before it charges storage. Each one is dated, because
changing a tolerance today must not change what last year's tests meant.

## model/specification.py

The specification stamped into the crown of a cylinder.

The spec is the first thing read off a cylinder and the last word on most of
what follows. It fixes the service pressure, it decides which requalification
methods are legal, and it decides whether the cylinder can ever wear a star.
Everything downstream asks this module rather than matching on strings.

## model/testrecord.py

What comes off the rig when a cylinder is pressurised.

The readings are recorded exactly as the operator read them and are never
adjusted here. A shop that rounds a permanent expansion before storing it has
thrown away the only evidence it has that a borderline cylinder was borderline.

## model/ultrasonic.py

Ultrasonic examination: measuring the wall instead of stretching it.

An ultrasonic requalification does not pressurise the cylinder at all. It
measures the wall at a set of points and compares each reading against the
minimum wall the cylinder was designed to. That makes it a different shape of
evidence from a water jacket test, and the difference matters: a volumetric
test asks whether the cylinder as a whole came back, and this asks whether any
one spot has thinned.

## model/units.py

Measured quantities, all of them integers underneath.

A requalification decision compares an expansion against a limit that is
itself derived from another expansion. Doing that in binary floating point
puts a cylinder on the wrong side of a limit roughly once in every few
thousand tests, and the shop cannot defend the ones it gets wrong. So every
quantity here stores an integer in its smallest stamped unit and every ratio
is an exact Fraction.

## model/valve.py

Valve outlet connections, which are how the gas industry stops mistakes.

Every compressed gas has a connection assigned to it, and the assignments are
deliberately incompatible: an oxygen regulator will not thread onto a hydrogen
cylinder, because hydrogen is left hand threaded and oxygen is not. That is
the whole safety argument, and it only works if the valve in the cylinder is
the one the gas calls for. A shop that fits whatever valve is on the shelf has
quietly removed the interlock.
