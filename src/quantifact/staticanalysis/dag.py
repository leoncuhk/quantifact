"""The dependency graph derived from code, and its cross-check against the plan.

The cross-check is the part a prompt-only system cannot do: it catches a task
that quietly consumes an upstream frame the plan never declared, which is both
a correctness bug and a cache-invalidation bug.
"""

from __future__ import annotations

from .ast_checks import CodeFacts


def dependency_graph(facts: dict[str, CodeFacts]) -> dict[str, list[str]]:
    """Actual dependencies, read from each function's parameters."""
    return {name: list(f.params) for name, f in facts.items()}


def cross_check(
    actual: dict[str, list[str]], declared: dict[str, list[str]]
) -> list[str]:
    problems = []
    for name, deps in actual.items():
        want, got = set(declared.get(name, [])), set(deps)
        if got - want:
            problems.append(
                f"task '{name}': code consumes undeclared upstream {sorted(got - want)}"
            )
        if want - got:
            problems.append(
                f"task '{name}': declared dependency {sorted(want - got)} "
                "is never consumed by the generated code"
            )
    return problems
