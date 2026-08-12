# Architecture: four bounded subsystems

The architecture is organised around error containment, not around how many
agents appear in a diagram. Each subsystem owns one irreversible hand-off and
emits a reviewable artefact.

![Four-subsystem Quantifact architecture](assets/architecture.svg)

## 1. Research understanding

**Input:** user question, identity, entitlements and knowledge date.

**Owns:** clarification, document and series search, concrete data binding,
workflow selection, and the pre-registered critical-thinking contract.

**Output:** `ResearchDesign + AnalysisPlan`.

It must not write or execute analysis code. A future chat service may add
persistence, cancellation and continuation without changing this hand-off.

## 2. Analysis compiler

**Input:** the reviewed research design and typed plan.

**Owns:** plan compilation, parallel task code generation, AST checks, and the
cross-check between declared and actual dependencies.

**Output:** checked task functions plus the actual DAG.

The model is a replaceable backend inside this subsystem. It does not choose
whether compilation or static analysis runs.

## 3. Controlled execution

**Input:** checked functions, DAG, point-in-time adapter and knowledge date.

**Owns:** loader binding, cache identity, layered materialisation, result
contracts, targeted repair, self-review, report, receipt and governed writeback.

**Output:** a reviewable evidence package or a named, blocking failure.

The current restricted Python namespace reduces blast radius but is not a
production sandbox. A container or VM remains required for untrusted models.

## 4. Organisation learning

**Input:** an expert correction or a missed failure from a completed run.

**Owns:** failure reproduction, benchmark creation, candidate workflow/planner/
contract changes, full regression, and preparation for human review.

**Output:** a versioned lesson and benchmark; never an automatically merged
runtime mutation.

This is intentionally off the success path. Ordinary runs do not continually
rewrite their own controls.

## Shared trust boundary

Permission-aware point-in-time adapters serve both research understanding and
controlled execution. Search metadata and execution data must share the same
identity, entitlement and knowledge-date semantics. If an adapter cannot supply
publication timing or vintage history, the system must weaken or refuse the
corresponding guarantee rather than imply point-in-time safety.

## Arrow semantics

- **Blue:** mandatory control and evidence hand-off.
- **Dashed grey:** permissioned point-in-time data access.
- **Violet:** benchmark-gated learning and approved versioned change.

Combining these into a single generic arrow would hide important authority
boundaries: data access is not control flow, and feedback is not permission to
self-modify.
