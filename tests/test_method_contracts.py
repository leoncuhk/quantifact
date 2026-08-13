"""Domain methods fail closed instead of surviving as report prose."""

from __future__ import annotations

from copy import deepcopy

from quantifact.contracts.methods import validate_method_design, validate_method_evidence


def test_supported_plan_declares_and_passes_method_contracts(plan, qf):
    assert plan.research_design.methodologies == ["event_study", "historical_analogy"]
    assert validate_method_design(plan) == []
    art = qf.analyse(plan.question, writeback=False)
    verdicts = validate_method_evidence(art.plan, art.result.frames)
    assert verdicts and all(v.ok for v in verdicts)


def test_event_study_rejects_an_uncontracted_window(plan):
    broken = deepcopy(plan)
    task = broken["market_episode_returns"]
    task.invariants = [x for x in task.invariants if x.get("kind") != "row_count"]
    assert any("exact expected row-set" in p for p in validate_method_design(broken))


def test_unknown_method_is_a_compile_error(plan):
    broken = deepcopy(plan)
    broken.research_design.methodologies.append("magic_alpha")
    assert "unknown research methodology" in " ".join(validate_method_design(broken))
