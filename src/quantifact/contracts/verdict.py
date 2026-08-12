"""The verdict type shared by every contract layer."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Verdict:
    task: str
    layer: str
    ok: bool
    problems: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.ok

    def __str__(self) -> str:
        if self.ok:
            return f"[{self.layer}] {self.task}: ok"
        return f"[{self.layer}] {self.task}: " + "; ".join(self.problems)


class TaskUnfixable(RuntimeError):
    """A task failed a layer and the repair budget is exhausted.

    Raised rather than degraded on purpose: an analysis that cannot satisfy its
    own contract must stop with a name attached, not ship a chart nobody can
    defend.
    """

    def __init__(self, verdict: Verdict):
        self.verdict = verdict
        super().__init__(str(verdict))
