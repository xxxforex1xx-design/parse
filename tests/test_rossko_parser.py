"""Тесты парсера Rossko (BeautifulSoup-вариант)."""

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

from bs4_rossko_parser import parse_file  # noqa: E402

FIXTURE = WORKSPACE / "tests" / "fixtures" / "rossko.html"


def test_fixture_exists():
    assert FIXTURE.exists(), f"Fixture not found: {FIXTURE}"
    assert FIXTURE.stat().st_size > 50_000, "Fixture слишком маленькая"


def test_title_and_h1():
    parsed = parse_file(FIXTURE)
    assert parsed["title"] is not None
    assert "РОССКО" in parsed["title"] or "Rossko" in parsed["title"]
    assert parsed["h1"] is not None
    assert "6RU698151" in parsed["h1"] or "6RU 698 151" in parsed["h1"]


def test_offers_count():
    parsed = parse_file(FIXTURE)
    assert parsed["offers_count"] >= 5, (
        f"Rossko должен показать минимум 5 брендов, получили {parsed['offers_count']}"
    )


def test_known_brands_present():
    """Rossko для 6RU698151 должен показать VAG, ABS, Vite, Porsche."""
    parsed = parse_file(FIXTURE)
    brands = {o["brand"] for o in parsed["offers"] if o["brand"]}
    expected = {"VAG", "ABS", "Vite", "Porsche"}
    missing = expected - brands
    assert not missing, f"Не найдены бренды: {missing}"


def test_vag_offer_is_cheapest():
    """VAG-оригинал на Rossko от 894 ₽ — это дешевле Exist и Autodoc."""
    parsed = parse_file(FIXTURE)
    vag = next((o for o in parsed["offers"] if o["brand"] == "VAG"), None)
    assert vag is not None, "VAG-оффер не найден"
    assert vag["price_value"] is not None
    assert vag["price_value"] < 1000, (
        f"VAG должен быть от 894 ₽, получили {vag['price_value']}"
    )


def test_available_and_unavailable_offers():
    """Rossko для 6RU698151: VAG есть, ABS/Vite нет в наличии."""
    parsed = parse_file(FIXTURE)
    vag = next((o for o in parsed["offers"] if o["brand"] == "VAG"), None)
    abs_ = next((o for o in parsed["offers"] if o["brand"] == "ABS"), None)
    assert vag is not None and vag["is_available"] is True
    assert abs_ is not None and abs_["is_available"] is False


def test_variants_count_for_vag():
    """VAG должен иметь 15 вариантов."""
    parsed = parse_file(FIXTURE)
    vag = next((o for o in parsed["offers"] if o["brand"] == "VAG"), None)
    assert vag is not None
    assert vag["variants_count"] == 15, (
        f"Ожидалось 15 вариантов, получили {vag['variants_count']}"
    )


def test_compare_rossko_with_exist():
    """Rossko VAG (894 ₽) должен быть дешевле Exist VAG (11 629 ₽)."""
    parsed = parse_file(FIXTURE)
    vag = next((o for o in parsed["offers"] if o["brand"] == "VAG"), None)
    assert vag is not None
    assert vag["price_value"] < 11_629, (
        f"Rossko VAG ({vag['price_value']}) должен быть дешевле Exist VAG (11 629)"
    )
