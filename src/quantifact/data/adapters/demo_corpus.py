"""A synthetic research corpus, dated the way real research is dated.

Four kinds of writing a desk actually has — broker notes, internal memos,
earnings-call transcripts and news — around the episodes in the demo universe.
Every document has a publication date, and roughly a fifth of them are
deliberately written *after* the 2026 escalation, so a search taken as of an
earlier date has something real to exclude.

None of this is journalism or research. It is scaffolding shaped like research
so the retrieval contract can be exercised offline.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from ..documents import Document, DocumentStore

EPISODE_NOTES = [
    (
        "gulf_war_1990",
        "1990-08-02",
        "1990 Gulf War",
        "Brent doubled within three "
        "months of the invasion; equities fell about twenty per cent before "
        "recovering, and the dollar rallied as a haven.",
    ),
    (
        "russia_ukraine_2022",
        "2022-02-24",
        "2022 Russia-Ukraine",
        "Energy led, "
        "European equities lagged, and the correlation between commodities and "
        "equities inverted for two quarters.",
    ),
    (
        "israel_iran_2025",
        "2025-06-13",
        "2025 Israel-Iran",
        "A short, sharp move: "
        "crude spiked, then retraced most of it inside a month as the supply "
        "disruption proved narrower than feared.",
    ),
    (
        "iran_hormuz_2026",
        "2026-06-15",
        "2026 Iran/Hormuz",
        "Freight and insurance "
        "costs moved before crude did, which is the tell that the market is pricing "
        "a chokepoint rather than a production loss.",
    ),
]

THEMES = [
    (
        "channel",
        "Oil shocks reach equities through the growth channel, bonds "
        "through flight to safety, and commodities through substitution — pooling "
        "them into one cross-market number hides more than it reveals.",
    ),
    (
        "macro",
        "What matters going in is the macro starting point: the output gap, "
        "the real yield, and whether the economy is a net energy importer.",
    ),
    (
        "positioning",
        "Positioning going into a chokepoint event tends to be shorter "
        "than positioning going into a production event, which changes the shape of "
        "the first week.",
    ),
    (
        "inflation",
        "Headline inflation responds within two months; core takes three "
        "quarters and only if wages follow.",
    ),
    (
        "methodology",
        "Measure the response over a window fixed in advance. Choosing "
        "the window after seeing the path is how research talks itself into a "
        "conclusion.",
    ),
]

BROKERS = ["Northbank Research", "Kestrel Macro", "Pemberton & Co", "Aldgate Global"]
DESKS = ["macro desk", "commodities desk", "rates desk", "cross-asset desk"]


def build_documents(seed: int = 42) -> list[Document]:
    rng = np.random.default_rng(seed)
    docs: list[Document] = []
    n = 0

    for episode, start, label, summary in EPISODE_NOTES:
        for offset, source in (
            (-21, "broker"),
            (2, "news"),
            (9, "internal-memo"),
            (35, "broker"),
            (70, "internal-memo"),
        ):
            n += 1
            published = str(np.datetime64(start, "D") + np.timedelta64(offset, "D"))
            theme_key, theme = THEMES[n % len(THEMES)]
            broker = BROKERS[n % len(BROKERS)]
            desk = DESKS[n % len(DESKS)]
            if source == "broker":
                title = f"{label}: what the tape is telling us"
                author = broker
                body = (
                    f"{summary} {theme} Our read into the {label.lower()} "
                    "episode is that the first week is dominated by hedging "
                    "flow rather than by any revision to demand."
                )
                lic = "third-party-research"
            elif source == "internal-memo":
                title = f"{label} — {desk} note"
                author = f"{desk} ({'internal' if n % 2 else 'shared'})"
                body = (
                    f"Internal read on {label}. {theme} We should measure this "
                    "against the earlier episodes on a fixed window and refuse "
                    "to move the window afterwards."
                )
                lic = "internal"
            else:
                title = f"{label}: markets react"
                author = "wire"
                body = (
                    f"{summary} Traders cited {theme_key} as the reason for the "
                    "move, though attribution on day two is mostly narrative."
                )
                lic = "public"
            docs.append(
                Document(
                    doc_id=f"DOC-{n:03d}",
                    title=title,
                    body=body,
                    published_at=published,
                    source=source,
                    author=author,
                    tags=[episode, theme_key, "oil-shock"],
                    license_tag=lic,
                )
            )

    # standing methodology pieces, undated relative to any episode
    for i, (theme_key, theme) in enumerate(THEMES, start=1):
        n += 1
        docs.append(
            Document(
                doc_id=f"DOC-{n:03d}",
                title=f"House methodology: {theme_key} in event studies",
                body=(
                    f"{theme} Applies to every episode comparison we publish; the "
                    "window, the universe and the alignment rule are decided before "
                    "the data is pulled."
                ),
                published_at=f"20{10 + i}-03-15",
                source="internal-memo",
                author="research standards",
                tags=[theme_key, "methodology"],
                license_tag="internal",
            )
        )

    # a few entitlement-gated notes, so the filter has something to hide
    for i in range(3):
        n += 1
        docs.append(
            Document(
                doc_id=f"DOC-{n:03d}",
                title="Book positioning into the energy complex",
                body=(
                    "Aggregate positioning across the energy complex and the hedges "
                    "against it. Firm confidential."
                ),
                published_at=f"2026-0{4 + i}-01",
                source="internal-memo",
                author="portfolio construction",
                tags=["positioning", "confidential"],
                entitlement_tags=["secure:positions"],
                license_tag="internal-confidential",
            )
        )

    # transcripts, which is where the words are freshest and the numbers worst
    for i in range(6):
        n += 1
        year = 2022 + i % 5
        docs.append(
            Document(
                doc_id=f"DOC-{n:03d}",
                title=f"Energy major Q{1 + i % 4} {year} earnings call — excerpt",
                body=(
                    "Management noted freight and insurance costs ahead of crude, "
                    "flagged chokepoint risk as the swing factor for the quarter, and "
                    "declined to guide on realisations."
                ),
                published_at=f"{year}-0{2 + i % 6}-1{i % 9}",
                source="transcript",
                author="investor relations",
                tags=["energy", "chokepoint"],
                license_tag="public",
            )
        )

    rng.shuffle(docs)
    return sorted(docs, key=lambda d: d.doc_id)


def ensure_corpus(root: str | Path, seed: int = 42) -> DocumentStore:
    path = Path(root) / "documents.jsonl"
    if path.exists():
        return DocumentStore(path)
    return DocumentStore(path, build_documents(seed))
