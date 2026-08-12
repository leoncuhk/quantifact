"""The analysis plan: quantifact's intermediate representation.

A plan is not a to-do list. It is a *natural-language Python project*: every
task declares the dataframe it produces — index, columns with dtype, unit and
semantic role, row grain, row order and invariants — plus the tasks it
consumes. That level of detail is what makes parallel code generation, layered
validation and content-addressed caching possible downstream.

Two fields carry the finance-specific weight:

``AnalysisPlan.as_of``
    The knowledge date of the whole analysis. Everything the plan may read had
    to be *published* on or before this date. It is required, not optional:
    an analysis without a knowledge date cannot be checked for look-ahead, and
    an unchecked analysis of the past is worth nothing.

``ColumnSpec.role``
    What a column *is* — an observation date, a publication date, an entity
    key, a dimension or a measure. Roles are what let the contract layer say
    "no observation in this frame may post-date the knowledge date" without
    guessing from column names.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

TaskType = Literal["data_ingestion", "table_logic", "chart"]
ColumnRole = Literal[
    "observation_date", "publication_date", "entity", "dimension", "measure"
]

ALLOWED_DTYPES = {
    "float64",
    "int64",
    "bool",
    "string",
    "category",
    "datetime64[ns]",
}
ALLOWED_ROLES = {"observation_date", "publication_date", "entity", "dimension", "measure"}


@dataclass
class ResearchClaim:
    """A conclusion the analysis is allowed to support, declared before execution."""

    id: str
    statement: str
    kind: Literal["descriptive", "associational", "causal", "predictive"]
    evidence_tasks: list[str]
    falsifiers: list[str]

    @staticmethod
    def from_dict(d: dict[str, Any]) -> ResearchClaim:
        return ResearchClaim(**d)


@dataclass
class AlternativeExplanation:
    """A rival account and the planned evidence that could distinguish it."""

    id: str
    statement: str
    discriminating_tasks: list[str]

    @staticmethod
    def from_dict(d: dict[str, Any]) -> AlternativeExplanation:
        return AlternativeExplanation(**d)


@dataclass
class ResearchDesign:
    """Critical-thinking contract: what may be inferred, and what could defeat it.

    This is deliberately part of the plan rather than prose generated after the
    results are known.  It makes rival explanations and falsification criteria
    reviewable before code generation, when changing the research design is cheap.
    """

    question_type: Literal["descriptive", "comparative", "causal", "predictive"]
    decision_context: str
    claims: list[ResearchClaim]
    alternatives: list[AlternativeExplanation]
    limitations: list[str]
    identification_strategy: str | None = None
    out_of_sample_test: str | None = None

    @staticmethod
    def from_dict(d: dict[str, Any]) -> ResearchDesign:
        d = dict(d)
        d["claims"] = [ResearchClaim.from_dict(x) for x in d.get("claims", [])]
        d["alternatives"] = [
            AlternativeExplanation.from_dict(x) for x in d.get("alternatives", [])
        ]
        return ResearchDesign(**d)


class PlanError(Exception):
    """Raised when a plan fails compile-time validation."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("plan failed validation:\n  - " + "\n  - ".join(problems))


def parse_date(value: str | date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


@dataclass
class ColumnSpec:
    name: str
    description: str
    dtype: str = "float64"
    unit: str | None = None
    role: ColumnRole | None = None
    nullable: bool = False

    @staticmethod
    def from_dict(d: dict[str, Any]) -> ColumnSpec:
        return ColumnSpec(**d)


@dataclass
class Task:
    """One task == one Python function == one dataframe.

    Deliberately shaped like a function *type signature*: inputs
    (``depends_on``, ``series_inputs``), output shape (``index``, ``columns``,
    ``row_expectation``, ``sort``) and output contract (``invariants``).
    """

    name: str
    type: TaskType
    description: str
    columns: list[ColumnSpec]
    index: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    series_inputs: list[str] = field(default_factory=list)
    row_expectation: str | None = None
    # [[column, ascending], ...] — presentation order is part of the contract,
    # not a detail left to whoever writes the code.
    sort: list[list] | None = None
    invariants: list[dict[str, Any]] = field(default_factory=list)
    chart_spec: dict[str, Any] | None = None
    # Structured operation hint. The reference backend compiles it directly;
    # the LLM backend treats it as a hint alongside the description.
    op: dict[str, Any] | None = None

    @property
    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]

    def column(self, name: str) -> ColumnSpec | None:
        return next((c for c in self.columns if c.name == name), None)

    def columns_with_role(self, role: ColumnRole) -> list[ColumnSpec]:
        return [c for c in self.columns if c.role == role]

    @staticmethod
    def from_dict(d: dict[str, Any]) -> Task:
        d = dict(d)
        d["columns"] = [ColumnSpec.from_dict(c) for c in d.get("columns", [])]
        return Task(**d)


@dataclass
class AnalysisPlan:
    question: str
    tasks: list[Task]
    # Knowledge date: nothing published after this may enter the analysis.
    as_of: str = ""
    resolved_assumptions: list[str] = field(default_factory=list)
    research_design: ResearchDesign | None = None

    # ---------------------------------------------------------------- lookup
    def __getitem__(self, name: str) -> Task:
        t = self.task(name)
        if t is None:
            raise KeyError(name)
        return t

    def task(self, name: str) -> Task | None:
        return next((t for t in self.tasks if t.name == name), None)

    @property
    def names(self) -> list[str]:
        return [t.name for t in self.tasks]

    @property
    def as_of_date(self) -> date:
        return parse_date(self.as_of)

    def charts(self) -> list[Task]:
        return [t for t in self.tasks if t.type == "chart"]

    def series_inputs(self) -> list[str]:
        return sorted({s for t in self.tasks for s in t.series_inputs})

    # ------------------------------------------------------------- (de)serde
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, path: str | Path) -> Path:
        p = Path(path)
        p.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False))
        return p

    @staticmethod
    def from_dict(d: dict[str, Any]) -> AnalysisPlan:
        return AnalysisPlan(
            question=d["question"],
            tasks=[Task.from_dict(t) for t in d["tasks"]],
            as_of=d.get("as_of", ""),
            resolved_assumptions=list(d.get("resolved_assumptions", [])),
            research_design=(
                ResearchDesign.from_dict(d["research_design"])
                if d.get("research_design")
                else None
            ),
        )

    @staticmethod
    def load(path: str | Path) -> AnalysisPlan:
        return AnalysisPlan.from_dict(json.loads(Path(path).read_text()))
