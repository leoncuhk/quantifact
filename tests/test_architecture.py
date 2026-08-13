"""The guarantees the architecture is supposed to provide.

Each test names one property from the README table. They are deliberately about
*properties*, not about implementation details: a rewrite that keeps these green
keeps the promise.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

from quantifact import (
    ANALYST,
    PM,
    AnalysisPlan,
    ColumnSpec,
    PlanCompiler,
    PlanError,
    Quantifact,
    ReferenceCodegen,
    SeriesSearch,
    UnsupportedQuestionError,
)
from quantifact.bench import edit_last_chart, values_hash
from quantifact.codegen.base import generate_all
from quantifact.contracts.layers import l1_schema, l2_invariants
from quantifact.harness.cache import ValueCache
from quantifact.harness.execute import ExecutionHarness, TaskExecutionError
from quantifact.learn.benchmarks import BenchmarkSuite
from quantifact.learn.lessons import LessonRepo
from quantifact.learn.teach import teach
from quantifact.planner import RulePlanner, _as_store
from quantifact.static_analysis.ast_checks import analyse
from quantifact.static_analysis.dag import cross_check, dependency_graph

from .conftest import AS_OF, QUESTION, toy_task

# ---------------------------------------------------------- plan compiler


def test_rejects_a_cycle():
    p = AnalysisPlan(
        "q",
        [toy_task(name="a", depends_on=["b"]), toy_task(name="b", depends_on=["a"])],
        as_of=AS_OF,
    )
    with pytest.raises(PlanError, match="cycle"):
        PlanCompiler().compile(p)


def test_rejects_unknown_dependency():
    problems = PlanCompiler().validate(
        AnalysisPlan("q", [toy_task(depends_on=["nope"])], as_of=AS_OF)
    )
    assert any("unknown task 'nope'" in x for x in problems)


def test_rejects_late_binding():
    t = toy_task(type="data_ingestion", depends_on=[])
    problems = PlanCompiler().validate(AnalysisPlan("q", [t], as_of=AS_OF))
    assert any("no series_inputs" in x for x in problems)


def test_rejects_a_plan_without_a_knowledge_date():
    problems = PlanCompiler().validate(AnalysisPlan("q", [toy_task()], as_of=""))
    assert any("no as_of" in x for x in problems)


def test_rejects_a_date_role_on_a_non_date_column():
    t = toy_task(
        columns=[ColumnSpec("d", "when", "float64", role="observation_date")], index=["d"]
    )
    problems = PlanCompiler().validate(AnalysisPlan("q", [t], as_of=AS_OF))
    assert any("date roles must be datetime64" in x for x in problems)


def test_rejects_a_column_nobody_produces():
    up = toy_task(
        name="u",
        depends_on=[],
        type="data_ingestion",
        series_inputs=["S"],
        columns=[ColumnSpec("x", "x")],
        index=["x"],
    )
    down = toy_task(
        name="d", depends_on=["u"], op={"kind": "union", "consumes": ["missing"]}
    )
    problems = PlanCompiler().validate(AnalysisPlan("q", [up, down], as_of=AS_OF))
    assert any("consumes column 'missing'" in x for x in problems)


def test_rejects_conflicting_units():
    a = toy_task(
        name="a", depends_on=["b"], columns=[ColumnSpec("v", "v", unit="%")], index=["v"]
    )
    b = toy_task(
        name="b",
        depends_on=[],
        type="data_ingestion",
        series_inputs=["S"],
        columns=[ColumnSpec("v", "v", unit="bp")],
        index=["v"],
    )
    problems = PlanCompiler().validate(AnalysisPlan("q", [a, b], as_of=AS_OF))
    assert any("conflicting units" in x for x in problems)


def test_the_real_plan_compiles(plan, qf):
    layers = PlanCompiler(
        known_series={m.series_id for m in qf.adapter.catalog()},
        known_tables=set(qf.adapter.tables()),
    ).compile(plan)
    assert len(plan.tasks) >= 14
    assert len(layers) >= 4
    # ingestion is all in the first layer: nothing to wait for
    assert all(plan[n].type == "data_ingestion" for n in layers[0])


def test_rule_planner_refuses_an_unsupported_research_family(qf):
    with pytest.raises(UnsupportedQuestionError, match="supports oil/energy"):
        qf.build_plan("Build a DCF valuation for a semiconductor company")


def test_rule_planner_does_not_offer_oil_clarifications_for_an_unrelated_question(qf):
    with pytest.raises(UnsupportedQuestionError):
        qf.clarify("Optimize my portfolio")


def test_cli_presents_an_unsupported_question_as_a_refusal(tmp_path, capsys):
    from quantifact.cli import main

    status = main(
        [
            "--workspace",
            str(tmp_path / "ws"),
            "plan",
            "Build a DCF valuation for a semiconductor company",
        ]
    )
    captured = capsys.readouterr()
    assert status == 2
    assert captured.out == ""
    assert captured.err.startswith("refused:")
    assert "supports oil/energy" in captured.err


# -------------------------------------------------------- static analysis


def test_blocks_io_and_nondeterminism():
    facts = analyse("t", "import os\ndef t():\n    open('x')\n    return 1\n")
    joined = " ".join(facts.violations)
    assert "not allowed" in joined and "forbidden call: open()" in joined


def test_blocks_inplace_mutation():
    src = "def t(u):\n    u.dropna(inplace=True)\n    return u\n"
    assert any("inplace" in v for v in analyse("t", src).violations)


def test_cache_identity_ignores_comments():
    a = analyse("t", "def t():\n    x = 1\n    return x\n")
    b = analyse("t", "def t():\n    # a comment\n\n    x = 1\n    return x\n")
    assert a.ast_digest == b.ast_digest


def test_undeclared_upstream_is_caught():
    facts = {"d": analyse("d", "def d(a, b):\n    return a\n")}
    problems = cross_check(dependency_graph(facts), {"d": ["a"]})
    assert any("undeclared upstream ['b']" in p for p in problems)


def test_generated_code_passes_static_analysis(plan, codes):
    for name, src in codes.items():
        facts = analyse(name, src)
        assert not facts.violations, (name, facts.violations)
        assert set(facts.params) == set(plan[name].depends_on)


# ---------------------------------------------------------------- harness


def test_cache_hit_and_selective_recompute(qf, plan, codes, tmp_path):
    h = ExecutionHarness(qf.adapter, ValueCache(tmp_path / "c"))
    cold = h.run(plan, codes)
    assert cold.cache_hits == 0
    warm = h.run(plan, codes)
    assert warm.cache_hits == len(plan.tasks)

    edited = edit_last_chart(plan)
    after = h.run(edited, generate_all(edited, ReferenceCodegen()))
    recomputed = [t.task for t in after.traces if not t.cached]
    assert recomputed == [edited.charts()[-1].name]


def test_execution_is_deterministic(qf, plan, tmp_path):
    a = ExecutionHarness(qf.adapter, ValueCache(tmp_path / "a", enabled=False))
    b = ExecutionHarness(qf.adapter, ValueCache(tmp_path / "b", enabled=False))
    ha = values_hash(a.run(plan, generate_all(plan, ReferenceCodegen())).frames)
    hb = values_hash(b.run(plan, generate_all(plan, ReferenceCodegen())).frames)
    assert ha == hb


def test_harness_blocks_filesystem_access(qf, tmp_path):
    t = toy_task(name="evil", depends_on=[])
    p = AnalysisPlan("q", [t], as_of=AS_OF)
    src = "def evil():\n    open('/etc/passwd')\n    return pd.DataFrame({'a': [1]})\n"
    h = ExecutionHarness(qf.adapter, ValueCache(tmp_path / "e"))
    with pytest.raises(TaskExecutionError):
        h.run(p, {"evil": src})


# ------------------------------------------------------------- contracts


def test_schema_validation_catches_wrong_columns():
    t = toy_task(columns=[ColumnSpec("a", "a"), ColumnSpec("b", "b")])
    v = l1_schema(t, pd.DataFrame({"a": [1.0]}))
    assert not v.ok and any("missing columns ['b']" in p for p in v.problems)


def test_declared_row_order_is_enforced():
    t = toy_task(columns=[ColumnSpec("a", "a")], index=["a"], sort=[["a", False]])
    v = l1_schema(t, pd.DataFrame({"a": [1.0, 2.0]}))
    assert not v.ok and "not ordered" in v.problems[0]


def test_invariants_catch_out_of_range():
    t = toy_task(invariants=[{"kind": "range", "column": "a", "min": 0, "max": 1}])
    v = l2_invariants(t, pd.DataFrame({"a": [0.5, 7.0]}))
    assert not v.ok and "outside" in v.problems[0]


# ------------------------------------------------------------- entitlements


def test_entitlements_are_enforced_in_the_index(qf):
    analyst = SeriesSearch(_as_store(qf.adapter), ANALYST.entitlements)
    pm = SeriesSearch(_as_store(qf.adapter), PM.entitlements)
    q = "aggregate book positioning"
    assert not [h for h in analyst.search(q) if "POSITIONS" in h.meta.series_id]
    assert [h for h in pm.search(q) if "POSITIONS" in h.meta.series_id]


# ------------------------------------------------------------------ search


def test_inspection_rejects_wrong_scale_and_frequency(qf):
    search = SeriesSearch(_as_store(qf.adapter), ())
    hits = search.search(
        "US headline CPI year over year", k=8, frequency="M", unit="%", prior=(-6.0, 20.0)
    )
    by_id = {h.meta.series_id: h for h in hits}
    assert by_id["US.CPI.HEADLINE.YOY"].accepted
    assert not by_id["US.CPI.HEADLINE.YOY.BPS"].accepted  # right unit, wrong scale
    assert "outside prior" in by_id["US.CPI.HEADLINE.YOY.BPS"].reasons[0]


def test_every_requirement_binds(qf):
    _, planner = qf.build_plan(QUESTION)
    assert planner.bindings and all(b.chosen for b in planner.bindings)


def test_catalog_cards_carry_what_binding_needs(qf):
    card = qf.adapter.store.meta("US.CPI.HEADLINE.YOY").card()
    for token in ("freq=M", "unit=%", "coverage=", "values[", "license="):
        assert token in card


# --------------------------------------------------------------- flywheel


def test_teach_requires_a_reproducible_failure_then_fixes_it(ws, qf):
    repo = LessonRepo(ws / "ctx-lessons")
    suite = BenchmarkSuite(ws / "benchmarks")
    complaint = (
        "When comparing multiple historical episodes, break the scatter out "
        "by asset class instead of pooling every market into one panel."
    )
    res = teach(complaint, QUESTION, adapter=qf.adapter, repo=repo, suite=suite)
    assert res.failed_before, "the benchmark must fail before the lesson exists"
    assert res.passes_after and not res.regressions and res.accepted

    p = RulePlanner(qf.adapter, lessons=repo.all()).plan(QUESTION)
    assert p.task("market_scatter_by_asset_class") is not None

    again = teach(
        complaint,
        QUESTION,
        adapter=qf.adapter,
        repo=repo,
        suite=suite,
        bench_id="teach-again",
    )
    assert not again.failed_before and not again.accepted


# ------------------------------------------------------------- end to end


def test_end_to_end_produces_a_report_and_writes_back(ws, tmp_path):
    qf = Quantifact(ws)
    art = qf.analyse(QUESTION, out=tmp_path / "r.html")
    assert art.report_path.exists() and "<svg" in art.report_path.read_text()
    assert all(v.ok for v in art.verdicts)
    assert not [f for f in art.findings if f.severity == "blocking"]
    assert art.written_series
    meta = qf.adapter.store.meta(art.written_series[0])
    assert meta.source == "quantifact-analysis" and meta.lineage
    receipt = art.receipt(backend="reference", user="analyst")
    assert receipt["schema_version"] == 1 and len(receipt["plan_sha256"]) == 64
    assert set(receipt["code_sha256"]) == set(art.plan.names)
    assert receipt["execution"] and receipt["verdicts"]
    assert receipt["planning_trace"]["planner"] == "RulePlanner"


def test_plan_round_trips_through_json(plan, tmp_path):
    p = tmp_path / "plan.json"
    plan.save(p)
    again = AnalysisPlan.load(p)
    assert json.dumps(again.to_dict(), sort_keys=True) == json.dumps(
        plan.to_dict(), sort_keys=True
    )
