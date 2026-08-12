"""Search: recall, then inspection.

Recall finds candidates by text. Inspection decides, the way a researcher does:
is the frequency right, the unit right, the currency right, does it cover every
window the analysis needs, and — the check that matters most — do the values
look like the concept being asked for. A series called "US headline CPI" whose
values run 120..480 is not an inflation rate, whatever its name says.

Every accept and reject writes a reason into the trace. That is what makes an
analysis auditable by a human or by a background agent later.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from .registry import SeriesMeta, SeriesStore

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


@dataclass
class SearchHit:
    meta: SeriesMeta
    recall_score: float
    accepted: bool = True
    reasons: list[str] = field(default_factory=list)


class SeriesSearch:
    """BM25-lite recall over the catalog, then an explicit inspection pass."""

    def __init__(self, store: SeriesStore, entitlements: Iterable[str] = ()):
        self.store = store
        self.entitlements = set(entitlements)
        self._docs: dict[str, list[str]] = {}
        self._df: dict[str, int] = {}
        for m in store.all_meta():
            toks = _tokens(
                " ".join(
                    filter(
                        None,
                        [
                            m.series_id.replace(".", " "),
                            m.name,
                            m.description,
                            " ".join(m.aliases),
                            m.geography or "",
                            m.asset_class or "",
                            m.unit,
                            m.currency or "",
                        ],
                    )
                )
            )
            self._docs[m.series_id] = toks
            for t in set(toks):
                self._df[t] = self._df.get(t, 0) + 1
        self._n = max(1, len(self._docs))
        self._avglen = sum(len(d) for d in self._docs.values()) / self._n

    # ------------------------------------------------------------- recall
    def _bm25(self, query: str, sid: str, k1: float = 1.4, b: float = 0.75) -> float:
        doc = self._docs[sid]
        if not doc:
            return 0.0
        score = 0.0
        for q in set(_tokens(query)):
            f = doc.count(q)
            if not f:
                continue
            df = self._df.get(q, 0)
            idf = math.log(1 + (self._n - df + 0.5) / (df + 0.5))
            score += (
                idf * (f * (k1 + 1)) / (f + k1 * (1 - b + b * len(doc) / self._avglen))
            )
        return score

    def visible(self, m: SeriesMeta) -> bool:
        """Entitlement filter at the index level, not in a prompt.

        What a user may not see is never recalled, so there is nothing for a
        clever prompt to talk its way into.
        """
        return all(tag in self.entitlements for tag in m.entitlement_tags)

    def recall(self, query: str, k: int = 12) -> list[SearchHit]:
        hits = [
            SearchHit(meta=m, recall_score=self._bm25(query, m.series_id))
            for m in self.store.all_meta()
            if self.visible(m)
        ]
        hits = [h for h in hits if h.recall_score > 0]
        hits.sort(key=lambda h: (-h.recall_score, h.meta.series_id))
        return hits[:k]

    # --------------------------------------------------------- inspection
    def inspect(
        self,
        hits: list[SearchHit],
        *,
        frequency: str | None = None,
        unit: str | None = None,
        currency: str | None = None,
        covers: tuple[str, str] | None = None,
        prior: tuple[float, float] | None = None,
    ) -> list[SearchHit]:
        for h in hits:
            m = h.meta
            if frequency and m.frequency != frequency:
                h.accepted = False
                h.reasons.append(f"frequency {m.frequency} != required {frequency}")
            if unit and m.unit != unit:
                h.accepted = False
                h.reasons.append(f"unit '{m.unit}' != required '{unit}'")
            if currency and (m.currency or "") != currency:
                h.accepted = False
                h.reasons.append(f"currency '{m.currency}' != required '{currency}'")
            if covers and m.first_obs and m.last_obs:
                lo, hi = covers
                if not (m.first_obs <= lo and m.last_obs >= hi):
                    h.accepted = False
                    h.reasons.append(
                        f"coverage {m.first_obs}..{m.last_obs} does not span {lo}..{hi}"
                    )
            if prior and m.value_stats:
                lo, hi = prior
                mn, mx = m.value_stats.get("min"), m.value_stats.get("max")
                if mn is not None and (mn < lo or mx > hi):
                    h.accepted = False
                    h.reasons.append(
                        f"values [{mn:.4g}, {mx:.4g}] outside prior [{lo:g}, {hi:g}] "
                        "— likely a level or a different scale, not this concept"
                    )
            if h.accepted:
                h.reasons.append(
                    "frequency, unit, coverage and value range match the requirement"
                )
        return hits

    def search(self, query: str, k: int = 12, **inspection: Any) -> list[SearchHit]:
        return self.inspect(self.recall(query, k), **inspection)
