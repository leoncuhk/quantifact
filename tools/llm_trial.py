"""Run the real pipeline with an LLM writing the code, and grade it.

The reference backend is the oracle: for every task we ask whether the model's
free-form pandas passes each validation layer and whether it produces the same
values as the deterministic compiler. That is the honest version of the talk's
"two LLMs on the same task should produce semantically equivalent code".

    QF_LLM_API_KEY=... uv run python tools/llm_trial.py --rounds 2 --fix

Writes benchmarks/llm_trial.json, which benchmarks/RESULTS.md reports.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import pandas as pd

from quantifact import ANALYST, Quantifact, ReferenceCodegen
from quantifact.codegen.base import generate_all, schemas_of
from quantifact.codegen.openai_compat import (
    LLMClient,
    OpenAICompatCodegen,
    OpenAICompatDebugger,
)
from quantifact.contracts.layers import l0_static, l1_schema, l2_invariants
from quantifact.harness.cache import ValueCache
from quantifact.harness.execute import ExecutionHarness
from quantifact.review.checks import review_frame
from quantifact.staticanalysis.ast_checks import analyse

QUESTION = ("How have markets responded to the conflict in the Middle East and the "
            "resulting oil supply shortage, and how does today compare to similar "
            "historical episodes?")


def frame_hash(df: pd.DataFrame) -> str:
    h = hashlib.sha256()
    h.update(pd.util.hash_pandas_object(df.round(10), index=False).to_numpy().tobytes())
    return h.hexdigest()[:16]


def grade(pa, plan, codes, oracle_frames, label, debugger=None, max_fix=1):
    """Run every task, layer by layer, and grade it against the oracle."""
    harness = ExecutionHarness(pa.adapter, ValueCache(pa.ws / f"cache-{label}",
                                                      enabled=False))
    frames: dict[str, pd.DataFrame] = {}
    rows = []
    for layer in plan_layers(plan):
        for name in layer:
            task = plan[name]
            row = {"task": name, "type": task.type, "fix_rounds": 0,
                   "l0": None, "l1": None, "l2": None, "review": None,
                   "values_match": None, "error": None,
                   "chars": len(codes[name])}
            for attempt in range(max_fix + 1):
                facts = analyse(name, codes[name])
                v0 = l0_static(task, codes[name], facts)
                row["l0"] = v0.ok
                row["l0_problems"] = v0.problems
                if not v0.ok:
                    if debugger and attempt < max_fix:
                        codes[name] = debugger.edit(task, codes[name], v0,
                                                    upstream=schemas_of(plan, task))
                        row["fix_rounds"] += 1
                        continue
                    break
                try:
                    single = harness.run_one(task, codes[name], frames, plan.as_of)
                except Exception as e:                       # runtime failure
                    row["error"] = f"{type(e).__name__}: {e}"
                    if debugger and attempt < max_fix:
                        from quantifact.contracts.verdict import Verdict
                        codes[name] = debugger.edit(
                            task, codes[name],
                            Verdict(name, "runtime", False, [row["error"]]),
                            upstream=schemas_of(plan, task))
                        row["fix_rounds"] += 1
                        continue
                    break
                v1 = l1_schema(task, single)
                v2 = l2_invariants(task, single, plan.as_of)
                row["l1"], row["l1_problems"] = v1.ok, v1.problems
                row["l2"], row["l2_problems"] = v2.ok, v2.problems
                if not (v1.ok and v2.ok) and debugger and attempt < max_fix:
                    codes[name] = debugger.edit(task, codes[name], v1 if not v1.ok else v2,
                                                upstream=schemas_of(plan, task))
                    row["fix_rounds"] += 1
                    continue
                frames[name] = single
                row["rows"] = len(single)
                row["values_hash"] = frame_hash(single)
                row["review"] = [f.severity for f in review_frame(task, single)]
                oracle = oracle_frames[name]
                row["values_match"] = (
                    len(single) == len(oracle)
                    and list(single.columns) == list(oracle.columns)
                    and frame_hash(single) == frame_hash(oracle))
                break
            if name not in frames:
                # downstream tasks cannot run without this frame; use the oracle
                # so the rest of the plan is still graded
                frames[name] = oracle_frames[name]
                row["substituted_oracle"] = True
            rows.append(row)
    return rows, codes


def plan_layers(plan):
    from quantifact.plan.layers import topo_layers
    return topo_layers({t.name: list(t.depends_on) for t in plan.tasks})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=2,
                    help="independent codegen rounds, for determinism")
    ap.add_argument("--workspace", default=".qf-llm")
    ap.add_argument("--fix", action="store_true", help="enable the debugger agent")
    ap.add_argument("--out", default="benchmarks/llm_trial.json")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--runtime-hint", action="store_true",
                    help="tell the model which pandas/numpy it is compiling for")
    args = ap.parse_args()

    qf = Quantifact(args.workspace, ANALYST)
    plan, _ = qf.build_plan(QUESTION)

    # oracle: deterministic compiler
    ref_codes = generate_all(plan, ReferenceCodegen())
    oracle = ExecutionHarness(qf.adapter,
                              ValueCache(qf.ws / "cache-ref", enabled=False)).run(plan, ref_codes)

    client = LLMClient()
    from quantifact.harness.cache import RUNTIME_ID
    backend = OpenAICompatCodegen(
        client, runtime_hint=RUNTIME_ID if args.runtime_hint else None)
    debugger = OpenAICompatDebugger(client) if args.fix else None

    result = {"model": client.model, "base_url": client.base_url,
              "tasks": len(plan.tasks), "rounds": [], "fix_enabled": bool(args.fix),
              "runtime_hint": bool(args.runtime_hint)}
    round_codes = []
    for r in range(args.rounds):
        t0 = time.perf_counter()
        codes = generate_all(plan, backend, max_workers=args.workers)
        gen_seconds = time.perf_counter() - t0
        rows, codes = grade(qf, plan, dict(codes), oracle.frames, f"r{r}", debugger)
        round_codes.append(codes)
        ok = [x for x in rows if x["values_match"]]
        result["rounds"].append({
            "round": r, "codegen_seconds": gen_seconds, "rows": rows,
            "l0_pass": sum(1 for x in rows if x["l0"]),
            "l1_pass": sum(1 for x in rows if x["l1"]),
            "l2_pass": sum(1 for x in rows if x["l2"]),
            "runtime_errors": sum(1 for x in rows if x["error"]),
            "values_match": len(ok),
            "fix_rounds": sum(x["fix_rounds"] for x in rows),
        })
        print(f"round {r}: codegen {gen_seconds:.1f}s  "
              f"L0 {result['rounds'][-1]['l0_pass']}/{len(rows)}  "
              f"L1 {result['rounds'][-1]['l1_pass']}/{len(rows)}  "
              f"L2 {result['rounds'][-1]['l2_pass']}/{len(rows)}  "
              f"values match {len(ok)}/{len(rows)}", flush=True)

    if len(round_codes) > 1:
        a, b = round_codes[0], round_codes[1]
        h0 = {x["task"]: x.get("values_hash") for x in result["rounds"][0]["rows"]}
        h1 = {x["task"]: x.get("values_hash") for x in result["rounds"][1]["rows"]}
        result["determinism"] = {
            "identical_code": sum(1 for k in a if a[k] == b[k]),
            # the metric that matters: same task compiled twice, same values out
            "identical_values_round_to_round": sum(
                1 for k in h0 if h0[k] is not None and h0[k] == h1.get(k)),
            "matched_oracle_both_rounds": sum(
                1 for k in a
                if next(x for x in result["rounds"][0]["rows"] if x["task"] == k)["values_match"]
                and next(x for x in result["rounds"][1]["rows"] if x["task"] == k)["values_match"]),
            "tasks": len(a),
        }
    u = client.usage
    result["usage"] = {"calls": u.calls, "retries": u.retries,
                       "prompt_tokens": u.prompt_tokens,
                       "completion_tokens": u.completion_tokens,
                       "seconds": u.seconds,
                       "slowest_call": max(u.per_call or [0]),
                       "median_call": sorted(u.per_call)[len(u.per_call) // 2] if u.per_call else 0}
    result["samples"] = {k: round_codes[0][k] for k in list(round_codes[0])[:40]}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=1))
    print(f"\nwrote {args.out}")
    print(json.dumps({k: v for k, v in result.items()
                      if k in ("determinism", "usage")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
