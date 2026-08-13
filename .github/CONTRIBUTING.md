# Contributing

## What is most useful

1. **Adapters.** A new data source that implements the six-method protocol is
   the highest-value contribution. Keep credentials and licensed data out of the
   repository; an adapter is code, not a data dump.
2. **Contract checks.** New invariant kinds, new static-analysis rules, new
   self-review checks — especially ones that caught a real mistake.
3. **Benchmarks.** A plan-level assertion that fails on today's planner is worth
   more than an opinion about it.
4. **Failure reports.** If a model wrote something wrong and a layer did *not*
   catch it, that is the most valuable issue you can file.

## Ground rules

- Every behavioural change comes with a test that fails without it.
- Tests assert *properties*, not implementation details.
- No new runtime dependencies without discussion; the core is pandas, numpy and
  pyarrow on purpose.
- Docstrings explain **why**, not what — the code already says what.
- Never commit credentials, licensed data, or a dataset you cannot redistribute.
  CI runs a secret scanner and it is not there for decoration.

## Development

```bash
uv sync --extra duckdb
uv run pytest -q
uv run ruff check .
uv run ruff format --check src tests examples tools
uv run qf bench
uv run qf audit
uv build
```

## Adding an adapter

Implement `catalog`, `read_series`, `tables`, `read_table`, `invariants` and
`fingerprint`. Then prove it works by running the shared conformance test
against it — see `tests/test_duckdb_adapter.py` for the pattern. An adapter
that cannot serve `pub_date` per observation cannot support point-in-time and
should say so in its docstring rather than pretending.

Run `qf adapter-check --json adapter-conformance.json` before writing bespoke
integration tests. Passing the suite is necessary, not proof that a data source
is accurate or licensed.

## Claims and operating evidence

Do not describe repository functionality as expert accuracy, production safety
or user value. Changes to `benchmarks/quality-evidence.json` require an immutable
raw artifact, measurement window, denominator, sample size and named approver.
See `docs/acceptance.md` and `ROADMAP.md` before proposing a maturity claim.
