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
