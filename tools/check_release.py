#!/usr/bin/env python3
"""Fail closed when release identity files disagree."""

from __future__ import annotations

import argparse
import ast
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _package_version() -> str:
    tree = ast.parse((ROOT / "src/quantifact/__init__.py").read_text())
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(t, ast.Name) and t.id == "__version__" for t in node.targets
            )
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            return node.value.value
    raise ValueError("src/quantifact/__init__.py has no literal __version__")


def versions() -> dict[str, str]:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    citation_text = (ROOT / "CITATION.cff").read_text()
    match = re.search(r"^version:\s*[\"']?([^\s\"']+)", citation_text, re.MULTILINE)
    if not match:
        raise ValueError("CITATION.cff has no version")
    return {
        "pyproject": project,
        "package": _package_version(),
        "citation": match.group(1),
    }


def check(tag: str | None = None) -> str:
    found = versions()
    unique = set(found.values())
    if len(unique) != 1:
        raise SystemExit(
            "release versions disagree: "
            + ", ".join(f"{k}={v}" for k, v in found.items())
        )
    version = unique.pop()
    changelog = (ROOT / "CHANGELOG.md").read_text()
    if f"## [{version}]" not in changelog:
        raise SystemExit(f"CHANGELOG.md has no release section for {version}")
    if tag is not None and tag != f"v{version}":
        raise SystemExit(f"tag {tag!r} does not match version v{version}")
    return version


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag")
    parser.add_argument("--print-version", action="store_true")
    args = parser.parse_args()
    version = check(args.tag)
    if args.print_version:
        print(version)
    else:
        print(f"release identity valid: {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
