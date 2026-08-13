"""Command line surface.

qf ask "<question>"        clarify, plan, execute, review, report
qf clarify "<question>"    the clarifying questions and their defaults
qf plan "<question>"       compile the plan and show layers and bindings
qf catalog [query]         browse the catalog the way an agent sees it
qf search "<query>"        recall plus inspection, with reasons
qf docs "<query>"          the research corpus, as of a knowledge date
qf teach "<complaint>"     the full teach → benchmark → patch loop
qf evals                   run the benchmark suite
qf bench                   run the performance benchmarks
qf audit                   evidence-backed PAT maturity audit
qf verify <package>        verify a research evidence package offline
qf adapter-check           run the point-in-time adapter conformance suite
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
QUESTION = (
    "How have markets responded to the conflict in the Middle East and the "
    "resulting oil supply shortage, and how does today compare to similar "
    "historical episodes?"
)


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
    return (
        OpenAICompatCodegen(client, runtime_hint=hint),
        OpenAICompatDebugger(client, runtime_hint=hint)
        if getattr(args, "fix", False)
        else None,
        OpenAICompatValidator(client) if getattr(args, "semantic", False) else None,
    )


def _planner_backend(args):
    """Use a model planner within the exposed data and operation vocabulary.

    The plan compiler still decides whether its output is admissible.
    """
    if getattr(args, "planner", "rule") != "llm":
        return None
    from .codegen.openai_compat import LLMClient

    return LLMClient()


def cmd_ask(args) -> int:
    backend, debugger, semantic = _llm(args)
    qf = Quantifact(
        args.workspace,
        _user(args.user),
        backend=backend,
        cache_enabled=not args.no_cache,
        debugger=debugger,
        semantic_validator=semantic,
        planner_backend=_planner_backend(args),
        execution_mode=args.execution,
        task_timeout_seconds=args.task_timeout,
    )
    answers = json.loads(args.answers) if args.answers else {}
    if args.as_of:
        answers["as_of"] = args.as_of
    if args.interactive:
        answers.update(_ask_clarifications(qf, args.question, answers))
    out = args.out or Path(args.workspace) / "report.html"

    def stage(name: str, secs: float) -> None:
        print(f"  {name:<10} {secs * 1000:8.1f} ms", flush=True)

    print(f"question: {args.question}\n")
    art = qf.analyse(
        args.question,
        answers or None,
        out=out,
        on_stage=stage,
        max_fix_rounds=args.fix_rounds,
        evidence_out=args.evidence,
    )
    print(f"\nas_of      {art.plan.as_of} (nothing published later was read)")
    print(f"plan       {len(art.plan.tasks)} tasks in {len(art.layers)} layers")
    print(
        f"execution  {art.result.cache_hits}/{len(art.result.traces)} cached, "
        f"{art.result.wall_seconds * 1000:.0f} ms"
    )
    print(
        f"contracts  {sum(1 for v in art.verdicts if v.ok)}/{len(art.verdicts)} "
        "verdicts passed"
    )
    print(f"review     {len(art.findings)} findings")
    if art.written_series:
        print(
            f"writeback  {len(art.written_series)} series, e.g. {art.written_series[0]}"
        )
    if art.fix_rounds:
        print(f"repairs    {art.fix_rounds} round(s)")
    print(f"report     {art.report_path}")
    if art.evidence_path:
        print(f"evidence   {art.evidence_path} ({art.evidence.package_id[:12]})")
    if args.receipt:
        receipt = art.receipt(backend=qf.backend.name, user=qf.user.name)
        if backend is not None:
            u = backend.client.usage
            receipt["llm"] = {
                "model": backend.client.model,
                "calls": u.calls,
                "retries": u.retries,
                "api_seconds": u.seconds,
                "prompt_tokens": u.prompt_tokens,
                "completion_tokens": u.completion_tokens,
            }
        Path(args.receipt).write_text(json.dumps(receipt, indent=1))
        print(f"receipt    {args.receipt}")
    if backend is not None:
        print(f"llm        {backend.client.usage.summary()}")
    return 0


def _ask_clarifications(qf, question: str, answers: dict) -> dict:
    """The back-and-forth, in a terminal. People under-invest in planning; the
    questions exist to make that expensive rather than easy."""
    out = {}
    for c in qf.clarify(question):
        if c.id in answers:
            continue
        print(f"\n{c.question}\n  why: {c.why}")
        for i, o in enumerate(c.options, 1):
            mark = "  [recommended]" if o.get("recommended") else ""
            print(f"  {i}. {o['label']}{mark}")
        raw = input("  choose [enter = recommended]: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(c.options):
            out[c.id] = c.options[int(raw) - 1]["value"]
        else:
            out[c.id] = c.recommended
    print()
    return out


def cmd_clarify(args) -> int:
    qf = Quantifact(args.workspace, _user(args.user))
    for c in qf.clarify(args.question):
        print(f"\n{c.question}")
        print(f"  why: {c.why}")
        for o in c.options:
            print(
                f"   - {o['label']}" + ("  [RECOMMENDED]" if o.get("recommended") else "")
            )
    return 0


def cmd_plan(args) -> int:
    from .plan.layers import topo_layers

    qf = Quantifact(args.workspace, _user(args.user))
    answers = {"as_of": args.as_of} if args.as_of else None
    plan, planner = qf.build_plan(args.question, answers)
    print(f"as_of {plan.as_of}\n")
    for i, layer in enumerate(
        topo_layers({t.name: list(t.depends_on) for t in plan.tasks})
    ):
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
        metas = [
            m
            for m in metas
            if q in m.series_id.lower()
            or q in m.name.lower()
            or q in m.description.lower()
        ]
    for m in metas[: args.limit]:
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
        print(
            f"{'accept' if h.accepted else 'REJECT'}  {h.meta.series_id:<30} "
            f"score={h.recall_score:5.2f}  {h.meta.frequency} {h.meta.unit}"
        )
        for r in h.reasons:
            print(f"         {r}")
    return 0


def cmd_docs(args) -> int:
    qf = Quantifact(args.workspace, _user(args.user))
    search = getattr(qf.adapter, "search_documents", None)
    if search is None:
        print("this adapter serves no documents")
        return 0
    hits = search(
        args.query, as_of=args.as_of, k=args.k, entitlements=qf.user.entitlements
    )
    print(f"as of {args.as_of}, {len(hits)} of {len(qf.adapter.documents)} documents\n")
    for h in hits:
        print(f"{h.citation()}")
        print(f"   {h.snippet}")
        print(f"   {h.reasons[0]}\n")
    return 0


def cmd_teach(args) -> int:
    from .learn.teach import teach

    ws = Path(args.workspace)
    qf = Quantifact(ws, _user(args.user))
    res = teach(
        args.complaint,
        args.question,
        adapter=qf.adapter,
        repo=LessonRepo(ws / "context" / "lessons"),
        suite=BenchmarkSuite(ws / "benchmarks"),
        entitlements=qf.user.entitlements,
    )
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
    report = suite.report(
        qf.adapter, LessonRepo(ws / "context" / "lessons").all(), qf.user.entitlements
    )
    results = report.results
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
    for family, counts in report.slices("family").items():
        print(f"  family {family:<24} {counts['passed']}/{counts['total']}")
    print(f"silent critical failures: {report.silent_critical_failures}")
    if args.json:
        Path(args.json).write_text(json.dumps(report.to_dict(), indent=2))
        print(f"wrote {args.json}")
    return 1 if failed else 0


def cmd_bench(args) -> int:
    from . import bench

    return bench.main(
        ["--workspace", str(args.workspace)]
        + (["--json", args.json] if args.json else [])
    )


def cmd_audit(args) -> int:
    """Measure maturity without treating repository features as product proof."""
    from .quality import audit, load_evidence

    report = audit(evidence=load_evidence(args.evidence))
    rendered = report.markdown()
    print(rendered, end="")
    if args.out:
        Path(args.out).write_text(rendered)
        print(f"\nwrote {args.out}")
    if args.json:
        Path(args.json).write_text(json.dumps(report.to_dict(), indent=2))
        print(f"wrote {args.json}")
    return 1 if args.strict and report.level != "PAT-level evidence" else 0


def cmd_verify(args) -> int:
    """Verify internal package integrity; this is not publisher authentication."""
    from .evidence import ResearchEvidencePackage

    package = ResearchEvidencePackage.load(args.package)
    problems = package.verify()
    if problems:
        print("INVALID")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(f"VALID       {package.package_id}")
    print(f"as_of       {package.payload['as_of']}")
    print(f"admission   {package.payload['admission']['decision']}")
    print("authenticity not established; verify provenance through a trusted registry")
    print("investment  not approved; expert judgement remains required")
    return 0


def cmd_adapter_check(args) -> int:
    from .data.conformance import check_adapter

    qf = Quantifact(args.workspace, _user(args.user))
    report = check_adapter(
        qf.adapter,
        early_as_of=args.early_as_of,
        late_as_of=args.late_as_of,
        sample_size=args.sample_size,
    )
    for check in report.checks:
        print(f"{'PASS' if check.passed else 'FAIL'}  {check.id:<34} {check.evidence}")
    if args.json:
        Path(args.json).write_text(json.dumps(report.to_dict(), indent=2))
        print(f"wrote {args.json}")
    return 0 if report.passed else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="qf",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
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
    a.add_argument(
        "--evidence",
        help="write the versioned research evidence package (default: beside report)",
    )
    a.add_argument("--no-cache", action="store_true")
    a.add_argument(
        "--execution",
        choices=["in_process", "process"],
        default="in_process",
        help="process contains crashes/timeouts; it is not a no-network sandbox",
    )
    a.add_argument("--task-timeout", type=float, default=30.0)
    a.add_argument("--backend", default="reference", choices=["reference", "llm"])
    a.add_argument("--fix", action="store_true", help="enable the debugger agent")
    a.add_argument("--semantic", action="store_true", help="enable L3 review")
    a.add_argument("--fix-rounds", type=int, default=2)
    a.add_argument("--no-runtime-hint", action="store_true")
    a.add_argument(
        "--planner",
        default="rule",
        choices=["rule", "llm"],
        help="rule: built-in demo planner; llm: model planner over supported ops",
    )
    a.add_argument(
        "--interactive",
        action="store_true",
        help="answer the clarifying questions in the terminal",
    )

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

    dc = sub.add_parser("docs")
    dc.set_defaults(fn=cmd_docs)
    dc.add_argument("query")
    dc.add_argument("--as-of", dest="as_of", default="2026-08-01")
    dc.add_argument("-k", type=int, default=5)

    t = sub.add_parser("teach")
    t.set_defaults(fn=cmd_teach)
    t.add_argument("complaint")
    t.add_argument("--question", default=QUESTION)

    e = sub.add_parser("evals")
    e.set_defaults(fn=cmd_evals)
    e.add_argument("--dir", help="benchmark directory (default: the workspace's)")
    e.add_argument("--json", help="write the sliced machine-readable evaluation")

    b = sub.add_parser("bench")
    b.set_defaults(fn=cmd_bench)
    b.add_argument("--json")

    au = sub.add_parser("audit")
    au.set_defaults(fn=cmd_audit)
    au.add_argument("--evidence", help="versioned operating-evidence JSON")
    au.add_argument("--out", help="write the Markdown audit")
    au.add_argument("--json", help="write the machine-readable audit")
    au.add_argument(
        "--strict",
        action="store_true",
        help="exit non-zero until PAT-level evidence is reached",
    )

    verify = sub.add_parser("verify")
    verify.set_defaults(fn=cmd_verify)
    verify.add_argument("package", help="research evidence package JSON")

    adapter = sub.add_parser("adapter-check")
    adapter.set_defaults(fn=cmd_adapter_check)
    adapter.add_argument("--early-as-of", default="2022-03-01")
    adapter.add_argument("--late-as-of", default="2026-08-01")
    adapter.add_argument("--sample-size", type=int, default=8)
    adapter.add_argument("--json")

    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except Exception as exc:
        # Domain refusals are expected product outcomes. Keep programming bugs
        # noisy, but do not present an unsupported question or failed contract
        # as an internal crash.
        from .contracts.point_in_time import LookAheadError
        from .contracts.verdict import TaskUnfixable
        from .plan.model import PlanError
        from .planner import UnsupportedQuestionError

        if isinstance(
            exc, (UnsupportedQuestionError, LookAheadError, PlanError, TaskUnfixable)
        ):
            print(f"refused: {exc}", file=sys.stderr)
            return 2
        raise


if __name__ == "__main__":
    sys.exit(main())
