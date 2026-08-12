"""Content-addressed value cache.

The key answers one question: would running this task again produce the same
dataframe? It is built from

  normalised AST      logic, not formatting — reflowing code keeps the hit
  upstream keys       the whole chain above this task, recursively
  data fingerprint    which series, at which content hash, seen as of when
  knowledge date      the same code at a different as_of is a different question
  runtime id          pandas/numpy versions, because their semantics move

Because the key is recursive, editing the last chart in a plan invalidates that
chart alone. That is the difference between an agent you tweak and an agent you
re-run.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..plan.model import Task
from ..static_analysis.ast_checks import CodeFacts

RUNTIME_ID = f"pd{pd.__version__}-np{np.__version__}"


def cache_key(
    task: Task,
    facts: CodeFacts,
    upstream_keys: dict[str, str],
    data_fingerprint: str,
    as_of: str,
) -> str:
    payload = json.dumps(
        {
            "ast": facts.ast_digest,
            "upstream": [upstream_keys[d] for d in task.depends_on],
            "data": data_fingerprint,
            "as_of": as_of,
            "runtime": RUNTIME_ID,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:20]


def frame_fingerprint(df: pd.DataFrame) -> str:
    h = hashlib.sha256()
    h.update(pd.util.hash_pandas_object(df, index=True).to_numpy().tobytes())
    return h.hexdigest()[:16]


class ValueCache:
    """Parquet on disk, memo in process. Disable it to measure what it buys."""

    def __init__(self, root: str | Path, enabled: bool = True):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.enabled = enabled
        self._mem: dict[str, pd.DataFrame] = {}

    def _path(self, key: str) -> Path:
        return self.root / f"{key}.parquet"

    def get(self, key: str) -> pd.DataFrame | None:
        if not self.enabled:
            return None
        if key in self._mem:
            return self._mem[key].copy()
        p = self._path(key)
        if p.exists():
            df = pd.read_parquet(p)
            self._mem[key] = df
            return df.copy()
        return None

    def put(self, key: str, df: pd.DataFrame) -> None:
        if not self.enabled:
            return
        self._mem[key] = df.copy()
        df.to_parquet(self._path(key))

    def clear(self) -> None:
        self._mem.clear()
        for p in self.root.glob("*.parquet"):
            p.unlink()
