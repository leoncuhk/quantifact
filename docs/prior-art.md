# Prior art and acknowledgement

## The talk this replicates

The architecture here is an independent implementation of the one Bridgewater
Associates described publicly at INTERRUPT26, in a talk about an internal tool
they call the Pocket Analyst. The ideas taken from it, and worth attributing
clearly:

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

quantifact is not affiliated with, endorsed by, or derived from any Bridgewater
code, data or trademark. No proprietary material was used: this is a clean-room
implementation of publicly described ideas, with synthetic data, and every
number in this repository was measured from this code.

## Where quantifact goes further

Two things the talk did not need to specify, because a firm with fifty years of
data infrastructure already had them, and which any outside implementation must
solve:

1. **Point-in-time as a first-class contract** — bitemporal storage, loaders
   bound to a knowledge date, survivorship-free universes, and `as_of` in the
   cache key. See [concepts/point-in-time.md](concepts/point-in-time.md).
2. **A five-method adapter protocol** so the data layer is replaceable, with
   invariants and licence tags travelling inside the catalog.

## Older ideas this leans on

- **Compilers**: intermediate representations, static analysis, dependency
  graphs, content-addressed builds. None of this is new; it is new *here*.
- **Data contracts and testable pipelines**: dbt tests, Great Expectations, and
  the broader idea that a dataset should ship the assertions that make it
  usable.
- **Bitemporal modelling**: valid time versus knowledge time, from temporal
  databases, which is exactly the distinction finance calls point-in-time.
