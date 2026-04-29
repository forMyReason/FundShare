# Requires: PowerShell, Python on PATH, deps from requirements.txt
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

Write-Host "== pytest (quick) ==" -ForegroundColor Cyan
python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "== pytest + coverage (fundshare) ==" -ForegroundColor Cyan
python -m pytest --cov=fundshare --cov-report=term-missing -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "All checks passed." -ForegroundColor Green
