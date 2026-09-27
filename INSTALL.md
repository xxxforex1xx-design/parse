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

```bash
py -m pip install fastapi uvicorn jinja2 python-multipart \
                   playwright requests beautifulsoup4 lxml \
                   pydantic click rich pyyaml pytest
```

Все зависимости **в одном `pip install`**, потому что они перечислены в `pyproject.toml` скиллов.

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
2. **Установить зависимости** (один раз): `pip install ...` + `playwright install`
3. **Запустить** (каждый раз): `run_server.bat` → http://127.0.0.1:8000/
4. **Использовать**: вводить SKU, получать карточку
5. **Обновить** (когда я скажу): `git pull`
6. **Переключиться на dev** (если хочешь свежее): `git checkout dev && git pull`
7. **Посмотреть чек-лист**: открыть `tools/CHECKLIST.md`
8. **Писать в issues / предлагать фичи**: GitHub → New Issue
