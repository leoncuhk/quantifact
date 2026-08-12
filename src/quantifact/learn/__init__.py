"""The flywheel: lessons, benchmarks, and the teach loop that connects them."""

from .benchmarks import Benchmark, BenchmarkResult, BenchmarkSuite
from .lessons import Lesson, LessonRepo
from .teach import KNOWN_EFFECTS, TeachResult, draft_lesson, teach

__all__ = [
    "KNOWN_EFFECTS",
    "Benchmark",
    "BenchmarkResult",
    "BenchmarkSuite",
    "Lesson",
    "LessonRepo",
    "TeachResult",
    "draft_lesson",
    "teach",
]
