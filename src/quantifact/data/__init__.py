"""Data: catalog, search, entitlements and the adapter protocol."""

from .adapters.base import Adapter, DocumentSource
from .adapters.demo_synthetic import DemoSyntheticAdapter
from .documents import Document, DocumentHit, DocumentStore
from .registry import SeriesMeta, SeriesStore
from .search import SearchHit, SeriesSearch

__all__ = [
    "Adapter",
    "DemoSyntheticAdapter",
    "Document",
    "DocumentHit",
    "DocumentSource",
    "DocumentStore",
    "SearchHit",
    "SeriesMeta",
    "SeriesSearch",
    "SeriesStore",
]
