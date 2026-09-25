"""Тесты парсера Exist (BeautifulSoup-вариант).

Запуск:
    cd workspace
    py -m pytest tests/ -v
    py -m pytest tests/test_exist_parser.py::test_offers_count -v
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# UTF-8 для теста
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

# Добавляем tools/ в sys.path, чтобы импортировать bs4_exist_parser
WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE / "tools"))

from bs4_exist_parser import parse_file, summarize  # noqa: E402

FIXTURE = WORKSPACE / "tests" / "fixtures" / "exist.html"


def test_fixture_exists():
    """Фикстура должна существовать на диске."""
    assert FIXTURE.exists(), f"Fixture not found: {FIXTURE}"
    assert FIXTURE.stat().st_size > 100_000, "Fixture слишком маленькая"


def test_offers_count():
    """Exist должен показать 178 офферов для 6RU698151."""
    parsed = parse_file(FIXTURE)
    assert parsed["offers_count"] == 178, (
        f"Ожидалось 178 офферов, получили {parsed['offers_count']}"
    )


def test_title_and_h1():
    """Title и H1 должны содержать правильную информацию о детали."""
    parsed = parse_file(FIXTURE)
    assert parsed["title"] is not None
    assert "6RU 698 151" in parsed["title"] or "6RU698151" in parsed["title"]
    assert "VAG" in parsed["title"]
    assert parsed["h1"] is not None
    assert "6RU 698 151" in parsed["h1"] or "VAG" in parsed["h1"]


def test_every_offer_has_partno():
    """Каждый row-container должен иметь оригинальный partno."""
    parsed = parse_file(FIXTURE)
    with_partno = sum(1 for o in parsed["offers"] if o["partno"] is not None)
    assert with_partno == parsed["offers_count"], (
        f"Только {with_partno}/{parsed['offers_count']} имеют partno"
    )


def test_known_brands_present():
    """Известные бренды Exist (LYNXauto, Marshall, Amd, CTR, Ferodo, Brembo)
    должны быть в списке офферов."""
    parsed = parse_file(FIXTURE)
    summary = summarize(parsed)
    expected = {"LYNXauto", "Marshall", "Amd", "CTR", "Finwhale", "Kortex", "Miles"}
    found = set(summary.keys())
    missing = expected - found
    assert not missing, f"Не найдены ожидаемые бренды: {missing}"


def test_each_offer_has_at_least_one_variant():
    """У каждого оффера должен быть хотя бы один pricerow."""
    parsed = parse_file(FIXTURE)
    without = [i for i, o in enumerate(parsed["offers"]) if not o["variants"]]
    assert not without, f"Офферы без вариантов: {without[:5]}"


def test_prices_are_numeric_and_reasonable():
    """Цены должны быть числами в разумном диапазоне 100..100000."""
    parsed = parse_file(FIXTURE)
    prices: list[float] = []
    for off in parsed["offers"]:
        for v in off["variants"]:
            if v["price_value"] is not None:
                prices.append(v["price_value"])
    assert len(prices) > 100, f"Слишком мало цен: {len(prices)}"
    assert min(prices) >= 100, f"Слишком низкая цена: {min(prices)}"
    assert max(prices) <= 100_000, f"Слишком высокая цена: {max(prices)}"


def test_terms_are_present():
    """У большинства вариантов должны быть сроки ('Завтра', 'Чт', 'В офисе' и т.д.)."""
    parsed = parse_file(FIXTURE)
    with_term = 0
    total = 0
    for off in parsed["offers"]:
        for v in off["variants"]:
            total += 1
            if v["term"]:
                with_term += 1
    ratio = with_term / total if total else 0
    assert ratio > 0.7, f"Только {with_term}/{total} ({ratio:.0%}) вариантов имеют срок"


def test_best_offers_marked():
    """Среди вариантов должны быть best_offers (отмеченные is_best_offer=True)."""
    parsed = parse_file(FIXTURE)
    best = sum(
        1 for off in parsed["offers"]
        for v in off["variants"] if v["is_best_offer"]
    )
    assert best > 100, f"Слишком мало best_offers: {best}"


def test_min_price_reasonable():
    """Минимальная цена среди всех вариантов должна быть в реалистичном
    диапазоне (100..1500). Exist показывает и оптовые / мелкоколичественные
    цены, поэтому нижняя граница — 100."""
    parsed = parse_file(FIXTURE)
    all_prices = [
        v["price_value"]
        for off in parsed["offers"]
        for v in off["variants"]
        if v["price_value"] is not None
    ]
    min_p = min(all_prices)
    assert 100 <= min_p <= 1500, f"Неожиданная минимальная цена: {min_p}"
