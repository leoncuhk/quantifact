# Caching

The value cache is not a performance optimisation bolted on afterwards. It is
what makes the product usable: the first run is interesting, the *second* run is
what decides whether an investor keeps the tool open.

## The key

```
key = H(normalised AST, upstream keys, data fingerprint, as_of, runtime id)
```

- **normalised AST** — logic, not formatting. Reflowing code or changing a
  comment keeps the hit; changing a filter does not.
- **upstream keys** — recursive, so invalidation propagates downwards and only
  downwards.
- **data fingerprint** — which series, at which content hash, seen as of when.
- **as_of** — the same code at a different knowledge date is a different
  question.
- **runtime id** — pandas and numpy semantics move between versions.

## What it buys, measured

`qf bench`, deterministic backend, 16 tasks:

| scenario | wall | executed | cached |
|---|---:|---:|---:|
| cold | 133 ms | 16 | 0 |
| warm | 5.0 ms | 0 | 16 |
| one-task edit | 6.1 ms | 1 | 15 |
| same edit, cache off | 89 ms | 16 | 0 |

The row that matters is the third: editing the last chart in a plan re-executes
*one* task. An agent that re-invokes its own code re-runs everything, which is
the fourth row.

## Why owning execution is the precondition

You cannot cache what you do not run. A coding agent that shells out to run its
own code gives up caching, tracing, containment and the knowledge-date binding
in one move — and gains a tool-call round trip per step.
