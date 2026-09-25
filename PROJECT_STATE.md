# Project State — Auto Parts Meta-Search

> Рабочий лог проекта. Обновляется по мере прогресса. Это не официальная
> документация (та живёт в `SPEC.md`, `TASKS.md`, issues), а «второй мозг»
> для решений, находок и шагов, которые иначе потерялись бы.

## Цель проекта

Мета-поиск автозапчастей по OEM/артикулу: пользователь вводит артикул →
карточка с ценами и наличием с нескольких партнёров (Exist, Emex, Autodoc).

## Текущая фаза

**MVP — проверка технической реализуемости ✅.** 3 из 4 источников
работают с TDD-фикстурами (Exist, Autodoc, Rossko). 26 тестов проходят за
3.4 сек. Готов этичный crawler (`rate_limited_parser.py`) для Exist +
Autodoc — Rossko нужно добавить. Emex — отложен в v1.1 (нужен IP whitelist
или Piloterr/xmldatafeed).

### ✅ Rossko.ru — канал РАБОТАЕТ (с TDD-фикстурой)

**Вывод (по состоянию на 2026-09-25):**

- Rossko **не блокирует ботов** — никакой captcha, прямой поиск.
- URL поиска: `https://rossko.ru/single/search/?focus_request_id=…&q=…`
  (не основной `/search/`, а фокусный `/single/search/`).
- Использует Next.js + обычный HTML (без Vue/Angular — проще парсить).
- **9 офферов** для VAG `6RU698151`:
  - VAG (ОРИГИНАЛ, 6 мес.) — от **894 ₽**, 15 вариантов
  - ABS — Нет в наличии
  - Vite — Нет в наличии
  - Porsche (ОРИГИНАЛ) — от 894 ₽, 9 вариантов
  - Vika (ОПТИМАЛЬНЫЙ ВЫБОР) — от 2 217 ₽, 1 вариант
  - KoTL, Riginal, Finwhale, Dafmi — aftermarket

**Сравнение Rossko vs Exist vs Autodoc (VAG 6RU698151):**

| Источник | Брендов | Мин. цена | Макс. цена | Тип |
|---|---|---|---|---|
| Exist | 178+ | 998 ₽ (Amd) | 11 629 ₽ (VAG оригинал) | Самый полный |
| Autodoc | 1 | 6 726 ₽ | — | Только VAG оригинал |
| **Rossko** | **9** | **894 ₽** | 2 217 ₽ | Основные бренды |

Rossko **самый дешёвый** для VAG оригинала (894 ₽ vs 11 629 ₽ Exist).

**DOM-структура:**

```
DIV.goods-items
└── DIV.goods-item (.not-available для карточек без доставки)
    └── DIV.data
        ├── DIV.brand           ← «VAG», «ABS», «Finwhale»
        ├── DIV.name            ← «Колодки тормозные дисковые»
        ├── DIV.cost
        │   └── DIV.price       ← «от 894 ₽»
        └── DIV.info (варианты, гарантия)
```

**Партнёрка Rossko:** через Admitad (5.36% ставка), AdvCake, Pampadu.
Прямого affiliate-API нет, B2B API (api.rossko.ru) требует ключей.

**Скрипты:**

```
rossko_smoke.py        Playwright + поиск по артикулу
rossko_inspect.py      Инспекция DOM
bs4_rossko_parser.py   BS4-парсер карточек, работает на фикстуре
tests/test_rossko_parser.py  8 pytest'ов (включая сравнение с Exist)
```

**TDD-фикстура (8 тестов):**

```
test_fixture_exists PASSED
test_title_and_h1 PASSED                # РОССКО, «Нашли по запросу»
test_offers_count PASSED                # 5+
test_known_brands_present PASSED        # VAG, ABS, Vite, Porsche
test_vag_offer_is_cheapest PASSED       # 894 ₽
test_available_and_unavailable_offers PASSED
test_variants_count_for_vag PASSED      # 15 вариантов
test_compare_rossko_with_exist PASSED   # 894 < 11 629

8 passed in 3.38s
```

**Что осталось для Rossko:**

- [x] Recon (сделан)
- [x] TDD-фикстура + 8 pytest'ов (сделано)
- [ ] Добавить в `rate_limited_parser.py` (сейчас только Exist + Autodoc)
- [ ] Проверить на aftermarket SKU
- [ ] Live Playwright-парсер для прод-режима

