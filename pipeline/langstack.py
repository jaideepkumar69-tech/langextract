"""LangChain + LangGraph + LangSmith + LangFlow, merged into LangExtract.

LangChain / LangGraph / LangSmith live in pipeline/.venv.
LangFlow is isolated in pipeline/.venv-langflow so its pins cannot
break the extraction stack. No Docker.
"""

from __future__ import annotations

import importlib.metadata
import os
import socket
import subprocess
from pathlib import Path
from typing import Any, TypedDict

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
FLOW_VENV = ROOT / ".venv-langflow"
FLOW_HOST = os.environ.get("LANGFLOW_HOST", "127.0.0.1")
FLOW_PORT = int(os.environ.get("LANGFLOW_PORT", "7860"))
FLOW_PID = ROOT / "outputs" / "langflow.pid"
SMITH_PROJECT = os.environ.get("LANGSMITH_PROJECT") or os.environ.get(
    "LANGCHAIN_PROJECT", "langextract"
)

PACKAGES = ("langchain", "langchain-core", "langgraph", "langsmith", "langflow", "langflow-base")


class ExtractState(TypedDict, total=False):
    document: str
    queries: list[str]
    provider: str
    model: str
    passes: int
    out_dir: str
    source_chars: int
    summary: dict[str, Any]
    validation: dict[str, Any]
    error: str
    engine: str


def _pkg_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex((host, port)) == 0


def _flow_python() -> Path | None:
    for candidate in (
        FLOW_VENV / "Scripts" / "python.exe",
        FLOW_VENV / "bin" / "python",
    ):
        if candidate.is_file():
            return candidate
    return None


