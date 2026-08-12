"""The whole pipeline in one file, on synthetic data.

    uv run python examples/01_quickstart/run.py
"""

from __future__ import annotations

from pathlib import Path

from quantifact import Quantifact

WS = Path(".qf-quickstart")
QUESTION = ("How have markets responded to the conflict in the Middle East and the "
            "resulting oil supply shortage, and how does today compare to similar "
            "historical episodes?")


def main() -> int:
    qf = Quantifact(WS)

    print("clarifying questions the planner would ask:")
    for c in qf.clarify(QUESTION):
        recommended = next(o["label"] for o in c.options if o.get("recommended"))
        print(f"  · {c.question}\n      recommended: {recommended}")

    print("\nfirst run (cold cache)")
    art = qf.analyse(QUESTION, out=WS / "report.html",
                     on_stage=lambda n, s: print(f"  {n:<10}{s * 1000:8.1f} ms"))
    print(f"  {len(art.plan.tasks)} tasks in {len(art.layers)} layers, "
          f"{sum(1 for v in art.verdicts if v.ok)}/{len(art.verdicts)} verdicts passed")

    print("\nsecond run (nothing changed)")
    again = qf.analyse(QUESTION, out=WS / "report.html")
    print(f"  {again.result.cache_hits}/{len(again.result.traces)} tasks served "
          f"from cache in {again.result.wall_seconds * 1000:.0f} ms")
    print(f"\nreport: {again.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
