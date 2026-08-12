"""Prompts and conventions shared by every code-generating backend.

The conventions are not style advice. Each line maps to a check in
``static_analysis.ast_checks``, so a model that ignores one fails the build
rather than producing something plausible.
"""

from __future__ import annotations

from ..plan.model import Task

CONVENTIONS = """\
Coding conventions (enforced by static analysis — violating them fails the build):
- emit exactly one top-level function named after the task
- signature: def <task_name>(<dep1>: pd.DataFrame, ...) -> pd.DataFrame, in the
  exact order the task declares its dependencies
- data may only enter through load_series("<id>") / load_table("<name>")
- never pass arguments other than the identifier to those loaders: the
  knowledge date is fixed by the plan and bound by the harness
- no imports, no file or network IO, no randomness, no current time
- no inplace=True, no chained assignment
- sort explicitly and reset_index(drop=True) so row order is deterministic
- return a dataframe matching the declared columns exactly (names and order)
"""

CODEGEN_PROMPT = """You compile one task of an analysis plan into a single Python function.

{conventions}

TASK
name: {name}
type: {type}
description: {description}
knowledge date (as_of): {as_of} — every input is already filtered to what had
been published by then; never reconstruct or extrapolate beyond it
row grain: {row_expectation}
index columns: {index}
{row_order}
output columns:
{columns}

UPSTREAM DATAFRAMES (already computed, passed as arguments in this order):
{upstream}

{extras}
Return ONLY the function source. No prose, no markdown fence, no imports.
`pd` (pandas), `np` (numpy), `load_series(series_id)` and `load_table(name)` are
already in scope."""


def row_order_line(task: Task) -> str:
    if not task.sort:
        return ""
    parts = ", ".join(f"{c} {'ascending' if a else 'descending'}" for c, a in task.sort)
    return f"required row order (checked after execution): {parts}"


def column_lines(task: Task) -> str:
    out = []
    for c in task.columns:
        bits = [c.dtype]
        if c.unit:
            bits.append(c.unit)
        if c.role:
            bits.append(f"role={c.role}")
        out.append(f"  - {c.name} ({', '.join(bits)}): {c.description}")
    return "\n".join(out)


def upstream_lines(upstream: dict[str, list[dict]]) -> str:
    if not upstream:
        return "  (none)"
    return "\n".join(
        f"  {dep}: " + ", ".join(f"{c['name']}:{c['dtype']}" for c in schema)
        for dep, schema in upstream.items()
    )
