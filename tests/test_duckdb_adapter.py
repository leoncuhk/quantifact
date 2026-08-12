"""The DuckDB path, exercised against a file exported from the demo store.

Running the same plan through a second adapter is the real test of the
protocol: if the abstraction is right, nothing else in the system changes.
"""

from __future__ import annotations

import pytest

pytest.importorskip("duckdb")

from quantifact import Quantifact
from quantifact.data.adapters.demo_synthetic import (
    episodes_table,
    trading_calendar,
    universe,
)
from quantifact.data.adapters.duckdb_local import (
    DuckDBAdapter,
    export_store,
)

from .conftest import QUESTION


@pytest.fixture(scope="module")
def duck(qf, tmp_path_factory):
    path = tmp_path_factory.mktemp("duck") / "hub.duckdb"
    export_store(
        qf.adapter.store,
        path,
        tables={
            "markets": universe(),
            "episodes": episodes_table(),
            "calendar": trading_calendar(),
        },
    )
    return DuckDBAdapter(
        path,
        tables={"markets": "markets", "episodes": "episodes", "calendar": "calendar"},
    )


def test_catalog_survives_the_round_trip(qf, duck):
    assert {m.series_id for m in qf.adapter.catalog()} == {
        m.series_id for m in duck.catalog()
    }
    meta = next(m for m in duck.catalog() if m.series_id == "US.CPI.HEADLINE.YOY")
    assert meta.unit == "%" and meta.pub_lag_days == 14 and meta.invariants


def test_reads_are_point_in_time(duck):
    early = duck.read_series("US.OUTPUT_GAP", as_of="2026-06-14")
    late = duck.read_series("US.OUTPUT_GAP", as_of="2026-08-01")
    assert len(early) < len(late)


def test_universe_is_survivorship_free(duck):
    old = duck.read_table("markets", as_of="2007-01-01")["market_id"].tolist()
    new = duck.read_table("markets", as_of="2026-08-01")["market_id"].tolist()
    assert "LEHM.EQ" in old and "LEHM.EQ" not in new


def test_the_same_plan_runs_on_the_duckdb_adapter(duck, tmp_path):
    qf = Quantifact(tmp_path / "ws", adapter=duck)
    art = qf.analyse(QUESTION, out=tmp_path / "r.html", writeback=False)
    assert all(v.ok for v in art.verdicts)
    assert art.report_path.exists()
