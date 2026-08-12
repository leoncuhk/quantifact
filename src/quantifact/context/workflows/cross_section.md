---
id: cross-section
applies_to: ranking or scoring a universe at one date
---
# Cross-section at a date

1. **One row per entity, one knowledge date.** State it in `row_expectation`
   and enforce it with a `unique` invariant on the entity key.
2. **Every input must be knowable at that date.** Fundamentals carry a
   publication lag; using a figure the market did not have is the whole of
   look-ahead in one line.
3. **Declare the universe from the spine**, including names that have since
   delisted, or the ranking is measured on survivors only.
4. **Give every measure a unit** and never mix percent with ratio in the same
   column name — the contract layer will catch it, but only if the units are
   declared honestly.
5. **Sort is part of the answer.** A ranking table without a declared sort is
   not reproducible.
