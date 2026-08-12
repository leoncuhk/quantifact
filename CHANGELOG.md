# Changelog

All notable changes to this project are documented here, following
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] — 2026-08-12

First public release.

### Added
- **Plan as an intermediate representation**: typed tasks with columns, units,
  semantic roles, row grain, row order and invariants, plus a required
  knowledge date; `PlanCompiler` rejects 15 classes of malformed plan before any
  code is generated.
- **Contracts**: L0 static analysis, L1 schema and row order, L1-pit
  observation dates, L2 invariants, optional L3 semantic review, L4 self review.
- **Point-in-time by construction**: bitemporal store, loaders bound to the
  knowledge date, survivorship-free universes, `as_of` in the cache key.
- **Parallel codegen** behind a backend protocol, with a deterministic reference
  compiler used as the test oracle and an OpenAI-compatible LLM backend.
- **Execution harness** with restricted globals, layered execution and a
  content-addressed value cache.
- **Adapters**: five-method protocol, synthetic demo adapter, DuckDB adapter.
- **The flywheel**: lessons, benchmarks and a teach loop that only accepts a
  lesson which first reproduces the failure.
- **Reports**: single-file HTML with inline SVG charts, per-chart CSV export,
  generated code and the full execution trace.
- CLI (`qf`), benchmarks (`qf bench`) and 41 tests covering the guarantees.
