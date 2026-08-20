# langextract

Use the langextract skill (`~/.grok/skills/langextract/SKILL.md`) when the user asks for LangExtract, LangChain extraction, character offsets, or the review dashboard.

- Demo root: this directory
- MCP server name: `langextract`
- CLI: `pipeline\.venv\Scripts\python.exe scripts\langextract_pipeline.py run --provider mock`
- Merged stack: `pipeline\.venv\Scripts\python.exe scripts\langextract_pipeline.py stack`
- LangGraph: `pipeline\.venv\Scripts\python.exe scripts\langextract_pipeline.py graph --provider mock`
- Review: `pipeline\.venv\Scripts\python.exe pipeline\visualizer.py`
- MCP tools also: `stack_status`, `graph_run`, `smith_status`, `flow_status`

Do not invent extracted values. Read `pipeline/outputs/annotations.json` and only keep grounded/remapped spans.
