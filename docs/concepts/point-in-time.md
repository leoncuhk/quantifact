# Point-in-time

An analysis of the past is worth something only if it could have been run in the
past. This is the correctness dimension that finance does not share with other
data work, and the one that is silent when it breaks: the numbers look fine, the
code looks fine, and the conclusion is a fantasy.

## The bitemporal model

Every observation carries two dates:

| column | meaning |
|---|---|
| `obs_date` | what the number describes — the index |
| `pub_date` | when the number first became knowable |

A read is always taken *as of* a knowledge date and drops anything with a later
`pub_date`. A monthly output gap published 45 days after the reference month is
simply not there on the 14th of the following month, because it was not there in
reality either.

The plan carries the knowledge date (`AnalysisPlan.as_of`) and it is required.
A plan without one cannot be checked for look-ahead, and an unchecked analysis
of the past is not admissible.

## Three enforcement points, in order of strength

**1. The loader is bound.** The harness injects `load_series` and `load_table`
already closed over the knowledge date, and static analysis rejects any keyword
argument to them. Late data is not filtered out — it is never handed over.

```python
load_series("MKT.BRENT.CO.TRI")                       # what the model writes
adapter.read_series("MKT.BRENT.CO.TRI", as_of=...)    # what actually runs
load_series("MKT.BRENT.CO.TRI", as_of="2026-08-01")   # L0-static rejects this
```

**2. Dated outputs are checked.** Any column with role `observation_date` or
`publication_date` must not contain a value later than the knowledge date. This
catches code that *synthesises* dates — a `date_range`, a `resample`, a negative
shift — rather than reading them.

**3. The cache key carries it.** The same code against the same series at a
different `as_of` is a different question and gets a different entry, so a
re-run cannot silently serve yesterday's knowledge.

## Universes, not just series

A universe read as of a date contains the names that were listed then, including
ones that have since died, and excludes ones that had not yet listed. That is
what makes it survivorship-free, and it has a consequence worth stating in the
plan: a market that did not exist has no return for an older episode, so those
cells are `nullable` and any chart that needs both coordinates drops them
*explicitly*.

Event tables work the same way: asking to include an episode that had not begun
raises `LookAheadError` at plan time.

## Where the defence ends

Stated plainly, because a defence whose limits are unstated is a liability:

- **Choices made with hindsight are invisible to it.** An episode window, a
  threshold or a filter picked because you already know how it turned out is
  look-ahead that no loader can catch.
- **Revisions beyond the served vintage are not modelled.** If your hub keeps a
  single revised value per observation, quantifact cannot recover the number as
  first printed. It enforces *knowability*, not *vintage fidelity*.
- **Adapters must supply `pub_date`.** A source that only stores observation
  dates cannot support any of this, and its adapter should say so rather than
  imply otherwise.

## Checking it yourself

```bash
uv run python examples/04_point_in_time/run.py
uv run pytest tests/test_point_in_time.py -v
```
