"""LangChain LLM backends (Ollama default) plus Claude / Grok / Gemini / OpenAI / mock."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

from pipeline.models import LLMExtraction

DEFAULT_OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
DEFAULT_OLLAMA_MODEL = os.environ.get("EXTRACT_MODEL") or "gemma2:2b"
DEFAULT_CLAUDE_MODEL = "claude-sonnet-5"
DEFAULT_GROK_MODEL = "grok-4.6"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_LANGEXTRACT_MODEL = "gemini-3.5-flash"
# Larger local models the user can pull: qwen2.5:32b, qwen2.5:14b, llama3.1:8b
RECOMMENDED_LOCAL = ("qwen2.5:32b", "qwen2.5:14b", "qwen2.5-coder:7b", "gemma2:2b")

PROVIDER_ALIASES = {
    "claude": "claude",
    "anthropic": "claude",
    "grok": "xai",
    "xai": "xai",
    "openai": "openai",
    "gemini": "gemini",
    "ollama": "ollama",
    "mock": "mock",
    "langextract": "langextract",
}

LATEST_MODELS = {
    "claude": DEFAULT_CLAUDE_MODEL,
    "xai": DEFAULT_GROK_MODEL,
    "openai": DEFAULT_OPENAI_MODEL,
    "gemini": DEFAULT_GEMINI_MODEL,
    "langextract": DEFAULT_LANGEXTRACT_MODEL,
}

SYSTEM_PROMPT = """You are a grounded financial extraction engine.
Return ONLY valid JSON. Do not add markdown, commentary, or extra keys.

Schema:
{
  "items": [
    {
      "query": "the user query",
      "value": "short normalized fact (number + unit)",
      "quote": "EXACT contiguous substring copied from SOURCE",
      "start": 0,
      "end": 0,
      "confidence": 0.0
    }
  ]
}

