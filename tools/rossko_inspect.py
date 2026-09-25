"""Rossko DOM-инспекция: ищем селекторы для бренда, цены, наличия."""

from __future__ import annotations

import json
import os
import sys
import time

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

from playwright.sync_api import sync_playwright  # noqa: E402

SKU = "6RU698151"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)

INSPECT_JS = r"""
() => {
  const text = (el) => (el ? (el.innerText || '').trim() : null);
  const out = {};
  out.title = document.title;
  out.h1 = (document.querySelector('h1') || {}).innerText;
  out.url = location.href;

  // Карточки результатов поиска
  const cards = [];
  // Типичные селекторы карточек Rossko
  document.querySelectorAll('[class*="card" i], [class*="product" i], [class*="item" i], [class*="offer" i]').forEach(el => {
    const t = (el.innerText || '').trim();
    if (t && t.length > 20 && t.length < 600) {
      cards.push({
        tag: el.tagName,
        cls: (el.className || '').toString().slice(0, 200),
        text: t.slice(0, 300),
      });
    }
  });
  out.cards_count = cards.length;
  out.cards_examples = cards.slice(0, 12);

  // Все элементы с «руб»
  const priceLike = [];
  document.querySelectorAll('*').forEach(el => {
    const t = el.innerText || '';
    if (!t || t.length > 200 || el.children.length > 5) return;
    if (/от\s*\d|^\d[\d  \xa0]*\s*₽|руб/.test(t)) {
      priceLike.push({
        tag: el.tagName,
        cls: (el.className || '').toString().slice(0, 200),
        parent_cls: el.parentElement ? (el.parentElement.className || '').toString().slice(0, 200) : null,
        gp_cls: el.parentElement && el.parentElement.parentElement ?
          (el.parentElement.parentElement.className || '').toString().slice(0, 200) : null,
        text: t.slice(0, 100),
      });
    }
  });
  out.price_like_count = priceLike.length;
  out.price_like_examples = priceLike.slice(0, 15);

  // Тело страницы (первые 2000 chars)
  out.body_first_2000 = (document.body.innerText || '').slice(0, 2000);

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

        page.goto("https://rossko.ru/", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)

        # Вводим SKU
        page.locator("input[name='q']").first.fill(SKU)
        page.wait_for_timeout(500)
        try:
            with page.expect_navigation(wait_until="domcontentloaded", timeout=15000):
                page.locator("input[name='q']").first.press("Enter")
        except Exception as e:
            print(f"[?] Enter: {e}")
            page.wait_for_timeout(3000)
        page.wait_for_timeout(5000)

        info = page.evaluate(INSPECT_JS)

        # Сохраняем HTML
        html = page.content()
        Path_ = __import__("pathlib").Path
        out_dir = Path_("tools/fixtures")
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"rossko-{SKU}.html").write_text(html, encoding="utf-8")
        page.screenshot(path=str(out_dir / f"rossko-{SKU}.png"), full_page=False)

        browser.close()

    print(json.dumps(info, ensure_ascii=False, indent=2))
    print(f"\nГотово за {time.monotonic() - t0:.1f}с")
    return 0


if __name__ == "__main__":
    sys.exit(main())
