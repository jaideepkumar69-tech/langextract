"""Pydantic schemas for grounded extractions and the review report."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


ProviderName = Literal["auto", "ollama", "gemini", "openai", "xai", "mock", "langextract"]
ReviewState = Literal["pending", "accepted", "rejected", "fixed"]
GroundingStatus = Literal["grounded", "remapped", "blocked"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid4().hex[:12]


class CharSpan(BaseModel):
    start: int
    end: int

    @field_validator("start", "end")
    @classmethod
    def _non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("character offsets must be >= 0")
        return value


class ExtractionItem(BaseModel):
    id: str = Field(default_factory=new_id)
    query: str
    value: str = ""
    quote: str = ""
    start: int | None = None
    end: int | None = None
    confidence: float = 0.0
    status: GroundingStatus = "blocked"
    pass_index: int = 0
    chunk_id: int = 0
    latency_ms: float = 0.0
    reason: str = ""
    review: ReviewState = "pending"
    notes: str = ""

    @property
    def grounded(self) -> bool:
        return self.status in {"grounded", "remapped"} and self.start is not None


class QueryResult(BaseModel):
    query: str
    latency_ms: float = 0.0
    items: list[ExtractionItem] = Field(default_factory=list)
    grounded_count: int = 0
    blocked_count: int = 0


class DocumentMeta(BaseModel):
    path: str
    name: str
    sha256: str = ""
    char_count: int = 0
    text: str = ""
    loader: str = "text"


class ModelMeta(BaseModel):
    provider: str
    model: str
    engine: str = "langchain"
    ollama_url: str = "http://127.0.0.1:11434"


class ExtractionReport(BaseModel):
    generated_at: str = Field(default_factory=utc_now)
    document: DocumentMeta
    model: ModelMeta
    queries: list[str]
    passes: int = 1
    chunk_size: int = 4000
    chunk_overlap: int = 400
    metrics: dict[str, Any] = Field(default_factory=dict)
    results: list[QueryResult] = Field(default_factory=list)
    extractions: list[ExtractionItem] = Field(default_factory=list)

    def accepted_or_grounded(self) -> list[ExtractionItem]:
        out: list[ExtractionItem] = []
        for item in self.extractions:
            if item.review == "rejected":
                continue
            if item.review in {"accepted", "fixed"} or item.grounded:
                out.append(item)
        return out


class LLMExtraction(BaseModel):
    """Raw model payload before grounding."""

    query: str = ""
    value: str = ""
    quote: str = ""
    start: int | None = None
    end: int | None = None
    confidence: float = 0.5
