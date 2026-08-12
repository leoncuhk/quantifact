"""Benchmarks: what the architecture buys, measured on this machine.

The comparison that cannot be reproduced here is against another agent product.
The comparison that can — and that is the actual mechanism — is the same plan
and the same generated code run with the harness's cache and layering switched
on versus off.

  cold          empty cache, everything executes
  warm          nothing changed, every task served from cache
  small_edit    the final chart is edited; how much re-executes
  no_cache      the same edit with caching disabled — the behaviour of an agent
                that re-invokes its own code every round
  codegen       parallel versus serial, at a fixed simulated per-task latency
  determinism   the same plan compiled twice: identical code, identical values
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from .agent import ANALYST, Quantifact
from .codegen.base import CodegenBackend, generate_all, generate_serially
from .codegen.reference import ReferenceCodegen
from .codegen.simulated import SimulatedLatencyCodegen
from .harness.cache import ValueCache
from .harness.execute import ExecutionHarness
from .plan.model import AnalysisPlan

QUESTION = (
    "How have markets responded to the conflict in the Middle East and the "
    "resulting oil supply shortage, and how does today compare to similar "
    "historical episodes?"
)


@dataclass
class Timing:
    label: str
    seconds: float
    tasks_executed: int
    tasks_cached: int
    note: str = ""


@dataclass
class BenchReport:
    question: str
    tasks: int
    layers: int
    as_of: str = ""
    timings: list[Timing] = field(default_factory=list)
    determinism: dict[str, Any] = field(default_factory=dict)
    codegen: dict[str, Any] = field(default_factory=dict)
    environment: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["speedups"] = self.speedups()
        return d

    def get(self, label: str) -> Timing:
        return next(t for t in self.timings if t.label == label)

    def speedups(self) -> dict[str, float]:
        out: dict[str, float] = {}
        try:
            out["warm_vs_cold"] = self.get("cold").seconds / max(
                self.get("warm").seconds, 1e-9
            )
            out["small_edit_vs_no_cache"] = self.get("no_cache").seconds / max(
                self.get("small_edit").seconds, 1e-9
            )
            out["small_edit_vs_cold"] = self.get("cold").seconds / max(
                self.get("small_edit").seconds, 1e-9
            )
        except StopIteration:
            pass
        return out

    def markdown(self) -> str:
        rows = "\n".join(
            f"| {t.label} | {t.seconds * 1000:8.1f} ms | {t.tasks_executed} | "
            f"{t.tasks_cached} | {t.note} |"
            for t in self.timings
        )
        head = (
            f"plan: {self.tasks} tasks in {self.layers} layers, "
            f"as_of {self.as_of}\n\n"
            "| scenario | wall | executed | cached | note |\n"
            "|---|---:|---:|---:|---|\n"
        )
        tail = "\n\n" + "\n".join(
            f"- {k}: **{v:.1f}x**" for k, v in self.speedups().items()
        )
        det = (
            f"\n- code identical across two compilations: "
            f"{self.determinism.get('identical_code', 0)}/{self.tasks} tasks"
            f"\n- values identical: "
            f"{self.determinism.get('identical_values', 0)}/{self.tasks} tasks"
        )
        cg = (
            f"\n- codegen at {self.codegen.get('simulated_latency_per_task', 0):.2f}s"
            f" simulated latency per task: parallel "
            f"{self.codegen.get('parallel', 0):.2f}s vs serial "
            f"{self.codegen.get('serial', 0):.2f}s "
            f"({self.codegen.get('speedup', 0):.1f}x)"
            f"\n- the same codegen for a 3-task plan: "
            f"{self.codegen.get('parallel_3_tasks', 0):.2f}s"
        )
        return head + rows + tail + det + cg


def edit_last_chart(plan: AnalysisPlan) -> AnalysisPlan:
    """The edit benchmark: retitle and reorder the final chart, nothing else."""
    edited = AnalysisPlan.from_dict(json.loads(json.dumps(plan.to_dict())))
    chart = edited.charts()[-1]
    chart.chart_spec["title"] = chart.chart_spec.get("title", "") + " (revised)"
    if chart.sort:
        chart.sort = [[c, not a] for c, a in chart.sort]
    return edited


def values_hash(frames: dict[str, pd.DataFrame]) -> dict[str, str]:
    out = {}
    for name, df in frames.items():
        h = hashlib.sha256()
        h.update(pd.util.hash_pandas_object(df, index=False).to_numpy().tobytes())
        out[name] = h.hexdigest()[:16]
    return out


def run(
    workspace: str | Path = ".qf-bench",
    backend: CodegenBackend | None = None,
    keep: bool = False,
    latency: float = 0.4,
) -> BenchReport:
    ws = Path(workspace)
    if ws.exists() and not keep:
        shutil.rmtree(ws)
    backend = backend or ReferenceCodegen()
    qf = Quantifact(ws, ANALYST, backend=backend)
    plan, _ = qf.build_plan(QUESTION)

    report = BenchReport(
        question=QUESTION,
        tasks=len(plan.tasks),
        layers=0,
        as_of=plan.as_of,
        environment={
            "backend": backend.name,
            "pandas": pd.__version__,
            "adapter": qf.adapter.name,
        },
    )

    # ---- codegen: parallel vs serial ------------------------------------
    codes = generate_all(plan, backend)
    sim = SimulatedLatencyCodegen(latency)
    small = AnalysisPlan(
        question=plan.question,
        as_of=plan.as_of,
        tasks=[t for t in plan.tasks if t.type == "data_ingestion"][:3],
    )
    t0 = time.perf_counter()
    generate_all(plan, sim)
    par = time.perf_counter() - t0
    t0 = time.perf_counter()
    generate_serially(plan, sim)
    ser = time.perf_counter() - t0
    t0 = time.perf_counter()
    generate_all(small, sim)
    par3 = time.perf_counter() - t0
    report.codegen = {
        "simulated_latency_per_task": latency,
        "parallel": par,
        "serial": ser,
        "speedup": ser / max(par, 1e-9),
        "parallel_3_tasks": par3,
        "tasks": len(plan.tasks),
    }

    def timed(
        label: str,
        harness: ExecutionHarness,
        p: AnalysisPlan,
        c: dict[str, str],
        note: str = "",
    ) -> Timing:
        t = time.perf_counter()
        res = harness.run(p, c)
        elapsed = time.perf_counter() - t
        report.layers = len(res.layers)
        return Timing(
            label, elapsed, len(res.traces) - res.cache_hits, res.cache_hits, note
        )

    # Warm the OS page cache first so every scenario is measured on the same
    # footing; otherwise the first full run pays for reading the store off disk
    # and the comparison flatters the cache.
    ExecutionHarness(qf.adapter, ValueCache(ws / "warmup", enabled=False)).run(
        plan, codes
    )

    cache = ValueCache(ws / "bench-cache")
    cache.clear()
    harness = ExecutionHarness(qf.adapter, cache)
    report.timings.append(timed("cold", harness, plan, codes, "empty cache"))
    report.timings.append(timed("warm", harness, plan, codes, "nothing changed"))

    edited = edit_last_chart(plan)
    edited_codes = generate_all(edited, backend)
    report.timings.append(
        timed("small_edit", harness, edited, edited_codes, "final chart edited")
    )
    naive = ExecutionHarness(qf.adapter, ValueCache(ws / "nocache", enabled=False))
    report.timings.append(
        timed("no_cache", naive, edited, edited_codes, "same edit, caching disabled")
    )

    # ---- determinism ----------------------------------------------------
    a_codes, b_codes = generate_all(plan, backend), generate_all(plan, backend)
    ra = ExecutionHarness(qf.adapter, ValueCache(ws / "det-a", enabled=False)).run(
        plan, a_codes
    )
    rb = ExecutionHarness(qf.adapter, ValueCache(ws / "det-b", enabled=False)).run(
        plan, b_codes
    )
    ha, hb = values_hash(ra.frames), values_hash(rb.frames)
    report.determinism = {
        "identical_code": sum(1 for k in a_codes if a_codes[k] == b_codes[k]),
        "identical_values": sum(1 for k in ha if ha[k] == hb.get(k)),
        "tasks": len(plan.tasks),
    }
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="quantifact benchmarks")
    ap.add_argument("--workspace", default=".qf-bench")
    ap.add_argument("--json", type=str, default=None, help="write results as JSON")
    args = ap.parse_args(argv)
    rep = run(args.workspace)
    print(rep.markdown())
    if args.json:
        Path(args.json).write_text(json.dumps(rep.to_dict(), indent=2))
        print(f"\nwrote {args.json}")
    return 0
