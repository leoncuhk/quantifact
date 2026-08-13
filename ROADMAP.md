# Maturity and roadmap

Quantifact is a high-quality **alpha architecture prototype**, not yet a
production investment-research operating system. This distinction is a product
control: repository features cannot substitute for expert accuracy, operating
reliability or adoption evidence.

## Evidence snapshot

| Dimension | Current evidence | Status | Exit evidence |
|---|---|---|---|
| Typed research compiler | Executable plan IR, actual-DAG cross-check and property tests | Implemented for supported ops | Held-out plans across 6–10 research families |
| Point-in-time | Bitemporal demo store, PIT-bound loaders, survivorship tests and visible-slice cache identity | Implemented prototype | Licensed vintage data and adversarial adapter conformance |
| Evidence admission | Method, claim, schema, invariant, PIT and review gates; verifiable evidence package | Implemented prototype | ≥95% expert acceptance and zero known silent critical errors |
| Research breadth | Rule-complete oil-event workflow; model planner stub-tested | Limited | ≥50 expert-audited heterogeneous questions, ≥90% plan acceptance |
| Data and tools | Synthetic series/documents and local DuckDB adapter | Limited | Licensed corpora and ≥80% sampled human-workflow tool coverage |
| Execution security | AST policy and restricted namespace | Not production-safe | No-network, resource-limited sandbox and escape evaluation |
| Learning | Failure → benchmark → candidate lesson → regression → human review | Minimum loop | General effects and ≥80% held-out lift without regression |
| Service | CLI and offline package | Not a service | Cancellable/resumable operation and ≥99.5% measured success |
| User value | Product metrics and protocol defined | Unmeasured | Named cohort, ≥60% weekly retention, ≥50% median time saved |

Run `qf audit` for the live machine-readable assessment. As of 2026-08-13 the
repository-only result is **41.5/100 — concept prototype** with seven operating
evidence blockers. The rule planner now refuses unsupported families, public
evaluations report family/risk slices, and the demo adapter passes 8/8 protocol
checks; none substitutes for real breadth or licensed-data evidence. Scores are
not manually promoted.

## Delivery sequence

### 1. Prove one research family

- Convene 2–3 accountable domain reviewers.
- Build at least 50 held-out event-study and historical-analogy cases.
- Include refusal, revision, date-boundary, universe, unit and selection traps.
- Publish the rubric, denominators, reviewer disagreement and raw outcomes.

### 2. Prove real point-in-time data

- Connect one licensed, revision-aware adapter and document corpus.
- Add observation, availability, revision and effective-time conformance tests.
- Validate claim-to-source lineage under real entitlements and licences.

### 3. Isolate execution

- Move generated code into no-network, read-only, resource-limited workers.
- Replace per-task process spawn with a pre-warmed isolated worker pool.
- Add cancellation, checkpoints and resumability.
- Run sandbox escape, prompt-injection and entitlement adversarial suites.

### 4. Demonstrate operating and user outcomes

- Pilot with a named expert cohort and a pre-registered baseline.
- Measure serious-error escape rate separately from refusal/run failure.
- Measure time to reviewable evidence, reviewer effort, retention and reuse.
- Supply immutable evidence to `qf audit --strict` only after approval.

### 5. Release maturity

- Protect `main` with CI, secret scan and review requirements.
- Enable dependency alerts and automated dependency updates.
- Publish signed releases, attestations and a trusted evidence-package registry.
- Claim PAT-level evidence only when every strict operating gate passes.

## Contribution priorities

The highest-value contributions are counterexamples and evidence: a missed
failure, an expert-authored held-out plan, a correctly versioned adapter, a
research-family contract or a reproducible isolation test. Broad feature
requests without a failure or evaluation case are intentionally lower priority.
