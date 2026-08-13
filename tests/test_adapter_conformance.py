"""Adapters prove their temporal contract through one public conformance suite."""

from __future__ import annotations

from quantifact import check_adapter


def test_demo_adapter_passes_the_public_conformance_suite(qf):
    report = check_adapter(qf.adapter, early_as_of="2022-03-01", late_as_of="2026-08-01")
    assert report.passed
    assert len(report.checks) >= 8
    assert all(check.evidence for check in report.checks)


def test_conformance_report_is_machine_readable(qf):
    report = check_adapter(
        qf.adapter, early_as_of="2022-03-01", late_as_of="2026-08-01", sample_size=2
    )
    payload = report.to_dict()
    assert payload["schema_version"] == 1
    assert payload["passed"] is True
    assert payload["adapter"] == qf.adapter.name


def test_missing_series_file_is_a_failed_check_not_a_crash(qf, monkeypatch):
    original = qf.adapter.read_series

    def broken(series_id, *, as_of):
        if series_id == qf.adapter.catalog()[0].series_id:
            raise FileNotFoundError("simulated missing parquet")
        return original(series_id, as_of=as_of)

    monkeypatch.setattr(qf.adapter, "read_series", broken)
    report = check_adapter(
        qf.adapter, early_as_of="2022-03-01", late_as_of="2026-08-01", sample_size=1
    )
    check = next(c for c in report.checks if c.id == "sample_series_readable")
    assert not report.passed and not check.passed
    assert "simulated missing parquet" in check.evidence
