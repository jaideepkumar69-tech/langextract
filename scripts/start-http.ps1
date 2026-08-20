# Streamable HTTP MCP for grok.com and Grok Desktop (no Docker).
# Default: http://127.0.0.1:8768/mcp
# Use -Tunnel to publish via cloudflared for grok.com/connectors.
param(
    [int]$Port = 8768,
    [switch]$Tunnel
)

$ErrorActionPreference = "Stop"
$pyCandidates = @(
    "C:\Users\USER\projects\langextract\pipeline\.venv\Scripts\python.exe",
    "C:\Python314\python.exe"
)
$py = $pyCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $py) { throw "No Python found for langextract MCP" }
$server = "C:\Users\USER\projects\langextract\mcp\server.py"
$url = "http://127.0.0.1:$Port/mcp"
$stateDir = "C:\Users\USER\projects\langextract\packs\grok-web"
New-Item -ItemType Directory -Force -Path $stateDir | Out-Null

Write-Host "Starting langextract MCP HTTP on $url"
Write-Host "Claude Desktop / Claude CLI / Grok Build already use stdio."
Write-Host "This HTTP mode is for grok.com and Grok Desktop."

$httpJob = Start-Process -FilePath $py -ArgumentList @($server, "--http", "--port", "$Port") -PassThru -WindowStyle Normal
Write-Host "Python PID $($httpJob.Id)"
$httpJob.Id | Set-Content -Path (Join-Path $stateDir "http.pid") -Encoding ascii

if ($Tunnel) {
    $cf = Get-Command cloudflared -ErrorAction SilentlyContinue
    if (-not $cf) {
        Write-Host ""
        Write-Host "cloudflared is not installed. grok.com needs a public HTTPS URL."
        Write-Host "Install: winget install --id Cloudflare.cloudflared"
        Write-Host ""
        Wait-Process -Id $httpJob.Id
        exit 1
    }

    Write-Host "Waiting for local server..."
    $ready = $false
    $initBody = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"health","version":"1"}}}'
    for ($i = 1; $i -le 25; $i++) {
        try {
            $null = Invoke-WebRequest -Uri $url -Method POST -TimeoutSec 3 -UseBasicParsing -ContentType "application/json" -Headers @{ Accept = "application/json, text/event-stream" } -Body $initBody
            $ready = $true
            break
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    if (-not $ready) {
        Write-Host "Local server did not answer yet; starting tunnel anyway."
    }

    Write-Host ""
    Write-Host "Opening cloudflared quick tunnel."
    Write-Host "Copy the https://....trycloudflare.com URL and add /mcp at the end."
    Write-Host "Paste that into https://grok.com/connectors  ->  New Connector  ->  Custom"
    Write-Host "Same connector then works in Grok Desktop (same grok.com account)."
    Write-Host "Leave this window open. Ctrl+C stops the tunnel and the local MCP."
    Write-Host ""
    try {
        & cloudflared tunnel --url "http://127.0.0.1:$Port"
    } finally {
        if ($httpJob -and -not $httpJob.HasExited) {
            Stop-Process -Id $httpJob.Id -Force -ErrorAction SilentlyContinue
        }
    }
} else {
    Write-Host "Leave this window open. Ctrl+C in the Python window stops the server."
    try {
        Wait-Process -Id $httpJob.Id
    } finally {
        if ($httpJob -and -not $httpJob.HasExited) {
            Stop-Process -Id $httpJob.Id -Force -ErrorAction SilentlyContinue
        }
    }
}
