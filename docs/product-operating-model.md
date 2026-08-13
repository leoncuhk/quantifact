# Product and operating model

## The first-principles product

Investment research is a controlled belief update, not a document-generation
task. A useful system must reduce the time from an ambiguous question to
decision-grade evidence while bounding undetected error, look-ahead, reviewer
effort and loss of organisational knowledge.

Quantifact therefore optimises **trusted research capacity**:

```
research coverage × update speed × expert acceptance
× reproducibility × traceability
```

The durable product is a `ResearchEvidencePackage`. Chat and HTML are views of
that object. The package preserves the question, reviewed assumptions,
knowledge date, method contracts, source vintages and licences, plan, code,
output fingerprints, verdicts, repairs and claim-level lineage. Its admission
status means that the declared gates passed; it never means that an investment
was approved or a claim was proven true.

## Who uses, benefits and pays

| Role | Job to be done | Evidence of value |
|---|---|---|
| Analyst | remove repetitive binding, cleaning, reruns and chart updates | time to first reviewable evidence; plan edit rate |
| Portfolio manager | challenge a claim and update it when facts change | update latency; claim-to-source drill-down |
| Head of research / CIO | scale expert judgement and retain methods | workflow reuse; accepted evidence per expert hour |
| Risk, compliance and model governance | reconstruct what was knowable and why release was allowed | PIT violations; untraceable claims; review time |
| CTO / data platform | replace fragmented notebooks with governed execution | tool coverage; reliability; duplicated pipelines |

The economic buyer is normally the CIO or Head of Research where speed and
coverage dominate, the COO/CRO where governance dominates, and the CTO/CDO for
platform consolidation. The initial customer should have expensive research
labour, repeated workflows, versioned data, high review cost and material error
consequences. A team seeking only news summaries is not the target.

Annual value should be measured, not asserted:

```
hours saved + value of shorter decision latency + expected loss avoided
+ coverage/capacity gained - total operating cost
```

Alpha is an important eventual outcome but a poor early sales metric because it
is noisy and difficult to attribute. Early pilots should pre-register time,
review effort, coverage, serious-error escape rate and adoption metrics.

## Authority model

| Actor | May decide | May not decide |
|---|---|---|
| Model | propose a plan, implementation, repair, rival or test | permissions, mandatory gates, evidence admission |
| System | data visibility, execution, cache identity, checks and admission | economic importance, portfolio action |
| Expert | approve the design, challenge evidence, accept lessons and make decisions | silently waive provenance or mandatory controls |

In short: **the model proposes, the system admits evidence, the expert judges**.

## Build order

1. Select one repeated, high-value research family with observable correctness.
2. Build expert-authored held-out questions, gold plans, traps and refusal cases.
3. Connect licensed point-in-time data and encode its semantics in adapters.
4. Compile that family's methods into deterministic contracts.
5. Run generated code in isolated, resource-limited workers.
6. Integrate evidence review into the tools researchers already use.
7. Expand only from reproduced real failures, with full regression and approval.

Do not begin with a universal autonomous analyst. Breadth without evaluated
methods increases the surface on which plausible wrong answers can escape.

## Organisational ownership

- **Research methods council:** taxonomy, gold plans, method contracts, error
  severity and acceptance. Domain experts have veto power over methodology.
- **Data and platform:** PIT/vintage semantics, permissions, licences,
  isolation, lineage, reliability and cost.
- **Agent and evaluation:** planner/compiler backends, repair, evaluation
  harness, failure clustering, model upgrades and adversarial tests.
- **Single product owner:** accountable for expert-accepted evidence, escaped
  critical errors, review time, reuse and adoption—not model calls or reports.

Shared controls change only through a reproduced failure, a failing benchmark,
a candidate change, full regression and named human approval.
