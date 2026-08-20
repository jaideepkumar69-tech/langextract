"""Post-extraction grounding: exact quotes and character offsets, or block."""

from __future__ import annotations

import re
import unicodedata

from pipeline.models import ExtractionItem, LLMExtraction


_WS = re.compile(r"\s+")


def normalize_ws(text: str) -> str:
    return _WS.sub(" ", text).strip()


def _is_subsequence_span(source: str, quote: str) -> tuple[int, int] | None:
    """Find `quote` in `source` allowing only whitespace differences."""
    if not quote or not source:
        return None
    q = normalize_ws(quote)
    if not q:
        return None
    # Fast exact path
    pos = source.find(quote)
    if pos >= 0:
        return pos, pos + len(quote)
    pos = source.find(q)
    if pos >= 0:
        return pos, pos + len(q)

    # Walk source, skip extra whitespace in both strings
    q_idx = 0
    start = None
    i = 0
    n, m = len(source), len(q)
    while i < n and q_idx < m:
        if source[i] == q[q_idx]:
            if start is None:
                start = i
            q_idx += 1
            i += 1
            continue
        if source[i].isspace() and (q_idx == 0 or q[q_idx - 1].isspace() or q[q_idx].isspace()):
            i += 1
            continue
        if q[q_idx].isspace():
            q_idx += 1
            continue
        # mismatch — restart after start+1
        if start is None:
            i += 1
        else:
            i = start + 1
            start = None
            q_idx = 0
    if q_idx == m and start is not None:
        end = i
        # trim trailing whitespace from the matched span
        while end > start and source[end - 1].isspace():
            end -= 1
        return start, end
    return None


def find_span(source: str, quote: str) -> tuple[int, int] | None:
    """Locate an exact or whitespace-normalized quote in the source."""
    if not quote:
        return None
    pos = source.find(quote)
    if pos >= 0:
        return pos, pos + len(quote)
    # Unique case-insensitive exact match
    lower_src = source.lower()
    lower_q = quote.lower()
    first = lower_src.find(lower_q)
    if first >= 0 and lower_src.find(lower_q, first + 1) < 0:
        return first, first + len(quote)
    return _is_subsequence_span(source, quote)


def offsets_match(source: str, start: int | None, end: int | None, quote: str) -> bool:
    if start is None or end is None:
        return False
    if start < 0 or end > len(source) or end <= start:
        return False
    slice_ = source[start:end]
    if slice_ == quote:
        return True
    return normalize_ws(slice_) == normalize_ws(quote)


def looks_like_paraphrase(source: str, quote: str) -> bool:
    """True when the quote is not a source substring even after light normalize."""
    if not quote or not quote.strip():
        return True
    if find_span(source, quote) is not None:
        return False
    # Token overlap: if fewer than half the content words appear, it's invented.
    words = [w for w in re.findall(r"[A-Za-z0-9$%.,]+", quote.lower()) if len(w) > 2]
    if not words:
        return True
    src_l = source.lower()
    hits = sum(1 for w in words if w in src_l)
    return hits < max(1, len(words) // 2)


def validate_extraction(
    source: str,
    raw: LLMExtraction,
    *,
    chunk_start: int = 0,
    pass_index: int = 0,
    chunk_id: int = 0,
    latency_ms: float = 0.0,
) -> ExtractionItem:
    """Verify quote + offsets against the full source document.

    - grounded: model offsets already match the source exactly
    - remapped: quote found in source, offsets corrected
    - blocked: paraphrase, empty, or not found — do not export as fact
    """
    item = ExtractionItem(
        query=raw.query,
        value=(raw.value or "").strip(),
        quote=(raw.quote or "").strip(),
        start=raw.start,
        end=raw.end,
        confidence=max(0.0, min(1.0, raw.confidence)),
        pass_index=pass_index,
        chunk_id=chunk_id,
        latency_ms=latency_ms,
        status="blocked",
    )
    if not item.quote:
        item.reason = "empty quote"
        item.confidence = 0.0
        return item

    # Model offsets are often chunk-relative.
    candidates: list[tuple[int, int]] = []
    if raw.start is not None and raw.end is not None:
        candidates.append((raw.start, raw.end))
        candidates.append((raw.start + chunk_start, raw.end + chunk_start))

    for start, end in candidates:
        if offsets_match(source, start, end, item.quote):
            item.start, item.end = start, end
            item.quote = source[start:end]
            item.status = "grounded"
            item.reason = "exact offset match"
            if not item.value:
                item.value = item.quote
            return item

    found = find_span(source, item.quote)
    if found:
        start, end = found
        item.start, item.end = start, end
        item.quote = source[start:end]
        item.status = "remapped"
        item.reason = "quote located; offsets corrected"
        if item.confidence > 0:
            item.confidence = min(item.confidence, 0.85)
        if not item.value:
            item.value = item.quote
        return item

    if looks_like_paraphrase(source, item.quote):
        item.reason = "blocked: paraphrase or hallucinated quote not in source"
    else:
        item.reason = "blocked: quote tokens appear but no contiguous span"
    item.start = None
    item.end = None
    item.confidence = 0.0
    item.status = "blocked"
    return item


def fold_for_compare(text: str) -> str:
    return unicodedata.normalize("NFKC", normalize_ws(text)).lower()


def dedupe_items(items: list[ExtractionItem]) -> list[ExtractionItem]:
    """Keep the best item per (query, normalized quote/span)."""
    ranked = sorted(
        items,
        key=lambda it: (
            0 if it.status == "grounded" else 1 if it.status == "remapped" else 2,
            -it.confidence,
            it.latency_ms,
        ),
    )
    seen: set[tuple[str, str, int | None, int | None]] = set()
    out: list[ExtractionItem] = []
    for item in ranked:
        key = (fold_for_compare(item.query), fold_for_compare(item.quote), item.start, item.end)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out
