# API reference

The public surface is small and stable:

| import | what it is |
|---|---|
| `quantifact.Quantifact` | the system: `clarify`, `build_plan`, `analyse` |
| `quantifact.AnalysisPlan`, `Task`, `ColumnSpec` | the intermediate representation |
| `quantifact.PlanCompiler` | compile-time validation, returns execution layers |
| `quantifact.Adapter` | the six-method data protocol |
| `quantifact.DemoSyntheticAdapter` | synthetic data, no credentials |
| `quantifact.SeriesMeta`, `SeriesStore`, `SeriesSearch` | catalog, storage, binding |
| `quantifact.ExecutionHarness`, `ValueCache` | execution and caching |
| `quantifact.Verdict`, `TaskUnfixable` | contract results |
| `quantifact.ReferenceCodegen`, `generate_all` | the deterministic backend |
| `quantifact.Lesson`, `Benchmark`, `teach` | the flywheel |

Everything else is an implementation detail and may move between 0.x releases.
Docstrings carry the reasoning; `docs/concepts/` carries the design.
