"""Chat-side planning: clarify, bind, then compile a plan.

Two things carry the weight here.

**Clarifying questions exist to remove ambiguities that would fork the plan** —
the knowledge date, the episode set, the response window, the indicator set —
and every question carries a recommended answer drawn from domain context. A
question without a good default gets skipped, and a skipped question buys
nothing.

**Every ingestion task is bound to concrete series ids at plan time**, through
the inspection-aware search. Late binding moves failures into execution, where
they are more expensive and less legible.

``RulePlanner`` is deterministic and needs no API key: it is the reference
implementation the benchmarks run against. Lessons learned through the teach
loop are injected here and change the plan it emits.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from .contracts.pointintime import LookAheadError
from .data.registry import SeriesMeta
from .data.search import SearchHit, SeriesSearch, SeriesStore
from .learn.lessons import Lesson
from .plan.model import AnalysisPlan, ColumnSpec, Task, parse_date

DEFAULT_AS_OF = "2026-08-01"

# How stale the newest observation of a series may be and still count as
# covering the knowledge date. A monthly series published with a lag simply has
# nothing for the last few weeks; demanding otherwise would reject every
# correct series and accept only ones that leak.
STALENESS_DAYS = {"D": 7, "W": 21, "M": 95, "Q": 200, "A": 500}


@dataclass
class Clarification:
    id: str
    question: str
    why: str
    options: list[dict[str, Any]]

    @property
    def recommended(self) -> Any:
        return next(o["value"] for o in self.options if o.get("recommended"))


@dataclass
class BindingTrace:
    """What the search looked at, and why it accepted or rejected it."""
    requirement: str
    query: str
    chosen: str | None
    considered: list[dict[str, Any]] = field(default_factory=list)


# label, query, unit, plausible value range for the concept
MACRO_REQUIREMENTS = [
    ("us_real_yield", "US 10y real yield", "%", (-6.0, 12.0)),
    ("us_output_gap", "US output gap potential", "% of potential", (-15.0, 15.0)),
    ("us_headline_cpi", "US headline CPI year over year", "%", (-6.0, 20.0)),
    ("us_core_cpi", "US core CPI year over year", "%", (-6.0, 20.0)),
    ("us_net_energy_trade", "US net energy trade balance", "% of GDP", (-15.0, 15.0)),
]

DATE_COL = ColumnSpec("date", "observation date", "datetime64[ns]",
                      role="observation_date")


class RulePlanner:
    def __init__(self, adapter: Any, entitlements: tuple[str, ...] = (),
                 lessons: list[Lesson] | None = None):
        self.adapter = adapter
        self.search = SeriesSearch(_as_store(adapter), entitlements)
        self.lessons = lessons or []
        self.bindings: list[BindingTrace] = []

    # ------------------------------------------------------------- clarify
    def clarify(self, prompt: str) -> list[Clarification]:
        episodes = [row["episode"] for _, row in
                    self.adapter.read_table("episodes", as_of=DEFAULT_AS_OF).iterrows()]
        return [
            Clarification(
                id="as_of",
                question="As of when should this be answered?",
                why="The knowledge date decides what the analysis is allowed to "
                    "know. Answering 'today' for a historical question is how "
                    "look-ahead gets into research.",
                options=[
                    {"label": f"Today ({DEFAULT_AS_OF})", "value": DEFAULT_AS_OF,
                     "recommended": True},
                    {"label": "The eve of the 2026 escalation (2026-06-14)",
                     "value": "2026-06-14"},
                    {"label": "Year-end 2025 (2025-12-31)", "value": "2025-12-31"},
                ]),
            Clarification(
                id="episodes",
                question="Which historical episodes should today's shock be "
                         "compared against?",
                why="The episode set defines every downstream comparison; choosing "
                    "it after seeing results is what makes research unreproducible.",
                options=[
                    {"label": f"All known oil supply shocks ({len(episodes)})",
                     "value": episodes, "recommended": True},
                    {"label": "Only the two most commonly cited precedents",
                     "value": episodes[:2]},
                    {"label": "Post-2020 episodes only", "value": episodes[1:]},
                ]),
            Clarification(
                id="window_days",
                question="Over what window should the market response be measured?",
                why="Five days measures the impact reaction; a quarter measures the "
                    "regime. Mixing them across episodes is the classic error here.",
                options=[
                    {"label": "20 calendar days after the episode start",
                     "value": 20, "recommended": True},
                    {"label": "5 calendar days (impact only)", "value": 5},
                    {"label": "90 calendar days (full transmission)", "value": 90},
                ]),
            Clarification(
                id="indicators",
                question="Which macro conditions should be compared going into "
                         "each episode?",
                why="'Macro conditions' is under-specified: real yields, output gap, "
                    "trade balances, inflation, or a dozen other things.",
                options=[
                    {"label": "Real yield, output gap, headline CPI, core CPI, "
                              "net energy trade (5 indicators)",
                     "value": [r[0] for r in MACRO_REQUIREMENTS], "recommended": True},
                    {"label": "Three classics: real yield, headline CPI, output gap",
                     "value": ["us_real_yield", "us_headline_cpi", "us_output_gap"]},
                ]),
        ]

    def defaults(self) -> dict[str, Any]:
        return {c.id: c.recommended for c in self.clarify("")}

    # ------------------------------------------------------------- binding
    def bind_series(self, requirement: str, query: str, unit: str,
                    prior: tuple[float, float], as_of: str,
                    frequency: str = "M",
                    covers: tuple[str, str] | None = None) -> str:
        if covers is None:
            slack = timedelta(days=STALENESS_DAYS.get(frequency, 95))
            covers = ("1990-01-01", str(parse_date(as_of) - slack))
        hits: list[SearchHit] = self.search.search(
            query, k=8, frequency=frequency, unit=unit, prior=prior, covers=covers)
        trace = BindingTrace(requirement=requirement, query=query, chosen=None)
        for h in hits:
            trace.considered.append({
                "series_id": h.meta.series_id, "score": round(h.recall_score, 3),
                "accepted": h.accepted, "reasons": h.reasons})
        # Outputs of earlier analyses are searchable on purpose, but a vendor or
        # internally-modelled series wins a tie: binding an input to a previous
        # run's output silently chains analyses together.
        accepted = sorted((h for h in hits if h.accepted),
                          key=lambda h: (h.meta.source == "quantifact-analysis",
                                         -h.recall_score))
        if not accepted:
            self.bindings.append(trace)
            raise LookupError(
                f"no series satisfies requirement '{requirement}' (query={query!r}); "
                + ("candidates rejected: " + "; ".join(
                    f"{c['series_id']}: {c['reasons'][0]}" for c in trace.considered)
                   if trace.considered else "nothing was recalled"))
        trace.chosen = accepted[0].meta.series_id
        self.bindings.append(trace)
        return trace.chosen

    def bind_universe(self, as_of: str) -> dict[str, str]:
        """Universe from the spine table, not from whatever files exist.

        Taking it as of the knowledge date is what keeps it survivorship-free:
        a name that was alive then is included even if it has since died, and a
        name that had not yet listed is not.
        """
        markets = self.adapter.read_table("markets", as_of=as_of)
        catalog = {m.series_id for m in self.adapter.catalog()
                   if self.search.visible(m)}
        out = {}
        for market_id in markets["market_id"]:
            sid = f"MKT.{market_id}.TRI"
            if sid in catalog:
                out[sid] = market_id
        return dict(sorted(out.items()))

    # ---------------------------------------------------------------- plan
    def plan(self, prompt: str, answers: dict[str, Any] | None = None) -> AnalysisPlan:
        given = dict(answers or {})
        a = {**self.defaults(), **given}
        as_of: str = str(a["as_of"])
        window: int = int(a["window_days"])

        # The episode set is derived from the knowledge date unless the caller
        # names one explicitly — and naming an event that had not happened yet
        # is look-ahead, so it is refused rather than quietly dropped.
        episode_rows = self.adapter.read_table("episodes", as_of=as_of)
        visible = list(episode_rows["episode"])
        if "episodes" in given:
            episodes = list(given["episodes"])
            unknown = [e for e in episodes if e not in visible]
            if unknown:
                raise LookAheadError(
                    f"episode(s) {unknown} had not begun as of {as_of}; asking for "
                    "them would be look-ahead")
        else:
            episodes = visible
        indicators: list[str] = list(a["indicators"])
        self.bindings = []

        markets = self.bind_universe(as_of)
        # A survivorship-free universe means younger names simply have no
        # return in older episodes. The expected cell count therefore comes
        # from listing dates, not from a rectangle.
        market_rows = self.adapter.read_table("markets", as_of=as_of)
        starts = {r["episode"]: r["start_date"]
                  for _, r in episode_rows.iterrows() if r["episode"] in episodes}
        listed = {r["market_id"]: r["listed_from"] for _, r in market_rows.iterrows()}
        n_cells = sum(1 for mid in markets.values() for ep in episodes
                      if listed.get(mid) is not None and listed[mid] <= starts[ep])
        tasks: list[Task] = []

        tasks.append(Task(
            name="spine_episodes", type="data_ingestion",
            description="Episode spine: one row per oil supply shock under study.",
            op={"kind": "table", "table": "episodes"},
            index=["episode"], row_expectation="one row per episode",
            sort=[["episode", True]],
            columns=[
                ColumnSpec("episode", "stable episode key", "string", role="entity"),
                ColumnSpec("label", "human readable episode label", "string",
                           role="dimension"),
                ColumnSpec("start_date", "first day of the episode",
                           "datetime64[ns]", role="observation_date"),
                ColumnSpec("oil_shock", "size of the oil supply shock", "float64",
                           "ratio", role="measure"),
            ],
            invariants=[{"kind": "unique", "columns": ["episode"]},
                        {"kind": "row_count", "min": 2},
                        {"kind": "no_future_observations"}]))

        tasks.append(Task(
            name="spine_markets", type="data_ingestion",
            description="Market spine as of the knowledge date: survivorship-free "
                        "universe with each market's asset class.",
            op={"kind": "table", "table": "markets"},
            index=["market_id"], row_expectation="one row per listed market",
            sort=[["market_id", True]],
            columns=[
                ColumnSpec("market_id", "stable market key", "string", role="entity"),
                ColumnSpec("asset_class", "equity/bond/fx/commodity/credit/inflation",
                           "string", role="dimension"),
                ColumnSpec("listed_from", "first date this market existed",
                           "datetime64[ns]", role="dimension"),
            ],
            invariants=[{"kind": "unique", "columns": ["market_id"]},
                        {"kind": "row_count", "min": len(markets),
                         "max": len(markets)}]))

        tasks.append(Task(
            name="market_prices", type="data_ingestion",
            description="Daily total-return index for every market in the universe.",
            series_inputs=list(markets),
            op={"kind": "load_panel", "entity_col": "market_id",
                "value_col": "price", "entities": markets},
            index=["market_id", "date"],
            row_expectation="one row per market per trading day",
            sort=[["market_id", True], ["date", True]],
            columns=[
                DATE_COL,
                ColumnSpec("market_id", "market key", "string", role="entity"),
                ColumnSpec("price", "total return index level", "float64", "index",
                           role="measure"),
            ],
            invariants=[{"kind": "nonnull", "column": "price", "min": 0.999},
                        {"kind": "range", "column": "price", "min": 0.0, "max": 1e9},
                        {"kind": "no_future_observations"}]))

        macro_tasks: list[str] = []
        for label, query, unit, prior in MACRO_REQUIREMENTS:
            if label not in indicators:
                continue
            sid = self.bind_series(label, query, unit, prior, as_of)
            macro_tasks.append(label)
            tasks.append(Task(
                name=label, type="data_ingestion",
                description=f"Monthly {label.replace('_', ' ')} from {sid}.",
                series_inputs=[sid],
                op={"kind": "load_panel", "entity_col": "indicator",
                    "value_col": "value", "entities": {sid: label}},
                index=["indicator", "date"], row_expectation="one row per month",
                sort=[["indicator", True], ["date", True]],
                columns=[
                    DATE_COL,
                    ColumnSpec("indicator", "indicator key", "string", role="entity"),
                    ColumnSpec("value", "indicator value, percent-family unit "
                                        "(see indicator)", "float64", "%",
                               role="measure"),
                ],
                invariants=[{"kind": "nonnull", "column": "value", "min": 0.99},
                            {"kind": "no_future_observations"}]))

        tasks.append(Task(
            name="macro_panel", type="table_logic",
            description="Long panel of every macro indicator used by the dashboard.",
            depends_on=macro_tasks, op={"kind": "union"},
            index=["indicator", "date"],
            row_expectation="one row per indicator per month",
            sort=[["indicator", True], ["date", True]],
            columns=[
                DATE_COL,
                ColumnSpec("indicator", "indicator key", "string", role="entity"),
                ColumnSpec("value", "indicator value, percent-family unit "
                                    "(see indicator)", "float64", "%", role="measure"),
            ],
            invariants=[{"kind": "unique", "columns": ["indicator", "date"]},
                        {"kind": "no_future_observations"}]))

        tasks.append(Task(
            name="market_episode_returns", type="table_logic",
            description=(f"Total return of each market over the {window} calendar "
                         "days following each episode start."),
            depends_on=["market_prices", "spine_episodes"],
            op={"kind": "event_window_return", "entity_col": "market_id",
                "price_col": "price", "window_days": window, "out_col": "return_pct"},
            index=["market_id", "episode"],
            row_expectation="one row per market per episode",
            sort=[["market_id", True], ["episode", True]],
            columns=[
                ColumnSpec("market_id", "market key", "string", role="entity"),
                ColumnSpec("episode", "episode key", "string", role="entity"),
                ColumnSpec("return_pct", f"return over the {window}d window after "
                                         "the episode start", "float64", "ratio",
                           role="measure"),
            ],
            invariants=[{"kind": "unique", "columns": ["market_id", "episode"]},
                        {"kind": "range", "column": "return_pct", "min": -0.95,
                         "max": 3.0},
                        {"kind": "nonnull", "column": "return_pct", "min": 1.0},
                        # every market appears in every episode: a join or window
                        # that silently drops one is the classic failure here
                        {"kind": "row_count", "min": n_cells, "max": n_cells}]))

        tasks.append(Task(
            name="market_action_data", type="table_logic",
            description="Episode returns joined to the asset class of each market.",
            depends_on=["market_episode_returns", "spine_markets"],
            op={"kind": "join", "on": ["market_id"], "how": "inner"},
            index=["market_id", "episode"],
            row_expectation="one row per market per episode",
            sort=[["market_id", True], ["episode", True]],
            columns=[
                ColumnSpec("market_id", "market key", "string", role="entity"),
                ColumnSpec("episode", "episode key", "string", role="entity"),
                ColumnSpec("asset_class", "asset class of the market", "string",
                           role="dimension"),
                ColumnSpec("return_pct", "episode window return", "float64", "ratio",
                           role="measure"),
            ],
            invariants=[{"kind": "unique", "columns": ["market_id", "episode"]},
                        {"kind": "row_count", "min": n_cells, "max": n_cells}]))

        # nullable on purpose: a market that had not listed yet has no return
        # for an older episode, and pretending otherwise would be a lie the
        # contract layer would have to accept
        ret_cols = [ColumnSpec(f"ret_{e}", f"window return during {e}", "float64",
                               "ratio", role="measure", nullable=True)
                    for e in episodes]
        tasks.append(Task(
            name="market_pairwise_returns", type="table_logic",
            description=("Wide pivot of market_action_data: one row per market with "
                         "its return in every episode, used by the scatter grid."),
            depends_on=["market_action_data"],
            op={"kind": "pivot", "index": ["market_id"], "columns": "episode",
                "values": "return_pct", "prefix": "ret_", "keep": ["asset_class"]},
            index=["market_id"], row_expectation="one row per market",
            sort=[["market_id", True]],
            columns=[ColumnSpec("market_id", "market key", "string", role="entity"),
                     ColumnSpec("asset_class", "asset class of the market", "string",
                                role="dimension"),
                     *ret_cols],
            invariants=[{"kind": "unique", "columns": ["market_id"]},
                        {"kind": "row_count", "min": len(markets),
                         "max": len(markets)}]))

        tasks.append(Task(
            name="macro_event_time_overlay", type="table_logic",
            description=("Macro indicators aligned in event time around each episode "
                         "start, from 18 months before to 18 months after."),
            depends_on=["macro_panel", "spine_episodes"],
            op={"kind": "event_time_overlay", "entity_col": "indicator",
                "value_col": "value", "pre_months": 18, "post_months": 18},
            index=["indicator", "episode", "month_offset"],
            row_expectation="one row per indicator per episode per month offset",
            sort=[["indicator", True], ["episode", True], ["month_offset", True]],
            columns=[
                ColumnSpec("indicator", "indicator key", "string", role="entity"),
                ColumnSpec("episode", "episode key", "string", role="entity"),
                ColumnSpec("month_offset", "months relative to episode start",
                           "int64", "months", role="dimension"),
                ColumnSpec("value", "indicator value, percent-family unit "
                                    "(see indicator)", "float64", "%", role="measure"),
            ],
            invariants=[{"kind": "unique",
                         "columns": ["indicator", "episode", "month_offset"]},
                        {"kind": "range", "column": "month_offset", "min": -18,
                         "max": 18}]))

        # ---- charts ------------------------------------------------------
        tasks.append(Task(
            name="market_action_table", type="chart",
            description="Returns by market during each episode, largest moves first.",
            depends_on=["market_action_data"],
            op={"kind": "select", "limit": 30},
            index=["market_id", "episode"],
            row_expectation="one row per market per episode, top 30 by return",
            sort=[["return_pct", False]],
            columns=[
                ColumnSpec("market_id", "market key", "string", role="entity"),
                ColumnSpec("asset_class", "asset class of the market", "string",
                           role="dimension"),
                ColumnSpec("episode", "episode key", "string", role="entity"),
                ColumnSpec("return_pct", "episode window return", "float64", "ratio",
                           role="measure"),
            ],
            chart_spec={"kind": "table", "title": "Market action table",
                        "color_by": ["return_pct"], "percent": True},
            invariants=[{"kind": "row_count", "min": 1, "max": 30}]))

        latest = episodes[-1]
        prior_ep = episodes[1] if len(episodes) > 1 else episodes[0]
        # the scatter needs both coordinates, so markets missing either episode
        # are dropped here — declared, not silently
        scatter_cols = [
            ColumnSpec("market_id", "market key", "string", role="entity"),
            ColumnSpec("asset_class", "asset class of the market", "string",
                       role="dimension"),
            ColumnSpec(f"ret_{prior_ep}", f"window return during {prior_ep}",
                       "float64", "ratio", role="measure"),
            ColumnSpec(f"ret_{latest}", f"window return during {latest}",
                       "float64", "ratio", role="measure")]

        tasks.append(Task(
            name="market_pairwise_scatter", type="chart",
            description=(f"Each market's {prior_ep} response against its {latest} "
                         "response; a steep positive slope would mean today rhymes."),
            depends_on=["market_pairwise_returns"],
            op={"kind": "select", "dropna": True}, index=["market_id"],
            row_expectation="one point per market present in both episodes",
            sort=[["market_id", True]],
            columns=list(scatter_cols),
            chart_spec={"kind": "scatter", "x": f"ret_{prior_ep}",
                        "y": f"ret_{latest}", "label": "market_id",
                        "color_by": "asset_class",
                        "title": f"{prior_ep} vs {latest} — all markets",
                        "xlabel": f"{prior_ep} return",
                        "ylabel": f"{latest} return", "percent": True}))

        tasks.append(Task(
            name="macro_conditions_dashboard", type="chart",
            description=("Macro conditions leading into each episode, aligned on the "
                         "episode start date."),
            depends_on=["macro_event_time_overlay"],
            op={"kind": "select"},
            index=["indicator", "episode", "month_offset"],
            row_expectation="one row per indicator per episode per month offset",
            sort=[["indicator", True], ["episode", True], ["month_offset", True]],
            columns=[
                ColumnSpec("indicator", "indicator key", "string", role="entity"),
                ColumnSpec("episode", "episode key", "string", role="entity"),
                ColumnSpec("month_offset", "months relative to episode start",
                           "int64", "months", role="dimension"),
                ColumnSpec("value", "indicator value, percent-family unit "
                                    "(see indicator)", "float64", "%", role="measure"),
            ],
            chart_spec={"kind": "line", "x": "month_offset", "y": "value",
                        "series": "episode", "facet": "indicator",
                        "title": "US macro conditions — event-time overlay",
                        "xlabel": "months from episode start", "ylabel": "level"}))

        # ---- lesson-gated tasks -----------------------------------------
        if self.lesson_active("per_asset_class_panels",
                              multi_episode=len(episodes) > 1):
            tasks.append(Task(
                name="market_scatter_by_asset_class", type="chart",
                description=("The same comparison broken out by asset class: FX, "
                             "rates, equities and commodities transmit an oil shock "
                             "through different channels, so one pooled scatter "
                             "hides more than it reveals."),
                depends_on=["market_pairwise_returns"],
                op={"kind": "select", "dropna": True}, index=["market_id"],
                row_expectation="one point per market present in both episodes",
                sort=[["asset_class", True], ["market_id", True]],
                columns=list(scatter_cols),
                chart_spec={"kind": "scatter", "x": f"ret_{prior_ep}",
                            "y": f"ret_{latest}", "facet": "asset_class",
                            "label": "market_id",
                            "title": f"{prior_ep} vs {latest} — by asset class",
                            "xlabel": f"{prior_ep} return",
                            "ylabel": f"{latest} return", "percent": True}))

        assumptions = [
            f"Knowledge date (as_of): {as_of} — nothing published later was read",
            f"Universe: {len(markets)} markets listed as of that date "
            "(survivorship-free)",
            f"Episodes compared: {', '.join(episodes)}",
            f"Market response measured over {window} calendar days after each start",
            f"Macro indicators: {', '.join(indicators)}",
            "Macro conditions aligned in event time, -18 to +18 months",
        ]
        for lesson in self.lessons:
            assumptions.append(f"Applied lesson: {lesson.id}")

        return AnalysisPlan(question=prompt, tasks=tasks, as_of=as_of,
                            resolved_assumptions=assumptions)

    # -------------------------------------------------------------- lessons
    def lesson_active(self, effect: str, **features: bool) -> bool:
        for lesson in self.lessons:
            if lesson.effect != effect:
                continue
            if lesson.when and not features.get(lesson.when, False):
                continue
            return True
        return False


def _as_store(adapter: Any) -> SeriesStore:
    """Search works off the catalog; adapters that keep a store expose it."""
    store = getattr(adapter, "store", None)
    if store is not None:
        return store
    return _CatalogOnlyStore(adapter.catalog())


class _CatalogOnlyStore:
    """Minimal store-shaped view over a catalog, for adapters without one."""

    def __init__(self, metas: list[SeriesMeta]):
        self._meta = {m.series_id: m for m in metas}

    def all_meta(self) -> list[SeriesMeta]:
        return [self._meta[k] for k in sorted(self._meta)]

    def meta(self, series_id: str) -> SeriesMeta:
        return self._meta[series_id]

    @property
    def ids(self) -> list[str]:
        return sorted(self._meta)


def default_as_of() -> date:
    return parse_date(DEFAULT_AS_OF)
