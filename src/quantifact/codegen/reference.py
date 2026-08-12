"""The reference backend: a deterministic compiler, and the oracle.

It compiles the structured ``op`` spec of a task straight into pandas. No
model, no network, no variance — which is what makes it usable as the test
oracle a language-model backend is graded against, and what lets every number
in the benchmarks be reproduced offline.

Supported ops: ``table`` (a reference table), ``load_panel`` (series into a long
panel), ``union``, ``join``, ``pivot``, ``event_window_return``,
``event_time_overlay`` and ``select`` (charts).
"""

from __future__ import annotations

import textwrap

from ..plan.model import Task

# The single source of truth for what a plan may ask for. The planner is given
# this verbatim, so a plan cannot name an operation nothing can compile.
OP_REFERENCE = """\
table                 {"kind": "table", "table": "<reference table name>"}
                      reads a reference table (markets, episodes, calendar) as of
                      the knowledge date. data_ingestion only.
load_panel            {"kind": "load_panel", "entity_col": "...", "value_col": "...",
                       "entities": {"<series_id>": "<entity label>", ...}}
                      loads series into a long panel: date, <entity_col>,
                      <value_col>. data_ingestion only; every series id must be
                      listed in series_inputs too.
union                 {"kind": "union"}  concatenates all upstream frames.
aggregate             {"kind": "aggregate", "by": ["asset_class"],
                       "aggs": {"avg_return": ["return_pct", "mean"],
                                "n_markets": ["market_id", "count"]}}
                      group and reduce. One upstream. Output columns are exactly
                      `by` plus the keys of `aggs`.
filter                {"kind": "filter", "column": "episode",
                       "values": ["russia_ukraine_2022"]}
                      keeps only rows whose column is in values. One upstream.
join                  {"kind": "join", "on": ["col"], "how": "inner"}  two upstreams.
pivot                 {"kind": "pivot", "index": ["col"], "columns": "col",
                       "values": "col", "prefix": "ret_", "keep": ["col"]}
event_window_return   {"kind": "event_window_return", "entity_col": "...",
                       "price_col": "...", "window_days": 20, "out_col": "..."}
                      upstream order: (price panel, episode spine).
event_time_overlay    {"kind": "event_time_overlay", "entity_col": "...",
                       "value_col": "...", "pre_months": 18, "post_months": 18}
                      upstream order: (indicator panel, episode spine).
select                {"kind": "select", "limit": 30, "dropna": true}
                      chart tasks only: pick declared columns from one upstream,
                      order by the task's `sort`, optionally drop incomplete rows.
"""


def _cols(task: Task) -> str:
    return "[" + ", ".join(repr(c) for c in task.column_names) + "]"


