"""Extraction engine: chunk, call the LLM, map exact character spans, validate.

Ingests large PDF/text documents, runs a grounded extractor (LangChain + Ollama
by default; Claude, Grok, Gemini, OpenAI, or Google LangExtract configurable),
and blocks paraphrases / hallucinations that cannot be located in the source.
"""

from __future__ import annotations

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))

from pipeline.chunking import Chunk, chunk_text, pass_shifts  # noqa: E402
from pipeline.llm import (  # noqa: E402
    default_model_for,
    invoke_model,
    pick_ollama_model,
    resolve_provider,
)
from pipeline.loaders import load_document  # noqa: E402
from pipeline.models import (  # noqa: E402
    ExtractionItem,
    ExtractionReport,
    LLMExtraction,
    ModelMeta,
    QueryResult,
)
from pipeline.validator import dedupe_items, validate_extraction  # noqa: E402

# Re-export for `from pipeline.extractor import chunk_text, validate_extraction`
__all__ = [
    "chunk_text",
    "extract_document",
    "extract_query",
    "validate_extraction",
]


def _engine_for(provider: str) -> str:
    if provider == "langextract":
        return "langextract"
    if provider == "mock":
        return "mock"
    return "langchain"


def _invoke_langextract(source: str, query: str, model_id: str) -> list[LLMExtraction]:
    """Optional Google LangExtract backend (same grounding contract)."""
    import langextract as lx

    prompt = (
        "Extract the financial fact requested. Use exact source text. "
        "Do not paraphrase. One extraction per supporting quote."
    )
    examples = [
        lx.data.ExampleData(
            text="The company reported record revenue of $12.4 billion for the quarter.",
            extractions=[
                lx.data.Extraction(
                    extraction_class="metric",
                    extraction_text="record revenue of $12.4 billion",
                    attributes={"query": "total revenue", "value": "$12.4 billion"},
                )
            ],
        )
    ]
    result = lx.extract(
        text_or_documents=source,
        prompt_description=f"{prompt}\nRequested fact: {query}",
        examples=examples,
        model_id=model_id,
        extraction_passes=1,
        max_char_buffer=min(4000, max(800, len(source))),
        fence_output=True,
        use_schema_constraints=False,
    )
    items: list[LLMExtraction] = []
    for ext in result.extractions or []:
        start = getattr(getattr(ext, "char_interval", None), "start_pos", None)
        end = getattr(getattr(ext, "char_interval", None), "end_pos", None)
        attrs = ext.attributes or {}
        items.append(
            LLMExtraction(
                query=str(attrs.get("query") or query),
                value=str(attrs.get("value") or ext.extraction_text or ""),
                quote=ext.extraction_text or "",
                start=start,
                end=end,
                confidence=0.8 if start is not None else 0.4,
            )
        )
    return items


def _run_chunk(
    *,
    source: str,
    chunk: Chunk,
    query: str,
    provider: str,
    model: str,
) -> list[ExtractionItem]:
    t0 = time.perf_counter()
    if provider == "langextract":
        raw_items = _invoke_langextract(chunk.text, query, model)
    else:
        raw_items = invoke_model(provider, model, chunk.text, query)
    latency = (time.perf_counter() - t0) * 1000
    validated: list[ExtractionItem] = []
    for raw in raw_items:
        raw.query = raw.query or query
        item = validate_extraction(
            source,
            raw,
            chunk_start=chunk.start,
            pass_index=chunk.pass_index,
            chunk_id=chunk.chunk_id,
            latency_ms=round(latency, 2),
        )
        validated.append(item)
    return validated


def extract_query(
    source: str,
    query: str,
    *,
    provider: str = "auto",
    model: str | None = None,
    passes: int = 3,
    chunk_size: int = 4000,
    overlap: int = 400,
    max_workers: int = 4,
) -> QueryResult:
    """Multi-pass extraction for a single query with overlapping chunks."""
    provider = resolve_provider(provider)
    if provider == "ollama":
        model = pick_ollama_model(model)
    else:
        model = default_model_for(provider, model)

    t0 = time.perf_counter()
    shifts = pass_shifts(chunk_size, max(1, passes))
    jobs: list[Chunk] = []
    for pass_index, shift in enumerate(shifts):
        jobs.extend(
            chunk_text(
                source,
                chunk_size=chunk_size,
                overlap=overlap,
                pass_index=pass_index,
                offset_shift=shift,
            )
        )
    if not jobs:
        jobs = [Chunk(chunk_id=0, start=0, end=len(source), text=source, pass_index=0)]

    collected: list[ExtractionItem] = []
    workers = max(1, min(max_workers, len(jobs)))
    if workers == 1:
        for chunk in jobs:
            collected.extend(
                _run_chunk(source=source, chunk=chunk, query=query, provider=provider, model=model)
            )
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futs = [
                pool.submit(
                    _run_chunk,
                    source=source,
                    chunk=chunk,
                    query=query,
                    provider=provider,
                    model=model,
                )
                for chunk in jobs
            ]
            for fut in as_completed(futs):
                collected.extend(fut.result())

    items = dedupe_items(collected)
    grounded = [i for i in items if i.grounded]
    blocked = [i for i in items if not i.grounded]
    return QueryResult(
        query=query,
        latency_ms=round((time.perf_counter() - t0) * 1000, 2),
        items=items,
        grounded_count=len(grounded),
        blocked_count=len(blocked),
    )


def extract_document(
    path: str | Path,
    queries: list[str],
    *,
    provider: str = "auto",
    model: str | None = None,
    passes: int = 3,
    chunk_size: int = 4000,
    overlap: int = 400,
    max_workers: int = 4,
    parallel_queries: bool = True,
) -> ExtractionReport:
    """Run every query (optionally in parallel) and assemble a review report."""
    doc = load_document(path)
    provider = resolve_provider(provider)
    if provider == "ollama":
        model_id = pick_ollama_model(model)
    else:
        model_id = default_model_for(provider, model)

    t0 = time.perf_counter()
    results: list[QueryResult] = []

    def _one(q: str) -> QueryResult:
        return extract_query(
            doc.text,
            q,
            provider=provider,
            model=model_id,
            passes=passes,
            chunk_size=chunk_size,
            overlap=overlap,
            max_workers=max_workers,
        )

    if parallel_queries and len(queries) > 1:
        with ThreadPoolExecutor(max_workers=min(max_workers, len(queries))) as pool:
            futs = {pool.submit(_one, q): q for q in queries}
            by_q = {futs[f]: f.result() for f in as_completed(futs)}
        results = [by_q[q] for q in queries]
    else:
        results = [_one(q) for q in queries]

    extractions: list[ExtractionItem] = []
    for result in results:
        extractions.extend(result.items)

    total_ms = (time.perf_counter() - t0) * 1000
    grounded = sum(1 for e in extractions if e.grounded)
    blocked = sum(1 for e in extractions if not e.grounded)
    report = ExtractionReport(
        document=doc,
        model=ModelMeta(
            provider=provider,
            model=model_id,
            engine=_engine_for(provider),
            ollama_url=os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434"),
        ),
        queries=list(queries),
        passes=passes,
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        metrics={
            "total_latency_ms": round(total_ms, 2),
            "grounded": grounded,
            "blocked": blocked,
            "queries": len(queries),
            "per_query_ms": {r.query: r.latency_ms for r in results},
        },
        results=results,
        extractions=extractions,
    )
    return report
