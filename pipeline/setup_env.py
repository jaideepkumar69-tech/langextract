"""Create a dedicated venv and install pipeline + LangExtract dependencies.

Prefers Python 3.12 for LangChain wheels; falls back to the current interpreter.
Also prints Ollama instructions for local models (qwen2.5:32b or gemma2:2b).
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
REQ = ROOT / "requirements.txt"
VENV = ROOT / ".venv"


def find_python() -> str:
    if os.environ.get("PIPELINE_PYTHON"):
        return os.environ["PIPELINE_PYTHON"]
    # Prefer a real 3.12 if present (LangChain is happiest there).
    for cmd in (
        ["py", "-3.12", "-c", "import sys; print(sys.executable)"],
        [
            r"C:\Users\USER\AppData\Local\Programs\Python\Python312\python.exe",
            "-c",
            "import sys; print(sys.executable)",
        ],
    ):
        try:
            if cmd[0] != "py" and not Path(cmd[0]).is_file():
                continue
            out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
            if out and Path(out).is_file():
                return out
        except (OSError, subprocess.CalledProcessError):
            continue
    return sys.executable


def run(cmd: list[str]) -> None:
    print(">", " ".join(cmd))
    subprocess.check_call(cmd)


def venv_python() -> Path:
    if os.name == "nt":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recreate", action="store_true")
    args = parser.parse_args()

    py = find_python()
    print(f"Using interpreter: {py}")
    if args.recreate and VENV.exists():
        shutil.rmtree(VENV)
    if not venv_python().is_file():
        run([py, "-m", "venv", str(VENV)])
    pip = [str(venv_python()), "-m", "pip"]
    run(pip + ["install", "--upgrade", "pip"])
    run(pip + ["install", "-r", str(REQ)])
    run(pip + ["install", "-e", str(PROJECT) + "[all]"])
    run(pip + ["install", "mcp>=1.12.0,<2", "pytest>=7.4.0"])

    flow = ROOT / ".venv-langflow"
    flow_py = flow / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not flow_py.is_file():
        run([py, "-m", "venv", str(flow)])
    print()
    print("LangFlow sidecar (optional, isolated so it cannot pin-break LangChain):")
    print(f"  {flow_py} -m pip install langflow")
    print(f"  {flow_py} -m langflow run --host 127.0.0.1 --port 7860")

    print()
    print("Environment ready.")
    print(f"  {venv_python()} --version")
    print()
    print("Local models via Ollama")
    print("  1. Install: https://ollama.com/download")
    print("  2. ollama serve          (if the app is not already running)")
    print("  3. ollama pull gemma2:2b           # small, already used by LangExtract demo")
    print("  4. ollama pull qwen2.5:32b         # recommended quality if you have VRAM")
    print("  5. ollama pull qwen2.5-coder:7b    # mid-size alternative")
    print()
    print("Run (offline demo, no GPU needed):")
    print(f'  {venv_python()} {ROOT / "main.py"} --provider mock')
    print("Run (local Ollama):")
    print(f'  {venv_python()} {ROOT / "main.py"} --provider ollama --model gemma2:2b')
    print("Review UI:")
    print(f'  {venv_python()} {ROOT / "visualizer.py"}')
    print()
    print("Cloud providers (optional, current-generation defaults):")
    print("  set ANTHROPIC_API_KEY=...  then --provider claude --model claude-sonnet-5")
    print("  set XAI_API_KEY=...        then --provider xai --model grok-4.6")
    print("  set GEMINI_API_KEY=...     then --provider gemini --model gemini-2.5-flash")
    print("  set OPENAI_API_KEY=...     then --provider openai --model gpt-4o-mini")
    print("  Claude flagship: --model claude-opus-5   frontier: --model claude-fable-5")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
