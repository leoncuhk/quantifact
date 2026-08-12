"""Diff the charts of two reports: LLM-written code vs the deterministic oracle.

    uv run python tools/compare_reports.py llm-report.html reference-report.html \
        benchmarks/llm_vs_reference.json
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

import pandas as pd

PATTERN = (r'task, code and data — (\w+)</summary><pre>(.*?)</pre>'
           r'<pre id="csv\d+"[^>]*>(.*?)</pre>')
ENTITIES = [("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&#x27;", "'"),
            ("&quot;", '"')]


def charts(path: str) -> dict[str, pd.DataFrame]:
    html = Path(path).read_text()
    out = {}
    for m in re.finditer(PATTERN, html, re.S):
        csv = m.group(3)
        for a, b in ENTITIES:
            csv = csv.replace(a, b)
        out[m.group(1)] = pd.read_csv(io.StringIO(csv))
    return out


def main(llm: str, ref: str, out: str = "site/llm_vs_reference.json") -> int:
    a, b = charts(llm), charts(ref)
    rows = []
    for name, y in b.items():
        x = a.get(name)
        if x is None:
            rows.append({"chart": name, "status": "missing"})
            continue
        same_shape = x.shape == y.shape and list(x.columns) == list(y.columns)
        num = [c for c in y.columns if pd.api.types.is_numeric_dtype(y[c])]
        diff = None
        if same_shape and num:
            diff = float((x[num].astype(float) - y[num].astype(float)).abs().max().max())
        rows.append({
            "chart": name, "llm_rows": len(x), "reference_rows": len(y),
            "identical": bool(x.equals(y)),
            "max_abs_diff": diff,
            "status": ("identical" if x.equals(y)
                       else "equal within float epsilon" if diff is not None and diff < 1e-9
                       else "differs"),
        })
    Path(out).write_text(json.dumps(rows, indent=1))
    for r in rows:
        print(f"{r['chart']:<32} {r.get('status')}  rows {r.get('llm_rows')} vs "
              f"{r.get('reference_rows')}  max|diff| {r.get('max_abs_diff')}")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:]))
