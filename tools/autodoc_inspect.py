"""Инспекция DOM Autodoc: ищем селекторы для бренда, цены, наличия.

Autodoc = Angular SPA. Цены рендерятся через JS после загрузки.
Идём через page.evaluate на живом DOM после достаточного wait.
"""

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
  const text = (el) => (el ? (el.innerText || el.textContent || '').trim() : null);
  const out = {};

  // 1. Заголовок
  out.title = document.title;
  out.h1 = (document.querySelector('h1') || {}).innerText;
  out.url = location.href;

  // 2. Все элементы с «руб» или ₽ в innerText (только непустые и без кучи детей)
  const priceLike = [];
  document.querySelectorAll('*').forEach(el => {
    const t = el.innerText || '';
    if (!t || t.length > 200) return;
    if (el.children.length > 5) return;
    if (/\d[\d  \xa0]*[.,]?\d{0,2}\s*(?:руб|₽)/.test(t)) {
      // Соберём классы
      const classes = (el.className || '').toString().slice(0, 200);
      const parentCls = el.parentElement ? (el.parentElement.className || '').toString().slice(0, 200) : null;
      const gpCls = el.parentElement && el.parentElement.parentElement ?
        (el.parentElement.parentElement.className || '').toString().slice(0, 200) : null;
      priceLike.push({
        tag: el.tagName,
        cls: classes,
        parent_cls: parentCls,
        gp_cls: gpCls,
        text: t.slice(0, 100),
      });
    }
  });
  out.price_like_count = priceLike.length;
  out.price_like_examples = priceLike.slice(0, 15);

  // 3. Возможные классы продуктовых карточек
  const productish = [];
  document.querySelectorAll('[class*="product" i], [class*="card" i], [class*="item" i], [class*="offer" i]').forEach(el => {
    const t = (el.innerText || '').slice(0, 100);
    if (t && t.length > 10) {
      productish.push({
        tag: el.tagName,
        cls: (el.className || '').toString().slice(0, 200),
        text: t,
      });
    }
  });
  out.productish_count = productish.length;
  out.productish_examples = productish.slice(0, 10);

  // 4. Сводка: текст страницы (первые 1500 chars)
  out.body_first_1500 = (document.body.innerText || '').slice(0, 1500);

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

        # Идём сразу на прямой URL карточки
        url = f"https://www.autodoc.ru/man/657/part/{SKU}"
        print(f"[i] Открываю {url}")
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        # Angular SPA требует времени
        page.wait_for_timeout(6000)

        # Дополнительно: подождём, пока появятся элементы с ценами
        try:
            page.wait_for_function(
                "() => document.body.innerText.length > 500 && /\\d/.test(document.body.innerText)",
                timeout=10000,
            )
        except Exception:
            print("[?] wait_for_function не дождался")

        page.wait_for_timeout(2000)

        info = page.evaluate(INSPECT_JS)

        # Сохраняем HTML для офлайн-разбора
        html = page.content()
        Path_ = __import__("pathlib").Path
        out_dir = Path_("tools/fixtures")
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"autodoc-{SKU}.html").write_text(html, encoding="utf-8")
        page.screenshot(path=str(out_dir / f"autodoc-{SKU}.png"), full_page=False)

        browser.close()

    elapsed = time.monotonic() - t0
    print(json.dumps(info, ensure_ascii=False, indent=2))
    print(f"\nГотово за {elapsed:.1f}с")
    return 0


if __name__ == "__main__":
    sys.exit(main())
