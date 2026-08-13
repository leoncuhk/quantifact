"""A model-driven planner for questions covered by the available data and ops.

`RulePlanner` compiles one shape of question perfectly and nothing else. This
planner takes a broader question and emits a plan within the supplied catalog,
tables and operation vocabulary. That is a weaker guarantee, so it is wrapped
in the only thing that makes it usable: **the
compiler talks back**. A plan that fails validation returns to the model as a
list of specific problems, up to a fixed number of rounds, and a plan that never
compiles is refused rather than executed.

That loop is the whole design. The model is allowed to be wrong about
structure, because being wrong about structure is cheap and legible here: it
costs one more round trip and produces an error message, not a chart.

What the model is given, and nothing else:

* the knowledge date, and the instruction that everything is bound to it;
* catalog cards for the series that matched the question, with units, frequency,
  coverage and value ranges — so it binds to real ids or not at all;
* the reference tables and their columns;
* the operation vocabulary the deterministic compiler can actually execute;
* the plan schema, field by field;
* the workflow guides and lessons that apply;
* what the research corpus already says about the question, as of that date.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol

from .codegen.reference import OP_REFERENCE
from .data.search import SeriesSearch
from .learn.lessons import Lesson
from .learn.workflows import Workflow, WorkflowRepo
from .plan.compile import PlanCompiler
from .plan.model import AnalysisPlan, PlanError
from .planner import DEFAULT_AS_OF, Clarification, RulePlanner, _as_store

PLAN_SCHEMA = """\
{
  "question": "<the user's question, restated precisely>",
  "as_of": "<YYYY-MM-DD knowledge date, given to you — do not change it>",
  "resolved_assumptions": ["<every choice you made that a reviewer must see>"],
  "research_design": {
    "question_type": "descriptive | comparative | causal | predictive",
    "methodologies": ["event_study | historical_analogy"],
    "decision_context": "<what decision this evidence informs; never imply a trade>",
    "claims": [{
      "id": "snake_case", "statement": "<bounded claim>",
      "kind": "descriptive | associational | causal | predictive",
      "evidence_tasks": ["<task names>"],
      "falsifiers": ["<observable result that would weaken or defeat the claim>"]
    }],
    "alternatives": [{
      "id": "snake_case", "statement": "<rival explanation>",
      "discriminating_tasks": ["<task names that distinguish it>" ]
    }],
    "limitations": ["<what this design cannot establish>"],
    "identification_strategy": "<required for causal questions, otherwise null>",
    "out_of_sample_test": "<required for predictive questions, otherwise null>"
  },
  "tasks": [
    {
      "name": "snake_case_identifier",           // == the python function name
      "type": "data_ingestion | table_logic | chart",
      "description": "<what this computes, in one sentence>",
      "depends_on": ["<upstream task names, in argument order>"],
      "series_inputs": ["<exact series ids>"],   // data_ingestion only
      "index": ["<columns that identify a row>"],
      "row_expectation": "<one row per ...>",
      "sort": [["column", true]],                // true = ascending
      "columns": [
        {"name": "...", "description": "...", "dtype": "float64|int64|string|datetime64[ns]|bool",
         "unit": "<unit or null>", "role": "observation_date|publication_date|entity|dimension|measure",
         "nullable": false}
      ],
      "invariants": [
        {"kind": "unique", "columns": ["..."]},
        {"kind": "nonnull", "column": "...", "min": 0.99},
        {"kind": "range", "column": "...", "min": -1, "max": 3},
        {"kind": "row_count", "min": 1, "max": 1000},
        {"kind": "no_future_observations"}
      ],
      "chart_spec": {"kind": "table|scatter|line|bar", "title": "...", "x": "...",
                     "y": "...", "series": "...", "facet": "...", "label": "...",
                     "color_by": "...", "percent": true},   // chart tasks only
      "op": { ... }                              // from the operation vocabulary
    }
  ]
}"""

RULES = """\
Hard rules, each one checked by the compiler before any code is written:

- pre-register bounded claims, falsifiers, rival explanations and evidence tasks
- declare a registered methodology only when its deterministic method contracts apply
- comparative/causal/predictive work must test at least one rival explanation
- never label a claim causal without a causal question and identification strategy
- never label a claim predictive without a stated out-of-sample test
- every task declares index, row_expectation, sort and at least one column, and
  every column carries a description, a dtype and a role
- date columns use dtype datetime64[ns]; a column that holds an observation date
  must have role observation_date
- data_ingestion tasks bind concrete series ids (from the catalog below) or read
  a reference table; they never depend on other tasks
- table_logic and chart tasks depend on at least one task and never bind series
- a column name means the same thing everywhere: the same name may not carry two
  different units across tasks
- chart_spec fields must name columns the chart task itself declares
- no cycles; every depends_on names a task in this plan
- put a row_count invariant on fact tables when you can derive the number — it is
  the check that catches a join silently dropping an entity
- add {"kind": "no_future_observations"} to any task with an observation-date
  column

