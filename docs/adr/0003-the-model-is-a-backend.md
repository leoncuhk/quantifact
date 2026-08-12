# ADR 0003 — The model is a replaceable backend

**Status**: accepted · **Date**: 2026-08-12

## Context

It is tempting to build around one model's behaviour: its prompt format, its
tool protocol, its quirks. Models change every few months; the architecture
should not.

## Decision

Code generation sits behind a one-method protocol. Three backends ship: a
deterministic reference compiler (the test oracle), an OpenAI-compatible client
(stdlib only, no vendor SDK), and a latency simulator for measuring structural
claims without spending calls.

## Consequences

- Every benchmark in the repository is reproducible offline, because the
  reference backend has no variance.
- A real model can be graded task by task against the oracle, which is how
  `benchmarks/RESULTS.md` is produced.
- The default path needs no API key, so the project is evaluable by anyone in
  sixty seconds — which matters more for adoption than any feature.
- Backend-specific behaviour (a reasoning model that spends its whole budget
  thinking, a gateway that rejects large token budgets) is handled in the
  backend, not in the engine.
