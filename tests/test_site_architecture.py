"""The public architecture must stay aligned with the executable system."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_architecture_names_system_planes_subsystems_and_interfaces():
    path = ROOT / "docs/assets/architecture.svg"
    ET.parse(path)  # malformed SVG should fail before GitHub renders it
    svg = path.read_text()
    for phrase in (
        "RESEARCH UNDERSTANDING",
        "ANALYSIS COMPILER",
        "CONTROLLED EXECUTION",
        "ORGANISATION LEARNING",
        "QUANTIFACT SYSTEM BOUNDARY",
        "ONLINE RUNTIME PLANE",
        "SHARED CONTROL + PLATFORM PLANE",
        "OFFLINE GOVERNANCE PLANE",
        "PIT DATA + RETRIEVAL",
        "EVIDENCE + OBSERVABILITY STORE",
    ):
        assert phrase in svg
    for flow in ('class="flow"', 'class="dependency"', 'class="learn"'):
        assert flow in svg


def test_site_explains_architecture_workflow_and_reasoning_contract():
    page = (ROOT / "site/index.html").read_text()
    assert "__ARCHITECTURE__" not in page and "__DATA__" not in page
    for phrase in (
        "Contain error before model output becomes investment evidence",
        "Investment Research System Architecture",
        "PAT lifecycle implemented in Quantifact",
        "Critical investment reasoning",
        "governed lifecycle",
        "APPROVED RELEASE ARTEFACTS",
        "PARTIAL · executable core",
        "IMPLEMENTED · supported ops",
        "MINIMUM LOOP · one effect",
    ):
        assert phrase in page


def test_site_data_carries_the_pre_registered_research_design():
    data = json.loads((ROOT / "site/data.json").read_text())
    design = data["plan"]["research_design"]
    assert design["claims"] and design["alternatives"] and design["limitations"]
    assert all(c["evidence_tasks"] and c["falsifiers"] for c in design["claims"])
