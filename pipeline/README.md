# Grounded extraction pipeline

LangChain + Ollama (Claude 5 / Grok 4.6 / Gemini / OpenAI / Google LangExtract optional) on top of the local Google LangExtract checkout.

Current-generation defaults:

| Provider | Flag | Default model | Env key |
|---|---|---|---|
| Claude | `--provider claude` | `claude-sonnet-5` | `ANTHROPIC_API_KEY` |
| Grok | `--provider xai` | `grok-4.6` | `XAI_API_KEY` |
| Gemini | `--provider gemini` | `gemini-2.5-flash` | `GEMINI_API_KEY` |
| OpenAI | `--provider openai` | `gpt-4o-mini` | `OPENAI_API_KEY` |

Claude aliases: `claude`, `anthropic`. Grok aliases: `xai`, `grok`. Other Claude IDs: `claude-opus-5`, `claude-fable-5`, `claude-haiku-4-5`.

## Setup

```powershell
powershell -File pipeline\setup_env.ps1
```

Creates `pipeline\.venv` (prefers Python 3.12) and installs LangChain, pypdf, pymupdf, pydantic, and this repo editable.

### Ollama

```text
ollama serve
ollama pull gemma2:2b          # already used by examples/ollama
ollama pull qwen2.5:32b        # better quality if you have VRAM
```

Then:

```powershell
pipeline\.venv\Scripts\python.exe pipeline\main.py --provider ollama --model gemma2:2b
```

## Run

```powershell
# Offline (no GPU / no API key)
pipeline\.venv\Scripts\python.exe pipeline\main.py --provider mock

# Claude 5 (Sonnet default; pass --model claude-opus-5 for flagship)
pipeline\.venv\Scripts\python.exe pipeline\main.py --provider claude --model claude-sonnet-5

# Grok 4.6
pipeline\.venv\Scripts\python.exe pipeline\main.py --provider xai --model grok-4.6

# Review highlighted spans
pipeline\.venv\Scripts\python.exe pipeline\visualizer.py
```

Outputs:

- `pipeline/outputs/outputs.md`
- `pipeline/outputs/annotations.json`
- `pipeline/outputs/annotations.clean.json`

## Tests

```powershell
pipeline\.venv\Scripts\python.exe -m pytest pipeline\tests -q
pipeline\.venv\Scripts\python.exe scripts\smoke.py
```
