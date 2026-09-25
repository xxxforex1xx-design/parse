"""Парсинг результатов Exist через живой DOM (page.evaluate).

Exist использует Vue.js — цены появляются в DOM только после JS-рендера.
BeautifulSoup читает raw HTML до рендера. Поэтому идём через page.evaluate.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

from playwright.sync_api import sync_playwright  # noqa: E402

SKU = sys.argv[1] if len(sys.argv) > 1 else "6RU698151"
CATALOG_PREF = sys.argv[2] if len(sys.argv) > 2 else "VAG"

OUT_DIR = Path("tools/fixtures")
OUT_DIR.mkdir(parents=True, exist_ok=True)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)

# JS-функция, которая идёт по DOM и достаёт все видимые офферы.
# Возвращает массив объектов с типизированными полями.
EXTRACT_OFFERS_JS = r"""
() => {
  const text = (el) => (el ? (el.innerText || el.textContent || '').trim() : null);
  const cleanNum = (s) => {
    if (!s) return null;
    const m = s.replace(/[^\d.,]/g, '').replace(/[ \s]/g, '').replace(',', '.');
    const n = parseFloat(m);
    return Number.isFinite(n) ? n : null;
  };

  const offers = [];

  // 1. Прямой селектор: строки с ценами Exist имеют класс .pricerow
  document.querySelectorAll('.pricerow').forEach((row, idx) => {
    if (idx >= 60) return;
    const brand = text(row.querySelector('.bname, [class*="brand" i], .brand-name'));
    const art = text(row.querySelector('.pcode, [class*="art" i], .article'));
    const descr = text(row.querySelector('.description, .name, [class*="name" i]'));
    const priceText = text(row.querySelector('.price, [class*="price" i]'));
    const availability = text(row.querySelector('[class*="stock" i], [class*="avail" i], [class*="in_stock" i]'));
    const delivery = text(row.querySelector('[class*="deliv" i], [class*="term" i]'));
    offers.push({
      source: 'pricerow',
      brand, art, descr, priceText, availability, delivery,
      priceValue: cleanNum(priceText),
    });
  });

  // 2. Альтернативный: tr в таблицах с ценой
  if (offers.length === 0) {
    document.querySelectorAll('table tr').forEach((row) => {
      const cells = Array.from(row.querySelectorAll('td')).map(td => text(td));
      const hasPrice = cells.some(c => c && /\d{2,}/.test(c) && /(руб|₽)/.test(row.innerText));
      if (hasPrice && cells.length >= 2) {
        offers.push({
          source: 'table-row',
          cells,
        });
      }
    });
  }

  // 3. Совсем общий: любой элемент с числом и «руб»
  if (offers.length === 0) {
    const seen = new Set();
    document.querySelectorAll('div, span, td').forEach((el) => {
      const t = el.innerText || '';
      const m = t.match(/(\d[\d  \xa0]*[.,]\d{2})\s*(?:руб|RUR|₽)/);
      if (!m || el.children.length > 5) return;
      const key = t.slice(0, 60);
      if (seen.has(key)) return;
      seen.add(key);
      const parent = el.closest('div[class*="row" i], tr, .pricerow') || el.parentElement;
      offers.push({
        source: 'generic',
        snippet: t.slice(0, 200),
        parentText: parent ? parent.innerText.slice(0, 300) : null,
        priceValue: cleanNum(m[1]),
      });
    });
  }

  // 4. Служебные данные: число найденных предложений
  const totalText = (document.querySelector('[class*="total" i], [class*="count" i]') || {}).innerText;
  const title = document.title;
  const h1 = document.querySelector('h1')?.innerText?.trim();

  return { title, h1, totalText, offersCount: offers.length, offers: offers.slice(0, 60) };
}
"""


def main() -> int:
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

        # Шаг 1: главная
        page.goto("https://www.exist.ru/", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1500)

        # Шаг 2: ввод SKU
        page.locator("#pcode, input[name='pcode']").first.fill(SKU)
        page.locator("#pcode, input[name='pcode']").first.press("Enter")
        page.wait_for_load_state("domcontentloaded", timeout=20000)
        page.wait_for_timeout(3000)

        # Шаг 3: выбор каталога
        cat_link = page.locator(f"a:has-text('{CATALOG_PREF}')").first
        cat_link.click(timeout=8000)
        page.wait_for_load_state("domcontentloaded", timeout=20000)
        # Главное: даём Vue время отрендерить
        page.wait_for_timeout(5000)

        print(f"[i] Final URL: {page.url}")
        print(f"[i] Title: {page.title()}")

        # Шаг 4: парсим через page.evaluate на ЖИВОМ DOM
        print(f"[i] Запускаю page.evaluate для извлечения офферов из DOM…")
        result = page.evaluate(EXTRACT_OFFERS_JS)

        # Дополнительно: проверим, отрендерился ли Vue. Ищем элементы с ценами.
        rendered_check = page.evaluate("""
            () => {
              const pricerows = document.querySelectorAll('.pricerow').length;
              const allWithRub = Array.from(document.querySelectorAll('*'))
                .filter(el => el.innerText && /\\d[\\d  ]*[.,]\\d{2}\\s*(?:руб|₽)/.test(el.innerText))
                .length;
              return { pricerows, allWithRub };
            }
        """)

        # Сохраняем финальный HTML (для отчёта, если что-то не так)
        final_html = page.content()
        (OUT_DIR / f"exist-final-{SKU}.html").write_text(final_html, encoding="utf-8")
        page.screenshot(path=str(OUT_DIR / f"exist-final-{SKU}.png"), full_page=False)

        browser.close()

    elapsed = time.monotonic() - t0

    # ── Вывод
    print(f"\n--- DOM CHECK ---")
    print(f"  .pricerow элементов: {rendered_check['pricerows']}")
    print(f"  Элементов с «руб» в innerText: {rendered_check['allWithRub']}")

    print(f"\n--- RESULT ---")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    out_json = OUT_DIR / f"exist-offers-{SKU}.json"
    out_json.write_text(json.dumps({
        "sku": SKU,
        "catalog": CATALOG_PREF,
        "url": result.get("url", ""),
        "dom_check": rendered_check,
        "result": result,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[+] JSON сохранён: {out_json}")
    print(f"[i] Готово за {elapsed:.1f}с")
    return 0


if __name__ == "__main__":
    sys.exit(main())
