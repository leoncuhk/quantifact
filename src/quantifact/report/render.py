"""Interactive report renderer.

Charts are emitted as inline SVG from an explicit chart spec, not chosen by a
model: one less source of nondeterminism, and the same visual language every
time. Every chart carries its underlying dataframe as CSV so the report can
hand its data to another tool, and every chart links to the task and the
generated code that produced it (diagnosability).

Output is a single self-contained HTML file: no external CSS, JS or fonts.
"""

from __future__ import annotations

import html
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from ..contracts.pointintime import describe
from ..harness.execute import RunResult
from ..plan.model import AnalysisPlan, Task
from ..review.checks import Finding

PALETTE = ["#3b6fd4", "#d97b28", "#3f9e6a", "#b04a6a", "#7b5bd6", "#2f8f9d"]


# --------------------------------------------------------------------------
# SVG primitives
# --------------------------------------------------------------------------

@dataclass
class Scale:
    lo: float
    hi: float
    px0: float
    px1: float

    def __post_init__(self) -> None:
        if self.hi == self.lo:
            self.hi = self.lo + 1.0

    def __call__(self, v: float) -> float:
        return self.px0 + (v - self.lo) / (self.hi - self.lo) * (self.px1 - self.px0)

    def ticks(self, n: int = 5) -> list[float]:
        step = (self.hi - self.lo) / (n - 1)
        return [self.lo + i * step for i in range(n)]


def _fmt(v: float, pct: bool = False) -> str:
    if pct:
        return f"{v * 100:.0f}%"
    if abs(v) >= 1000 or (abs(v) < 0.01 and v != 0):
        return f"{v:.3g}"
    return f"{v:.2f}"


def _pad(values: list[float]) -> tuple[float, float]:
    lo, hi = min(values), max(values)
    if lo == hi:
        return lo - 1, hi + 1
    m = (hi - lo) * 0.08
    return lo - m, hi + m


def _axes(x: Scale, y: Scale, w: float, h: float, *, pct_x: bool, pct_y: bool,
          xlabel: str, ylabel: str) -> str:
    parts = [f'<rect class="plot-bg" x="{x.px0}" y="{y.px1}" '
             f'width="{x.px1 - x.px0}" height="{y.px0 - y.px1}"/>']
    for t in y.ticks():
        py = y(t)
        parts.append(f'<line class="grid" x1="{x.px0}" y1="{py:.1f}" '
                     f'x2="{x.px1}" y2="{py:.1f}"/>')
        parts.append(f'<text class="tick" x="{x.px0 - 6}" y="{py + 3.5:.1f}" '
                     f'text-anchor="end">{_fmt(t, pct_y)}</text>')
    for t in x.ticks(4):
        px = x(t)
        parts.append(f'<text class="tick" x="{px:.1f}" y="{y.px0 + 14}" '
                     f'text-anchor="middle">{_fmt(t, pct_x)}</text>')
    if min(y.lo, y.hi) <= 0 and max(y.lo, y.hi) >= 0:
        parts.append(f'<line class="zero" x1="{x.px0}" y1="{y(0):.1f}" '
                     f'x2="{x.px1}" y2="{y(0):.1f}"/>')
    if min(x.lo, x.hi) <= 0 and max(x.lo, x.hi) >= 0:
        parts.append(f'<line class="zero" x1="{x(0):.1f}" y1="{y.px1}" '
                     f'x2="{x(0):.1f}" y2="{y.px0}"/>')
    parts.append(f'<text class="axis-label" x="{(x.px0 + x.px1) / 2:.1f}" '
                 f'y="{y.px0 + 30}" text-anchor="middle">{html.escape(xlabel)}</text>')
    parts.append(f'<text class="axis-label" transform="rotate(-90 12 '
                 f'{(y.px0 + y.px1) / 2:.1f})" x="12" '
                 f'y="{(y.px0 + y.px1) / 2:.1f}" text-anchor="middle">'
                 f'{html.escape(ylabel)}</text>')
    return "".join(parts)


