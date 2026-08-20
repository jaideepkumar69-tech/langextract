"""Offline smoke checks for the grounded extraction pipeline (no Ollama required)."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from pipeline.chunking import chunk_text
from pipeline.llm import invoke_mock
from pipeline.models import LLMExtraction
from pipeline.validator import validate_extraction


SAMPLE = PROJECT / "pipeline" / "samples" / "nvidia_q4_fy2025.txt"


def main() -> int:
    assert SAMPLE.is_file(), SAMPLE
    source = SAMPLE.read_text(encoding="utf-8").replace("\r\n", "\n")
    chunks = chunk_text(source, chunk_size=400, overlap=40)
    assert chunks and chunks[0].text == source[chunks[0].start : chunks[0].end]

    items = invoke_mock(source, "total revenue")
    assert items and "39.3" in items[0].quote, items

    grounded = validate_extraction(source, items[0])
    assert grounded.status in {"grounded", "remapped"}, grounded
    assert source[grounded.start : grounded.end] == grounded.quote

    fake = validate_extraction(
        source,
        LLMExtraction(query="total revenue", value="nope", quote="made-up trillion dollar profit"),
    )
    assert fake.status == "blocked", fake

    from pipeline.main import run

    with tempfile.TemporaryDirectory() as tmp:
        summary = run(
            [
                "--input",
                str(SAMPLE),
                "--provider",
                "mock",
                "--passes",
                "2",
                "--out",
                tmp,
                "--sequential-queries",
            ]
        )
        assert summary["ok"] and summary["grounded"] >= 5, summary
        ann = Path(tmp) / "annotations.json"
        data = json.loads(ann.read_text(encoding="utf-8"))
        assert data["extractions"]

    print("smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
