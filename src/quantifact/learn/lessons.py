"""Lessons: the context repository, written by domain experts.

A lesson is plain Markdown with a small structured header so a human and the
planner can both read it. The header is what makes a lesson verifiable: it
names an *effect* the planner understands and a feature flag that must hold.
A lesson that maps to no effect is prose that changes nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

HEADER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.S)


@dataclass
class Lesson:
    id: str
    effect: str  # machine-readable hook the planner checks
    when: str | None  # feature flag that must hold, e.g. multi_episode
    text: str  # the human-readable lesson
    origin: str = "teach"

    def to_markdown(self) -> str:
        head = {
            "id": self.id,
            "effect": self.effect,
            "when": self.when or "",
            "origin": self.origin,
        }
        lines = "\n".join(f"{k}: {v}" for k, v in head.items())
        return f"---\n{lines}\n---\n{self.text.strip()}\n"

    @staticmethod
    def from_markdown(src: str) -> Lesson:
        m = HEADER_RE.match(src)
        if not m:
            raise ValueError("lesson file has no header block")
        head = {
            k.strip(): v.strip()
            for k, v in (
                line.split(":", 1) for line in m.group(1).splitlines() if ":" in line
            )
        }
        return Lesson(
            id=head["id"],
            effect=head["effect"],
            when=head.get("when") or None,
            text=m.group(2).strip(),
            origin=head.get("origin", "teach"),
        )


class LessonRepo:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def all(self) -> list[Lesson]:
        return [
            Lesson.from_markdown(p.read_text()) for p in sorted(self.root.glob("*.md"))
        ]

    def add(self, lesson: Lesson) -> Path:
        p = self.root / f"{lesson.id}.md"
        p.write_text(lesson.to_markdown())
        return p

    def remove(self, lesson_id: str) -> None:
        (self.root / f"{lesson_id}.md").unlink(missing_ok=True)
