"""Inline the measured run data into the blueprint page.

    uv run python tools/export_site_data.py site/data.json
    uv run python tools/build_site.py

The page is a single self-contained file so it can be published as an artifact:
no fetch, no CDN, no external assets.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _summarise_trial(path: Path) -> dict | None:
    """Round-level aggregates only: the page does not need the generated code."""
    if not path.exists():
        return None
    d = json.loads(path.read_text())
    rounds = [
        {
            k: r[k]
            for k in (
                "codegen_seconds",
                "l0_pass",
                "l1_pass",
                "l2_pass",
                "runtime_errors",
                "values_match",
                "fix_rounds",
            )
        }
        for r in d["rounds"]
    ]
    return {
        "model": d["model"],
        "tasks": d["tasks"],
        "fix_enabled": d.get("fix_enabled"),
        "runtime_hint": d.get("runtime_hint"),
        "rounds": rounds,
        "determinism": d.get("determinism"),
        "usage": d.get("usage"),
        "failures": [
            {
                "task": x["task"],
                "l1": x["l1"],
                "l2": x["l2"],
                "error": x["error"],
                "values_match": x["values_match"],
                "problems": (x.get("l1_problems") or x.get("l2_problems") or [])[:1],
            }
            for x in d["rounds"][0]["rows"]
            if not x["values_match"]
        ],
    }


def _collect_llm(root: Path) -> dict:
    """Grading runs live in benchmarks/ so the page and RESULTS.md never drift."""
    bench = root / "benchmarks"
    out = {
        "baseline": _summarise_trial(bench / "llm_trial_baseline.json"),
        "with_debugger": _summarise_trial(bench / "llm_trial.json"),
    }
    run = bench / "llm_run.json"
    if run.exists():
        out["end_to_end"] = json.loads(run.read_text())
    cmp_path = bench / "llm_vs_reference.json"
    if cmp_path.exists():
        out["vs_reference"] = json.loads(cmp_path.read_text())
    return {k: v for k, v in out.items() if v}


def main(
    template: str = "site/template.html",
    data: str = "site/data.json",
    out: str = "site/blueprint.html",
) -> int:
    tpl = (ROOT / template).read_text()
    payload_obj = json.loads((ROOT / data).read_text())
    llm = _collect_llm(ROOT)
    if llm:
        payload_obj["llm"] = llm
    payload = json.dumps(payload_obj, separators=(",", ":"))
    if "__DATA__" not in tpl:
        raise SystemExit("template has no __DATA__ placeholder")
    page = tpl.replace("__DATA__", payload)
    p = ROOT / out
    p.write_text(page)
    print(f"wrote {p} ({p.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
