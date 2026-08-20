"""Review dashboard: highlight exact character spans and export JSON (Prompt 4)."""

from __future__ import annotations

import argparse
import json
import sys
import threading
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from pipeline.models import ExtractionItem, ExtractionReport, LLMExtraction  # noqa: E402
from pipeline.report import write_annotations, write_clean_json, write_markdown  # noqa: E402
from pipeline.validator import validate_extraction  # noqa: E402

DEFAULT_ANN = ROOT / "outputs" / "annotations.json"
DEFAULT_PORT = 8788

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>LangExtract review</title>
<style>
  :root {
    --bg:#0f1419; --panel:#1a222c; --ink:#e7ecf3; --muted:#8b98a5;
    --line:#2b3642; --ok:#3dd68c; --warn:#f5c451; --bad:#ff6b6b;
    --accent:#6aa7ff; --chip:#243040;
  }
  * { box-sizing:border-box; }
  html,body { margin:0; height:100%; background:var(--bg); color:var(--ink);
    font:14px/1.45 "Segoe UI", system-ui, sans-serif; }
  header { display:flex; gap:16px; align-items:center; justify-content:space-between;
    padding:12px 18px; border-bottom:1px solid var(--line); background:#121922; }
  header h1 { font-size:16px; margin:0; font-weight:600; }
  header .meta { color:var(--muted); font-size:12px; }
  .actions { display:flex; gap:8px; flex-wrap:wrap; }
  button, .btn { background:var(--accent); color:#071018; border:0; border-radius:8px;
    padding:7px 12px; font-weight:600; cursor:pointer; text-decoration:none; }
  button.secondary { background:var(--chip); color:var(--ink); }
  button.danger { background:#5a2430; color:#ffd6dc; }
  main { display:grid; grid-template-columns: 1.4fr 1fr; height:calc(100% - 58px); }
  #source, #side { overflow:auto; padding:18px; }
  #source { border-right:1px solid var(--line); white-space:pre-wrap;
    font-family:Consolas, "Cascadia Mono", ui-monospace, monospace; font-size:13px; }
  .mark { border-radius:3px; padding:0 2px; cursor:pointer; }
  .mark.grounded { background:#1f4d38; outline:1px solid #3dd68c55; }
  .mark.remapped { background:#4a3b12; outline:1px solid #f5c45155; }
  .mark.blocked { background:#4a1d24; outline:1px dashed #ff6b6b88; }
  .mark.active { outline:2px solid #fff; }
  .card { background:var(--panel); border:1px solid var(--line); border-radius:10px;
    padding:12px; margin-bottom:10px; }
  .card h3 { margin:0 0 6px; font-size:14px; }
  .badge { font-size:11px; font-weight:700; padding:2px 6px; border-radius:999px; }
  .badge.grounded { background:#1f4d38; color:var(--ok); }
  .badge.remapped { background:#4a3b12; color:var(--warn); }
  .badge.blocked { background:#4a1d24; color:var(--bad); }
  .row { color:var(--muted); font-size:12px; margin:3px 0; }
  textarea, input[type=text] { width:100%; background:#0f1419; color:var(--ink);
    border:1px solid var(--line); border-radius:6px; padding:6px; font:12px/1.4 inherit; }
  .stats { display:flex; gap:12px; color:var(--muted); font-size:12px; }
  @media (max-width: 900px) { main { grid-template-columns:1fr; } }
</style>
</head>
<body>
<header>
  <div>
    <h1>LangExtract review</h1>
    <div class="meta" id="meta">Loading…</div>
    <div class="stats" id="stats"></div>
  </div>
  <div class="actions">
    <button class="secondary" onclick="reload()">Reload</button>
    <a class="btn" href="/api/export" download="annotations.clean.json">Export JSON</a>
    <button class="secondary" onclick="save()">Save review</button>
  </div>
</header>
<main>
  <article id="source"></article>
  <aside id="side"></aside>
</main>
<script>
let REPORT = null;
let ACTIVE = null;

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
  }[c]));
}

async function reload() {
  const r = await fetch("/api/report");
  REPORT = await r.json();
  render();
}

function items() { return REPORT?.extractions || []; }

function renderSource() {
  const text = REPORT.document.text || "";
  const spans = items()
    .filter(it => it.start != null && it.end != null && it.end > it.start)
    .sort((a,b) => a.start - b.start || b.end - a.end);
  let html = "";
  let cursor = 0;
  for (const it of spans) {
    const start = Math.max(it.start, cursor);
    const end = Math.max(start, it.end);
    if (start > cursor) html += esc(text.slice(cursor, start));
    if (end > start) {
      const cls = "mark " + (it.status || "blocked") + (ACTIVE === it.id ? " active" : "");
      html += `<span class="${cls}" data-id="${esc(it.id)}" title="${esc(it.query)}">${esc(text.slice(start, end))}</span>`;
    }
    cursor = Math.max(cursor, end);
  }
  if (cursor < text.length) html += esc(text.slice(cursor));
  document.getElementById("source").innerHTML = html || "<em>No source text in annotations.json</em>";
  document.getElementById("source").querySelectorAll(".mark").forEach(el => {
    el.addEventListener("click", () => focusItem(el.dataset.id));
  });
}

function renderSide() {
  const side = document.getElementById("side");
  side.innerHTML = items().map(it => `
    <section class="card" id="card-${esc(it.id)}">
      <h3>${esc(it.query)} <span class="badge ${esc(it.status)}">${esc(it.status)}</span></h3>
      <div class="row">value: <strong>${esc(it.value)}</strong></div>
      <div class="row">span: ${it.start ?? "—"}–${it.end ?? "—"} · pass ${it.pass_index} · ${it.latency_ms} ms</div>
      <div class="row">review: ${esc(it.review)} · ${esc(it.reason)}</div>
      <label class="row">quote</label>
      <textarea id="quote-${esc(it.id)}" rows="3">${esc(it.quote)}</textarea>
      <label class="row">value</label>
      <input id="value-${esc(it.id)}" type="text" value="${esc(it.value)}"/>
      <label class="row">notes</label>
      <input id="notes-${esc(it.id)}" type="text" value="${esc(it.notes)}"/>
      <div class="actions" style="margin-top:8px">
        <button onclick="review('${it.id}','accepted')">Accept</button>
        <button class="danger" onclick="review('${it.id}','rejected')">Reject</button>
        <button class="secondary" onclick="fixItem('${it.id}')">Fix + revalidate</button>
      </div>
    </section>
  `).join("") || "<p>No extractions.</p>";
}

function render() {
  const d = REPORT.document || {};
  const m = REPORT.model || {};
  const met = REPORT.metrics || {};
  document.getElementById("meta").textContent =
    `${d.name || ""} · ${m.provider || ""}/${m.model || ""} · ${d.char_count || 0} chars`;
  document.getElementById("stats").innerHTML =
    `<span>latency ${met.total_latency_ms ?? "—"} ms</span>
     <span>grounded ${met.grounded ?? 0}</span>
     <span>blocked ${met.blocked ?? 0}</span>`;
  renderSource();
  renderSide();
}

function focusItem(id) {
  ACTIVE = id;
  renderSource();
  const card = document.getElementById("card-" + id);
  if (card) card.scrollIntoView({behavior:"smooth", block:"nearest"});
}

async function review(id, state) {
  const notes = document.getElementById("notes-" + id)?.value || "";
  await fetch("/api/review", {
    method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({id, state, notes})
  });
  await reload();
}

async function fixItem(id) {
  const quote = document.getElementById("quote-" + id)?.value || "";
  const value = document.getElementById("value-" + id)?.value || "";
  const notes = document.getElementById("notes-" + id)?.value || "";
  await fetch("/api/fix", {
    method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({id, quote, value, notes})
  });
  await reload();
}

async function save() {
  const r = await fetch("/api/save", {method:"POST"});
  const data = await r.json();
  alert(data.ok ? "Saved " + data.annotations : (data.error || "save failed"));
}

reload();
</script>
</body>
</html>
"""


class ReviewState:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.report = self._load(path)

    def _load(self, path: Path) -> ExtractionReport:
        if not path.is_file():
            raise FileNotFoundError(
                f"annotations not found: {path}. Run pipeline/main.py first."
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        return ExtractionReport.model_validate(data)

    def reload(self) -> None:
        self.report = self._load(self.path)

    def find(self, item_id: str) -> ExtractionItem:
        for item in self.report.extractions:
            if item.id == item_id:
                return item
        raise KeyError(item_id)

    def persist(self) -> dict:
        write_annotations(self.report, self.path)
        out_dir = self.path.parent
        md = write_markdown(self.report, out_dir / "outputs.md")
        clean = write_clean_json(self.report, out_dir / "annotations.clean.json")
        return {
            "ok": True,
            "annotations": str(self.path),
            "markdown": str(md),
            "clean": str(clean),
        }


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, state: ReviewState, *args, **kwargs) -> None:
        self.state = state
        super().__init__(*args, **kwargs)

    def log_message(self, fmt: str, *args) -> None:  # quieter
        if args and str(args[0]).startswith("GET /api/report"):
            return
        super().log_message(fmt, *args)

    def _json(self, payload: object, code: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8") or "{}")

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in {"/", "/index.html"}:
            body = HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/report":
            self._json(self.state.report.model_dump())
            return
        if path == "/api/export":
            rows = [i.model_dump() for i in self.state.report.accepted_or_grounded()]
            payload = {
                "document": self.state.report.document.name,
                "sha256": self.state.report.document.sha256,
                "extractions": [
                    {
                        "id": r["id"],
                        "query": r["query"],
                        "value": r["value"],
                        "quote": r["quote"],
                        "start": r["start"],
                        "end": r["end"],
                        "status": r["status"],
                        "review": r["review"],
                    }
                    for r in rows
                ],
            }
            self._json(payload)
            return
        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            if path == "/api/review":
                data = self._read_json()
                item = self.state.find(data["id"])
                item.review = data.get("state") or "pending"
                item.notes = data.get("notes") or item.notes
                self._json({"ok": True, "item": item.model_dump()})
                return
            if path == "/api/fix":
                data = self._read_json()
                item = self.state.find(data["id"])
                raw = LLMExtraction(
                    query=item.query,
                    value=data.get("value") or item.value,
                    quote=data.get("quote") or item.quote,
                    start=None,
                    end=None,
                    confidence=item.confidence or 0.7,
                )
                fixed = validate_extraction(self.state.report.document.text, raw)
                item.value = fixed.value
                item.quote = fixed.quote
                item.start = fixed.start
                item.end = fixed.end
                item.status = fixed.status
                item.reason = fixed.reason
                item.review = "fixed" if fixed.grounded else "pending"
                item.notes = data.get("notes") or item.notes
                self._json({"ok": True, "item": item.model_dump()})
                return
            if path == "/api/save":
                self._json(self.state.persist())
                return
        except Exception as exc:  # noqa: BLE001
            self._json({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, 400)
            return
        self.send_error(404)


def serve(annotations: Path, host: str, port: int, open_browser: bool) -> None:
    state = ReviewState(annotations)
    handler = partial(Handler, state)
    httpd = ThreadingHTTPServer((host, port), handler)
    url = f"http://{host}:{port}/"
    print(f"Review UI: {url}")
    print(f"Annotations: {annotations}")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped review UI.")
    finally:
        httpd.server_close()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Highlight grounded spans for human review")
    p.add_argument("--annotations", default=str(DEFAULT_ANN))
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--no-browser", action="store_true")
    return p.parse_args(argv)


def main() -> int:
    args = parse_args()
    serve(Path(args.annotations), args.host, args.port, open_browser=not args.no_browser)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
