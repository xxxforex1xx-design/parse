"""Полный Playwright-flow Exist: ввод SKU → выбор каталога VAG → парсинг цен.

Один пользовательский сценарий (эквивалент одному реальному посетителю сайта).
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

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402

SKU = sys.argv[1] if len(sys.argv) > 1 else "6RU698151"
# Какой каталог кликать: первый в списке, либо VAG/VAG Asia явно
CATALOG_PREF = sys.argv[2] if len(sys.argv) > 2 else "VAG"

OUT_DIR = Path("tools/fixtures")
OUT_DIR.mkdir(parents=True, exist_ok=True)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)


def parse_offers(html: str) -> list[dict]:
    """Извлечь офферы из HTML Exist после выбора каталога.

    Структура Exist (типичная): таблица/список с колонками
    Бренд | Артикул | Описание | Срок | Цена | Наличие.
    """
    soup = BeautifulSoup(html, "html.parser")
    offers: list[dict] = []

    # Подход 1: типичные селекторы офферов Exist
    rows = (
        soup.select("tr.offer, tr[class*='offer' i]")
        or soup.select("div.offer, div[class*='offer-item' i]")
        or soup.select("[data-offer-id], [data-brand]")
    )

    # Подход 2: если rows пусто — попробуем любую таблицу с ценами
    if not rows:
        tables = soup.select("table")
        for tbl in tables:
            t_rows = tbl.select("tbody tr")
            if len(t_rows) >= 2:
                rows = t_rows
                break

    for r in rows:
        text = r.get_text(" | ", strip=True)
        if not text:
            continue
        # Цена — первое число с «руб» или ₽
        price_match = re.search(
            r"(\d{1,3}(?:[\s\xa0]\d{3})*(?:[\.,]\d{1,2})?)\s*(?:руб|RUR|₽)",
            text,
        )
        price = price_match.group(0).strip() if price_match else None
        # Наличие — слова «в наличии», «под заказ», «есть», «ожидание»
        avail_match = re.search(
            r"(в наличии|под заказ|есть|ожидается|нет в наличии|мало|много)",
            text,
            re.I,
        )
        availability = avail_match.group(0) if avail_match else None
        # Срок доставки — обычно «X дн.»
        term_match = re.search(r"(\d+)\s*(?:дн|день|дня|дней)", text)
        delivery = f"{term_match.group(1)} дн." if term_match else None

        offers.append({
            "raw": text[:300],
            "price": price,
            "availability": availability,
            "delivery_days": delivery,
        })

    return offers


def main() -> int:
    t0 = time.monotonic()
    print(f"[i] Запуск Chromium…")
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

        # ── Шаг 1: главная Exist
        print("[i] Шаг 1: открываю https://www.exist.ru/")
        page.goto("https://www.exist.ru/", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1500)

        # ── Шаг 2: ввод SKU
        print(f"[i] Шаг 2: ввожу SKU={SKU}")
        search = page.locator("#pcode, input[name='pcode'], input[type='search']").first
        search.click()
        search.fill(SKU)
        page.wait_for_timeout(500)
        search.press("Enter")

        # Ждём страницу выбора каталога
        page.wait_for_load_state("domcontentloaded", timeout=20000)
        page.wait_for_timeout(2500)
        print(f"[i] Шаг 2 готово. URL={page.url}, title={page.title()!r}")

        # Сохраняем страницу выбора каталога для отчёта
        choice_html = page.content()
        (OUT_DIR / f"exist-flow-1-catalog-{SKU}.html").write_text(choice_html, encoding="utf-8")
        page.screenshot(path=str(OUT_DIR / f"exist-flow-1-catalog-{SKU}.png"), full_page=True)

        # ── Шаг 3: кликнуть на «VAG» (или другой каталог по предпочтению)
        print(f"[i] Шаг 3: ищу ссылку на каталог «{CATALOG_PREF}»")

        # Селекторы для ссылок каталога — Exist использует ссылки в списке опций
        cat_link = page.locator(f"a:has-text('{CATALOG_PREF}')").first
        if cat_link.count() == 0:
            # Альтернатива: кликнуть по тексту в любом теге
            cat_link = page.locator(f":text('{CATALOG_PREF}')").first
        if cat_link.count() == 0:
            print(f"[!] Не нашёл ссылку на «{CATALOG_PREF}». Пробую первый элемент списка.")
            cat_link = page.locator(".catalog-link, .select-catalog a, [class*='catalog' i] a").first

        try:
            cat_link.click(timeout=5000)
        except Exception as e:
            print(f"[!] Не удалось кликнуть каталог: {e}")
            page.screenshot(path=str(OUT_DIR / f"exist-flow-FAIL-{SKU}.png"), full_page=True)
            browser.close()
            return 1

        page.wait_for_load_state("domcontentloaded", timeout=20000)
        page.wait_for_timeout(3000)
        print(f"[i] Шаг 3 готово. URL={page.url}, title={page.title()!r}")

        # ── Шаг 4: парсинг результатов
        result_html = page.content()
        page.screenshot(path=str(OUT_DIR / f"exist-flow-2-results-{SKU}.png"), full_page=True)
        (OUT_DIR / f"exist-flow-2-results-{SKU}.html").write_text(result_html, encoding="utf-8")
        print(f"[i] HTML: {len(result_html)} chars")

        offers = parse_offers(result_html)
        print(f"[+] Найдено офферов: {len(offers)}")

        # Дополнительно: ищем общую информацию о товаре
        soup = BeautifulSoup(result_html, "html.parser")
        h1 = soup.h1.get_text(strip=True) if soup.h1 else None
        title = soup.title.string.strip() if soup.title and soup.title.string else None

        # ── Сохраняем итог
        result = {
            "sku": SKU,
            "catalog_chosen": CATALOG_PREF,
            "title": title,
            "h1": h1,
            "final_url": page.url,
            "offers_count": len(offers),
            "offers": offers[:20],
        }
        out_json = OUT_DIR / f"exist-flow-result-{SKU}.json"
        out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[+] JSON: {out_json}")

        print(f"\nTitle: {title}")
        print(f"H1: {h1}")
        print(f"URL: {page.url}")
        print(f"Офферов: {len(offers)}")
        for i, off in enumerate(offers[:6], 1):
            print(f"  [{i}] {off['price'] or '—'} · {off['availability'] or '—'} · {off['delivery_days'] or '—'}")
            print(f"      {off['raw'][:150]}")

        browser.close()

    elapsed = time.monotonic() - t0
    print(f"\n[i] Готово за {elapsed:.1f}с")
    return 0


if __name__ == "__main__":
    sys.exit(main())
