"""Point-in-time: the one correctness dimension finance does not share.

An analysis of the past is only worth something if it could have been run in
the past. Three mechanisms enforce that here, in increasing order of how much
they can be talked out of:

1. **The loader is bound.** The harness injects ``load_series`` and
   ``load_table`` already closed over the plan's knowledge date. Generated code
   cannot pass its own ``as_of``; static analysis rejects the attempt. Data
   published after the knowledge date is not filtered out later — it is never
   handed over in the first place.

2. **The contract checks the output.** Any column declared with role
   ``observation_date`` or ``publication_date`` must not contain a value later
   than the knowledge date. This catches code that *synthesises* future dates
   (a date range, a resample, a forward shift) rather than reading them.

3. **The cache key carries it.** The same code against the same series at a
   different ``as_of`` is a different question and gets a different entry.

What this does *not* do: it does not model revisions of an already published
number beyond the vintage the adapter serves, and it does not detect
look-ahead that is smuggled in through a parameter chosen with hindsight. Both
are stated in the docs rather than silently implied.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from ..plan.model import Task, parse_date
from .verdict import Verdict

DATE_ROLES = ("observation_date", "publication_date")


class LookAheadError(RuntimeError):
    """Raised when data later than the knowledge date reaches a result."""


def no_future_observations(task: Task, df: pd.DataFrame, as_of: str | date) -> Verdict:
    """L1-pit: no dated column may post-date the knowledge date."""
    cut = pd.Timestamp(parse_date(as_of))
    problems: list[str] = []
    for spec in task.columns:
        if spec.role not in DATE_ROLES or spec.name not in df.columns:
            continue
        col = pd.to_datetime(df[spec.name], errors="coerce")
        future = col > cut
        n = int(future.sum())
        if n:
            worst = col[future].max()
            problems.append(
                f"column '{spec.name}' (role={spec.role}) has {n} row(s) after the "
                f"knowledge date {cut.date()}, latest {worst.date()} — look-ahead"
            )
    return Verdict(task.name, "L1-pit", not problems, problems)


def describe(as_of: str | date) -> str:
    """One line for the report header, so a reader always sees the vintage."""
    return (
        f"knowledge date {parse_date(as_of)} — every input was filtered to what "
        "had been published on or before this date"
    )
