"""The execution harness — quantifact runs the code, the model does not.

Owning execution is what makes four things possible at once: the value cache,
a trace an auditor can read, containment (no builtins beyond a whitelist, no
imports, no IO), and the look-ahead defence — because the ``load_series`` and
``load_table`` handed to generated code are already closed over the plan's
knowledge date.

Execution is layer by layer over the dependency DAG, and the DAG is the one
static analysis derived from the code, cross-checked against the one the plan
declared.
"""

from __future__ import annotations

import builtins
import multiprocessing as mp
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from ..plan.layers import topo_layers
from ..plan.model import AnalysisPlan, PlanError, Task
from ..static_analysis.ast_checks import CodeFacts, analyse
from ..static_analysis.dag import cross_check, dependency_graph
from .cache import ValueCache, cache_key, frame_fingerprint

SAFE_BUILTINS = {
    n: getattr(builtins, n)
    for n in (
        "abs",
        "all",
        "any",
        "bool",
        "dict",
        "enumerate",
        "float",
        "int",
        "len",
        "list",
        "max",
        "min",
        "range",
        "round",
        "set",
        "sorted",
        "str",
        "sum",
        "tuple",
        "zip",
        "isinstance",
        "getattr",
        "print",
        "ValueError",
        "KeyError",
        "TypeError",
        "Exception",
        "reversed",
        "map",
        "filter",
    )
}


def _namespace(adapter: Any, as_of: str) -> dict[str, Any]:
    """The generated-code namespace, shared by in-process and worker execution."""

    def load_series(series_id: str) -> pd.Series:
        return adapter.read_series(series_id, as_of=as_of)

    def load_table(name: str) -> pd.DataFrame:
        return adapter.read_table(name, as_of=as_of)

    return {
        "__builtins__": SAFE_BUILTINS,
        "pd": pd,
        "np": np,
        "load_series": load_series,
        "load_table": load_table,
    }


def _execute_source(
    adapter: Any, task_name: str, source: str, args: list[pd.DataFrame], as_of: str
) -> pd.DataFrame:
    ns = _namespace(adapter, as_of)
    exec(compile(source, f"<task:{task_name}>", "exec"), ns)
    fn = ns.get(task_name)
    if not callable(fn):
        raise RuntimeError(f"generated code defines no function '{task_name}'")
    result = fn(*args)
    if not isinstance(result, pd.DataFrame):
        raise TypeError(
            f"{task_name} returned {type(result).__name__}, expected DataFrame"
        )
    return result.reset_index(drop=True)


def _process_worker(
    connection,
    adapter: Any,
    task_name: str,
    source: str,
    args: list[pd.DataFrame],
    as_of: str,
    cpu_seconds: int,
    memory_mb: int,
) -> None:
    """Child entry point. Resource limits are best-effort and platform-specific."""
    try:
        try:
            import resource

            resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))
            if hasattr(resource, "RLIMIT_AS"):
                limit = memory_mb * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
        except (ImportError, OSError, ValueError):
            pass
        connection.send((True, _execute_source(adapter, task_name, source, args, as_of)))
    except BaseException as exc:  # child must return a bounded error, then die
        connection.send((False, f"{type(exc).__name__}: {exc}"))
    finally:
        connection.close()


@dataclass
class TaskTrace:
    task: str
    cache_key: str
    cached: bool
    seconds: float
    rows: int
    columns: list[str]
    error: str | None = None


@dataclass
class RunResult:
    frames: dict[str, pd.DataFrame]
    traces: list[TaskTrace]
    layers: list[list[str]]
    as_of: str = ""

    @property
    def wall_seconds(self) -> float:
        return sum(t.seconds for t in self.traces)

    @property
    def cache_hits(self) -> int:
        return sum(1 for t in self.traces if t.cached)

    def trace(self, name: str) -> TaskTrace:
        return next(t for t in self.traces if t.task == name)


class TaskExecutionError(RuntimeError):
    def __init__(self, task: str, message: str, traces: list[TaskTrace]):
        self.task = task
        self.message = message
        self.traces = traces
        super().__init__(f"task '{task}' failed: {message}")


