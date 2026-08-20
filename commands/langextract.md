---
description: Run grounded LangExtract / LangChain extraction and open the review UI
---

Run the grounded document extraction pipeline at `C:\Users\USER\projects\langextract`.

## Do this now

1. Load `~/.claude/skills/langextract/SKILL.md` or `~/.grok/skills/langextract/SKILL.md`.
2. If the `langextract` MCP server is connected, call `stack_status` then `extract_run` or `graph_run` (provider `mock` unless the user asked for Ollama/Claude/Grok/Gemini/OpenAI). Live defaults: `claude` → `claude-sonnet-5`, `xai` → `grok-4.6`. Then `extract_validate` and `extract_review`. Use `smith_status` / `flow_status` when the user mentions LangSmith or LangFlow.
3. Otherwise:

```powershell
C:\Users\USER\projects\langextract\pipeline\.venv\Scripts\python.exe C:\Users\USER\projects\langextract\scripts\langextract_pipeline.py run --provider mock
```

4. Report grounded vs blocked counts, latency, and the paths of `outputs.md` / `annotations.json`. Do not invent figures. Only quote spans that match the source.
