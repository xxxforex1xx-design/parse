# Установка Auto Parts Meta-Search из Git

Пошаговая инструкция: от `git clone` до работающего сайта на `localhost:8000`.

---

## 1. Клонировать репозиторий

```bash
git clone https://github.com/xxxforex1xx-design/parse.git
cd parse
```

Или для конкретной ветки:

```bash
# Стабильная версия (рекомендуется для первого запуска)
git clone -b main https://github.com/xxxforex1xx-design/parse.git
cd parse

# Активная разработка (свежий код, может быть нестабильно)
git clone -b dev https://github.com/xxxforex1xx-design/parse.git
cd parse
```

---

## 2. Проверить Python

Нужен Python **3.11+**. Проверить:

```bash
python --version
# или, если не в PATH:
py --version
```

Если Python не установлен:
- **Windows**: скачать с https://www.python.org/downloads/ (при установке включить «Add to PATH»)
- **Linux/Mac**: `sudo apt install python3.11` или `brew install python@3.11`

Если `python` не работает, а `py` работает — дальше в командах используй `py` вместо `python`.

---

## 3. Установить зависимости

Есть два способа:

### Способ A — через `requirements.txt` (рекомендуется)

```bash
py -m pip install -r requirements.txt
```

`requirements.txt` содержит все runtime + dev зависимости с зафиксированными нижними границами версий.

### Способ B — вручную (как раньше)

```bash
py -m pip install fastapi uvicorn jinja2 python-multipart \
                   playwright requests beautifulsoup4 lxml \
                   pydantic click rich pyyaml pytest
```

### Установить Chromium для Playwright

```bash
py -m playwright install chromium
```

Скачает ~200 MB. Делается один раз.

---

## 4. Запустить сервер

### Вариант A — батник (Windows)

```cmd
run_server.bat
```

Двойной клик или из PowerShell/cmd. Скрипт:
- Создаёт `tools/cache/`
- Ставит/обновляет зависимости
- Ставит Chromium (если ещё не)
- Запускает сервер на http://127.0.0.1:8000

### Вариант B — PowerShell-скрипт

```powershell
.\run_server.ps1
```

### Вариант C — вручную

```bash
py tools/web_app.py
```

---

## 5. Открыть в браузере

<http://127.0.0.1:8000/>

Ввести SKU (например, `6RU698151`), нажать «Искать». Через ~30–90 сек получишь карточку с ценами.

---

## 6. Обновление до последней версии

```bash
# В корне проекта
git pull origin main
```

Если ты на ветке `dev` (активная разработка):

```bash
git checkout dev
git pull origin dev
```

Если есть локальные изменения:

```bash
git stash                  # спрятать изменения
git pull origin main        # обновить
git stash pop              # вернуть изменения (возможны конфликты)
```

---

## 7. Переключение между версиями

```bash
# Посмотреть все ветки
git branch -a

# Переключиться на стабильную
git checkout main

# Переключиться на разработку
git checkout dev

# Посмотреть историю
git log --oneline --graph --all
```

| Ветка | Что внутри |
|---|---|
| `main` | Стабильная, всегда рабочая |
| `dev` | Активная разработка |
| `v3-cache` | Web + cache (как main, без README/CHECKLIST) |
| `v2-web` | Basic web без cache |
| `v1-cli` | CLI-only без web |

---

## 8. Запуск тестов

```bash
py -m pytest tests/ -v
```

Должно быть **36 passed in 3-4 сек**. Без интернета, без браузера.

---

## 9. Возможные проблемы

### `python` не найден

Используй `py` вместо `python`. На Windows `py` — это Windows Python Launcher, всегда работает.

### `pip install` падает с warning про `normalizer.exe` / подобное

Это не критично. Зависимости всё равно устанавливаются. Проверь:
```bash
py -c "import fastapi, playwright; print('OK')"
```

### `playwright install chromium` падает

Часто из-за антивируса. Решения:
1. Добавить `C:\Users\<USER>\AppData\Local\ms-playwright` в исключения антивируса
2. Запустить cmd от имени администратора
3. Использовать VPN (иногда блокируется CDN playwright)

### Сервер не стартует

Проверить логи:
```bash
py tools/web_app.py
```
Ошибки печатаются в консоль.

Если `Directory 'tools/static' does not exist` — **уже исправлено**, мы удалили `app.mount("/static")`.

### Поиск выдаёт captcha / бан

Сменить паузу между запросами в UI на большее:
```bash
py tools/web_app.py
```
Затем в UI — но пауза выставляется через `--min-delay 30 --max-delay 60`. Дефолт 8-12 сек иногда слишком быстро для Exist.

Если бан устойчивый — подождать 1 час или сменить IP.

### Кэш отдаёт старые данные

Кэш имеет TTL 24 часа. Удалить вручную:
```bash
# Windows
del tools\cache\*.json

# Linux/Mac
rm tools/cache/*.json
```

---

## 10. Структура после установки

