# ADR 0002 — Point-in-time is a contract, not a convention

**Status**: accepted · **Date**: 2026-08-12

## Context

Look-ahead is the failure mode that makes historical research worthless, and it
is silent. Most systems handle it with a convention ("remember to filter by
filing date") or a parameter on a reader that callers may forget.

## Decision

`AnalysisPlan.as_of` is required. The harness binds `load_series` and
`load_table` to it and static analysis forbids passing another. Dated output
columns are checked against it. It is part of the cache key. Universes and event
tables are read as of it, making them survivorship-free.

## Consequences

- Adapters must supply `pub_date` per observation; sources that cannot are
  second-class and must say so.
- Some correct-looking questions are refused ("include the 2026 episode" as of
  June 2026), which is the point.
- It does not catch hindsight in *choices*, and it does not model revisions
  beyond the served vintage. Both limits are documented rather than implied.
