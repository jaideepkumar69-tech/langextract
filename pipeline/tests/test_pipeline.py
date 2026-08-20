"""Offline tests for chunking, grounding, mock extraction, and report export."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.chunking import chunk_text, pass_shifts
from pipeline.extractor import extract_document, extract_query
from pipeline.llm import default_model_for, invoke_mock, resolve_provider
from pipeline.loaders import load_document, write_sample_pdf
from pipeline.main import run as run_pipeline
from pipeline.models import LLMExtraction
from pipeline.validator import find_span, validate_extraction


SAMPLE = ROOT / "pipeline" / "samples" / "nvidia_q4_fy2025.txt"


def test_chunk_overlap_and_offsets():
    text = "ABCDEFGHIJ" * 20  # 200 chars
    chunks = chunk_text(text, chunk_size=50, overlap=10)
    assert chunks
    assert chunks[0].start == 0
    assert chunks[0].text == text[chunks[0].start : chunks[0].end]
    # Overlap: next window starts 40 chars after previous
    if len(chunks) > 1:
        assert chunks[1].start == 40
        assert text[chunks[0].end - 10 : chunks[0].end] == text[chunks[1].start : chunks[1].start + 10]


def test_pass_shifts():
    assert pass_shifts(3000, 1) == [0]
    assert pass_shifts(3000, 3) == [0, 1000, 2000]


def test_validator_grounded_and_blocked():
    source = SAMPLE.read_text(encoding="utf-8").replace("\r\n", "\n")
    quote = "record revenue of $39.3 billion"
    start = source.index(quote)
    ok = validate_extraction(
        source,
        LLMExtraction(query="total revenue", value="$39.3 billion", quote=quote, start=start, end=start + len(quote)),
    )
    assert ok.status == "grounded"
    assert source[ok.start : ok.end] == quote

    remapped = validate_extraction(
        source,
        LLMExtraction(query="total revenue", value="$39.3 billion", quote=quote, start=0, end=5),
    )
    assert remapped.status == "remapped"
    assert source[remapped.start : remapped.end] == quote

    blocked = validate_extraction(
        source,
        LLMExtraction(
            query="total revenue",
            value="a trillion dollars",
            quote="NVIDIA secretly earned a trillion dollars this quarter",
        ),
    )
    assert blocked.status == "blocked"
    assert blocked.start is None


def test_find_span_whitespace():
    source = "GAAP gross profit margin was 73.0 percent"
    span = find_span(source, "GAAP  gross   profit margin was 73.0 percent")
    assert span is not None
    assert "73.0" in source[span[0] : span[1]]


def test_mock_extracts_nvidia_facts():
    source = SAMPLE.read_text(encoding="utf-8").replace("\r\n", "\n")
    items = invoke_mock(source, "total revenue")
    assert items
    assert "39.3" in items[0].quote
    margin = invoke_mock(source, "gross profit margin")
    assert margin and "73.0" in margin[0].quote


def test_extract_query_mock_grounded():
    source = SAMPLE.read_text(encoding="utf-8").replace("\r\n", "\n")
    result = extract_query(source, "data center revenue", provider="mock", passes=2, chunk_size=800, overlap=80)
    assert result.grounded_count >= 1
    item = next(i for i in result.items if i.grounded)
    assert source[item.start : item.end] == item.quote
    assert "35.6" in item.quote


def test_pipeline_exports(tmp_path: Path):
    summary = run_pipeline(
        [
            "--input",
            str(SAMPLE),
            "--provider",
            "mock",
            "--passes",
            "2",
            "--out",
            str(tmp_path),
            "--sequential-queries",
        ]
    )
    assert summary["ok"]
    assert summary["grounded"] >= 5
    assert (tmp_path / "outputs.md").is_file()
    data = json.loads((tmp_path / "annotations.json").read_text(encoding="utf-8"))
    assert data["document"]["text"]
    for row in data["extractions"]:
        if row["status"] in {"grounded", "remapped"}:
            start, end = row["start"], row["end"]
            assert data["document"]["text"][start:end] == row["quote"]


def test_stack_status_and_graph_run(tmp_path: Path):
    from pipeline.langstack import graph_run, smith_status, stack_status

    info = stack_status()
    assert info["ok"]
    assert info["langchain"]["installed"]
    assert info["langgraph"]["installed"]
    assert info["langsmith"]["installed"]
    smith = smith_status()
    assert smith["ok"]
    assert smith["has_key"] is False

    summary = graph_run(
        document=str(SAMPLE),
        queries=["total revenue", "gross profit margin"],
        provider="mock",
        passes=2,
        out_dir=str(tmp_path),
    )
    assert summary["ok"]
    assert summary["engine"] == "langgraph"
    assert summary["grounded"] >= 2
    assert summary["validation"]["ok"]
    data = json.loads((tmp_path / "annotations.json").read_text(encoding="utf-8"))
    for row in data["extractions"]:
        if row["status"] in {"grounded", "remapped"}:
            assert data["document"]["text"][row["start"] : row["end"]] == row["quote"]


def test_latest_claude_and_grok_defaults(monkeypatch):
    monkeypatch.delenv("EXTRACT_MODEL", raising=False)
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    monkeypatch.delenv("CLAUDE_MODEL", raising=False)
    monkeypatch.delenv("XAI_MODEL", raising=False)
    from pipeline import llm

    assert resolve_provider("claude") == "claude"
    assert resolve_provider("anthropic") == "claude"
    assert resolve_provider("grok") == "xai"
    assert resolve_provider("xai") == "xai"
    assert default_model_for("claude") == llm.DEFAULT_CLAUDE_MODEL
    assert default_model_for("anthropic") == llm.DEFAULT_CLAUDE_MODEL
    assert default_model_for("xai") == llm.DEFAULT_GROK_MODEL
    assert default_model_for("grok") == llm.DEFAULT_GROK_MODEL
    assert llm.DEFAULT_CLAUDE_MODEL == "claude-sonnet-5"
    assert llm.DEFAULT_GROK_MODEL == "grok-4.6"
    assert default_model_for("claude", "claude-opus-5") == "claude-opus-5"
    assert default_model_for("xai", "grok-4.5") == "grok-4.5"
    assert default_model_for("mock") == "mock"


def test_pdf_roundtrip(tmp_path: Path):
    text = SAMPLE.read_text(encoding="utf-8")
    try:
        import fitz  # noqa: F401
    except ImportError:
        pytest.skip("pymupdf not installed")
    pdf = write_sample_pdf(text, tmp_path / "nvidia.pdf")
    doc = load_document(pdf)
    assert "39.3" in doc.text
    assert doc.loader in {"pymupdf", "pypdf"}
    result = extract_query(doc.text, "total revenue", provider="mock", passes=1)
    assert result.grounded_count >= 1
