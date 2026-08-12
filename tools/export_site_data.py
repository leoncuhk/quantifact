"""Collect real artefacts from a live run into one JSON for the blueprint page.

Everything the page shows about *this* replication (plan, generated code, cache
keys, timings, benchmark table, teach-loop output) comes from here, so the page
can never drift from what the code actually does.

    uv run python tools/export_site_data.py site/data.json
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from quantifact import ANALYST, Quantifact
from quantifact.bench import run as run_bench
from quantifact.learn.benchmarks import BenchmarkSuite
from quantifact.learn.lessons import LessonRepo
from quantifact.learn.teach import teach

QUESTION = ("How have markets responded to the conflict in the Middle East and the "
            "resulting oil supply shortage, and how does today compare to similar "
            "historical episodes?")


def main(out: str = "site/data.json") -> int:
    ws = Path(".qf-site")
    if ws.exists():
        shutil.rmtree(ws)
    qf = Quantifact(ws, ANALYST)

    clarifications = [
        {"question": c.question, "why": c.why,
         "options": [{"label": o["label"], "recommended": bool(o.get("recommended"))}
                     for o in c.options]}
        for c in qf.clarify(QUESTION)
    ]

    # cold run
    art_cold = qf.analyse(QUESTION, out=ws / "report.html")
    # warm run: nothing changed
    art_warm = qf.analyse(QUESTION, out=ws / "report.html")

    _, planner = qf.build_plan(QUESTION)
    bindings = [{"requirement": b.requirement, "query": b.query, "chosen": b.chosen,
                 "considered": b.considered} for b in planner.bindings]

    repo = LessonRepo(ws / "context" / "lessons")
    suite = BenchmarkSuite(ws / "benchmarks")
    complaint = ("When comparing multiple historical episodes, break the analysis out "
                 "by asset class — FX, rates, equities and commodities transmit an oil "
                 "shock through fundamentally different channels, so a single pooled "
                 "scatter hides more than it reveals.")
    tr = teach(complaint, QUESTION, adapter=qf.adapter, repo=repo, suite=suite)
    art_taught = qf.analyse(QUESTION, out=ws / "report-taught.html")

    bench = run_bench(ws / "bench")

    plan = art_taught.plan
    # the same question at an earlier knowledge date — the page's PIT section
    earlier = qf.analyse(QUESTION, {"as_of": "2026-06-14"},
                         out=ws / "report-earlier.html", writeback=False)

    data = {
        "question": QUESTION,
        "as_of": art_taught.plan.as_of,
        "point_in_time": {
            "late": {"as_of": art_taught.plan.as_of,
                     "episodes": sorted(set(
                         art_taught.result.frames["spine_episodes"]["episode"])),
                     "return_cells": len(
                         art_taught.result.frames["market_episode_returns"]),
                     "cache_key": art_taught.result.trace("market_prices").cache_key},
            "early": {"as_of": earlier.plan.as_of,
                      "episodes": sorted(set(
                          earlier.result.frames["spine_episodes"]["episode"])),
                      "return_cells": len(
                          earlier.result.frames["market_episode_returns"]),
                      "cache_key": earlier.result.trace("market_prices").cache_key},
        },
        "clarifications": clarifications,
        "bindings": bindings,
        "plan": {
            "layers": art_taught.layers,
            "assumptions": plan.resolved_assumptions,
            "tasks": [
                {
                    "name": t.name, "type": t.type, "description": t.description,
                    "sort": t.sort,
                    "depends_on": t.depends_on, "index": t.index,
                    "row_expectation": t.row_expectation,
                    "series_inputs": t.series_inputs[:3],
                    "n_series": len(t.series_inputs),
                    "columns": [{"name": c.name, "dtype": c.dtype, "unit": c.unit,
                                 "role": c.role, "description": c.description}
                                for c in t.columns],
                    "invariants": t.invariants,
                    "chart_spec": t.chart_spec,
                    "code": art_taught.codes[t.name],
                    "rows": art_taught.result.trace(t.name).rows,
                    "cache_key": art_taught.result.trace(t.name).cache_key,
                }
                for t in plan.tasks
            ],
        },
        "runs": {
            "cold": {"stages": art_cold.timings,
                     "cached": art_cold.result.cache_hits,
                     "tasks": len(art_cold.result.traces),
                     "traces": [{"task": t.task, "ms": round(t.seconds * 1000, 2),
                                 "cached": t.cached, "rows": t.rows}
                                for t in art_cold.result.traces]},
            "warm": {"stages": art_warm.timings,
                     "cached": art_warm.result.cache_hits,
                     "tasks": len(art_warm.result.traces)},
            "after_teach": {"stages": art_taught.timings,
                            "cached": art_taught.result.cache_hits,
                            "tasks": len(art_taught.result.traces)},
        },
        "teach": {
            "complaint": complaint,
            "lesson_id": tr.lesson.id,
            "benchmark_id": tr.benchmark.id,
            "assertions": tr.benchmark.assertions,
            "failed_before": tr.failed_before,
            "passes_after": tr.passes_after,
            "regressions": tr.regressions,
            "accepted": tr.accepted,
            "files": [str(Path(f).relative_to(ws)) for f in tr.files],
        },
        "bench": bench.to_dict(),
        "review": [{"task": f.task, "severity": f.severity, "message": f.message}
                   for f in art_taught.findings],
        "store": {
            "series": len(qf.adapter.catalog()),
            "written_back": art_taught.written_series[:3],
        },
    }
    p = Path(out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=1, ensure_ascii=False))
    print(f"wrote {p} ({p.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
