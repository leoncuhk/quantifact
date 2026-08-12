"""A latency-simulating backend.

Not a model. It exists so the structural claim — codegen wall time is set by
the slowest single task, not by how many there are — can be measured without
spending real calls to show it. Every number produced with it is labelled a
simulation wherever it appears.
"""

from __future__ import annotations

import time

from ..plan.model import Task
from .base import CodegenBackend
from .reference import ReferenceCodegen


class SimulatedLatencyCodegen:
    def __init__(self, seconds: float = 0.4, inner: CodegenBackend | None = None):
        self.seconds = seconds
        self.inner = inner or ReferenceCodegen()
        self.name = f"simulated({seconds}s/task)"

    def generate(
        self, task: Task, upstream: dict[str, list[dict]], as_of: str = ""
    ) -> str:
        time.sleep(self.seconds)
        return self.inner.generate(task, upstream, as_of)
