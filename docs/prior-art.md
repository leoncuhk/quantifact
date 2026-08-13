# Prior art and acknowledgements

## Inspiration

Quantifact was inspired in part by Bridgewater Associates' public presentation
of *Pat, the Pocket Analyst* at INTERRUPT26. That talk offered a compelling way
to think about reliable agentic analysis:

- **the plan is the analysis** — invest in a detailed plan and execution
  becomes reliable;
- **a task is a function type signature**, and a plan is "a natural-language
  Python project" rather than a to-do list;
- **codegen fans out** because a task needs its inputs' schemas, not their code;
- **correctness is enforced in the architecture** — the orchestration is plain
  code, so agents cannot forget to validate;
- **the harness runs the code for the model**, which is what makes caching and
  tracing possible;
- **treat agentic coding as a compiler problem**, not an agent problem;
- **a lesson must first reproduce the failure** before it is allowed to fix it.

Those ideas sit alongside established work in compilers, data contracts,
temporal databases, reproducible computation, and software testing. Quantifact
develops them as an independent open-source project with its own code, data
model, evidence format, and evaluation gates. It is not affiliated with or
endorsed by Bridgewater Associates.

## Quantifact's focus

The project concentrates on two requirements that matter when this architecture
must work across independently supplied data systems:

1. **Point-in-time as a first-class contract** — bitemporal storage, loaders
   bound to a knowledge date, survivorship-free universes, and `as_of` in the
   cache key. See [concepts/point-in-time.md](concepts/point-in-time.md).
2. **A six-method adapter protocol** so the data layer is replaceable, with
   invariants and licence tags travelling inside the catalog.

## Older ideas this leans on

- **Compilers**: intermediate representations, static analysis, dependency
  graphs, content-addressed builds. None of this is new; it is new *here*.
- **Data contracts and testable pipelines**: dbt tests, Great Expectations, and
  the broader idea that a dataset should ship the assertions that make it
  usable.
- **Bitemporal modelling**: valid time versus knowledge time, from temporal
  databases, which is exactly the distinction finance calls point-in-time.

## Open-source systems reviewed

The relevant projects solve different layers; popularity is not evidence that
their trust model should be copied.

| Project | Strength to learn from | What Quantifact should not infer |
|---|---|---|
| [Qlib](https://github.com/microsoft/qlib) | broad quant workflow, datasets, models and experiment infrastructure | a backtest/model platform by itself makes generated research admissible |
| [RD-Agent](https://github.com/microsoft/RD-Agent) | experiment generation, feedback and iterative R&D | autonomous iteration may rewrite shared controls without benchmark governance |
| [OpenBB](https://github.com/OpenBB-finance/OpenBB) | provider ecosystem and analyst/agent data interfaces | a broad catalog supplies revision-aware PIT semantics automatically |
| [FinRobot](https://github.com/AI4Finance-Foundation/FinRobot) | composable financial agents and approachable examples | more agent roles imply stronger correctness or reproducibility |
| [FinGPT](https://github.com/AI4Finance-Foundation/FinGPT) | financial models, datasets and evaluation community | model domain knowledge can replace data and method contracts |
| [ai-hedge-fund](https://github.com/virattt/ai-hedge-fund) | understandable multi-perspective demonstration | simulated personas constitute an institutional research process |
| [IRAB](https://github.com/Rabyte-Technology/Investment-Research-Agent-Benchmark) | real buy-side task taxonomy, per-task rubrics, gold references and held-out evaluation | an LLM judge alone is sufficient for exact numeric/PIT correctness |

The synthesis is deliberate: borrow data/tool extensibility from OpenBB and
Qlib, experiment regression from RD-Agent, usable examples from financial-agent
projects, and real-task evaluation structure from IRAB. Keep PAT's thick plan,
system-owned execution and benchmark-gated learning as the control plane.

This review directly produced three executable changes:

- unsupported rule-planner questions now fail closed instead of receiving an
  oil-event workflow;
- benchmark cases declare research family, risk tags, expected outcome and
  severity, with sliced reports and a separate silent-critical-error count;
- third-party adapters have a public PIT conformance suite, and generated tasks
  may run behind a disposable process boundary with explicit limitations.
