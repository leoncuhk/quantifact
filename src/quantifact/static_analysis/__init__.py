"""Static analysis: everything that can be known about generated code without
running it."""

from .ast_checks import CodeFacts, analyse
from .dag import cross_check, dependency_graph

__all__ = ["CodeFacts", "analyse", "cross_check", "dependency_graph"]
