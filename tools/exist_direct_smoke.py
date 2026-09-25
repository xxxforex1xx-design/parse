"""Прямой URL карточки Exist: /Catalog/Goods/{brand}/{sku}/.

Один запрос, 8 сек пауза. Если URL правильный — сервер отдаст
страницу с ценой, наличием и описанием без multi-step flow.
"""

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
import re  # noqa: E402

SKU = sys.argv[1] if len(sys.argv) > 1 else "6RU698151"
BRAND = sys.argv[2] if len(sys.argv) > 2 else "trw"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7",
    "Referer": "https://www.exist.ru/",
    "DNT": "1",
}

# Прямой URL карточки. Exist обычно использует /Catalog/Goods/{brand}/{sku}/{anything}/
URL = f"https://www.exist.ru/Catalog/Goods/{BRAND}/{SKU}/"

print("[i] Sleep 8s…")
time.sleep(8)
print(f"[i] GET {URL}")
t0 = time.monotonic()
try:
    resp = requests.get(URL, headers=HEADERS, timeout=30, allow_redirects=True)
except requests.RequestException as e:
    print(f"[!] {e}")
    sys.exit(1)

elapsed = time.monotonic() - t0
print(f"[i] HTTP {resp.status_code} · {len(resp.content)} bytes · {elapsed:.1f}s")
print(f"[i] Final URL: {resp.url}")

ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
fix = f"tools/fixtures/exist-direct-{BRAND}-{SKU}-{ts}.html"
with open(fix, "w", encoding="utf-8") as f:
    f.write(resp.text)
print(f"[+] {fix}")

soup = BeautifulSoup(resp.text, "html.parser")
title = soup.title.string.strip() if soup.title and soup.title.string else "(none)"
h1 = soup.h1.get_text(strip=True) if soup.h1 else "(none)"

# Типичные селекторы для карточки Exist
price_selectors = [
    ".price-value",
    ".offer-price",
    "[class*='PriceValue' i]",
    "[data-role='price']",
    "span.price",
]
found_prices: list[str] = []
for sel in price_selectors:
    for el in soup.select(sel):
        txt = el.get_text(strip=True)
        if txt:
            found_prices.append(f"[{sel}] = {txt}")

# Резервный regex
regex_prices = re.findall(
    r"(\d{1,3}(?:[\s\xa0]\d{3})*(?:[\.,]\d{1,2})?)\s*(?:руб|RUR|₽)",
    resp.text,
)
print(f"\nTitle: {title}")
print(f"H1: {h1}")
print(f"Final URL отличается от запроса: {resp.url.rstrip('/') != URL.rstrip('/')}")
print(f"По селекторам найдено цен: {len(found_prices)}")
for p in found_prices[:6]:
    print(f"  {p}")
print(f"Regex нашёл цен: {len(regex_prices)}, first 5: {regex_prices[:5]}")

if "Выберите каталог" in resp.text:
    print("\n[!] Снова вернулась главная «Выберите каталог» — этот brand/SKU не существует.")
elif found_prices or regex_prices:
    print("\n[+] Похоже, есть цены. Можно парсить.")
elif resp.url != URL:
    print(f"\n[?] Был redirect на {resp.url} — может, это и есть карточка.")
else:
    print("\n[?] Непонятно. Открой фикстуру в браузере.")