class ReferenceCodegen:
    """Compiles the structured `op` spec of a task into pandas code."""

    name = "reference"

    def generate(
        self, task: Task, upstream: dict[str, list[dict]], as_of: str = ""
    ) -> str:
        op = dict(task.op or {})
        kind = op.get("kind")
        fn = getattr(self, f"_op_{kind}", None)
        if fn is None:
            raise NotImplementedError(
                f"reference backend cannot compile op kind '{kind}' "
                f"(task '{task.name}'); use the LLM backend or add an op compiler"
            )
        body = textwrap.dedent(fn(task, op)).strip("\n")
        params = ", ".join(f"{d}: pd.DataFrame" for d in task.depends_on)
        return (
            f"def {task.name}({params}) -> pd.DataFrame:\n"
            + textwrap.indent(body, "    ")
            + "\n"
        )

    # -- data ingestion ---------------------------------------------------
    def _op_table(self, task: Task, op: dict) -> str:
        return f"""
        out = load_table({op["table"]!r}).copy()
        out = out[{_cols(task)}]
        return out.sort_values({task.index!r}).reset_index(drop=True)
        """

    def _op_load_panel(self, task: Task, op: dict) -> str:
        entity_col = op["entity_col"]
        value_col = op["value_col"]
        mapping = op["entities"]  # series_id -> entity label
        return f"""
        mapping = {mapping!r}
        frames = []
        for series_id, entity in mapping.items():
            s = load_series(series_id)
            frames.append(pd.DataFrame({{
                'date': s.index,
                {entity_col!r}: entity,
                {value_col!r}: s.to_numpy(dtype='float64'),
            }}))
        out = pd.concat(frames, ignore_index=True)
        out = out[{_cols(task)}]
        return out.sort_values({task.index!r}).reset_index(drop=True)
        """

    # -- table logic ------------------------------------------------------
    def _op_union(self, task: Task, op: dict) -> str:
        args = ", ".join(task.depends_on)
        return f"""
        out = pd.concat([{args}], ignore_index=True)
        out = out[{_cols(task)}]
        return out.sort_values({task.index!r}).reset_index(drop=True)
        """

    def _op_event_window_return(self, task: Task, op: dict) -> str:
        prices, episodes = task.depends_on
        return f"""
        px = {prices}.copy()
        px['date'] = pd.to_datetime(px['date'])
        ep = {episodes}.copy()
        ep['start_date'] = pd.to_datetime(ep['start_date'])
        rows = []
        for _, e in ep.iterrows():
            t0 = e['start_date']
            t1 = t0 + pd.Timedelta(days={op["window_days"]})
            win = px[(px['date'] >= t0) & (px['date'] <= t1)]
            for entity, g in win.groupby({op["entity_col"]!r}, sort=True):
                g = g.sort_values('date')
                if len(g) < 2:
                    continue
                first = float(g[{op["price_col"]!r}].iloc[0])
                last = float(g[{op["price_col"]!r}].iloc[-1])
                if first == 0.0:
                    continue
                rows.append({{
                    {op["entity_col"]!r}: entity,
                    'episode': e['episode'],
                    {op["out_col"]!r}: last / first - 1.0,
                }})
        out = pd.DataFrame(rows)
        out = out[{_cols(task)}]
        return out.sort_values({task.index!r}).reset_index(drop=True)
        """

    def _op_filter(self, task: Task, op: dict) -> str:
        src = task.depends_on[0]
        col, values = op["column"], op["values"]
        return f"""
        out = {src}.copy()
        out = out[out[{col!r}].isin({list(values)!r})]
        out = out[{_cols(task)}]
        return out.sort_values({task.index!r}).reset_index(drop=True)
        """

    def _op_aggregate(self, task: Task, op: dict) -> str:
        src = task.depends_on[0]
        by, aggs = op["by"], op["aggs"]  # {"out_col": ["src_col", "mean"]}
        spec = {out: (col, how) for out, (col, how) in aggs.items()}
        return f"""
        out = {src}.groupby({by!r}, as_index=False).agg(
            **{{k: pd.NamedAgg(column=v[0], aggfunc=v[1]) for k, v in {spec!r}.items()}})
        out = out[{_cols(task)}]
        return out.sort_values({task.index!r}).reset_index(drop=True)
        """

    def _op_join(self, task: Task, op: dict) -> str:
        left, right = task.depends_on
        return f"""
        out = {left}.merge({right}, on={op["on"]!r}, how={op.get("how", "inner")!r})
        out = out[{_cols(task)}]
        return out.sort_values({task.index!r}).reset_index(drop=True)
        """

    def _op_pivot(self, task: Task, op: dict) -> str:
        src = task.depends_on[0]
        keep = op.get("keep", [])
        return f"""
        src = {src}.copy()
        wide = src.pivot_table(index={op["index"]!r}, columns={op["columns"]!r},
                               values={op["values"]!r}, aggfunc='first')
        wide.columns = [{op["prefix"]!r} + str(c) for c in wide.columns]
        wide = wide.reset_index()
        extra = src[{op["index"]!r} + {keep!r}].drop_duplicates({op["index"]!r})
        out = wide.merge(extra, on={op["index"]!r}, how='left')
        out = out[{_cols(task)}]
        return out.sort_values({task.index!r}).reset_index(drop=True)
        """

    def _op_event_time_overlay(self, task: Task, op: dict) -> str:
        panel, episodes = task.depends_on
        return f"""
        pn = {panel}.copy()
        pn['date'] = pd.to_datetime(pn['date'])
        ep = {episodes}.copy()
        ep['start_date'] = pd.to_datetime(ep['start_date'])
        rows = []
        for _, e in ep.iterrows():
            t0 = e['start_date']
            lo = t0 - pd.DateOffset(months={op["pre_months"]})
            hi = t0 + pd.DateOffset(months={op["post_months"]})
            win = pn[(pn['date'] >= lo) & (pn['date'] <= hi)]
            for indicator, g in win.groupby({op["entity_col"]!r}, sort=True):
                g = g.sort_values('date')
                offs = ((g['date'].dt.year - t0.year) * 12
                        + (g['date'].dt.month - t0.month))
                for off, val in zip(offs.to_numpy(), g[{op["value_col"]!r}].to_numpy()):
                    rows.append({{
                        {op["entity_col"]!r}: indicator,
                        'episode': e['episode'],
                        'month_offset': int(off),
                        {op["value_col"]!r}: float(val),
                    }})
        out = pd.DataFrame(rows)
        out = out.groupby({task.index!r}, as_index=False)[{op["value_col"]!r}].mean()
        out = out[{_cols(task)}]
        return out.sort_values({task.index!r}).reset_index(drop=True)
        """

    # -- charts -----------------------------------------------------------
    def _op_select(self, task: Task, op: dict) -> str:
        src = task.depends_on[0]
        if task.sort:
            sort_by = [c for c, _ in task.sort]
            asc = [bool(a) for _, a in task.sort]
        else:
            sort_by = op.get("sort_by") or task.index
            asc = op.get("ascending", True)
        limit = op.get("limit")
        tail = f"\n        out = out.head({limit})" if limit else ""
        dropna = (
            (
                "\n        out = out.dropna(subset=%r)"
                % [c.name for c in task.columns if not c.nullable]
            )
            if op.get("dropna")
            else ""
        )
        return f"""
        out = {src}.copy()
        out = out[{_cols(task)}]{dropna}
        out = out.sort_values({sort_by!r}, ascending={asc!r}).reset_index(drop=True){tail}
        return out
        """


# --------------------------------------------------------------------------
# LLM backend
# --------------------------------------------------------------------------
