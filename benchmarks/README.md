# Benchmarks

Three kinds, deliberately kept apart.

## Behaviour — assertions over what the planner produces

```bash
qf evals --dir benchmarks/plan
qf evals --dir benchmarks/contract
qf evals --dir benchmarks/refusal --json refusal-results.json
```

These are the public subset: enough to show the shape and to regression-test the
planner. `qf teach` writes new ones into your workspace as it learns.

| file | asserts |
|---|---|
| `plan/plan-compiles.json` | the demo question yields a plan that compiles, with the expected structure |
| `contract/binds-the-rate-not-the-index.json` | three trap series that match the query text are considered and rejected |
| `refusal/*.json` | unsupported research families fail closed instead of receiving an oil-event plan |

Every case names a research `family`, `risk_tags`, `expected_outcome` and
`severity`. Reports are sliced by family and risk and count silent critical
failures separately. A growing total pass rate is meaningless if all new cases
come from the same easy family.

Assertion types: `plan_has_task`, `plan_lacks_task`, `chart_has_facet`,
`task_count_min`, `plan_valid`, `series_bound`, `series_rejected`.

Write assertions that fail for a stated reason. `series_rejected` is stronger
than `series_bound` alone: it proves the trap was seen and refused, not merely
that the right answer happened to rank first.

## Performance and correctness — `qf bench`

Cold / warm / one-task edit / uncached, codegen scaling, and determinism, on the
deterministic backend so the numbers reproduce anywhere. Latest measurements and
the language-model grading runs are in [RESULTS.md](RESULTS.md).
