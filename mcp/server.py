"""
langextract MCP server

Grounded document extraction (LangChain + LangGraph + LangSmith + LangFlow)
with exact character spans and a review UI.

  - stdio  — Claude CLI, Claude Desktop, Grok Build CLI
  - HTTP   — grok.com + Grok Desktop via a public tunnel (/mcp)

No Docker. LangFlow runs in an isolated sidecar venv if installed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

from langextract_pipeline import (  # noqa: E402
    default_queries,
    demo_path,
    run_extract,
    start_review,
    status,
    validate_annotations,
)
from mcp.server.fastmcp import FastMCP  # noqa: E402
from mcp.server.transport_security import TransportSecuritySettings  # noqa: E402

DEFAULT_PORT = 8768

mcp = FastMCP(
    "langextract",
    instructions=(
        "Merged LangExtract MCP: LangChain + LangGraph + LangSmith + LangFlow. "
        r"Default sample is C:\Users\USER\projects\langextract\pipeline\samples\nvidia_q4_fy2025.txt. "
        "Call stack_status first. extract_run or graph_run (provider=mock for offline). "
        "Live models: provider=claude model=claude-sonnet-5 (or claude-opus-5); "
        "provider=xai model=grok-4.6. "
        "Then extract_validate and extract_review. Do not invent figures; only report grounded spans."
    ),
    host=os.environ.get("FASTMCP_HOST", "127.0.0.1"),
    port=int(os.environ.get("FASTMCP_PORT", str(DEFAULT_PORT))),
    stateless_http=True,
)


def _out(data: object) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)


def _safe(fn, *args, **kwargs) -> str:
    try:
        return _out(fn(*args, **kwargs))
    except Exception as exc:  # noqa: BLE001
        return _out({"ok": False, "error": f"{type(exc).__name__}: {exc}"})


@mcp.tool()
def extract_status() -> str:
    """Show pipeline path, Ollama models, last annotations, and review URL."""
    return _safe(status)


@mcp.tool()
def extract_run(
    document: str = "",
    queries: str = "",
    provider: str = "mock",
    model: str = "",
    passes: int = 2,
) -> str:
    """Run multi-pass grounded extraction. queries is a semicolon-separated list.

    Providers: mock, ollama, claude (claude-sonnet-5 / claude-opus-5), xai (grok-4.6),
    gemini, openai, langextract.
    """
    qlist = [q.strip() for q in queries.split(";") if q.strip()] or None

    def _run() -> dict:
        return run_extract(document, qlist, provider or "mock", model or None, passes)

    return _safe(_run)


@mcp.tool()
def extract_validate(annotations: str = "") -> str:
    """Re-check every grounded quote against the stored source text."""
    return _safe(validate_annotations, annotations)


@mcp.tool()
def extract_review(port: int = 8788) -> str:
    """Start the local review UI (highlights exact character spans) and return its URL."""
    return _safe(start_review, port)


@mcp.tool()
def extract_demo_path() -> str:
    """Absolute path of the bundled NVIDIA Q4 sample document."""
    return _safe(demo_path)


@mcp.tool()
def extract_queries() -> str:
    """Default financial queries (revenue, margin, YoY, EPS, …)."""
    return _safe(default_queries)


def _stack():
    from pipeline.langstack import (  # noqa: WPS433
        flow_start,
        flow_status,
        flow_stop,
        graph_run,
        smith_status,
        stack_status,
    )

    return stack_status, graph_run, smith_status, flow_status, flow_start, flow_stop


@mcp.tool()
def stack_status() -> str:
    """Versions and health of LangChain, LangGraph, LangSmith, and LangFlow."""
    status_fn, *_ = _stack()
    return _safe(status_fn)


@mcp.tool()
def graph_run(
    document: str = "",
    queries: str = "",
    provider: str = "mock",
    model: str = "",
    passes: int = 2,
) -> str:
    """Run extraction as a LangGraph (load → extract → validate). Same grounding rules."""
    qlist = [q.strip() for q in queries.split(";") if q.strip()] or None
    _, run_fn, *_ = _stack()

    def _run() -> dict:
        return run_fn(document, qlist, provider or "mock", model or None, passes)

    return _safe(_run)


@mcp.tool()
def smith_status() -> str:
    """LangSmith tracing status (set LANGSMITH_API_KEY to enable)."""
    return _safe(_stack()[2])


@mcp.tool()
def flow_status() -> str:
    """LangFlow UI status (sidecar venv, local port 7860)."""
    return _safe(_stack()[3])


@mcp.tool()
def flow_start() -> str:
    """Start the local LangFlow UI if the sidecar venv is installed. No Docker."""
    return _safe(_stack()[4])


@mcp.tool()
def flow_stop() -> str:
    """Stop the LangFlow UI started by flow_start."""
    return _safe(_stack()[5])


def main() -> None:
    parser = argparse.ArgumentParser(description="langextract MCP")
    parser.add_argument("--http", action="store_true")
    parser.add_argument("--sse", action="store_true")
    parser.add_argument("--host", default=os.environ.get("FASTMCP_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("FASTMCP_PORT", str(DEFAULT_PORT))))
    args = parser.parse_args()
    mcp.settings.host = args.host
    mcp.settings.port = args.port
    if args.http or args.sse:
        mcp.settings.transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=False
        )
    if args.http:
        mcp.run(transport="streamable-http")
    elif args.sse:
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
