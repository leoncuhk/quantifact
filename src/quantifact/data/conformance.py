"""Executable conformance contract for third-party point-in-time adapters."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

import pandas as pd

from ..plan.model import parse_date


@dataclass
class ConformanceCheck:
    id: str
    passed: bool
    evidence: str


@dataclass
class AdapterConformanceReport:
    adapter: str
    checks: list[ConformanceCheck]

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(check.passed for check in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "adapter": self.adapter,
            "passed": self.passed,
            "checks": [asdict(check) for check in self.checks],
        }


def check_adapter(
    adapter: Any,
    *,
    early_as_of: str | date,
    late_as_of: str | date,
    sample_size: int = 8,
) -> AdapterConformanceReport:
    """Probe temporal claims every production adapter must make reproducibly.

    Passing establishes protocol behaviour on sampled catalog entries. It does
    not establish source correctness, licence compliance or full-catalog quality.
    """
    early = parse_date(early_as_of)
    late = parse_date(late_as_of)
    if early >= late:
        raise ValueError("early_as_of must be before late_as_of")
    checks: list[ConformanceCheck] = []

    catalog = adapter.catalog()
    ids = [meta.series_id for meta in catalog]
    checks.append(ConformanceCheck("catalog_nonempty", bool(ids), f"{len(ids)} series"))
    unique = len(ids) == len(set(ids))
    checks.append(
        ConformanceCheck(
            "catalog_ids_unique",
            unique,
            "all identifiers unique" if unique else "duplicate series identifiers",
        )
    )
    required = ("frequency", "unit", "source", "license_tag")
    complete = all(
        all(getattr(meta, field, None) for field in required) for meta in catalog
    )
    checks.append(
        ConformanceCheck(
            "catalog_semantics_complete",
            complete,
            f"required fields: {', '.join(required)}",
        )
    )

    sampled = ids[:sample_size]
    no_future = True
    monotone = True
    deterministic = True
    read_errors: list[str] = []
    for sid in sampled:
        try:
            early_values = adapter.read_series(sid, as_of=early)
            late_values = adapter.read_series(sid, as_of=late)
        except Exception as exc:
            read_errors.append(f"{sid}: {type(exc).__name__}: {exc}")
            no_future = monotone = deterministic = False
            continue
        for values, cut in ((early_values, early), (late_values, late)):
            if not isinstance(values, pd.Series):
                no_future = False
                continue
            if len(values) and pd.Timestamp(values.index.max()) > pd.Timestamp(cut):
                no_future = False
        if not set(early_values.index).issubset(set(late_values.index)):
            monotone = False
        a = adapter.fingerprint([sid], as_of=early)
        b = adapter.fingerprint([sid], as_of=early)
        if not a or a != b:
            deterministic = False
    checks += [
        ConformanceCheck(
            "sample_series_readable",
            not read_errors,
            (
                f"sampled {len(sampled)} series"
                if not read_errors
                else "; ".join(read_errors[:3])
            ),
        ),
        ConformanceCheck(
            "no_future_observation_dates",
            no_future,
            f"sampled {len(sampled)} series at two vintages",
        ),
        ConformanceCheck(
            "vintage_visibility_monotone",
            monotone,
            "early observation keys are a subset of later keys",
        ),
        ConformanceCheck(
            "fingerprint_deterministic",
            deterministic,
            f"repeated fingerprints agree for {len(sampled)} series",
        ),
    ]

    table_names = adapter.tables()
    tables_ok = True
    for name in table_names:
        frame = adapter.read_table(name, as_of=early)
        tables_ok = tables_ok and isinstance(frame, pd.DataFrame)
        date_columns = [
            column
            for column in frame.columns
            if pd.api.types.is_datetime64_any_dtype(frame[column])
        ]
        for column in date_columns:
            if len(frame) and pd.Timestamp(frame[column].max()) > pd.Timestamp(early):
                tables_ok = False
    checks.append(
        ConformanceCheck(
            "reference_tables_point_in_time",
            tables_ok,
            f"checked {len(table_names)} reference tables",
        )
    )
    return AdapterConformanceReport(
        getattr(adapter, "name", type(adapter).__name__), checks
    )
