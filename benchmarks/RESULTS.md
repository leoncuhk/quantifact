# Results

Every number here was measured on this repository. The deterministic ones
reproduce anywhere with `qf bench`; the language-model ones depend on the model
and endpoint, which are named.

Plan under test: the demo question, **16 tasks in 5 layers**, `as_of 2026-08-01`,
synthetic adapter.

---

## 1. What the harness buys — `qf bench`

Reference (deterministic) backend, pandas 3.0.5, Apple silicon laptop.

| scenario | wall | executed | cached |
|---|---:|---:|---:|
| cold — empty cache | 158.5 ms | 16 | 0 |
| warm — nothing changed | 6.0 ms | 0 | 16 |
| one-task edit — final chart retitled and reordered | 7.0 ms | 1 | 15 |
| the same edit, caching disabled | 100.0 ms | 16 | 0 |

- **warm vs cold: 26.4×**
- **one-task edit vs the same edit uncached: 14.4×** — the number that decides
  whether a person iterates on an analysis or gives up
- codegen at 0.40 s simulated latency per task: **parallel 0.41 s vs serial
  6.46 s (15.8×)**, and a 3-task plan takes **0.41 s** — the same as the 16-task
  plan, because fan-out is a property of the plan, not of the model
- determinism: **16/16 tasks byte-identical, 16/16 values identical** across two
  independent compilations

Absolute times are milliseconds because the reference backend compiles a
structured spec instead of calling a model. The **ratios** are the transferable
part: they come from the two mechanisms — one edit re-executes one task, and
codegen wall time is set by the slowest single task.

---

## 2. A real model writing every task

`deepseek-v4-flash`, temperature 0, served through a third-party
OpenAI-compatible gateway (the gateway is irrelevant to the result; the model
name is not).
Every task is graded against the reference compiler as oracle: which contract
layers it passed, and whether its values match.

### 2.1 Bare prompt, no repair loop

| layer | passed |
|---|---:|
| L0 static — conventions, signature, no IO/clock/randomness | **16/16** |
| L1 schema — declared columns, dtypes, order | 9/16 |
| L2 invariants | 9/16 |
| runtime errors | 7 |
| **values equal to the oracle** | **9/16** |

Every failure was semantic, and **not one wrong number reached a report**. The
failures cluster into four families, all of them the data layer's problem as
much as the model's:

| what happened | family |
|---|---|
| five ingestion tasks called `Series.rename(columns=…)`, which pandas 3 does not have | wrong runtime API |
| `pd.to_timedelta(unit='M')` — removed in pandas 3 | wrong runtime API |
| an exact-date merge of episode starts against month-end observations → empty result | wrong join key |
| `KeyError: 'market_id'` from grouping the wrong frame | wrong join key |

### 2.2 One line of context, then a repair loop

"Target runtime: pandas 3.0.5 / numpy 2.5.2" is one line. The repair loop feeds
each verdict back with the upstream schemas and a description of what the data
actually looks like.

| configuration | L0 | L1 | L2 | runtime errors | values == oracle |
|---|---:|---:|---:|---:|---:|
| bare prompt | 16/16 | 9/16 | 9/16 | 7 | 9/16 |
| + runtime named, + repair loop (round 0) | 16/16 | 12/16 | 14/16 | repaired | 12/16 |
| + runtime named, + repair loop (round 1) | 16/16 | 13/16 | 13/16 | repaired | 13/16 |

Cost of one graded run: **53 calls, ~80k tokens, 490 s of API time**.

### 2.3 Determinism

Two independent compilations of the same plan at temperature 0:

| | code byte-identical | values identical |
|---|---:|---:|
| reference compiler | 16/16 | 16/16 |
| the model | 7/16 | **12/16** |

The model agrees with itself on **values** far more often than on **text**,
which is the whole argument for writing the contract on values — schema, units,
row grain, row order, invariants — and never on code.

---

## 3. What none of the deterministic layers caught

In an earlier run of the same architecture, the model's event-time overlay
produced 630 rows where the oracle produced 620: the boundary months of each
event window were handled differently. L1, L2 and L4 all passed — both versions
satisfy the declared contract — and **L3 semantic review also said OK**.

That single result is the argument for hard benchmarks over model judgement, and
the reason L3 is the last layer rather than the first. Where it matters, tighten
the contract: an exact `row_count` derived from the universe and the calendar
would have caught it.

---

## Reproducing

```bash
qf bench                                   # section 1
QF_LLM_API_KEY=... QF_LLM_BASE_URL=... QF_LLM_MODEL=... \
  uv run python tools/llm_trial.py --rounds 2 --fix --runtime-hint   # section 2
```

Raw output is committed alongside this file: `bench.json`,
`llm_trial_baseline.json`, `llm_trial.json`.
