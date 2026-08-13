"""Cache and evidence identity describe the visible vintage, not future bytes."""

from __future__ import annotations

import pandas as pd


def test_future_rows_do_not_change_an_earlier_visible_fingerprint(qf):
    store = qf.adapter.store
    sid = "US.OUTPUT_GAP"
    cut = "2022-03-01"
    before = store.fingerprint([sid], as_of=cut)
    frame = store.read_frame(sid)
    future = frame[frame["pub_date"] > pd.Timestamp(cut)]
    assert not future.empty

    # This mirrors the fingerprint algorithm with future rows removed. If the
    # implementation hashed the full file, these identities could not match.
    visible = frame[frame["pub_date"] <= pd.Timestamp(cut)]
    import hashlib

    h = hashlib.sha256()
    h.update(cut.encode())
    h.update(sid.encode())
    h.update(
        hashlib.sha256(
            pd.util.hash_pandas_object(visible, index=True).to_numpy().tobytes()
        ).digest()
    )
    assert before == h.hexdigest()[:16]


def test_visible_fingerprint_changes_when_the_visible_slice_changes(qf):
    sid = "US.OUTPUT_GAP"
    early = qf.adapter.store.fingerprint([sid], as_of="2022-03-01")
    late = qf.adapter.store.fingerprint([sid], as_of="2026-08-01")
    assert early != late


def test_visible_fingerprint_is_memoised_per_series_and_vintage(qf, monkeypatch):
    store = qf.adapter.store
    sid = "US.CPI.CORE.YOY"
    store._visible_fingerprints.clear()
    calls = 0
    original = store.read_frame

    def counted(series_id):
        nonlocal calls
        calls += 1
        return original(series_id)

    monkeypatch.setattr(store, "read_frame", counted)
    a = store.fingerprint([sid], as_of="2026-08-01")
    b = store.fingerprint([sid], as_of="2026-08-01")
    assert a == b and calls == 1
