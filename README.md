# Quantifact

**Turn an investment question into evidence another person can inspect, reproduce, and challenge.**

[![CI](https://github.com/leoncuhk/quantifact/actions/workflows/ci.yml/badge.svg)](https://github.com/leoncuhk/quantifact/actions/workflows/ci.yml)
[![Secret scan](https://github.com/leoncuhk/quantifact/actions/workflows/secrets.yml/badge.svg)](https://github.com/leoncuhk/quantifact/actions/workflows/secrets.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-3776AB.svg)](pyproject.toml)
[![License Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-6B7280.svg)](LICENSE)
[![Explore a run](https://img.shields.io/badge/explore-a_live_run-14B8A6.svg)](https://leoncuhk.github.io/quantifact/)

Quantifact is an open-source investment-research system built as an evidence
compiler. Four bounded subsystems turn an ambiguous question into a typed
research design, generated analysis, verified execution, and benchmark-gated
organisational learning. The result carries the code, checks, lineage,
assumptions, rival explanations, and inference limits needed to challenge it.

> The model proposes the analysis. The system decides whether the evidence is
> fit to use.

<p align="center">
  <img src="docs/assets/architecture.svg" alt="Quantifact uses four bounded subsystems: research understanding, analysis compiler, controlled execution, and organisation learning" width="100%">
</p>

Blue arrows are control and evidence flow, dashed grey arrows are permissioned
point-in-time data access, and violet arrows are learning that may return only
after a failing benchmark, full regression, and human approval. Models sit
above these boundaries as replaceable planners, code generators, or critics;
no model owns orchestration or can bypass a required gate.

## What you get

A successful run produces more than a chart:

- a plan that fixes definitions, schemas, units, row grain, and knowledge date;
- a pre-registered research design that binds claims to evidence, rival
  explanations, falsifiers, and explicit inference limits;
- generated pandas functions and their actual dependency graph;
- contract verdicts from static checks through point-in-time and semantic checks;
- a self-contained HTML report with charts, data exports, and source code;
- a machine-readable receipt containing input fingerprints, hashes, repairs,
  timings, findings, and output lineage;
- content-addressed results, so changing one task recomputes only what changed.

If a required check fails, the run stops or repairs the named task. It does not
quietly turn an unverified number into a polished report.

## Try it in 60 seconds

The demo is deterministic, synthetic, and runs offline—no API key, credentials,
or market-data licence required.

```bash
uv add git+https://github.com/leoncuhk/quantifact
qf ask --receipt .qf/run.json
```

```text
as_of      2026-08-01 (nothing published later was read)
plan       16 tasks in 5 layers
contracts  68/68 verdicts passed
report     .qf/report.html
receipt    .qf/run.json
```

Run `qf ask` again and all 16 task values come from cache. Change one final task
and its unaffected upstream work remains cached.

```python
from quantifact import Quantifact

qf = Quantifact(".qf")
run = qf.analyse(
    "How did markets respond to the oil supply shock?",
    answers={"as_of": "2026-06-14"},
    out="report.html",
)

run.plan.as_of
run.verdicts
run.receipt()
```

## Why this is useful

Research rarely fails because nobody can generate code. It fails because the
question was underspecified, the data revision was unknowable at the stated
date, a definition changed between reviewers, or nobody can reconstruct how the
final number was produced.

Quantifact makes those failure modes explicit:

| Research risk | System response |
|---|---|
| Ambiguous question | Clarifications compile into a typed plan before code generation |
| Look-ahead and survivorship bias | Loaders, universes, outputs, and cache keys share one knowledge date |
| Plausible but wrong output | Schemas, invariants, semantic checks, and self-review gate the report |
| Confirmation bias or overclaiming | Claims, rivals, falsifiers and inference limits compile before code generation |
| Hidden dependencies | Static analysis derives the DAG from generated code and compares it with the plan |
| Slow review | Every result carries code, inputs, checks, repairs, and lineage |
| Expensive iteration | Content-addressed caching recomputes only the affected subgraph |
| Unsafe learning | A lesson must reproduce a failure, fix it, and pass regression before acceptance |

## Four bounded subsystems

The public PAT presentation is best understood as four cooperating subsystems,
not four Python modules. Quantifact implements the same separation because each
boundary limits a different class of error.

| Subsystem | Value and responsibility | Quantifact implementation | Current boundary |
|---|---|---|---|
| **1. Research understanding** | Turn a vague request into an admissible research question: permissions, definitions, knowledge date, data binding, claims, rivals and falsifiers | `planner.py`, `planner_llm.py`, `data/`, `learn/workflows.py`, `ResearchDesign` | Executable core; no persistent LangGraph chat, live web search, or broad expert context yet |
| **2. Analysis compiler** | Convert the reviewed design into a typed IR and constrain implementation before execution | `plan/`, `codegen/`, `static_analysis/`; `PlanCompiler` and parallel task codegen | Strongest subsystem; operation vocabulary and real-model research breadth remain limited |
| **3. Controlled execution** | Materialise values without giving the model terminal control; enforce PIT, contracts, repair, cache, report and receipt | `harness/`, `contracts/`, `review/`, `report/`, `Quantifact.analyse()` | Fully executable prototype; process isolation and same-layer parallel execution are not production complete |
| **4. Organisation learning** | Convert a real missed failure into a reproducible benchmark and an approved, regression-safe system change | `learn/teach.py`, `LessonRepo`, `BenchmarkSuite` | Minimum safe loop; one registered effect, no automatic conversation mining or PR service |

These responsibilities deliberately do not collapse into one generic agent:

1. **Understand** — bind the definition, universe, horizon, `as_of`, data IDs,
   bounded claims, rival explanations, and falsifiers.
2. **Compile** — validate the plan, generate one pandas function per task in
   parallel, statically inspect it, and derive the actual dependency DAG.
3. **Execute** — run through harness-owned point-in-time loaders, enforce all
   mandatory verdicts, repair only a named failure, and emit a report or stop.
4. **Learn** — reproduce an expert correction as a failing benchmark, propose a
   versioned change, run the full regression suite, and leave acceptance to a
   human reviewer.

The hand-off contracts are the architecture: subsystem 1 emits
`ResearchDesign + AnalysisPlan`; subsystem 2 emits checked functions plus an
actual DAG; subsystem 3 emits a report and receipt or a named failure; subsystem
4 emits a candidate lesson and benchmark, never a silent runtime mutation.

The default reference backend makes the example reproducible offline. An
OpenAI-compatible backend may plan, generate, debug, and semantically inspect
code without weakening the deterministic boundaries around it.

## Point-in-time by construction

The knowledge date is not a reminder in a prompt. The harness binds it into the
data loaders before generated code runs, dated outputs are checked against it,
and the cache key includes it.

```python
prices = load_series("MKT.BRENT.CO.TRI")  # loader is already bound to 2026-06-14

load_series("MKT.BRENT.CO.TRI", as_of="2026-08-01")
# rejected: generated code cannot override the plan's knowledge date
```

The guarantee is only as strong as the connected adapter's vintage history.
Run [`examples/04_point_in_time`](examples/04_point_in_time) to see six guarded
failure modes, including revised observations and survivorship-free universes.

## Evidence, not claims

The repository keeps reproducible engineering evidence separate from claims
that require real users and production operation.

```bash
qf bench
qf audit --out audit.md --json audit.json
qf audit --evidence benchmarks/quality-evidence.json --strict
```

On the bundled 16-task workflow, the current deterministic benchmark records:

| Scenario | Work performed | Result |
|---|---:|---:|
| Cold run | 16 executed, 0 cached | 159 ms |
| Warm run | 0 executed, 16 cached | 6.0 ms |
| One-task edit | 1 executed, 15 cached | 7.0 ms |
| Same edit without cache | 16 executed | 100 ms |

Code and value determinism are both **16/16** with the reference backend. A
real-model evaluation, including failures caught before reporting, is recorded
in [`benchmarks/RESULTS.md`](benchmarks/RESULTS.md). Run the benchmark on your
machine rather than treating these numbers as universal performance claims.

## Bring your own data

The engine is market-agnostic. A data adapter exposes six methods; its catalog
carries frequency, currency, units, publication timing, entitlements, licence
tags, and invariants alongside each series.

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

Start with [Bring your own data](docs/guides/byo-data.md) or
[Write an adapter](docs/guides/write-an-adapter.md).

## Project status

Quantifact is an **alpha research system**, not a production trading system and
not a source of investment advice. Its compiler, contracts, point-in-time
controls, cache, receipts, and packaged examples are executable and tested.
Production isolation, broad expert evaluation, service reliability, and user
outcomes still require operating evidence.

[`qf audit`](docs/quality-model.md) makes that boundary measurable and the
release workflow fails closed when required evidence is absent. See
[Production guidance](docs/guides/production.md) before connecting an untrusted
model or proprietary data.

## Contributing

Quantifact should become useful through shared evidence, not broader promises.
Contributions are especially welcome in four areas:

- **adapters** for correctly versioned, permission-aware data sources;
- **research workflows** with explicit definitions and expected outputs;
- **contracts** that catch a real failure without rejecting correct work;
- **evaluations** containing difficult questions, date traps, and regression cases.

See [Contributing](.github/CONTRIBUTING.md), open an
[adapter request](.github/ISSUE_TEMPLATE/adapter-request.yml), or report a
[missed failure](.github/ISSUE_TEMPLATE/missed-failure.yml). A missed failure is
one of the most valuable contributions this project can receive.

## Documentation

- [Quickstart](docs/guides/quickstart.md)
- [Four-subsystem architecture](docs/architecture.md)
- [Concepts](docs/concepts/) — plan as IR, contracts, point-in-time, caching, learning
- [Guides](docs/guides/) — data adapters, evaluations, and production
- [Public API](docs/index.md#public-api)
- [Architecture decisions](docs/adr/)
- [Interactive run explorer](https://leoncuhk.github.io/quantifact/)
- [Quality model and delivery gates](docs/quality-model.md)

## Acknowledgements

Quantifact was inspired in part by Bridgewater Associates' public presentation
of *Pat, the Pocket Analyst* at INTERRUPT26, particularly its framing of
agentic analysis as a compiler problem. This project is an independent
open-source effort, with its own implementation, point-in-time model, evidence
format, and evaluation gates. It is not affiliated with or endorsed by
Bridgewater Associates. See [Prior art and acknowledgements](docs/prior-art.md).

Apache-2.0. Synthetic demo data only. See the [licence](LICENSE),
[security policy](.github/SECURITY.md), and [disclaimer](docs/disclaimer.md).
