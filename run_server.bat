@echo off
REM ===================================================================
REM Auto Parts Meta-Search — Windows launcher
REM ===================================================================

setlocal
cd /d "%~dp0"

echo.
echo === Auto Parts Meta-Search launcher ===
echo.

REM --- Шаг 1: Создать нужные директории ---
if not exist "tools\cache" mkdir "tools\cache"
if not exist "tools\cache" (
    echo [ERROR] Не удалось создать tools\cache
    exit /b 1
)

REM --- Шаг 2: Установить зависимости ---
echo [1/3] Installing Python dependencies...
py -m pip install --quiet --disable-pip-version-check fastapi uvicorn jinja2 python-multipart playwright requests beautifulsoup4 lxml pydantic click rich pyyaml pytest 2>nul
if errorlevel 1 (
    echo [WARN] pip install завершился с предупреждением, продолжаем...
)

REM --- Шаг 3: Установить Chromium для Playwright ---
echo [2/3] Installing Playwright Chromium...
py -m playwright install chromium 2>nul
if errorlevel 1 (
    echo [WARN] playwright install завершился с предупреждением, продолжаем...
)

REM --- Шаг 4: Запуск ---
echo [3/3] Starting server at http://127.0.0.1:8000
echo        Press Ctrl+C to stop
echo.

py tools\web_app.py

endlocal
