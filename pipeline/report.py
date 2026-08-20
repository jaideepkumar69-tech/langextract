"""Export a grounded extraction report to outputs.md and annotations.json."""

from __future__ import annotations

import json
from pathlib import Path

from pipeline.models import ExtractionReport


def write_annotations(report: ExtractionReport, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(report.model_dump(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return dest


def _md_escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def write_markdown(report: ExtractionReport, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    doc = report.document
    model = report.model
    metrics = report.metrics
    lines: list[str] = [
        f"# Extraction report — {doc.name}",
        "",
        f"- Generated: `{report.generated_at}`",
        f"- Source: `{doc.path}` ({doc.char_count} chars, loader `{doc.loader}`)",
        f"- SHA-256: `{doc.sha256}`",
        f"- Provider: `{model.provider}` / `{model.model}` (engine `{model.engine}`)",
        f"- Passes: {report.passes} · chunk {report.chunk_size} / overlap {report.chunk_overlap}",
        f"- Total latency: **{metrics.get('total_latency_ms', 0):.1f} ms**",
        f"- Grounded: **{metrics.get('grounded', 0)}** · blocked: **{metrics.get('blocked', 0)}**",
        "",
        "## Queries",
        "",
        "| Query | Latency (ms) | Grounded | Blocked |",
        "| --- | ---: | ---: | ---: |",
    ]
    for result in report.results:
        lines.append(
            f"| {_md_escape(result.query)} | {result.latency_ms:.1f} | "
            f"{result.grounded_count} | {result.blocked_count} |"
        )
    lines += ["", "## Extractions", ""]
    for item in report.extractions:
        span = f"{item.start}–{item.end}" if item.start is not None else "—"
        badge = item.status.upper()
        lines += [
            f"### {item.query} · `{badge}`",
            "",
            f"- id: `{item.id}`",
            f"- value: **{_md_escape(item.value) or '—'}**",
            f"- quote: “{_md_escape(item.quote)}”",
            f"- span: `{span}` · pass {item.pass_index} · chunk {item.chunk_id}",
            f"- confidence: {item.confidence:.2f} · latency {item.latency_ms:.1f} ms",
            f"- review: `{item.review}`",
            f"- note: {_md_escape(item.reason) or '—'}",
            "",
        ]
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dest


def write_clean_json(report: ExtractionReport, dest: Path) -> Path:
    """Database-ready export: accepted/fixed/grounded rows only, no full text."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for item in report.accepted_or_grounded():
        rows.append(
            {
                "id": item.id,
                "query": item.query,
                "value": item.value,
                "quote": item.quote,
                "start": item.start,
                "end": item.end,
                "status": item.status,
                "review": item.review,
                "confidence": item.confidence,
                "document": report.document.name,
                "sha256": report.document.sha256,
            }
        )
    dest.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return dest