Budget: at most 8 tasks. Keep every description under 120 characters and emit
compact JSON — a truncated plan is a failed plan, and verbosity is the usual
cause."""

PROMPT = """You are the planning half of an investment-research system. You do not write
code. You produce an analysis plan that a deterministic compiler turns into
pandas, one function per task.

QUESTION
{question}

KNOWLEDGE DATE (as_of): {as_of}
Everything the analysis may read had to be published on or before this date. The
loaders are already bound to it. Never plan a task that needs a later fact, and
never reference an event that had not happened by then.

CLARIFICATIONS ALREADY AGREED
{answers}

WORKFLOW GUIDES THAT APPLY
{workflows}

LESSONS THIS DESK HAS LEARNED
{lessons}

WHAT THE RESEARCH CORPUS SAYS, AS OF THE KNOWLEDGE DATE
{documents}

REFERENCE TABLES (read with load_table, filtered to the knowledge date)
{tables}

SERIES CATALOG (bind only to these ids)
{catalog}

OPERATION VOCABULARY (the compiler executes exactly these)
{ops}

PLAN SCHEMA
{schema}

{rules}

Return ONLY the JSON object, compact, with no prose and no markdown fence."""

REPAIR = """The plan you produced does not compile. The compiler reports:

{problems}

THE PLAN YOU SENT
{previous}

