@echo off
title langextract for grok.com / Grok Desktop
cd /d "%~dp0"
echo Starting local MCP + Cloudflare tunnel for grok.com connectors...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-http.ps1" -Tunnel
echo.
echo Tunnel stopped. Press any key to close.
pause >nul