Rules:
- quote MUST be copied character-for-character from SOURCE. Never paraphrase.
- start/end are 0-based character offsets into the SOURCE string you were given.
- end is exclusive (Python slice).
- If the fact is not in SOURCE, return {"items": []}.
- One item per distinct supporting quote. Prefer the most specific numeric sentence.
"""


def ollama_alive(url: str = DEFAULT_OLLAMA_URL, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(f"{url}/api/tags", timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def list_ollama_models(url: str = DEFAULT_OLLAMA_URL) -> list[str]:
    try:
        with urllib.request.urlopen(f"{url}/api/tags", timeout=3) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return [m.get("name", "") for m in payload.get("models", []) if m.get("name")]
    except Exception:  # noqa: BLE001
        return []


def pick_ollama_model(preferred: str | None = None) -> str:
    available = list_ollama_models()
    if preferred and (preferred in available or any(m.startswith(preferred) for m in available)):
        return preferred
    for name in RECOMMENDED_LOCAL:
        if name in available:
            return name
    return preferred or DEFAULT_OLLAMA_MODEL


def resolve_provider(explicit: str | None = None) -> str:
    name = (explicit or os.environ.get("EXTRACT_PROVIDER") or "auto").strip().lower()
    if name and name != "auto":
        return PROVIDER_ALIASES.get(name, name)
    if ollama_alive():
        return "ollama"
    return "mock"


def default_model_for(provider: str, explicit: str | None = None) -> str:
    """Return the caller model, EXTRACT_MODEL, or the current-generation default."""
    if explicit:
        return explicit
    canonical = PROVIDER_ALIASES.get(provider, provider)
    if canonical == "mock":
        return "mock"
    env = os.environ.get("EXTRACT_MODEL")
    if env:
        return env
    if canonical == "ollama":
        return pick_ollama_model(None)
    if canonical == "claude":
        return (
            os.environ.get("ANTHROPIC_MODEL")
            or os.environ.get("CLAUDE_MODEL")
            or DEFAULT_CLAUDE_MODEL
        )
    if canonical == "xai":
        return os.environ.get("XAI_MODEL") or DEFAULT_GROK_MODEL
    if canonical == "openai":
        return os.environ.get("OPENAI_MODEL") or DEFAULT_OPENAI_MODEL
    if canonical == "gemini":
        return os.environ.get("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL
    return LATEST_MODELS.get(canonical, DEFAULT_OLLAMA_MODEL)


def _extract_json(text: str) -> Any:
    text = text.strip()
    if not text:
        raise ValueError("empty model response")
    fence = re.search(r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\}|\[.*\])", text, re.S)
        if not match:
            raise
        return json.loads(match.group(1))


def parse_items(payload: Any, fallback_query: str) -> list[LLMExtraction]:
    if isinstance(payload, list):
        raw_items = payload
    elif isinstance(payload, dict):
        raw_items = payload.get("items") or payload.get("extractions") or [payload]
    else:
        return []
    out: list[LLMExtraction] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        item = LLMExtraction(
            query=str(raw.get("query") or fallback_query),
            value=str(raw.get("value") or raw.get("normalized_value") or ""),
            quote=str(raw.get("quote") or raw.get("extraction_text") or raw.get("text") or ""),
            start=raw.get("start") if raw.get("start") is not None else raw.get("start_pos"),
            end=raw.get("end") if raw.get("end") is not None else raw.get("end_pos"),
            confidence=float(raw.get("confidence") or 0.5),
        )
        if item.quote.strip():
            out.append(item)
    return out


def _user_prompt(source: str, query: str) -> str:
    return (
        f"QUERY: {query}\n\n"
        f"SOURCE (character length {len(source)}):\n"
        f"{source}\n"
    )


def _langchain_chat(provider: str, model: str):
    temperature = 0
    if provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=model,
            temperature=temperature,
            format="json",
            base_url=os.environ.get("OLLAMA_HOST", DEFAULT_OLLAMA_URL),
        )
    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=model or DEFAULT_GEMINI_MODEL,
            temperature=temperature,
            google_api_key=os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"),
        )
    if provider in {"claude", "anthropic"}:
        from langchain_anthropic import ChatAnthropic

        chat_kwargs = {
            "model": model or DEFAULT_CLAUDE_MODEL,
            "temperature": temperature,
            "anthropic_api_key": os.environ.get("ANTHROPIC_API_KEY"),
        }
        if os.environ.get("ANTHROPIC_BASE_URL"):
            chat_kwargs["anthropic_api_url"] = os.environ["ANTHROPIC_BASE_URL"]
        return ChatAnthropic(**chat_kwargs)
    if provider in {"openai", "xai", "grok"}:
        from langchain_openai import ChatOpenAI

        if provider in {"xai", "grok"}:
            return ChatOpenAI(
                model=model or DEFAULT_GROK_MODEL,
                temperature=temperature,
                api_key=os.environ.get("XAI_API_KEY"),
                base_url=os.environ.get("XAI_BASE_URL", "https://api.x.ai/v1"),
            )
        return ChatOpenAI(
            model=model or DEFAULT_OPENAI_MODEL,
            temperature=temperature,
            api_key=os.environ.get("OPENAI_API_KEY"),
            base_url=os.environ.get("OPENAI_BASE_URL") or None,
        )
    raise ValueError(f"unsupported langchain provider: {provider}")


def invoke_langchain(provider: str, model: str, source: str, query: str) -> list[LLMExtraction]:
    from langchain_core.messages import HumanMessage, SystemMessage

    chat = _langchain_chat(provider, model)
    resp = chat.invoke(
        [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=_user_prompt(source, query))]
    )
    content = resp.content if hasattr(resp, "content") else str(resp)
    if isinstance(content, list):
        content = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part) for part in content
        )
    return parse_items(_extract_json(str(content)), query)


def invoke_ollama_http(model: str, source: str, query: str) -> list[LLMExtraction]:
    url = os.environ.get("OLLAMA_HOST", DEFAULT_OLLAMA_URL).rstrip("/") + "/api/chat"
    body = {
        "model": model,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _user_prompt(source, query)},
        ],
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    content = payload.get("message", {}).get("content", "")
    return parse_items(_extract_json(content), query)


# Deterministic patterns for tests and offline demo (NVIDIA sample + generic 10-K phrasing).
MOCK_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("total revenue", re.compile(r"record revenue of \$[\d.,]+\s*billion", re.I)),
    ("total revenue", re.compile(r"total revenue (?:was|of) \$[\d.,]+\s*billion", re.I)),
    ("total revenue", re.compile(r"Revenue of \$[\d.,]+\s*billion", re.I)),
    ("gross profit margin", re.compile(r"GAAP gross (?:profit )?margin was [\d.]+\s*percent", re.I)),
    ("gross profit margin", re.compile(r"gross (?:profit )?margin of [\d.]+%", re.I)),
    ("year-over-year", re.compile(r"(?:increased|up) [\d.]+\s*percent from a year ago", re.I)),
    ("yoy", re.compile(r"up [\d.]+% year over year", re.I)),
    ("sequential", re.compile(r"(?:increased|up) [\d.]+\s*percent from the prior quarter", re.I)),
    ("data center", re.compile(r"Data Center revenue was \$[\d.,]+\s*billion", re.I)),
    ("diluted eps", re.compile(r"GAAP diluted earnings per share was \$[\d.]+(?!\d)", re.I)),
    ("eps", re.compile(r"diluted EPS of \$[\d.]+", re.I)),
    ("net income", re.compile(r"GAAP net income (?:was|of) \$[\d.,]+\s*billion", re.I)),
    ("full-year", re.compile(r"Full-year fiscal 2025 revenue was \$[\d.,]+\s*billion", re.I)),
    ("full year", re.compile(r"Full-year fiscal \d{4} revenue was \$[\d.,]+\s*billion", re.I)),
]


def _query_matches(query: str, label: str) -> bool:
    q = query.lower()
    label_l = label.lower()
    if label_l in q:
        return True
    aliases = {
        "yoy": ("yoy", "year-over-year", "year over year"),
        "eps": ("eps", "earnings per share", "diluted earnings per share"),
        "diluted eps": ("diluted eps", "diluted earnings per share", "earnings per share"),
        "full-year": ("full-year", "full year"),
        "full year": ("full-year", "full year"),
        "year-over-year": ("year-over-year", "year over year", "yoy"),
        "sequential": ("sequential", "prior quarter", "qoq"),
        "data center": ("data center", "datacenter"),
        "gross profit margin": ("gross profit margin", "gross margin"),
        "total revenue": ("total revenue", "record revenue"),
        "net income": ("net income",),
    }
    if label_l in aliases:
        return any(alias in q for alias in aliases[label_l])
    tokens = [t for t in re.split(r"[^a-z0-9]+", label_l) if t and t not in {"of", "the", "a"}]
    # Require every distinctive token; "revenue" alone is not enough.
    distinctive = [t for t in tokens if t not in {"revenue", "gaap"}]
    if distinctive:
        return all(t in q for t in distinctive)
    return bool(tokens) and all(t in q for t in tokens)


def invoke_mock(source: str, query: str) -> list[LLMExtraction]:
    items: list[LLMExtraction] = []
    q = query.lower()
    for label, pattern in MOCK_PATTERNS:
        if not _query_matches(q, label):
            continue
        match = pattern.search(source)
        if not match:
            continue
        quote = match.group(0).rstrip(".,;:")
        # Prefer currency or percent over incidental numbers (e.g. fiscal year).
        num = (
            re.search(r"\$[\d.,]+\s*(?:billion|million)?", quote, re.I)
            or re.search(r"[\d.]+\s*(?:percent|%)", quote, re.I)
            or re.search(r"\$?[\d.,]+", quote, re.I)
        )
        items.append(
            LLMExtraction(
                query=query,
                value=(num.group(0).strip() if num else quote),
                quote=quote,
                start=match.start(),
                end=match.end(),
                confidence=0.99,
            )
        )
        break
    return items


def invoke_model(
    provider: str,
    model: str,
    source: str,
    query: str,
    *,
    prefer_langchain: bool = True,
) -> list[LLMExtraction]:
    if provider == "mock":
        return invoke_mock(source, query)
    if prefer_langchain:
        try:
            return invoke_langchain(provider, model, source, query)
        except ImportError:
            if provider != "ollama":
                raise
        except Exception:
            if provider != "ollama":
                raise
    if provider == "ollama":
        return invoke_ollama_http(model, source, query)
    raise RuntimeError(f"provider {provider} requires LangChain extras")
