"""Evaluation reports expose coverage and silent failure, not one vanity score."""

from __future__ import annotations

from quantifact.learn.benchmarks import Benchmark, BenchmarkReport, BenchmarkResult


def test_repository_benchmarks_include_success_and_refusal_cases(qf):
    from pathlib import Path

    from quantifact.learn.benchmarks import BenchmarkSuite

    root = Path(__file__).resolve().parents[1] / "benchmarks"
    suites = [BenchmarkSuite(root / name) for name in ("plan", "contract", "refusal")]
    results = [r for suite in suites for r in suite.run_all(qf.adapter, [])]
    report = BenchmarkReport(results)
    assert report.total == 4 and report.passed == 4
    assert report.silent_critical_failures == 0
    assert report.slices("family")["equity_fundamental"] == {"passed": 1, "total": 1}
    assert report.slices("risk_tags")["unsupported_family"] == {
        "passed": 2,
        "total": 2,
    }


def test_repository_root_discovers_cases_without_loading_result_json(qf):
    from pathlib import Path

    from quantifact.learn.benchmarks import BenchmarkSuite

    root = Path(__file__).resolve().parents[1] / "benchmarks"
    report = BenchmarkSuite(root).report(qf.adapter, [])

    assert report.total == 4
    assert report.passed == 4


def test_report_counts_a_silent_critical_failure():
    bench = Benchmark(
        "bad",
        "q",
        [],
        family="event_study",
        severity="critical",
        expected_outcome="plan",
    )
    report = BenchmarkReport([BenchmarkResult(bench, False, ["wrong answer escaped"])])
    assert report.silent_critical_failures == 1
    assert report.to_dict()["by_family"]["event_study"]["passed"] == 0
