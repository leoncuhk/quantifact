# Critical thinking as a contract

The execution engine can establish that code satisfies a plan. It cannot infer
that the plan asks the right question. A perfectly reproducible calculation can
still be useless because it selected a convenient episode, ignored a rival
explanation, confused association with causation, or discovered its hypothesis
after looking at the answer.

Quantifact therefore treats critical thinking as part of the intermediate
representation, before code generation, rather than as persuasive prose added
to the report afterwards.

## What a research design declares

Every executable run carries:

- the question type: descriptive, comparative, causal or predictive;
- the decision context and the deliberately bounded claims;
- the tasks whose outputs count as evidence for each claim;
- observations that would weaken or falsify each claim;
- rival explanations and the tasks intended to distinguish them;
- limitations the design cannot remove;
- an identification strategy for causal claims;
- an out-of-sample test for predictive claims.

The plan compiler rejects missing evidence, undeclared rivals, causal language
without identification, and predictive language without an out-of-sample test.
After execution, the evidence gate checks that every named task actually
materialised a non-empty result. The report exposes the complete design next to
the charts, and the receipt preserves it inside the hashed plan.

## What this does and does not prove

This gate limits *admissible inference*. It does not prove that a claim is true,
that a falsifier is powerful, or that a discriminating task actually rules out
its rival. Those require research-family-specific benchmarks and expert review.

The useful guarantee is narrower:

> An undeclared, unfalsifiable or unsupported claim cannot quietly acquire the
> visual authority of a finished Quantifact report.

## Why not use another model as a critic?

A critic model is useful for proposing missed rivals and tests, but it is not a
load-bearing control. It can share the planner's blind spot, approve plausible
prose, or rationalise a result after seeing it. Deterministic structure remains
the gate; models may suggest content within it.

## Next evidence required

The generic contract is only the first layer. A production research taxonomy
should add executable design checks by family:

- event studies: placebo dates, window sensitivity and episode-selection rules;
- cross-sectional work: universe construction, multiple testing and holdouts;
- causal work: treatment timing, controls, pre-trends and negative controls;
- predictive work: walk-forward splits, leakage checks and stability by regime.

These checks should be added only against expert-authored held-out failures,
not because they sound methodologically sophisticated.
