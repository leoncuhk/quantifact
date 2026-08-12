# Evals and benchmarks

Two different things share the word "benchmark" here, and keeping them apart is
the point.

## Performance benchmarks — `qf bench`

Cold, warm, one-task edit, and the same edit uncached, plus codegen scaling and
determinism. Deterministic backend, so anyone can reproduce the numbers on their
own machine. This is what the README table reports.

## Behaviour benchmarks — `qf evals`

Assertions over what the planner produces for a given question:

```json
{
  "id": "teach-per-asset-class-panels",
  "prompt": "compare the oil shocks",
  "kind": "plan",
  "assertions": [
    {"type": "plan_has_task", "name": "market_scatter_by_asset_class"},
    {"type": "chart_has_facet", "facet": "asset_class"},
    {"type": "plan_valid"}
  ]
}
```

Available assertion types: `plan_has_task`, `plan_lacks_task`, `chart_has_facet`,
`task_count_min`, `plan_valid`, `series_bound`, `series_rejected`.

`series_rejected` is the one to reach for when a trap series exists: it asserts
that a specific candidate was *considered and rejected*, which is stronger than
asserting that the right one was chosen.

## Why hard assertions rather than a model judge

A reproducible system deserves checks that fail for a stated reason. Model
judgement was measured here and it approved a result that differed from the
reference by ten boundary rows — a soft score would have sent hill-climbing in
the wrong direction while looking like progress.

## Grading a real model

`tools/llm_trial.py` runs the plan through a model backend and grades every task
against the reference compiler: which layers passed, whether the values match,
and how often two independent compilations agree. Results go in
`benchmarks/RESULTS.md`.
