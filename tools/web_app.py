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
from fastapi.staticfiles import StaticFiles  # noqa: E402
from fastapi.templating import Jinja2Templates  # noqa: E402
from fastapi import Request  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout  # noqa: E402

from rate_limited_parser import (  # noqa: E402
    parse_exist, parse_autodoc, parse_rossko, UA,
)
from aggregator import aggregate, normalize_sku  # noqa: E402

TEMPLATES_DIR = WORKSPACE / "tools" / "templates"
STATIC_DIR = WORKSPACE / "tools" / "static"

# Хранилище статусов поиска в памяти (in-memory).
# В проде — Redis, но для MVP достаточно.
SEARCHES: dict[str, dict[str, Any]] = {}


def _normalize_query(q: str) -> tuple[str, str]:
    """Нормализуем запрос. Возвращает (тип, нормализованный)."""
    s = q.strip()
    # SKU/артикул: только буквы/цифры, обычно 4-15 символов
    cleaned = s.replace(" ", "").replace("-", "").replace("/", "").replace(".", "")
    if cleaned and all(c.isalnum() for c in cleaned) and 4 <= len(cleaned) <= 20:
        return ("sku", cleaned.upper())
    if " " in s:
        return ("name", s)
    return ("unknown", s)


def _run_search_sync(sku: str, sources: set[str],
                     min_delay: float, max_delay: float) -> list[dict[str, Any]]:
    """Синхронный Playwright-парсинг 3 источников. Возвращает плоский список офферов."""
    records: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc).isoformat()

    parsers = {
        "exist": lambda page: _parse_exist(page, sku, now, records),
        "autodoc": lambda page: _parse_autodoc(page, sku, now, records),
        "rossko": lambda page: _parse_rossko(page, sku, now, records),
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
                delay = min_delay + (max_delay - min_delay) * (0.5 + 0.5 * (hash(sku + src) % 100) / 100)
                time.sleep(delay)
            try:
                parsers[src](page)
            except PWTimeout:
                pass
            except Exception:
                pass

        browser.close()
    return records


def _parse_exist(page, sku: str, now: str, records: list) -> None:
    parsed = parse_exist(page, sku)
    for off in parsed.get("offers", []):
        for v in off.get("variants", []):
            if v.get("price_value") is None:
                continue
            records.append({
                "source": "exist",
                "sku": sku,
                "brand": off.get("brand") or off.get("art"),
                "name": off.get("descr"),
                "price_value": v["price_value"],
                "price_text": v.get("price_text"),
                "is_best_offer": v.get("is_best_offer"),
                "flags": None,
                "url": parsed.get("url"),
                "scraped_at": now,
            })


def _parse_autodoc(page, sku: str, now: str, records: list) -> None:
    parsed = parse_autodoc(page, sku)
    c = parsed.get("card") or {}
    if c.get("price_value") is not None:
        records.append({
            "source": "autodoc",
            "sku": sku,
            "brand": c.get("brand"),
            "name": c.get("name"),
            "price_value": c["price_value"],
            "price_text": c.get("price_text"),
            "is_available": True,
            "flags": None,
            "url": parsed.get("url"),
            "scraped_at": now,
        })


def _parse_rossko(page, sku: str, now: str, records: list) -> None:
    parsed = parse_rossko(page, sku)
    for off in parsed.get("offers", []):
        if off.get("price_value") is None:
            continue
        records.append({
            "source": "rossko",
            "sku": sku,
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
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


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
    """Запустить поиск в фоне, вернуть search_id для опроса статуса."""
    q_type, sku = _normalize_query(req.q)
    if q_type != "sku":
        raise HTTPException(
            status_code=400,
            detail={
                "error": "only_sku_supported",
                "message": f"Пока поддерживается только поиск по артикулу (SKU). Получили: {q_type!r} — {req.q!r}",
                "tip": "Введите артикул вида 6RU698151 или 0446533450"
            },
        )

    search_id = str(uuid.uuid4())[:8]
    SEARCHES[search_id] = {
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "sku": sku,
        "sources": req.sources,
        "progress": {},
        "result": None,
        "error": None,
    }

    asyncio.create_task(_do_search(search_id, sku, req.sources, req.min_delay, req.max_delay))
    return {"search_id": search_id, "sku": sku}


async def _do_search(search_id: str, sku: str, sources: list[str],
                      min_delay: float, max_delay: float) -> None:
    """Фоновая задача: парсит 3 источника, обновляет прогресс."""
    try:
        # Запускаем синхронный crawler в executor
        loop = asyncio.get_event_loop()
        sources_set = set(sources)
        SEARCHES[search_id]["progress"] = {src: "queued" for src in sources_set}

        # Помечаем прогресс по источникам
        for src in sources_set:
            SEARCHES[search_id]["progress"][src] = "running"

        records = await loop.run_in_executor(
            None,
            _run_search_sync,
            sku, sources_set, min_delay, max_delay,
        )

        for src in sources_set:
            SEARCHES[search_id]["progress"][src] = "done"

        result = aggregate(records)
        SEARCHES[search_id]["status"] = "done"
        SEARCHES[search_id]["result"] = result
        SEARCHES[search_id]["records_count"] = len(records)
    except Exception as e:
        SEARCHES[search_id]["status"] = "error"
        SEARCHES[search_id]["error"] = str(e)


@app.get("/api/search/{search_id}")
async def get_search(search_id: str):
    """Опрос статуса поиска."""
    if search_id not in SEARCHES:
        raise HTTPException(404, "search_id not found")
    return SEARCHES[search_id]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
