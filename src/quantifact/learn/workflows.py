"""Workflow guides — context that reads like a procedure, not a pile of facts.

Domain context alone produces an agent that knows a great deal and still has to
be told what to do. A guide is the other half: for *this shape of question*,
here are the steps, in order, with the trap at each one named. It is the
difference between a system that can answer and a system you can depend on.

Guides ship with the package and can be overridden or extended per workspace,
because the useful ones are written by the people who do the work — the same
argument as for lessons, one level up.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

PACKAGED = Path(__file__).resolve().parent.parent / "context" / "workflows"
HEADER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.S)


@dataclass
class Workflow:
    id: str
    applies_to: str
    text: str
    source: str = "packaged"

    @staticmethod
    def from_markdown(src: str, source: str = "packaged") -> Workflow:
        m = HEADER_RE.match(src)
        if not m:
            raise ValueError("workflow file has no header block")
        head = {
            k.strip(): v.strip()
            for k, v in (
                line.split(":", 1) for line in m.group(1).splitlines() if ":" in line
            )
        }
        return Workflow(
            id=head.get("id", "unnamed"),
            applies_to=head.get("applies_to", ""),
            text=m.group(2).strip(),
            source=source,
        )


class WorkflowRepo:
    """Packaged guides plus anything in the workspace, workspace winning."""

    def __init__(self, root: str | Path | None = None):
        self.root = Path(root) if root else None
        if self.root:
            self.root.mkdir(parents=True, exist_ok=True)

    def all(self) -> list[Workflow]:
        out: dict[str, Workflow] = {}
        for path in sorted(PACKAGED.glob("*.md")):
            out[path.stem] = Workflow.from_markdown(path.read_text(), "packaged")
        if self.root:
            for path in sorted(self.root.glob("*.md")):
                out[path.stem] = Workflow.from_markdown(path.read_text(), "workspace")
        return [out[k] for k in sorted(out)]

    def matching(self, prompt: str, limit: int = 2) -> list[Workflow]:
        """Cheap relevance: shared words between the question and `applies_to`."""
        words = set(re.findall(r"[a-z]{4,}", prompt.lower()))
        scored = [
            (len(words & set(re.findall(r"[a-z]{4,}", w.applies_to.lower()))), w)
            for w in self.all()
        ]
        scored.sort(key=lambda pair: -pair[0])
        return [w for score, w in scored[:limit] if score > 0] or self.all()[:1]
