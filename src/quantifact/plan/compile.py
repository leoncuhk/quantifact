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
INVARIANT_KINDS = {
    "nonnull",
    "range",
    "row_count",
    "unique",
    "sum_to",
    "no_future_observations",
}
# The operations the deterministic compiler can execute. A plan naming anything
# else is rejected here rather than at codegen, where the error is a stack trace
# instead of a sentence.
OP_KINDS = {
    "table",
    "load_panel",
    "union",
    "filter",
    "join",
    "pivot",
    "aggregate",
    "event_window_return",
    "event_time_overlay",
    "select",
}
OP_REQUIRED_FIELDS = {
    "table": ("table",),
    "load_panel": ("entity_col", "value_col", "entities"),
    "filter": ("column", "values"),
    "join": ("on",),
    "pivot": ("index", "columns", "values", "prefix"),
    "aggregate": ("by", "aggs"),
    "event_window_return": ("entity_col", "price_col", "window_days", "out_col"),
    "event_time_overlay": ("entity_col", "value_col", "pre_months", "post_months"),
}


def _is_identifier(name: str) -> bool:
    return bool(name) and name[0].isalpha() and set(name) <= _IDENT


class PlanCompiler:
    """Validates structure, grain, closure, units and the knowledge date."""

    def __init__(
        self,
        known_series: set[str] | None = None,
        known_tables: set[str] | None = None,
        table_columns: dict[str, set[str]] | None = None,
    ):
        self.known_series = known_series
        self.known_tables = known_tables
        self.table_columns = table_columns or {}

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
            p.append(
                "plan has no as_of (knowledge date); an analysis of the past "
                "that cannot be checked for look-ahead is not admissible"
            )
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
                    p.append(
                        f"{where}: column '{c.name}' has unsupported dtype {c.dtype}"
                    )
                if c.role is not None and c.role not in ALLOWED_ROLES:
                    p.append(f"{where}: column '{c.name}' has unknown role {c.role}")
                if (
                    c.role in ("observation_date", "publication_date")
                    and c.dtype != "datetime64[ns]"
                ):
                    p.append(
                        f"{where}: column '{c.name}' has role {c.role} but "
                        f"dtype {c.dtype}; date roles must be datetime64[ns]"
                    )
                if not c.description.strip():
                    p.append(f"{where}: column '{c.name}' has no semantic description")

            for ix in t.index:
                if ix not in t.column_names:
                    p.append(f"{where}: index column '{ix}' is not among output columns")
            if not t.index:
                p.append(f"{where}: no index declared (row grain must be explicit)")
            if not t.row_expectation:
                p.append(f"{where}: no row_expectation (row grain must be stated)")
            for col, _asc in t.sort or []:
                if col not in t.column_names:
                    p.append(f"{where}: sort column '{col}' is not an output column")

            for d in t.depends_on:
                if d not in names:
                    p.append(f"{where}: depends on unknown task '{d}'")

            kind = (t.op or {}).get("kind")
            if not kind:
                p.append(
                    f"{where}: no op declared; every task must name an "
                    f"operation from {sorted(OP_KINDS)}"
                )
            elif kind not in OP_KINDS:
                p.append(
                    f"{where}: unknown op '{kind}'; the compiler executes "
                    f"only {sorted(OP_KINDS)}"
                )
            else:
                missing = [
                    f for f in OP_REQUIRED_FIELDS.get(kind, ()) if not (t.op or {}).get(f)
                ]
                if missing:
                    p.append(
                        f"{where}: op '{kind}' is missing required field(s) {missing}"
                    )

            # --- binding ----------------------------------------------------
            if t.type == "data_ingestion":
                is_table = (t.op or {}).get("kind") == "table"
                if not t.series_inputs and not is_table:
                    p.append(
                        f"{where}: data_ingestion with no series_inputs "
                        "(late binding is not allowed)"
                    )
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
                    for col in [ref] if isinstance(ref, str) else list(ref or []):
                        if col and col not in t.column_names:
                            p.append(
                                f"{where}: chart_spec.{key}='{col}' is not an "
                                "output column"
                            )

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
        # Every declared column must be something the task can actually produce:
        # either it comes from upstream, or the operation creates it. Without
        # this the plan compiles and the failure surfaces minutes later as a
        # KeyError from generated code, which is the expensive way to learn it.
        by_name = {t.name: t for t in plan.tasks}
        for t in plan.tasks:
            upstream_cols: set[str] = set()
            for d in t.depends_on:
                if d in by_name:
                    upstream_cols |= set(by_name[d].column_names)
            for col in (t.op or {}).get("consumes", []):
                if col not in upstream_cols:
                    p.append(
                        f"task '{t.name}': consumes column '{col}' that no "
                        "upstream task produces"
                    )

            available = self._available_columns(t, upstream_cols)
            if available is None:
                continue
            for col in t.column_names:
                if col not in available:
                    p.append(
                        f"task '{t.name}': declares column '{col}', which "
                        f"neither an upstream task nor op "
                        f"'{(t.op or {}).get('kind')}' produces "
                        f"(available: {sorted(available)[:8]})"
                    )

        # --- unit consistency ---------------------------------------------
        units: dict[str, set[str]] = {}
        for t in plan.tasks:
            for c in t.columns:
                units.setdefault(c.name, set()).add(c.unit or "")
        for col, us in units.items():
            if len(us) > 1:
                p.append(
                    f"column '{col}' has conflicting units across tasks: {sorted(us)}"
                )

        # --- acyclic --------------------------------------------------------
        if not any("unknown task" in x for x in p):
            try:
                topo_layers({t.name: list(t.depends_on) for t in plan.tasks})
            except PlanError as e:
                p.extend(e.problems)

        return p

    def _available_columns(self, t, upstream_cols: set[str]) -> set[str] | None:
        """What columns this task could legitimately output, or None when the
        operation is unknown to us and we should not guess."""
        op = t.op or {}
        kind = op.get("kind")
        if kind == "table":
            known = self.table_columns.get(op.get("table", ""))
            return set(known) if known else None
        if kind == "load_panel":
            return {"date", op.get("entity_col", ""), op.get("value_col", "")}
        if kind in ("union", "join", "select", "filter"):
            return set(upstream_cols)
        if kind == "pivot":
            prefix = op.get("prefix", "")
            return (
                set(op.get("index", []))
                | set(op.get("keep", []))
                | {f"{prefix}{v}" for v in upstream_cols}
                | {c for c in t.column_names if c.startswith(prefix) and prefix}
            )
        if kind == "aggregate":
            return set(op.get("by", [])) | set(op.get("aggs", {}))
        if kind == "event_window_return":
            return {op.get("entity_col", ""), "episode", op.get("out_col", "")}
        if kind == "event_time_overlay":
            return {
                op.get("entity_col", ""),
                "episode",
                "month_offset",
                op.get("value_col", ""),
            }
        return None

    def compile(self, plan: AnalysisPlan) -> list[list[str]]:
        """Validate and return execution layers. Raises ``PlanError``."""
        problems = self.validate(plan)
        if problems:
            raise PlanError(problems)
        return topo_layers({t.name: list(t.depends_on) for t in plan.tasks})
