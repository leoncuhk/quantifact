# Bring your own data

```bash
uv run --extra duckdb python examples/02_bring_your_own_data/build_hub.py
```

Exports the synthetic store into a DuckDB file, then runs the same analysis
against it through `DuckDBAdapter`. Nothing in the plan, the contracts or the
harness changes — which is the test of whether the adapter protocol is the right
abstraction.

## What your hub has to expose

```sql
CREATE TABLE series_catalog (
    series_id VARCHAR PRIMARY KEY, name VARCHAR, description VARCHAR,
    frequency VARCHAR, unit VARCHAR, source VARCHAR, license_tag VARCHAR,
    currency VARCHAR, geography VARCHAR, asset_class VARCHAR, owner VARCHAR,
    pub_lag_days INTEGER, entitlement_tags VARCHAR, aliases VARCHAR,
    lineage VARCHAR, invariants VARCHAR, content_hash VARCHAR,
    first_obs DATE, last_obs DATE, n_obs INTEGER, value_stats VARCHAR
);
CREATE TABLE series_observations (
    series_id VARCHAR, obs_date DATE, pub_date DATE, value DOUBLE
);
```

`pub_date` is the one column people leave out and the one that matters: without
it a hub cannot answer *what did we know then*, and every historical analysis
built on it is unfalsifiable.

`value_stats` and `invariants` are the second thing people leave out. They are
what let the agent reject a series whose values do not match the concept, and
what let the contract layer generate its checks instead of guessing.

For a vendor feed, write an adapter against the vendor API with the same five
methods and keep your credentials on your side. quantifact ships no data and no
credentials, and cannot make redistribution of licensed data lawful — see
[DISCLAIMER.md](../../DISCLAIMER.md).
