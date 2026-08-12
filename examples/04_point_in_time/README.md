# Point-in-time

```bash
uv run python examples/04_point_in_time/run.py
```

Six demonstrations, in order of how hard they are to talk your way around:

1. **The loader is bound.** The same series read at two knowledge dates returns
   different numbers of observations, because publication lags are stored per
   observation rather than assumed.
2. **Code cannot rebind it.** `load_series("X", as_of=...)` fails static
   analysis. The knowledge date belongs to the plan.
3. **Dated results are checked.** A frame whose `observation_date` column runs
   past the knowledge date fails L1-pit — this catches code that *invents*
   dates instead of reading them.
4. **Future events are refused.** Asking to include an episode that had not
   begun raises `LookAheadError` at plan time, rather than quietly dropping it.
5. **Two knowledge dates, two answers.** The same question as of 2026-06-14 and
   2026-08-01 produces three episodes versus four, and 167 versus 223 return
   cells. Both are correct; only one of them is correct *for that date*.
6. **The cache agrees.** The same code at a different `as_of` has a different
   cache key, so a re-run cannot silently serve yesterday's knowledge.

## Where the defence ends

It cannot detect look-ahead that enters through a *choice*: an episode window, a
threshold or a universe filter picked because you already know how it turned
out. It also models only the vintage your adapter serves — if your hub keeps a
single revised value per observation, quantifact cannot recover the number as
first printed. Both limits are stated in
[`docs/concepts/point-in-time.md`](../../docs/concepts/point-in-time.md).
