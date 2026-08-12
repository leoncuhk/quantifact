"""The model-driven planner, tested without a model.

The interesting behaviour is not what a model writes — it is what happens when
what it writes does not compile. A stub backend makes that testable, offline and
deterministically.
"""

from __future__ import annotations

import json

import pytest

from quantifact import PlanError
from quantifact.learn.workflows import WorkflowRepo
from quantifact.planner_llm import LLMPlanner

from .conftest import QUESTION

AS_OF = "2026-08-01"


def _valid_plan(as_of: str = AS_OF) -> dict:
    """The smallest plan that compiles: one reference table, one chart."""
    return {
        "question": "how many episodes are there",
        "as_of": as_of,
        "resolved_assumptions": ["Episodes taken from the spine"],
        "tasks": [
            {
                "name": "spine_episodes",
                "type": "data_ingestion",
                "description": "Episode spine, one row per oil supply shock.",
                "index": ["episode"],
                "row_expectation": "one row per episode",
                "sort": [["episode", True]],
                "columns": [
                    {
                        "name": "episode",
                        "description": "episode key",
                        "dtype": "string",
                        "role": "entity",
                    },
                    {
                        "name": "label",
                        "description": "human label",
                        "dtype": "string",
                        "role": "dimension",
                    },
                    {
                        "name": "start_date",
                        "description": "first day",
                        "dtype": "datetime64[ns]",
                        "role": "observation_date",
                    },
                    {
                        "name": "oil_shock",
                        "description": "shock size",
                        "dtype": "float64",
                        "unit": "ratio",
                        "role": "measure",
                    },
                ],
                "invariants": [
                    {"kind": "unique", "columns": ["episode"]},
                    {"kind": "no_future_observations"},
                ],
                "op": {"kind": "table", "table": "episodes"},
            },
            {
                "name": "episode_table",
                "type": "chart",
                "description": "The episodes under study.",
                "depends_on": ["spine_episodes"],
                "index": ["episode"],
                "row_expectation": "one row per episode",
                "sort": [["episode", True]],
                "columns": [
                    {
                        "name": "episode",
                        "description": "episode key",
                        "dtype": "string",
                        "role": "entity",
                    },
                    {
                        "name": "label",
                        "description": "human label",
                        "dtype": "string",
                        "role": "dimension",
                    },
                    {
                        "name": "oil_shock",
                        "description": "shock size",
                        "dtype": "float64",
                        "unit": "ratio",
                        "role": "measure",
                    },
                ],
                "chart_spec": {"kind": "table", "title": "Episodes"},
                "op": {"kind": "select"},
            },
        ],
    }


class StubBackend:
    """Returns canned responses, one per call, and records the prompts."""

    model = "stub"

    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.prompts: list[str] = []

    def complete(
        self, prompt: str, max_tokens: int = 4000, temperature: float = 0.0
    ) -> str:
        self.prompts.append(prompt)
        return self.responses.pop(0) if self.responses else "{}"


def _planner(qf, responses):
    return LLMPlanner(
        qf.adapter, StubBackend(responses), workflows=WorkflowRepo(), max_rounds=3
    )


def test_a_compiling_plan_is_accepted(qf):
    p = _planner(qf, [json.dumps(_valid_plan())])
    plan = p.plan(QUESTION, {"as_of": AS_OF})
    assert plan.names == ["spine_episodes", "episode_table"]
    assert plan.as_of == AS_OF
    assert p.trace.rounds == 1


def test_the_compiler_talks_back_and_the_plan_is_repaired(qf):
    broken = _valid_plan()
    broken["tasks"][1]["depends_on"] = ["does_not_exist"]  # unknown upstream
    del broken["tasks"][0]["row_expectation"]  # missing row grain
    p = _planner(qf, [json.dumps(broken), json.dumps(_valid_plan())])
    plan = p.plan(QUESTION, {"as_of": AS_OF})
    assert plan.names == ["spine_episodes", "episode_table"]
    assert p.trace.rounds == 2
    problems = " ".join(p.trace.problems[0])
    assert "unknown task 'does_not_exist'" in problems
    assert "row_expectation" in problems
    # the repair prompt contains the problems, not the original brief
    assert "does not compile" in p.backend.prompts[1]


def test_a_plan_that_never_compiles_is_refused(qf):
    broken = json.dumps({"question": "q", "tasks": [], "as_of": AS_OF})
    p = _planner(qf, [broken, broken, broken])
    with pytest.raises(PlanError, match="could not produce a compiling plan"):
        p.plan(QUESTION, {"as_of": AS_OF})
    assert p.trace.rounds == 3


def test_garbage_is_reported_as_a_problem_not_a_crash(qf):
    p = _planner(qf, ["I'm afraid I can't do that", json.dumps(_valid_plan())])
    plan = p.plan(QUESTION, {"as_of": AS_OF})
    assert plan.names
    assert "not a usable plan" in " ".join(p.trace.problems[0])


def test_the_model_cannot_move_the_knowledge_date(qf):
    sneaky = _valid_plan(as_of="2027-01-01")
    p = _planner(qf, [json.dumps(sneaky)])
    plan = p.plan(QUESTION, {"as_of": "2026-06-14"})
    assert plan.as_of == "2026-06-14"


def test_the_brief_carries_catalog_tables_ops_and_citations(qf):
    p = _planner(qf, [json.dumps(_valid_plan())])
    p.plan(QUESTION, {"as_of": AS_OF})
    brief = p.backend.prompts[0]
    for token in (
        "KNOWLEDGE DATE",
        "SERIES CATALOG",
        "REFERENCE TABLES",
        "OPERATION VOCABULARY",
        "PLAN SCHEMA",
        "WORKFLOW GUIDES",
    ):
        assert token in brief
    assert "MKT." in brief or "US.CPI" in brief  # real ids to bind to
    assert "event_window_return" in brief  # the op vocabulary
    assert p.trace.documents  # corpus was consulted


def test_a_planned_plan_executes_end_to_end(qf, tmp_path):
    """The point of compiling: a model-authored plan runs like any other."""
    p = _planner(qf, [json.dumps(_valid_plan())])
    plan = p.plan(QUESTION, {"as_of": AS_OF})
    from quantifact.codegen.base import generate_all
    from quantifact.codegen.reference import ReferenceCodegen
    from quantifact.harness.cache import ValueCache
    from quantifact.harness.execute import ExecutionHarness

    codes = generate_all(plan, ReferenceCodegen())
    result = ExecutionHarness(qf.adapter, ValueCache(tmp_path / "c")).run(plan, codes)
    assert len(result.frames["episode_table"]) == 4
