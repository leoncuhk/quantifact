"""The compiler front end: what generated code is allowed to be.

Three questions are answered before any code runs:

* is it allowed to run at all — forbidden APIs, IO, randomness, the clock, and
  any attempt to pass its own ``as_of`` to a loader (which would side-step the
  look-ahead defence);
* what does it actually depend on — parameters and literal series ids, which
  are cross-checked against what the plan declared;
* what is its cache identity — a digest of the normalised AST, so comments and
  formatting do not invalidate a cached value but logic does.
"""

from __future__ import annotations

import ast
import hashlib
from dataclasses import dataclass, field

FORBIDDEN_CALLS = {
    "open",
    "eval",
    "exec",
    "compile",
    "input",
    "__import__",
    "read_csv",
    "read_parquet",
    "to_csv",
    "to_parquet",
    "to_pickle",
    "system",
    "popen",
    "run",
    "check_output",
    "urlopen",
    "get",
    "post",
}
FORBIDDEN_MODULES = {
    "os",
    "sys",
    "subprocess",
    "socket",
    "requests",
    "urllib",
    "pathlib",
    "random",
    "secrets",
    "shutil",
    "pickle",
    "time",
    "datetime",
}
ALLOWED_MODULES = {"pandas", "numpy", "math"}
NONDETERMINISTIC = {"now", "today", "rand", "randn", "random", "sample", "shuffle"}
LOADERS = {"load_series", "load_table"}


@dataclass
class CodeFacts:
    task: str
    func_name: str
    params: list[str]
    series_ids: list[str] = field(default_factory=list)
    tables: list[str] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)
    ast_digest: str = ""


def _norm_source(tree: ast.AST) -> str:
    """Docstring-stripped, re-unparsed source: stable under comments/spacing."""
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module, ast.ClassDef)
        ):
            body = getattr(node, "body", [])
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                node.body = body[1:] or [ast.Pass()]
    return ast.unparse(ast.fix_missing_locations(tree))


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def analyse(task_name: str, source: str) -> CodeFacts:
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return CodeFacts(
            task=task_name, func_name="", params=[], violations=[f"syntax error: {e}"]
        )

    facts = CodeFacts(task=task_name, func_name="", params=[])
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    if len(funcs) != 1:
        facts.violations.append(
            f"expected exactly one top-level function, found {len(funcs)}"
        )
        if not funcs:
            return facts
    fn = funcs[0]
    facts.func_name = fn.name
    facts.params = [a.arg for a in fn.args.args]
    if fn.name != task_name:
        facts.violations.append(
            f"function name '{fn.name}' does not match task name '{task_name}'"
        )

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] not in ALLOWED_MODULES:
                    facts.violations.append(f"import of '{a.name}' is not allowed")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root not in ALLOWED_MODULES:
                facts.violations.append(f"import from '{node.module}' is not allowed")
            if root in FORBIDDEN_MODULES:
                facts.violations.append(f"forbidden module '{root}'")
        elif isinstance(node, ast.Call):
            fname = _call_name(node.func)
            if fname in FORBIDDEN_CALLS:
                facts.violations.append(f"forbidden call: {fname}()")
            if fname in NONDETERMINISTIC:
                facts.violations.append(f"nondeterministic call: {fname}()")
            if fname in LOADERS:
                sink = facts.series_ids if fname == "load_series" else facts.tables
                if node.keywords:
                    # The knowledge date is bound by the harness. Code that tries
                    # to choose its own would be choosing what it may know.
                    facts.violations.append(
                        f"{fname}() takes no keyword arguments; the knowledge date "
                        "is fixed by the plan and bound by the harness"
                    )
                if node.args and isinstance(node.args[0], ast.Constant):
                    sink.append(str(node.args[0].value))
                elif not any(isinstance(a, ast.Name) for a in node.args):
                    facts.violations.append(
                        f"{fname}() must be called with a literal identifier"
                    )
            for kw in node.keywords:
                if kw.arg == "inplace" and getattr(kw.value, "value", False) is True:
                    facts.violations.append("inplace=True is not allowed")

    if not any(isinstance(n, ast.Return) for n in ast.walk(fn)):
        facts.violations.append("function never returns a dataframe")

    facts.ast_digest = hashlib.sha256(_norm_source(tree).encode()).hexdigest()[:16]
    return facts