```
parse/                                  ← сюда git clone
├── tools/
│   ├── web_app.py                     ← главный сервер
│   ├── interactive_search.py           ← CLI
│   ├── aggregator.py
│   ├── rate_limited_parser.py
│   ├── bs4_*_parser.py
│   ├── templates/index.html           ← UI
│   ├── cache/                         ← кэш (создаётся автоматически)
│   ├── fixtures/                      ← recon-фикстуры
│   └── CHECKLIST.md                   ← что сделано / TODO
├── tests/
│   ├── fixtures/{exist,autodoc,rossko}.html
│   └── test_*_parser.py
├── run_server.bat / .ps1              ← запуск
├── README.md / INSTALL.md / PROJECT_STATE.md
├── pyproject.toml                       ← нет в репо, но можно создать
├── .gitignore
└── .git/                                ← история
```

---

## 11. Обновить Git у себя после моих изменений

```bash
git pull origin main
```

Или, если ты на `dev`:

```bash
git checkout dev
git pull origin dev
```

Если будут конфликты — пиши мне, разберём.

---

## 12. Типичный workflow

1. **Клонировать** (один раз): `git clone https://github.com/xxxforex1xx-design/parse.git`
2. **Установить зависимости** (один раз): `pip install -r requirements.txt` + `playwright install`
3. **Запустить** (каждый раз): `run_server.bat` → http://127.0.0.1:8000/
4. **Использовать**: вводить SKU, получать карточку
5. **Обновить** (когда я скажу): `git pull`
6. **Переключиться на dev** (если хочешь свежее): `git checkout dev && git pull`
7. **Посмотреть чек-лист**: открыть `tools/CHECKLIST.md`
8. **Писать в issues / предлагать фичи**: GitHub → New Issue

---

## 13. Deployment (Docker / Dokku)

В репозитории есть готовые файлы для прода: `Dockerfile`, `Procfile`,
`app.json` (Dokku-конфиг), `.dockerignore`, `requirements.txt`.

### 13.1. Локально через Docker

```bash
# Сборка образа (~5-7 мин на первой сборке, потом ~30 сек)
docker build -t autoparts-meta-search .

# Запуск
docker run --rm -p 8000:8000 autoparts-meta-search
# Открыть http://localhost:8000
```

Базовый образ — `mcr.microsoft.com/playwright/python:v1.50.0-jammy`,
уже содержит Chromium и системные зависимости для headless-парсинга.
Финальный образ ~1.2 GB.

### 13.2. На Hetzner через Dokku

Dokku автоматически обнаружит `Dockerfile` в корне репозитория и
использует его вместо buildpack. Никакой дополнительной настройки
не требуется — только push в Dokku-remote.

```bash
# На сервере Hetzner (один раз):
dokku apps:create autoparts-meta-search
dokku config:set autoparts-meta-search \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8

# Локально — добавить Dokku как remote:
git remote add dokku dokku@your-hetzner-host:autoparts-meta-search

# Деплой:
git push dokku main
# или для dev-ветки:
git push dokku dev:master
```

После `git push` Dokku:
1. Соберёт образ через `Dockerfile`
2. Запустит контейнер с переменной `$PORT`
3. Маршрутизирует 80/443 → порт через nginx

### 13.3. Что внутри Dockerfile

| Шаг | Что делает |
|---|---|
| `FROM mcr.microsoft.com/playwright/python:v1.50.0-jammy` | Базовый образ с Python 3.12 + Chromium |
| `COPY requirements.txt` → `pip install` | Кэшируется отдельно от кода |
| `COPY tools/ templates/` | Код приложения |
| `ENV PYTHONUNBUFFERED=1` | Логи без буферизации |
| `HEALTHCHECK` | Проверяет `/` каждые 30 сек |
| `CMD uvicorn tools.web_app:app --host 0.0.0.0 --port $PORT` | Запуск FastAPI |

### 13.4. Переменные окружения

| Имя | Дефолт | Описание |
|---|---|---|
| `PORT` | 8000 | Порт FastAPI (Dokku прокидывает автоматически) |
| `PYTHONUNBUFFERED` | 1 | Без буфера stdout (для `docker logs`) |
| `PYTHONIOENCODING` | utf-8 | Кодировка вывода |
| `PLAYWRIGHT_BROWSERS_PATH` | `/ms-playwright` | Где лежит Chromium в базовом образе |

### 13.5. Кэш между деплоями

`tools/cache/*.json` хранится в volume контейнера. Чтобы кэш
не терялся при редеплое, смонтируйте volume:

```bash
# Docker
docker run --rm -p 8000:8000 \
    -v autoparts-cache:/app/tools/cache \
    autoparts-meta-search

# Dokku
dokku storage:mount autoparts-meta-search /var/lib/dokku/data/storage/autoparts-meta-search/cache:/app/tools/cache
```

### 13.6. Альтернатива — buildpack (если удалить Dockerfile)

`Procfile` и `app.json` позволяют Dokku/Heroku собрать проект через
`heroku-buildpack-python` без Docker. Удалите `Dockerfile`, и Dokku
автоматически переключится на buildpack-режим:

```bash
# Удалить Dockerfile (или переименовать в Dockerfile.disabled)
rm Dockerfile
git add -A && git commit -m "Switch to buildpack mode"
git push dokku main
```

В buildpack-режиме Dokku сам поставит Python и зависимости через
`pip install -r requirements.txt`, но Playwright Chromium придётся
доставить отдельно через `app.json` scripts или multi-buildpack.
