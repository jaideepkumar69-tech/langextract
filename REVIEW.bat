@echo off
setlocal EnableExtensions
title LangExtract review
cd /d "%~dp0"
set "PY=%~dp0pipeline\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=C:\Python314\python.exe"
if not exist "%~dp0pipeline\outputs\annotations.json" (
  echo No annotations yet — running mock pipeline first...
  "%PY%" "%~dp0pipeline\main.py" --provider mock
  if errorlevel 1 exit /b 1
)
echo Opening review dashboard at http://127.0.0.1:8788/
"%PY%" "%~dp0pipeline\visualizer.py" --port 8788
exit /b %ERRORLEVEL%
