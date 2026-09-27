# Project Checklist — Auto Parts Meta-Search

> Обновляется после каждого рабочего блока. Источник истины для текущего
> состояния проекта.

**Дата последнего обновления:** авто-обновляется через cron

---

## ✅ Сделано

### Phase 1 — Recon (2026-09-25)
- [x] Разведка Exist.ru (robots.txt, защиты, структура)
- [x] Разведка Autodoc.ru
- [x] Разведка Rossko.ru
- [x] Разведка Emex.ru → отложен (нужен IP whitelist)
- [x] Разведка Avito → отклонён (anti-bot, ToS)

### Phase 2 — Парсеры (2026-09-25)
- [x] Exist BS4-парсер (Vue.js, 178 офферов, 10 pytest'ов)
- [x] Autodoc BS4-парсер (Angular, 8 pytest'ов)
- [x] Rossko BS4-парсер (HTML+Next.js, 8 pytest'ов)
- [x] rate_limited_parser.py (этичный crawler, 15-30 сек паузы)
- [x] aggregator.py (нормализация брендов, best-price)
- [x] **26 тестов** проходят за 3 сек (без интернета)

### Phase 3 — Web (2026-09-26)
- [x] FastAPI сервер с async поиском
- [x] Jinja2 + Tailwind CDN UI
- [x] Polling статуса (queued/running/done)
- [x] Файловое кэширование (24ч TTL)
- [x] История поисков (последние 20)
- [x] Retry на EPIPE при запуске Playwright
- [x] End-to-end: 6RU698151 → 331 оффер из 3 источников

### Phase 4 — Git + документация (2026-09-26)
- [x] 5 коммитов на main, 1 на dev
- [x] 5 веток: main, dev, v1-cli, v2-web, v3-cache
- [x] README.md с быстрым стартом
- [x] PROJECT_STATE.md как devlog
- [x] .gitignore правильный
- [x] PortableGit установлен, push через PAT работает

---

## 🟡 В работе (ветка dev)

- [ ] README — дополнить примерами и скриншотами
- [ ] CHANGELOG.md — история изменений
- [ ] Поиск по VIN и названию (через Rossko q=)
- [ ] Адаптив для мобильных (Tailwind responsive)
- [ ] Кнопка «Купить» с affiliate-шаблоном

---

## 🔴 Не сделано (TODO)

### Высокий приоритет
- [ ] Dockerfile для деплоя
- [ ] Procfile для Dokku (есть в SPEC, платформа — Hetzner)
- [ ] Фильтр по бренду/источнику в UI
- [ ] Сортировка результатов (цена/бренд/источник)
- [ ] Детальная карточка бренда (раскрытие по клику)
- [ ] Сравнение 2-3 SKU рядом

### Средний приоритет
- [ ] Поиск по VIN (у Rossko есть VIN-поле)
- [ ] Экспорт результата в CSV / Excel
- [ ] Email-уведомление при обновлении цены
- [ ] Графики цен (Chart.js)
- [ ] Мобильная адаптация
- [ ] Сохранение истории между перезапусками

### Низкий приоритет (v1.1+)
- [ ] Emex через Piloterr / xmldatafeed (4-й источник)
- [ ] Поддержка английского языка в UI
- [ ] Регистрация / авторизация пользователей
- [ ] Полный переход на TypeScript + Next.js (по SPEC.md)
- [ ] PostgreSQL вместо файлового кэша
- [ ] Redis для очереди crawler'а
- [ ] WebSocket вместо polling

### Когда-нибудь
- [ ] Telegram-бот для поиска
- [ ] Мобильное приложение
- [ ] Affiliate-система через Admitad/AdvCake/Pampadu

---

## 🚨 Известные проблемы / долги

- 🐛 PowerShell 5.1 не отображает UTF-8 эмодзи (₽, →) — это терминал, не код
- 🐛 Поллинг в UI жёстко зашит на 1.5 сек — нет backoff при долгом ожидании
- 🐛 `_run_search_sync` блокирует event loop на 30-60 сек — в продакшене нужен worker pool
- 🐛 Cache TTL — файлы лежат вечно, нужно чистить старые (>24ч)
- 🐛 Playwright EPIPE на Windows — частично решено retry, но возможны сбои
- 🟡 Кэш может отдавать устаревшие данные о наличии (только цены обновляются ежедневно)

---

## 📊 Метрики

| | |
|---|---|
| Тестов | 36/36 passing за 3 сек |
| Источников с TDD | 3 из 4 (Exist, Autodoc, Rossko) |
| Веток Git | 5 |
| Коммитов | 6 |
| Строк кода | ~3500 |
| End-to-end test | 6RU698151 → 331 оффер за 60 сек |
| Cache hit rate | зависит от использования |
| Поддержка языков | RU only (i18n в v1.1) |

---

## 🌿 Ветки

| Ветка | Что | Коммит |
|---|---|---|
| `main` | Стабильная | 18b2781 |
| `dev` | Активная разработка | 7cb9f14 |
| `v3-cache` | Web + cache (как main, но без README) | 18b2781 |
| `v2-web` | Basic web без cache | 9539b27 |
| `v1-cli` | CLI-only без web | 9e7fc14 |

Для отката:
```bash
git checkout main     # стабильная
git checkout v1-cli   # CLI-only
```
