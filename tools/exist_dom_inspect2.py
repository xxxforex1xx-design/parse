"""Глубокая инспекция: parent .pricerow, поиск бренда и артикула."""

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
CATALOG = "VAG"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)

INSPECT_JS = r"""
() => {
  const out = {};

  // 1. Найти .pricerow, посмотреть его parent и grandparent
  const pricerow = document.querySelector('.pricerow');
  if (!pricerow) return { error: 'no .pricerow' };
  let parent = pricerow.parentElement;
  let grandparent = parent ? parent.parentElement : null;
  let great = grandparent ? grandparent.parentElement : null;

  out.parent_chain = [parent, grandparent, great].filter(Boolean).map((el, lvl) => ({
    lvl,
    tag: el.tagName,
    cls: (el.className || '').toString().slice(0, 200),
    id: el.id || null,
    child_count: el.children.length,
    text_snippet: (el.innerText || '').slice(0, 300),
  }));

  // 2. Ищем все элементы с "brand" в классе по всей странице
  out.brand_classed = Array.from(document.querySelectorAll('[class*="brand" i]')).slice(0, 12).map(el => ({
    tag: el.tagName,
    cls: (el.className || '').toString().slice(0, 120),
    text: (el.innerText || '').slice(0, 60),
  }));

  // 3. Ищем все элементы с типичными именами брендов
  const knownBrands = ['TRW', 'Bosch', 'Brembo', 'ATE', 'Ferodo', 'Textar', 'Sachs', 'Valeo'];
  out.brand_text_matches = [];
  for (const b of knownBrands) {
    const els = Array.from(document.querySelectorAll('*')).filter(el =>
      el.children.length === 0 &&
      el.textContent &&
      el.textContent.trim() === b
    ).slice(0, 3);
    for (const el of els) {
      out.brand_text_matches.push({
        brand: b,
        tag: el.tagName,
        cls: (el.className || '').toString().slice(0, 120),
        parent_cls: el.parentElement ? (el.parentElement.className || '').toString().slice(0, 120) : null,
        grandparent_cls: el.parentElement && el.parentElement.parentElement ?
          (el.parentElement.parentElement.className || '').toString().slice(0, 120) : null,
      });
    }
  }

  // 4. Ищем артикул (SKU + вариации)
  out.art_text_matches = [];
  const artEls = Array.from(document.querySelectorAll('*')).filter(el =>
    el.children.length === 0 &&
    el.textContent &&
    /6RU\s*698\s*151/.test(el.textContent)
  ).slice(0, 5);
  for (const el of artEls) {
    out.art_text_matches.push({
      text: el.textContent.trim().slice(0, 60),
      tag: el.tagName,
      cls: (el.className || '').toString().slice(0, 120),
      parent_cls: el.parentElement ? (el.parentElement.className || '').toString().slice(0, 120) : null,
    });
  }

  // 5. Снимаем одну «полную» строку как образец — идём вверх до контейнера,
  //    который содержит несколько .pricerow подряд (один бренд = много офферов)
  if (parent) {
    // Ищем ближайший ancestor с > 1 .pricerow ребёнком
    let rowGroup = parent;
    while (rowGroup && rowGroup.querySelectorAll('.pricerow').length < 2 && rowGroup.parentElement) {
      rowGroup = rowGroup.parentElement;
    }
    out.row_group = rowGroup ? {
      tag: rowGroup.tagName,
      cls: (rowGroup.className || '').toString().slice(0, 200),
      child_count: rowGroup.children.length,
      text_first_500: (rowGroup.innerText || '').slice(0, 500),
    } : null;
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
