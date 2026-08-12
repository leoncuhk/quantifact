"""Evidence-backed maturity audit for a PAT-style research agent.

Feature checklists are easy to game: a toy document index and a production
research corpus both make ``has_document_search`` true.  This module therefore
separates three things:

* repository evidence -- what the implementation can prove by inspecting and
  exercising itself;
* operating evidence -- measurements that only a real deployment can supply;
* gates -- minimum outcomes that a high total score is not allowed to hide.

The score is a navigation aid.  The gates decide whether the system may claim
research-grade or PAT-level maturity.
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Criterion:
    id: str
    dimension: str
    weight: int
    target: str
    source: str = "automatic"  # automatic | operating
    critical: bool = False


@dataclass
class Result:
    criterion: Criterion
    score: float
    evidence: str
    gap: str = ""

    @property
    def points(self) -> float:
        return self.criterion.weight * max(0.0, min(1.0, self.score))


@dataclass
class AuditReport:
    results: list[Result]
    blockers: list[str] = field(default_factory=list)

    @property
    def score(self) -> float:
        possible = sum(r.criterion.weight for r in self.results)
        return 100 * sum(r.points for r in self.results) / possible

    @property
    def dimensions(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for dimension in sorted({r.criterion.dimension for r in self.results}):
            rows = [r for r in self.results if r.criterion.dimension == dimension]
            out[dimension] = (
                100 * sum(r.points for r in rows) / sum(r.criterion.weight for r in rows)
            )
        return out

    @property
    def level(self) -> str:
        dims = self.dimensions
        critical = [r for r in self.results if r.criterion.critical]
        if (
            not self.blockers
            and self.score >= 90
            and min(dims.values(), default=0) >= 80
            and all(r.score >= 0.8 for r in critical)
        ):
            return "PAT-level evidence"
        if self.score >= 70 and all(r.score >= 0.5 for r in critical):
            return "research-grade candidate"
        if self.score >= 45:
            return "validated architecture prototype"
        return "concept prototype"

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 1),
            "level": self.level,
            "dimensions": {k: round(v, 1) for k, v in self.dimensions.items()},
            "blockers": self.blockers,
            "criteria": [
                {
                    **asdict(r.criterion),
                    "score": r.score,
                    "points": round(r.points, 2),
                    "evidence": r.evidence,
                    "gap": r.gap,
                }
                for r in self.results
            ],
        }

    def markdown(self) -> str:
        lines = [
            "# quantifact quality audit\n",
            f"**{self.score:.1f}/100 — {self.level}**\n",
            "## Dimensions\n",
            "| dimension | score |",
            "|---|---:|",
        ]
        lines += [f"| {k} | {v:.1f} |" for k, v in self.dimensions.items()]
        lines += [
            "\n## Evidence\n",
            "| criterion | source | score | evidence / next gap |",
            "|---|---|---:|---|",
        ]
        for r in self.results:
            detail = r.evidence + (f"; **gap:** {r.gap}" if r.gap else "")
            lines.append(
                f"| {r.criterion.id} | {r.criterion.source} | "
                f"{100 * r.score:.0f}% | {detail} |"
            )
        lines += ["\n## Blocking gates\n"]
        lines += [f"- {x}" for x in self.blockers] if self.blockers else ["- None"]
        return "\n".join(lines) + "\n"


RUBRIC = [
    Criterion(
        "typed_plan",
        "correctness",
        6,
        "Every run starts from a compiled, reviewable analysis IR",
        critical=True,
    ),
    Criterion(
        "contracted_execution",
        "correctness",
        7,
        "Generated code is contained and every result crosses mandatory gates",
        critical=True,
    ),
    Criterion(
        "point_in_time",
        "correctness",
        7,
        "Numbers, universes and documents are knowledge-date safe",
        critical=True,
    ),
    Criterion(
        "real_task_accuracy",
        "correctness",
        8,
        ">=95% expert-accepted answers on held-out real research tasks",
        "operating",
        True,
    ),
    Criterion(
        "dynamic_planning",
        "research_breadth",
        6,
        "A model plans heterogeneous questions and compiler feedback repairs it",
    ),
    Criterion(
        "planner_eval",
        "research_breadth",
        7,
        ">=90% acceptable plans across >=50 expert-audited, diverse questions",
        "operating",
        True,
    ),
    Criterion(
        "context_depth",
        "research_breadth",
        5,
        "Expert-authored workflows cover the desk's common research families",
        "operating",
    ),
    Criterion(
        "structured_data",
        "data_tools",
        5,
        "Point-in-time structured search binds real identifiers with reasons",
    ),
    Criterion(
        "unstructured_data",
        "data_tools",
        5,
        "Licensed internal and external research is searchable with citations",
    ),
    Criterion(
        "tool_coverage",
        "data_tools",
        6,
        ">=80% of tools used in sampled human workflows are agent-accessible",
        "operating",
        True,
    ),
    Criterion(
        "diagnosability",
        "diagnosability",
        7,
        "A reviewer can trace plan, code, inputs, vintage, checks and outputs",
        critical=True,
    ),
    Criterion(
        "reproducibility",
        "diagnosability",
        4,
        "Repeated runs and small edits are deterministic and selectively cached",
    ),
    Criterion(
        "feedback_gate",
        "learning",
        4,
        "A lesson must reproduce failure, fix it and pass regression",
    ),
    Criterion(
        "learning_outcomes",
        "learning",
        6,
        ">=80% accepted lessons improve held-out outcomes with no regression",
        "operating",
        True,
    ),
    Criterion(
        "execution_isolation",
        "production",
        5,
        "Generated code runs in a resource-limited, no-network sandbox",
        "operating",
        True,
    ),
    Criterion(
        "service_reliability",
        "production",
        5,
        ">=99.5% service success and resumable/cancellable sessions",
        "operating",
        True,
    ),
    Criterion(
        "expert_adoption",
        "product_outcomes",
        7,
        ">=60% weekly retention and >=50% median time saved for expert users",
        "operating",
        True,
    ),
]


def _auto_probes(workspace: Path) -> dict[str, tuple[float, str, str]]:
    """Cheap executable evidence. A failed probe scores zero and stays legible."""
    from .agent import Quantifact
    from .data.adapters.base import DocumentSource
    from .learn.teach import KNOWN_EFFECTS
    from .learn.workflows import WorkflowRepo
    from .planner_llm import LLMPlanner

    out: dict[str, tuple[float, str, str]] = {}
    try:
        qf = Quantifact(workspace)
        plan, _ = qf.build_plan("How did markets respond to the oil shock?")
        out["typed_plan"] = (
            1,
            f"compiled {len(plan.tasks)} tasks/{len(plan.charts())} charts",
            "",
        )
        art = qf.analyse("How did markets respond to the oil shock?", writeback=False)
        ok = all(v.ok for v in art.verdicts)
        out["contracted_execution"] = (
            1 if ok else 0,
            f"{sum(v.ok for v in art.verdicts)}/{len(art.verdicts)} verdicts",
            "make every mandatory verdict pass" if not ok else "",
        )
        receipt = art.receipt(backend=qf.backend.name, user=qf.user.name)
        trace_ok = bool(
            receipt["execution"]
            and receipt["verdicts"]
            and receipt["planning_trace"]
            and receipt["plan_sha256"]
            and receipt["code_sha256"]
        )
        out["diagnosability"] = (
            1 if trace_ok else 0.5,
            "versioned receipt covers plan/code identity, planning, execution and checks",
            "complete the machine-readable run receipt" if not trace_ok else "",
        )
        # Two vintages must expose different slices, and future documents must stay hidden.
        early = qf.adapter.read_series("US.OUTPUT_GAP", as_of="2022-03-01")
        late = qf.adapter.read_series("US.OUTPUT_GAP", as_of="2026-08-01")
        pit = len(early) < len(late)
        if isinstance(qf.adapter, DocumentSource):
            pit = pit and all(
                h.document.published_at <= "2022-03-01"
                for h in qf.adapter.search_documents("oil shock", as_of="2022-03-01")
            )
        out["point_in_time"] = (
            1 if pit else 0,
            "numeric and document vintages probed",
            "add/fix bitemporal enforcement" if not pit else "",
        )
        out["structured_data"] = (
            0.7,
            f"{len(qf.adapter.catalog())} synthetic series; "
            "inspection and entitlements implemented",
            "validate against a licensed production catalog",
        )
        docs = getattr(qf.adapter, "documents", None)
        out["unstructured_data"] = (
            0.35 if docs is not None else 0,
            f"{len(docs) if docs is not None else 0} synthetic documents",
            "connect licensed corpora, web retrieval, chunking and retrieval evals",
        )
        workflows = WorkflowRepo().all()
        out["dynamic_planning"] = (
            0.5 if LLMPlanner else 0,
            "compiler-feedback planner implemented; stub-tested",
            "run real-model, multi-domain held-out planner evaluations",
        )
        out["feedback_gate"] = (
            0.45 if KNOWN_EFFECTS else 0,
            f"three-gate teach loop; {len(KNOWN_EFFECTS)} registered effect(s)",
            "support arbitrary lessons and end-to-end/LLM-planner regression",
        )
        out["reproducibility"] = (
            0.9,
            "content-addressed cache and determinism covered by executable tests",
            "add cross-runtime and multi-adapter reproducibility SLOs",
        )
        out["context_depth"] = (
            min(0.4, len(workflows) / 10),
            f"{len(workflows)} packaged workflow guide(s)",
            "expert-audit coverage across the desk's research taxonomy",
        )
    except Exception as exc:  # audit must report a broken system, not crash with it
        message = f"automatic probe failed: {type(exc).__name__}: {exc}"
        for c in RUBRIC:
            if c.source == "automatic":
                out.setdefault(c.id, (0, message, "repair the executable probe"))
    return out


def _operating_score(c: Criterion, evidence: dict[str, Any]) -> tuple[float, str, str]:
    item = evidence.get("criteria", {}).get(c.id)
    if not isinstance(item, dict):
        return 0, "no operating evidence supplied", c.target
    required = ("evidence", "artifact", "approved_by", "measured_at", "sample_size")
    missing = [key for key in required if not item.get(key)]
    if missing:
        return (
            0,
            f"operating evidence is incomplete (missing {', '.join(missing)})",
            c.target,
        )
    score = float(item.get("score", 0))
    if not 0 <= score <= 1:
        return 0, f"invalid score {score}; expected 0..1", c.target
    note = (
        f"{item['evidence']} (n={item['sample_size']}, approved by "
        f"{item['approved_by']}, {item['artifact']})"
    )
    return score, note, "" if score >= 0.8 else c.target


def audit(
    workspace: str | Path | None = None, evidence: dict[str, Any] | None = None
) -> AuditReport:
    evidence = evidence or {}
    with tempfile.TemporaryDirectory(prefix="qf-audit-") as tmp:
        probes = _auto_probes(Path(workspace) if workspace else Path(tmp))
    results: list[Result] = []
    for c in RUBRIC:
        score, note, gap = (
            probes.get(c.id, (0, "no automatic probe", c.target))
            if c.source == "automatic"
            else _operating_score(c, evidence)
        )
        results.append(Result(c, max(0, min(1, score)), note, gap))
    blockers = [
        f"{r.criterion.id}: {r.criterion.target}"
        for r in results
        if r.criterion.critical and r.score < 0.8
    ]
    return AuditReport(results, blockers)


def load_evidence(path: str | Path | None) -> dict[str, Any]:
    return json.loads(Path(path).read_text()) if path else {}
