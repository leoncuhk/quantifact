# A real model writing the code

```bash
export QF_LLM_API_KEY=...          # any OpenAI-compatible endpoint
export QF_LLM_BASE_URL=https://api.openai.com/v1
export QF_LLM_MODEL=gpt-4o-mini

qf ask --backend llm --fix --fix-rounds 5
```

The model receives one task at a time — its contract, its upstream schemas, the
knowledge date and the coding conventions — and writes one pandas function.
Everything else is unchanged: the same static analysis, the same contracts, the
same cache.

`--fix` enables the repair loop. A failure of any kind (an exception, a schema
breach, an implausible result) becomes a verdict, and the verdict plus a
description of what the data actually looks like goes back to the model.

## What to expect

Grading a real model task by task against the reference compiler is what
`benchmarks/RESULTS.md` records. The short version from the runs published
there: the static layer passes on the first attempt, the *semantic* layers do
not, and the failures are always the same four families — wrong unit, wrong
frequency, wrong join key, wrong window. None of them reached a report.
