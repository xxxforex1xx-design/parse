"""Smoke-test Autodoc: Playwright + ввод SKU, медленно.

Используем тот же SKU 6RU698151, что и Exist, для сравнимости.
Autodoc robots.txt запрещает /price/* и *?* — это основной путь с ценами.
Проверяем, что реально доступно.
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

SKU = sys.argv[1] if len(sys.argv) > 1 else "6RU698151"
OUT_DIR = Path("tools/fixtures")
OUT_DIR.mkdir(parents=True, exist_ok=True)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)


def find_search_input(page):
    candidates = [
        "input[name*='search' i]",
        "input[id*='search' i]",
        "input[type='search']",
        "input[placeholder*='артикул' i]",
        "input[placeholder*='Артикул' i]",
        "input[placeholder*='номер' i]",
        "input[placeholder*='Поиск' i]",
        "input[placeholder*='поиск' i]",
        "input[name='partNumber']",
        "input[name='articleNumber']",
        "input[name='oem']",
        "input[name='sku']",
        "input[class*='search' i]",
    ]
    for sel in candidates:
        loc = page.locator(sel).first
        try:
            if loc.count() > 0 and loc.is_visible():
                return loc, sel
        except Exception:
            continue
    return None, None


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
        print("[i] Открываю https://www.autodoc.ru/")
        page.goto("https://www.autodoc.ru/", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)

        initial_title = page.title()
        initial_url = page.url
        print(f"[i] Initial: title={initial_title!r}, url={initial_url}")

        # Сохраняем скриншот главной
        page.screenshot(path=str(OUT_DIR / "autodoc-main.png"), full_page=False)

        # Шаг 2: ищем поле поиска
        search, used_sel = find_search_input(page)
        if not search:
            print("[!] Поле поиска не найдено стандартными селекторами.")
            print("[i] Все input'ы на странице:")
            for el in page.query_selector_all("input"):
                try:
                    print(f"  <{el.get_attribute('outerHTML')[:200]}>")
                except Exception:
                    pass
            page.screenshot(path=str(OUT_DIR / "autodoc-no-search.png"), full_page=True)
            browser.close()
            return 1

        print(f"[+] Поле найдено: {used_sel}")
        try:
            print(f"    HTML: {search.evaluate('el => el.outerHTML.slice(0,200)')}")
        except Exception:
            pass

        # Шаг 3: ввод SKU
        search.click()
        search.fill(SKU)
        page.wait_for_timeout(500)
        # Пробуем Enter
        try:
            with page.expect_navigation(wait_until="domcontentloaded", timeout=15000):
                search.press("Enter")
        except Exception as e:
            print(f"[?] expect_navigation: {e}")
            page.wait_for_timeout(3000)

        page.wait_for_timeout(3000)
        print(f"[i] After search: title={page.title()!r}, url={page.url}")

        # Сохраняем результат
        html = page.content()
        ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        (OUT_DIR / f"autodoc-result-{SKU}-{ts}.html").write_text(html, encoding="utf-8")
        page.screenshot(path=str(OUT_DIR / f"autodoc-result-{SKU}.png"), full_page=True)

        # Анализ: captcha? бан? redirect?
        captcha = bool(re.search(r"captcha|robot|verify.{0,20}human|antibot|cloudflare|hCaptcha|smartcaptcha", html, re.I))
        forbidden = bool(re.search(r"доступ.{0,10}запрещ|403|forbidden|access.{0,5}denied", html, re.I))

        # Цены?
        price_signals = re.findall(r"(\d[\d\s\xa0]*[.,]?\d{0,2})\s*(?:руб|₽|\<[^>]+\>руб)", html, re.I)

        print(f"\n--- VERDICT ---")
        print(f"  Captcha-маркеры: {captcha}")
        print(f"  Forbidden-маркеры: {forbidden}")
        print(f"  Найдено цен-сигналов: {len(price_signals)}")
        if price_signals:
            for p_ in price_signals[:5]:
                print(f"    {p_}")
        if page.url != initial_url:
            print(f"  URL изменился: {initial_url} → {page.url}")

        browser.close()

    elapsed = time.monotonic() - t0
    print(f"\n[i] Готово за {elapsed:.1f}с")
    return 0


if __name__ == "__main__":
    sys.exit(main())
