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
from .data.conformance import AdapterConformanceReport, check_adapter
from .data.registry import SeriesMeta, SeriesStore
from .data.search import SeriesSearch
from .evidence import ResearchEvidencePackage
from .harness.cache import ValueCache
from .harness.execute import ExecutionHarness, ProcessExecutionHarness
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
from .planner import RulePlanner, UnsupportedQuestionError

__all__ = [
    "ANALYST",
    "AlternativeExplanation",
    "PM",
    "Adapter",
    "AdapterConformanceReport",
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
    "ProcessExecutionHarness",
    "Quantifact",
    "ReferenceCodegen",
    "ResearchEvidencePackage",
    "ResearchClaim",
    "ResearchDesign",
    "RulePlanner",
    "SeriesMeta",
    "SeriesSearch",
    "SeriesStore",
    "Task",
    "TaskUnfixable",
    "User",
    "UnsupportedQuestionError",
    "ValueCache",
    "Verdict",
    "generate_all",
    "check_adapter",
    "teach",
]
__version__ = "0.3.0a1"
