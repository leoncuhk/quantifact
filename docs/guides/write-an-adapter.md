# Write an adapter

Six methods. Everything else — entitlements, publication lags, licence tags —
travels inside `SeriesMeta` rather than in a parallel system.

```python
class MyAdapter:
    name = "my-hub"

    def catalog(self) -> list[SeriesMeta]: ...
    def read_series(self, series_id: str, *, as_of) -> pd.Series: ...
    def tables(self) -> list[str]: ...
    def read_table(self, name: str, *, as_of) -> pd.DataFrame: ...
    def invariants(self, series_id: str) -> list[dict]: ...
    def fingerprint(self, series_ids, *, as_of) -> str: ...
```

## The rules that matter

**`read_series` must honour `as_of`.** Filter on publication date, not on
observation date. If your source cannot tell you when a number became knowable,
say so in the adapter's docstring — do not approximate, because an approximate
knowledge date is worse than an absent one.

**`fingerprint` must change when the visible slice changes.** It is a cache key
input. Hash the content hashes of the series plus the knowledge date; do not
hash a mutable timestamp, or nothing will ever hit the cache.

**`catalog` is a product, not an afterthought.** It is what the agent reads to
choose. Fill in `unit`, `frequency`, `value_stats`, `aliases` and `pub_lag_days`
— those five fields are the difference between a search that binds correctly and
one that binds plausibly.

**`read_table` filters universes by listing dates.** A universe that only
contains names alive today will quietly bias every historical result.

**`invariants` should be real.** Row counts derived from the calendar, ranges
that reflect the instrument (a daily A-share return cannot exceed ±21%),
uniqueness on the natural key.

## Conformance

Run the public suite first:

```bash
qf adapter-check --early-as-of 2022-03-01 --late-as-of 2026-08-01 \
  --json adapter-conformance.json
```

Programmatically, call `quantifact.check_adapter(your_adapter, ...)`. The suite
samples catalog semantics, future-date exclusion, monotone vintage visibility,
deterministic fingerprints and point-in-time reference tables.

Then copy `tests/test_duckdb_adapter.py`, point the fixture at your adapter, and
keep its integration properties: the catalog round-trips, reads are
point-in-time, universes are survivorship-free, and the same plan runs unchanged.
Passing conformance is necessary but not sufficient: it does not prove source
accuracy, complete revision history, licence compliance or full-catalog quality.

## Entitlements

Tag restricted series in `SeriesMeta.entitlement_tags`. Filtering happens at the
index — a user without the tag never sees the series in recall, so there is
nothing for a clever prompt to talk its way into. Do not implement permission
checks in prompts.
