"""Pure BS4-парсер страницы поиска Rossko.

Работает на сохранённой HTML-фикстуре без Playwright.
Используется в тестах.

Структура Rossko (HTML-рендер):
  DIV.goods-items
  └── DIV.goods-item (.not-available если нет в наличии)
      └── DIV.data
          ├── DIV.manufacturer      ← «VAG»
          ├── DIV.code              ← «6RU 698 151»
          ├── DIV.description       ← «Колодки тормозные дисковые, передние»
          ├── DIV.flags / .original ← «ОРИГИНАЛ»
          └── DIV.info
              └── DIV.cost
                  └── DIV.price     ← «от 894 ₽»
                  └── DIV.variants  ← «15 вариантов»
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
    """«от 894 ₽», «от 1 006,50 ₽»."""
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


def _clean_variants(s: str | None) -> int | None:
    """«15 вариантов» — ищем именно слово «вариант», иначе попадает цена."""
    if not s:
        return None
    m = re.search(r"(\d+)\s*вариант", s, re.I)
    if not m:
        # fallback: последнее число в строке
        nums = re.findall(r"\d+", s.replace("\xa0", "").replace(" ", ""))
        if nums:
            try:
                return int(nums[-1])
            except ValueError:
                return None
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def parse(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")

    title_el = soup.find("title")
    h1_el = soup.find("h1")

    offers = []
    for card in soup.select(".goods-items .goods-item"):
        # Бренд: первый .brand внутри карточки
        brand_el = card.select_one(".brand")
        brand = _text(brand_el) if brand_el else None

        # Название / описание
        name = _text(card.select_one(".name"))

        # Цена
        price_text = _text(card.select_one(".price"))
        price_value = _clean_price(price_text)

        # Варианты («15 вариантов») — в .cost или .info
        cost_text = _text(card.select_one(".cost")) or ""
        variants_count = _clean_variants(cost_text)

        # Наличие: смотрим на текст «Нет в наличии» vs «X вариантов»
        # Класс not-available у Rossko относится к доставке, а не к наличию
        # товара как такового. Считаем оффер доступным, если есть цена и
        # в тексте нет «Нет в наличии».
        full_text = _text(card) or ""
        is_available = ("Нет в наличии" not in full_text) and (price_value is not None)

        # Флаги («ОРИГИНАЛ», «ОПТИМАЛЬНЫЙ ВЫБОР», «Экономичный вариант»)
        flags_text = " ".join(
            _text(f) for f in card.select(".badge, .promo-label")
            if _text(f)
        ).strip() or None

        offers.append({
            "brand": brand,
            "name": name,
            "price_text": price_text,
            "price_value": price_value,
            "variants_count": variants_count,
            "is_available": is_available,
            "flags": flags_text,
        })

    return {
        "title": _text(title_el),
        "h1": _text(h1_el),
        "offers_count": len(offers),
        "offers": offers,
    }


def _extract_brand(text: str) -> str | None:
    """Если .manufacturer не нашёлся, берём первый токен из текста карточки."""
    # Первая строка карточки обычно — артикул, вторая — бренд
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    if len(lines) >= 2:
        return lines[1]
    return None


def _extract_code(text: str) -> str | None:
    """Первый токен из текста карточки."""
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    if lines:
        return lines[0]
    return None


def parse_file(path: Path) -> dict[str, Any]:
    return parse(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 2:
        print("Usage: py tools/bs4_rossko_parser.py <html-file>")
        sys.exit(1)

    result = parse_file(Path(sys.argv[1]))
    print(json.dumps(result, ensure_ascii=False, indent=2))