def _scatter_panel(df: pd.DataFrame, spec: dict, w: int, h: int,
                   title: str | None = None) -> str:
    xcol, ycol = spec["x"], spec["y"]
    xs = [float(v) for v in df[xcol]]
    ys = [float(v) for v in df[ycol]]
    if not xs:
        return f'<svg width="{w}" height="{h}"></svg>'
    x = Scale(*_pad(xs), 52, w - 14)
    y = Scale(*_pad(ys), h - 40, 26)
    pct = bool(spec.get("percent", True))
    out = [f'<svg viewBox="0 0 {w} {h}" width="100%" preserveAspectRatio="xMidYMid meet">']
    if title:
        out.append(f'<text class="panel-title" x="{w / 2}" y="16" '
                   f'text-anchor="middle">{html.escape(title)}</text>')
    out.append(_axes(x, y, w, h, pct_x=pct, pct_y=pct,
                     xlabel=spec.get("xlabel", xcol), ylabel=spec.get("ylabel", ycol)))
    label = spec.get("label")
    color_by = spec.get("color_by")
    cats = sorted(df[color_by].unique()) if color_by and color_by in df else []
    for i, row in enumerate(df.itertuples(index=False)):
        cx, cy = x(float(getattr(row, xcol))), y(float(getattr(row, ycol)))
        color = PALETTE[cats.index(getattr(row, color_by)) % len(PALETTE)] if cats else PALETTE[0]
        tip = html.escape(str(getattr(row, label))) if label else f"{i}"
        out.append(f'<circle class="pt" cx="{cx:.1f}" cy="{cy:.1f}" r="3.4" '
                   f'fill="{color}"><title>{tip}: '
                   f'{_fmt(float(getattr(row, xcol)), pct)} → '
                   f'{_fmt(float(getattr(row, ycol)), pct)}</title></circle>')
    # ols fit line, drawn only when it means something
    if len(xs) > 2:
        n = len(xs)
        mx, my = sum(xs) / n, sum(ys) / n
        sxx = sum((v - mx) ** 2 for v in xs)
        if sxx > 0:
            b = sum((xs[i] - mx) * (ys[i] - my) for i in range(n)) / sxx
            a = my - b * mx
            sst = sum((v - my) ** 2 for v in ys)
            ssr = sum((ys[i] - (a + b * xs[i])) ** 2 for i in range(n))
            r2 = 1 - ssr / sst if sst else 0.0
            out.append(f'<line class="fit" x1="{x(x.lo):.1f}" y1="{y(a + b * x.lo):.1f}" '
                       f'x2="{x(x.hi):.1f}" y2="{y(a + b * x.hi):.1f}"/>')
            out.append(f'<text class="r2" x="{w - 18}" y="{34}" text-anchor="end">'
                       f'R² = {r2:.3f}</text>')
    out.append("</svg>")
    return "".join(out)


def _line_panel(df: pd.DataFrame, spec: dict, w: int, h: int,
                title: str | None = None) -> str:
    xcol, ycol, scol = spec["x"], spec["y"], spec.get("series")
    if df.empty:
        return f'<svg width="{w}" height="{h}"></svg>'
    xs = [float(v) for v in df[xcol]]
    ys = [float(v) for v in df[ycol]]
    x = Scale(min(xs), max(xs), 52, w - 14)
    y = Scale(*_pad(ys), h - 40, 26)
    out = [f'<svg viewBox="0 0 {w} {h}" width="100%" preserveAspectRatio="xMidYMid meet">']
    if title:
        out.append(f'<text class="panel-title" x="{w / 2}" y="16" '
                   f'text-anchor="middle">{html.escape(title)}</text>')
    out.append(_axes(x, y, w, h, pct_x=False, pct_y=bool(spec.get("percent", False)),
                     xlabel=spec.get("xlabel", xcol), ylabel=spec.get("ylabel", ycol)))
    groups = list(df.groupby(scol, sort=True)) if scol else [(None, df)]
    for i, (name, g) in enumerate(groups):
        g = g.sort_values(xcol)
        pts = " ".join(f"{x(float(a)):.1f},{y(float(b)):.1f}"
                       for a, b in zip(g[xcol], g[ycol], strict=False))
        color = PALETTE[i % len(PALETTE)]
        out.append(f'<polyline class="ln" points="{pts}" stroke="{color}">'
                   f'<title>{html.escape(str(name))}</title></polyline>')
    out.append("</svg>")
    return "".join(out)


