"""Research-family contracts.

Generic schemas can prove that a dataframe matches its declaration. They
cannot prove that an event study declared its window before seeing results or
that a historical analogy avoided causal overclaiming.  Method contracts close
that gap one research family at a time and remain ordinary Python gates: a
model may propose a methodology, but it cannot waive its requirements.
"""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd

from ..plan.model import AnalysisPlan
from .verdict import Verdict

DesignCheck = Callable[[AnalysisPlan], list[str]]
EvidenceCheck = Callable[[AnalysisPlan, dict[str, pd.DataFrame]], list[str]]


def _event_study_design(plan: AnalysisPlan) -> list[str]:
    problems: list[str] = []
    event_tasks = [
        t for t in plan.tasks if (t.op or {}).get("kind") == "event_window_return"
    ]
    if not event_tasks:
        return ["event_study declares no event_window_return task"]
    for task in event_tasks:
        window = (task.op or {}).get("window_days")
        if not isinstance(window, int) or window <= 0:
            problems.append(
                f"task '{task.name}' has no positive pre-declared event window"
            )
        exact = [
            x
            for x in task.invariants
            if x.get("kind") == "row_count" and x.get("min") == x.get("max")
        ]
        if not exact:
            problems.append(f"task '{task.name}' has no exact expected row-set contract")
        unique = [x for x in task.invariants if x.get("kind") == "unique"]
        if not unique:
            problems.append(
                f"task '{task.name}' does not declare event/entity uniqueness"
            )
    design = plan.research_design
    falsifiers = " ".join(
        f for claim in (design.claims if design else []) for f in claim.falsifiers
    ).lower()
    if "window" not in falsifiers:
        problems.append("event_study has no pre-declared window-sensitivity falsifier")
    return problems


def _event_study_evidence(
    plan: AnalysisPlan, frames: dict[str, pd.DataFrame]
) -> list[str]:
    problems: list[str] = []
    for task in plan.tasks:
        if (task.op or {}).get("kind") != "event_window_return":
            continue
        frame = frames.get(task.name)
        if frame is None or frame.empty:
            problems.append(f"event result '{task.name}' did not materialise")
            continue
        if {"episode", "market_id"} <= set(frame.columns):
            counts = frame.groupby("episode")["market_id"].nunique()
            if len(counts) < 2:
                problems.append("event study materialised fewer than two episodes")
    return problems


def _historical_analogy_design(plan: AnalysisPlan) -> list[str]:
    design = plan.research_design
    if design is None:
        return ["historical_analogy has no research design"]
    problems: list[str] = []
    if any(c.kind == "causal" for c in design.claims):
        problems.append(
            "historical analogy may not present an analogy as causal evidence"
        )
    limits = " ".join(design.limitations).lower()
    if not any(word in limits for word in ("observational", "causal", "forecast")):
        problems.append("historical analogy does not disclose its inference limit")
    if not design.alternatives:
        problems.append("historical analogy declares no rival explanation")
    return problems


def _historical_analogy_evidence(
    plan: AnalysisPlan, frames: dict[str, pd.DataFrame]
) -> list[str]:
    episode_frames = [df for df in frames.values() if "episode" in df.columns]
    if not episode_frames:
        return ["historical analogy materialised no episode-labelled evidence"]
    episodes = {str(x) for df in episode_frames for x in df["episode"].dropna().unique()}
    return (
        []
        if len(episodes) >= 2
        else ["historical analogy contains fewer than two episodes"]
    )


METHODS: dict[str, tuple[DesignCheck, EvidenceCheck]] = {
    "event_study": (_event_study_design, _event_study_evidence),
    "historical_analogy": (_historical_analogy_design, _historical_analogy_evidence),
}


def validate_method_design(plan: AnalysisPlan) -> list[str]:
    design = plan.research_design
    if design is None:
        return []
    problems: list[str] = []
    for method in design.methodologies:
        registered = METHODS.get(method)
        if registered is None:
            problems.append(f"unknown research methodology '{method}'")
        else:
            problems.extend(registered[0](plan))
    return problems


def validate_method_evidence(
    plan: AnalysisPlan, frames: dict[str, pd.DataFrame]
) -> list[Verdict]:
    design = plan.research_design
    if design is None:
        return []
    verdicts: list[Verdict] = []
    for method in design.methodologies:
        registered = METHODS.get(method)
        problems = (
            [f"unknown research methodology '{method}'"]
            if registered is None
            else registered[1](plan, frames)
        )
        verdicts.append(Verdict(method, "M-method", not problems, problems))
    return verdicts
