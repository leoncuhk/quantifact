"""Teach: reproduce, fix, prove nothing else broke, then emit a patch.

The order is the whole point. A lesson is accepted only if a benchmark can be
written that fails against today's context, passes once the lesson is applied,
and leaves the rest of the suite green. Nothing merges itself.
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass
from typing import Any

from .benchmarks import Benchmark, BenchmarkSuite
from .lessons import Lesson, LessonRepo

KNOWN_EFFECTS = {
    "per_asset_class_panels": {
        "when": "multi_episode",
        "keywords": ["asset class", "per-asset", "by asset", "资产类别", "分资产"],
        "assertions": [{"type": "plan_has_task", "name": "market_scatter_by_asset_class"},
                       {"type": "chart_has_facet", "facet": "asset_class"},
                       {"type": "plan_valid"}],
    },
}


@dataclass
class TeachResult:
    lesson: Lesson
    benchmark: Benchmark
    failed_before: bool
    passes_after: bool
    regressions: list[str]
    files: list[str]
    accepted: bool

    def summary(self) -> str:
        lines = [
            f"lesson      {self.lesson.id}",
            f"benchmark   {self.benchmark.id}",
            f"reproduced  {'yes — benchmark failed before the change' if self.failed_before else 'NO — benchmark already passed, nothing to learn'}",
            f"fixed       {'yes' if self.passes_after else 'no'}",
            f"regressions {len(self.regressions)}"
            + ("" if not self.regressions else ": " + ", ".join(self.regressions)),
            f"verdict     {'PR ready' if self.accepted else 'rejected — not merged'}",
        ]
        return "\n".join(lines)


def draft_lesson(complaint: str) -> tuple[str, str, str | None]:
    """Map a free-text complaint to (effect, lesson_id, when).

    Deterministic keyword routing into a registry of effects the planner
    actually understands. A model can draft the prose instead — and will do it
    better — but the triple it returns still has to name an effect, because a
    lesson that maps to no effect cannot be verified and therefore cannot be
    accepted. That constraint is the point, not the keyword matching.
    """
    low = complaint.lower()
    for effect, spec in KNOWN_EFFECTS.items():
        if any(k in low for k in spec["keywords"]):
            return effect, effect.replace("_", "-"), spec["when"]
    raise ValueError(
        "no known planner effect matches this complaint; add one to "
        "KNOWN_EFFECTS (a lesson that maps to no effect cannot be verified)")


def teach(complaint: str, prompt: str, *, adapter, repo: LessonRepo,
          suite: BenchmarkSuite, entitlements: tuple[str, ...] = (),
          answers: dict[str, Any] | None = None,
          bench_id: str | None = None) -> TeachResult:
    effect, lesson_id, when = draft_lesson(complaint)
    spec = KNOWN_EFFECTS[effect]
    bench = Benchmark(
        id=bench_id or f"teach-{lesson_id}",
        prompt=prompt, answers=answers or {},
        assertions=spec["assertions"], origin="teach",
        note=textwrap.shorten(complaint, 200))

    # 1. reproduce: the benchmark must fail against the context *as it is today*
    baseline = repo.all()
    before = suite.run(bench, adapter, baseline, entitlements)
    failed_before = not before.passed

    lesson = Lesson(id=lesson_id, effect=effect, when=when, text=complaint.strip())
    candidate = [x for x in baseline if x.id != lesson.id] + [lesson]

    # 2. apply the lesson and re-run
    after = suite.run(bench, adapter, candidate, entitlements)

    # 3. regression check across the whole existing suite
    regressions: list[str] = []
    for r in suite.run_all(adapter, candidate, entitlements):
        if not r.passed:
            regressions.append(r.benchmark.id)

    accepted = failed_before and after.passed and not regressions
    files: list[str] = []
    if accepted:
        files.append(str(repo.add(lesson)))
        files.append(str(suite.add(bench)))
    return TeachResult(lesson=lesson, benchmark=bench, failed_before=failed_before,
                       passes_after=after.passed, regressions=regressions,
                       files=files, accepted=accepted)
