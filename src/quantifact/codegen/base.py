"""Codegen driver: one call per task, all tasks in flight at once.

The fan-out works because a task needs only the *schemas* of the frames it
consumes, never their generated code. A chart at the end of the plan can
therefore be compiled at the same instant as the ingestion at the front, and
wall time is set by the slowest single task rather than by their number.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Protocol

from ..plan.model import AnalysisPlan, Task


class CodegenBackend(Protocol):
    """Anything that can turn a task into one Python function."""

    name: str

    def generate(self, task: Task, upstream: dict[str, list[dict]],
                 as_of: str = "") -> str: ...


def schemas_of(plan: AnalysisPlan, task: Task) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for dep in task.depends_on:
        t = plan[dep]
        out[dep] = [{"name": c.name, "dtype": c.dtype, "unit": c.unit,
                     "role": c.role, "description": c.description}
                    for c in t.columns]
    return out


def generate_all(plan: AnalysisPlan, backend: CodegenBackend,
                 max_workers: int = 16) -> dict[str, str]:
    def one(task: Task) -> tuple[str, str]:
        return task.name, backend.generate(task, schemas_of(plan, task), plan.as_of)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        return dict(pool.map(one, plan.tasks))


def generate_serially(plan: AnalysisPlan, backend: CodegenBackend) -> dict[str, str]:
    """Only used to measure what the parallelism buys."""
    return {t.name: backend.generate(t, schemas_of(plan, t), plan.as_of)
            for t in plan.tasks}
