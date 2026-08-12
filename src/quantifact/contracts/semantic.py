"""L3 semantic review and the repair prompt.

These are the two places a model is allowed to judge rather than produce, and
both are optional. The deterministic layers stay the backbone: measured on a
real endpoint, L3 approved a result that differed from the reference by ten
boundary rows, which is exactly why it is the last line and not the first.
"""

from __future__ import annotations

from typing import Protocol

import pandas as pd

from ..plan.model import Task
from .verdict import Verdict

SEMANTIC_PROMPT = """You are validating one task of an analysis plan.

TASK DESCRIPTION
{description}
row grain: {row_expectation}
declared columns: {columns}
knowledge date (as_of): {as_of}

GENERATED CODE
{code}

RESULT SAMPLE (first rows)
{sample}

Does the code implement the task description faithfully? Consider: wrong
aggregation level, wrong window, silently dropped rows, the wrong column, an
operation the description did not ask for, or any use of information that
would not have been available on the knowledge date.

Answer with exactly one line: OK  or  PROBLEM: <one sentence>."""

DEBUG_PROMPT = """The generated function for task '{name}' failed validation.

TASK
{description}
declared columns: {columns}
row grain: {row_expectation}
knowledge date (as_of): {as_of}
{upstream}{evidence}
CODE
{code}

FAILURES
{problems}

{conventions}
Return ONLY the corrected function source."""


class SemanticValidator(Protocol):
    def validate(
        self, task: Task, code: str, df: pd.DataFrame, as_of: str = ""
    ) -> Verdict: ...


class Debugger(Protocol):
    def edit(
        self,
        task: Task,
        code: str,
        verdict: Verdict,
        upstream: dict | None = None,
        evidence: str = "",
        as_of: str = "",
    ) -> str: ...