Fix every problem and return the COMPLETE corrected JSON object — "question",
"as_of", "resolved_assumptions" and every task, not just the parts you changed.
Do not explain."""


class PlannerBackend(Protocol):
    """Anything that can turn a prompt into a JSON plan."""

    def complete(
        self, prompt: str, max_tokens: int = 4000, temperature: float = 0.0
    ) -> str: ...


@dataclass
class PlanningTrace:
    rounds: int = 0
    problems: list[list[str]] = field(default_factory=list)
    prompt_chars: int = 0
    documents: list[str] = field(default_factory=list)

    def summary(self) -> str:
        if self.rounds <= 1 and not self.problems:
            return "compiled on the first attempt"
        fixed = sum(len(p) for p in self.problems)
        return (
            f"{self.rounds} rounds, {fixed} compiler problem(s) returned to the "
            "planner and fixed"
        )


def _normalise(payload: dict[str, Any]) -> dict[str, Any]:
    """Absorb the shapes models reach for instead of the schema.

    Not leniency about meaning — only about notation. A plan that says
    `sort: [{"column": "x", "ascending": true}]` means exactly what
    `sort: [["x", true]]` means, and refusing it teaches the model nothing.
    Anything that changes what the plan *does* is still a compile error.
    """
    for task in payload.get("tasks", []) or []:
        sort = task.get("sort")
        if isinstance(sort, list):
            fixed = []
            for entry in sort:
                if isinstance(entry, dict):
                    col = entry.get("column") or entry.get("name") or entry.get("by")
                    asc = entry.get("ascending", entry.get("asc", True))
                    fixed.append([col, bool(asc)])
                elif isinstance(entry, str):
                    fixed.append([entry, True])
                else:
                    fixed.append(list(entry))
            task["sort"] = fixed or None
        idx = task.get("index")
        if isinstance(idx, list):
            task["index"] = [
                c.get("name", c.get("column")) if isinstance(c, dict) else str(c)
                for c in idx
            ]
        for col in task.get("columns", []) or []:
            unit = col.get("unit")
            if isinstance(unit, (dict, list)):
                col["unit"] = str(unit)
            if isinstance(col.get("role"), (dict, list)):
                col["role"] = None
        if isinstance(task.get("depends_on"), str):
            task["depends_on"] = [task["depends_on"]]
        if isinstance(task.get("series_inputs"), str):
            task["series_inputs"] = [task["series_inputs"]]
    return payload


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("no JSON object in the response")
    return json.loads(text[start : end + 1])


class LLMPlanner:
    """Plans supported questions, with the plan compiler as the referee."""

    def __init__(
        self,
        adapter: Any,
        backend: PlannerBackend,
        entitlements: tuple[str, ...] = (),
        lessons: list[Lesson] | None = None,
        workflows: WorkflowRepo | None = None,
        max_rounds: int = 4,
        catalog_size: int = 24,
        max_tokens: int = 6000,
    ):
        self.adapter = adapter
        self.backend = backend
        self.entitlements = entitlements
        self.lessons = lessons or []
        self.workflows = workflows or WorkflowRepo()
        self.max_rounds = max_rounds
        self.catalog_size = catalog_size
        self.max_tokens = max_tokens
        self.search = SeriesSearch(_as_store(adapter), entitlements)
        self.trace = PlanningTrace()
        self._rules = RulePlanner(adapter, entitlements, lessons)

    # -------------------------------------------------------------- context
    def clarify(self, prompt: str) -> list[Clarification]:
        """Reuse the rule planner's questions: they are the ambiguities that
        fork *any* episode-style plan, and asking them costs nothing."""
        return self._rules.clarify(prompt)

    def _catalog(self, question: str, as_of: str) -> str:
        """Query hits, plus every non-market series.

        A model that cannot see a series invents an id for it — the single most
        common planning failure. Market series are sampled because there are
        hundreds of them and they share a naming rule; everything else is shown
        in full, because those are the ids people actually get wrong.
        """
        chosen: dict[str, Any] = {}
        for h in self.search.recall(question, k=self.catalog_size):
            chosen[h.meta.series_id] = h.meta
        markets = 0
        for m in self.search.store.all_meta():
            if not self.search.visible(m):
                continue
            if m.series_id.startswith("MKT."):
                markets += 1
                if markets <= 6:
                    chosen.setdefault(m.series_id, m)
            else:
                chosen[m.series_id] = m
        cards = "\n".join(chosen[k].card() for k in sorted(chosen))
        return (
            cards + f"\n\n(plus {markets - min(markets, 6)} further MKT.*.TRI "
            "market series following the same naming rule; use load_panel with "
            "the exact ids you need, and never invent one)"
        )

    def _tables(self, as_of: str) -> str:
        out = []
        for name in self.adapter.tables():
            df = self.adapter.read_table(name, as_of=as_of)
            cols = ", ".join(f"{c}:{df[c].dtype}" for c in df.columns)
            out.append(f"{name} ({len(df)} rows as of {as_of}): {cols}")
        return "\n".join(out)

    def _documents(self, question: str, as_of: str, k: int = 4) -> str:
        search = getattr(self.adapter, "search_documents", None)
        if search is None:
            return "(no research corpus attached)"
        hits = search(question, as_of=as_of, k=k, entitlements=self.entitlements)
        self.trace.documents = [h.citation() for h in hits]
        return (
            "\n".join(f"- {h.citation()}\n  {h.snippet}" for h in hits)
            or "(nothing written on this before the knowledge date)"
        )

    # ----------------------------------------------------------------- plan
    def plan(self, prompt: str, answers: dict[str, Any] | None = None) -> AnalysisPlan:
        a = {**self._rules.defaults(), **(answers or {})}
        as_of = str(a.get("as_of", DEFAULT_AS_OF))
        workflows: list[Workflow] = self.workflows.matching(prompt)
        compiler = PlanCompiler(
            known_series={m.series_id for m in self.adapter.catalog()},
            known_tables=set(self.adapter.tables()),
            table_columns={
                name: set(self.adapter.read_table(name, as_of=as_of).columns)
                for name in self.adapter.tables()
            },
            require_research_design=True,
        )

        self.trace = PlanningTrace()
        message = PROMPT.format(
            question=prompt,
            as_of=as_of,
            answers=json.dumps({k: v for k, v in a.items() if k != "as_of"}, indent=1),
            workflows="\n\n".join(f"## {w.id} ({w.source})\n{w.text}" for w in workflows)
            or "(none)",
            lessons="\n".join(f"- {x.id}: {x.text}" for x in self.lessons) or "(none)",
            documents=self._documents(prompt, as_of),
            tables=self._tables(as_of),
            catalog=self._catalog(prompt, as_of),
            ops=OP_REFERENCE,
            schema=PLAN_SCHEMA,
            rules=RULES,
        )
        self.trace.prompt_chars = len(message)

        last_problems: list[str] = []
        for _ in range(self.max_rounds):
            self.trace.rounds += 1
            raw = self.backend.complete(message, max_tokens=self.max_tokens)
            try:
                payload = _normalise(_extract_json(raw))
                # The question and the knowledge date are not the model's to
                # invent or to move; everything else is its to get right.
                payload["question"] = prompt
                payload["as_of"] = as_of
                previous = json.dumps(payload, indent=1)[:6000]
                plan = AnalysisPlan.from_dict(payload)
                problems = compiler.validate(plan)
            except (ValueError, KeyError, TypeError, AttributeError) as e:
                problems = [
                    f"the response was not a usable plan: {type(e).__name__}: {e}",
                    "return the exact JSON schema given in the brief: tasks is a "
                    "list of objects, sort is a list of [column, ascending] pairs, "
                    "index is a list of column names, and every column is an "
                    "object with name/description/dtype/role",
                ]
                previous = raw[:4000]
            if not problems:
                plan.resolved_assumptions = (
                    list(plan.resolved_assumptions)
                    + [
                        f"Knowledge date (as_of): {as_of} — nothing published later was read",
                        f"Planned by {getattr(self.backend, 'model', 'a model')}, "
                        f"{self.trace.summary()}",
                    ]
                    + [f"Cited: {c}" for c in self.trace.documents]
                )
                return plan
            self.trace.problems.append(problems)
            last_problems = problems
            message = REPAIR.format(
                problems="\n".join(f"- {p}" for p in problems), previous=previous
            )

        raise PlanError(
            [
                f"the planner could not produce a compiling plan in "
                f"{self.max_rounds} rounds",
                *last_problems,
            ]
        )
