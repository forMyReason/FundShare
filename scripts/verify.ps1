# Requires: PowerShell, Python on PATH, deps from requirements.txt
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

Write-Host "== pytest (quick) ==" -ForegroundColor Cyan
python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "== pytest + coverage (fundshare) ==" -ForegroundColor Cyan
python -m pytest --cov=fundshare --cov-report=term-missing -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "== ruff (optional) ==" -ForegroundColor Cyan
pip show ruff 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) {
    python -m ruff check fundshare
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    Write-Host "Skip: ruff not installed (pip install ruff)." -ForegroundColor DarkGray
}

Write-Host "All checks passed." -ForegroundColor Green
