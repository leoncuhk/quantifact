"""Layered validation. Cheap and deterministic first, model last.

  L0 static     one function, right signature, no IO, no clock, no randomness
  L1 schema     declared columns, dtypes, nullability, declared row order
  L1 pit        no observation later than the knowledge date
  L2 invariants non-null ratios, ranges, uniqueness, row counts, sums
  L3 semantic   does the code do what the task says            (model, optional)
  L4 review     are the resulting numbers plausible            (see review/)

L0 to L2 are ordinary Python and run unconditionally. That is the point: a
model cannot skip a check it finds inconvenient, and the expensive layers only
ever see code that already passes the cheap ones.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from ..plan.model import AnalysisPlan, Task
from ..static_analysis.ast_checks import CodeFacts, analyse
from .point_in_time import no_future_observations
from .verdict import TaskUnfixable, Verdict

DTYPE_CHECK = {
    "float64": pd.api.types.is_float_dtype,
    "int64": pd.api.types.is_integer_dtype,
    "bool": pd.api.types.is_bool_dtype,
    "datetime64[ns]": pd.api.types.is_datetime64_any_dtype,
}


# ---------------------------------------------------------------- L0 static


def l0_static(task: Task, source: str, facts: CodeFacts | None = None) -> Verdict:
    facts = facts or analyse(task.name, source)
    problems = list(facts.violations)
    if set(facts.params) != set(task.depends_on):
        problems.append(
            f"signature {facts.params} does not match declared "
            f"dependencies {task.depends_on}"
        )
    if task.series_inputs and facts.series_ids:
        undeclared = set(facts.series_ids) - set(task.series_inputs)
        if undeclared:
            problems.append(f"loads undeclared series {sorted(undeclared)}")
    return Verdict(task.name, "L0-static", not problems, problems)


def validate_static(
    plan: AnalysisPlan, codes: dict[str, str], facts: dict[str, CodeFacts] | None = None
) -> list[Verdict]:
    return [l0_static(t, codes[t.name], (facts or {}).get(t.name)) for t in plan.tasks]


# ---------------------------------------------------------------- L1 schema


def l1_schema(task: Task, df: pd.DataFrame) -> Verdict:
    problems: list[str] = []
    want = task.column_names
    if list(df.columns) != want:
        missing = [c for c in want if c not in df.columns]
        extra = [c for c in df.columns if c not in want]
        if missing:
            problems.append(f"missing columns {missing}")
        if extra:
            problems.append(f"unexpected columns {extra}")
        if not missing and not extra:
            problems.append(f"column order {list(df.columns)} != declared {want}")

    for spec in task.columns:
        if spec.name not in df.columns:
            continue
        col = df[spec.name]
        check = DTYPE_CHECK.get(spec.dtype)
        if check and not check(col):
            problems.append(
                f"column '{spec.name}' has dtype {col.dtype}, declared {spec.dtype}"
            )
        if not spec.nullable and col.isna().any():
            problems.append(
                f"column '{spec.name}' declared non-nullable but has "
                f"{int(col.isna().sum())} nulls"
            )
    if df.empty:
        problems.append("dataframe is empty")

    if task.sort and not problems:
        cols = [c for c, _ in task.sort]
        asc = [bool(a) for _, a in task.sort]
        if all(c in df.columns for c in cols):
            want_order = df.sort_values(cols, ascending=asc, kind="stable")
            if not df.reset_index(drop=True).equals(want_order.reset_index(drop=True)):
                problems.append(f"rows are not ordered by declared sort {task.sort}")
    return Verdict(task.name, "L1-schema", not problems, problems)


# ------------------------------------------------------------ L2 invariants


def l2_invariants(
    task: Task, df: pd.DataFrame, as_of: str | date | None = None
) -> Verdict:
    problems: list[str] = []
    for inv in task.invariants:
        kind = inv["kind"]
        if kind == "nonnull":
            col = inv["column"]
            if col in df.columns:
                ratio = float(df[col].notna().mean()) if len(df) else 0.0
                if ratio < inv.get("min", 1.0):
                    problems.append(
                        f"non-null ratio of '{col}' is {ratio:.3f} < {inv['min']}"
                    )
        elif kind == "range":
            col = inv["column"]
            if col in df.columns and len(df):
                lo, hi = inv.get("min", -float("inf")), inv.get("max", float("inf"))
                bad = int(((df[col] < lo) | (df[col] > hi)).sum())
                if bad:
                    problems.append(
                        f"{bad} rows of '{col}' outside [{lo}, {hi}] "
                        f"(observed {df[col].min():.4g}..{df[col].max():.4g})"
                    )
        elif kind == "row_count":
            n = len(df)
            if n < inv.get("min", 0) or n > inv.get("max", 10**12):
                problems.append(
                    f"row count {n} outside [{inv.get('min', 0)}, {inv.get('max', '∞')}]"
                )
        elif kind == "unique":
            cols = inv["columns"]
            if all(c in df.columns for c in cols):
                dupes = int(df.duplicated(subset=cols).sum())
                if dupes:
                    problems.append(f"{dupes} duplicate rows on {cols}")
        elif kind == "sum_to":
            col, target = inv["column"], inv["value"]
            if col in df.columns:
                got = float(df[col].sum())
                if abs(got - target) > inv.get("tol", 1e-6):
                    problems.append(f"sum of '{col}' is {got:.6g}, expected {target}")
        elif kind == "no_future_observations" and as_of is not None:
            v = no_future_observations(task, df, as_of)
            problems.extend(v.problems)
    return Verdict(task.name, "L2-invariants", not problems, problems)


def validate_result(
    task: Task, df: pd.DataFrame, as_of: str | date | None = None
) -> list[Verdict]:
    """L1 + L1-pit + L2 for one materialised frame."""
    out = [l1_schema(task, df)]
    if as_of is not None:
        out.append(no_future_observations(task, df, as_of))
    out.append(l2_invariants(task, df, as_of))
    return out


__all__ = [
    "DTYPE_CHECK",
    "TaskUnfixable",
    "Verdict",
    "l0_static",
    "l1_schema",
    "l2_invariants",
    "no_future_observations",
    "validate_result",
    "validate_static",
]
