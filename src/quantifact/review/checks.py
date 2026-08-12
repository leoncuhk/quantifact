"""Self review (L4): the "check your work before coming back to me" pass.

Deterministic plausibility checks over the materialised frames. Findings are
severity-tagged; `blocking` findings send the analysis back into the fix loop,
the rest are surfaced in the report so the human can see what the agent noticed.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..plan.model import AnalysisPlan, Task


@dataclass
class Finding:
    task: str
    severity: str          # blocking | warning | note
    message: str


def _numeric_columns(task: Task, df: pd.DataFrame) -> list[str]:
    return [c.name for c in task.columns
            if c.dtype in ("float64", "int64") and c.name in df.columns
            and c.name not in task.index]


def review_frame(task: Task, df: pd.DataFrame) -> list[Finding]:
    out: list[Finding] = []
    if df.empty:
        return [Finding(task.name, "blocking", "produced zero rows")]

    for col in _numeric_columns(task, df):
        s = pd.to_numeric(df[col], errors="coerce")
        v = s.dropna()
        if v.empty:
            out.append(Finding(task.name, "blocking", f"'{col}' is entirely null"))
            continue
        if v.nunique() == 1 and len(v) > 3:
            # a wide, entirely constant analytic column is not a style issue:
            # it is almost always a join or pivot that silently matched nothing
            severity = "blocking" if (len(v) > 20 and task.type != "data_ingestion") \
                else "warning"
            out.append(Finding(task.name, severity,
                               f"'{col}' is constant at {v.iloc[0]:.6g} across "
                               f"{len(v)} rows — check the computation"))
        if np.isinf(v).any():
            out.append(Finding(task.name, "blocking", f"'{col}' contains infinities"))
        # Outlier screen on the median/MAD, and never on level series: a total
        # return index compounds, so "10 sigma from the mean" is its normal
        # behaviour, not a defect.
        spec = task.column(col)
        if (spec.unit or "") not in ("index", "notional") and len(v) > 8:
            med = float(v.median())
            mad = float((v - med).abs().median())
            if mad > 0:
                z = (v - med).abs() / (1.4826 * mad)
                extreme = int((z > 12).sum())
                if extreme:
                    out.append(Finding(task.name, "warning",
                                       f"'{col}' has {extreme} value(s) beyond 12 "
                                       f"robust sigma (worst {float(v[z.idxmax()]):.6g})"))
        null_ratio = float(s.isna().mean())
        if 0 < null_ratio <= 0.5:
            out.append(Finding(task.name, "note",
                               f"'{col}' is {null_ratio:.0%} null"))
        elif null_ratio > 0.5:
            out.append(Finding(task.name, "blocking",
                               f"'{col}' is {null_ratio:.0%} null"))

    if task.index and all(c in df.columns for c in task.index):
        dupes = int(df.duplicated(subset=task.index).sum())
        if dupes:
            out.append(Finding(task.name, "blocking",
                               f"{dupes} duplicate rows on index {task.index}"))

    if task.type == "chart":
        spec = task.chart_spec or {}
        if spec.get("kind") in ("line", "scatter") and len(df) < 2:
            out.append(Finding(task.name, "blocking",
                               f"{spec['kind']} chart with {len(df)} point(s)"))
        facet = spec.get("facet")
        if facet and facet in df.columns:
            small = df.groupby(facet).size()
            thin = small[small < 2]
            if len(thin):
                out.append(Finding(task.name, "warning",
                                   f"facets with a single point: {list(thin.index)[:5]}"))
    return out


def review(plan: AnalysisPlan, frames: dict[str, pd.DataFrame]) -> list[Finding]:
    findings: list[Finding] = []
    for task in plan.tasks:
        if task.name in frames:
            findings.extend(review_frame(task, frames[task.name]))
    return findings


def blocking(findings: list[Finding]) -> list[Finding]:
    return [f for f in findings if f.severity == "blocking"]
