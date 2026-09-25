"""Playwright smoke-test Exist: проходим search flow.

Что делаем:
1. Открываем https://www.exist.ru/
2. Находим поле поиска
3. Вводим SKU
4. Нажимаем Enter
5. Ждём результаты
6. Сохраняем HTML + скриншот
7. Парсим цены

Без stealth — новый Playwright сам маскирует navigator.webdriver.
"""

from __future__ import annotations

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
from bs4 import BeautifulSoup  # noqa: E402

SKU = sys.argv[1] if len(sys.argv) > 1 else "6RU698151"

OUT_DIR = Path("tools/fixtures")
OUT_DIR.mkdir(parents=True, exist_ok=True)
SCREENSHOT = OUT_DIR / f"exist-playwright-{SKU}.png"
HTML_DUMP = OUT_DIR / f"exist-playwright-{SKU}.html"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)


def parse_prices(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    found: list[str] = []
    # Типичные селекторы карточки Exist
    for sel in [
        "[class*='price-value' i]",
        "[class*='PriceValue' i]",
        "[data-role='price']",
        ".offer-price",
        "[class*='price' i] > span",
    ]:
        for el in soup.select(sel):
            txt = el.get_text(strip=True)
            if txt and re.search(r"\d", txt):
                found.append(f"[{sel}] {txt}")
    # Резервный regex
    for m in re.findall(r"(\d{1,3}(?:[\s\xa0]\d{3})*(?:[\.,]\d{1,2})?)\s*(?:руб|RUR|₽)", html):
        found.append(f"[regex] {m}")
    return found


def find_search_input(page):
    """Несколько вариантов селекторов для поля поиска Exist."""
    candidates = [
        "input[id*='search' i]",
        "input[name*='search' i]",
        "input[placeholder*='артикул' i]",
        "input[placeholder*='Артикул' i]",
        "input[placeholder*='Поиск' i]",
        "input[id*='pcode' i]",
        "input[name='pcode']",
        "input[type='search']",
        "#searchInput",
        ".search-input",
    ]
    for sel in candidates:
        loc = page.locator(sel).first
        try:
            if loc.count() > 0 and loc.is_visible():
                return loc
        except Exception:
            continue
    return None


def main() -> int:
    t0 = time.monotonic()
    print(f"[i] Запускаю Playwright Chromium…")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(
            user_agent=UA,
            locale="ru-RU",
            timezone_id="Europe/Moscow",
            viewport={"width": 1366, "height": 900},
            extra_http_headers={
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7",
                "DNT": "1",
            },
        )
        # Скрываем webdriver через init script (минимальный stealth)
        ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        page = ctx.new_page()

        print("[i] Открываю https://www.exist.ru/")
        page.goto("https://www.exist.ru/", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)

        # Сохраняем стартовое состояние
        initial_html = page.content()
        print(f"[i] Initial: {len(initial_html)} chars, title={page.title()!r}")

        # Ищем поле поиска
        print(f"[i] Ищу поле поиска для SKU={SKU}")
        search = find_search_input(page)
        if not search:
            print("[!] Поле поиска не найдено. Сохраняю скриншот и HTML для анализа.")
            page.screenshot(path=str(SCREENSHOT), full_page=True)
            HTML_DUMP.write_text(initial_html, encoding="utf-8")
            browser.close()
            return 1

        # Вводим SKU
        print(f"[+] Поле найдено: <{search.evaluate('el => el.outerHTML.slice(0,200)')}>")
        search.click()
        search.fill(SKU)
        page.wait_for_timeout(500)

        # Пробуем отправить через Enter
        try:
            with page.expect_navigation(wait_until="domcontentloaded", timeout=15000):
                search.press("Enter")
        except Exception as e:
            print(f"[?] expect_navigation поймал: {e}")
            # Возможно SPA — просто ждём
            page.wait_for_timeout(3000)

        page.wait_for_timeout(2000)
        after_html = page.content()
        print(f"[i] After search: {len(after_html)} chars, title={page.title()!r}")
        print(f"[i] Final URL: {page.url}")

        page.screenshot(path=str(SCREENSHOT), full_page=True)
        HTML_DUMP.write_text(after_html, encoding="utf-8")
        print(f"[+] Скриншот: {SCREENSHOT}")
        print(f"[+] HTML: {HTML_DUMP}")

        # Ищем признаки результата
        prices = parse_prices(after_html)
        print(f"[i] Цены найдены: {len(prices)}")
        for p_ in prices[:8]:
            print(f"  {p_}")

        # Капча?
        captcha = bool(re.search(r"captcha|robot|verify.{0,20}human|antibot", after_html, re.I))
        if captcha:
            print("[!] Captcha обнаружена в HTML — нужен stealth или ручной обход.")
        if "Выберите каталог" in after_html:
            print("[?] Снова экран выбора каталога.")

        browser.close()

    elapsed = time.monotonic() - t0
    print(f"\n[i] Готово за {elapsed:.1f}с")
    return 0


if __name__ == "__main__":
    sys.exit(main())
