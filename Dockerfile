# Auto Parts Meta-Search — production image
#
# Используется официальный образ Playwright (Python + Chromium + системные
# зависимости), чтобы не накапливать apt-get слои вручную. Это ~1.2 GB
# (Python 3.12 + Chromium 130 + headless-shell). Для MVP-демо хватает;
# для v1.0 можно перейти на slim + ручной playwright install.
#
# Сборка:
#   docker build -t autoparts-meta-search .
# Запуск:
#   docker run --rm -p 8000:8000 autoparts-meta-search
#   # и открыть http://localhost:8000
#
# Dokku / Heroku:
#   Dockerfile автоматически определяется Dokku, никакой доп. конфигурации
#   не требуется. Procfile оставлен для buildpack-режима (если Dockerfile
#   удалить — Dokku fallback на buildpack).
#
# Что внутри:
#   - Python 3.12 (в образе Playwright)
#   - Chromium + headless-shell + системные библиотеки для Playwright
#   - FastAPI + uvicorn
#   - Jinja2, Pydantic, BS4, lxml
#   - Кэш-директория /app/tools/cache (смонтировать volume для персистентности)

FROM mcr.microsoft.com/playwright/python:v1.50.0-jammy

# Метаданные для Docker Hub / labels
LABEL org.opencontainers.image.title="autoparts-meta-search" \
      org.opencontainers.image.description="Meta-search across Exist / Autodoc / Rossko for OEM auto parts" \
      org.opencontainers.image.source="https://github.com/xxxforex1xx-design/parse" \
      org.opencontainers.image.licenses="MIT"

WORKDIR /app

# Зависимости Python — копируем файл отдельно, чтобы кэш Docker не
# пересобирался при изменении только кода.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Playwright Chromium уже в базовом образе. Если хотите гарантировать
# свежую версию — раскомментируйте строку ниже (добавляет ~30 сек к сборке).
# RUN playwright install chromium

# Код приложения
COPY tools/        ./tools/
COPY templates/    ./templates/ 2>/dev/null || true

# Документация (для /api/health, healthcheck, etc. — можно удалить если не нужно)
COPY README.md INSTALL.md PROJECT_STATE.md ./

# Кэш и runtime-директории
RUN mkdir -p /app/tools/cache /app/logs

# Переменные окружения
ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PORT=8000 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    WEB_APP_HOST=0.0.0.0

# Порт приложения
EXPOSE 8000

# Healthcheck — открываем корень / и убеждаемся что FastAPI отвечает 200.
# Замените на специализированный /api/health если добадите эндпоинт.
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request, sys; \
        sys.exit(0) if urllib.request.urlopen('http://localhost:8000/', timeout=5).status == 200 else sys.exit(1)"

# Команда запуска. В Dokku/Hetzner переменная $PORT переопределит --port.
CMD ["sh", "-c", "uvicorn tools.web_app:app --host 0.0.0.0 --port ${PORT:-8000}"]
