"""Benchmarks: hard assertions over what the planner produces.

Model judgement is deliberately absent here. A reproducible system deserves
checks that fail for a stated reason; soft scoring sends hill-climbing into
noise.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .lessons import Lesson


@dataclass
class Benchmark:
    id: str
    prompt: str
    assertions: list[dict[str, Any]]
    answers: dict[str, Any] = field(default_factory=dict)
    kind: str = "plan"
    origin: str = "teach"
    human_audited: bool = False
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict[str, Any]) -> Benchmark:
        return Benchmark(**d)


@dataclass
class BenchmarkResult:
    benchmark: Benchmark
    passed: bool
    failures: list[str] = field(default_factory=list)


class BenchmarkSuite:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def all(self) -> list[Benchmark]:
        return [Benchmark.from_dict(json.loads(p.read_text()))
                for p in sorted(self.root.glob("*.json"))]

    def add(self, bench: Benchmark) -> Path:
        p = self.root / f"{bench.id}.json"
        p.write_text(json.dumps(bench.to_dict(), indent=2, ensure_ascii=False))
        return p

    def remove(self, bench_id: str) -> None:
        (self.root / f"{bench_id}.json").unlink(missing_ok=True)

    # -------------------------------------------------------------- running
    def run(self, bench: Benchmark, adapter, lessons: list[Lesson],
            entitlements: tuple[str, ...] = ()) -> BenchmarkResult:
        from ..plan.compile import PlanCompiler
        from ..planner import RulePlanner

        planner = RulePlanner(adapter, entitlements=entitlements, lessons=lessons)
        failures: list[str] = []
        try:
            plan = planner.plan(bench.prompt, bench.answers)
        except Exception as e:
            return BenchmarkResult(bench, False, [f"planning raised {type(e).__name__}: {e}"])

        for a in bench.assertions:
            t = a["type"]
            if t == "plan_has_task":
                if plan.task(a["name"]) is None:
                    failures.append(f"plan has no task '{a['name']}'")
            elif t == "plan_lacks_task":
                if plan.task(a["name"]) is not None:
                    failures.append(f"plan unexpectedly contains task '{a['name']}'")
            elif t == "chart_has_facet":
                ok = any((c.chart_spec or {}).get("facet") == a["facet"]
                         for c in plan.charts())
                if not ok:
                    failures.append(f"no chart faceted by '{a['facet']}'")
            elif t == "task_count_min":
                if len(plan.tasks) < a["value"]:
                    failures.append(f"plan has {len(plan.tasks)} tasks, "
                                    f"expected >= {a['value']}")
            elif t == "plan_valid":
                problems = PlanCompiler(
                    known_series={m.series_id for m in adapter.catalog()},
                    known_tables=set(adapter.tables())).validate(plan)
                failures.extend(f"plan invalid: {p}" for p in problems)
            elif t == "series_bound":
                b = next((x for x in planner.bindings
                          if x.requirement == a["requirement"]), None)
                if b is None:
                    failures.append(f"requirement '{a['requirement']}' was never bound")
                elif b.chosen != a["series_id"]:
                    failures.append(f"requirement '{a['requirement']}' bound to "
                                    f"{b.chosen}, expected {a['series_id']}")
            elif t == "series_rejected":
                b = next((x for x in planner.bindings
                          if x.requirement == a["requirement"]), None)
                considered = {c["series_id"]: c for c in (b.considered if b else [])}
                c = considered.get(a["series_id"])
                if c is None:
                    failures.append(f"'{a['series_id']}' was never even considered for "
                                    f"'{a['requirement']}'")
                elif c["accepted"]:
                    failures.append(f"'{a['series_id']}' was accepted for "
                                    f"'{a['requirement']}' but should be rejected")
            else:
                failures.append(f"unknown assertion type '{t}'")
        return BenchmarkResult(bench, not failures, failures)

    def run_all(self, adapter, lessons: list[Lesson],
                entitlements: tuple[str, ...] = ()) -> list[BenchmarkResult]:
        return [self.run(b, adapter, lessons, entitlements) for b in self.all()]


