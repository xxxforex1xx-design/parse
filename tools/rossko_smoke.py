"""Rossko smoke-test: Playwright + ввод SKU.

Из recon:
- B2B API (api.rossko.ru) — требует ключей, регистрация
- Поиск /search/ закрыт в robots.txt
- /catalog/?page= открыт
- Партнёрки через Admitad есть

Цель: проверить, есть ли прямой URL карточки, как у Autodoc.
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
        )
        ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        page = ctx.new_page()

        print("[i] Открываю https://rossko.ru/")
        page.goto("https://rossko.ru/", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)
        print(f"[i] Title: {page.title()!r}")

        page.screenshot(path=str(OUT_DIR / "rossko-main.png"), full_page=False)

        # Ищем поле поиска гибко
        try:
            page.wait_for_function(
                "() => document.querySelectorAll('input').length > 1",
                timeout=15000,
            )
        except Exception:
            pass
        page.wait_for_timeout(2000)

        INSPECT_JS = """
        () => {
          const inputs = Array.from(document.querySelectorAll('input')).map(el => ({
            type: el.type,
            name: el.name || null,
            id: el.id || null,
            placeholder: el.placeholder || null,
            visible: !!(el.offsetWidth || el.offsetHeight),
          })).filter(i => i.visible);
          return { inputs };
        }
        """
        info = page.evaluate(INSPECT_JS)
        print(f"[i] Inputs:")
        for i in info["inputs"]:
            print(f"  type={i['type']} name={i['name']!r} id={i['id']!r} ph={i['placeholder']!r}")

        # Ищем поле по placeholder — типичные паттерны
        target = None
        for i in info["inputs"]:
            ph = (i.get("placeholder") or "").lower()
            name = (i.get("name") or "").lower()
            id_ = (i.get("id") or "").lower()
            if any(kw in ph for kw in ["артикул", "номер", "vin", "поиск", "детал"]):
                target = i
                break
            if any(kw in name for kw in ["search", "article", "part", "query", "q"]):
                target = i
                break
            if any(kw in id_ for kw in ["search", "article", "part", "query"]):
                target = i
                break

        if not target:
            print("[!] Поле поиска не найдено")
            page.screenshot(path=str(OUT_DIR / "rossko-no-search.png"), full_page=True)
            browser.close()
            return 1

        print(f"[+] Поле найдено: {target}")

        # Вводим
        sel = f"input[placeholder='{target['placeholder']}']"
        if not target.get("placeholder"):
            if target.get("id"):
                sel = f"input#{target['id']}"
            elif target.get("name"):
                sel = f"input[name='{target['name']}']"
        try:
            inp = page.locator(sel).first
            inp.click()
            inp.fill(SKU)
            page.wait_for_timeout(500)

            try:
                with page.expect_navigation(wait_until="domcontentloaded", timeout=15000):
                    inp.press("Enter")
            except Exception as e:
                print(f"[?] Enter: {e}")
                page.wait_for_timeout(3000)

            page.wait_for_timeout(4000)
            print(f"[i] After search: title={page.title()!r}, url={page.url}")

            html = page.content()
            ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
            (OUT_DIR / f"rossko-result-{SKU}-{ts}.html").write_text(html, encoding="utf-8")
            page.screenshot(path=str(OUT_DIR / f"rossko-result-{SKU}.png"), full_page=False)

            captcha = bool(re.search(
                r"captcha|robot|antibot|cloudflare|smartcaptcha|hcaptcha|datadome",
                html, re.I
            ))
            price_signals = re.findall(
                r"(\d[\d\s\xa0]*[.,]?\d{0,2})\s*(?:руб|₽)", html, re.I
            )
            print(f"\n--- VERDICT ---")
            print(f"  URL: {page.url}")
            print(f"  Captcha: {captcha}")
            print(f"  Цены: {len(price_signals)}")
            for ps in price_signals[:5]:
                print(f"    {ps}")
            h1 = page.locator("h1").first.inner_text() if page.locator("h1").count() else "(none)"
            print(f"  H1: {h1[:200]}")
        except Exception as e:
            print(f"[!] Ошибка: {e}")

        browser.close()

    print(f"\nГотово за {time.monotonic() - t0:.1f}с")
    return 0


if __name__ == "__main__":
    sys.exit(main())
