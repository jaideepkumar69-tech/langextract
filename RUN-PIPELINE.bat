@echo off
setlocal EnableExtensions
title LangExtract pipeline
cd /d "%~dp0"
set "PY=%~dp0pipeline\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo Pipeline venv missing. Running setup...
  C:\Python314\python.exe "%~dp0pipeline\setup_env.py"
  if errorlevel 1 exit /b 1
)
"%PY%" "%~dp0pipeline\main.py" --provider mock %*
echo.
echo Review UI: RUN  REVIEW.bat   or open http://127.0.0.1:8788/ after starting visualizer
exit /b %ERRORLEVEL%
