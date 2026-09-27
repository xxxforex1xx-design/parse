"""Минимальный веб-интерфейс для Auto Parts Meta-Search.

Стек: FastAPI + Jinja2 + Tailwind CDN. Без сложной TS-инфраструктуры —
это MVP-демо, которое запускается локально и показывает работу парсеров.

Запуск:
    py tools/web_app.py
    # или
    uvicorn tools.web_app:app --host 0.0.0.0 --port 8000

Открой http://localhost:8000 в браузере.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE / "tools"))

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.responses import HTMLResponse, JSONResponse  # noqa: E402
from fastapi.templating import Jinja2Templates  # noqa: E402
from fastapi import Request  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout  # noqa: E402
from playwright._impl._errors import Error as PWError  # noqa: E402

from rate_limited_parser import (  # noqa: E402
    parse_exist, parse_autodoc, parse_rossko, UA,
)
from aggregator import aggregate, normalize_sku  # noqa: E402
from query_utils import (  # noqa: E402
    normalize_query, cache_key_for_query, sources_for_query_type,
)

TEMPLATES_DIR = WORKSPACE / "tools" / "templates"
CACHE_DIR = WORKSPACE / "tools" / "cache"

# TTL кэша: 24 часа (для мета-поиска автозапчастей цены меняются ежедневно)
CACHE_TTL_SECONDS = 24 * 3600

# Хранилище статусов поиска в памяти (in-memory).
# В проде — Redis, но для MVP достаточно.
SEARCHES: dict[str, dict[str, Any]] = {}

# История поисков (последние N, в памяти)
HISTORY_MAX = 20
HISTORY: list[dict[str, Any]] = []


def cache_path(sku: str) -> Path:
    return CACHE_DIR / f"{sku}.json"


def load_cache(sku: str) -> dict[str, Any] | None:
    """Загрузить кэш с проверкой TTL."""
    p = cache_path(sku)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    # Проверяем возраст
    cached_at = data.get("cached_at")
    if cached_at:
        try:
            ts = datetime.fromisoformat(cached_at.replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - ts).total_seconds()
            if age > CACHE_TTL_SECONDS:
                return None  # устарело
        except (ValueError, TypeError):
            return None
    return data


def save_cache(sku: str, data: dict[str, Any]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path(sku).write_text(json.dumps(data, ensure_ascii=False, indent=2),
                              encoding="utf-8")


def cache_age(cached_at: str) -> str:
    """Человекочитаемая давность кэша."""
    try:
        ts = datetime.fromisoformat(cached_at.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - ts
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return f"{seconds} сек назад"
        if seconds < 3600:
            return f"{seconds // 60} мин назад"
        if seconds < 86400:
            return f"{seconds // 3600} ч назад"
        return f"{seconds // 86400} дн назад"
    except (ValueError, TypeError):
        return "неизвестно"


def add_to_history(query: str, q_type: str, sources: list[str], records_count: int) -> None:
    HISTORY.insert(0, {
        "query": query,
        "q_type": q_type,
        "sources": sources,
        "records_count": records_count,
        "ts": datetime.now(timezone.utc).isoformat(),
    })
    while len(HISTORY) > HISTORY_MAX:
        HISTORY.pop()


def _run_search_sync(query: str, sources: set[str],
                     min_delay: float, max_delay: float) -> list[dict[str, Any]]:
    """Синхронный Playwright-парсинг выбранных источников. Возвращает плоский список офферов."""
    records: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc).isoformat()

    parsers = {
        "exist": lambda page: _parse_exist(page, query, now, records),
        "autodoc": lambda page: _parse_autodoc(page, query, now, records),
        "rossko": lambda page: _parse_rossko(page, query, now, records),
    }

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(
            user_agent=UA,
            locale="ru-RU",
            timezone_id="Europe/Moscow",
            viewport={"width": 1366, "height": 900},
        )
        ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        page = ctx.new_page()

        for i, src in enumerate(sources):
            if i > 0:
                delay = min_delay + (max_delay - min_delay) * (0.5 + 0.5 * (hash(query + src) % 100) / 100)
                time.sleep(delay)
            try:
                parsers[src](page)
            except PWTimeout:
                pass
            except Exception:
                pass

        browser.close()
    return records


def _parse_exist(page, query: str, now: str, records: list) -> None:
    parsed = parse_exist(page, query)
    for off in parsed.get("offers", []):
        for v in off.get("variants", []):
            if v.get("price_value") is None:
                continue
            records.append({
                "source": "exist",
                "sku": query,
                "brand": off.get("brand") or off.get("art"),
                "name": off.get("descr"),
                "price_value": v["price_value"],
                "price_text": v.get("price_text"),
                "is_best_offer": v.get("is_best_offer"),
                "flags": None,
                "url": parsed.get("url"),
                "scraped_at": now,
            })


def _parse_autodoc(page, query: str, now: str, records: list) -> None:
    parsed = parse_autodoc(page, query)
    c = parsed.get("card") or {}
    if c.get("price_value") is not None:
        records.append({
            "source": "autodoc",
            "sku": query,
            "brand": c.get("brand"),
            "name": c.get("name"),
            "price_value": c["price_value"],
            "price_text": c.get("price_text"),
            "is_available": True,
            "flags": None,
            "url": parsed.get("url"),
            "scraped_at": now,
        })


def _parse_rossko(page, query: str, now: str, records: list) -> None:
    parsed = parse_rossko(page, query)
    for off in parsed.get("offers", []):
        if off.get("price_value") is None:
            continue
        records.append({
            "source": "rossko",
            "sku": query,
            "brand": off.get("brand"),
            "name": off.get("name"),
            "price_value": off["price_value"],
            "price_text": off.get("price_text"),
            "is_available": off.get("is_available"),
            "flags": off.get("flags"),
            "url": parsed.get("url"),
            "scraped_at": now,
        })


# ── FastAPI app ────────────────────────────────────────────────────────

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Auto Parts Meta-Search", lifespan=lifespan)


class SearchRequest(BaseModel):
    q: str
    sources: list[str] = ["exist", "autodoc", "rossko"]
    min_delay: float = 8.0
    max_delay: float = 12.0


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.post("/api/search")
async def start_search(req: SearchRequest):
    """Запустить поиск в фоне, вернуть search_id для опроса статуса.

    Поддерживает три типа запросов:
    - SKU (4-20 alnum)  → Exist + Autodoc + Rossko
    - VIN (17 alnum)    → только Rossko
    - NAME (текст)      → только Rossko
    """
    q_type, normalized = normalize_query(req.q)
    if q_type == "empty":
        raise HTTPException(
            status_code=400,
            detail={
                "error": "empty_query",
                "message": "Пустой запрос — введите артикул, VIN или название",
            },
        )

    # Источники, которые реально поддерживают этот тип запроса.
    # Если клиент прислал свой список — пересекаем с поддерживаемыми.
    supported = sources_for_query_type(q_type)
    sources = [s for s in req.sources if s in supported] or supported

    cache_key = cache_key_for_query(q_type, normalized)

    # Сначала проверяем кэш
    cached = load_cache(cache_key)
    if cached and set(cached.get("_sources", [])) >= set(sources):
        search_id = str(uuid.uuid4())[:8]
        SEARCHES[search_id] = {
            "status": "done",
            "started_at": cached.get("cached_at"),
            "query": normalized,
            "q_type": q_type,
            "cache_key": cache_key,
            "sources": sources,
            "progress": {src: "cached" for src in sources},
            "result": cached["result"],
            "records_count": cached.get("records_count", 0),
            "from_cache": True,
            "error": None,
        }
        return {
            "search_id": search_id,
            "query": normalized,
            "q_type": q_type,
            "sources": sources,
            "from_cache": True,
        }

    search_id = str(uuid.uuid4())[:8]
    SEARCHES[search_id] = {
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "query": normalized,
        "q_type": q_type,
        "cache_key": cache_key,
        "sources": sources,
        "progress": {},
        "result": None,
        "from_cache": False,
        "error": None,
    }

    asyncio.create_task(_do_search(search_id, normalized, cache_key, q_type,
                                    sources, req.min_delay, req.max_delay))
    return {
        "search_id": search_id,
        "query": normalized,
        "q_type": q_type,
        "sources": sources,
        "from_cache": False,
    }


async def _do_search(search_id: str, normalized: str, cache_key: str,
                      q_type: str, sources: list[str],
                      min_delay: float, max_delay: float) -> None:
    """Фоновая задача: парсит источники, обновляет прогресс."""
    loop = asyncio.get_event_loop()
    sources_set = set(sources)
    SEARCHES[search_id]["progress"] = {src: "queued" for src in sources_set}
    for src in sources_set:
        SEARCHES[search_id]["progress"][src] = "running"

    # Retry на запуск Playwright (EPIPE на Windows)
    records: list[dict[str, Any]] = []
    last_err = None
    for attempt in range(3):
        try:
            records = await loop.run_in_executor(
                None,
                _run_search_sync,
                normalized, sources_set, min_delay, max_delay,
            )
            last_err = None
            break
        except (PWError, PWTimeout, OSError, RuntimeError) as e:
            last_err = e
            wait = 5 * (attempt + 1)
            SEARCHES[search_id]["error"] = f"Попытка {attempt+1}/3: {type(e).__name__}: {str(e)[:120]}"
            await asyncio.sleep(wait)
        except Exception as e:
            last_err = e
            SEARCHES[search_id]["error"] = f"Попытка {attempt+1}/3: {type(e).__name__}: {str(e)[:120]}"
            break

    for src in sources_set:
        SEARCHES[search_id]["progress"][src] = "done"

    if last_err:
        SEARCHES[search_id]["status"] = "error"
        if not SEARCHES[search_id].get("error"):
            SEARCHES[search_id]["error"] = f"Все попытки упали: {last_err}"
        return

    if not records:
        SEARCHES[search_id]["status"] = "error"
        SEARCHES[search_id]["error"] = "Ничего не найдено"
        return

    result = aggregate(records)
    SEARCHES[search_id]["status"] = "done"
    SEARCHES[search_id]["result"] = result
    SEARCHES[search_id]["records_count"] = len(records)

    save_cache(cache_key, {
        "query": normalized,
        "q_type": q_type,
        "_sources": list(sources_set),
        "records_count": len(records),
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "result": result,
    })
    add_to_history(normalized, q_type, list(sources_set), len(records))


@app.get("/api/search/{search_id}")
async def get_search(search_id: str):
    """Опрос статуса поиска."""
    if search_id not in SEARCHES:
        raise HTTPException(404, "search_id not found")
    return SEARCHES[search_id]


@app.get("/api/history")
async def get_history():
    """Последние N поисковых запросов."""
    return {"history": HISTORY}


@app.get("/api/cache/{cache_key:path}")
async def get_cache(cache_key: str):
    """Получить кэшированный результат по cache_key."""
    cached = load_cache(cache_key)
    if not cached:
        raise HTTPException(404, "not cached")
    return cached


@app.get("/api/export/{cache_key:path}.csv")
async def export_csv(cache_key: str):
    """Экспорт результата в CSV (из кэша)."""
    if not cache_key.endswith(".csv"):
        cache_key = cache_key + ".csv"
    return _do_export(cache_key[:-4])


def _do_export(cache_key: str):
    cached = load_cache(cache_key)
    if not cached:
        raise HTTPException(404, "not cached")

    rows = []
    for card in cached.get("result", {}).get("cards", []):
        for brand in card.get("brands", []):
            rows.append({
                "sku": card["sku"],
                "brand": brand["brand"],
                "min_price": brand["min_price"],
                "max_price": brand["max_price"],
                "is_original": brand["is_original"],
                "sources": ",".join(brand.get("sources", [])),
                "offers_count": brand["offers_count"],
                "card_offers_count": card["offers_count"],
                "offer_url": brand.get("offer_url") or "",
            })

    # Простой CSV (без csv-модуля, чтобы не тянуть лишнее)
    lines = ["sku,brand,min_price,max_price,is_original,sources,offers_count,card_offers_count,offer_url"]
    for r in rows:
        lines.append(
            f'{r["sku"]},{r["brand"]},{r["min_price"]:.0f},{r["max_price"]:.0f},'
            f'{r["is_original"]},{r["sources"]},{r["offers_count"]},{r["card_offers_count"]},{r["offer_url"]}'
        )

    from fastapi.responses import PlainTextResponse
    # Имя файла: для SKU — SKU.csv, для vin/name — query.csv (sanitized)
    q = cached.get("query", cache_key)
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in q)[:60]
    return PlainTextResponse(
        content="\n".join(lines),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={safe_name}.csv"},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