class ExecutionHarness:
    def __init__(self, adapter: Any, cache: ValueCache):
        self.adapter = adapter
        self.cache = cache

    # ------------------------------------------------------------ builtins
    def _namespace(self, as_of: str) -> dict[str, Any]:
        """Loaders bound to the knowledge date. Generated code cannot rebind
        them: static analysis rejects any keyword argument to a loader."""
        return _namespace(self.adapter, as_of)

    def _compile(
        self, task_name: str, source: str, as_of: str
    ) -> Callable[..., pd.DataFrame]:
        ns = self._namespace(as_of)
        exec(compile(source, f"<task:{task_name}>", "exec"), ns)
        fn = ns.get(task_name)
        if not callable(fn):
            raise RuntimeError(f"generated code defines no function '{task_name}'")
        return fn

    # ----------------------------------------------------------- data ident
    def _fingerprint(self, task: Task, as_of: str) -> str:
        if task.series_inputs:
            return self.adapter.fingerprint(task.series_inputs, as_of=as_of)
        table = (task.op or {}).get("table")
        if table:
            return frame_fingerprint(self.adapter.read_table(table, as_of=as_of))
        return ""

    # ------------------------------------------------------------- one task
    def run_one(
        self, task: Task, source: str, frames: dict[str, pd.DataFrame], as_of: str
    ) -> pd.DataFrame:
        """Execute a single task against already-materialised upstream frames.
        Used by the repair loop and by graders; no caching, no layering."""
        return self._materialise(
            task, source, [frames[d] for d in task.depends_on], as_of
        )

    def _materialise(
        self, task: Task, source: str, args: list[pd.DataFrame], as_of: str
    ) -> pd.DataFrame:
        return _execute_source(self.adapter, task.name, source, args, as_of)

    # ----------------------------------------------------------------- run
    def run(
        self,
        plan: AnalysisPlan,
        codes: dict[str, str],
        facts: dict[str, CodeFacts] | None = None,
        on_task: Callable[[TaskTrace], None] | None = None,
    ) -> RunResult:
        facts = facts or {n: analyse(n, src) for n, src in codes.items()}
        as_of = plan.as_of

        declared = {t.name: list(t.depends_on) for t in plan.tasks}
        problems = cross_check(dependency_graph(facts), declared)
        if problems:
            raise PlanError(problems)

        layers = topo_layers(declared)
        frames: dict[str, pd.DataFrame] = {}
        keys: dict[str, str] = {}
        traces: list[TaskTrace] = []

        for layer in layers:
            for name in layer:
                task = plan[name]
                key = cache_key(
                    task, facts[name], keys, self._fingerprint(task, as_of), as_of
                )
                keys[name] = key

                t0 = time.perf_counter()
                cached = self.cache.get(key)
                if cached is not None:
                    frames[name] = cached
                    tr = TaskTrace(
                        name,
                        key,
                        True,
                        time.perf_counter() - t0,
                        len(cached),
                        list(cached.columns),
                    )
                else:
                    try:
                        df = self._materialise(
                            task,
                            codes[name],
                            [frames[d] for d in task.depends_on],
                            as_of,
                        )
                    except Exception as e:
                        tr = TaskTrace(
                            name,
                            key,
                            False,
                            time.perf_counter() - t0,
                            0,
                            [],
                            error=f"{type(e).__name__}: {e}",
                        )
                        traces.append(tr)
                        if on_task:
                            on_task(tr)
                        raise TaskExecutionError(name, str(e), traces) from e
                    if not isinstance(df, pd.DataFrame):
                        raise TaskExecutionError(
                            name,
                            f"returned {type(df).__name__}, expected DataFrame",
                            traces,
                        )
                    df = df.reset_index(drop=True)
                    self.cache.put(key, df)
                    frames[name] = df
                    tr = TaskTrace(
                        name,
                        key,
                        False,
                        time.perf_counter() - t0,
                        len(df),
                        list(df.columns),
                    )
                traces.append(tr)
                if on_task:
                    on_task(tr)

        return RunResult(frames=frames, traces=traces, layers=layers, as_of=as_of)


class ProcessExecutionHarness(ExecutionHarness):
    """Run each generated task in a disposable, resource-bounded process.

    This contains interpreter crashes, runaway CPU and wall-time overruns. It is
    intentionally not called a sandbox: the worker still shares the host kernel
    and network namespace. Production deployment must put this worker behind a
    no-network container or VM boundary.
    """

    def __init__(
        self,
        adapter: Any,
        cache: ValueCache,
        *,
        timeout_seconds: float = 10.0,
        cpu_seconds: int = 5,
        memory_mb: int = 1024,
    ):
        super().__init__(adapter, cache)
        self.timeout_seconds = timeout_seconds
        self.cpu_seconds = cpu_seconds
        self.memory_mb = memory_mb

    def _materialise(
        self, task: Task, source: str, args: list[pd.DataFrame], as_of: str
    ) -> pd.DataFrame:
        context = mp.get_context("spawn")
        parent, child = context.Pipe(duplex=False)
        process = context.Process(
            target=_process_worker,
            args=(
                child,
                self.adapter,
                task.name,
                source,
                args,
                as_of,
                self.cpu_seconds,
                self.memory_mb,
            ),
        )
        process.start()
        child.close()
        process.join(self.timeout_seconds)
        if process.is_alive():
            process.terminate()
            process.join(1)
            parent.close()
            raise TimeoutError(
                f"task '{task.name}' exceeded {self.timeout_seconds:.2f}s wall limit"
            )
        if not parent.poll():
            code = process.exitcode
            parent.close()
            raise RuntimeError(f"task worker exited without a result (exitcode={code})")
        ok, value = parent.recv()
        parent.close()
        if not ok:
            raise RuntimeError(value)
        return value
