"""Emex v2: ждём рендер Next.js, ищем поле поиска гибче."""

from __future__ import annotations

import os
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

INSPECT_JS = r"""
() => {
  const text = (el) => (el ? (el.innerText || el.placeholder || '').trim() : null);
  const out = {};
  const inputs = Array.from(document.querySelectorAll('input'));
  out.inputs = inputs.map((el, idx) => ({
    idx,
    type: el.type,
    name: el.name || null,
    id: el.id || null,
    placeholder: el.placeholder || null,
    visible: !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length),
    cls: (el.className || '').toString().slice(0, 100),
  })).filter(i => i.visible);
  out.h1 = (document.querySelector('h1') || {}).innerText;
  return out;
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
        )
        ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        page = ctx.new_page()
        page.goto("https://emex.ru/", wait_until="domcontentloaded", timeout=30000)

        # Ждём появления input'ов через Next.js (дольше)
        try:
            page.wait_for_function(
                "() => document.querySelectorAll('input').length > 1",
                timeout=15000,
            )
        except Exception as e:
            print(f"[?] wait_for_function: {e}")

        page.wait_for_timeout(3000)

        info = page.evaluate(INSPECT_JS)
        print(f"[i] Initial inputs:")
        for i in info["inputs"]:
            print(f"  [{i['idx']}] type={i['type']} name={i['name']!r} "
                  f"id={i['id']!r} ph={i['placeholder']!r}")
        print(f"[i] H1: {info.get('h1')!r}")

        # Ищем поле по placeholder (Номер детали / VIN / Артикул)
        target = None
        for i in info["inputs"]:
            ph = (i.get("placeholder") or "").lower()
            if any(kw in ph for kw in ["номер", "детал", "vin", "артикул", "поиск"]):
                target = i
                break

        if not target:
            print("[!] Поле поиска не найдено даже после расширенного поиска")
            page.screenshot(path=str(OUT_DIR / "emex-v2-no-search.png"), full_page=False)
            browser.close()
            return 1

        print(f"[+] Поле найдено: placeholder={target['placeholder']!r}")

        # Кликаем и вводим
        sel = f"input[placeholder='{target['placeholder']}']"
        try:
            inp = page.locator(sel).first
            inp.click()
            inp.fill(SKU)
            page.wait_for_timeout(500)

            # Пробуем нажать «Найти» (кнопка рядом)
            try:
                with page.expect_navigation(wait_until="domcontentloaded", timeout=15000):
                    inp.press("Enter")
            except Exception as e:
                print(f"[?] expect_navigation Enter: {e}")
                # Альтернатива — кнопка
                try:
                    with page.expect_navigation(wait_until="domcontentloaded", timeout=15000):
                        page.get_by_role("button", name="Найти").click()
                except Exception as e2:
                    print(f"[?] expect_navigation Кнопка: {e2}")
                    page.wait_for_timeout(3000)

            page.wait_for_timeout(4000)
            print(f"[i] After search: title={page.title()!r}, url={page.url}")

            html = page.content()
            ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
            (OUT_DIR / f"emex-result-{SKU}-{ts}.html").write_text(html, encoding="utf-8")
            page.screenshot(path=str(OUT_DIR / f"emex-result-{SKU}.png"), full_page=False)

            # Анализ
            import re
            captcha = bool(re.search(
                r"captcha|robot|antibot|cloudflare|smartcaptcha|hcaptcha|datadome",
                html, re.I
            ))
            price_signals = re.findall(
                r"(\d[\d\s\xa0]*[.,]?\d{0,2})\s*(?:руб|₽)", html, re.I
            )
            login_required = bool(re.search(
                r"войти|вход|авториз|регистрац", html, re.I
            ))

            print(f"\n--- VERDICT ---")
            print(f"  URL после поиска: {page.url}")
            print(f"  Captcha-маркеры: {captcha}")
            print(f"  Login required (главная содержит «войти/вход»): {login_required}")
            print(f"  Найдено цен-сигналов: {len(price_signals)}")
            for ps in price_signals[:5]:
                print(f"    {ps}")
        except Exception as e:
            print(f"[!] Ошибка при вводе: {e}")

        browser.close()

    print(f"\nГотово за {time.monotonic() - t0:.1f}с")
    return 0


if __name__ == "__main__":
    sys.exit(main())
