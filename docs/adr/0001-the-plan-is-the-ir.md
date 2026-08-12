# ADR 0001 — The plan is the intermediate representation

**Status**: accepted · **Date**: 2026-08-12

## Context

A coding agent can be given a to-do list ("load prices, compute returns, plot")
or a typed specification. The first is cheaper to produce and is what most
agent products use.

## Decision

The plan is a typed IR. Every task declares its inputs, its output columns with
dtype, unit and semantic role, its row grain, its row order and its invariants,
and the plan as a whole declares a knowledge date. A plan that does not compile
never reaches codegen.

## Consequences

- Codegen parallelises, because schemas are known before any code exists.
- Validation has something to check against, and cache keys have something
  stable to hash.
- Planning is more expensive, and the planner needs domain context to fill the
  fields honestly. We pay that deliberately: it is the same trade the talk this
  replicates describes making.
- A plan is reviewable by a human before anything runs — which turns out to be
  the artefact investors actually want to argue with.
