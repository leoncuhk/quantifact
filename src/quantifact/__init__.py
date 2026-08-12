"""quantifact — an investment-research agent that has to prove its numbers.

A question is clarified into a plan; the plan is an intermediate representation
with real schemas, units, row grain and a knowledge date; each task compiles in
parallel into one pandas function; static analysis derives the dependency graph;
layered contracts run as ordinary Python that no model can skip; and a caching
harness executes the code on the model's behalf, bound to the knowledge date so
look-ahead is structurally impossible rather than discouraged.

    from quantifact import Quantifact
    qf = Quantifact(".qf")
    art = qf.analyse("How did markets respond to the oil supply shock?",
                     out="report.html")
"""

from .agent import ANALYST, PM, Artifacts, Quantifact, User
from .codegen.base import CodegenBackend, generate_all
from .codegen.reference import ReferenceCodegen
from .contracts.verdict import TaskUnfixable, Verdict
from .data.adapters.base import Adapter
from .data.adapters.demo_synthetic import DemoSyntheticAdapter
from .data.registry import SeriesMeta, SeriesStore
from .data.search import SeriesSearch
from .harness.cache import ValueCache
from .harness.execute import ExecutionHarness
from .learn.benchmarks import Benchmark, BenchmarkSuite
from .learn.lessons import Lesson, LessonRepo
from .learn.teach import teach
from .plan.compile import PlanCompiler
from .plan.model import (
    AlternativeExplanation,
    AnalysisPlan,
    ColumnSpec,
    PlanError,
    ResearchClaim,
    ResearchDesign,
    Task,
)
from .planner import RulePlanner

__all__ = [
    "ANALYST",
    "AlternativeExplanation",
    "PM",
    "Adapter",
    "AnalysisPlan",
    "Artifacts",
    "Benchmark",
    "BenchmarkSuite",
    "CodegenBackend",
    "ColumnSpec",
    "DemoSyntheticAdapter",
    "ExecutionHarness",
    "Lesson",
    "LessonRepo",
    "PlanCompiler",
    "PlanError",
    "Quantifact",
    "ReferenceCodegen",
    "ResearchClaim",
    "ResearchDesign",
    "RulePlanner",
    "SeriesMeta",
    "SeriesSearch",
    "SeriesStore",
    "Task",
    "TaskUnfixable",
    "User",
    "ValueCache",
    "Verdict",
    "generate_all",
    "teach",
]
__version__ = "0.2.0"
