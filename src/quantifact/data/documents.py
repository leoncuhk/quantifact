"""Unstructured research: memos, broker notes, transcripts — and their dates.

A research desk does not start from a series. It starts from what was written:
what happened, what people thought was happening, and when they thought it. So
documents get the same treatment as numbers here — a publication date, an
entitlement tag, a licence tag — and the same rule: a search taken as of a
knowledge date cannot return a note that had not been written yet.

That rule is easy to state and almost universally broken. Retrieval systems
index a corpus and search all of it; a corpus of research notes searched without
a knowledge date will happily tell a 2022 analysis how the 2026 crisis turned
out, and nothing in the output will look wrong.

What this module is *not*: a production retrieval stack. Recall is BM25 over
title and body, deliberately, because the interesting part is the metadata
contract around it, not the ranker. Swap in embeddings behind the same protocol
if you have them.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from ..plan.model import parse_date

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


@dataclass
class Document:
    doc_id: str
    title: str
    body: str
    published_at: str  # when it became knowable
    source: str  # broker | internal-memo | transcript | news
    author: str = "unknown"
    tags: list[str] = field(default_factory=list)
    entitlement_tags: list[str] = field(default_factory=list)
    license_tag: str = "unspecified"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict[str, Any]) -> Document:
        return Document(**d)

    def card(self, width: int = 240) -> str:
        """What a planner reads before deciding to open it."""
        body = " ".join(self.body.split())
        if len(body) > width:
            body = body[:width].rsplit(" ", 1)[0] + "…"
        return (
            f"[{self.doc_id}] {self.title}\n"
            f"  {self.published_at} · {self.source} · {self.author}\n"
            f"  {body}"
        )


@dataclass
class DocumentHit:
    document: Document
    score: float
    snippet: str
    reasons: list[str] = field(default_factory=list)

    def citation(self) -> str:
        return f"{self.document.doc_id} ({self.document.published_at}): {self.document.title}"


class DocumentStore:
    """JSONL-backed corpus with point-in-time search."""

    def __init__(self, path: str | Path, documents: Iterable[Document] | None = None):
        self.path = Path(path)
        if documents is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                "\n".join(json.dumps(d.to_dict(), ensure_ascii=False) for d in documents)
            )
        self._docs = [
            Document.from_dict(json.loads(line))
            for line in self.path.read_text().splitlines()
            if line.strip()
        ]
        self._index = {d.doc_id: d for d in self._docs}
        self._toks = {
            d.doc_id: _tokens(f"{d.title} {d.body} {' '.join(d.tags)}")
            for d in self._docs
        }
        self._df: dict[str, int] = {}
        for toks in self._toks.values():
            for t in set(toks):
                self._df[t] = self._df.get(t, 0) + 1
        self._n = max(1, len(self._docs))
        self._avglen = sum(len(t) for t in self._toks.values()) / self._n

    # ------------------------------------------------------------------ api
    def __len__(self) -> int:
        return len(self._docs)

    def all(self) -> list[Document]:
        return list(self._docs)

    def get(self, doc_id: str) -> Document:
        return self._index[doc_id]

    def visible(
        self, doc: Document, as_of: str | date, entitlements: Iterable[str] = ()
    ) -> bool:
        if parse_date(doc.published_at) > parse_date(as_of):
            return False
        return all(tag in set(entitlements) for tag in doc.entitlement_tags)

    def _bm25(self, query: str, doc_id: str, k1: float = 1.4, b: float = 0.75) -> float:
        toks = self._toks[doc_id]
        if not toks:
            return 0.0
        score = 0.0
        for q in set(_tokens(query)):
            f = toks.count(q)
            if not f:
                continue
            df = self._df.get(q, 0)
            idf = math.log(1 + (self._n - df + 0.5) / (df + 0.5))
            score += (
                idf * (f * (k1 + 1)) / (f + k1 * (1 - b + b * len(toks) / self._avglen))
            )
        return score

    def _snippet(self, doc: Document, query: str, width: int = 220) -> str:
        body = " ".join(doc.body.split())
        terms = [t for t in _tokens(query) if len(t) > 3]
        low = body.lower()
        pos = next((low.find(t) for t in terms if low.find(t) >= 0), 0)
        start = max(0, pos - width // 3)
        out = body[start : start + width]
        return ("…" if start else "") + out + ("…" if start + width < len(body) else "")

    def search(
        self,
        query: str,
        *,
        as_of: str | date,
        k: int = 6,
        entitlements: Iterable[str] = (),
        sources: Iterable[str] | None = None,
    ) -> list[DocumentHit]:
        """Rank what was already written, and say why each hit qualified."""
        wanted = set(sources) if sources else None
        hits: list[DocumentHit] = []
        for doc in self._docs:
            if not self.visible(doc, as_of, entitlements):
                continue
            if wanted and doc.source not in wanted:
                continue
            score = self._bm25(query, doc.doc_id)
            if score <= 0:
                continue
            hits.append(
                DocumentHit(
                    document=doc,
                    score=score,
                    snippet=self._snippet(doc, query),
                    reasons=[
                        f"published {doc.published_at}, on or before the knowledge "
                        f"date {parse_date(as_of)}",
                        f"source={doc.source}",
                    ],
                )
            )
        hits.sort(key=lambda h: (-h.score, h.document.published_at))
        return hits[:k]
