# One-command demo bring-up: upstream -> Bifrost OSS -> Foresight console
# Usage: powershell -File scripts/run-demo.ps1 [-SkipSeed] [-NoBrowser]
param(
  [switch]$SkipSeed,
  [switch]$NoBrowser
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root 'backend'
$bifrost = Join-Path $root 'bifrost-config'

function Test-Port($port) {
  try { $c = New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1', $port); $c.Close(); return $true } catch { return $false }
}

function Wait-Http($url, $timeoutSec) {
  $deadline = (Get-Date).AddSeconds($timeoutSec)
  while ((Get-Date) -lt $deadline) {
    try { Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3 | Out-Null; return $true } catch { Start-Sleep -Seconds 2 }
  }
  return $false
}

Write-Host '== Bifrost Foresight demo ==' -ForegroundColor Magenta

if (-not (Test-Port 9100)) {
  Write-Host 'Starting demo upstream (:9100) ...'
  Start-Process -WindowStyle Hidden -WorkingDirectory $backend -FilePath 'python' -ArgumentList '-m','foresight.fakellm' | Out-Null
} else { Write-Host 'Upstream already running on :9100' }

if (-not (Test-Port 8080)) {
  Write-Host 'Starting Bifrost OSS (:8080) ... this takes ~30-60s'
  Start-Process -WindowStyle Hidden -WorkingDirectory $bifrost -FilePath 'npx' -ArgumentList '-y','@maximhq/bifrost','-app-dir',$bifrost,'-port','8080' | Out-Null
} else { Write-Host 'Bifrost already running on :8080' }

if (-not (Test-Port 8400)) {
  Write-Host 'Starting Foresight console (:8400) ...'
  Start-Process -WindowStyle Hidden -WorkingDirectory $backend -FilePath 'python' -ArgumentList 'main.py' | Out-Null
} else { Write-Host 'Foresight already running on :8400' }

Write-Host 'Waiting for services ...'
[void](Wait-Http 'http://127.0.0.1:9100/health' 60)
[void](Wait-Http 'http://127.0.0.1:8400/api/health' 90)
$bifrostUp = Wait-Http 'http://127.0.0.1:8080/' 150
if (-not $bifrostUp) { Write-Warning 'Bifrost did not come up in 150s — console will show it offline until it does.' }

if (-not $SkipSeed) {
  Write-Host 'Seeding the 21-day demo fleet ...'
  Invoke-RestMethod -Uri 'http://127.0.0.1:8400/api/seed' -Method POST -ContentType 'application/json' -Body '{}' | Out-Null
}

Write-Host ''
Write-Host 'Console:  http://localhost:8400' -ForegroundColor Green
Write-Host 'Bifrost:  http://localhost:8080' -ForegroundColor Green
Write-Host 'Upstream: http://localhost:9100' -ForegroundColor Green
if (-not $NoBrowser) { Start-Process 'http://localhost:8400' }
