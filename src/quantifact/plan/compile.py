"""PlanCompiler — reject bad plans before a single token is spent on codegen.

This is the first place where correctness is enforced by the architecture
rather than by diligence. Every check here is a *compile error*: it costs
milliseconds and it prevents a class of failure that would otherwise surface
minutes later, halfway through an execution, as something much harder to read.

The checks, grouped:

structure      identifiers, duplicates, empty descriptions, declared columns
grain          index columns exist, row grain stated, sort columns exist
dependencies   referenced tasks exist, no cycles, ingestion consumes nothing
binding        data_ingestion binds concrete series ids at plan time
closure        every consumed column is produced by some upstream task
semantics      dtypes and roles are known, units do not conflict across tasks
knowledge date as_of present and parseable, observation-date columns typed
charts         chart fields exist among the task's own output columns
"""

from __future__ import annotations

from .layers import topo_layers
from .model import ALLOWED_DTYPES, ALLOWED_ROLES, AnalysisPlan, PlanError, parse_date

_IDENT = set("abcdefghijklmnopqrstuvwxyz0123456789_")
INVARIANT_KINDS = {"nonnull", "range", "row_count", "unique", "sum_to",
                   "no_future_observations"}


def _is_identifier(name: str) -> bool:
    return bool(name) and name[0].isalpha() and set(name) <= _IDENT


class PlanCompiler:
    """Validates structure, grain, closure, units and the knowledge date."""

    def __init__(self, known_series: set[str] | None = None,
                 known_tables: set[str] | None = None):
        self.known_series = known_series
        self.known_tables = known_tables

    # ------------------------------------------------------------ validate
    def validate(self, plan: AnalysisPlan) -> list[str]:
        p: list[str] = []
        names = plan.names

        if not plan.tasks:
            p.append("plan has no tasks")
        for n in set(names):
            if names.count(n) > 1:
                p.append(f"duplicate task name: {n}")

        # --- knowledge date -------------------------------------------------
        if not plan.as_of:
            p.append("plan has no as_of (knowledge date); an analysis of the past "
                     "that cannot be checked for look-ahead is not admissible")
        else:
            try:
                parse_date(plan.as_of)
            except ValueError:
                p.append(f"as_of '{plan.as_of}' is not an ISO date")

        for t in plan.tasks:
            where = f"task '{t.name}'"
            if not _is_identifier(t.name):
                p.append(f"{where}: name is not a valid python identifier")
            if not t.description.strip():
                p.append(f"{where}: empty description")
            if not t.columns:
                p.append(f"{where}: declares no output columns")

            for c in t.columns:
                if c.dtype not in ALLOWED_DTYPES:
                    p.append(f"{where}: column '{c.name}' has unsupported dtype "
                             f"{c.dtype}")
                if c.role is not None and c.role not in ALLOWED_ROLES:
                    p.append(f"{where}: column '{c.name}' has unknown role {c.role}")
                if c.role in ("observation_date", "publication_date") \
                        and c.dtype != "datetime64[ns]":
                    p.append(f"{where}: column '{c.name}' has role {c.role} but "
                             f"dtype {c.dtype}; date roles must be datetime64[ns]")
                if not c.description.strip():
                    p.append(f"{where}: column '{c.name}' has no semantic description")

            for ix in t.index:
                if ix not in t.column_names:
                    p.append(f"{where}: index column '{ix}' is not among output columns")
            if not t.index:
                p.append(f"{where}: no index declared (row grain must be explicit)")
            if not t.row_expectation:
                p.append(f"{where}: no row_expectation (row grain must be stated)")
            for col, _asc in (t.sort or []):
                if col not in t.column_names:
                    p.append(f"{where}: sort column '{col}' is not an output column")

            for d in t.depends_on:
                if d not in names:
                    p.append(f"{where}: depends on unknown task '{d}'")

            # --- binding ----------------------------------------------------
            if t.type == "data_ingestion":
                is_table = (t.op or {}).get("kind") == "table"
                if not t.series_inputs and not is_table:
                    p.append(f"{where}: data_ingestion with no series_inputs "
                             "(late binding is not allowed)")
                if is_table:
                    table = (t.op or {}).get("table")
                    if not table:
                        p.append(f"{where}: reference-table task without op.table")
                    elif self.known_tables is not None and table not in self.known_tables:
                        p.append(f"{where}: unknown reference table '{table}'")
                if t.depends_on:
                    p.append(f"{where}: data_ingestion must not depend on other tasks")
                if self.known_series is not None:
                    for s in t.series_inputs:
                        if s not in self.known_series:
                            p.append(f"{where}: unknown series_id '{s}'")
            else:
                if t.series_inputs:
                    p.append(f"{where}: only data_ingestion may bind series_inputs")
                if not t.depends_on:
                    p.append(f"{where}: {t.type} task consumes nothing")

            # --- charts -----------------------------------------------------
            if t.type == "chart":
                spec = t.chart_spec or {}
                if not spec.get("kind"):
                    p.append(f"{where}: chart task without chart_spec.kind")
                for key in ("x", "y", "facet", "series", "label"):
                    ref = spec.get(key)
                    for col in ([ref] if isinstance(ref, str) else list(ref or [])):
                        if col and col not in t.column_names:
                            p.append(f"{where}: chart_spec.{key}='{col}' is not an "
                                     "output column")

            # --- invariants -------------------------------------------------
            for inv in t.invariants:
                kind = inv.get("kind")
                if kind not in INVARIANT_KINDS:
                    p.append(f"{where}: unknown invariant kind '{kind}'")
                col = inv.get("column")
                if col and col not in t.column_names:
                    p.append(f"{where}: invariant references unknown column '{col}'")
                for c in inv.get("columns", []):
                    if c not in t.column_names:
                        p.append(f"{where}: invariant references unknown column '{c}'")

        # --- column closure ----------------------------------------------
        by_name = {t.name: t for t in plan.tasks}
        for t in plan.tasks:
            upstream_cols: set[str] = set()
            for d in t.depends_on:
                if d in by_name:
                    upstream_cols |= set(by_name[d].column_names)
            for col in (t.op or {}).get("consumes", []):
                if col not in upstream_cols:
                    p.append(f"task '{t.name}': consumes column '{col}' that no "
                             "upstream task produces")

        # --- unit consistency ---------------------------------------------
        units: dict[str, set[str]] = {}
        for t in plan.tasks:
            for c in t.columns:
                units.setdefault(c.name, set()).add(c.unit or "")
        for col, us in units.items():
            if len(us) > 1:
                p.append(f"column '{col}' has conflicting units across tasks: "
                         f"{sorted(us)}")

        # --- acyclic --------------------------------------------------------
        if not any("unknown task" in x for x in p):
            try:
                topo_layers({t.name: list(t.depends_on) for t in plan.tasks})
            except PlanError as e:
                p.extend(e.problems)

        return p

    def compile(self, plan: AnalysisPlan) -> list[list[str]]:
        """Validate and return execution layers. Raises ``PlanError``."""
        problems = self.validate(plan)
        if problems:
            raise PlanError(problems)
        return topo_layers({t.name: list(t.depends_on) for t in plan.tasks})