def _bar_panel(df: pd.DataFrame, spec: dict, w: int, h: int) -> str:
    xcol, ycol = spec["x"], spec["y"]
    ys = [float(v) for v in df[ycol]]
    if not ys:
        return f'<svg width="{w}" height="{h}"></svg>'
    y = Scale(*_pad(ys + [0.0]), h - 46, 20)
    n = len(df)
    left, right = 52, w - 14
    bw = (right - left) / max(n, 1) * 0.7
    out = [f'<svg viewBox="0 0 {w} {h}" width="100%" preserveAspectRatio="xMidYMid meet">']
    out.append(f'<rect class="plot-bg" x="{left}" y="{y.px1}" '
               f'width="{right - left}" height="{y.px0 - y.px1}"/>')
    for t in y.ticks():
        py = y(t)
        out.append(f'<line class="grid" x1="{left}" y1="{py:.1f}" x2="{right}" y2="{py:.1f}"/>')
        out.append(f'<text class="tick" x="{left - 6}" y="{py + 3.5:.1f}" '
                   f'text-anchor="end">{_fmt(t, bool(spec.get("percent", True)))}</text>')
    y0 = y(0)
    for i, row in enumerate(df.itertuples(index=False)):
        v = float(getattr(row, ycol))
        cx = left + (right - left) * (i + 0.5) / n
        top, bot = min(y(v), y0), max(y(v), y0)
        color = PALETTE[2] if v >= 0 else PALETTE[3]
        out.append(f'<rect class="bar" x="{cx - bw / 2:.1f}" y="{top:.1f}" '
                   f'width="{bw:.1f}" height="{max(bot - top, 0.5):.1f}" fill="{color}">'
                   f'<title>{html.escape(str(getattr(row, xcol)))}: '
                   f'{_fmt(v, True)}</title></rect>')
        out.append(f'<text class="bar-label" x="{cx:.1f}" y="{h - 20}" '
                   f'text-anchor="end" transform="rotate(-35 {cx:.1f} {h - 20})">'
                   f'{html.escape(str(getattr(row, xcol))[:14])}</text>')
    out.append("</svg>")
    return "".join(out)


