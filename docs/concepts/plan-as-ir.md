# The plan is an intermediate representation

A to-do list says *what to do next*. An intermediate representation says *what
must be true of the result*. That difference is what everything downstream is
built on.

## A task is a function type signature

```python
Task(
    name="market_episode_returns",  # == the function name
    type="table_logic",
    description="Total return of each market over the 20 calendar days "
    "following each episode start.",
    depends_on=["market_prices", "spine_episodes"],  # == the parameters
    index=["market_id", "episode"],  # == the row grain
    row_expectation="one row per market per episode",
    sort=[["market_id", True], ["episode", True]],  # == presentation order
    columns=[...],  # == the return type
    invariants=[{"kind": "row_count", "min": 223, "max": 223}, ...],
)
```

Everything a compiler needs is there: inputs, output type, and assertions about
the output. Nothing about *how*.

## What that buys

**Parallel codegen.** A task needs the schemas of its inputs, never their code,
so all tasks compile at once. Wall time is set by the slowest single task, not
by how many there are — measurable with `qf bench`.

**A real dependency graph.** Static analysis reads the actual dependencies out
of the generated function's parameters and compares them against the declared
ones. A task that quietly consumes an extra frame is caught; in a prompt-only
system it is invisible.

**Compile errors.** Cycles, unknown upstreams, columns nobody produces,
conflicting units, unbound series and a missing knowledge date are rejected in
milliseconds, before a token is spent.

**Cache identity.** Because the plan pins semantics, the code's normalised AST
plus its inputs is a complete identity for the value.

**Something to validate against.** "Correct" is not a vibe: it is the declared
columns, dtypes, row grain, order and invariants.

## Roles

Columns carry a semantic role — `observation_date`, `publication_date`,
`entity`, `dimension`, `measure`. Roles are what let contracts say "no
observation in this frame may post-date the knowledge date" without guessing
from column names, and what let a report label axes without being told.

## Where plans come from

`RulePlanner` builds one deterministically, which is what the benchmarks run
against. A model-driven planner produces the same structure; the difference is
that the compiler treats both with equal suspicion.
