"""Одноразовый smoke-test: один запрос к Exist по артикулу, медленно.

Не скилл, не для прод-запуска. Только для проверки «получаем ли мы
цены с Exist в принципе». Длинный User-Agent, большие задержки, один
запрос за запуск.

Запуск:
    py tools/exist_smoke.py 6RU698151
    py tools/exist_smoke.py 04465-33450 --delay 10

Результат: tools/fixtures/exist-<sku>-<timestamp>.html + JSON в stdout.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

import requests
from bs4 import BeautifulSoup  # noqa: E402

# Аргументы
parser = argparse.ArgumentParser()
parser.add_argument("sku", help="Артикул для поиска (например, 6RU698151).")
parser.add_argument("--delay", type=int, default=5,
                    help="Задержка перед запросом в секундах (по умолчанию 5).")
parser.add_argument("--timeout", type=int, default=30,
                    help="HTTP-таймаут в секундах (по умолчанию 30).")
parser.add_argument("--out", default="tools/fixtures",
                    help="Каталог для сохранения фикстуры.")
args = parser.parse_args()

# Константы
SKU = args.sku.strip()
DELAY = max(args.delay, 0)
TIMEOUT = args.timeout
OUT_DIR = Path(args.out).resolve()
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Поисковая выдача Exist: формат URL https://www.exist.ru/Price/?pcode={SKU}
# (проверено: /Price/ — это публичный прайс-лист по артикулу)
SEARCH_URL = "https://www.exist.ru/Price/"
REFERER = "https://www.exist.ru/"

# User-Agent — обычный браузер. Не маскируем под Googlebot, чтобы не нарваться
# на ручную проверку. UA выбран из реальных Chrome 130+.
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36"
)

# Accept-Language — русский, потому что сайт русскоязычный и без него
# могут отдавать другой контент.
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": REFERER,
    "DNT": "1",
    "Sec-Ch-Ua": '"Chromium";v="130", "Not;A_Brand";v="24"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

print(f"[i] Sleep {DELAY}s перед запросом (этичный rate-limit)…")
time.sleep(DELAY)

print(f"[i] GET {SEARCH_URL} (sku={SKU})")
t0 = time.monotonic()
try:
    resp = requests.get(
        SEARCH_URL,
        params={"pcode": SKU},
        headers=HEADERS,
        timeout=TIMEOUT,
        allow_redirects=True,
    )
except requests.RequestException as e:
    print(f"[!] Сетевая ошибка: {e}")
    sys.exit(1)

elapsed = time.monotonic() - t0
print(f"[i] HTTP {resp.status_code} · {len(resp.content)} bytes · {elapsed:.1f}s")
print(f"[i] Final URL: {resp.url}")
print(f"[i] Content-Type: {resp.headers.get('Content-Type')}")

# Сохраняем фикстуру
ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
fix_path = OUT_DIR / f"exist-{SKU}-{ts}.html"
fix_path.write_text(resp.text, encoding="utf-8")
print(f"[+] Фикстура: {fix_path}")

# Парсим: ищем признаки успеха/неуспеха
soup = BeautifulSoup(resp.text, "html.parser")

signals: dict = {
    "html_len": len(resp.text),
    "title": (soup.title.string.strip() if soup.title and soup.title.string else None),
    "has_price_block": bool(soup.select("[class*='price' i]")),
    "has_search_results": bool(soup.select("[class*='offer' i], [class*='result' i], [class*='product' i]")),
    "has_captcha_hint": bool(
        re.search(r"captcha|robot|antibot|verify.{0,20}human", resp.text, re.I)
    ),
    "has_blocked_hint": bool(
        re.search(r"blocked|access.{0,20}denied|too.{0,5}many.{0,5}requests", resp.text, re.I)
    ),
    "h1_text": (soup.h1.get_text(strip=True) if soup.h1 else None),
    "first_500_chars": resp.text[:500],
}

# Попробуем найти цену — типичные паттерны
price_candidates = re.findall(
    r'(\d[\d\s\xa0]*(?:[\.,]\d{1,2})?)\s*(?:руб|RUR|₽|\<[^>]+\>руб)',
    resp.text,
    re.I,
)
signals["price_candidates_first_5"] = price_candidates[:5]

# JSON-вывод для агента
print("\n--- JSON ---")
print(json.dumps(signals, ensure_ascii=False, indent=2))

print("\n--- VERDICT ---")
if signals["has_captcha_hint"]:
    print("[!] ОБНАРУЖЕНА CAPTCHA-страница или robot-чекеринг. Нужен stealth-обход.")
elif signals["has_blocked_hint"]:
    print("[!] ОБНАРУЖЕН БЛОК. Менять IP или ждать.")
elif signals["has_search_results"] and signals["has_price_block"]:
    print("[+] Похоже, есть результаты поиска и блок с ценами. Стоит копать глубже.")
elif signals["html_len"] < 5000:
    print("[?] HTML слишком короткий — возможно JS-only или пустая выдача. Нужен Playwright.")
else:
    print("[?] Неопределённый ответ. Открой фикстуру в браузере и посмотри структуру.")
