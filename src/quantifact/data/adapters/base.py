"""The adapter protocol — six methods, and they are the whole data contract.

Anything that can answer these six questions can drive quantifact:

``catalog()``      what exists, in enough detail to *choose* without reading data
``read_series()``  a series as it was knowable on a given date
``read_table()``   a reference table (calendar, universe, events) as of that date
``invariants()``   what must be true of this data — shipped *with* the data, so
                   the contract layer can generate its checks instead of
                   guessing
``fingerprint()``  identity of the visible slice, for the value cache

Keeping this surface small is deliberate. A vendor adapter is then a few
hundred lines against a licensed feed, and nothing about the engine changes.
Entitlements, publication lags and licence tags all ride along inside
``SeriesMeta`` rather than living in a second, parallel system.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Any, Protocol, runtime_checkable

import pandas as pd

from ..registry import SeriesMeta


@runtime_checkable
class Adapter(Protocol):
    """What a data source must implement to be usable by quantifact."""

    name: str

    def catalog(self) -> list[SeriesMeta]:
        """Every series this adapter can serve, with metadata rich enough to
        bind against: unit, frequency, coverage, value statistics, licence."""
        ...

    def read_series(self, series_id: str, *, as_of: str | date) -> pd.Series:
        """Observations knowable on ``as_of``, indexed by observation date."""
        ...

    def tables(self) -> list[str]:
        """Names of the reference tables this adapter serves."""
        ...

    def read_table(self, name: str, *, as_of: str | date) -> pd.DataFrame:
        """A reference table as of a knowledge date. Universe tables must be
        survivorship-free: a company delisted after ``as_of`` is still in it."""
        ...

    def invariants(self, series_id: str) -> list[dict[str, Any]]:
        """Assertions that must hold for this series."""
        ...

    def fingerprint(self, series_ids: Iterable[str], *, as_of: str | date) -> str:
        """Stable identity of the visible slice, for cache keys."""
        ...


@runtime_checkable
class DocumentSource(Protocol):
    """Optional: an adapter that also serves written research.

    Separate from ``Adapter`` because plenty of useful sources have numbers and
    no documents, and because a document corpus usually lives behind a different
    system. The knowledge date applies identically — a note that had not been
    written cannot be retrieved.
    """

    def search_documents(
        self,
        query: str,
        *,
        as_of: str | date,
        k: int = 6,
        entitlements: Iterable[str] = (),
    ) -> list[Any]: ...

    def read_document(self, doc_id: str) -> Any: ...
