"""Rate-limited парсер Exist + Autodoc.

Этичный crawler: медленно, с паузами, не долбит.
Парсит список SKU по одному, сохраняет результаты в JSONL.

Особенности:
- Пауза 15-30 сек между запросами (с jitter, чтобы не было паттерна)
- До 3 retry с exponential backoff при сетевых ошибках
- Сохранение в JSONL: по одной строке на оффер
- Прогресс в stderr, чистые данные в stdout / файле

Использование:
    # Один SKU
    py tools/rate_limited_parser.py --source exist --sku 6RU698151

    # Несколько SKU из файла (по одному на строку)
    py tools/rate_limited_parser.py --source autodoc --skus-file skus.txt --out results.jsonl

    # Кастомные паузы
    py tools/rate_limited_parser.py --source exist --sku 0446533450 \\
        --min-delay 20 --max-delay 40

    # Dry-run (без реальных запросов, для отладки)
    py tools/rate_limited_parser.py --source exist --sku 6RU698151 --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout  # noqa: E402

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)


# ── JS-сниппеты для парсинга DOM ──────────────────────────────────────

EXIST_PARSE_JS = r"""
() => {
  const text = (el) => (el ? (el.innerText || '').trim() : null);
  const cleanNum = (s) => {
    if (!s) return null;
    const m = s.replace(/[^\d.,]/g, '').replace(/\s/g, '').replace(',', '.');
    const n = parseFloat(m);
    return Number.isFinite(n) ? n : null;
  };
  const offers = [];
  document.querySelectorAll('.table-body .row-container').forEach((rc) => {
    const name = rc.querySelector('.name-container');
    const brand = text(name && name.querySelector('.brand'));
    const art = text(name && name.querySelector('.art'));
    const partno = text(name && name.querySelector('.partno'));
    const descr = text(name && name.querySelector('.description'));
    const variants = [];
    rc.querySelectorAll('.pricerow').forEach((pr) => {
      variants.push({
        term: text(pr.querySelector('.params')),
        price_text: text(pr.querySelector('.price__wrapper')),
        price_value: cleanNum(text(pr.querySelector('.price__wrapper'))),
        is_best_offer: !!pr.closest('.bestOffers'),
      });
    });
    offers.push({ brand, art, partno, descr, variants });
  });
  return {
    title: document.title,
    h1: (document.querySelector('h1') || {}).innerText,
    offers,
  };
}
"""

AUTODOC_PARSE_JS = r"""
() => {
  const text = (el) => (el ? (el.innerText || '').trim() : null);
  const cleanNum = (s) => {
    if (!s) return null;
    const m = s.replace(/[^\d.,]/g, '').replace(/\s/g, '').replace(',', '.');
    const n = parseFloat(m);
    return Number.isFinite(n) ? n : null;
  };
  const card = document.querySelector('.grid.card');
  if (!card) return { title: document.title, h1: (document.querySelector('h1')||{}).innerText, card: null };
  const brand = text(card.querySelector('.card__manufacturer'));
  return {
    title: document.title,
    h1: (document.querySelector('h1') || {}).innerText,
    card: {
      name: text(card.querySelector('.card__name')),
      brand: brand ? brand.split('Производитель')[0].trim() : null,
      price_text: text(card.querySelector('.card__price-link')),
      price_value: cleanNum(text(card.querySelector('.card__price-link'))),
      stock_text: text(card.querySelector('.card__price-stock')),
      delivery_text: text(card.querySelector('.card__delivery')),
    },
  };
}
"""


# ── Парсеры ────────────────────────────────────────────────────────────

def parse_exist(page, sku: str, catalog_pref: str = "VAG") -> dict[str, Any]:
    page.goto("https://www.exist.ru/", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(1500)
    page.locator("#pcode").first.fill(sku)
    page.locator("#pcode").first.press("Enter")
    page.wait_for_load_state("domcontentloaded", timeout=20000)
    page.wait_for_timeout(3000)
    try:
        cat_link = page.locator(f"a:has-text('{catalog_pref}')").first
        if cat_link.count() > 0:
            cat_link.click(timeout=8000)
            page.wait_for_load_state("domcontentloaded", timeout=20000)
            page.wait_for_timeout(5000)
    except PWTimeout:
        pass
    result = page.evaluate(EXIST_PARSE_JS)
    result["url"] = page.url
    return result


def parse_autodoc(page, sku: str) -> dict[str, Any]:
    # Autodoc: прямой URL карточки (без поиска)
    url = f"https://www.autodoc.ru/man/657/part/{sku}"
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(6000)
    try:
        page.wait_for_function(
            "() => document.body.innerText.length > 500 && /\\d/.test(document.body.innerText)",
            timeout=10000,
        )
    except PWTimeout:
        pass
    page.wait_for_timeout(2000)
    result = page.evaluate(AUTODOC_PARSE_JS)
    result["url"] = url
    return result


# ── Rate-limit + retry ─────────────────────────────────────────────────

def jitter_delay(min_s: float, max_s: float) -> float:
    """Сон со случайной паузой."""
    return random.uniform(min_s, max_s)


def with_retry(fn, *, attempts: int = 3, base: float = 5.0):
    """Обёртка с retry и exponential backoff."""
    last_err = None
    for i in range(attempts):
        try:
            return fn()
        except (PWTimeout, Exception) as e:
            last_err = e
            wait = base * (2 ** i)
            print(f"[!] Попытка {i+1}/{attempts} упала: {e}. Жду {wait:.0f}с.", file=sys.stderr)
            time.sleep(wait)
    raise last_err  # type: ignore


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--source", choices=["exist", "autodoc"], required=True)
    p.add_argument("--sku", help="Один SKU для парсинга")
    p.add_argument("--skus-file", type=Path, help="Файл со списком SKU (по одному на строку)")
    p.add_argument("--out", type=Path, help="JSONL-файл для результатов")
    p.add_argument("--catalog", default="VAG", help="Каталог Exist (VAG / VAG Asia)")
    p.add_argument("--min-delay", type=float, default=15.0,
                   help="Минимальная пауза между запросами, сек (по умолчанию 15)")
    p.add_argument("--max-delay", type=float, default=30.0,
                   help="Максимальная пауза между запросами, сек (по умолчанию 30)")
    p.add_argument("--retries", type=int, default=3, help="Retry-попытки")
    p.add_argument("--dry-run", action="store_true", help="Не делать реальных запросов")
    args = p.parse_args()

    # Собираем список SKU
    skus: list[str] = []
    if args.sku:
        skus.append(args.sku.strip())
    if args.skus_file:
        skus.extend(
            line.strip() for line in args.skus_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        )
    if not skus:
        print("[!] Не указаны SKU (--sku или --skus-file)", file=sys.stderr)
        return 1

    print(f"[i] Источник: {args.source}")
    print(f"[i] SKU: {len(skus)} шт.")
    print(f"[i] Паузы: {args.min_delay}–{args.max_delay} сек (с jitter)")
    print(f"[i] Retry: {args.retries}")

    if args.dry_run:
        for s in skus:
            print(f"[dry-run] {args.source} / {s}")
        return 0

    results: list[dict[str, Any]] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
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

        for i, sku in enumerate(skus, 1):
            print(f"\n[{i}/{len(skus)}] {args.source} / {sku}")
            t0 = time.monotonic()
            try:
                if args.source == "exist":
                    parsed = with_retry(
                        lambda: parse_exist(page, sku, args.catalog),
                        attempts=args.retries,
                    )
                    for off in parsed.get("offers", []):
                        for v in off.get("variants", []):
                            results.append({
                                "source": "exist",
                                "sku": sku,
                                "brand": off.get("brand"),
                                "art": off.get("art"),
                                "partno": off.get("partno"),
                                "descr": off.get("descr"),
                                "term": v.get("term"),
                                "price_text": v.get("price_text"),
                                "price_value": v.get("price_value"),
                                "is_best_offer": v.get("is_best_offer"),
                                "url": parsed.get("url"),
                                "scraped_at": datetime.now(timezone.utc).isoformat(),
                            })
                elif args.source == "autodoc":
                    parsed = with_retry(
                        lambda: parse_autodoc(page, sku),
                        attempts=args.retries,
                    )
                    c = parsed.get("card") or {}
                    results.append({
                        "source": "autodoc",
                        "sku": sku,
                        "brand": c.get("brand"),
                        "name": c.get("name"),
                        "price_text": c.get("price_text"),
                        "price_value": c.get("price_value"),
                        "stock_text": c.get("stock_text"),
                        "delivery_text": c.get("delivery_text"),
                        "url": parsed.get("url"),
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                    })
                print(f"[+] OK за {time.monotonic() - t0:.1f}с")
            except Exception as e:
                print(f"[!] Final fail: {e}", file=sys.stderr)
                results.append({
                    "source": args.source,
                    "sku": sku,
                    "error": str(e),
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                })

            # Пауза между запросами (но не после последнего)
            if i < len(skus):
                delay = jitter_delay(args.min_delay, args.max_delay)
                print(f"[i] Пауза {delay:.1f}с...")
                time.sleep(delay)

        browser.close()

    # Сохраняем
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8") as f:
            for r in results:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"\n[+] Сохранено {len(results)} записей в {args.out}")
    else:
        for r in results:
            print(json.dumps(r, ensure_ascii=False))

    # Краткая сводка
    ok = sum(1 for r in results if "error" not in r)
    err = sum(1 for r in results if "error" in r)
    print(f"\n[ИТОГ] ok={ok}, errors={err}, всего={len(results)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
