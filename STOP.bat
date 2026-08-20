@echo off
title Stop langextract HTTP / tunnel
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop-http.ps1"
exit /b %ERRORLEVEL%
