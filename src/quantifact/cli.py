"""Command line surface.

    qf ask "<question>"        clarify, plan, execute, review, report
    qf clarify "<question>"    the clarifying questions and their defaults
    qf plan "<question>"       compile the plan and show layers and bindings
    qf catalog [query]         browse the catalog the way an agent sees it
    qf search "<query>"        recall plus inspection, with reasons
    qf teach "<complaint>"     the full teach → benchmark → patch loop
    qf evals                   run the benchmark suite
    qf bench                   run the performance benchmarks
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .agent import ANALYST, PM, Quantifact, User
from .learn.benchmarks import BenchmarkSuite
from .learn.lessons import LessonRepo

DEFAULT_WS = Path(".qf")
QUESTION = ("How have markets responded to the conflict in the Middle East and the "
            "resulting oil supply shortage, and how does today compare to similar "
            "historical episodes?")


def _user(name: str) -> User:
    return {"analyst": ANALYST, "pm": PM}.get(name, ANALYST)


def _llm(args):
    """Build the LLM backend trio when --backend llm is requested."""
    if getattr(args, "backend", "reference") != "llm":
        return None, None, None
    from .codegen.openai_compat import (
        LLMClient,
        OpenAICompatCodegen,
        OpenAICompatDebugger,
        OpenAICompatValidator,
    )
    from .harness.cache import RUNTIME_ID
    client = LLMClient()
    hint = None if getattr(args, "no_runtime_hint", False) else RUNTIME_ID
    return (OpenAICompatCodegen(client, runtime_hint=hint),
            OpenAICompatDebugger(client, runtime_hint=hint)
            if getattr(args, "fix", False) else None,
            OpenAICompatValidator(client) if getattr(args, "semantic", False) else None)


def cmd_ask(args) -> int:
    backend, debugger, semantic = _llm(args)
    qf = Quantifact(args.workspace, _user(args.user), backend=backend,
                    cache_enabled=not args.no_cache, debugger=debugger,
                    semantic_validator=semantic)
    answers = json.loads(args.answers) if args.answers else {}
    if args.as_of:
        answers["as_of"] = args.as_of
    out = args.out or Path(args.workspace) / "report.html"

    def stage(name: str, secs: float) -> None:
        print(f"  {name:<10} {secs * 1000:8.1f} ms", flush=True)

    print(f"question: {args.question}\n")
    art = qf.analyse(args.question, answers or None, out=out, on_stage=stage,
                     max_fix_rounds=args.fix_rounds)
    print(f"\nas_of      {art.plan.as_of} (nothing published later was read)")
    print(f"plan       {len(art.plan.tasks)} tasks in {len(art.layers)} layers")
    print(f"execution  {art.result.cache_hits}/{len(art.result.traces)} cached, "
          f"{art.result.wall_seconds * 1000:.0f} ms")
    print(f"contracts  {sum(1 for v in art.verdicts if v.ok)}/{len(art.verdicts)} "
          "verdicts passed")
    print(f"review     {len(art.findings)} findings")
    if art.written_series:
        print(f"writeback  {len(art.written_series)} series, "
              f"e.g. {art.written_series[0]}")
    if art.fix_rounds:
        print(f"repairs    {art.fix_rounds} round(s)")
    print(f"report     {art.report_path}")
    if args.receipt:
        receipt = {
            "as_of": art.plan.as_of, "backend": qf.backend.name,
            "tasks": len(art.plan.tasks), "layers": len(art.layers),
            "stages": art.timings, "fix_rounds": art.fix_rounds,
            "cached": art.result.cache_hits, "traces": len(art.result.traces),
            "findings": [{"task": f.task, "severity": f.severity,
                          "message": f.message} for f in art.findings],
            "written_series": len(art.written_series),
        }
        if backend is not None:
            u = backend.client.usage
            receipt["llm"] = {"model": backend.client.model, "calls": u.calls,
                              "retries": u.retries, "api_seconds": u.seconds,
                              "prompt_tokens": u.prompt_tokens,
                              "completion_tokens": u.completion_tokens}
        Path(args.receipt).write_text(json.dumps(receipt, indent=1))
        print(f"receipt    {args.receipt}")
    if backend is not None:
        print(f"llm        {backend.client.usage.summary()}")
    return 0


def cmd_clarify(args) -> int:
    qf = Quantifact(args.workspace, _user(args.user))
    for c in qf.clarify(args.question):
        print(f"\n{c.question}")
        print(f"  why: {c.why}")
        for o in c.options:
            print(f"   - {o['label']}" + ("  [RECOMMENDED]" if o.get("recommended")
                                          else ""))
    return 0


def cmd_plan(args) -> int:
    from .plan.layers import topo_layers
    qf = Quantifact(args.workspace, _user(args.user))
    answers = {"as_of": args.as_of} if args.as_of else None
    plan, planner = qf.build_plan(args.question, answers)
    print(f"as_of {plan.as_of}\n")
    for i, layer in enumerate(topo_layers(
            {t.name: list(t.depends_on) for t in plan.tasks})):
        print(f"layer {i}: {', '.join(layer)}")
    print()
    for t in plan.tasks:
        deps = f" <- {', '.join(t.depends_on)}" if t.depends_on else ""
        print(f"  {t.name:<32} {t.type:<14}{deps}")
    print("\nbindings:")
    for b in planner.bindings:
        print(f"  {b.requirement:<22} -> {b.chosen}")
        for c in b.considered:
            if not c["accepted"]:
                print(f"      rejected {c['series_id']}: {c['reasons'][0]}")
    if args.json:
        plan.save(args.json)
        print(f"\nwrote {args.json}")
    return 0


def cmd_catalog(args) -> int:
    qf = Quantifact(args.workspace, _user(args.user))
    metas = qf.adapter.catalog()
    if args.query:
        q = args.query.lower()
        metas = [m for m in metas
                 if q in m.series_id.lower() or q in m.name.lower()
                 or q in m.description.lower()]
    for m in metas[:args.limit]:
        print(m.card())
        print()
    print(f"{len(metas)} series (showing up to {args.limit})")
    return 0


def cmd_search(args) -> int:
    from .data.search import SeriesSearch
    from .planner import _as_store
    qf = Quantifact(args.workspace, _user(args.user))
    search = SeriesSearch(_as_store(qf.adapter), qf.user.entitlements)
    kwargs = {}
    if args.frequency:
        kwargs["frequency"] = args.frequency
    if args.unit:
        kwargs["unit"] = args.unit
    if args.prior:
        lo, hi = args.prior.split(",")
        kwargs["prior"] = (float(lo), float(hi))
    for h in search.search(args.query, k=args.k, **kwargs):
        print(f"{'accept' if h.accepted else 'REJECT'}  {h.meta.series_id:<30} "
              f"score={h.recall_score:5.2f}  {h.meta.frequency} {h.meta.unit}")
        for r in h.reasons:
            print(f"         {r}")
    return 0


def cmd_teach(args) -> int:
    from .learn.teach import teach
    ws = Path(args.workspace)
    qf = Quantifact(ws, _user(args.user))
    res = teach(args.complaint, args.question, adapter=qf.adapter,
                repo=LessonRepo(ws / "context" / "lessons"),
                suite=BenchmarkSuite(ws / "benchmarks"),
                entitlements=qf.user.entitlements)
    print(res.summary())
    if res.accepted:
        print("\nfiles written (this is the patch):")
        for f in res.files:
            print(f"  {f}")
    return 0 if res.accepted else 1


def cmd_evals(args) -> int:
    ws = Path(args.workspace)
    qf = Quantifact(ws, _user(args.user))
    suite = BenchmarkSuite(Path(args.dir) if args.dir else ws / "benchmarks")
    results = suite.run_all(qf.adapter, LessonRepo(ws / "context" / "lessons").all(),
                            qf.user.entitlements)
    if not results:
        print("no benchmarks yet — run `qf teach` first")
        return 0
    failed = 0
    for r in results:
        print(f"{'PASS' if r.passed else 'FAIL'}  {r.benchmark.id}")
        for f in r.failures:
            print(f"      {f}")
        failed += not r.passed
    print(f"\n{len(results) - failed}/{len(results)} passing")
    return 1 if failed else 0


def cmd_bench(args) -> int:
    from . import bench
    return bench.main(["--workspace", str(args.workspace)]
                      + (["--json", args.json] if args.json else []))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="qf", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workspace", default=str(DEFAULT_WS))
    ap.add_argument("--user", default="analyst", choices=["analyst", "pm"])
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("ask")
    a.set_defaults(fn=cmd_ask)
    a.add_argument("question", nargs="?", default=QUESTION)
    a.add_argument("--as-of", dest="as_of", help="knowledge date, YYYY-MM-DD")
    a.add_argument("--answers", help="JSON dict of clarification answers")
    a.add_argument("--out", help="report path")
    a.add_argument("--receipt", help="write a JSON receipt of this run")
    a.add_argument("--no-cache", action="store_true")
    a.add_argument("--backend", default="reference", choices=["reference", "llm"])
    a.add_argument("--fix", action="store_true", help="enable the debugger agent")
    a.add_argument("--semantic", action="store_true", help="enable L3 review")
    a.add_argument("--fix-rounds", type=int, default=2)
    a.add_argument("--no-runtime-hint", action="store_true")

    c = sub.add_parser("clarify")
    c.set_defaults(fn=cmd_clarify)
    c.add_argument("question", nargs="?", default=QUESTION)

    p = sub.add_parser("plan")
    p.set_defaults(fn=cmd_plan)
    p.add_argument("question", nargs="?", default=QUESTION)
    p.add_argument("--as-of", dest="as_of")
    p.add_argument("--json", help="write the plan as JSON")

    cat = sub.add_parser("catalog")
    cat.set_defaults(fn=cmd_catalog)
    cat.add_argument("query", nargs="?")
    cat.add_argument("--limit", type=int, default=10)

    s = sub.add_parser("search")
    s.set_defaults(fn=cmd_search)
    s.add_argument("query")
    s.add_argument("-k", type=int, default=8)
    s.add_argument("--frequency")
    s.add_argument("--unit")
    s.add_argument("--prior", help="lo,hi value prior")

    t = sub.add_parser("teach")
    t.set_defaults(fn=cmd_teach)
    t.add_argument("complaint")
    t.add_argument("--question", default=QUESTION)

    e = sub.add_parser("evals")
    e.set_defaults(fn=cmd_evals)
    e.add_argument("--dir", help="benchmark directory (default: the workspace's)")

    b = sub.add_parser("bench")
    b.set_defaults(fn=cmd_bench)
    b.add_argument("--json")

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
