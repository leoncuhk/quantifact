"""Codegen: the model is a replaceable backend behind one interface."""

from .base import CodegenBackend, generate_all, generate_serially, schemas_of
from .prompts import CODEGEN_PROMPT, CONVENTIONS
from .reference import ReferenceCodegen
from .simulated import SimulatedLatencyCodegen

__all__ = [
    "CODEGEN_PROMPT",
    "CONVENTIONS",
    "CodegenBackend",
    "ReferenceCodegen",
    "SimulatedLatencyCodegen",
    "generate_all",
    "generate_serially",
    "schemas_of",
]
