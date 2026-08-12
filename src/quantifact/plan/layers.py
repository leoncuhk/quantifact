"""Dependency layering — the only graph algorithm the planner needs."""

from __future__ import annotations

from .model import PlanError


def topo_layers(edges: dict[str, list[str]]) -> list[list[str]]:
    """Kahn layering. ``edges[node]`` lists that node's dependencies.

    Returns groups that can be executed (and validated) in parallel. Raises
    ``PlanError`` on a cycle, which is a compile error, not a runtime one.
    """
    remaining = {n: set(deps) for n, deps in edges.items()}
    layers: list[list[str]] = []
    while remaining:
        ready = sorted(n for n, deps in remaining.items() if not deps)
        if not ready:
            raise PlanError([f"dependency cycle among: {sorted(remaining)}"])
        layers.append(ready)
        for n in ready:
            remaining.pop(n)
        for deps in remaining.values():
            deps.difference_update(ready)
    return layers
