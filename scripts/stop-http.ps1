# Stop the local langextract HTTP MCP (port 8768) and leftover cloudflared.
$ErrorActionPreference = "SilentlyContinue"
$port = 8768
$pidFile = "C:\Users\USER\projects\langextract\packs\grok-web\http.pid"

if (Test-Path $pidFile) {
    $saved = Get-Content $pidFile | Select-Object -First 1
    if ($saved) {
        Stop-Process -Id ([int]$saved) -Force -ErrorAction SilentlyContinue
    }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }

Get-CimInstance Win32_Process -Filter "Name = 'cloudflared.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match "127\.0\.0\.1:$port" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

Write-Host "Stopped langextract HTTP on port $port (if it was running)."
