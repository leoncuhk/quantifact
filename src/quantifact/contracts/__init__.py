"""Contracts: what must be true of generated code and of its results."""

from .layers import l0_static, l1_schema, l2_invariants, validate_result, validate_static
from .pointintime import LookAheadError, describe, no_future_observations
from .semantic import DEBUG_PROMPT, SEMANTIC_PROMPT, Debugger, SemanticValidator
from .verdict import TaskUnfixable, Verdict

__all__ = [
    "DEBUG_PROMPT",
    "SEMANTIC_PROMPT",
    "Debugger",
    "LookAheadError",
    "SemanticValidator",
    "TaskUnfixable",
    "Verdict",
    "describe",
    "l0_static",
    "l1_schema",
    "l2_invariants",
    "no_future_observations",
    "validate_result",
    "validate_static",
]
