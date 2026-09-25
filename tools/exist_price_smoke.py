"""Пробуем POST /Price/default.aspx?pcode=... — найдена в HTML как форма поиска."""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

import requests  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402

SKU = sys.argv[1] if len(sys.argv) > 1 else "6RU698151"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7",
    "Referer": f"https://www.exist.ru/Price/?pcode={SKU}",
    "Origin": "https://www.exist.ru",
    "DNT": "1",
}

URL = f"https://www.exist.ru/Price/default.aspx?pcode={SKU}"

print("[i] Sleep 8s…")
time.sleep(8)
print(f"[i] POST {URL}")
t0 = time.monotonic()
try:
    resp = requests.post(
        URL,
        headers=HEADERS,
        timeout=30,
        allow_redirects=True,
    )
except requests.RequestException as e:
    print(f"[!] {e}")
    sys.exit(1)

elapsed = time.monotonic() - t0
print(f"[i] HTTP {resp.status_code} · {len(resp.content)} bytes · {elapsed:.1f}s")
print(f"[i] Final URL: {resp.url}")

ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
fix = f"tools/fixtures/exist-price-{SKU}-{ts}.html"
with open(fix, "w", encoding="utf-8") as f:
    f.write(resp.text)
print(f"[+] {fix}")

soup = BeautifulSoup(resp.text, "html.parser")
title = soup.title.string.strip() if soup.title and soup.title.string else "(none)"
h1 = soup.h1.get_text(strip=True) if soup.h1 else "(none)"

# Ищем признаки результатов: таблицы с ценами, OfferName и т.д.
offer_rows = soup.select("[class*='offer' i]")
price_cells = soup.select("[class*='price' i]")
sku_cells = soup.select("[id*='art' i], [class*='art' i]")

import re
prices = re.findall(r"(\d[\d\s\xa0]*(?:[\.,]\d{1,2})?)\s*(?:руб|RUR|₽)", resp.text)
brands = re.findall(r"(?:brand|бренд)[^<>]{0,40}?(?:[A-ZА-Я][A-Za-zА-Яа-яё0-9-]{2,20})", resp.text, re.I)[:5]

print(f"\nTitle: {title}")
print(f"H1: {h1}")
print(f"offer_rows: {len(offer_rows)}")
print(f"price_cells: {len(price_cells)}")
print(f"sku_cells: {len(sku_cells)}")
print(f"prices_found: {len(prices)}, first 5: {prices[:5]}")
print(f"brands_candidates: {brands}")

# Дополнительно: проверим, может это всё ещё главная
if "Выберите каталог" in resp.text:
    print("\n[!] Снова вернулась главная «Выберите каталог».")
elif offer_rows or "Каталог" in title or "цена" in resp.text.lower():
    print("\n[+] Похоже, есть результаты или хотя бы раздел каталога.")
else:
    print("\n[?] Структура не распознана, открой фикстуру в браузере.")
