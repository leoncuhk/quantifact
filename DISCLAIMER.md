# Disclaimer

**Not investment advice.** quantifact is research infrastructure. It does not
produce recommendations, signals, or trading logic, and nothing it computes
should be read as advice to buy or sell anything.

**The bundled data is synthetic.** The demo adapter generates deterministic
pseudo-random series with a fixed seed. Its "markets", "episodes" and macro
indicators are shaped like real ones so the pipeline can be exercised offline;
they are not market history and must never be used to draw conclusions about
real assets.

**Bring your own data, and your own licences.** Real adapters are yours to
write and yours to license. quantifact ships no vendor data and no vendor
credentials, and it cannot make redistribution of licensed data lawful. Check
your data agreements before pointing an adapter at them, and note that most
market-data contracts also cover derived works.

**Point-in-time is a defence, not a guarantee.** The knowledge date is enforced
at the loader, checked on dated output columns and carried in the cache key.
It cannot detect look-ahead that enters through a parameter chosen with
hindsight, nor model revisions to a number beyond the vintage your adapter
serves. See `docs/concepts/point-in-time.md` for the exact boundary.

**No warranty.** Licensed under Apache-2.0, which includes a disclaimer of
warranties and limitation of liability. Read it before relying on this software
for anything that matters.

**No affiliation.** The architecture is a public talk's; the implementation is
independent. Bridgewater Associates is not involved in this project.
