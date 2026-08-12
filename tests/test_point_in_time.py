"""The look-ahead defence, tested at every layer that implements it.

If one of these fails, quantifact's central claim is false, so they are the
tests to read first.
"""

from __future__ import annotations

import pandas as pd
import pytest

from quantifact import AnalysisPlan, ColumnSpec, Quantifact, Task
from quantifact.contracts.layers import validate_result
from quantifact.contracts.pointintime import LookAheadError, no_future_observations
from quantifact.harness.cache import ValueCache, cache_key
from quantifact.harness.execute import ExecutionHarness
from quantifact.staticanalysis.ast_checks import analyse

from .conftest import QUESTION, toy_task

# --------------------------------------------------------------- the store

def test_store_hides_observations_published_after_as_of(qf):
    """A monthly indicator with a 45-day lag is not knowable the day it ends."""
    full = qf.adapter.read_series("US.OUTPUT_GAP", as_of="2026-08-01")
    early = qf.adapter.read_series("US.OUTPUT_GAP", as_of="2026-06-14")
    assert full.index.max() > early.index.max()
    assert early.index.max() <= pd.Timestamp("2026-06-14")
    # and the cut is the publication date, not the observation date
    frame = qf.adapter.store.read_frame("US.OUTPUT_GAP")
    visible = frame[frame["pub_date"] <= pd.Timestamp("2026-06-14")]
    assert len(early) == len(visible)


def test_daily_series_are_cut_at_the_knowledge_date(qf):
    s = qf.adapter.read_series("MKT.BRENT.CO.TRI", as_of="2022-03-01")
    assert s.index.max() <= pd.Timestamp("2022-03-01")


# -------------------------------------------------------------- the loader

def test_generated_code_cannot_choose_its_own_as_of():
    src = ("def t():\n"
           "    s = load_series('X', as_of='2026-08-01')\n"
           "    return pd.DataFrame({'a': [1.0]})\n")
    facts = analyse("t", src)
    assert any("takes no keyword arguments" in v for v in facts.violations)


def test_harness_binds_the_loader_to_the_plan(qf, tmp_path):
    """Two identical plans differing only in as_of see different data."""
    task = Task(name="brent", type="data_ingestion", description="brent",
                series_inputs=["MKT.BRENT.CO.TRI"],
                columns=[ColumnSpec("date", "obs date", "datetime64[ns]",
                                    role="observation_date"),
                         ColumnSpec("price", "level", "float64", "index")],
                index=["date"], row_expectation="one row per day")
    src = ("def brent() -> pd.DataFrame:\n"
           "    s = load_series('MKT.BRENT.CO.TRI')\n"
           "    return pd.DataFrame({'date': s.index, 'price': s.to_numpy()})\n")
    harness = ExecutionHarness(qf.adapter, ValueCache(tmp_path / "c", enabled=False))
    early = harness.run(AnalysisPlan("q", [task], as_of="2022-03-01"), {"brent": src})
    late = harness.run(AnalysisPlan("q", [task], as_of="2026-08-01"), {"brent": src})
    assert len(early.frames["brent"]) < len(late.frames["brent"])
    assert early.frames["brent"]["date"].max() <= pd.Timestamp("2022-03-01")


# ------------------------------------------------------------- the contract

def test_dated_columns_may_not_post_date_the_knowledge_date():
    task = toy_task(columns=[ColumnSpec("date", "obs", "datetime64[ns]",
                                        role="observation_date")], index=["date"])
    df = pd.DataFrame({"date": pd.to_datetime(["2026-01-31", "2026-12-31"])})
    v = no_future_observations(task, df, "2026-08-01")
    assert not v.ok and "look-ahead" in v.problems[0]


def test_contract_catches_synthesised_future_dates():
    """Code that *invents* dates rather than reading them is still caught."""
    task = toy_task(columns=[ColumnSpec("date", "obs", "datetime64[ns]",
                                        role="observation_date")],
                    index=["date"], invariants=[{"kind": "no_future_observations"}])
    df = pd.DataFrame({"date": pd.date_range("2026-01-31", periods=24, freq="ME")})
    verdicts = validate_result(task, df, "2026-08-01")
    assert any(not v.ok for v in verdicts)


# ---------------------------------------------------------------- the cache

def test_cache_key_changes_with_the_knowledge_date(plan, codes, qf):
    task = plan["market_prices"]
    facts = analyse(task.name, codes[task.name])
    a = cache_key(task, facts, {},
                  qf.adapter.fingerprint(task.series_inputs, as_of="2026-08-01"),
                  "2026-08-01")
    b = cache_key(task, facts, {},
                  qf.adapter.fingerprint(task.series_inputs, as_of="2026-06-14"),
                  "2026-06-14")
    assert a != b, "the same code at a different as_of is a different question"


# --------------------------------------------------------------- the planner

def test_planner_refuses_an_episode_that_had_not_happened(qf):
    with pytest.raises(LookAheadError, match="look-ahead"):
        qf.build_plan(QUESTION, {"as_of": "2026-06-14",
                                 "episodes": ["gulf_war_1990", "iran_hormuz_2026"]})


def test_episode_set_follows_the_knowledge_date(qf):
    early, _ = qf.build_plan(QUESTION, {"as_of": "2026-06-14"})
    late, _ = qf.build_plan(QUESTION, {"as_of": "2026-08-01"})
    early_eps = [a for a in early.resolved_assumptions if a.startswith("Episodes")][0]
    late_eps = [a for a in late.resolved_assumptions if a.startswith("Episodes")][0]
    assert "iran_hormuz_2026" not in early_eps
    assert "iran_hormuz_2026" in late_eps


def test_universe_is_survivorship_free(qf):
    """A name delisted in 2008 belongs to a 2007 universe and not a 2026 one."""
    old = qf.adapter.read_table("markets", as_of="2007-01-01")["market_id"].tolist()
    new = qf.adapter.read_table("markets", as_of="2026-08-01")["market_id"].tolist()
    assert "LEHM.EQ" in old and "LEHM.EQ" not in new
    assert "NEWCO.EQ" in new and "NEWCO.EQ" not in old


def test_analysis_at_an_earlier_as_of_runs_end_to_end(ws, tmp_path):
    qf = Quantifact(ws)      # reuses the session store
    art = qf.analyse(QUESTION, {"as_of": "2025-12-31"}, out=tmp_path / "r.html")
    assert art.plan.as_of == "2025-12-31"
    for frame in art.result.frames.values():
        for col in frame.columns:
            if pd.api.types.is_datetime64_any_dtype(frame[col]):
                assert frame[col].max() <= pd.Timestamp("2025-12-31")
