"""A DuckDB adapter — the shape most in-house data hubs already have.

Two tables carry everything:

``series_catalog``       one row per series: the metadata an agent binds against
``series_observations``  (series_id, obs_date, pub_date, value)

The bitemporal columns are not optional. ``pub_date`` is what makes the
knowledge date enforceable, and a hub that only stores ``obs_date`` cannot
answer "what did we know then" no matter how good the agent on top of it is.
Reference tables are read as-is; those with an ``as_of`` semantic column
(``listed_from`` / ``delisted_on`` / ``start_date``) are filtered here.

Install with the extra: ``pip install "quantifact[duckdb]"``.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from ...plan.model import parse_date
from ..registry import SeriesMeta

CATALOG_DDL = """
CREATE TABLE IF NOT EXISTS series_catalog (
    series_id VARCHAR PRIMARY KEY,
    name VARCHAR, description VARCHAR, frequency VARCHAR, unit VARCHAR,
    source VARCHAR, license_tag VARCHAR, currency VARCHAR, geography VARCHAR,
    asset_class VARCHAR, owner VARCHAR, pub_lag_days INTEGER,
    entitlement_tags VARCHAR, aliases VARCHAR, lineage VARCHAR,
    invariants VARCHAR, content_hash VARCHAR,
    first_obs DATE, last_obs DATE, n_obs INTEGER, value_stats VARCHAR
);
"""
OBSERVATIONS_DDL = """
CREATE TABLE IF NOT EXISTS series_observations (
    series_id VARCHAR, obs_date DATE, pub_date DATE, value DOUBLE
);
"""


def _connect(path: str | Path, read_only: bool = True):
    try:
        import duckdb
    except ImportError as e:  # pragma: no cover - optional dependency
        raise RuntimeError(
            'duckdb is not installed; pip install "quantifact[duckdb]"') from e
    return duckdb.connect(str(path), read_only=read_only)


class DuckDBAdapter:
    """Serve a bitemporal series hub held in a single DuckDB file."""

    name = "duckdb"

    def __init__(self, path: str | Path, tables: dict[str, str] | None = None):
        self.path = Path(path)
        # logical name -> physical table name for reference tables
        self.table_map = tables or {}
        self._catalog: list[SeriesMeta] | None = None

    # ------------------------------------------------------------- catalog
    def catalog(self) -> list[SeriesMeta]:
        if self._catalog is None:
            con = _connect(self.path)
            try:
                rows = con.execute("SELECT * FROM series_catalog").fetchdf()
            finally:
                con.close()
            self._catalog = [self._to_meta(r) for _, r in rows.iterrows()]
        return list(self._catalog)

    @staticmethod
    def _to_meta(r: pd.Series) -> SeriesMeta:
        def txt(v, default=None):
            """DuckDB hands back NaN for SQL NULL in object columns."""
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return default
            return str(v)

        def js(v, default):
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return default
            return json.loads(v) if isinstance(v, str) else v

        return SeriesMeta(
            series_id=r["series_id"], name=r["name"], description=r["description"],
            frequency=r["frequency"], unit=r["unit"], source=r["source"],
            license_tag=txt(r.get("license_tag"), "unspecified"),
            currency=txt(r.get("currency")), geography=txt(r.get("geography")),
            asset_class=txt(r.get("asset_class")),
            owner=txt(r.get("owner"), "unknown"),
            pub_lag_days=int(r.get("pub_lag_days") or 0),
            entitlement_tags=js(r.get("entitlement_tags"), []),
            aliases=js(r.get("aliases"), []), lineage=js(r.get("lineage"), []),
            invariants=js(r.get("invariants"), []),
            content_hash=txt(r.get("content_hash"), ""),
            first_obs=str(r["first_obs"]) if r.get("first_obs") is not None else None,
            last_obs=str(r["last_obs"]) if r.get("last_obs") is not None else None,
            n_obs=int(r.get("n_obs") or 0),
            value_stats=js(r.get("value_stats"), {}))

    # -------------------------------------------------------------- reads
    def read_series(self, series_id: str, *, as_of: str | date) -> pd.Series:
        con = _connect(self.path)
        try:
            df = con.execute(
                "SELECT obs_date, value FROM series_observations "
                "WHERE series_id = ? AND pub_date <= ? ORDER BY obs_date",
                [series_id, str(parse_date(as_of))]).fetchdf()
        finally:
            con.close()
        s = pd.Series(df["value"].to_numpy(dtype="float64"),
                      index=pd.to_datetime(df["obs_date"]), name=series_id)
        s.index.name = "obs_date"
        return s

    def tables(self) -> list[str]:
        return sorted(self.table_map)

    def read_table(self, name: str, *, as_of: str | date) -> pd.DataFrame:
        physical = self.table_map[name]
        con = _connect(self.path)
        try:
            df = con.execute(f"SELECT * FROM {physical}").fetchdf()
        finally:
            con.close()
        cut = pd.Timestamp(parse_date(as_of))
        if "listed_from" in df.columns:
            alive = pd.to_datetime(df["listed_from"]) <= cut
            if "delisted_on" in df.columns:
                gone = pd.to_datetime(df["delisted_on"])
                alive &= gone.isna() | (gone >= cut)
                df = df.drop(columns=["delisted_on"])
            df = df[alive]
        elif "start_date" in df.columns:
            df = df[pd.to_datetime(df["start_date"]) <= cut]
        return df.reset_index(drop=True)

    def invariants(self, series_id: str) -> list[dict[str, Any]]:
        return next((m.invariants for m in self.catalog()
                     if m.series_id == series_id), [])

    def fingerprint(self, series_ids: Iterable[str], *, as_of: str | date) -> str:
        by_id = {m.series_id: m for m in self.catalog()}
        h = hashlib.sha256()
        h.update(str(parse_date(as_of)).encode())
        for sid in sorted(series_ids):
            h.update(sid.encode())
            h.update((by_id[sid].content_hash or "").encode())
        return h.hexdigest()[:16]


def export_store(store, path: str | Path,
                 tables: dict[str, pd.DataFrame] | None = None) -> Path:
    """Write a ``SeriesStore`` into a DuckDB file in the layout above.

    Used by the examples and tests so the DuckDB path is exercised without a
    proprietary database, and useful as a reference for what an in-house hub
    needs to expose.
    """
    path = Path(path)
    if path.exists():
        path.unlink()
    con = _connect(path, read_only=False)
    try:
        con.execute(CATALOG_DDL)
        con.execute(OBSERVATIONS_DDL)
        cat_rows, obs_frames = [], []
        for meta in store.all_meta():
            cat_rows.append({
                "series_id": meta.series_id, "name": meta.name,
                "description": meta.description, "frequency": meta.frequency,
                "unit": meta.unit, "source": meta.source,
                "license_tag": meta.license_tag, "currency": meta.currency,
                "geography": meta.geography, "asset_class": meta.asset_class,
                "owner": meta.owner, "pub_lag_days": meta.pub_lag_days,
                "entitlement_tags": json.dumps(meta.entitlement_tags),
                "aliases": json.dumps(meta.aliases),
                "lineage": json.dumps(meta.lineage),
                "invariants": json.dumps(meta.invariants),
                "content_hash": meta.content_hash,
                "first_obs": meta.first_obs, "last_obs": meta.last_obs,
                "n_obs": meta.n_obs, "value_stats": json.dumps(meta.value_stats)})
            frame = store.read_frame(meta.series_id).reset_index()
            frame.insert(0, "series_id", meta.series_id)
            obs_frames.append(frame[["series_id", "obs_date", "pub_date", "value"]])
        catalog = pd.DataFrame(cat_rows)                      # noqa: F841
        observations = pd.concat(obs_frames, ignore_index=True)  # noqa: F841
        con.execute("INSERT INTO series_catalog SELECT * FROM catalog")
        con.execute("INSERT INTO series_observations SELECT * FROM observations")
        for name, df in (tables or {}).items():
            con.register(f"_tbl_{name}", df)
            con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM _tbl_{name}")
    finally:
        con.close()
    return path
