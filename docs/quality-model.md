# What quantifact is trying to solve

## First principles

Investment research converts an ambiguous question into a decision-relevant
belief. The expensive part is not producing text or code; it is establishing
that the evidence is relevant, knowable at the stated date, calculated under an
agreed definition, reviewable, and cheap enough to revise when the question
changes.

The product objective is therefore:

> Reduce time from question to decision-grade evidence, subject to explicit
> bounds on undetected error, look-ahead, data entitlement, reproducibility and
> reviewer effort.

PAT's public architecture attacks that objective with a typed analysis plan,
parallel code generation, compiler checks, harness-owned execution, layered
contracts, traces, caching, self-review, writeback and a benchmark-gated learning
loop. quantifact's goal is an independent, point-in-time-safe implementation of
that architecture that can be measured rather than trusted.

Quantifact additionally compiles a critical-thinking contract before execution:
bounded claims, rival explanations, falsifiers, evidence tasks and inference
limits. This prevents unsupported conclusions from reaching a report, but it
does not count as evidence that the declared design is scientifically adequate;
that remains an expert-held-out evaluation problem.

## What “highest quality” means

Highest quality is an outcome, not a feature count. A system must demonstrate:

1. **Correctness** — expert-held-out answers are right, and wrong answers fail
   closed; all evidence is point-in-time.
2. **Research breadth** — it asks substantive clarifications and produces sound
   plans across the desk's real question taxonomy.
3. **Data and tool coverage** — it can reach the licensed data, research and
   analytical tools people actually use, under the same permissions.
4. **Diagnosability** — a reviewer can reconstruct every input, assumption,
   transformation, check, repair and output.
5. **Safe learning** — feedback improves held-out outcomes and cannot silently
   regress the shared system.
6. **Production fitness** — isolation, reliability, cancellation, continuation,
   cost and latency meet declared SLOs.
7. **Expert outcomes** — experts retain the product, save time and accept its
   evidence without lowering their review standard.

A weighted score alone is insufficient. `qf audit` also applies critical gates
and a minimum per-dimension threshold. Missing expert or production evidence
scores zero; repository features cannot substitute for it.

## Evaluation protocol

Run the self-audit:

```bash
qf audit --out audit.md --json audit.json
qf audit --evidence benchmarks/quality-evidence.json --strict
```

The first command executes repository probes. The second combines them with a
versioned operating-evidence file. `--strict` exits non-zero until the result is
`PAT-level evidence`.

The tagged-release workflow enforces the same strict check and refuses to
publish without `benchmarks/quality-evidence.json`. The example file is not
accepted as evidence.

Operating evidence must name its measurement window, cohort, denominator,
rubric and approver. Use `benchmarks/quality-evidence.example.json` as the
schema, but do not turn estimates into scores.

## Delivery plan

### Gate 1 — make the prototype claim exact

- Keep all automatic probes and the full test suite green.
- Package the current LLM planner, document retrieval and workflows.
- Rebuild the moved environment and smoke-test the wheel, not only the source.
- Persist a single run receipt containing search, plan/repair, execution,
  contract, citation and writeback lineage.

Exit: no automatic critical blocker and reproducible install/run from a wheel.

### Gate 2 — prove research breadth

- Build a taxonomy of 6–10 research families with domain experts.
- Curate at least 50 held-out questions, including refusal cases and traps.
- Replace oil-event-specific clarification with dynamic, benchmarked questions.
- Expand the operation/tool registry only in response to those gold plans.

Exit: at least 90% acceptable plans, no invented identifiers, and every failure
is explicit.

### Gate 3 — prove decision-grade answers

- Attach a licensed point-in-time dataset and document corpus.
- Create exact expected-value, row-set, date-boundary and citation assertions.
- Double-review a held-out answer set; adjudicate reviewer disagreement.
- Measure undetected wrong-answer rate separately from run failure rate.

Exit: at least 95% expert acceptance and zero known silent critical errors.

### Gate 4 — prove safe operations and learning

- Execute generated code in a no-network, resource-limited sandbox.
- Add persistent, cancellable and resumable chat sessions with dynamic tools.
- Generalise Teach to planner, workflow, contract and harness changes, all behind
  human approval and full regression.
- Run adversarial entitlement, prompt-injection and sandbox-escape evaluations.

Exit: isolation tests pass, service SLO >=99.5%, and accepted lessons improve
held-out outcomes without regression.

### Gate 5 — prove product value

- Pilot with a named expert cohort and pre-register success metrics.
- Measure weekly retention, end-to-end time saved, plan edits, reviewer effort,
  failure causes and trust calibration.
- Promote only when evidence holds across more than one research family and one
  data adapter.

Exit: >=60% weekly retention and >=50% median time saved without reducing
correctness or review standards. Only then use the PAT-level claim.