**Вывод (по состоянию на 2026-09-25):**

- Exist **не блокирует ботов** — никакой captcha не понадобилась.
- Используется **Vue.js** для рендеринга цен → `page.content()` отдаёт
  сырой HTML до рендера, нужны `page.evaluate()` или `page.locator()`.
- **Многошаговый ViewState-flow:**
  1. `GET https://www.exist.ru/` — главная
  2. Ввод SKU в `#pcode` + Enter → переход на `/Price/?pcode=…`
  3. Страница «Выберите каталог» с двумя опциями (например, VAG / VAG Asia)
  4. Клик по каталогу → `/Price/?pid=…` с **реальными предложениями**
- **178 предложений** для VAG `6RU 698 151` (тормозные колодки Polo/Fabia)
- Минимальная цена: **326 ₽** (опт/мелкое количество), рекомендуемая Exist — **«от 998 ₽»** (Amd)
- Сроки: «Завтра 14:30», «Чт 14:00», «05.10 14:00», «В офисе»

**DOM-структура (Vue-рендер):**

```
DIV.table-body (178 row-container)
└── DIV.row-container        ← один оффер = бренд + варианты
    ├── DIV.name-container
    │   ├── DIV.brand        ← «LYNXauto», «Marshall» (бренд производителя)
    │   ├── DIV.art          ← Exist-артикул / название
    │   ├── DIV.partno       ← оригинальный OEM «6RU 698 151»
    │   └── DIV.description  ← название детали
    ├── DIV.bestOffers       ← «Лучшие предложения»
    │   └── DIV.pricerow ×N  ← срок + цена
    └── DIV.allOffers        ← остальные варианты
        └── DIV.pricerow ×N
```

**Стек парсера:**

- `playwright` 1.63.0 (Chromium 1243, winldd 1007) — установлено локально
- `py -m playwright install chromium` — единожды
- `page.evaluate()` + JS — для парсинга Vue-DOM (живой сбор)
- Python `beautifulsoup4` + `pytest` — для TDD на сохранённых фикстурах
  (без сети, за 3 сек)

**Артефакты (в `tools/fixtures/` и `tests/fixtures/`):**

```
tests/fixtures/exist.html                       1.2 MB фикстура для TDD
tools/fixtures/exist-flow-1-catalog-…html/.png  Шаг 1: «Выберите каталог»
tools/fixtures/exist-flow-2-results-…html/.png Шаг 2: 178 офферов (22k px)
tools/fixtures/exist-final-6RU698151.html       Отрендеренный DOM
tools/fixtures/exist-final-6RU698151.json       178 офферов (JSON)
tools/fixtures/exist-offers-6RU698151.json      60 офферов (промежуточный)
tools/fixtures/exist-…(404/captcha/redirect…)  История неудачных подходов
```

**Скрипты (в `tools/`):**

```
exist_smoke.py            GET /Price/?pcode=… → captcha-страница
exist_api_smoke.py        GET /Api/Parts/Search?term=… → 404
exist_direct_smoke.py     GET /Catalog/Goods/{brand}/{sku}/ → redirect
exist_price_smoke.py      POST /Price/default.aspx?pcode=… → главная
exist_playwright_smoke.py Playwright: ввод + Enter → 2 опции каталога
exist_full_flow.py        Playwright: ввод + клик → 178 офферов
exist_dom_parse.py        Playwright + page.evaluate → 60 офферов
exist_dom_inspect.py      Инспекция DOM .pricerow
exist_dom_inspect2.py     Инспекция parent и поиск бренда
exist_parser.py           Playwright CLI: ввод → клик → JSON
bs4_exist_parser.py       BS4-парсер: работает на фикстуре без браузера
tests/test_exist_parser.py 10 pytest'ов, 3 сек, без интернета
```

**TDD-фикстура (10 тестов):**

```
test_fixture_exists PASSED
test_offers_count PASSED                       # 178
test_title_and_h1 PASSED                       # VAG 6RU 698 151
test_every_offer_has_partno PASSED             # 178/178
test_known_brands_present PASSED               # LYNXauto, Marshall, Amd, …
test_each_offer_has_at_least_one_variant PASSED
test_prices_are_numeric_and_reasonable PASSED  # 100..100000
test_terms_are_present PASSED                  # 70%+ имеют срок
test_best_offers_marked PASSED                 # 100+ best_offers
test_min_price_reasonable PASSED               # 326 ₽ minimum

10 passed in 3.01s
```

