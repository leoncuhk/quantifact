# quantifact documentation

**Concepts** — why the system is shaped this way

- [Plan as an intermediate representation](concepts/plan-as-ir.md)
- [Contracts](concepts/contracts.md)
- [Point-in-time](concepts/point-in-time.md)
- [Caching](concepts/caching.md)
- [The flywheel](concepts/flywheel.md)

**Guides** — how to do a thing

- [Quickstart](guides/quickstart.md)
- [Bring your own data](guides/byo-data.md)
- [Write an adapter](guides/write-an-adapter.md)
- [Evals and benchmarks](guides/evals.md)
- [Running it for real](guides/production.md)

**See it**

- [Interactive architecture walkthrough](https://claude.ai/code/artifact/3e2419d3-23b3-4975-b946-445cf23aee8f) — pass listing, a real compiled
  plan, the point-in-time defence and the benchmarks, from a live run

**Public API**

| import | what it is |
|---|---|
| `quantifact.Quantifact` | the system: `clarify`, `build_plan`, `analyse` |
| `AnalysisPlan`, `Task`, `ColumnSpec` | the intermediate representation |
| `PlanCompiler` | compile-time validation; returns execution layers |
| `Adapter`, `DemoSyntheticAdapter` | the six-method data protocol, and one implementation |
| `SeriesMeta`, `SeriesStore`, `SeriesSearch` | catalog, bitemporal storage, binding |
| `ExecutionHarness`, `ValueCache` | execution and caching |
| `Verdict`, `TaskUnfixable` | contract results |
| `ReferenceCodegen`, `generate_all` | the deterministic backend |
| `Lesson`, `Benchmark`, `teach` | the flywheel |

Everything else is an implementation detail and may move between 0.x releases.
Docstrings carry the reasoning; the concept pages carry the design.

**Context**

- [How this compares to Dagster, dbt and agent frameworks](compare.md)
- [Prior art](prior-art.md)
- [Architecture decisions](adr/)

## The one-paragraph version

A question is clarified into an **analysis plan**: an intermediate
representation with schemas, units, semantic roles, row grain, row order,
invariants and a **knowledge date**. Every task compiles in parallel into
exactly one pandas function, because a task needs only its inputs' *schemas*.
Static analysis derives the dependency graph from the code and cross-checks it
against the plan. Layered contracts run as ordinary Python that no model can
skip. A caching harness executes the code, bound to the knowledge date, so
look-ahead is structurally impossible and the second run is nearly free.
