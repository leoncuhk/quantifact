"""Adapters: one small protocol, many possible data sources."""

from .base import Adapter
from .demo_synthetic import DemoSyntheticAdapter

__all__ = ["Adapter", "DemoSyntheticAdapter"]
