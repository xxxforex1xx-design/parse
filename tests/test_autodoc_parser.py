"""Тесты парсера Autodoc (BeautifulSoup-вариант).

Запуск:
    cd workspace
    py -m pytest tests/test_autodoc_parser.py -v
"""

from __future__ import annotations

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

from bs4_autodoc_parser import parse_file  # noqa: E402

FIXTURE = WORKSPACE / "tests" / "fixtures" / "autodoc.html"


def test_fixture_exists():
    assert FIXTURE.exists(), f"Fixture not found: {FIXTURE}"
    assert FIXTURE.stat().st_size > 50_000, "Fixture слишком маленькая"


def test_title_and_h1():
    parsed = parse_file(FIXTURE)
    assert parsed["title"] is not None
    assert "6RU698151" in parsed["title"]
    assert "VAG" in parsed["title"]
    assert parsed["h1"] is not None
    assert "VAG" in parsed["h1"]
    assert "6RU698151" in parsed["h1"]


def test_offers_count():
    parsed = parse_file(FIXTURE)
    assert parsed["offers_count"] >= 1, "Autodoc должен показать хотя бы 1 оффер"


def test_brand_is_vag():
    parsed = parse_file(FIXTURE)
    off = parsed["offers"][0]
    assert off["brand"] == "VAG", f"Ожидался VAG, получили {off['brand']!r}"


def test_price_is_numeric():
    parsed = parse_file(FIXTURE)
    off = parsed["offers"][0]
    assert off["price_value"] is not None
    assert 1000 <= off["price_value"] <= 50_000, f"Цена вне диапазона: {off['price_value']}"


def test_stock_is_numeric():
    parsed = parse_file(FIXTURE)
    off = parsed["offers"][0]
    assert off["stock_value"] is not None
    assert off["stock_value"] >= 1


def test_delivery_options_present():
    parsed = parse_file(FIXTURE)
    off = parsed["offers"][0]
    assert off["delivery_text"] is not None
    # Типичные варианты доставки Autodoc
    text = off["delivery_text"].lower()
    assert any(opt in text for opt in ["самовывоз", "курьер", "экспресс"]), \
        f"Нет типичных вариантов доставки: {off['delivery_text']!r}"


def test_compare_with_exist():
    """Autodoc для VAG 6RU698151 должен быть дешевле Exist (по нашему
    измерению: Exist VAG = 11 629, Autodoc = 6 726)."""
    parsed = parse_file(FIXTURE)
    autodoc_price = parsed["offers"][0]["price_value"]
    # Exist VAG original — от 11 629 ₽ (см. PROJECT_STATE.md)
    exist_vag_price = 11_629
    assert autodoc_price < exist_vag_price, (
        f"Autodoc ({autodoc_price}) должен быть дешевле Exist VAG ({exist_vag_price})"
    )
