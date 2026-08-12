---
id: event-study
applies_to: comparing an event against historical episodes
---
# Event study across episodes

1. **Fix the episode set and the window before pulling data.** Both go in
   `resolved_assumptions`. Changing either after seeing the result is how a
   desk talks itself into a conclusion.
2. **Take the universe from the spine as of the knowledge date**, never from
   whichever series happen to exist. Younger names have no return for older
   episodes; declare those columns nullable rather than dropping the names.
3. **Measure the response over a window fixed in advance**, the same window for
   every episode.
4. **Align macro context in event time**, not calendar time, and state the
   pre/post span.
5. **Break the comparison out by asset class** when more than one episode is
   involved: equities, rates, FX and commodities transmit a shock through
   different channels, so a pooled scatter hides more than it reveals.
6. **Put an exact row-count invariant on the fact table** — markets present at
   each episode start, times episodes. A join that silently drops an entity is
   the most common failure in this shape of analysis and the cheapest to catch.
