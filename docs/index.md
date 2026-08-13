# quantifact documentation

**Concepts** — why the system is shaped this way

- [Plan as an intermediate representation](concepts/plan-as-ir.md)
- [Critical thinking as a contract](concepts/critical-thinking.md)
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
- [Quality model and delivery gates](quality-model.md)
- [Product, buyer and operating model](product-operating-model.md)
- [Highest-quality acceptance protocol](acceptance.md)
- [Maturity matrix and roadmap](../ROADMAP.md)
- [Release process and evidence gate](releasing.md)

**See it**

- [Interactive run explorer](https://leoncuhk.github.io/quantifact/) — a real
  compiled plan, point-in-time comparison, and reproducible benchmarks

**Public API**

| import | what it is |
|---|---|
| `quantifact.Quantifact` | the system: `clarify`, `build_plan`, `analyse` |
| `ResearchEvidencePackage` | the durable, integrity-checked run product |
| `AnalysisPlan`, `Task`, `ColumnSpec`, `ResearchDesign` | the intermediate representation and inference contract |
| `PlanCompiler` | compile-time validation; returns execution layers |
| `Adapter`, `DemoSyntheticAdapter`, `check_adapter` | data protocol, demo and PIT conformance suite |
| `SeriesMeta`, `SeriesStore`, `SeriesSearch` | catalog, bitemporal storage, binding |
| `ExecutionHarness`, `ProcessExecutionHarness`, `ValueCache` | fast execution, process containment and caching |
| `Verdict`, `TaskUnfixable` | contract results |
| `ReferenceCodegen`, `generate_all` | the deterministic backend |
| `Lesson`, `Benchmark`, `teach` | the flywheel |

Everything else is an implementation detail and may move between 0.x releases.
Docstrings carry the reasoning; the concept pages carry the design.

**Context**

- [Four-subsystem architecture](architecture.md)
- [How this compares to Dagster, dbt and agent frameworks](compare.md)
- [Prior art](prior-art.md)
- [Architecture decisions](adr/)

## The one-paragraph version

A question crosses four bounded subsystems. Research understanding emits an
**analysis plan and research design** with schemas, units, semantic roles, row
grain, knowledge date, claims, rivals and falsifiers. The analysis compiler
generates one pandas function per task and derives the actual dependency graph.
Controlled execution runs mandatory contracts and a point-in-time caching
harness. Organisation learning may return an audited failure only through a
failing benchmark, regression suite and human approval. No model owns these
boundaries.