def _table_panel(df: pd.DataFrame, spec: dict) -> str:
    color_cols = [c for c in spec.get("color_by", []) if c in df.columns]
    bounds = {c: (float(df[c].min()), float(df[c].max())) for c in color_cols
              if len(df) and pd.api.types.is_numeric_dtype(df[c])}
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in df.columns)
    rows = []
    for row in df.itertuples(index=False):
        tds = []
        for col, val in zip(df.columns, row, strict=False):
            style = ""
            text = html.escape(str(val))
            if col in bounds and pd.notna(val):
                lo, hi = bounds[col]
                span = max(abs(lo), abs(hi)) or 1.0
                a = min(abs(float(val)) / span, 1.0) * 0.42
                hue = "142" if float(val) >= 0 else "353"
                style = f' style="background:hsl({hue} 62% 46% / {a:.3f})"'
                text = _fmt(float(val), bool(spec.get("percent", True)))
            tds.append(f"<td{style}>{text}</td>")
        rows.append("<tr>" + "".join(tds) + "</tr>")
    return (f'<div class="tbl-wrap"><table class="data"><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def render_chart(task: Task, df: pd.DataFrame) -> str:
    spec = dict(task.chart_spec or {})
    kind = spec.get("kind")
    facet = spec.get("facet")
    if kind == "table":
        return _table_panel(df, spec)
    if facet and facet in df.columns:
        panels = []
        for name, g in df.groupby(facet, sort=True):
            fn = _scatter_panel if kind == "scatter" else _line_panel
            panels.append(f'<div class="panel">{fn(g, spec, 420, 260, str(name))}</div>')
        return f'<div class="facets">{"".join(panels)}</div>'
    if kind == "scatter":
        return f'<div class="panel wide">{_scatter_panel(df, spec, 900, 420)}</div>'
    if kind == "line":
        return f'<div class="panel wide">{_line_panel(df, spec, 900, 360)}</div>'
    if kind == "bar":
        return f'<div class="panel wide">{_bar_panel(df, spec, 900, 380)}</div>'
    return _table_panel(df, spec)


# --------------------------------------------------------------------------
# Page
# --------------------------------------------------------------------------

CSS = """
:root{--bg:#ffffff;--panel:#f7f8fa;--ink:#12161c;--muted:#5a6472;--line:#dfe3ea;
--accent:#3b6fd4;--good:#2f8f5b;--warn:#b8791f;--bad:#c0392b;--mono:ui-monospace,
SFMono-Regular,Menlo,monospace}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#0f1216;
--panel:#161b22;--ink:#e7ecf3;--muted:#97a3b4;--line:#252c36;--accent:#6f9bf0}}
:root[data-theme=dark]{--bg:#0f1216;--panel:#161b22;--ink:#e7ecf3;--muted:#97a3b4;
--line:#252c36;--accent:#6f9bf0}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:1040px;margin:0 auto;padding:32px 20px 80px}
h1{font-size:26px;margin:0 0 6px}h2{font-size:19px;margin:34px 0 10px}
h3{font-size:15px;margin:0 0 8px}
.sub{color:var(--muted);margin:0 0 22px}
.asof{margin-top:-14px;font-size:13px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;
padding:16px 18px;margin:14px 0}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.kpi b{display:block;font-size:20px}
.kpi span{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.04em}
ul{margin:6px 0 0 18px;padding:0}li{margin:3px 0}
.tbl-wrap{overflow-x:auto}
table.data{border-collapse:collapse;font-size:13px;width:100%}
table.data th,table.data td{border-bottom:1px solid var(--line);padding:5px 9px;
text-align:right;white-space:nowrap}
table.data th:first-child,table.data td:first-child{text-align:left}
table.data th{color:var(--muted);font-weight:600;text-align:right}
.facets{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:10px}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:6px}
.plot-bg{fill:transparent}.grid{stroke:var(--line);stroke-width:1}
.zero{stroke:var(--muted);stroke-width:1;stroke-dasharray:3 3;opacity:.7}
.tick,.bar-label{fill:var(--muted);font-size:10px}
.axis-label{fill:var(--muted);font-size:11px}
.panel-title{fill:var(--ink);font-size:12px;font-weight:600}
.r2{fill:var(--muted);font-size:11px}
.fit{stroke:var(--muted);stroke-width:1.4;stroke-dasharray:5 4;opacity:.9}
.ln{fill:none;stroke-width:1.8}
.pt{opacity:.85}.pt:hover{opacity:1;r:5}
.trace{font-family:var(--mono);font-size:12px}
.tag{display:inline-block;font-size:11px;padding:1px 7px;border-radius:20px;
border:1px solid var(--line);color:var(--muted)}
.hit{color:var(--good);border-color:var(--good)}
.sev-blocking{color:var(--bad)}.sev-warning{color:var(--warn)}.sev-note{color:var(--muted)}
details{margin-top:8px}summary{cursor:pointer;color:var(--muted);font-size:13px}
pre{overflow-x:auto;background:var(--bg);border:1px solid var(--line);border-radius:8px;
padding:12px;font-family:var(--mono);font-size:12px;line-height:1.45}
button.dl{font:inherit;font-size:12px;color:var(--accent);background:none;
border:1px solid var(--line);border-radius:6px;padding:3px 10px;cursor:pointer}
.chart-head{display:flex;justify-content:space-between;align-items:center;gap:12px;
margin:22px 0 6px}
"""

JS = """
function dl(id,name){const t=document.getElementById(id).textContent;
const b=new Blob([t],{type:'text/csv'});const a=document.createElement('a');
a.href=URL.createObjectURL(b);a.download=name;a.click();URL.revokeObjectURL(a.href);}
"""


def _kpi(label: str, value: str) -> str:
    return f'<div class="kpi"><b>{html.escape(value)}</b><span>{html.escape(label)}</span></div>'


def render_report(plan: AnalysisPlan, result: RunResult, findings: list[Finding],
                  codes: dict[str, str], out_path: str | Path,
                  meta: dict[str, Any] | None = None) -> Path:
    meta = meta or {}
    parts: list[str] = []
    parts.append(f"<h1>{html.escape(plan.question)}</h1>")
    parts.append('<p class="sub">quantifact · '
                 f'{len(plan.tasks)} tasks in {len(result.layers)} layers · '
                 f'{result.cache_hits}/{len(result.traces)} served from cache · '
                 f'{result.wall_seconds:.2f}s</p>')
    if plan.as_of:
        # The vintage belongs at the top of the page, not in an appendix: a
        # reader should never have to ask what this analysis was allowed to know.
        parts.append(f'<p class="sub asof">{html.escape(describe(plan.as_of))}</p>')

    parts.append('<div class="kpis">')
    if plan.as_of:
        parts.append(_kpi("knowledge date", plan.as_of))
    parts.append(_kpi("tasks", str(len(plan.tasks))))
    parts.append(_kpi("layers", str(len(result.layers))))
    parts.append(_kpi("cache hits", f"{result.cache_hits}/{len(result.traces)}"))
    parts.append(_kpi("execution", f"{result.wall_seconds:.2f}s"))
    for k, v in meta.items():
        parts.append(_kpi(k, str(v)))
    parts.append("</div>")

    if plan.resolved_assumptions:
        parts.append('<div class="card"><h3>Resolved assumptions</h3><ul>')
        parts += [f"<li>{html.escape(a)}</li>" for a in plan.resolved_assumptions]
        parts.append("</ul></div>")

    if findings:
        parts.append('<h2>Self review</h2><div class="card"><ul>')
        for f in findings:
            parts.append(f'<li class="sev-{f.severity}">[{f.severity}] '
                         f'<code>{html.escape(f.task)}</code> — {html.escape(f.message)}</li>')
        parts.append("</ul></div>")

    for i, task in enumerate(plan.charts()):
        df = result.frames.get(task.name)
        if df is None:
            continue
        csv_id = f"csv{i}"
        parts.append('<div class="chart-head">'
                     f'<h2 style="margin:0">{html.escape(task.chart_spec.get("title", task.name))}</h2>'
                     f'<button class="dl" onclick="dl(\'{csv_id}\',\'{task.name}.csv\')">'
                     'Export CSV</button></div>')
        if task.description:
            parts.append(f'<p class="sub" style="margin:0 0 8px">'
                         f'{html.escape(task.description)}</p>')
        parts.append(render_chart(task, df))
        parts.append(f'<details><summary>task, code and data — {task.name}</summary>'
                     f'<pre>{html.escape(codes.get(task.name, ""))}</pre>'
                     f'<pre id="{csv_id}" style="max-height:220px">'
                     f'{html.escape(df.to_csv(index=False))}</pre></details>')

    parts.append("<h2>Execution trace</h2>")
    rows = "".join(
        f"<tr><td>{html.escape(t.task)}</td>"
        f'<td class="trace">{t.cache_key[:10]}</td>'
        f'<td><span class="tag {"hit" if t.cached else ""}">'
        f'{"cache" if t.cached else "computed"}</span></td>'
        f"<td>{t.seconds * 1000:.1f} ms</td><td>{t.rows}</td></tr>"
        for t in result.traces)
    parts.append('<div class="tbl-wrap"><table class="data"><thead><tr>'
                 "<th>task</th><th>cache key</th><th>status</th><th>time</th>"
                 "<th>rows</th></tr></thead><tbody>" + rows + "</tbody></table></div>")

    parts.append('<details><summary>full plan (json)</summary><pre>'
                 + html.escape(json.dumps(plan.to_dict(), indent=2, ensure_ascii=False))
                 + "</pre></details>")

    page = (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{html.escape(plan.question[:80])}</title>"
            f"<style>{CSS}</style></head><body><div class='wrap'>"
            + "".join(parts) + f"</div><script>{JS}</script></body></html>")
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(page)
    return p
