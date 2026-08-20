@echo off
setlocal EnableExtensions
title LangExtract
cd /d "%~dp0"

set "ROOT=%CD%"
set "VENV_PY=%ROOT%\.venv\Scripts\python.exe"
set "MODE=%~1"
if "%MODE%"=="" set "MODE=shell"

echo.
echo  LangExtract - local starter
echo  Project: %ROOT%
echo.

if not exist "%VENV_PY%" (
  echo Creating virtual environment...
  py -3 -m venv .venv 2>nul || python -m venv .venv
  if errorlevel 1 (
    echo [ERROR] Failed to create .venv. Install Python 3.10+ and retry.
    if /i not "%MODE%"=="check" if not defined LANGEXTRACT_NONINTERACTIVE pause
    exit /b 1
  )
  echo Installing langextract into .venv...
  "%VENV_PY%" -m pip install --upgrade pip
  if errorlevel 1 (
    echo [ERROR] pip upgrade failed.
    if /i not "%MODE%"=="check" if not defined LANGEXTRACT_NONINTERACTIVE pause
    exit /b 1
  )
  "%VENV_PY%" -m pip install -e ".[test]"
  if errorlevel 1 (
    echo [ERROR] Failed to install langextract.
    if /i not "%MODE%"=="check" if not defined LANGEXTRACT_NONINTERACTIVE pause
    exit /b 1
  )
)

"%VENV_PY%" -c "import langextract" 1>nul 2>nul
if errorlevel 1 (
  echo Installing langextract into existing .venv...
  "%VENV_PY%" -m pip install -e ".[test]"
  if errorlevel 1 (
    echo [ERROR] langextract is not importable and install failed.
    if /i not "%MODE%"=="check" if not defined LANGEXTRACT_NONINTERACTIVE pause
    exit /b 1
  )
)

echo  Python:
"%VENV_PY%" --version
"%VENV_PY%" -c "import langextract as lx; print('  import langextract  OK  (' + lx.__file__ + ')')"
if errorlevel 1 (
  echo [ERROR] import langextract failed.
  if /i not "%MODE%"=="check" if not defined LANGEXTRACT_NONINTERACTIVE pause
  exit /b 1
)
echo.

if /i "%MODE%"=="check" (
  echo  Check passed.
  exit /b 0
)

if /i "%MODE%"=="help" goto :usage
if /i "%MODE%"=="/?" goto :usage
if /i "%MODE%"=="-h" goto :usage
if /i "%MODE%"=="--help" goto :usage

if /i "%MODE%"=="repl" (
  echo  Starting interactive Python. langextract is imported as lx.
  echo.
  if defined LANGEXTRACT_NONINTERACTIVE (
    "%VENV_PY%" -c "import langextract as lx; print('Ready: import langextract as lx')"
    exit /b
  )
  "%VENV_PY%" -i -c "import langextract as lx; print('Ready: import langextract as lx')"
  exit /b
)

if /i "%MODE%"=="test" (
  echo  Running offline pytest...
  echo  ^(skips live API, Vertex, pip-plugin packaging, Ollama integration^)
  echo.
  "%VENV_PY%" -m pytest tests -q --tb=short -m "not live_api and not vertex_ai and not requires_pip and not integration"
  exit /b
)

if /i "%MODE%"=="test-all" (
  echo  Running pytest except live Gemini/Vertex...
  echo.
  "%VENV_PY%" -m pytest tests -q --tb=short -m "not live_api and not vertex_ai"
  exit /b
)

if /i "%MODE%"=="demo" (
  echo  Running Ollama demo...
  echo.
  "%VENV_PY%" "%ROOT%\examples\ollama\demo_ollama.py" %2 %3 %4 %5 %6 %7 %8 %9
  exit /b
)

if /i "%MODE%"=="pipeline" (
  echo  Running grounded financial pipeline...
  echo.
  set "PIPE_PY=%ROOT%\pipeline\.venv\Scripts\python.exe"
  if not exist "%ROOT%\pipeline\.venv\Scripts\python.exe" (
    echo  Pipeline venv missing — creating it...
    "%VENV_PY%" "%ROOT%\pipeline\setup_env.py"
    if errorlevel 1 exit /b 1
  )
  "%ROOT%\pipeline\.venv\Scripts\python.exe" "%ROOT%\pipeline\main.py" --provider mock %2 %3 %4 %5 %6 %7 %8 %9
  exit /b
)

if /i "%MODE%"=="review" (
  echo  Starting review dashboard...
  echo.
  if not exist "%ROOT%\pipeline\outputs\annotations.json" (
    "%ROOT%\pipeline\.venv\Scripts\python.exe" "%ROOT%\pipeline\main.py" --provider mock
    if errorlevel 1 exit /b 1
  )
  "%ROOT%\pipeline\.venv\Scripts\python.exe" "%ROOT%\pipeline\visualizer.py" %2 %3 %4 %5 %6 %7 %8 %9
  exit /b
)

if /i "%MODE%"=="smoke" (
  echo  Running offline pipeline smoke...
  echo.
  "%VENV_PY%" "%ROOT%\scripts\smoke.py"
  exit /b
)

if /i "%MODE%"=="register" (
  echo  Registering Claude Desktop / Claude CLI / Grok Build...
  echo.
  "%VENV_PY%" "%ROOT%\scripts\register.py"
  exit /b
)

if /i not "%MODE%"=="shell" (
  echo [ERROR] Unknown option: %MODE%
  echo.
  goto :usage
)

echo  Commands:
echo    START.bat           Open a venv shell  ^(default^)
echo    START.bat repl      Python REPL with langextract imported
echo    START.bat test      Offline pytest
echo    START.bat test-all  Pytest including Ollama/plugin packaging
echo    START.bat demo      Run examples\ollama\demo_ollama.py
echo    START.bat pipeline  Grounded financial extract ^(mock^)
echo    START.bat review    Highlight spans in the review UI
echo    START.bat smoke     Offline pipeline smoke
echo    START.bat register  Wire Claude Desktop / CLI / Grok Build
echo    START.bat check     Verify venv + import, then exit
echo    START.bat help      Show usage
echo.

if defined LANGEXTRACT_NONINTERACTIVE (
  echo  Shell ready ^(noninteractive^).
  exit /b 0
)

echo %cmdcmdline% | find /i "/c" >nul
if errorlevel 1 (
  endlocal
  call "%~dp0.venv\Scripts\activate.bat"
  title LangExtract
  cd /d "%~dp0"
  echo  Venv activated. Type python to start.
  exit /b 0
)

endlocal
cd /d "%~dp0"
title LangExtract
cmd /k call .venv\Scripts\activate.bat
exit /b 0

:usage
echo  Usage: START.bat [shell^|repl^|test^|test-all^|demo^|pipeline^|review^|smoke^|register^|check^|help]
echo.
if /i "%MODE%"=="help" exit /b 0
if /i "%MODE%"=="/?" exit /b 0
if /i "%MODE%"=="-h" exit /b 0
if /i "%MODE%"=="--help" exit /b 0
exit /b 1
