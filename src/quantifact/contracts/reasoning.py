"""Deterministic gates for the epistemic part of an analysis.

Numeric contracts answer "did the program satisfy its specification?".  These
gates answer the prior question: "did the specification expose what would make
the proposed inference weak or wrong?".  They cannot prove a claim true.  They
can prevent an undeclared, unfalsifiable, or unsupported claim from acquiring
the visual authority of a finished report.
"""

from __future__ import annotations

import pandas as pd

from ..plan.model import AnalysisPlan
from .verdict import Verdict


def validate_research_design(plan: AnalysisPlan) -> list[str]:
    design = plan.research_design
    if design is None:
        return [
            "plan has no research_design; claims, rival explanations and "
            "falsification criteria must be declared before execution"
        ]

    problems: list[str] = []
    names = set(plan.names)
    claim_ids = [c.id for c in design.claims]
    alternative_ids = [a.id for a in design.alternatives]
    if not design.decision_context.strip():
        problems.append("research_design has no decision_context")
    if not design.claims:
        problems.append("research_design declares no claims")
    if len(claim_ids) != len(set(claim_ids)):
        problems.append("research_design has duplicate claim ids")
    if len(alternative_ids) != len(set(alternative_ids)):
        problems.append("research_design has duplicate alternative ids")
    if not design.limitations:
        problems.append("research_design declares no limitations")

    for claim in design.claims:
        where = f"claim '{claim.id}'"
        if not claim.statement.strip():
            problems.append(f"{where} has an empty statement")
        if not claim.evidence_tasks:
            problems.append(f"{where} names no evidence tasks")
        unknown = sorted(set(claim.evidence_tasks) - names)
        if unknown:
            problems.append(f"{where} references unknown evidence tasks {unknown}")
        if not claim.falsifiers:
            problems.append(f"{where} has no pre-declared falsifier")
        if claim.kind == "causal" and design.question_type != "causal":
            problems.append(
                f"{where} is causal but question_type is '{design.question_type}'"
            )
        if claim.kind == "predictive" and design.question_type != "predictive":
            problems.append(
                f"{where} is predictive but question_type is '{design.question_type}'"
            )

    # Comparative, causal and predictive work needs a rival account. Otherwise
    # the system is only collecting confirmatory evidence for its first story.
    if design.question_type != "descriptive" and not design.alternatives:
        problems.append(
            f"{design.question_type} research declares no alternative explanation"
        )
    for alt in design.alternatives:
        where = f"alternative '{alt.id}'"
        if not alt.statement.strip():
            problems.append(f"{where} has an empty statement")
        if not alt.discriminating_tasks:
            problems.append(f"{where} names no discriminating evidence task")
        unknown = sorted(set(alt.discriminating_tasks) - names)
        if unknown:
            problems.append(f"{where} references unknown tasks {unknown}")

    if (
        design.question_type == "causal"
        and not (design.identification_strategy or "").strip()
    ):
        problems.append("causal research has no identification_strategy")
    if (
        design.question_type == "predictive"
        and not (design.out_of_sample_test or "").strip()
    ):
        problems.append("predictive research has no out_of_sample_test")
    return problems


def validate_claim_evidence(
    plan: AnalysisPlan, frames: dict[str, pd.DataFrame]
) -> list[Verdict]:
    """Bind every pre-declared inference to materialised, non-empty evidence."""
    design = plan.research_design
    if design is None:
        return [Verdict("research_design", "CT-evidence", False, ["missing design"])]
    verdicts: list[Verdict] = []
    for claim in design.claims:
        problems = []
        for task in claim.evidence_tasks:
            frame = frames.get(task)
            if frame is None:
                problems.append(f"evidence task '{task}' did not materialise")
            elif frame.empty:
                problems.append(f"evidence task '{task}' produced zero rows")
        verdicts.append(Verdict(claim.id, "CT-evidence", not problems, problems))
    for alt in design.alternatives:
        problems = []
        for task in alt.discriminating_tasks:
            frame = frames.get(task)
            if frame is None or frame.empty:
                problems.append(f"discriminating task '{task}' has no evidence")
        verdicts.append(
            Verdict(f"alternative:{alt.id}", "CT-alternative", not problems, problems)
        )
    return verdicts
