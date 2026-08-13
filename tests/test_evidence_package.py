"""The run product is portable evidence, not just an HTML view."""

from __future__ import annotations

import json

from quantifact import ResearchEvidencePackage
from quantifact.cli import main

from .conftest import QUESTION


def test_end_to_end_run_emits_verifiable_claim_lineage(qf, tmp_path):
    report = tmp_path / "report.html"
    art = qf.analyse(QUESTION, out=report, writeback=False)

    assert art.evidence_path == report.with_suffix(".evidence.json")
    assert art.evidence.admitted
    assert art.evidence.verify() == []
    assert art.evidence.payload["admission"]["investment_approved"] is False
    assert art.evidence.payload["identity"]["execution_mode"] == "in_process"
    assert art.evidence.payload["research_design"]["methodologies"] == [
        "event_study",
        "historical_analogy",
    ]
    claim = art.evidence.payload["claims"][0]
    assert claim["evidence"]
    leaf = next(iter(claim["evidence"].values()))
    assert leaf["code_sha256"] and leaf["value_fingerprint"] and leaf["source_series"]
    assert art.evidence.payload["sources"]
    assert all(
        s["visible_fingerprint"] and s["license"] for s in art.evidence.payload["sources"]
    )
    assert set(art.evidence.payload["code"]) == set(art.plan.names)
    assert art.evidence.payload["plan"] == art.plan.to_dict()


def test_integrity_verification_detects_tampering(qf):
    art = qf.analyse(QUESTION, writeback=False)
    package = ResearchEvidencePackage(art.evidence.to_dict())
    package.payload["as_of"] = "2099-01-01"
    assert "integrity hash" in " ".join(package.verify())


def test_cli_verifies_a_package_and_rejects_a_mutated_one(qf, tmp_path, capsys):
    path = tmp_path / "evidence.json"
    qf.analyse(QUESTION, evidence_out=path, writeback=False)
    assert main(["verify", str(path)]) == 0
    assert "not approved" in capsys.readouterr().out

    payload = json.loads(path.read_text())
    payload["question"] = "tampered"
    path.write_text(json.dumps(payload))
    assert main(["verify", str(path)]) == 1
