"""End-to-end orchestration.

Deliberately plain Python: no agent decides what happens next. The sequence is
fixed, every stage is timed, and no validation stage can be skipped by a model
that "forgot".

    clarify → plan → compile plan → codegen (parallel) → L0 static
            → execute (as-of bound, cached, layered) → L1/L1-pit/L2 per frame
            → repair loop → L3 (optional) → L4 self review → write back → report

The repair loop is deliberately the same shape for every kind of failure: a
runtime exception, a schema breach and an implausible number all become a
verdict, and a verdict plus evidence is what the debugger receives.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from .codegen.base import CodegenBackend, generate_all, schemas_of
from .codegen.reference import ReferenceCodegen
from .contracts.layers import validate_result, validate_static
from .contracts.reasoning import validate_claim_evidence
from .contracts.verdict import TaskUnfixable, Verdict
from .data.adapters.demo_synthetic import DemoSyntheticAdapter
from .data.registry import SeriesMeta
from .harness.cache import ValueCache
from .harness.execute import ExecutionHarness, RunResult, TaskExecutionError
from .learn.lessons import LessonRepo
from .learn.workflows import WorkflowRepo
from .plan.compile import PlanCompiler
from .plan.model import AnalysisPlan, Task
from .planner import Clarification, RulePlanner
from .report.render import render_report
from .review.checks import Finding, blocking, review, review_frame
from .static_analysis.ast_checks import CodeFacts, analyse


@dataclass
class User:
    """Who is asking. Entitlement tags decide what their catalog contains."""

    name: str
    entitlements: tuple[str, ...] = ()


ANALYST = User("analyst", ())
PM = User("portfolio-manager", ("secure:positions",))


@dataclass
class Artifacts:
    plan: AnalysisPlan
    codes: dict[str, str]
    result: RunResult
    findings: list[Finding]
    verdicts: list[Verdict]
    timings: dict[str, float]
    report_path: Path | None = None
    written_series: list[str] = field(default_factory=list)
    fix_rounds: int = 0
    planning_trace: dict[str, Any] = field(default_factory=dict)
    repair_trace: list[dict[str, Any]] = field(default_factory=list)

    @property
    def layers(self) -> list[list[str]]:
        return self.result.layers

    def receipt(self, *, backend: str = "", user: str = "") -> dict[str, Any]:
        """A portable audit record, without embedding data or generated code.

        Hashes make the exact plan and code identifiable; inputs, verdicts,
        repairs and task traces make the path to the result reconstructable.
        The report remains the human surface, while this is the machine surface.
        """
        plan_json = json.dumps(self.plan.to_dict(), sort_keys=True, separators=(",", ":"))
        return {
            "schema_version": 1,
            "question": self.plan.question,
            "as_of": self.plan.as_of,
            "backend": backend,
            "user": user,
            "plan_sha256": hashlib.sha256(plan_json.encode()).hexdigest(),
            "plan": self.plan.to_dict(),
            "code_sha256": {
                name: hashlib.sha256(src.encode()).hexdigest()
                for name, src in sorted(self.codes.items())
            },
            "input_series": self.plan.series_inputs(),
            "planning_trace": self.planning_trace,
            "repair_trace": self.repair_trace,
            "execution": [asdict(t) for t in self.result.traces],
            "verdicts": [asdict(v) for v in self.verdicts],
            "findings": [asdict(f) for f in self.findings],
            "timings": self.timings,
            "written_series": self.written_series,
            "report": str(self.report_path) if self.report_path else None,
        }


def _planner_trace(planner: Any) -> dict[str, Any]:
    """Normalise both rule and model planner evidence without coupling them."""
    out: dict[str, Any] = {"planner": type(planner).__name__}
    bindings = getattr(planner, "bindings", None)
    if bindings is not None:
        out["bindings"] = [asdict(x) if is_dataclass(x) else vars(x) for x in bindings]
    trace = getattr(planner, "trace", None)
    if trace is not None:
        out["model"] = asdict(trace) if is_dataclass(trace) else vars(trace)
    return out


def evidence_for(task: Task, frames: dict[str, pd.DataFrame]) -> str:
    """What a human looks at before rewriting code: the real shape and range of
    every upstream frame. A verdict says what is wrong; evidence says what the
    data is."""
    lines: list[str] = []
    for dep in task.depends_on:
        df = frames.get(dep)
        if df is None:
            continue
        lines.append(f"{dep}: {len(df)} rows x {len(df.columns)} cols")
        for col in df.columns:
            s = df[col]
            if pd.api.types.is_datetime64_any_dtype(s):
                examples = [str(v)[:10] for v in s.drop_duplicates().head(3)]
                lines.append(
                    f"  {col} (datetime): {s.min()} .. {s.max()}; examples {examples}"
                )
            elif pd.api.types.is_numeric_dtype(s):
                lines.append(f"  {col} ({s.dtype}): {s.min():.6g} .. {s.max():.6g}")
            else:
                vals = [str(v) for v in s.drop_duplicates().head(4)]
                lines.append(f"  {col} ({s.dtype}): {vals}")
    return "\n".join(lines)


class Quantifact:
    """The whole system, assembled around one adapter and one user."""

    def __init__(
        self,
        workspace: str | Path,
        user: User = ANALYST,
        adapter: Any | None = None,
        backend: CodegenBackend | None = None,
        cache_enabled: bool = True,
        debugger: Any | None = None,
        semantic_validator: Any | None = None,
        planner_backend: Any | None = None,
    ):
        self.ws = Path(workspace)
        self.ws.mkdir(parents=True, exist_ok=True)
        self.user = user
        self.adapter = adapter or DemoSyntheticAdapter(self.ws / "store")
        self.cache = ValueCache(self.ws / "cache", enabled=cache_enabled)
        self.harness = ExecutionHarness(self.adapter, self.cache)
        self.backend = backend or ReferenceCodegen()
        self.lessons = LessonRepo(self.ws / "context" / "lessons")
        self.workflows = WorkflowRepo(self.ws / "context" / "workflows")
        self.debugger = debugger
        self.semantic_validator = semantic_validator
        # A planner backend broadens the supported questions within the exposed
        # data and operation vocabulary. The rule path stays exact and offline.
        self.planner_backend = planner_backend

    # ------------------------------------------------------------- planning
    def planner(self):
        if self.planner_backend is not None:
            from .planner_llm import LLMPlanner

            return LLMPlanner(
                self.adapter,
                self.planner_backend,
                entitlements=self.user.entitlements,
                lessons=self.lessons.all(),
                workflows=self.workflows,
            )
        return RulePlanner(
            self.adapter, entitlements=self.user.entitlements, lessons=self.lessons.all()
        )

    def clarify(self, prompt: str) -> list[Clarification]:
        return self.planner().clarify(prompt)

    def build_plan(
        self, prompt: str, answers: dict[str, Any] | None = None
    ) -> tuple[AnalysisPlan, RulePlanner]:
        p = self.planner()
        plan = p.plan(prompt, answers)
        PlanCompiler(
            known_series={m.series_id for m in self.adapter.catalog()},
            known_tables=set(self.adapter.tables()),
            table_columns=self._table_columns(plan.as_of),
            require_research_design=True,
        ).compile(plan)
        return plan, p

    def _table_columns(self, as_of: str) -> dict[str, set[str]]:
        return {
            name: set(self.adapter.read_table(name, as_of=as_of).columns)
            for name in self.adapter.tables()
        }

    # -------------------------------------------------------------- running
    def analyse(
        self,
        prompt: str,
        answers: dict[str, Any] | None = None,
        out: str | Path | None = None,
        max_fix_rounds: int = 2,
        writeback: bool = True,
        on_stage: Callable[[str, float], None] | None = None,
    ) -> Artifacts:
        timings: dict[str, float] = {}

        def stage(name: str, fn):
            t0 = time.perf_counter()
            value = fn()
            timings[name] = time.perf_counter() - t0
            if on_stage:
                on_stage(name, timings[name])
            return value

        plan, planner = stage("plan", lambda: self.build_plan(prompt, answers))
        planning_trace = _planner_trace(planner)
        repair_trace: list[dict[str, Any]] = []
        codes: dict[str, str] = stage("codegen", lambda: generate_all(plan, self.backend))
        facts: dict[str, CodeFacts] = stage(
            "static", lambda: {n: analyse(n, s) for n, s in codes.items()}
        )

        verdicts = validate_static(plan, codes, facts)
        rounds = 0
        bad = [v for v in verdicts if not v.ok]
        if bad:
            extra, more = self._repair_static(plan, codes, facts, bad, max_fix_rounds)
            verdicts += extra
            rounds += more
            repair_trace += [
                {"task": v.task, "layer": v.layer, "problems": v.problems, "rounds": more}
                for v in bad
            ]

        def execute() -> RunResult:
            """Execution loop: a runtime error is a verdict like any other.

            The repair budget is per task, not per run — a plan where five
            ingestions share one API mistake must not exhaust it on the first
            two.
            """
            nonlocal rounds
            attempts: dict[str, int] = {}
            while True:
                try:
                    return self.harness.run(plan, codes, facts)
                except TaskExecutionError as e:
                    attempts[e.task] = attempts.get(e.task, 0) + 1
                    if self.debugger is None or attempts[e.task] > max_fix_rounds:
                        raise
                    task = plan[e.task]
                    codes[e.task] = self.debugger.edit(
                        task,
                        codes[e.task],
                        Verdict(e.task, "runtime", False, [e.message]),
                        upstream=schemas_of(plan, task),
                        as_of=plan.as_of,
                    )
                    facts[e.task] = analyse(e.task, codes[e.task])
                    repair_trace.append(
                        {
                            "task": e.task,
                            "layer": "runtime",
                            "attempt": attempts[e.task],
                            "problems": [e.message],
                        }
                    )
                    rounds += 1

        result: RunResult = stage("execute", execute)

        reasoning_verdicts = stage(
            "critical_thinking", lambda: validate_claim_evidence(plan, result.frames)
        )
        verdicts += reasoning_verdicts
        failed_reasoning = [v for v in reasoning_verdicts if not v.ok]
        if failed_reasoning:
            raise TaskUnfixable(failed_reasoning[0])

        frame_verdicts = stage(
            "validate",
            lambda: [
                v
                for task in plan.tasks
                for v in validate_result(task, result.frames[task.name], plan.as_of)
            ],
        )
        verdicts += frame_verdicts

        failing = [v for v in frame_verdicts if not v.ok]
        if failing:
            extra, more = self._repair_results(
                plan, codes, facts, result.frames, failing, max_fix_rounds
            )
            rounds += more
            verdicts += extra
            repair_trace += [
                {"task": v.task, "layer": v.layer, "problems": v.problems, "rounds": more}
                for v in failing
            ]
            result = self.harness.run(plan, codes, facts)
            recheck = [
                v
                for task in plan.tasks
                for v in validate_result(task, result.frames[task.name], plan.as_of)
            ]
            verdicts += recheck
            still = [v for v in recheck if not v.ok]
            if still:
                raise TaskUnfixable(still[0])

        if self.semantic_validator is not None:
            for task in plan.tasks:
                v = self.semantic_validator.validate(
                    task, codes[task.name], result.frames[task.name], plan.as_of
                )
                verdicts.append(v)
                if not v.ok and self.debugger is None:
                    raise TaskUnfixable(v)

        findings = stage("review", lambda: review(plan, result.frames))
        if blocking(findings) and self.debugger is not None:
            by_task: dict[str, list[str]] = {}
            for f in blocking(findings):
                by_task.setdefault(f.task, []).append(f.message)
            extra, more = self._repair_results(
                plan,
                codes,
                facts,
                result.frames,
                [Verdict(t, "L4-review", False, msgs) for t, msgs in by_task.items()],
                max_fix_rounds,
            )
            rounds += more
            verdicts += extra
            repair_trace += [
                {"task": t, "layer": "L4-review", "problems": messages, "rounds": more}
                for t, messages in by_task.items()
            ]
            result = self.harness.run(plan, codes, facts)
            findings = review(plan, result.frames)
        if blocking(findings):
            raise TaskUnfixable(
                Verdict(
                    blocking(findings)[0].task,
                    "L4-review",
                    False,
                    [f.message for f in blocking(findings)],
                )
            )

        written: list[str] = []
        if writeback:
            written = stage("writeback", lambda: self.write_back(plan, result, prompt))

        report_path = None
        if out is not None:
            report_path = stage(
                "report",
                lambda: render_report(
                    plan,
                    result,
                    findings,
                    codes,
                    out,
                    meta={
                        "codegen": f"{timings['codegen']:.2f}s",
                        "backend": self.backend.name,
                        "user": self.user.name,
                    },
                ),
            )

        return Artifacts(
            plan=plan,
            codes=codes,
            result=result,
            findings=findings,
            verdicts=verdicts,
            timings=timings,
            report_path=report_path,
            written_series=written,
            fix_rounds=rounds,
            planning_trace=planning_trace,
            repair_trace=repair_trace,
        )

    # ------------------------------------------------------------ fix loops
    def _repair_static(
        self,
        plan: AnalysisPlan,
        codes: dict[str, str],
        facts: dict[str, CodeFacts],
        failures: list[Verdict],
        max_rounds: int,
    ) -> tuple[list[Verdict], int]:
        if self.debugger is None:
            raise TaskUnfixable(failures[0])
        out: list[Verdict] = []
        rounds = 0
        pending = {v.task: v for v in failures}
        while pending and rounds < max_rounds:
            rounds += 1
            for name, verdict in list(pending.items()):
                task = plan[name]
                codes[name] = self.debugger.edit(
                    task,
                    codes[name],
                    verdict,
                    upstream=schemas_of(plan, task),
                    as_of=plan.as_of,
                )
                facts[name] = analyse(name, codes[name])
                v = next(x for x in validate_static(plan, codes, facts) if x.task == name)
                out.append(v)
                if v.ok:
                    pending.pop(name)
        if pending:
            raise TaskUnfixable(next(iter(pending.values())))
        return out, rounds

    def _repair_results(
        self,
        plan: AnalysisPlan,
        codes: dict[str, str],
        facts: dict[str, CodeFacts],
        frames: dict[str, pd.DataFrame],
        failures: list[Verdict],
        max_rounds: int = 2,
    ) -> tuple[list[Verdict], int]:
        """Repair tasks whose *results* failed a layer.

        Each attempt re-executes that single task against its already-valid
        upstream frames and re-checks the same layers, so a repair that does not
        actually fix the contract cannot pass by accident.
        """
        if self.debugger is None:
            raise TaskUnfixable(failures[0])
        out: list[Verdict] = []
        rounds = 0
        pending = {v.task: v for v in failures}
        while pending and rounds < max_rounds:
            rounds += 1
            for name, verdict in list(pending.items()):
                task = plan[name]
                codes[name] = self.debugger.edit(
                    task,
                    codes[name],
                    verdict,
                    upstream=schemas_of(plan, task),
                    evidence=evidence_for(task, frames),
                    as_of=plan.as_of,
                )
                facts[name] = analyse(name, codes[name])
                v0 = next(
                    x for x in validate_static(plan, codes, facts) if x.task == name
                )
                out.append(v0)
                if not v0.ok:
                    pending[name] = v0
                    continue
                try:
                    df = self.harness.run_one(task, codes[name], frames, plan.as_of)
                except Exception as e:
                    pending[name] = Verdict(
                        name, "runtime", False, [f"{type(e).__name__}: {e}"]
                    )
                    out.append(pending[name])
                    continue
                checks = validate_result(task, df, plan.as_of)
                review_blocks = [
                    f.message for f in review_frame(task, df) if f.severity == "blocking"
                ]
                if review_blocks:
                    checks = [*checks, Verdict(name, "L4-review", False, review_blocks)]
                out.extend(checks)
                bad = [c for c in checks if not c.ok]
                if bad:
                    pending[name] = bad[0]
                else:
                    frames[name] = df
                    pending.pop(name)
        if pending:
            raise TaskUnfixable(next(iter(pending.values())))
        return out, rounds

    # ------------------------------------------------------------ writeback
    def write_back(self, plan: AnalysisPlan, result: RunResult, prompt: str) -> list[str]:
        """Outputs land in the same store the inputs came from.

        Two consequences: an analysis output is indistinguishable from a
        modelled input, and one analysis can feed the next — which is how a
        research desk compounds instead of repeating itself. The publication
        date of a written series is the knowledge date of the run that produced
        it, so it can never leak backwards into an earlier vintage.
        """
        store = getattr(self.adapter, "store", None)
        if store is None:
            return []
        slug = "".join(ch if ch.isalnum() else "_" for ch in prompt.lower())[:28].strip(
            "_"
        )
        written: list[str] = []
        upstream = plan.series_inputs()
        for task in plan.tasks:
            if task.type != "table_logic" or "date" not in task.column_names:
                continue
            entity = next((c for c in task.index if c != "date"), None)
            value_col = next(
                (
                    c.name
                    for c in task.columns
                    if c.dtype == "float64" and c.name not in task.index
                ),
                None,
            )
            if entity is None or value_col is None:
                continue
            df = result.frames[task.name]
            for key, g in df.groupby(entity, sort=True):
                sid = f"QF.{slug}.{task.name}.{key}".upper()
                s = pd.Series(
                    g[value_col].to_numpy(dtype="float64"),
                    index=pd.to_datetime(g["date"]),
                )
                s = s[~s.index.duplicated(keep="last")]
                pub = pd.Series(pd.Timestamp(plan.as_of), index=s.index)
                store.write(
                    SeriesMeta(
                        series_id=sid,
                        name=f"{task.name}: {key}",
                        description=(
                            f"Produced by quantifact for '{prompt[:70]}' "
                            f"(task {task.name}, as_of {plan.as_of})"
                        ),
                        frequency="M",
                        unit="%",
                        source="quantifact-analysis",
                        license_tag="derived",
                        owner=self.user.name,
                        lineage=upstream,
                    ),
                    s,
                    pub_dates=pub,
                )
                written.append(sid)
        return written
