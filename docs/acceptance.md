# Highest-quality acceptance protocol

“Highest quality” is an evidence claim, not a feature label. Repository tests
can validate architecture; they cannot substitute for expert, production or
adoption evidence. `qf audit --strict` therefore remains closed until every
critical operating gate has traceable evidence.

## Release acceptance

Every source release must pass from a clean environment:

```bash
uv sync --all-extras --group dev
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
qf ask --out .qf/report.html --evidence .qf/evidence.json
qf verify .qf/evidence.json
qf bench
qf audit
uv build
```

Install the resulting wheel into a fresh virtual environment and repeat the
offline `qf ask`/`qf verify` smoke test. A moved development virtual environment
is not release evidence.

`qf verify` checks internal hashes and manifests. Production distribution must
add a trusted signature/transparency registry; a self-hash is not publisher
authentication.

## Research acceptance

For each supported family, maintain at least 50 held-out, expert-audited cases
covering normal work, boundary dates, revised data, survivorship, wrong units,
missing permissions, method traps and required refusals. Pre-register:

- acceptable plan and answer rubric;
- exact values, row sets and date boundaries where possible;
- two independent reviewers and disagreement adjudication;
- critical/major/minor error severity;
- family and data-adapter slices.

Report separately:

- plan acceptance rate (target at least 90%);
- answer acceptance rate (target at least 95%);
- known silent critical errors (target zero);
- run failure/refusal rate—never combine this with silent errors;
- citation and PIT correctness;
- reviewer time and plan-edit rate.

## Production and product acceptance

- No-network, read-only, resource-limited isolation passes adversarial escape,
  entitlement and prompt-injection evaluations.
- Cancellable and resumable service achieves at least 99.5% success over a
  declared measurement window, with p95 latency and recovery tests.
- Accepted lessons improve held-out outcomes without regression.
- A named expert cohort reaches at least 60% weekly retention and 50% median
  time saved without reducing correctness or review standards.

Only after all critical gates pass may a release claim PAT-level operating
evidence. Until then Quantifact must describe itself as an alpha or validated
architecture prototype, however impressive an individual demo appears.
