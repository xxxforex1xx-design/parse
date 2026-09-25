"""Финальный парсер Exist через Playwright + page.evaluate.

Структура страницы (Vue-рендер):
  DIV.table-body
  └── DIV.row-container        ← один оффер = бренд + один/несколько вариантов
      ├── DIV.name-container
      │   ├── DIV.brand        ← «LYNXauto»
      │   ├── DIV.art          ← Exist-артикул «E6......BP»
      │   ├── DIV.partno       ← оригинальный «6RU 698 151»
      │   └── DIV.description  ← название детали
      ├── DIV.bestOffers       ← блок «Лучшие предложения»
      │   └── DIV.pricerow ×N  ← каждый = срок + цена
      └── DIV.allOffers        ← остальные варианты
          └── DIV.pricerow ×N

Использование:
    py tools/exist_parser.py 6RU698151
    py tools/exist_parser.py 6RU698151 --catalog "VAG Asia"
    py tools/exist_parser.py 6RU698151 --out result.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

from playwright.sync_api import sync_playwright  # noqa: E402

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)

# JS, который идёт по .row-container и достаёт офферы.
PARSE_OFFERS_JS = r"""
() => {
  const text = (el) => (el ? (el.innerText || el.textContent || '').trim() : null);
  const cleanNum = (s) => {
    if (!s) return null;
    const m = s.replace(/[^\d.,]/g, '').replace(/\s/g, '').replace(',', '.');
    const n = parseFloat(m);
    return Number.isFinite(n) ? n : null;
  };

  const offers = [];
  document.querySelectorAll('.table-body .row-container').forEach((rc) => {
    const nameContainer = rc.querySelector('.name-container');
    const brand = text(nameContainer && nameContainer.querySelector('.brand'));
    const art = text(nameContainer && nameContainer.querySelector('.art'));
    const partno = text(nameContainer && nameContainer.querySelector('.partno'));
    const descr = text(nameContainer && nameContainer.querySelector('.description'));

    const variants = [];
    rc.querySelectorAll('.pricerow').forEach((pr) => {
      const term = text(pr.querySelector('.params'));
      const priceText = text(pr.querySelector('.price__wrapper'));
      const isBest = !!pr.closest('.bestOffers');
      variants.push({
        term,
        price_text: priceText,
        price_value: cleanNum(priceText),
        is_best_offer: isBest,
      });
    });

    offers.push({ brand, art, partno, descr, variants });
  });

  return {
    title: document.title,
    h1: (document.querySelector('h1') || {}).innerText,
    total_offers_text: (document.querySelector('[class*="total" i]') || {}).innerText,
    offers_count: offers.length,
    offers,
  };
}
"""


def run(sku: str, catalog_pref: str, out_path: Path | None) -> dict[str, Any]:
    t0 = time.monotonic()
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(
            user_agent=UA,
            locale="ru-RU",
            timezone_id="Europe/Moscow",
            viewport={"width": 1366, "height": 900},
            extra_http_headers={"Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7"},
        )
        ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        page = ctx.new_page()

        page.goto("https://www.exist.ru/", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1500)

        page.locator("#pcode").first.fill(sku)
        page.locator("#pcode").first.press("Enter")
        page.wait_for_load_state("domcontentloaded", timeout=20000)
        page.wait_for_timeout(3000)

        # Если есть опции каталога — кликаем предпочтительную
        try:
            cat_link = page.locator(f"a:has-text('{catalog_pref}')").first
            if cat_link.count() > 0:
                cat_link.click(timeout=8000)
                page.wait_for_load_state("domcontentloaded", timeout=20000)
                page.wait_for_timeout(5000)
        except Exception:
            pass

        result = page.evaluate(PARSE_OFFERS_JS)
        result["sku"] = sku
        result["catalog"] = catalog_pref
        result["final_url"] = page.url
        result["elapsed_sec"] = round(time.monotonic() - t0, 1)

        browser.close()

    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("sku", help="Артикул для поиска")
    parser.add_argument("--catalog", default="VAG", help="Предпочтительный каталог")
    parser.add_argument("--out", type=Path, default=None, help="Куда сохранить JSON")
    args = parser.parse_args()

    result = run(args.sku, args.catalog, args.out)

    print(f"SKU: {result['sku']}")
    print(f"Catalog: {result['catalog']}")
    print(f"Title: {result['title']}")
    print(f"H1: {result.get('h1')}")
    print(f"Total: {result.get('total_offers_text')}")
    print(f"Офферов (брендов): {result['offers_count']}")
    print(f"Время: {result['elapsed_sec']}с")
    print()
    for i, off in enumerate(result["offers"][:10], 1):
        print(f"[{i}] {off['brand'] or '—'} · {off['art'] or '—'} · {off['descr'] or '—'}")
        for v in off["variants"][:3]:
            tag = "★" if v["is_best_offer"] else "·"
            print(f"    {tag} {v['price_text']} (срок: {v['term']})")

    if args.out:
        print(f"\n[+] JSON: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
