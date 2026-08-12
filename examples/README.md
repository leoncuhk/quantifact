# Examples

| | what it shows | needs |
|---|---|---|
| [04_point_in_time](04_point_in_time/) | six ways look-ahead is stopped | nothing |
| `01_quickstart/run.py` | plan → contracts → execute → report, then the cached second run | nothing |
| `02_bring_your_own_data/build_hub.py` | the same plan against a DuckDB hub you build ([guide](../docs/guides/byo-data.md)) | `quantifact[duckdb]` |
| `03_llm_backend` | a real model writing every task | an API key |

Start with 04 if you are evaluating whether this is serious.

```bash
uv run python examples/01_quickstart/run.py
uv run python examples/04_point_in_time/run.py
uv run --extra duckdb python examples/02_bring_your_own_data/build_hub.py
```

## 03 — a real model writing the code

```bash
export QF_LLM_API_KEY=...        # any OpenAI-compatible endpoint
export QF_LLM_BASE_URL=https://api.openai.com/v1
export QF_LLM_MODEL=gpt-4o-mini
qf ask --backend llm --fix --fix-rounds 5
```

The model gets one task at a time — its contract, its upstream schemas, the
knowledge date and the conventions — and writes one pandas function. Everything
else is unchanged: same static analysis, same contracts, same cache. `--fix`
turns each failure into a verdict and sends it back with a description of what
the data actually looks like. Grading runs are in
[`../benchmarks/RESULTS.md`](../benchmarks/RESULTS.md).
