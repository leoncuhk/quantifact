"""The durable product of a Quantifact run.

Reports are views and conversations are transient.  The evidence package is the
versioned, machine-verifiable research object: question, design, knowledge date,
source vintages and licences, code identity, materialised outputs, verdicts,
claim lineage and an explicit admission decision.  Admission means only that
the declared evidence crossed the configured gates; it is never investment
approval or a claim that the inference is true.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .harness.cache import RUNTIME_ID, frame_fingerprint

SCHEMA_VERSION = "quantifact.evidence/1"


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


@dataclass
class ResearchEvidencePackage:
    payload: dict[str, Any]

    @property
    def package_id(self) -> str:
        return self.payload["integrity"]["sha256"]

    @property
    def admitted(self) -> bool:
        return self.payload["admission"]["evidence_admitted"]

    def verify(self) -> list[str]:
        problems: list[str] = []
        if self.payload.get("schema_version") != SCHEMA_VERSION:
            problems.append(
                f"unsupported schema_version {self.payload.get('schema_version')!r}"
            )
        integrity = self.payload.get("integrity", {})
        body = {k: v for k, v in self.payload.items() if k != "integrity"}
        expected = _digest(body)
        if integrity.get("sha256") != expected:
            problems.append("package integrity hash does not match its contents")
        if not self.payload.get("as_of"):
            problems.append("package has no knowledge date")
        if not self.payload.get("claims"):
            problems.append("package carries no claim lineage")
        plan = self.payload.get("plan") or {}
        plan_names = {t.get("name") for t in plan.get("tasks", [])}
        task_names = set(self.payload.get("tasks", {}))
        if plan_names != task_names:
            problems.append("package task manifest does not match its plan")
        codes = self.payload.get("code", {})
        if set(codes) != task_names:
            problems.append("package code manifest does not match its tasks")
        for name, source in codes.items():
            actual = hashlib.sha256(source.encode()).hexdigest()
            expected_code = self.payload["tasks"].get(name, {}).get("code_sha256")
            if actual != expected_code:
                problems.append(f"task '{name}' code hash does not match embedded source")
        return problems

    def to_dict(self) -> dict[str, Any]:
        return self.payload

    def save(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.payload, indent=2, ensure_ascii=False))
        return target

    @staticmethod
    def load(path: str | Path) -> ResearchEvidencePackage:
        return ResearchEvidencePackage(json.loads(Path(path).read_text()))


def _task_sources(plan, name: str, memo: dict[str, list[str]]) -> list[str]:
    if name in memo:
        return memo[name]
    task = plan[name]
    sources = set(task.series_inputs)
    for dep in task.depends_on:
        sources.update(_task_sources(plan, dep, memo))
    memo[name] = sorted(sources)
    return memo[name]


def build_evidence_package(
    *,
    plan,
    codes: dict[str, str],
    result,
    findings,
    verdicts,
    timings: dict[str, float],
    planning_trace: dict[str, Any],
    repair_trace: list[dict[str, Any]],
    adapter,
    backend: str,
    user: str,
    report_path: Path | None,
    execution_mode: str = "in_process",
) -> ResearchEvidencePackage:
    metadata = {m.series_id: m for m in adapter.catalog()}
    source_ids = plan.series_inputs()
    sources = []
    for sid in source_ids:
        meta = metadata[sid]
        sources.append(
            {
                "series_id": sid,
                "source": meta.source,
                "license": meta.license_tag,
                "frequency": meta.frequency,
                "unit": meta.unit,
                "first_observation": meta.first_obs,
                "last_observation": meta.last_obs,
                "last_publication": meta.last_pub,
                "visible_fingerprint": adapter.fingerprint([sid], as_of=plan.as_of),
            }
        )

    memo: dict[str, list[str]] = {}
    tasks: dict[str, Any] = {}
    for task in plan.tasks:
        frame = result.frames[task.name]
        tasks[task.name] = {
            "type": task.type,
            "depends_on": task.depends_on,
            "source_series": _task_sources(plan, task.name, memo),
            "code_sha256": hashlib.sha256(codes[task.name].encode()).hexdigest(),
            "value_fingerprint": frame_fingerprint(frame),
            "rows": len(frame),
            "columns": list(frame.columns),
            "cache_key": result.trace(task.name).cache_key,
        }

    design = plan.research_design
    claims = []
    if design:
        for claim in design.claims:
            claims.append(
                {
                    **asdict(claim),
                    "evidence": {name: tasks[name] for name in claim.evidence_tasks},
                }
            )

    admission = {
        "evidence_admitted": True,
        "decision": "admitted_for_expert_review",
        "meaning": (
            "All mandatory system gates completed. This is not investment approval, "
            "proof that a claim is true, or authorisation to trade."
        ),
        "investment_approved": False,
        "blocking_findings": [asdict(f) for f in findings if f.severity == "blocking"],
    }
    body = {
        "schema_version": SCHEMA_VERSION,
        "question": plan.question,
        "as_of": plan.as_of,
        "identity": {
            "user": user,
            "backend": backend,
            "runtime": RUNTIME_ID,
            "execution_mode": execution_mode,
        },
        "admission": admission,
        "research_design": asdict(design) if design else None,
        "plan": plan.to_dict(),
        "code": dict(codes),
        "resolved_assumptions": plan.resolved_assumptions,
        "sources": sources,
        "tasks": tasks,
        "claims": claims,
        "verdicts": [asdict(v) for v in verdicts],
        "findings": [asdict(f) for f in findings],
        "planning_trace": planning_trace,
        "repair_trace": repair_trace,
        "timings": dict(timings),
        "report": str(report_path) if report_path else None,
    }
    return ResearchEvidencePackage(
        {**body, "integrity": {"algorithm": "sha256", "sha256": _digest(body)}}
    )
