"""The flywheel: lessons, benchmarks, and the teach loop that connects them."""

from .benchmarks import Benchmark, BenchmarkResult, BenchmarkSuite
from .lessons import Lesson, LessonRepo
from .teach import KNOWN_EFFECTS, TeachResult, draft_lesson, teach

__all__ = ["Benchmark", "BenchmarkResult", "BenchmarkSuite", "KNOWN_EFFECTS",
           "Lesson", "LessonRepo", "TeachResult", "draft_lesson", "teach"]
