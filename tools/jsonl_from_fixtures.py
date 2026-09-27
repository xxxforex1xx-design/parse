"""Конвертирует результаты BS4-парсеров (fixtures) в формат JSONL,
который ожидает aggregator.py.

Схема JSONL записи (для aggregator):
- source: str (exist|rossko|autodoc)
- sku: str
- brand: str
- price_value: float | None
- is_best_offer: bool | None   (Exist)
- is_available: bool | None    (Rossko, Autodoc)
- flags: str | None
- scraped_at: ISO 8601
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE / "tools"))

from bs4_exist_parser import parse_file as parse_exist  # noqa: E402
from bs4_autodoc_parser import parse_file as parse_autodoc  # noqa: E402
from bs4_rossko_parser import parse_file as parse_rossko  # noqa: E402

FIXTURES = WORKSPACE / "tests" / "fixtures"
OUT = WORKSPACE / "tools" / "fixtures"


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[+] Записан {path} ({len(records)} записей)")


def exist_to_jsonl() -> None:
    parsed = parse_exist(FIXTURES / "exist.html")
    sku = "6RU698151"
    now = datetime.now(timezone.utc).isoformat()
    out = []
    for off in parsed["offers"]:
        for v in off["variants"]:
            out.append({
                "source": "exist",
                "sku": sku,
                "brand": off.get("brand") or off.get("art"),
                "name": off.get("descr"),
                "price_value": v.get("price_value"),
                "price_text": v.get("price_text"),
                "is_best_offer": v.get("is_best_offer"),
                "flags": None,
                "url": "https://www.exist.ru/Price/?pid=F41092C5",
                "scraped_at": now,
            })
    # Оставим топ-20 для демо (иначе слишком много)
    out.sort(key=lambda r: (r["price_value"] is None, r["price_value"] or 0))
    out = out[:20]
    write_jsonl(OUT / "exist-demo.jsonl", out)


def autodoc_to_jsonl() -> None:
    parsed = parse_autodoc(FIXTURES / "autodoc.html")
    sku = "6RU698151"
    now = datetime.now(timezone.utc).isoformat()
    off = parsed["offers"][0]
    out = [{
        "source": "autodoc",
        "sku": sku,
        "brand": off["brand"],
        "name": off["name"],
        "price_value": off["price_value"],
        "price_text": off["price_text"],
        "is_available": True,
        "flags": None,
        "url": "https://www.autodoc.ru/man/657/part/6RU698151",
        "scraped_at": now,
    }]
    write_jsonl(OUT / "autodoc-demo.jsonl", out)


def rossko_to_jsonl() -> None:
    parsed = parse_rossko(FIXTURES / "rossko.html")
    sku = "6RU698151"
    now = datetime.now(timezone.utc).isoformat()
    out = []
    for off in parsed["offers"]:
        out.append({
            "source": "rossko",
            "sku": sku,
            "brand": off["brand"],
            "name": off["name"],
            "price_value": off["price_value"],
            "price_text": off["price_text"],
            "is_available": off["is_available"],
            "flags": off["flags"],
            "url": "https://rossko.ru/single/search/?q=6RU698151",
            "scraped_at": now,
        })
    write_jsonl(OUT / "rossko-demo.jsonl", out)


if __name__ == "__main__":
    print("[i] Генерирую JSONL из фикстур...")
    exist_to_jsonl()
    autodoc_to_jsonl()
    rossko_to_jsonl()
    print("\n[i] Запускаю aggregator...")
    os.system(f'py "{WORKSPACE}/tools/aggregator.py" '
              f'--exist "{OUT}/exist-demo.jsonl" '
              f'--autodoc "{OUT}/autodoc-demo.jsonl" '
              f'--rossko "{OUT}/rossko-demo.jsonl" '
              f'--sku 6RU698151 '
              f'--out "{OUT}/aggregated-demo.json"')
