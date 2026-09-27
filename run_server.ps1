# Запуск Auto Parts Meta-Search web app
# Использование: .\run_server.ps1

Set-Location $PSScriptRoot

Write-Host "Installing dependencies (one-time)..." -ForegroundColor Cyan
py -m pip install --quiet fastapi uvicorn jinja2 python-multipart playwright 2>&1 | Out-Null

Write-Host "Checking Playwright browser..." -ForegroundColor Cyan
py -m playwright install chromium 2>&1 | Out-Null

Write-Host ""
Write-Host "Starting server at http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""

py tools\web_app.py
