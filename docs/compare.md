# How this compares

The first question anyone technical asks is "isn't this Dagster with an LLM?" —
a fair question, answered here rather than in an issue.

## Dagster, dbt, Prefect

They orchestrate assets **you have already written**. Their graph is authored by
a human, reviewed once, and then trusted; their job is to schedule it, keep it
fresh and tell you when it broke.

quantifact orchestrates assets that **did not exist ten seconds ago**. Its
graph is derived per question, from code a model just wrote, and nothing about
it is trusted: static analysis re-derives the dependencies from the code and
compares them to what was declared, contracts check the result against a
declared type, and the run stops if it cannot satisfy them.

The overlap is real — a typed asset graph with materialisation and caching is
the same idea in both — and if your analyses are stable and hand-written, use
Dagster. quantifact is for the case where the analysis is *the answer to a
question asked once*.

| | Dagster / dbt | quantifact |
|---|---|---|
| who writes the graph | a human, once | a planner, per question |
| trust model | code is reviewed, then trusted | code is never trusted, always checked |
| unit of work | an asset / a model | a task with a declared type |
| point-in-time | your responsibility | enforced at the loader and checked on outputs |
| failure mode | pipeline breaks loudly | contract breaks loudly, then a repair loop |

## LangChain, LangGraph and agent frameworks

They give you a way to *build* an agent: tools, memory, control flow, retries.
quantifact is not a framework for building agents; it is one narrow workflow
built and benchmarked heavily — analytical investigation over a series store.

The relevant difference is where the control flow lives. In an agent framework
the model decides what happens next. Here the sequence is ordinary Python, and
the model's only job is to emit one function per task. That is what makes the
checks unskippable and the runs reproducible; it is also what makes quantifact
useless for open-ended tool use, which those frameworks handle well.

## Notebook copilots and "chat with your data"

Excellent for exploration, structurally unable to answer the reviewer's
question — *what exactly did it read, when could it have known it, and what would
have caught it if it were wrong*. A copilot's output is a transcript; this one's
output is a plan, a contract, a trace, a cache key and a report that carries all
four.

## Backtesting frameworks (Zipline, backtrader, QuantConnect, qlib)

Different layer entirely. They simulate strategies; quantifact answers research
questions and produces tables and charts. If anything it sits *before* them: the
series it writes back are the kind of input a strategy consumes.

## What quantifact is not

Not a backtester, not a trading system, not a data product, not a general agent
framework. See the README section of the same name.

## The strategic boundary

Quantifact should interoperate with these ecosystems rather than reproduce
them. OpenBB-style providers and Qlib-style data/model assets belong behind the
adapter/tool boundary. RD-Agent-style experiment proposals belong behind the
plan/compiler boundary. External real-task benchmarks belong in the evaluation
protocol. None receives authority to waive PIT, method, execution or admission
contracts.