def _flow_cli() -> list[str] | None:
    py = _flow_python()
    if not py:
        return None
    for name in ("langflow-base.exe", "langflow.exe", "langflow-base", "langflow"):
        exe = py.parent / name
        if exe.is_file():
            return [str(exe)]
    probe = (
        "import importlib.util, sys;"
        "sys.exit(0 if any(importlib.util.find_spec(n) for n in"
        " ('langflow','langflow_base','lfx')) else 1)"
    )
    try:
        subprocess.check_call(
            [str(py), "-c", probe],
            timeout=20,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return [str(py), "-m", "langflow"]
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None


def smith_api_key() -> str:
    return (
        os.environ.get("LANGSMITH_API_KEY")
        or os.environ.get("LANGCHAIN_API_KEY")
        or ""
    ).strip()


def configure_langsmith() -> dict[str, Any]:
    key = smith_api_key()
    enabled = bool(key)
    if enabled:
        os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
        os.environ.setdefault("LANGSMITH_TRACING", "true")
        os.environ.setdefault("LANGCHAIN_PROJECT", SMITH_PROJECT)
        os.environ.setdefault("LANGSMITH_PROJECT", SMITH_PROJECT)
        if "LANGSMITH_API_KEY" not in os.environ and os.environ.get("LANGCHAIN_API_KEY"):
            os.environ["LANGSMITH_API_KEY"] = os.environ["LANGCHAIN_API_KEY"]
    return {
        "enabled": enabled,
        "project": SMITH_PROJECT,
        "endpoint": os.environ.get("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com"),
        "has_key": enabled,
    }


def stack_status() -> dict[str, Any]:
    versions = {name: _pkg_version(name) for name in PACKAGES}
    flow_py = _flow_python()
    if flow_py and not versions.get("langflow"):
        try:
            versions["langflow"] = subprocess.check_output(
                [
                    str(flow_py),
                    "-c",
                    "import importlib.metadata as m\n"
                    "for n in ('langflow','langflow-base'):\n"
                    "    try:\n"
                    "        print(n+'=='+m.version(n)); break\n"
                    "    except m.PackageNotFoundError:\n"
                    "        pass",
                ],
                text=True,
                timeout=15,
                stderr=subprocess.DEVNULL,
            ).strip() or None
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            versions["langflow"] = "sidecar-unknown"
    smith = configure_langsmith()
    return {
        "ok": True,
        "merged_mcp": "langextract",
        "clients": ["claude-cli", "claude-desktop", "grok-build", "grok.com"],
        "packages": versions,
        "langchain": {"installed": bool(versions["langchain"]), "version": versions["langchain"]},
        "langgraph": {"installed": bool(versions["langgraph"]), "version": versions["langgraph"]},
        "langsmith": {**smith, "installed": bool(versions["langsmith"]), "version": versions["langsmith"]},
        "langflow": flow_status() | {"version": versions.get("langflow")},
        "venv": str(ROOT / ".venv"),
        "langflow_venv": str(FLOW_VENV) if FLOW_VENV.is_dir() else None,
    }


def smith_status() -> dict[str, Any]:
    info = configure_langsmith()
    info["ok"] = True
    info["installed"] = _pkg_version("langsmith") is not None
    info["version"] = _pkg_version("langsmith")
    if not info["has_key"]:
        info["hint"] = (
            "Set LANGSMITH_API_KEY (or LANGCHAIN_API_KEY) to send traces to "
            "https://smith.langchain.com. Offline extraction still works."
        )
        return info
    try:
        from langsmith import Client

        client = Client()
        info["reachable"] = True
        try:
            info["workspace"] = getattr(client, "info", lambda: None)() is not None
        except Exception:  # noqa: BLE001
            info["workspace"] = None
    except Exception as exc:  # noqa: BLE001
        info["reachable"] = False
        info["error"] = f"{type(exc).__name__}: {exc}"
    return info


def _node_load(state: ExtractState) -> ExtractState:
    from pipeline.loaders import load_document
    from pipeline.main import DEFAULT_QUERIES, DEFAULT_DOC

    path = state.get("document") or str(DEFAULT_DOC)
    queries = state.get("queries") or list(DEFAULT_QUERIES)
    doc = load_document(path)
    return {
        **state,
        "document": str(doc.path),
        "queries": queries,
        "source_chars": doc.char_count,
        "engine": "langgraph+langchain",
    }


def _node_extract(state: ExtractState) -> ExtractState:
    from pipeline.extractor import extract_document
    from pipeline.report import write_annotations, write_clean_json, write_markdown

    out_dir = Path(state.get("out_dir") or (ROOT / "outputs"))
    report = extract_document(
        state["document"],
        list(state.get("queries") or []),
        provider=state.get("provider") or "mock",
        model=state.get("model") or None,
        passes=int(state.get("passes") or 2),
        parallel_queries=False,
    )
    md = write_markdown(report, out_dir / "outputs.md")
    ann = write_annotations(report, out_dir / "annotations.json")
    clean = write_clean_json(report, out_dir / "annotations.clean.json")
    summary = {
        "ok": True,
        "document": report.document.path,
        "provider": report.model.provider,
        "model": report.model.model,
        "engine": "langgraph",
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
    return {**state, "summary": summary}


def _validate_annotations(path: str) -> dict[str, Any]:
    from pipeline.models import ExtractionReport

    target = Path(path) if path else ROOT / "outputs" / "annotations.json"
    if not target.is_file():
        return {"ok": False, "error": f"missing {target}"}
    report = ExtractionReport.model_validate_json(target.read_text(encoding="utf-8"))
    bad = []
    for item in report.extractions:
        if item.status not in {"grounded", "remapped"}:
            continue
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


def _node_validate(state: ExtractState) -> ExtractState:
    outputs = (state.get("summary") or {}).get("outputs") or {}
    path = outputs.get("annotations") or ""
    return {**state, "validation": _validate_annotations(path)}


def build_extract_graph():
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(ExtractState)
    graph.add_node("load", _node_load)
    graph.add_node("extract", _node_extract)
    graph.add_node("validate", _node_validate)
    graph.add_edge(START, "load")
    graph.add_edge("load", "extract")
    graph.add_edge("extract", "validate")
    graph.add_edge("validate", END)
    return graph.compile()


def graph_run(
    document: str = "",
    queries: list[str] | None = None,
    provider: str = "mock",
    model: str | None = None,
    passes: int = 2,
    out_dir: str = "",
) -> dict[str, Any]:
    """Run grounded extraction as a LangGraph: load → extract → validate."""
    smith = configure_langsmith()
    app = build_extract_graph()
    initial: ExtractState = {
        "document": document,
        "queries": list(queries or []),
        "provider": provider or "mock",
        "model": model or "",
        "passes": passes,
        "out_dir": out_dir,
    }
    try:
        final = app.invoke(initial)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "engine": "langgraph", "error": f"{type(exc).__name__}: {exc}"}
    summary = dict(final.get("summary") or {})
    summary.setdefault("ok", True)
    summary["engine"] = "langgraph"
    summary["langsmith"] = smith
    summary["validation"] = final.get("validation")
    summary["source_chars"] = final.get("source_chars")
    return summary


def flow_status() -> dict[str, Any]:
    url = f"http://{FLOW_HOST}:{FLOW_PORT}/"
    running = _port_open(FLOW_HOST, FLOW_PORT)
    pid = None
    if FLOW_PID.is_file():
        try:
            pid = int(FLOW_PID.read_text(encoding="utf-8").strip())
        except ValueError:
            pid = None
    cli = _flow_cli()
    return {
        "ok": True,
        "installed": cli is not None,
        "running": running,
        "url": url if running else None,
        "host": FLOW_HOST,
        "port": FLOW_PORT,
        "pid": pid,
        "venv": str(FLOW_VENV) if FLOW_VENV.is_dir() else None,
        "hint": None
        if cli
        else (
            "LangFlow is not installed. Sidecar: "
            r"pipeline\.venv-langflow\Scripts\python.exe -m pip install langflow"
        ),
    }


def flow_start() -> dict[str, Any]:
    current = flow_status()
    if current["running"]:
        return {**current, "already_running": True}
    cli = _flow_cli()
    if not cli:
        return {**current, "ok": False, "error": current["hint"]}
    FLOW_PID.parent.mkdir(parents=True, exist_ok=True)
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    log = FLOW_PID.with_suffix(".log")
    handle = log.open("a", encoding="utf-8")
    proc = subprocess.Popen(
        [*cli, "run", "--host", FLOW_HOST, "--port", str(FLOW_PORT)],
        cwd=str(PROJECT),
        stdout=handle,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
    )
    FLOW_PID.write_text(str(proc.pid), encoding="utf-8")
    return {
        "ok": True,
        "started": True,
        "pid": proc.pid,
        "url": f"http://{FLOW_HOST}:{FLOW_PORT}/",
        "log": str(log),
        "note": "LangFlow UI is local. Extraction still goes through extract_run / graph_run.",
    }


def flow_stop() -> dict[str, Any]:
    if not FLOW_PID.is_file():
        return {"ok": True, "stopped": False, "reason": "no pid file"}
    try:
        pid = int(FLOW_PID.read_text(encoding="utf-8").strip())
    except ValueError:
        FLOW_PID.unlink(missing_ok=True)
        return {"ok": True, "stopped": False, "reason": "bad pid file"}
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            os.kill(pid, 15)
    except OSError as exc:
        return {"ok": False, "error": str(exc), "pid": pid}
    FLOW_PID.unlink(missing_ok=True)
    return {"ok": True, "stopped": True, "pid": pid}
