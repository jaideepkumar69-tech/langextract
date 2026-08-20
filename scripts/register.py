"""Register langextract with Claude Desktop, Claude CLI, and Grok Build CLI."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

NAME = "langextract"
PROJECT = Path(r"C:\Users\USER\projects\langextract")
SERVER = PROJECT / "mcp" / "server.py"
HOME = Path.home()
VENV_PY = PROJECT / "pipeline" / ".venv" / "Scripts" / "python.exe"
PY = VENV_PY if VENV_PY.is_file() else Path(r"C:\Python314\python.exe")

STDIO = {"command": str(PY), "args": [str(SERVER)]}
CLAUDE_CLI = {"type": "stdio", "command": str(PY), "args": [str(SERVER)], "env": {}}
GROK_BLOCK = f"""
[mcp_servers.{NAME}]
command = '{PY}'
args = ['{SERVER}']
enabled = true
startup_timeout_sec = 60
tool_timeout_sec = 600
"""


def backup(path: Path) -> None:
    if path.is_file():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copy2(path, path.with_suffix(path.suffix + f".bak-{stamp}"))


def patch_json_mcp(path: Path, entry: dict, *, key: str = "mcpServers") -> None:
    if not path.is_file():
        print(f"skip missing {path}")
        return
    backup(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    servers = data.setdefault(key, {})
    servers[NAME] = entry
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"updated {path}")


def patch_grok(path: Path) -> None:
    if not path.is_file():
        print(f"skip missing {path}")
        return
    text = path.read_text(encoding="utf-8")
    marker = f"[mcp_servers.{NAME}]"
    if marker in text:
        print(f"already present {path}")
        return
    backup(path)
    path.write_text(text.rstrip() + "\n" + GROK_BLOCK, encoding="utf-8")
    print(f"updated {path}")


def install_skills() -> None:
    skill_src = PROJECT / "skills" / "SKILL.md"
    cmd_src = PROJECT / "commands" / "langextract.md"
    targets = [
        (HOME / ".claude" / "skills" / NAME, skill_src, "SKILL.md"),
        (HOME / ".grok" / "skills" / NAME, skill_src, "SKILL.md"),
        (HOME / ".claude" / "commands", cmd_src, "langextract.md"),
        (HOME / ".grok" / "commands", cmd_src, "langextract.md"),
    ]
    for dest_dir, src, name in targets:
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / name
        shutil.copy2(src, dest)
        print(f"copied {dest}")


def patch_user_claude_md() -> None:
    path = HOME / ".claude" / "CLAUDE.md"
    marker = "# langextract"
    block = (
        "\n# langextract\n"
        "- **langextract** (`~/.claude/skills/langextract/SKILL.md`) — grounded LangChain/LangExtract pipeline.\n"
        "  Trigger: `/langextract`. Project: `C:\\Users\\USER\\projects\\langextract`.\n"
        "  Prefer MCP tools `stack_status` / `extract_run` / `graph_run` / `extract_review` when connected.\n"
    )
    if not path.is_file():
        path.write_text(block.lstrip(), encoding="utf-8")
        print(f"wrote {path}")
        return
    text = path.read_text(encoding="utf-8")
    if marker in text:
        print(f"already present {path}")
        return
    backup(path)
    path.write_text(text.rstrip() + "\n" + block, encoding="utf-8")
    print(f"updated {path}")


def copy_desktop_packs() -> None:
    dest_root = Path(r"C:\Users\USER\Desktop\Projects\LangExtract-for-AI")
    mapping = {
        PROJECT / "packs" / "grok-web" / "HOW-TO-CONNECT.md": dest_root / "Grok-Web" / "README.md",
        PROJECT / "packs" / "grok-desktop" / "README.md": dest_root / "Grok-Desktop" / "README.md",
    }
    for src, dest in mapping.items():
        if not src.is_file():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        print(f"copied {dest}")


def main() -> None:
    if not SERVER.is_file():
        raise SystemExit(f"missing {SERVER}")
    patch_json_mcp(Path(r"C:\Users\USER\AppData\Roaming\Claude\claude_desktop_config.json"), STDIO)
    patch_json_mcp(HOME / ".claude.json", CLAUDE_CLI)
    patch_grok(HOME / ".grok" / "config.toml")
    (PROJECT / ".mcp.json").write_text(
        json.dumps({"mcpServers": {NAME: {**STDIO}}}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {PROJECT / '.mcp.json'}")
    install_skills()
    patch_user_claude_md()
    copy_desktop_packs()


if __name__ == "__main__":
    main()
