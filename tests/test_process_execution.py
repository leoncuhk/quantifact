"""Process containment has measurable limits and never masquerades as a sandbox."""

from __future__ import annotations

import pandas as pd
import pytest

from quantifact import AnalysisPlan, ColumnSpec, ProcessExecutionHarness, Task
from quantifact.harness.cache import ValueCache
from quantifact.harness.execute import TaskExecutionError


def _task() -> Task:
    return Task(
        name="bounded",
        type="table_logic",
        description="one bounded value",
        columns=[ColumnSpec("value", "bounded value", "float64")],
        index=["value"],
        row_expectation="one row",
    )


def test_process_worker_executes_and_returns_a_dataframe(qf, tmp_path):
    task = _task()
    source = "def bounded() -> pd.DataFrame:\n    return pd.DataFrame({'value': [1.0]})\n"
    harness = ProcessExecutionHarness(
        qf.adapter, ValueCache(tmp_path / "cache"), timeout_seconds=3
    )
    result = harness.run(
        AnalysisPlan("q", [task], as_of="2026-08-01"), {task.name: source}
    )
    pd.testing.assert_frame_equal(
        result.frames[task.name], pd.DataFrame({"value": [1.0]})
    )


def test_process_worker_terminates_a_runaway_task(qf, tmp_path):
    task = _task()
    source = "def bounded() -> pd.DataFrame:\n    while True:\n        pass\n"
    harness = ProcessExecutionHarness(
        qf.adapter,
        ValueCache(tmp_path / "cache", enabled=False),
        timeout_seconds=0.2,
        cpu_seconds=1,
    )
    with pytest.raises(TaskExecutionError, match="exceeded"):
        harness.run(AnalysisPlan("q", [task], as_of="2026-08-01"), {task.name: source})


def test_quantifact_process_mode_wires_the_containment_backend(qf, tmp_path):
    from quantifact import Quantifact

    isolated = Quantifact(
        tmp_path / "ws",
        adapter=qf.adapter,
        execution_mode="process",
        task_timeout_seconds=30,
    )
    assert isinstance(isolated.harness, ProcessExecutionHarness)
    assert isolated.execution_mode == "process"
