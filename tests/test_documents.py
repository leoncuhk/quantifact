"""Written research is bitemporal too.

A retrieval system that indexes a corpus and searches all of it will happily
tell a 2022 analysis how 2026 turned out. These tests are the reason that cannot
happen here.
"""

from __future__ import annotations

from quantifact.data.documents import Document, DocumentStore

AS_OF_EARLY = "2022-03-01"
AS_OF_LATE = "2026-08-01"


def test_search_cannot_return_a_note_that_had_not_been_written(qf):
    early = qf.adapter.search_documents(
        "oil shock market response", as_of=AS_OF_EARLY, k=10
    )
    assert early, "the corpus should have pre-2022 material"
    assert all(h.document.published_at <= AS_OF_EARLY for h in early)

    late = qf.adapter.search_documents(
        "oil shock market response", as_of=AS_OF_LATE, k=10
    )
    assert any(h.document.published_at > AS_OF_EARLY for h in late), (
        "the later search should surface material the earlier one could not see"
    )


def test_every_hit_says_why_it_qualified(qf):
    hits = qf.adapter.search_documents(
        "chokepoint freight insurance", as_of=AS_OF_LATE, k=3
    )
    assert hits
    for h in hits:
        assert "knowledge date" in h.reasons[0]
        assert h.snippet and h.citation().startswith("DOC-")


def test_confidential_notes_need_the_entitlement(qf):
    q = "book positioning energy complex confidential"
    analyst = qf.adapter.search_documents(q, as_of=AS_OF_LATE, k=5)
    pm = qf.adapter.search_documents(
        q, as_of=AS_OF_LATE, k=5, entitlements=("secure:positions",)
    )
    assert not [h for h in analyst if h.document.entitlement_tags]
    assert [h for h in pm if h.document.entitlement_tags]


def test_a_corpus_round_trips_through_disk(tmp_path):
    docs = [
        Document(
            doc_id="D-1",
            title="t",
            body="oil shock in the strait",
            published_at="2020-01-01",
            source="internal-memo",
        )
    ]
    path = tmp_path / "corpus.jsonl"
    DocumentStore(path, docs)
    again = DocumentStore(path)
    assert len(again) == 1
    assert again.get("D-1").title == "t"
    assert again.search("oil shock", as_of="2021-01-01")
    assert not again.search("oil shock", as_of="2019-01-01")