**Rate-limit политика:** 1 пользовательский сценарий = 1 запрос. Между
запусками парсера — пауза 5-10 сек. В продакшене — worker pool с
очередью BullMQ. Этичный crawler живёт в `tools/rate_limited_parser.py`
(15-30 сек jitter + retry/backoff).

- [x] Уточнить селекторы брендов (через `exist_dom_inspect2.py`)
- [x] Зафиксировать парсер как `tools/exist_parser.py` (Playwright CLI)
- [x] TDD-фикстура + 10 pytest'ов (`tests/test_exist_parser.py`)
- [x] Rate-limit middleware + retry/backoff (через `rate_limited_parser.py`)
- [ ] Переписать на TypeScript для интеграции в Fastify backend
- [ ] Добавить в расписание (cron/BullMQ) с актуальными ценами
- [ ] Sanitize-фикстура (убрать cookies/session) для публичного репо

### ⏳ Emex.ru — НЕ разведано полностью

- `robots.txt`: запрещён `/cabinet`, `/ws/`, `/api/` (кроме sitemap)
- B2B API через `wsdoc.emex.ru` — требует IP whitelist через менеджера
- Без whitelist — бан IP через несколько тысяч запросов

**Следующий шаг:** отправить запрос менеджеру на IP whitelist
(через `affiliate-onboarding` скилл). Параллельно можно проверить, есть
ли у Emex поисковая страница, которая работает без API (маловероятно,
но стоит попробовать как fallback).

### ⏳ Autodoc.ru — НЕ разведано полностью

- `robots.txt`: `Disallow: /price/*` — основной путь с ценами закрыт
- Запрещены все `?*` кроме `?page=` и `?categoryId=`
- Partner API (`partnerapi.autodoc.ru`) — для стоков, не публичный поиск
- Сторонние: xmldatafeed (готовые CSV), Piloterr (API-враппер)

**Следующий шаг:** оценить Piloterr / xmldatafeed (нужна коммерческая
регистрация — отложить до решения про партнёрку).

### ✅ Autodoc.ru — канал РАБОТАЕТ (с TDD-фикстурой)

**Вывод (по состоянию на 2026-09-25):**

- Autodoc **не блокирует ботов** — никакой captcha, никакого 403.
- Используется **Angular** (`_ngcontent-ng-*` атрибуты), не Vue — но
  подход тот же: `page.evaluate()` после `wait_for_timeout(6-8s)`.
- **Прямой URL карточки** (без multi-step flow):
  `https://www.autodoc.ru/man/{manufacturer_id}/part/{sku}`
- Title: `VAG 6RU698151 - Колодки тормозные`
- H1: `Колодки тормозные VAG 6RU698151`
- Цена: **от 6 726 ₽**
- Наличие: **79 шт**
- Доставка: Экспресс от 15 минут, Курьером от 1 дня, Самовывоз бесплатно

**Сравнение с Exist для `6RU698151`:**

| Источник | Бренд | Цена | Наличие |
|---|---|---|---|
| Exist (VAG оригинал) | VAG | от 11 629 ₽ | много вариантов |
| Exist (Amd) | Amd | от 998 ₽ | есть |
| Exist (LYNXauto) | LYNXauto | от 2 427 ₽ | есть |
| **Autodoc** | **VAG** | **от 6 726 ₽** | **79 шт** |

Autodoc дешевле Exist для VAG оригинала (6 726 ₽ vs 11 629 ₽).
Autodoc показывает **только оригинальный VAG**, Exist — широкую номенклатуру.

**DOM-структура (Angular-рендер):**

```
DIV.grid.card
├── DIV.card__info
│   ├── H5.card__name              ← «Колодки тормозные»
│   └── DIV.card__manufacturer     ← «VAG Производитель»
├── DIV.card__price
│   ├── DIV.card__price-wrapper
│   │   └── A.card__price-link     ← «от 6 726 ₽»
│   └── DIV.card__price-stock      ← «В наличии 79 шт»
└── DIV.card__delivery             ← способы доставки
```

**Скрипты (в `tools/`):**

