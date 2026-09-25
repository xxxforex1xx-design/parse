"""Smoke-test /Api/Parts/Search — найден в HTML главной Exist как источник
автокомплита. Один запрос с длинной паузой.

Запуск:
    py tools/exist_api_smoke.py 6RU698151
"""

from __future__ import annotations

import json
import os
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

import requests  # noqa: E402

SKU = sys.argv[1] if len(sys.argv) > 1 else "6RU698151"
DELAY = 7

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7",
    "Referer": "https://www.exist.ru/",
    "X-Requested-With": "XMLHttpRequest",
    "DNT": "1",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

URL = "https://www.exist.ru/Api/Parts/Search"

print(f"[i] Sleep {DELAY}s…")
time.sleep(DELAY)

print(f"[i] GET {URL}?term={SKU}")
t0 = time.monotonic()
try:
    resp = requests.get(
        URL,
        params={"term": SKU},
        headers=HEADERS,
        timeout=30,
        allow_redirects=False,
    )
except requests.RequestException as e:
    print(f"[!] {e}")
    sys.exit(1)

elapsed = time.monotonic() - t0
print(f"[i] HTTP {resp.status_code} · {len(resp.content)} bytes · {elapsed:.1f}s")
print(f"[i] Content-Type: {resp.headers.get('Content-Type')}")

out = Path("tools/fixtures")
out.mkdir(parents=True, exist_ok=True)
ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
fix = out / f"exist-api-{SKU}-{ts}.json"
fix.write_text(resp.text, encoding="utf-8")
print(f"[+] Фикстура: {fix}")

# Попробуем распарсить как JSON
try:
    data = resp.json()
    print(f"\n[+] JSON валидный. Тип: {type(data).__name__}")
    if isinstance(data, list):
        print(f"[+] Элементов: {len(data)}")
        print(json.dumps(data[:5], ensure_ascii=False, indent=2))
    elif isinstance(data, dict):
        print(f"[+] Ключи верхнего уровня: {list(data.keys())}")
        print(json.dumps(data, ensure_ascii=False, indent=2)[:2000])
except json.JSONDecodeError as e:
    print(f"[!] Не JSON: {e}")
    print("[i] Первые 500 символов тела:")
    print(resp.text[:500])
