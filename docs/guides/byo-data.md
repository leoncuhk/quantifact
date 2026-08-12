# Bring your own data

quantifact ships no data. The demo adapter is synthetic so the project is
evaluable offline; everything real comes through an adapter you control.

## The fastest path: DuckDB

If your data already lives in a warehouse, export two tables and point the
DuckDB adapter at them:

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

```python
from quantifact import Quantifact
from quantifact.data.adapters.duckdb_local import DuckDBAdapter

adapter = DuckDBAdapter("hub.duckdb",
                        tables={"markets": "markets", "episodes": "episodes",
                                "calendar": "calendar"})
qf = Quantifact(".qf", adapter=adapter)
```

## The four columns people leave out

| column | why it matters |
|---|---|
| `pub_date` | without it, point-in-time is unenforceable and every historical claim is unfalsifiable |
| `unit` | "revenue" in units versus thousands is the most common silent error in Chinese and US filings alike |
| `value_stats` | how the search layer tells a CPI *index* from a CPI *rate* when both match the query |
| `invariants` | ship the assertions with the data and the contract layer stops guessing |

## Reference tables

`markets` (or whatever your universe is called) should carry `listed_from` and
`delisted_on` so it can be read survivorship-free. Event tables should carry
`start_date`. The adapter filters both by the knowledge date.

## Licensing

Your adapter, your credentials, your contract with the vendor. quantifact
cannot make redistribution lawful, and most market-data agreements cover derived
works as well as raw data. Read [DISCLAIMER.md](../../DISCLAIMER.md).
