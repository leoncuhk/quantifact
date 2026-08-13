# Releasing

A tag is a claim about the installable artifact, not the source tree. Every
release, including an alpha, publishes only when all of these are true:

1. lint, format, tests, examples and deterministic benchmarks pass;
2. wheel and sdist build, and the wheel passes an isolated install smoke test;
3. the secret scan passes over history and the working tree;
4. all public research-family and refusal evaluations pass with zero silent
   critical failures;
5. version, changelog, citation metadata and tag agree;
6. GitHub publishes the wheel and sdist with build provenance.

Stable releases add two gates that alpha releases deliberately cannot claim:

7. `benchmarks/quality-evidence.json` supplies traceable operating evidence;
8. `qf audit --evidence benchmarks/quality-evidence.json --strict` reports
   `PAT-level evidence`, after which the trusted-publishing job may publish to
   PyPI.

Do not copy the example evidence file and fill it with estimates. Each operating
criterion requires an immutable artifact, measurement date, sample size and
accountable approver. Repository maintainers verify provenance; the CLI verifies
shape and thresholds.

Local release-candidate check:

```bash
uv run ruff format --check src tests examples tools
uv run ruff check .
uv run pytest -q
uv run qf evals --dir benchmarks
uv run qf adapter-check
uv run qf bench
uv run qf audit
uv run python tools/check_release.py
uv build
```

If strict audit fails, publish neither a PAT-level claim nor a stable/PyPI
release. An explicitly labelled PEP 440 prerelease may still be published on
GitHub for evaluation when every repository-level gate passes.
