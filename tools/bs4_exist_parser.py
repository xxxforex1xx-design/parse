"""Pure BS4-парсер страницы результатов Exist.

Работает на сохранённой HTML-фикстуре (без Playwright и без сети).
Используется в тестах и как fallback, если Playwright недоступен.

Структура Exist (Vue-рендер):
  DIV.table-body
  └── DIV.row-container        ← один оффер = бренд + варианты
      ├── DIV.name-container
      │   ├── DIV.brand        ← «LYNXauto», «Marshall»
      │   ├── DIV.art          ← Exist-артикул или короткое имя
      │   ├── DIV.partno       ← оригинальный OEM-артикул
      │   └── DIV.description  ← название детали
      ├── DIV.bestOffers       ← «Лучшие предложения»
      │   └── DIV.pricerow ×N  ← срок + цена
      └── DIV.allOffers        ← остальные варианты
          └── DIV.pricerow ×N
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
    """Извлечь цену из текста Exist.

    Формат Exist: «от 11 629 ₽», «от 1 006 ₽», иногда с копейками «1 006,50 ₽».
    Разделитель тысяч: NBSP (\xa0) или обычный пробел.
    Десятичный: запятая или точка.
    """
    if not s:
        return None
    # Удаляем «от», «руб», «₽», прочие слова
    s_clean = re.sub(r"[^\d\s\xa0.,]", "", s)
    # Ищем число: цифры + опционально разделитель тысяч + опционально копейки
    m = re.search(r"\d+(?:[\s\xa0]?\d{3})*(?:[.,]\d{1,2})?", s_clean)
    if not m:
        return None
    num = m.group(0).replace("\xa0", "").replace(" ", "").replace(",", ".")
    try:
        return float(num)
    except ValueError:
        return None


def parse(html: str) -> dict[str, Any]:
    """Возвращает распарсенные данные офферов из HTML Exist."""
    soup = BeautifulSoup(html, "html.parser")

    title_el = soup.find("title")
    h1_el = soup.find("h1")

    offers: list[dict[str, Any]] = []
    for rc in soup.select(".table-body .row-container"):
        name = rc.select_one(".name-container")
        brand = _text(name and name.select_one(".brand")) if name else None
        art = _text(name and name.select_one(".art")) if name else None
        partno = _text(name and name.select_one(".partno")) if name else None
        descr = _text(name and name.select_one(".description")) if name else None

        variants = []
        for pr in rc.select(".pricerow"):
            term_el = pr.select_one(".params")
            price_el = pr.select_one(".price__wrapper")
            is_best = pr.find_parent(class_=re.compile(r"bestOffers")) is not None
            variants.append({
                "term": _text(term_el),
                "price_text": _text(price_el),
                "price_value": _clean_price(_text(price_el)),
                "is_best_offer": is_best,
            })

        offers.append({
            "brand": brand,
            "art": art,
            "partno": partno,
            "descr": descr,
            "variants": variants,
        })

    return {
        "title": _text(title_el),
        "h1": _text(h1_el),
        "offers_count": len(offers),
        "offers": offers,
    }


def parse_file(path: Path) -> dict[str, Any]:
    """Прочитать HTML-файл и распарсить."""
    return parse(path.read_text(encoding="utf-8"))


def summarize(parsed: dict[str, Any]) -> dict[str, Any]:
    """Краткая сводка по офферам для быстрой проверки в тестах."""
    by_brand: dict[str, dict[str, Any]] = {}
    for off in parsed["offers"]:
        brand = off["brand"] or off["art"] or "(unknown)"
        variants = off["variants"]
        prices = [v["price_value"] for v in variants if v["price_value"] is not None]
        terms = [v["term"] for v in variants if v["term"]]
        by_brand[brand] = {
            "variants_count": len(variants),
            "min_price": min(prices) if prices else None,
            "max_price": max(prices) if prices else None,
            "terms": terms[:5],
        }
    return by_brand


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 2:
        print("Usage: py tools/bs4_exist_parser.py <html-file>")
        sys.exit(1)

    parsed = parse_file(Path(sys.argv[1]))
    summary = summarize(parsed)
    # ASCII-safe вывод: cp1251 в Windows-консоли не любит кириллицу/символ ₽
    print(f"Title: {parsed['title']}")
    print(f"Offers: {parsed['offers_count']}")
    print()
    for brand, info in list(summary.items())[:15]:
        prices = []
        if info['min_price'] is not None:
            prices.append(f"{info['min_price']:.0f}")
        if info['max_price'] is not None and info['max_price'] != info['min_price']:
            prices.append(f"{info['max_price']:.0f}")
        price_str = "..".join(prices) if prices else "n/a"
        print(f"  {brand}: {info['variants_count']} variants, {price_str} RUB")
