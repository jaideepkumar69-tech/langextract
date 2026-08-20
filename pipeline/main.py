"""Multi-pass financial document analysis (Prompt 3).

Load a document (default: sample NVIDIA Q4 commentary), run a list of
extraction queries in parallel, collect latency + exact character spans,
and export outputs.md + annotations.json.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from pipeline.extractor import extract_document  # noqa: E402
from pipeline.report import write_annotations, write_clean_json, write_markdown  # noqa: E402

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    load_dotenv(PROJECT / ".env")
except ImportError:
    pass

DEFAULT_DOC = ROOT / "samples" / "nvidia_q4_fy2025.txt"
DEFAULT_OUT = PROJECT / "pipeline" / "outputs"
DEFAULT_QUERIES = [
    "total revenue",
    "gross profit margin",
    "year-over-year revenue growth",
    "sequential revenue growth",
    "data center revenue",
    "GAAP diluted EPS",
]


def load_queries(path: str | None, extra: list[str]) -> list[str]:
    queries: list[str] = []
    if path:
        qpath = Path(path)
        text = qpath.read_text(encoding="utf-8")
        if qpath.suffix.lower() in {".yaml", ".yml"}:
            try:
                import yaml

                data = yaml.safe_load(text) or {}
                if isinstance(data, dict):
                    queries.extend(str(q) for q in data.get("queries", []))
                elif isinstance(data, list):
                    queries.extend(str(q) for q in data)
            except ImportError:
                queries.extend(
                    line[2:].strip() if line.lstrip().startswith("- ") else line.strip()
                    for line in text.splitlines()
                    if line.strip() and not line.strip().startswith("#")
                )
        else:
            queries.extend(line.strip() for line in text.splitlines() if line.strip())
    queries.extend(q.strip() for q in extra if q.strip())
    # de-dupe, keep order
    seen: set[str] = set()
    out: list[str] = []
    for q in queries:
        key = q.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(q)
    return out or list(DEFAULT_QUERIES)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Grounded multi-pass financial extraction")
    p.add_argument("--input", "-i", default=str(DEFAULT_DOC), help="PDF or text document")
    p.add_argument("--queries", "-q", action="append", default=[], help="Query (repeatable)")
    p.add_argument(
        "--queries-file",
        default=None,
        help="YAML/text list of queries. Ignored when --queries is passed.",
    )
    p.add_argument("--provider", default=os.environ.get("EXTRACT_PROVIDER", "auto"))
    p.add_argument("--model", default=os.environ.get("EXTRACT_MODEL"))
    p.add_argument("--passes", type=int, default=int(os.environ.get("EXTRACT_PASSES", "3")))
    p.add_argument("--chunk-size", type=int, default=4000)
    p.add_argument("--overlap", type=int, default=400)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--sequential-queries", action="store_true")
    return p.parse_args(argv)


def run(argv: list[str] | None = None) -> dict:
    args = parse_args(argv)
    qfile = args.queries_file
    if not args.queries and qfile is None:
        qfile = str(ROOT / "queries.yaml")
    queries = load_queries(qfile, args.queries)
    out_dir = Path(args.out)
    report = extract_document(
        args.input,
        queries,
        provider=args.provider,
        model=args.model,
        passes=args.passes,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
        max_workers=args.workers,
        parallel_queries=not args.sequential_queries,
    )
    md = write_markdown(report, out_dir / "outputs.md")
    ann = write_annotations(report, out_dir / "annotations.json")
    clean = write_clean_json(report, out_dir / "annotations.clean.json")
    summary = {
        "ok": True,
        "document": report.document.path,
        "provider": report.model.provider,
        "model": report.model.model,
        "queries": report.queries,
        "grounded": report.metrics.get("grounded"),
        "blocked": report.metrics.get("blocked"),
        "total_latency_ms": report.metrics.get("total_latency_ms"),
        "outputs": {
            "markdown": str(md),
            "annotations": str(ann),
            "clean": str(clean),
        },
    }
    return summary


def main() -> int:
    summary = run()
    print(
        f"provider={summary['provider']} model={summary['model']} "
        f"grounded={summary['grounded']} blocked={summary['blocked']} "
        f"latency_ms={summary['total_latency_ms']}"
    )
    print(f"report: {summary['outputs']['markdown']}")
    print(f"annotations: {summary['outputs']['annotations']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