```
autodoc_smoke.py      Playwright: открыть → ввод SKU → URL карточки
autodoc_inspect.py    Инспекция DOM, поиск селекторов
bs4_autodoc_parser.py BS4-парсер карточки, работает без браузера
tests/test_autodoc_parser.py  8 pytest'ов (включая сравнение с Exist)
```

**TDD-фикстура (8 тестов):**

```
test_fixture_exists PASSED
test_title_and_h1 PASSED                  # VAG 6RU698151
test_offers_count PASSED                  # 1+
test_brand_is_vag PASSED                  # VAG (без «Производитель»)
test_price_is_numeric PASSED              # 1000..50000
test_stock_is_numeric PASSED              # 79 шт
test_delivery_options_present PASSED      # экспресс/курьер/самовывоз
test_compare_with_exist PASSED            # 6726 < 11629

8 passed in 3.15s
```

**Rate-limit политика:** 1 пользовательский сценарий = 1 запрос. Между
запусками — пауза 5-10 сек. Autodoc более щадящий, чем Exist — можно
попробовать быстрее.

**Скрипты (в `tools/`):**

```
autodoc_smoke.py            Playwright: открыть → ввод SKU → URL карточки
autodoc_inspect.py          Инспекция DOM, поиск селекторов
bs4_autodoc_parser.py       BS4-парсер карточки, работает без браузера
tests/test_autodoc_parser.py 8 pytest'ов (включая сравнение с Exist)
rate_limited_parser.py      ОБЩИЙ crawler: rate-limit + retry + JSONL
                            (Exist + Autodoc, dry-run поддержка)
```

**Rate-limit политика для rate_limited_parser.py:**

- Пауза между запросами: **15–30 сек со случайным jitter**
  (чтобы паттерн не читался anti-bot'ом)
- Retry: до 3 попыток с exponential backoff (5с → 10с → 20с)
- В dry-run ничего не запрашивается, только печатает план

**Что осталось для Autodoc:**

- [x] Recon (сделан)
- [x] TDD-фикстура + 8 pytest'ов (сделано)
- [x] Rate-limited crawler (через `rate_limited_parser.py --source autodoc`)
- [ ] Проверить на aftermarket SKU (например, Brembo — там может быть
      другой layout карточки)
- [ ] Проверить на разных категориях (форсунки, фильтры)

## Стек проекта (зафиксировано в SPEC.md)

- **Backend**: Fastify + TypeScript + Prisma + PostgreSQL + Redis + BullMQ
- **Frontend**: Next.js 14 + Tailwind + shadcn/ui
- **Парсеры (планировалось)**: Playwright на TypeScript
- **Реальность**: парсер Exist = Python+Playwright (работает),
  остальные источники в очереди
- **Deploy**: Dokku на Hetzner, `apps/{api,web,scrapers}`

## Решения и договорённости

- **Питон для tooling, не для runtime**: backend и фронт остаются на TS.
  Python — для скриптов вокруг проекта (`tools/`, recon-скрипты).
- **Rate-limit по умолчанию**: 1 запрос / 5-10 сек на Exist. Не долбить.
- **Captcha-обход НЕ применяется**: Exist не ставит captcha, если другие
  источники поставят — решать через stealth/ручной обход.
- **Фикстуры для TDD**: HTML-фикстуры сохраняются на диск для
  CI-безопасных тестов парсера (без живого интернета в CI).

## Открытые вопросы

1. Переписывать ли парсер Exist с Python на TypeScript?
   - Плюс TS: единый язык с проектом, проще интеграция
   - Плюс Python: уже работает, быстрее экспериментировать
2. Какой следующий источник разведывать — Emex (нужен whitelist) или
   Autodoc (нужна коммерческая подписка)?
3. Делать ли scraper-recon скилл из того, что мы выяснили — или пока
   оставить как `tools/`?
4. Парсер Exist у нас сейчас работает через `.pricerow` + DOM — но Exist
   может в любой момент сменить вёрстку. Где держать актуальные фикстуры?

## Полезные ссылки

- SPEC: `.scratch/auto-parts-meta-search/SPEC — Auto Parts Meta-Search`
- TASKS: `.scratch/auto-parts-meta-search/Auto Parts Search — MVP Tasks`
- Issues: `.scratch/auto-parts-meta-search/issues/01-…md` (12 шт.)

---

*Обновлено: 2026-09-26. Exist + Autodoc + Rossko с TDD (26 тестов за 3.4 сек). Готов этичный crawler.*
