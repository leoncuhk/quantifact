"""A synthetic demo adapter — zero credentials, zero licence questions.

The shape is deliberately the shape of a real equity/macro stack: a
survivorship-free universe with listing and delisting dates, a trading
calendar, an event spine, daily total-return series and monthly macro series
with realistic publication lags. It also ships four traps that a careless
search would fall into:

It also ships a small research corpus (``demo_corpus``) so the unstructured
side of the knowledge date can be exercised: a fifth of the notes are written
after the 2026 escalation and must not appear in an earlier search.

  US.CPI.HEADLINE.INDEX      an index where a rate was asked for
  US.CPI.HEADLINE.YOY.BPS    the right unit label, the wrong scale
  US.OUTPUT_GAP.Q            the right concept, the wrong frequency
  MKT.DELISTED.EQ            a name that exists today but not on an older as_of

Nothing here is market data. It exists so the whole pipeline — including the
look-ahead defence — can be exercised and benchmarked by anyone, offline.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ...plan.model import parse_date
from ..documents import DocumentHit
from ..registry import SeriesMeta, SeriesStore
from .demo_corpus import ensure_corpus

# (episode key, label, start date, shock size)
EPISODES = [
    ("gulf_war_1990", "1990 Gulf War", "1990-08-02", 0.65),
    ("russia_ukraine_2022", "2022 Russia-Ukraine", "2022-02-24", 0.42),
    ("israel_iran_2025", "2025 Israel-Iran 12-Day War", "2025-06-13", 0.18),
    ("iran_hormuz_2026", "2026 Iran/Hormuz", "2026-06-15", 0.33),
]

# asset class -> (names, oil beta, annual drift, annual vol)
UNIVERSE_SPEC: dict[str, tuple[list[str], float, float, float]] = {
    "equity": (
        [
            "SPX",
            "NDX",
            "SX5E",
            "DAX",
            "UKX",
            "NKY",
            "HSI",
            "KOSPI",
            "TSX",
            "ASX",
            "IBOV",
            "SENSEX",
        ],
        -0.55,
        0.07,
        0.16,
    ),
    "bond": (
        [
            "UST2Y",
            "UST10Y",
            "UST30Y",
            "BUND10Y",
            "JGB10Y",
            "GILT10Y",
            "OAT10Y",
            "BTP10Y",
            "AUS10Y",
            "CAN10Y",
        ],
        -0.18,
        0.03,
        0.06,
    ),
    "fx": (
        [
            "EURUSD",
            "USDJPY",
            "GBPUSD",
            "AUDUSD",
            "USDCAD",
            "USDCHF",
            "USDNOK",
            "USDMXN",
            "USDBRL",
            "USDINR",
            "USDKRW",
            "USDZAR",
        ],
        0.12,
        0.0,
        0.09,
    ),
    "commodity": (
        [
            "BRENT",
            "WTI",
            "NATGAS",
            "GOLD",
            "SILVER",
            "COPPER",
            "ALUM",
            "CORN",
            "WHEAT",
            "SOY",
            "COTTON",
        ],
        0.85,
        0.02,
        0.24,
    ),
    "credit": (["USIG", "USHY", "EURIG", "EURHY", "EMSOV"], -0.25, 0.04, 0.08),
    "inflation": (["US10YTIPS", "US5Y5YBE", "UKILB", "EURILB", "JPBE"], 0.35, 0.02, 0.05),
}

# label, unit, plausible range, noise, oil beta, publication lag (days)
MACRO_SPEC: dict[str, tuple[str, str, tuple[float, float], float, float, int]] = {
    "US.REAL_YIELD.10Y": ("US 10y real yield", "%", (-1.5, 5.0), 0.35, -0.6, 1),
    "US.OUTPUT_GAP": ("US output gap", "% of potential", (-6.0, 4.0), 0.5, -1.1, 45),
    "US.CPI.HEADLINE.YOY": (
        "US headline CPI, year over year",
        "%",
        (0.5, 6.0),
        0.4,
        1.8,
        14,
    ),
    "US.CPI.CORE.YOY": ("US core CPI, year over year", "%", (1.0, 4.5), 0.25, 0.7, 14),
    "US.NET_ENERGY_TRADE": (
        "US net energy trade balance",
        "% of GDP",
        (-2.5, 1.5),
        0.2,
        -0.5,
        60,
    ),
}

DELISTED = ("LEHM", "equity", "2008-09-15")  # in the universe before it died
LISTED_LATE = ("NEWCO", "equity", "2021-03-01")

PRICE_INVARIANTS = [
    {"kind": "nonnull", "column": "value", "min": 0.999},
    {"kind": "range", "column": "value", "min": 0.0, "max": 1e9},
]
RATE_INVARIANTS = [
    {"kind": "nonnull", "column": "value", "min": 0.99},
    {"kind": "range", "column": "value", "min": -25.0, "max": 25.0},
]


def _market_id(name: str, asset_class: str) -> str:
    return f"{name}.{asset_class[:2].upper()}"


def universe() -> pd.DataFrame:
    """Survivorship-free universe: every name that ever existed, with dates."""
    rows: list[dict[str, Any]] = []
    for asset_class, (names, beta, drift, vol) in UNIVERSE_SPEC.items():
        for i, n in enumerate(names):
            rows.append(
                {
                    "market_id": _market_id(n, asset_class),
                    "asset_class": asset_class,
                    "beta_oil": beta * (0.7 + 0.6 * ((i % 5) / 4)),
                    "drift": drift,
                    "vol": vol,
                    "listed_from": pd.Timestamp("1988-01-01"),
                    "delisted_on": pd.NaT,
                }
            )
    name, ac, died = DELISTED
    rows.append(
        {
            "market_id": _market_id(name, ac),
            "asset_class": ac,
            "beta_oil": -0.4,
            "drift": 0.05,
            "vol": 0.28,
            "listed_from": pd.Timestamp("1988-01-01"),
            "delisted_on": pd.Timestamp(died),
        }
    )
    name, ac, born = LISTED_LATE
    rows.append(
        {
            "market_id": _market_id(name, ac),
            "asset_class": ac,
            "beta_oil": -0.6,
            "drift": 0.09,
            "vol": 0.22,
            "listed_from": pd.Timestamp(born),
            "delisted_on": pd.NaT,
        }
    )
    return pd.DataFrame(rows).sort_values("market_id").reset_index(drop=True)


def episodes_table() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"episode": e, "label": lab, "start_date": pd.Timestamp(d), "oil_shock": s}
            for e, lab, d, s in EPISODES
        ]
    )


def trading_calendar(start: str = "1988-01-01", end: str = "2026-12-31") -> pd.DataFrame:
    days = pd.bdate_range(start, end)
    return pd.DataFrame({"trade_date": days, "market": "GLOBAL"})


def _shock_path(
    dates: pd.DatetimeIndex, beta: float, rng: np.random.Generator
) -> np.ndarray:
    impact = np.zeros(len(dates))
    day = dates.to_numpy(dtype="datetime64[D]").astype("int64")
    for _, _, start, size in EPISODES:
        t0 = np.datetime64(start, "D").astype("int64")
        dt = day - t0
        ramp = np.clip(dt / 15.0, 0.0, 1.0) * (dt >= 0)
        decay = np.exp(-np.clip(dt - 15, 0, None) / 90.0)
        idio = 1.0 + 0.25 * rng.standard_normal()
        impact += beta * size * idio * ramp * decay * 0.35
    return impact


def build_store(root: str | Path, seed: int = 42) -> SeriesStore:
    """(Re)build the demo store. Deterministic for a given seed."""
    store = SeriesStore(root)
    rng = np.random.default_rng(seed)
    uni = universe()

    days = pd.bdate_range("1988-01-01", "2026-08-01")
    for row in uni.itertuples(index=False):
        window = days[
            (days >= row.listed_from)
            & (pd.isna(row.delisted_on) | (days <= row.delisted_on))
        ]
        n = len(window)
        noise = rng.standard_normal(n) * row.vol / np.sqrt(252)
        trend = np.full(n, row.drift / 252)
        path = np.cumsum(trend + noise) + _shock_path(window, row.beta_oil, rng)
        store.write(
            SeriesMeta(
                series_id=f"MKT.{row.market_id}.TRI",
                name=f"{row.market_id} total return index",
                description=(
                    f"Daily total return index for {row.market_id} "
                    f"({row.asset_class}), rebased to 100 at listing"
                ),
                frequency="D",
                unit="index",
                source="vendor",
                license_tag="demo-synthetic",
                asset_class=row.asset_class,
                geography="global",
                owner="market-data",
                pub_lag_days=0,
                aliases=[row.market_id, row.market_id.split(".")[0]],
                invariants=PRICE_INVARIANTS,
            ),
            pd.Series(100.0 * np.exp(path), index=window),
        )

    months = pd.date_range("1985-01-31", "2026-07-31", freq="ME")
    m = len(months)
    for sid, (name, unit, (lo, hi), noise, beta, lag) in MACRO_SPEC.items():
        base = np.linspace(lo + (hi - lo) * 0.35, lo + (hi - lo) * 0.6, m)
        wiggle = np.cumsum(rng.standard_normal(m) * noise) * 0.25
        impact = _shock_path(months, beta, rng) * 3.0
        store.write(
            SeriesMeta(
                series_id=sid,
                name=name,
                description=f"{name}, monthly, internally modelled; published ~{lag}d "
                "after the reference month",
                frequency="M",
                unit=unit,
                currency="USD",
                geography="US",
                source="internal-model",
                license_tag="demo-synthetic",
                owner="us-macro-team",
                pub_lag_days=lag,
                aliases=[sid.split(".")[-1].lower(), name.lower()],
                invariants=RATE_INVARIANTS,
            ),
            pd.Series(np.clip(base + wiggle + impact, lo, hi), index=months),
        )

    # --- traps ------------------------------------------------------------
    idx = 100 * np.exp(np.cumsum(np.full(m, 0.0025) + rng.standard_normal(m) * 0.001))
    store.write(
        SeriesMeta(
            series_id="US.CPI.HEADLINE.INDEX",
            name="US headline CPI index",
            description="US headline consumer price index, level (1982-84 = 100)",
            frequency="M",
            unit="index",
            currency="USD",
            geography="US",
            source="vendor",
            license_tag="demo-synthetic",
            owner="market-data",
            pub_lag_days=14,
            aliases=["cpi", "headline cpi"],
        ),
        pd.Series(idx, index=months),
    )

    store.write(
        SeriesMeta(
            series_id="US.CPI.HEADLINE.YOY.BPS",
            name="US headline CPI year over year, basis points",
            description="US headline consumer prices, year over year, in basis points",
            frequency="M",
            unit="%",
            currency="USD",
            geography="US",
            source="vendor",
            license_tag="demo-synthetic",
            owner="market-data",
            pub_lag_days=14,
            aliases=["cpi yoy bps"],
        ),
        pd.Series(
            np.clip(np.linspace(120, 480, m) + rng.standard_normal(m) * 40, 0, 1500),
            index=months,
        ),
    )

    quarters = pd.date_range("1985-03-31", "2026-06-30", freq="QE")
    q = len(quarters)
    store.write(
        SeriesMeta(
            series_id="US.OUTPUT_GAP.Q",
            name="US output gap, quarterly vintage",
            description="US output gap, quarterly frequency, vintage series",
            frequency="Q",
            unit="% of potential",
            currency="USD",
            geography="US",
            source="vendor",
            license_tag="demo-synthetic",
            owner="market-data",
            pub_lag_days=75,
            aliases=["output gap quarterly"],
        ),
        pd.Series(
            np.linspace(-1.0, 1.5, q) + rng.standard_normal(q) * 0.4, index=quarters
        ),
    )

    # --- entitlement-gated ------------------------------------------------
    store.write(
        SeriesMeta(
            series_id="BW.POSITIONS.AGGREGATE",
            name="Aggregate book positioning",
            description="Aggregate positioning across all markets, firm confidential",
            frequency="D",
            unit="notional",
            currency="USD",
            source="internal-model",
            license_tag="internal-confidential",
            owner="portfolio-construction",
            entitlement_tags=["secure:positions"],
            pub_lag_days=0,
        ),
        pd.Series(rng.standard_normal(len(days)).cumsum() * 1e6, index=days),
    )

    return store


class DemoSyntheticAdapter:
    """Adapter over the synthetic store. The default in every example."""

    name = "demo-synthetic"

    def __init__(self, root: str | Path, seed: int = 42):
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True)
        # CLI commands may start concurrently against the same workspace. A
        # build lock prevents one command from reading a partially populated
        # catalog while another is still writing the demo Parquet files.
        lock_path = root / ".build.lock"
        with lock_path.open("a+") as lock:
            try:
                import fcntl

                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            except ImportError:  # pragma: no cover - Windows is best effort
                pass
            existing = SeriesStore(root) if (root / "catalog.json").exists() else None
            complete = existing is not None and all(
                existing._path(series_id).exists() for series_id in existing.ids
            )
            self.store = existing if complete else build_store(root, seed)
            try:
                import fcntl

                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
            except ImportError:  # pragma: no cover
                pass
        self._universe = universe()[
            ["market_id", "asset_class", "listed_from", "delisted_on"]
        ]
        self._tables = {
            "markets": self._universe,
            "episodes": episodes_table(),
            "calendar": trading_calendar(),
        }
        self.documents = ensure_corpus(root)

    # ------------------------------------------------------------- protocol
    def catalog(self) -> list[SeriesMeta]:
        return self.store.all_meta()

    def read_series(self, series_id: str, *, as_of: str | date) -> pd.Series:
        return self.store.read(series_id, as_of=as_of)

    def tables(self) -> list[str]:
        return sorted(self._tables)

    def read_table(self, name: str, *, as_of: str | date) -> pd.DataFrame:
        """Reference tables are as-of aware too.

        ``markets`` keeps names that were listed on the knowledge date and were
        not yet delisted — including ones that have since died, which is what
        makes the universe survivorship-free. ``episodes`` only contains events
        that had already begun.
        """
        cut = pd.Timestamp(parse_date(as_of))
        df = self._tables[name].copy()
        if name == "markets":
            alive = (df["listed_from"] <= cut) & (
                df["delisted_on"].isna() | (df["delisted_on"] >= cut)
            )
            df = df.loc[alive, ["market_id", "asset_class", "listed_from"]]
        elif name == "episodes":
            df = df[df["start_date"] <= cut]
        elif name == "calendar":
            df = df[df["trade_date"] <= cut]
        return df.reset_index(drop=True)

    def invariants(self, series_id: str) -> list[dict[str, Any]]:
        return list(self.store.meta(series_id).invariants)

    def fingerprint(self, series_ids: Iterable[str], *, as_of: str | date) -> str:
        return self.store.fingerprint(series_ids, as_of=as_of)

    # ------------------------------------------------------ document source
    def search_documents(
        self,
        query: str,
        *,
        as_of: str | date,
        k: int = 6,
        entitlements: Iterable[str] = (),
    ) -> list[DocumentHit]:
        return self.documents.search(query, as_of=as_of, k=k, entitlements=entitlements)

    def read_document(self, doc_id: str):
        return self.documents.get(doc_id)
