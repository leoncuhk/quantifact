"""Series registry and store — bitemporal by construction.

Every observation carries two dates:

``obs_date``   what the number describes (the index)
``pub_date``   when the number first became knowable

A read is always taken *as of* a knowledge date and silently drops anything
whose ``pub_date`` is later. That is the whole look-ahead defence, and it lives
in the store rather than in a convention, because a convention is something a
generated function can forget.

Metadata is a first-class product, not decoration. ``value_stats`` exists so a
search agent can ask "do these numbers match my prior for this concept" — the
check that separates a CPI *index* from a CPI *rate* when both match the query
text. ``license_tag`` exists so provenance travels with derived outputs.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from ..plan.model import parse_date

Frequency = Literal["D", "W", "M", "Q", "A"]


@dataclass
class SeriesMeta:
    """Catalog entry for one series. Also the agent's search unit."""

    series_id: str
    name: str
    description: str
    frequency: Frequency
    unit: str
    source: str  # vendor | internal-model | quantifact-analysis
    entitlement_tags: list[str] = field(default_factory=list)
    license_tag: str = "unspecified"  # travels with every derived output
    aliases: list[str] = field(default_factory=list)
    currency: str | None = None
    geography: str | None = None
    asset_class: str | None = None
    owner: str = "unknown"
    lineage: list[str] = field(default_factory=list)
    pub_lag_days: int = 0  # typical publication lag, for documentation
    first_obs: str | None = None
    last_obs: str | None = None
    last_pub: str | None = None
    n_obs: int = 0
    value_stats: dict[str, float] = field(default_factory=dict)
    content_hash: str = ""
    invariants: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict[str, Any]) -> SeriesMeta:
        return SeriesMeta(**d)

    def card(self) -> str:
        """A token-budgeted catalog card: what an agent reads before binding.

        Deliberately short. The full schema is one hop away; what a planner
        needs to *choose* is identity, unit, grain, coverage and plausibility.
        """
        stats = self.value_stats
        rng = (
            f"{stats['min']:.4g}..{stats['max']:.4g}"
            if {"min", "max"} <= stats.keys()
            else "n/a"
        )
        bits = [
            f"{self.series_id} — {self.name}",
            f"  {self.description}",
            f"  freq={self.frequency} unit={self.unit}"
            + (f" ccy={self.currency}" if self.currency else "")
            + (f" geo={self.geography}" if self.geography else ""),
            f"  coverage={self.first_obs}..{self.last_obs} n={self.n_obs} "
            f"values[{rng}] pub_lag~{self.pub_lag_days}d",
            f"  source={self.source} license={self.license_tag}",
        ]
        if self.aliases:
            bits.append(f"  aka: {', '.join(self.aliases[:6])}")
        return "\n".join(bits)


def _content_hash(df: pd.DataFrame) -> str:
    h = hashlib.sha256()
    h.update(df.index.astype("datetime64[ns]").astype("int64").to_numpy().tobytes())
    h.update(df["value"].to_numpy(dtype="float64").tobytes())
    h.update(df["pub_date"].astype("datetime64[ns]").astype("int64").to_numpy().tobytes())
    return h.hexdigest()[:16]


def _stats(s: pd.Series) -> dict[str, float]:
    v = s.dropna()
    if v.empty:
        return {}
    return {
        "mean": float(v.mean()),
        "std": float(v.std() or 0.0),
        "min": float(v.min()),
        "max": float(v.max()),
        "last": float(v.iloc[-1]),
    }


class SeriesStore:
    """Parquet-backed bitemporal store: one file per series plus a JSON index."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.data_dir = self.root / "series"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "catalog.json"
        self._meta: dict[str, SeriesMeta] = {}
        if self.index_path.exists():
            raw = json.loads(self.index_path.read_text())
            self._meta = {k: SeriesMeta.from_dict(v) for k, v in raw.items()}

    # ------------------------------------------------------------------ io
    def _path(self, series_id: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", series_id)
        return self.data_dir / f"{safe}.parquet"

    def flush(self) -> None:
        self.index_path.write_text(
            json.dumps(
                {k: v.to_dict() for k, v in self._meta.items()},
                indent=1,
                ensure_ascii=False,
            )
        )

    def write(
        self, meta: SeriesMeta, values: pd.Series, pub_dates: pd.Series | None = None
    ) -> SeriesMeta:
        """Write a series. ``pub_dates`` defaults to obs_date + pub_lag_days."""
        values = values.sort_index()
        values.index = pd.to_datetime(values.index)
        if pub_dates is None:
            pub = pd.Series(values.index, index=values.index) + pd.Timedelta(
                days=meta.pub_lag_days
            )
        else:
            pub = pd.Series(pd.to_datetime(pub_dates.to_numpy()), index=values.index)
        df = pd.DataFrame(
            {"value": values.astype("float64").to_numpy(), "pub_date": pub.to_numpy()},
            index=values.index,
        )
        df.index.name = "obs_date"

        meta.n_obs = int(df["value"].notna().sum())
        meta.first_obs = str(df.index.min().date()) if len(df) else None
        meta.last_obs = str(df.index.max().date()) if len(df) else None
        meta.last_pub = (
            str(pd.Timestamp(df["pub_date"].max()).date()) if len(df) else None
        )
        meta.value_stats = _stats(df["value"])
        meta.content_hash = _content_hash(df)
        df.to_parquet(self._path(meta.series_id))
        self._meta[meta.series_id] = meta
        self.flush()
        return meta

    def read_frame(self, series_id: str) -> pd.DataFrame:
        if series_id not in self._meta:
            raise KeyError(f"unknown series_id: {series_id}")
        return pd.read_parquet(self._path(series_id))

    def read(self, series_id: str, *, as_of: str | date) -> pd.Series:
        """Observations knowable on ``as_of``. Never returns the future."""
        cut = pd.Timestamp(parse_date(as_of))
        df = self.read_frame(series_id)
        visible = df[df["pub_date"] <= cut]
        s = visible["value"]
        s.name = series_id
        return s

    # -------------------------------------------------------------- catalog
    def meta(self, series_id: str) -> SeriesMeta:
        return self._meta[series_id]

    @property
    def ids(self) -> list[str]:
        return sorted(self._meta)

    def all_meta(self) -> list[SeriesMeta]:
        return [self._meta[i] for i in self.ids]

    def fingerprint(self, series_ids: Iterable[str], *, as_of: str | date) -> str:
        """Identity of the *visible slice*: content plus knowledge date.

        Two runs with the same code but different ``as_of`` must not share a
        cache entry, because they are answering different questions.
        """
        h = hashlib.sha256()
        h.update(str(parse_date(as_of)).encode())
        for sid in sorted(series_ids):
            h.update(sid.encode())
            h.update(self._meta[sid].content_hash.encode())
        return h.hexdigest()[:16]
