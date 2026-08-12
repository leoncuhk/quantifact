"""Build a DuckDB hub in the layout quantifact expects, then read it back.

    uv run --extra duckdb python examples/02_bring_your_own_data/build_hub.py

The point is the *shape*, not the contents: two tables, one of them bitemporal.
Any in-house hub that can produce these two tables can be served to quantifact
without changing anything else.
"""

from __future__ import annotations

from pathlib import Path

from quantifact import Quantifact
from quantifact.data.adapters.demo_synthetic import (
    episodes_table,
    trading_calendar,
    universe,
)
from quantifact.data.adapters.duckdb_local import DuckDBAdapter, export_store

WS = Path(".qf-byod")


def main() -> int:
    seed = Quantifact(WS)  # the synthetic store, used only as a source
    path = export_store(
        seed.adapter.store,
        WS / "hub.duckdb",
        tables={
            "markets": universe(),
            "episodes": episodes_table(),
            "calendar": trading_calendar(),
        },
    )
    print(f"wrote {path}")
    print("  series_catalog        — one row per series, the agent's search index")
    print("  series_observations   — series_id, obs_date, pub_date, value")

    adapter = DuckDBAdapter(
        path,
        tables={"markets": "markets", "episodes": "episodes", "calendar": "calendar"},
    )
    qf = Quantifact(WS / "run", adapter=adapter)
    art = qf.analyse(
        "How did markets respond to the oil supply shock?",
        out=WS / "report.html",
        writeback=False,
    )
    print(
        f"\nsame plan, different adapter: {len(art.plan.tasks)} tasks, "
        f"{sum(1 for v in art.verdicts if v.ok)}/{len(art.verdicts)} verdicts passed"
    )
    print(f"report: {art.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
