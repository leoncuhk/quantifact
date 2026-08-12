# Running it for real

## Isolation

quantifact executes generated Python in a restricted namespace. That is a
reduction of blast radius, not a sandbox. For anything that matters:

- run in a container or VM with no credentials in the environment and no
  outbound network;
- mount the data read-only;
- treat the workspace directory as untrusted output;
- put a CPU and memory limit on the process.

## Cost and latency

With a model backend, one run of a 16-task plan costs roughly 20–50 calls
depending on how many repairs it needs. Three things reduce that materially:

1. **Name the runtime.** One line stating the pandas and numpy versions moved
   schema-layer pass rates from 6/16 to 13/16 in the measured runs.
2. **Give the repair loop evidence.** Upstream shapes, dtypes and date ranges,
   not just the verdict.
3. **Keep the cache warm.** Iteration on a report re-executes one task.

## Observability

Every run produces a trace: per task, the cache key, cached or computed, timing,
row count. Keep them. They are what lets a background agent — or a person —
answer "what changed" three weeks later.

## Where the human belongs

Two places, both deliberate:

- **the plan**, before execution: it is short, typed and reviewable, and it is
  where a domain expert catches a wrong window or a wrong universe in seconds;
- **the patch**, after a lesson: `qf teach` writes files, it does not merge them.

## What to monitor

- verdict failure rate by layer — a rising L1 rate usually means a data change,
  not a model change;
- repair rounds per run — trending up means context has drifted from the data;
- cache hit rate on interactive sessions — the number that predicts whether
  people keep using it.
