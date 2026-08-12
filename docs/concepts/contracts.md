# Contracts

Five layers, cheapest first. L0 to L2 are ordinary Python and run
unconditionally — a model cannot skip a check it finds inconvenient, and the
expensive layers only ever see code that already passed the cheap ones.

| layer | asks | cost | who runs it |
|---|---|---|---|
| **L0 static** | is this code allowed to run at all? | µs | AST walk |
| **L1 schema** | are the declared columns, dtypes, nullability and row order there? | ms | pandas |
| **L1 pit** | does anything post-date the knowledge date? | ms | pandas |
| **L2 invariants** | non-null ratios, ranges, uniqueness, row counts, sums | ms | pandas |
| **L3 semantic** | does the code do what the task says? | seconds + tokens | a model, optional |
| **L4 review** | are the numbers plausible? | ms | heuristics |

## L0 — static

One top-level function, named after the task, whose signature matches the
declared dependencies. No imports, no file or network IO, no clock, no
randomness, no in-place mutation, no keyword arguments to the loaders. Every
line of the coding conventions maps to a check here, which is why the
conventions are enforceable rather than advisory.

## L1 — schema and order

Declared columns in the declared order, dtypes that match, non-nullable columns
that are not null, and rows in the declared sort. Row order is part of the
contract because it is what a reader sees first, and because a model that
re-sorts by the index instead of by the ranking column produces a table that is
correct and useless.

## L2 — invariants

Shipped with the data where possible: an adapter returns the invariants for a
series and the contract layer generates the checks rather than inventing them.
`row_count` bounds derived from the universe and the calendar are the single
most effective check in practice — they catch the join that silently dropped an
entity.

## L3 — semantic

A model reads the task, the code and a sample of the result and answers OK or
PROBLEM. Useful, and not load-bearing: in the runs recorded in
`benchmarks/RESULTS.md` it approved a result that differed from the reference by
ten boundary rows. That is precisely why it is last.

## L4 — self review

Empty frames, constant columns, infinities, robust outliers (median/MAD, never
mean/σ — a total-return index compounds and would fail a naive sigma test),
null ratios, duplicate index rows, charts with too few points. Blocking
findings go back into the repair loop; the rest are surfaced in the report.

## When repair fails

`TaskUnfixable`, with the task name and the failing layer. Nothing degrades
quietly. An analysis that cannot satisfy its own contract must stop, because the
alternative is a chart that nobody can defend in a review.
