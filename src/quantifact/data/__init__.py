"""Data: catalog, search, entitlements and the adapter protocol."""

from .adapters.base import Adapter
from .adapters.demo_synthetic import DemoSyntheticAdapter
from .registry import SeriesMeta, SeriesStore
from .search import SearchHit, SeriesSearch

__all__ = ["Adapter", "DemoSyntheticAdapter", "SearchHit", "SeriesMeta",
           "SeriesSearch", "SeriesStore"]
