"""Инспекция DOM-структуры .pricerow Exist.

Цель: понять, какие селекторы дают бренд, артикул, цену, срок.
Не для прод — только разведка.
"""

from __future__ import annotations

import json
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

SKU = "6RU698151"
CATALOG = "VAG"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)

INSPECT_JS = r"""
() => {
  const out = {};
  const rows = document.querySelectorAll('.pricerow');
  out.rows_count = rows.length;

  if (rows.length === 0) return out;

  // Берём первые 3 строки и выводим их текст + структуру классов
  out.examples = [];
  for (let i = 0; i < Math.min(3, rows.length); i++) {
    const r = rows[i];
    // Соберём все уникальные классы внутри строки
    const classes = new Set();
    r.querySelectorAll('*').forEach(el => {
      if (el.className && typeof el.className === 'string') {
        el.className.split(/\s+/).forEach(c => {
          if (c) classes.add(c);
        });
      }
    });
    out.examples.push({
      idx: i,
      text_full: (r.innerText || '').slice(0, 500),
      classes_used: Array.from(classes).sort(),
      // Дети первого уровня: tag + class + text
      children: Array.from(r.children).slice(0, 20).map(c => ({
        tag: c.tagName,
        cls: (c.className || '').toString().slice(0, 100),
        text: (c.innerText || '').slice(0, 80),
      })),
    });
  }
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
        page.goto("https://www.exist.ru/", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1500)
        page.locator("#pcode").first.fill(SKU)
        page.locator("#pcode").first.press("Enter")
        page.wait_for_load_state("domcontentloaded", timeout=20000)
        page.wait_for_timeout(3000)
        page.locator(f"a:has-text('{CATALOG}')").first.click(timeout=8000)
        page.wait_for_load_state("domcontentloaded", timeout=20000)
        page.wait_for_timeout(5000)

        info = page.evaluate(INSPECT_JS)
        browser.close()

    elapsed = time.monotonic() - t0
    print(json.dumps(info, ensure_ascii=False, indent=2))
    print(f"\nГотово за {elapsed:.1f}с")
    return 0


if __name__ == "__main__":
    sys.exit(main())
