# quantifact

**An investment-research agent that has to prove its numbers.**
The model writes the code; the contract decides whether the number counts.

[![CI](https://github.com/leoncuhk/quantifact/actions/workflows/ci.yml/badge.svg)](https://github.com/leoncuhk/quantifact/actions/workflows/ci.yml)
[![Secret scan](https://github.com/leoncuhk/quantifact/actions/workflows/secrets.yml/badge.svg)](https://github.com/leoncuhk/quantifact/actions/workflows/secrets.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](pyproject.toml)
[![License Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

---

## Why

Getting a language model to write analysis code is easy. Getting a desk to
*use* the number that comes out is the hard part, and no amount of model
quality fixes it on its own: the reviewer's question is never "is this
plausible", it is "what exactly did it read, when could it have known it, and
what would have caught it if it were wrong".

quantifact answers that by treating agentic analysis as a **compiler problem**:

1. A question is clarified into an **analysis plan** — an intermediate
   representation with schemas, units, row grain, row order, invariants and a
   **knowledge date**.
2. Every task compiles **in parallel** into exactly one pandas function,
   because a task needs only the *schemas* of its inputs, never their code.
3. **Static analysis** derives the dependency graph from the code and
   cross-checks it against the graph the plan declared.
4. **Layered contracts** run as ordinary Python, so a model cannot skip a check
   it finds inconvenient.
5. A **caching harness** executes the code on the model's behalf — which is
   what makes look-ahead structurally impossible, traces auditable, and the
   second run nearly free.

### Is this the "Pat / Pocket Analyst" architecture?

Yes — quantifact is an independent, open-source implementation of the
investment-research agent architecture that **Bridgewater Associates** described
publicly at **INTERRUPT26**, in the talk about their internal tool **"Pat, the
Pocket Analyst"**: *the plan is the analysis*, a task is a function type
signature, codegen fans out, correctness is enforced by the architecture, the
harness runs the code for the model, and a lesson must reproduce the failure
before it may fix it.

If you came here searching for **Pocket Analyst**, **Pat agent**, **Bridgewater
AI analyst**, or **investment research agent**: this is a clean-room
implementation of the publicly described ideas, plus the point-in-time layer any
outside implementation needs. It uses no Bridgewater code, data or trademarks
and is **not affiliated with or endorsed by** Bridgewater Associates. Full
attribution and the list of what was taken from the talk — and what quantifact
adds — is in [`docs/prior-art.md`](docs/prior-art.md).

**[→ Interactive architecture walkthrough](https://claude.ai/code/artifact/3e2419d3-23b3-4975-b946-445cf23aee8f)** — thirteen passes, a real
compiled plan with its generated code, the point-in-time defence, and every
benchmark, all rendered from a live run of this repository.

## 60-second demo

No API key, no credentials, no data licence — the demo adapter is synthetic and
deterministic.

```bash
uv add git+https://github.com/leoncuhk/quantifact    # PyPI release pending
qf ask                     # plan → codegen → contracts → execute → report
qf ask                     # again: every task served from the value cache
```

```
as_of      2026-08-01 (nothing published later was read)
plan       16 tasks in 5 layers
execution  16/16 cached, 6 ms
contracts  64/64 verdicts passed
review     1 findings
report     .qf/report.html
```

```python
from quantifact import Quantifact

qf = Quantifact(".qf")
art = qf.analyse("How did markets respond to the oil supply shock?",
                 answers={"as_of": "2026-06-14"},   # the knowledge date
                 out="report.html")
```

## What it guarantees

| Property | Enforced by | How you can check |
|---|---|---|
| A bad plan never reaches codegen | `plan/compile.py` — typed structural and semantic checks | `test_architecture.py::test_rejects_*` |
| Generated code cannot do IO, use the clock, or reach the network | `staticanalysis/ast_checks.py` + restricted globals | `test_architecture.py::test_blocks_*` |
| Code cannot read data published after the knowledge date | loaders bound by the harness; dated columns checked; `as_of` in the cache key | `test_point_in_time.py` (10 tests) |
| Undeclared dependencies are caught | AST graph vs declared graph | `test_architecture.py::test_undeclared_upstream_is_caught` |
| Results match their declared schema, order and invariants | `contracts/layers.py` (L1, L1-pit, L2) | `test_architecture.py::test_schema_validation_*` |
| Editing one task re-executes exactly one task | content-addressed value cache | `test_architecture.py::test_cache_hit_and_selective_recompute` |
| The same plan produces the same values | reference backend + determinism test | `test_architecture.py::test_execution_is_deterministic` |
| The same plan runs unchanged on another adapter | six-method adapter protocol | `test_duckdb_adapter.py` |
| A lesson is only accepted if it first fails | `learn/teach.py` | `test_architecture.py::test_teach_requires_*` |

## Is it PAT-level yet?

The compiler architecture is a validated prototype; the whole product has not
yet earned that claim. `qf audit` separates repository proof from evidence that
only real experts, licensed data and production operation can supply:

```bash
qf audit --out audit.md --json audit.json
qf audit --evidence benchmarks/quality-evidence.json --strict
```

The score cannot hide a weak critical dimension. Real-task accuracy, diverse
planning, tool coverage, isolation, reliability and expert adoption are gates,
not optional polish. See [the quality model and delivery plan](docs/quality-model.md).

The LLM planner broadens the question set only within the series, tables and
operations exposed to it. It is fail-closed, not an unrestricted claim to
answer any investment question.

## Point-in-time, by construction

The knowledge date is not a filter someone remembers to apply. The harness
hands generated code a loader that is *already* closed over it, and static
analysis rejects any attempt to pass a different one:

```python
# what the model may write                what the harness bound
prices = load_series("MKT.BRENT.CO.TRI")  # → adapter.read_series(..., as_of="2026-06-14")
load_series("MKT.BRENT.CO.TRI", as_of="2026-08-01")
# L0-static: load_series() takes no keyword arguments; the knowledge date is
# fixed by the plan and bound by the harness
```

Run [`examples/04_point_in_time`](examples/04_point_in_time) to watch look-ahead
get stopped six different ways — including the same question, asked as of two
dates, producing two different and defensible answers.

## Bring your own data

An adapter is six methods. Everything else — entitlements, publication lags,
licence tags — travels inside the catalog metadata rather than in a parallel
system.

```python
class Adapter(Protocol):
    name: str
    def catalog(self) -> list[SeriesMeta]: ...
    def read_series(self, series_id: str, *, as_of) -> pd.Series: ...
    def tables(self) -> list[str]: ...
    def read_table(self, name: str, *, as_of) -> pd.DataFrame: ...
    def invariants(self, series_id: str) -> list[dict]: ...
    def fingerprint(self, series_ids, *, as_of) -> str: ...
```

Ship the invariants *with* the data and the contract layer generates its checks
instead of guessing. See [`docs/guides/write-an-adapter.md`](docs/guides/write-an-adapter.md).

## Benchmarks

Measured on this repository with the deterministic backend, so anyone can
reproduce them: `qf bench`.

| scenario | wall | executed | cached |
|---|---:|---:|---:|
| cold — empty cache | 159 ms | 16 | 0 |
| warm — nothing changed | 6.0 ms | 0 | 16 |
| one-task edit | 7.0 ms | 1 | 15 |
| same edit, caching disabled | 100 ms | 16 | 0 |

- warm vs cold **26.4×**, one-task edit vs uncached **14.4×**
- codegen at 0.4 s simulated latency per task: **16 tasks in 0.41 s**, the same
  as a 3-task plan — fan-out is a property of the plan, not of the model
- determinism: **16/16 tasks byte-identical, 16/16 values identical**

With a real model writing every task (`deepseek-v4-flash`, see
[`benchmarks/RESULTS.md`](benchmarks/RESULTS.md)): on a bare prompt the static
layer passed **16/16** while the schema layer passed **9/16** and seven tasks
raised at runtime — and **not one wrong number reached a report**. Naming the
target runtime and enabling the repair loop takes values-equal-to-oracle from
**9/16 to 13/16**. Two compilations of the same plan agree on **values 12/16**
but on **code only 7/16**, which is why the contract is written on values.

## What this is not

- **Not a backtester.** No portfolio construction, no execution, no P&L.
- **Not a trading system.** It ships no strategy and no signal.
- **Not a data product.** The bundled data is synthetic; real data is yours to
  license and adapt.
- **Not a general agent framework.** It automates one narrow workflow —
  analytical investigation over a series store — and benchmarks it heavily.
  See [`docs/compare.md`](docs/compare.md) for how it differs from Dagster,
  dbt and LLM agent frameworks.

## FAQ

**Do I need an API key?** No. The default backend is a deterministic compiler
and the demo data is synthetic, so `qf ask` works offline. A model backend is
one environment variable away when you want it.

**Does it work with my data?** If you can answer six questions about a series —
what exists, what it was as of a date, which reference tables you have, what
must be true of it, and its fingerprint — yes. Start with
[`docs/guides/write-an-adapter.md`](docs/guides/write-an-adapter.md).

**Can it use an LLM to write the analysis code?** Yes, through any
OpenAI-compatible endpoint. What makes that safe is everything around it: the
contracts, the static analysis and the knowledge-date binding are unchanged.
Grading results are in [`benchmarks/RESULTS.md`](benchmarks/RESULTS.md).

**How do you stop look-ahead bias / survivorship bias?** The loader is bound to
the plan's knowledge date, universes are read as of that date, dated outputs are
checked, and the cache key carries it. Limits are stated in
[`docs/concepts/point-in-time.md`](docs/concepts/point-in-time.md).

**Is this a backtester or a trading bot?** No. It answers research questions and
produces tables and charts. No strategy, no orders, no P&L.

**Can it run A-share / HK / US data?** It is market-agnostic: adapters decide.
Nothing in the engine assumes a calendar, a currency or an identifier scheme —
those live in your catalog and your reference tables.

**What happens when the model writes something wrong?** A layer catches it, the
verdict plus a description of the data goes back for repair, and if the repair
budget runs out the run stops with the failing task named. It does not ship a
chart it cannot defend.

## Documentation

- [Concepts](docs/concepts/) — [plan as IR](docs/concepts/plan-as-ir.md) ·
  [contracts](docs/concepts/contracts.md) ·
  [point-in-time](docs/concepts/point-in-time.md) ·
  [caching](docs/concepts/caching.md) · [the flywheel](docs/concepts/flywheel.md)
- [Guides](docs/guides/) — quickstart · bring your own data · write an adapter ·
  evals · production
- [Public API](docs/index.md#public-api) and [architecture decisions](docs/adr/)
- [Comparison](docs/compare.md) and [prior art](docs/prior-art.md)
- [Interactive walkthrough](https://claude.ai/code/artifact/3e2419d3-23b3-4975-b946-445cf23aee8f) — the same material as a single page

## Licence and disclaimer

Apache-2.0. Read the [disclaimer](docs/disclaimer.md) before pointing this at
anything real: not investment advice, synthetic demo data, and no licence to
redistribute anybody's market data.
