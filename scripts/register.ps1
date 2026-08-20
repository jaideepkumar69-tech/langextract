# Register langextract with Claude Desktop, Claude CLI, and Grok Build CLI.
$ErrorActionPreference = "Stop"
$py = "C:\Python314\python.exe"
$reg = Join-Path $PSScriptRoot "register.py"
& $py $reg
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Registered. Restart Claude Desktop and open a new Claude CLI / Grok session."
