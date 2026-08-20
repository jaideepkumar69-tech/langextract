"""CLI helper for the grounded LangExtract / LangChain pipeline."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
PIPELINE = PROJECT / "pipeline"
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))


def _out(data: object) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)


def _venv_python() -> Path:
    for candidate in (
        PIPELINE / ".venv" / "Scripts" / "python.exe",
        PIPELINE / ".venv" / "bin" / "python",
        PROJECT / ".venv" / "Scripts" / "python.exe",
    ):
        if candidate.is_file():
            return candidate
    return Path(sys.executable)


def status() -> dict:
    from pipeline.llm import list_ollama_models, ollama_alive, resolve_provider

    sample = PIPELINE / "samples" / "nvidia_q4_fy2025.txt"
    annotations = PIPELINE / "outputs" / "annotations.json"
    provider = resolve_provider(os.environ.get("EXTRACT_PROVIDER"))
    return {
        "ok": True,
        "project": str(PROJECT),
        "pipeline": str(PIPELINE),
        "python": str(_venv_python()),
        "sample": str(sample) if sample.is_file() else None,
        "annotations": str(annotations) if annotations.is_file() else None,
        "ollama": {
            "alive": ollama_alive(),
            "models": list_ollama_models(),
            "url": os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434"),
        },
        "provider": provider,
        "review_url": "http://127.0.0.1:8788/",
        "mcp_http": "http://127.0.0.1:8768/mcp",
        "langflow_url": "http://127.0.0.1:7860/",
    }


def run_extract(
    document: str = "",
    queries: list[str] | None = None,
    provider: str = "mock",
    model: str | None = None,
    passes: int = 2,
    out_dir: str = "",
) -> dict:
    from pipeline.main import run

    argv = [
        "--input",
        document or str(PIPELINE / "samples" / "nvidia_q4_fy2025.txt"),
        "--provider",
        provider or "mock",
        "--passes",
        str(passes),
        "--out",
        out_dir or str(PIPELINE / "outputs"),
        "--sequential-queries",
    ]
    if model:
        argv += ["--model", model]
    if queries:
        for q in queries:
            argv += ["--queries", q]
    return run(argv)


def validate_annotations(path: str = "") -> dict:
    from pipeline.models import ExtractionReport

    target = Path(path) if path else PIPELINE / "outputs" / "annotations.json"
    if not target.is_file():
        return {"ok": False, "error": f"missing {target}"}
    report = ExtractionReport.model_validate_json(target.read_text(encoding="utf-8"))
    bad = []
    for item in report.extractions:
        if item.status in {"grounded", "remapped"}:
            if item.start is None or item.end is None:
                bad.append({"id": item.id, "error": "missing offsets"})
                continue
            slice_ = report.document.text[item.start : item.end]
            if slice_ != item.quote:
                bad.append(
                    {
                        "id": item.id,
                        "error": "quote does not match source span",
                        "span": slice_,
                        "quote": item.quote,
                    }
                )
    return {
        "ok": not bad,
        "path": str(target),
        "checked": len(report.extractions),
        "mismatches": bad,
        "grounded": report.metrics.get("grounded"),
        "blocked": report.metrics.get("blocked"),
    }


def _port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex((host, port)) == 0


def start_review(port: int = 8788) -> dict:
    url = f"http://127.0.0.1:{port}/"
    if _port_open("127.0.0.1", port):
        return {"ok": True, "url": url, "already_running": True}
    py = _venv_python()
    vis = PIPELINE / "visualizer.py"
    ann = PIPELINE / "outputs" / "annotations.json"
    if not ann.is_file():
        return {"ok": False, "error": f"run extract first; missing {ann}"}
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    proc = subprocess.Popen(
        [str(py), str(vis), "--annotations", str(ann), "--port", str(port), "--no-browser"],
        cwd=str(PROJECT),
        creationflags=creationflags,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return {"ok": True, "url": url, "pid": proc.pid, "already_running": False}


def demo_path() -> dict:
    return {"ok": True, "path": str(PIPELINE / "samples" / "nvidia_q4_fy2025.txt")}


def default_queries() -> dict:
    from pipeline.main import DEFAULT_QUERIES

    return {"ok": True, "queries": DEFAULT_QUERIES}


def stack() -> dict:
    from pipeline.langstack import stack_status

    return stack_status()


def graph(
    document: str = "",
    queries: list[str] | None = None,
    provider: str = "mock",
    model: str | None = None,
    passes: int = 2,
    out_dir: str = "",
) -> dict:
    from pipeline.langstack import graph_run

    return graph_run(document, queries, provider, model, passes, out_dir)


def main() -> int:
    p = argparse.ArgumentParser(description="LangExtract grounded pipeline helper")
    p.add_argument(
        "cmd",
        choices=[
            "status",
            "run",
            "validate",
            "review",
            "demo",
            "queries",
            "stack",
            "graph",
            "smith",
            "flow",
        ],
    )
    p.add_argument("--input", default="")
    p.add_argument("--provider", default="mock")
    p.add_argument("--model", default="")
    p.add_argument("--passes", type=int, default=2)
    p.add_argument("--query", action="append", default=[])
    p.add_argument("--out", default="")
    p.add_argument("--annotations", default="")
    p.add_argument("--port", type=int, default=8788)
    args = p.parse_args()
    if args.cmd == "status":
        print(_out(status()))
    elif args.cmd == "run":
        print(
            _out(
                run_extract(
                    args.input,
                    args.query or None,
                    args.provider,
                    args.model or None,
                    args.passes,
                    args.out,
                )
            )
        )
    elif args.cmd == "validate":
        print(_out(validate_annotations(args.annotations)))
    elif args.cmd == "review":
        print(_out(start_review(args.port)))
    elif args.cmd == "demo":
        print(_out(demo_path()))
    elif args.cmd == "queries":
        print(_out(default_queries()))
    elif args.cmd == "stack":
        print(_out(stack()))
    elif args.cmd == "graph":
        print(
            _out(
                graph(
                    args.input,
                    args.query or None,
                    args.provider,
                    args.model or None,
                    args.passes,
                    args.out,
                )
            )
        )
    elif args.cmd == "smith":
        from pipeline.langstack import smith_status

        print(_out(smith_status()))
    elif args.cmd == "flow":
        from pipeline.langstack import flow_status

        print(_out(flow_status()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
