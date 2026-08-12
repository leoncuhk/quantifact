"""Critical thinking is a pre-registered contract, not an LLM opinion after the fact."""

from __future__ import annotations

from copy import deepcopy

import pandas as pd

from quantifact.contracts.reasoning import (
    validate_claim_evidence,
    validate_research_design,
)
from quantifact.plan.model import (
    AlternativeExplanation,
    AnalysisPlan,
    ResearchClaim,
    ResearchDesign,
)


def test_reference_plan_predeclares_claims_rivals_and_falsifiers(plan):
    assert plan.research_design is not None
    assert plan.research_design.alternatives
    assert all(c.evidence_tasks and c.falsifiers for c in plan.research_design.claims)
    assert not validate_research_design(plan)


def test_comparative_plan_without_a_rival_explanation_is_rejected(plan):
    broken = deepcopy(plan)
    broken.research_design.alternatives = []
    problems = validate_research_design(broken)
    assert any("no alternative explanation" in p for p in problems)


def test_causal_language_requires_an_identification_strategy(plan):
    broken = deepcopy(plan)
    broken.research_design = ResearchDesign(
        question_type="causal",
        decision_context="Estimate an intervention effect.",
        claims=[
            ResearchClaim(
                "oil_causes_returns",
                "The supply shock causes the observed market move.",
                "causal",
                ["market_pairwise_returns"],
                ["A placebo date produces an equal effect."],
            )
        ],
        alternatives=[
            AlternativeExplanation(
                "concurrent_news",
                "Concurrent macro news, not oil, caused the move.",
                ["macro_event_time_overlay"],
            )
        ],
        limitations=["Unobserved confounding may remain."],
    )
    assert any(
        "no identification_strategy" in p for p in validate_research_design(broken)
    )


def test_claim_cannot_reach_report_without_materialised_evidence(plan):
    frames = {
        name: pd.DataFrame({"x": [1]})
        for name in plan.names
        if name != "market_pairwise_scatter"
    }
    verdicts = validate_claim_evidence(plan, frames)
    failed = [v for v in verdicts if not v.ok]
    assert failed and failed[0].task == "market_responses_rhyme"


def test_report_exposes_inference_limits(qf, tmp_path):
    path = tmp_path / "report.html"
    qf.analyse("How did markets respond to the oil shock?", out=path, writeback=False)
    page = path.read_text()
    for phrase in (
        "Research design and inference limits",
        "Alternative explanations tested",
        "Would weaken or falsify",
        "Historical analogy is observational",
    ):
        assert phrase in page


def test_research_design_round_trips_with_the_plan(plan, tmp_path):
    path = tmp_path / "plan.json"
    plan.save(path)
    again = AnalysisPlan.load(path)
    assert again.research_design == plan.research_design
