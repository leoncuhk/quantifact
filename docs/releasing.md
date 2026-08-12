# Releasing

A tag is a claim about the installable artifact, not the source tree. The
release workflow publishes only when all of these are true:

1. lint, format, tests, examples and deterministic benchmarks pass;
2. wheel and sdist build, and the wheel passes an isolated install smoke test;
3. the secret scan passes over history and the working tree;
4. `benchmarks/quality-evidence.json` supplies traceable operating evidence;
5. `qf audit --evidence benchmarks/quality-evidence.json --strict` reports
   `PAT-level evidence`;
6. version, changelog and citation metadata agree;
7. the tag is signed or created through the protected GitHub release flow.

Do not copy the example evidence file and fill it with estimates. Each operating
criterion requires an immutable artifact, measurement date, sample size and
accountable approver. Repository maintainers verify provenance; the CLI verifies
shape and thresholds.

Local release-candidate check:

```bash
uv run ruff format --check src tests examples tools
uv run ruff check .
uv run pytest -q
uv run qf bench
uv run qf audit --evidence benchmarks/quality-evidence.json --strict
uv build
```

If strict audit fails, publish neither a PAT-level claim nor a final tag. A
source snapshot or explicitly labelled release candidate may still be shared
for evaluation.
