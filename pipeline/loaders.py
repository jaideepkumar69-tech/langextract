"""Load PDF or plain-text documents into a single character stream."""

from __future__ import annotations

import hashlib
from pathlib import Path

from pipeline.models import DocumentMeta


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_text_file(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def load_pdf_pypdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages: list[str] = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n\n".join(pages)


def load_pdf_pymupdf(path: Path) -> str:
    import fitz  # PyMuPDF

    doc = fitz.open(str(path))
    try:
        return "\n\n".join(page.get_text("text") for page in doc)
    finally:
        doc.close()


def load_pdf(path: Path) -> tuple[str, str]:
    """Return (text, loader_name). Prefer PyMuPDF, fall back to pypdf."""
    errors: list[str] = []
    try:
        text = load_pdf_pymupdf(path)
        if text.strip():
            return text, "pymupdf"
        errors.append("pymupdf returned empty text")
    except Exception as exc:  # noqa: BLE001 — try next loader
        errors.append(f"pymupdf: {exc}")
    try:
        text = load_pdf_pypdf(path)
        if text.strip():
            return text, "pypdf"
        errors.append("pypdf returned empty text")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"pypdf: {exc}")
    raise RuntimeError("PDF text extraction failed: " + "; ".join(errors))


def load_document(path: str | Path) -> DocumentMeta:
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    suffix = path.suffix.lower()
    raw = path.read_bytes()
    digest = _sha256_bytes(raw)
    if suffix == ".pdf":
        text, loader = load_pdf(path)
    else:
        text = load_text_file(path)
        loader = "text"
    # Normalize newlines so offsets are stable across Windows/Unix.
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return DocumentMeta(
        path=str(path),
        name=path.name,
        sha256=digest,
        char_count=len(text),
        text=text,
        loader=loader,
    )


def write_sample_pdf(text: str, dest: Path) -> Path:
    """Write a simple multi-page PDF so PDF loaders can be tested."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("pymupdf is required to write the sample PDF") from exc

    doc = fitz.open()
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    page = doc.new_page()
    y = 72
    fontsize = 10
    for para in paragraphs:
        block = para + "\n"
        # Simple wrap
        words = block.split()
        line = ""
        lines: list[str] = []
        for word in words:
            trial = f"{line} {word}".strip()
            if len(trial) > 95:
                lines.append(line)
                line = word
            else:
                line = trial
        if line:
            lines.append(line)
        for line_text in lines:
            if y > 740:
                page = doc.new_page()
                y = 72
            page.insert_text((72, y), line_text, fontsize=fontsize, fontname="helv")
            y += 14
        y += 8
    dest.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(dest))
    doc.close()
    return dest
