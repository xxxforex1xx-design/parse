@echo off
REM Запуск Auto Parts Meta-Search web app
REM Использование: run_server.bat

cd /d "%~dp0"

echo Installing dependencies (one-time)...
py -m pip install --quiet fastapi uvicorn jinja2 python-multipart playwright 2>nul

echo Checking Playwright browser...
py -m playwright install chromium 2>nul

echo.
echo Starting server at http://127.0.0.1:8000
echo Press Ctrl+C to stop
echo.

py tools\web_app.py
