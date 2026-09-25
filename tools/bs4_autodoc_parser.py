"""Pure BS4-парсер страницы карточки Autodoc.

Работает на сохранённой HTML-фикстуре без Playwright.
Используется в тестах.

Структура карточки (Angular-рендер):
  DIV.grid.card
  ├── DIV.card__info
  │   ├── H5.card__name              ← название товара
  │   └── DIV.card__manufacturer     ← «VAG\nПроизводитель»
  ├── DIV.card__price
  │   ├── DIV.card__price-wrapper
  │   │   └── A.card__price-link     ← «от 6 726 ₽»
  │   └── DIV.card__price-stock      ← «В наличии 79 шт»
  └── DIV.card__delivery             ← способы доставки
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup


def _text(el) -> str | None:
    if el is None:
        return None
    s = el.get_text(" ", strip=True)
    return s or None


def _clean_price(s: str | None) -> float | None:
    """Извлечь цену: «от 6 726 ₽», «от 1 006,50 ₽»."""
    if not s:
        return None
    s_clean = re.sub(r"[^\d\s\xa0.,]", "", s)
    m = re.search(r"\d+(?:[\s\xa0]?\d{3})*(?:[.,]\d{1,2})?", s_clean)
    if not m:
        return None
    num = m.group(0).replace("\xa0", "").replace(" ", "").replace(",", ".")
    try:
        return float(num)
    except ValueError:
        return None


def _clean_stock(s: str | None) -> int | None:
    """Извлечь количество: «В наличии 79 шт»."""
    if not s:
        return None
    m = re.search(r"(\d+)", s.replace("\xa0", "").replace(" ", ""))
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def _clean_brand(s: str | None) -> str | None:
    """«VAG Производитель» / «VAG\nПроизводитель» → «VAG»."""
    if not s:
        return None
    # BS4 get_text(" ") склеивает через пробел — режем по «Производитель»
    for sep in ["Производитель", "\n"]:
        if sep in s:
            s = s.split(sep)[0].strip()
    return s or None


def parse(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")

    title_el = soup.find("title")
    h1_el = soup.find("h1")

    card = soup.select_one(".grid.card")
    if not card:
        return {
            "title": _text(title_el),
            "h1": _text(h1_el),
            "error": "Card not found (.grid.card)",
            "offers": [],
        }

    name = _text(card.select_one(".card__name"))
    brand_raw = _text(card.select_one(".card__manufacturer"))
    brand = _clean_brand(brand_raw)
    price_text = _text(card.select_one(".card__price-link"))
    stock_text = _text(card.select_one(".card__price-stock"))
    delivery_text = _text(card.select_one(".card__delivery"))

    offers = [{
        "name": name,
        "brand": brand,
        "price_text": price_text,
        "price_value": _clean_price(price_text),
        "stock_text": stock_text,
        "stock_value": _clean_stock(stock_text),
        "delivery_text": delivery_text,
    }]

    return {
        "title": _text(title_el),
        "h1": _text(h1_el),
        "offers_count": len(offers),
        "offers": offers,
    }


def parse_file(path: Path) -> dict[str, Any]:
    return parse(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 2:
        print("Usage: py tools/bs4_autodoc_parser.py <html-file>")
        sys.exit(1)

    result = parse_file(Path(sys.argv[1]))
    print(json.dumps(result, ensure_ascii=False, indent=2))
