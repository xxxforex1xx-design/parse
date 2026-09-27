# Auto Parts Meta-Search

Мета-поиск автозапчастей по OEM/артикулу. Один запрос → сравнение цен с нескольких поставщиков (Exist, Autodoc, Rossko) в одной карточке.

## Что умеет

- 🔍 **Поиск по SKU** — вводишь артикул (например, `6RU698151`), получаешь карточку с ценами
- 📊 **3 источника** — Exist, Autodoc, Rossko (по 30–330 офферов на типичный артикул)
- 🏷️ **Best-price выборка** — самый дешёвый оффер + самый дешёвый ОРИГИНАЛ
- ⚡ **Файловое кэширование** — повторный запрос за 0 сек из `tools/cache/<SKU>.json`
- 📜 **История поисков** — последние 20 запросов в UI
- 🛡️ **Этичный crawler** — паузы 8–12 сек между источниками, retry на EPIPE

## Архитектура

```
Браузер (http://127.0.0.1:8000)
  ↓
FastAPI (uvicorn, Jinja2, Tailwind CDN)
  ↓
rate_limited_parser.py → Playwright → Exist / Autodoc / Rossko
  ↓
aggregator.py → нормализация брендов, best-price, JSON-карточка
  ↓
Файл tools/cache/<SKU>.json (кэш)
```

## Запуск

### 1. Установить зависимости

```bash
py -m pip install fastapi uvicorn jinja2 python-multipart playwright requests beautifulsoup4 lxml pydantic click rich pyyaml pytest
py -m playwright install chromium
```

### 2. Запустить сервер

```bash
# Двойной клик или из терминала:
.\run_server.bat
# или
.\run_server.ps1
# или вручную:
py tools/web_app.py
```

### 3. Открыть в браузере

<http://127.0.0.1:8000/>

## Структура репо

```
.
├── tools/
│   ├── web_app.py              ← FastAPI сервер
│   ├── interactive_search.py   ← CLI для ручного ввода SKU
│   ├── rate_limited_parser.py  ← этичный crawler Exist + Autodoc + Rossko
│   ├── aggregator.py           ← нормализация брендов, best-price
│   ├── bs4_*_parser.py         ← TDD-парсеры на фикстурах
│   ├── *smoke.py, *inspect.py  ← recon-скрипты (история)
│   ├── templates/index.html    ← Tailwind CDN UI
│   └── cache/                  ← кэш результатов (tools/cache/<SKU>.json)
├── tests/
│   ├── fixtures/{exist,autodoc,rossko}.html  ← фикстуры для TDD
│   └── test_*_parser.py         ← 36 pytest'ов (4 сек, без интернета)
├── PROJECT_STATE.md           ← рабочий лог проекта
├── run_server.bat             ← Windows запуск
├── run_server.ps1             ← PowerShell запуск
└── README.md
```

## Запуск тестов

```bash
py -m pytest tests/ -v
# 36 passed in 4.04s (без интернета, без браузера)
```

## Git-ветки

| Ветка | Что внутри |
|---|---|
| `main` | Стабильная, всегда рабочая |
| `dev` | Активная разработка |
| `v1-cli` | CLI-only (без web) |
| `v2-web` | Basic web без cache |
| `v3-cache` | Web + cache + history (текущая) |

## Источники

| Источник | Подход | Лимит |
|---|---|---|
| Exist.ru | Playwright + клик каталога | Низкий — captcha-friendly |
| Autodoc.ru | Playwright + прямой URL карточки | Средний |
| Rossko.ru | Playwright + поиск | Низкий |
| Emex.ru | B2B API + IP whitelist | Отложен в v1.1 |
| Avito | ❌ Не поддерживается (агрессивный anti-bot) | — |

## Что НЕ реализовано

- 🔴 Поиск по VIN (только SKU)
- 🔴 Поиск по названию детали (только SKU)
- 🟡 Кнопка «Купить» с affiliate-ссылками в карточке
- 🟡 История поисков не сохраняется между перезапусками сервера
- 🟡 Нет аутентификации, rate-limit на уровне пользователя
- 🟡 Деплой (Dokku, Dockerfile)

## Лицензия

Внутренний инструмент проекта.
