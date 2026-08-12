# Quickstart

```bash
uv run python examples/01_quickstart/run.py
```

Runs the demo question end to end on synthetic data: clarifying questions,
compiled plan, parallel codegen, contracts, cached execution, self review and an
interactive HTML report. Then runs it again to show every task served from the
value cache.

Nothing is downloaded and no key is needed. The store is generated once, from a
fixed seed, into `.qf-quickstart/`.
