"""Point-in-time, demonstrated three ways.

    uv run python examples/04_point_in_time/run.py

Look-ahead is the failure mode that makes historical research worthless, and
it is silent: the numbers look fine, the code looks fine, and the backtest is a
fantasy. quantifact stops it in three places, and this script shows each one
failing loudly on purpose.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pandas as pd

from quantifact import ColumnSpec, Quantifact, Task
from quantifact.contracts.layers import validate_result
from quantifact.contracts.pointintime import LookAheadError
from quantifact.staticanalysis.ast_checks import analyse

QUESTION = (
    "How have markets responded to the conflict in the Middle East and the "
    "resulting oil supply shortage?"
)


def rule(title: str) -> None:
    print(f"\n\033[1m{title}\033[0m\n" + "─" * 72)


def main() -> int:
    ws = Path(tempfile.mkdtemp(prefix="qf-pit-"))
    qf = Quantifact(ws)

    rule("1. The loader is bound to the knowledge date")
    for as_of in ("2022-03-01", "2026-08-01"):
        s = qf.adapter.read_series("MKT.BRENT.CO.TRI", as_of=as_of)
        print(f"  as_of {as_of}: {len(s):>5} observations, latest {s.index.max().date()}")
    print(
        "  Generated code never sees the rows beyond its knowledge date;"
        "\n  they are not filtered later, they are never handed over."
    )

    rule("2. Code cannot choose its own knowledge date")
    sneaky = (
        "def sneaky():\n"
        "    s = load_series('MKT.BRENT.CO.TRI', as_of='2026-08-01')\n"
        "    return pd.DataFrame({'a': [1.0]})\n"
    )
    for v in analyse("sneaky", sneaky).violations:
        print(f"  L0-static rejects: {v}")

    rule("3. Dated results are checked against the knowledge date")
    task = Task(
        name="invented",
        type="table_logic",
        description="synthesised dates",
        depends_on=["upstream"],
        columns=[
            ColumnSpec(
                "date", "observation date", "datetime64[ns]", role="observation_date"
            ),
            ColumnSpec("value", "a number", "float64"),
        ],
        index=["date"],
        row_expectation="one row per month",
        invariants=[{"kind": "no_future_observations"}],
    )
    df = pd.DataFrame(
        {"date": pd.date_range("2026-01-31", periods=12, freq="ME"), "value": range(12)}
    ).astype({"value": "float64"})
    for v in validate_result(task, df, "2026-08-01"):
        if not v.ok:
            print(f"  {v}")

    rule("4. Asking for an event that had not happened is refused")
    try:
        qf.build_plan(
            QUESTION,
            {"as_of": "2026-06-14", "episodes": ["gulf_war_1990", "iran_hormuz_2026"]},
        )
    except LookAheadError as e:
        print(f"  planner refuses: {e}")

    rule("5. The same question, two knowledge dates, two honest answers")
    for as_of in ("2026-06-14", "2026-08-01"):
        art = qf.analyse(QUESTION, {"as_of": as_of}, out=ws / f"report-{as_of}.html")
        episodes = art.result.frames["spine_episodes"]["episode"].tolist()
        rows = len(art.result.frames["market_episode_returns"])
        print(
            f"  as_of {as_of}: {len(art.plan.tasks)} tasks, "
            f"{len(episodes)} episodes {episodes}, {rows} return cells"
        )
        print(f"                 report → {art.report_path}")

    rule("6. And the cache knows they are different questions")
    a = qf.analyse(QUESTION, {"as_of": "2026-06-14"}, writeback=False)
    b = qf.analyse(QUESTION, {"as_of": "2026-08-01"}, writeback=False)
    ka = a.result.trace("market_prices").cache_key
    kb = b.result.trace("market_prices").cache_key
    print(f"  market_prices cache key @2026-06-14: {ka}")
    print(f"  market_prices cache key @2026-08-01: {kb}")
    print(f"  same key? {ka == kb}")

    print(f"\nworkspace: {ws}")
    if input("\ndelete the workspace? [Y/n] ").strip().lower() in ("", "y"):
        shutil.rmtree(ws)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
