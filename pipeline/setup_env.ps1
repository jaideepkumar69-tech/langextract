# Prompt 1 — create the pipeline venv and install dependencies.
$ErrorActionPreference = "Stop"
$py = $null
foreach ($c in @(
        "C:\Users\USER\AppData\Local\Programs\Python\Python312\python.exe",
        "C:\Python314\python.exe"
    )) {
    if (Test-Path $c) { $py = $c; break }
}
if (-not $py) { $py = (Get-Command python).Source }
Write-Host "Bootstrapping with $py"
& $py (Join-Path $PSScriptRoot "setup_env.py") @args
exit $LASTEXITCODE
