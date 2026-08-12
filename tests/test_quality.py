"""The maturity claim itself is a contract: missing evidence must stay missing."""

from __future__ import annotations

from quantifact.quality import RUBRIC, AuditReport, Criterion, Result, audit


def test_a_repository_only_audit_cannot_claim_pat_level():
    report = audit()
    assert report.level != "PAT-level evidence"
    assert report.blockers
    assert any("real_task_accuracy" in b for b in report.blockers)
    operating = [r for r in report.results if r.criterion.source == "operating"]
    assert operating and all(r.score == 0 for r in operating)


def test_operating_evidence_is_versioned_input_not_an_inferred_feature():
    evidence = {
        "criteria": {
            "real_task_accuracy": {
                "score": 0.96,
                "evidence": "96/100 held-out",
                "artifact": "evals/real-task-2026-08.json",
                "approved_by": "research-review-board",
                "measured_at": "2026-08-12",
                "sample_size": 100,
            },
        }
    }
    report = audit(evidence=evidence)
    result = next(r for r in report.results if r.criterion.id == "real_task_accuracy")
    assert result.score == 0.96 and "96/100" in result.evidence
    assert next(r for r in report.results if r.criterion.id == "planner_eval").score == 0


def test_an_untraceable_operating_score_is_rejected():
    report = audit(
        evidence={
            "criteria": {"real_task_accuracy": {"score": 1, "evidence": "trust me"}}
        }
    )
    result = next(r for r in report.results if r.criterion.id == "real_task_accuracy")
    assert result.score == 0 and "incomplete" in result.evidence


def test_critical_gate_blocks_a_high_average():
    criteria = [
        Criterion("safe", "a", 1, "safe", critical=True),
        Criterion("many", "b", 99, "many"),
    ]
    report = AuditReport(
        [Result(criteria[0], 0, "failed"), Result(criteria[1], 1, "passed")],
        ["safe failed"],
    )
    assert report.score == 99
    assert report.level != "PAT-level evidence"


def test_rubric_weights_are_a_complete_percentage():
    assert sum(c.weight for c in RUBRIC) == 100
    assert len({c.id for c in RUBRIC}) == len(RUBRIC)
