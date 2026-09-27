"""Тесты aggregator.py."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE / "tools"))

from aggregator import aggregate, normalize_brand, normalize_offer  # noqa: E402


def test_normalize_brand_vag():
    """VAG, VAG Asia, VW, Volkswagen, Skoda, Audi, Seat → VAG."""
    for raw in ["VAG", "VAG Asia", "VW", "Volkswagen", "Skoda", "Audi", "Seat"]:
        assert normalize_brand(raw) == "VAG", f"Failed for {raw!r}"


def test_normalize_brand_others():
    assert normalize_brand("Porsche") == "Porsche"
    assert normalize_brand("BMW") == "BMW"
    assert normalize_brand("Mini") == "BMW"
    assert normalize_brand("Mercedes") == "Mercedes-Benz"
    assert normalize_brand("MB") == "Mercedes-Benz"
    assert normalize_brand("Toyota") == "Toyota"
    assert normalize_brand("Lexus") == "Toyota"


def test_normalize_brand_none():
    assert normalize_brand(None) is None
    assert normalize_brand("") is None
    assert normalize_brand("   ") is None


def test_normalize_offer_drops_no_price():
    """Оффер без цены отбрасывается."""
    assert normalize_offer({"source": "exist", "price_value": None}) is None
    assert normalize_offer({"source": "exist"}) is None


def test_normalize_offer_basic():
    o = {
        "source": "rossko",
        "sku": "6RU698151",
        "brand": "VAG",
        "price_value": 894,
        "price_text": "от 894 ₽",
        "flags": "ОРИГИНАЛ",
        "url": "https://rossko.ru/...",
    }
    norm = normalize_offer(o)
    assert norm is not None
    assert norm["source"] == "rossko"
    assert norm["sku"] == "6RU698151"
    assert norm["brand"] == "VAG"
    assert norm["price"] == 894.0
    assert norm["is_original"] is True
    assert norm["url"] == "https://rossko.ru/..."


def test_aggregate_three_sources():
    """Агрегация 3 источников для 6RU698151."""
    records = [
        # Exist: VAG original 11 629
        {"source": "exist", "sku": "6RU698151", "brand": "VAG",
         "price_value": 11629, "is_best_offer": True, "flags": ""},
        # Exist: Amd 998
        {"source": "exist", "sku": "6RU698151", "brand": "Amd",
         "price_value": 998, "is_best_offer": True, "flags": ""},
        # Autodoc: VAG original 6726
        {"source": "autodoc", "sku": "6RU698151", "brand": "VAG",
         "price_value": 6726, "is_available": True, "flags": ""},
        # Rossko: VAG original 894
        {"source": "rossko", "sku": "6RU698151", "brand": "VAG",
         "price_value": 894, "is_available": True, "flags": "ОРИГИНАЛ"},
        # Rossko: Vika 2217
        {"source": "rossko", "sku": "6RU698151", "brand": "Vika",
         "price_value": 2217, "is_available": True, "flags": ""},
    ]
    result = aggregate(records)
    assert result["cards_count"] == 1
    card = result["cards"][0]
    assert card["sku"] == "6RU698151"
    assert card["offers_count"] == 5
    assert card["min_price"] == 894
    assert card["max_price"] == 11629
    assert card["best_price"]["source"] == "rossko"
    assert card["best_price"]["price"] == 894
    assert card["best_original"]["brand"] == "VAG"
    assert card["best_original"]["price"] in (894, 6726, 11629)
    # VAG должен быть в brands
    vags = [b for b in card["brands"] if b["brand"] == "VAG"]
    assert len(vags) >= 1
    assert vags[0]["min_price"] == 894  # Rossko дешевле всех


def test_aggregate_filters_by_sku():
    """Если указан --sku, берём только его."""
    records = [
        {"source": "exist", "sku": "A", "brand": "X", "price_value": 100},
        {"source": "exist", "sku": "B", "brand": "Y", "price_value": 200},
    ]
    result = aggregate(records, sku="A")
    assert result["cards_count"] == 1
    assert result["cards"][0]["sku"] == "A"


def test_aggregate_empty():
    """Пустой список → пустой результат без ошибок."""
    result = aggregate([])
    assert result["cards_count"] == 0


def test_best_in_stock_excludes_unavailable():
    """best_in_stock должен быть только среди в наличии."""
    records = [
        {"source": "rossko", "sku": "X", "brand": "A", "price_value": 100,
         "is_available": False, "flags": ""},
        {"source": "autodoc", "sku": "X", "brand": "B", "price_value": 200,
         "is_available": True, "flags": ""},
    ]
    result = aggregate(records)
    card = result["cards"][0]
    assert card["best_price"]["price"] == 100  # самый дешёвый вообще
    assert card["best_in_stock"]["price"] == 200  # только в наличии


def test_brand_alias_vag_asia_normalizes_to_vag():
    """VAG Asia и VAG должны попасть в одну группу 'VAG'."""
    records = [
        {"source": "exist", "sku": "X", "brand": "VAG", "price_value": 1000,
         "is_best_offer": True, "flags": ""},
        {"source": "rossko", "sku": "X", "brand": "VAG Asia", "price_value": 1200,
         "is_available": True, "flags": ""},
    ]
    result = aggregate(records)
    card = result["cards"][0]
    assert card["brands_count"] == 1
    vag = card["brands"][0]
    assert vag["brand"] == "VAG"
    assert vag["offers_count"] == 2
    assert vag["min_price"] == 1000
    assert vag["max_price"] == 1200
    assert set(vag["sources"]) == {"exist", "rossko"}


def test_offer_url_in_best_and_brand():
    """URL самого дешёвого оффера должен быть в best_* и в brand.offer_url."""
    records = [
        {"source": "exist", "sku": "X", "brand": "VAG", "price_value": 1500,
         "is_best_offer": True, "flags": "ОРИГИНАЛ",
         "url": "https://exist.ru/Parts/X-1500"},
        {"source": "rossko", "sku": "X", "brand": "VAG", "price_value": 1200,
         "is_available": True, "flags": "ОРИГИНАЛ",
         "url": "https://rossko.ru/search?code=X-1200"},
        {"source": "rossko", "sku": "X", "brand": "AMD", "price_value": 900,
         "is_available": True, "flags": "",
         "url": "https://rossko.ru/search?code=X-AMD"},
    ]
    result = aggregate(records)
    card = result["cards"][0]

    # best_price = AMD 900 ₽ с Rossko
    assert card["best_price"]["price"] == 900
    assert card["best_price"]["url"] == "https://rossko.ru/search?code=X-AMD"

    # best_original = VAG 1200 ₽ с Rossko (дешевле, чем Exist 1500)
    assert card["best_original"]["price"] == 1200
    assert card["best_original"]["url"] == "https://rossko.ru/search?code=X-1200"

    # best_in_stock = AMD 900
    assert card["best_in_stock"]["price"] == 900

    # offer_url в brands → URL самого дешёвого оффера каждого бренда
    brands_by_name = {b["brand"]: b for b in card["brands"]}
    assert brands_by_name["VAG"]["offer_url"] == "https://rossko.ru/search?code=X-1200"
    assert brands_by_name["AMD"]["offer_url"] == "https://rossko.ru/search?code=X-AMD"


def test_offer_url_none_when_missing():
    """Если у офферов нет url — offer_url остаётся None."""
    records = [
        {"source": "rossko", "sku": "X", "brand": "VAG", "price_value": 1200,
         "is_available": True, "flags": ""},  # без url
    ]
    result = aggregate(records)
    card = result["cards"][0]
    assert card["best_price"]["url"] is None
    assert card["brands"][0]["offer_url"] is None
