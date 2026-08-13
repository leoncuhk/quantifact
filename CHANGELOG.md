# Changelog

All notable changes to this project are documented here, following
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0a1] — 2026-08-13

This alpha release strengthens the repository's fail-closed research and
distribution boundaries. It does not claim expert validation, production
isolation, or investment fitness.

### Added
- Versioned `ResearchEvidencePackage` with plan, code, source-vintage manifest,
  claim lineage, value fingerprints, admission semantics and integrity checks.
- Offline `qf verify` command with explicit integrity/authenticity boundary.
- Registered event-study and historical-analogy method contracts.
- Product operating model, acceptance protocol, evidence-package ADR and public
  maturity roadmap.
- Visible-vintage fingerprint tests and memoisation.
- Fail-closed rule-planner routing for unsupported research families.
- Family/risk/severity-aware evaluation reports with refusal cases and a
  separate silent-critical-failure count.
- Public adapter PIT conformance suite and `qf adapter-check`.
- Optional disposable-process execution with wall/CPU/memory containment and
  explicit non-sandbox semantics.

### Changed
- Successful report runs emit an evidence package beside the HTML report.
- The quality audit requires the evidence package to verify before awarding
  full diagnosability credit.
- Cache input identity now hashes only the data visible at the knowledge date.

## [0.2.0] — 2026-08-12

### Added
- Compiler-feedback LLM planner for heterogeneous questions, with catalog,
  workflow, document and operation context and fail-closed plan repair.
- Point-in-time document retrieval with entitlement filtering and citations.
- Packaged expert workflow guides plus workspace overrides.
- Evidence-backed `qf audit` maturity gate; missing expert and production
  evidence cannot be inferred from repository features.
- Versioned, machine-readable run receipts covering the exact plan and code
  hashes, bindings/planner evidence, execution traces, verdicts, repairs,
  findings, lineage and outputs.
- Stronger plan compilation: operation vocabulary, required operation fields,
  table schemas and output-column closure.

### Changed
- The demo adapter now serves a dated synthetic research corpus in addition to
  bitemporal series and reference tables.
- CI runs the maturity audit as a smoke test.

## [0.1.0] — 2026-08-12

First public release.

### Added
- **Plan as an intermediate representation**: typed tasks with columns, units,
  semantic roles, row grain, row order and invariants, plus a required
  knowledge date; `PlanCompiler` rejects a malformed plan before any code is
  generated.
- **Contracts**: L0 static analysis, L1 schema and row order, L1-pit
  observation dates, L2 invariants, optional L3 semantic review, L4 self review.
- **Point-in-time by construction**: bitemporal store, loaders bound to the
  knowledge date, survivorship-free universes, `as_of` in the cache key.
- **Parallel codegen** behind a backend protocol, with a deterministic reference
  compiler used as the test oracle and an OpenAI-compatible LLM backend.
- **Execution harness** with restricted globals, layered execution and a
  content-addressed value cache.
- **Adapters**: six-method protocol, synthetic demo adapter, DuckDB adapter.
- **The flywheel**: lessons, benchmarks and a teach loop that only accepts a
  lesson which first reproduces the failure.
- **Reports**: single-file HTML with inline SVG charts, per-chart CSV export,
  generated code and the full execution trace.
- CLI (`qf`), reproducible benchmarks and property tests covering the guarantees.
