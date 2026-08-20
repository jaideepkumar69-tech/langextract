---
name: langextract
description: >
  Grounded document extraction with Google LangExtract + LangChain +
  LangGraph + LangSmith + LangFlow (Ollama, Claude 5, Grok 4.6, Gemini, OpenAI). Use when
  the user mentions LangExtract, LangChain extract, LangGraph, LangSmith,
  LangFlow, character offsets, annotations.json, financial PDF extraction,
  hallucination-blocked quotes, /langextract, or the review dashboard.
  Works in Claude CLI, Claude Desktop, and Grok Build CLI.
---

# LangExtract grounded pipeline

Project: `C:\Users\USER\projects\langextract`

Prefer MCP tools on the `langextract` server when it is connected. Otherwise run the CLI helper. Do not start Docker. Do not invent financial figures — only report spans that validate against the source.

**grok.com / Grok Desktop:** those clients cannot use stdio. Start `CONNECT-GROK-WEB.bat` (HTTP + Cloudflare tunnel) and add the `https://…/mcp` URL at https://grok.com/connectors → Custom. Same connector then works in Grok Desktop.

## Do this now

1. Status (Ollama, last report, review URL):

```powershell
C:\Users\USER\projects\langextract\pipeline\.venv\Scripts\python.exe C:\Users\USER\projects\langextract\scripts\langextract_pipeline.py status
```

2. Run multi-pass extraction (offline mock is the default for a reliable test):

```powershell
C:\Users\USER\projects\langextract\pipeline\.venv\Scripts\python.exe C:\Users\USER\projects\langextract\scripts\langextract_pipeline.py run --provider mock
```

Live Ollama (if `ollama list` shows a model):

```powershell
C:\Users\USER\projects\langextract\pipeline\.venv\Scripts\python.exe C:\Users\USER\projects\langextract\scripts\langextract_pipeline.py run --provider ollama --model gemma2:2b
```

3. Validate every quote against the source:

```powershell
C:\Users\USER\projects\langextract\pipeline\.venv\Scripts\python.exe C:\Users\USER\projects\langextract\scripts\langextract_pipeline.py validate
```

4. Open the review UI (highlights exact character spans):

```powershell
C:\Users\USER\projects\langextract\pipeline\.venv\Scripts\python.exe C:\Users\USER\projects\langextract\scripts\langextract_pipeline.py review
```

Then open http://127.0.0.1:8788/

MCP equivalents: `extract_status`, `extract_run`, `extract_validate`, `extract_review`, `extract_demo_path`, `extract_queries`, `stack_status`, `graph_run`, `smith_status`, `flow_status`, `flow_start`, `flow_stop`.

Merged stack (one MCP for Claude + Grok):

```powershell
C:\Users\USER\projects\langextract\pipeline\.venv\Scripts\python.exe C:\Users\USER\projects\langextract\scripts\langextract_pipeline.py stack
C:\Users\USER\projects\langextract\pipeline\.venv\Scripts\python.exe C:\Users\USER\projects\langextract\scripts\langextract_pipeline.py graph --provider mock
```

## Outputs

- `pipeline\outputs\outputs.md`
- `pipeline\outputs\annotations.json` (full text + spans, for the review UI)
- `pipeline\outputs\annotations.clean.json` (database-ready rows)

## Rules

- A fact is only valid when `source[start:end] == quote`. Status `blocked` means paraphrase/hallucination — do not present it as extracted data.
- Default sample: `pipeline\samples\nvidia_q4_fy2025.txt`.
- Providers: `mock` (offline), `ollama` (local), `claude` (`claude-sonnet-5` / `claude-opus-5`), `xai` (`grok-4.6`), `gemini`, `openai`, `langextract`.
- Recommended local models: `qwen2.5:32b` if VRAM allows, else `gemma2:2b` (already pulled on this machine).
