"""Overlapping character-window chunking with stable document offsets."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    chunk_id: int
    start: int
    end: int
    text: str
    pass_index: int = 0

    @property
    def size(self) -> int:
        return self.end - self.start


def chunk_text(
    text: str,
    chunk_size: int = 4000,
    overlap: int = 400,
    pass_index: int = 0,
    offset_shift: int = 0,
) -> list[Chunk]:
    """Split `text` into overlapping windows.

    `offset_shift` slides the first window so later passes catch facts that
    sat on a previous chunk boundary.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be >= 0 and < chunk_size")
    if not text:
        return []

    start = max(0, min(offset_shift, len(text) - 1)) if text else 0
    if offset_shift and start == 0 and offset_shift >= len(text):
        return []

    chunks: list[Chunk] = []
    idx = 0
    cursor = start
    n = len(text)
    step = chunk_size - overlap
    while cursor < n:
        end = min(cursor + chunk_size, n)
        chunks.append(
            Chunk(
                chunk_id=idx,
                start=cursor,
                end=end,
                text=text[cursor:end],
                pass_index=pass_index,
            )
        )
        idx += 1
        if end >= n:
            break
        cursor += step
        if cursor >= n:
            break
    return chunks


def pass_shifts(chunk_size: int, passes: int) -> list[int]:
    """Evenly spaced start offsets for multi-pass extraction."""
    if passes <= 1:
        return [0]
    stride = max(1, chunk_size // passes)
    return [i * stride for i in range(passes)]
