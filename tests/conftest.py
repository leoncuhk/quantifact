"""Shared fixtures. One synthetic store per session — building it is the slow
part, and every test wants the same deterministic one."""

from __future__ import annotations

import pytest

from quantifact import ANALYST, ColumnSpec, Quantifact, Task

AS_OF = "2026-08-01"
QUESTION = "How did markets respond to the oil supply shock?"


@pytest.fixture(scope="session")
def ws(tmp_path_factory):
    return tmp_path_factory.mktemp("qf")


@pytest.fixture(scope="session")
def qf(ws):
    return Quantifact(ws, ANALYST)


@pytest.fixture(scope="session")
def plan(qf):
    p, _ = qf.build_plan(QUESTION)
    return p


@pytest.fixture(scope="session")
def codes(plan, qf):
    from quantifact.codegen.base import generate_all

    return generate_all(plan, qf.backend)


def toy_task(**over) -> Task:
    base = {
        "name": "t",
        "type": "table_logic",
        "description": "d",
        "columns": [ColumnSpec("a", "col a")],
        "index": ["a"],
        "row_expectation": "one row",
        "depends_on": ["u"],
    }
    base.update(over)
    return Task(**base)
