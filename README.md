# quantifact

**An investment-research agent that has to prove its numbers.**
The model writes the code; the contract decides whether the number counts.

[![CI](https://github.com/leoncuhk/quantifact/actions/workflows/ci.yml/badge.svg)](https://github.com/leoncuhk/quantifact/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/quantifact.svg)](https://pypi.org/project/quantifact/)
[![Python](https://img.shields.io/pypi/pyversions/quantifact.svg)](https://pypi.org/project/quantifact/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

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

The architecture is an independent implementation of the one Bridgewater
Associates described publicly at INTERRUPT26. See [`docs/prior-art.md`](docs/prior-art.md).

## 60-second demo

No API key, no credentials, no data licence — the demo adapter is synthetic and
deterministic.

```bash
uv add quantifact          # or: pip install quantifact
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
| A bad plan never reaches codegen | `plan/compile.py` — 15 classes of compile error | `test_architecture.py::test_rejects_*` |
| Generated code cannot do IO, use the clock, or reach the network | `staticanalysis/ast_checks.py` + restricted globals | `test_architecture.py::test_blocks_*` |
| Code cannot read data published after the knowledge date | loaders bound by the harness; dated columns checked; `as_of` in the cache key | `test_point_in_time.py` (10 tests) |
| Undeclared dependencies are caught | AST graph vs declared graph | `test_architecture.py::test_undeclared_upstream_is_caught` |
| Results match their declared schema, order and invariants | `contracts/layers.py` (L1, L1-pit, L2) | `test_architecture.py::test_schema_validation_*` |
| Editing one task re-executes exactly one task | content-addressed value cache | `test_architecture.py::test_cache_hit_and_selective_recompute` |
| The same plan produces the same values | reference backend + determinism test | `test_architecture.py::test_execution_is_deterministic` |
| The same plan runs unchanged on another adapter | five-method protocol | `test_duckdb_adapter.py` |
| A lesson is only accepted if it first fails | `learn/teach.py` | `test_architecture.py::test_teach_requires_*` |

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

An adapter is five methods. Everything else — entitlements, publication lags,
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

## Documentation

- [Concepts](docs/concepts/) — [plan as IR](docs/concepts/plan-as-ir.md) ·
  [contracts](docs/concepts/contracts.md) ·
  [point-in-time](docs/concepts/point-in-time.md) ·
  [caching](docs/concepts/caching.md) · [the flywheel](docs/concepts/flywheel.md)
- [Guides](docs/guides/) — quickstart · bring your own data · write an adapter ·
  evals · production
- [Comparison](docs/compare.md) and [prior art](docs/prior-art.md)
- [Architecture decisions](docs/adr/)

## Licence and disclaimer

Apache-2.0. Read [DISCLAIMER.md](DISCLAIMER.md) before pointing this at
anything real: not investment advice, synthetic demo data, and no licence to
redistribute anybody's market data.
