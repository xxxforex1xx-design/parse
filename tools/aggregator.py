"""Aggregator: сводит результаты Exist + Autodoc + Rossko в одну карточку.

На вход: JSONL-файлы от `rate_limited_parser.py` (по одному на источник)
        или список словарей.
На выход: нормализованная карточка с:
        - деdup по (brand, sku)
        - best_price — самый дешёвый оффер
        - best_original — самый дешёвый ОРИГИНАЛЬНЫЙ оффер
        - offers — все офферы, отсортированные по цене

Пример:
    py tools/aggregator.py \\
        --exist exist.jsonl \\
        --autodoc autodoc.jsonl \\
        --rossko rossko.jsonl \\
        --sku 6RU698151
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass


# ── Нормализация брендов ───────────────────────────────────────────────

# Нормализация: приводим к каноническому виду, объединяем OEM-варианты.
# "VAG", "VAG Asia", "VW" → "VAG"
# "BMW/Mini" → "BMW"
BRAND_ALIASES = {
    "vag": "VAG",
    "vag asia": "VAG",
    "vag europe": "VAG",
    "vw": "VAG",
    "volkswagen": "VAG",
    "skoda": "VAG",
    "audi": "VAG",
    "seat": "VAG",
    "porsche": "Porsche",
    "ford": "Ford",
    "opel": "Opel",
    "chevrolet": "Chevrolet",
    "toyota": "Toyota",
    "lexus": "Toyota",
    "nissan": "Nissan",
    "infiniti": "Nissan",
    "bmw": "BMW",
    "mini": "BMW",
    "mercedes": "Mercedes-Benz",
    "mercedes-benz": "Mercedes-Benz",
    "mb": "Mercedes-Benz",
    "hyundai": "Hyundai",
    "kia": "Kia",
}

# Что считается OEM-производителем (оригинальная деталь)
OEM_BRANDS = {"VAG", "BMW", "Mercedes-Benz", "Toyota", "Nissan", "Ford", "Opel",
              "Chevrolet", "Hyundai", "Kia", "Renault", "Peugeot", "Citroen",
              "Porsche", "Audi", "Skoda", "Volkswagen"}


def normalize_brand(brand: str | None) -> str | None:
    if not brand:
        return None
    stripped = brand.strip()
    if not stripped:
        return None
    s = stripped.lower()
    s = re.sub(r"\s+", " ", s)
    return BRAND_ALIASES.get(s, stripped)


# ── Загрузка JSONL ─────────────────────────────────────────────────────

def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


# ── Нормализация одного оффера ─────────────────────────────────────────

def normalize_offer(o: dict[str, Any]) -> dict[str, Any] | None:
    """Привести оффер к единому формату. None если цена отсутствует."""
    price = o.get("price_value")
    if price is None:
        return None

    brand = normalize_brand(o.get("brand"))
    flags = (o.get("flags") or "").upper() if isinstance(o.get("flags"), str) else ""
    is_original = "ОРИГИНАЛ" in flags or (brand in OEM_BRANDS)

    return {
        "source": o["source"],
        "sku": o.get("sku"),
        "brand": brand,
        "name": o.get("name") or o.get("descr"),
        "price": float(price),
        "price_text": o.get("price_text"),
        "in_stock": (
            o.get("is_available")
            if o.get("is_available") is not None
            else o.get("is_best_offer")  # Exist: best_offer = в наличии
        ),
        "variants": o.get("variants_count"),
        "is_original": is_original,
        "url": o.get("url"),
        "scraped_at": o.get("scraped_at"),
    }


# ── Агрегация по SKU ───────────────────────────────────────────────────

def aggregate(records: list[dict[str, Any]], sku: str | None = None) -> dict[str, Any]:
    """Сгруппировать офферы по SKU, выбрать best_price и best_original."""
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for r in records:
        if sku and r.get("sku") and r.get("sku") != sku:
            continue
        norm = normalize_offer(r)
        if norm is None:
            continue
        buckets[norm["sku"] or "(unknown)"].append(norm)

    cards = []
    for s, offers in buckets.items():
        # Сортировка по цене
        offers.sort(key=lambda o: o["price"])

        in_stock = [o for o in offers if o["in_stock"]]
        originals = [o for o in offers if o["is_original"]]

        best_price = offers[0]
        best_original = originals[0] if originals else None
        best_in_stock = in_stock[0] if in_stock else None

        # Агрегация по брендам: сколько офферов от каждого бренда
        brand_stats: dict[str, dict[str, Any]] = {}
        for o in offers:
            b = o["brand"] or "(unknown)"
            if b not in brand_stats:
                brand_stats[b] = {
                    "brand": b,
                    "offers_count": 0,
                    "min_price": o["price"],
                    "max_price": o["price"],
                    "is_original": o["is_original"],
                    "sources": set(),
                }
            s_ = brand_stats[b]
            s_["offers_count"] += 1
            s_["min_price"] = min(s_["min_price"], o["price"])
            s_["max_price"] = max(s_["max_price"], o["price"])
            s_["sources"].add(o["source"])

        brand_list = [
            {**v, "sources": sorted(v["sources"])} for v in brand_stats.values()
        ]
        brand_list.sort(key=lambda b: b["min_price"])

        cards.append({
            "sku": s,
            "offers_count": len(offers),
            "sources": sorted({o["source"] for o in offers}),
            "brands_count": len(brand_stats),
            "min_price": offers[0]["price"],
            "max_price": offers[-1]["price"],
            "best_price": best_price,
            "best_in_stock": best_in_stock,
            "best_original": best_original,
            "brands": brand_list,
        })

    cards.sort(key=lambda c: c["sku"] or "")
    return {
        "cards_count": len(cards),
        "cards": cards,
    }


# ── CLI ────────────────────────────────────────────────────────────────

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--exist", type=Path, help="JSONL с результатами Exist")
    p.add_argument("--autodoc", type=Path, help="JSONL с результатами Autodoc")
    p.add_argument("--rossko", type=Path, help="JSONL с результатами Rossko")
    p.add_argument("--sku", help="Фильтр по конкретному SKU (опционально)")
    p.add_argument("--out", type=Path, help="Куда сохранить JSON с карточками")
    args = p.parse_args()

    records: list[dict[str, Any]] = []
    for path in (args.exist, args.autodoc, args.rossko):
        if path:
            records.extend(load_jsonl(path))

    if not records:
        print("[!] Нет данных для агрегации", file=sys.stderr)
        return 1

    print(f"[i] Загружено {len(records)} записей")
    result = aggregate(records, sku=args.sku)
    print(f"[i] Карточек: {result['cards_count']}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        print(f"[+] Сохранено в {args.out}")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
