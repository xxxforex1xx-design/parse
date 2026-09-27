"""Утилиты для нормализации поискового запроса.

Используется в web_app.py для роутинга:
- SKU (4-20 alnum, без пробелов)  → Exist + Autodoc + Rossko
- VIN (17 alnum, без пробелов)    → только Rossko
- NAME (содержит пробелы или >20)  → только Rossko
- EMPTY                            → ошибка
"""

from __future__ import annotations

import hashlib
import re
from typing import Literal

QueryType = Literal["sku", "vin", "name", "empty"]


def normalize_query(q: str) -> tuple[QueryType, str]:
    """Нормализует ввод пользователя.

    Returns:
        (type, normalized_value):
            - ("sku", "6RU698151")     — все источники
            - ("vin", "WBA3A5C57CF256789") — только Rossko
            - ("name", "тормозные колодки") — только Rossko
            - ("empty", "") — пустой ввод

    Логика:
        - сначала чистим от пробелов/дефисов/слэшей/точек
        - если пусто → "empty"
        - если ровно 17 alnum символов → VIN (но I/O/Q не используются в VIN)
        - если 4-20 alnum → SKU
        - иначе (пробелы или >20) → NAME
    """
    if not q:
        return ("empty", "")
    s = q.strip()
    if not s:
        return ("empty", "")

    cleaned = re.sub(r"[\s\-/.]", "", s)
    if not cleaned:
        return ("empty", "")
    upper = cleaned.upper()
    is_alnum = all(c.isalnum() and c.isascii() for c in upper)

    if not is_alnum:
        # содержит нелатинские буквы или спецсимволы → NAME
        return ("name", s)

    # VIN: 17 символов (стандарт ISO 3779). Буквы I, O, Q не используются.
    if len(upper) == 17 and not any(c in upper for c in "IOQ"):
        return ("vin", upper)

    # SKU: 4-20 alnum без пробелов
    if 4 <= len(upper) <= 20:
        return ("sku", upper)

    # Слишком короткое или длинное для SKU — текстовый запрос
    return ("name", s)


def cache_key_for_query(q_type: QueryType, normalized: str) -> str:
    """Имя файла кэша для запроса.

    - SKU: <SKU>.json
    - VIN: vin_<md5>.json (md5 от upper-case нормализованного)
    - NAME: name_<md5>.json
    - EMPTY: empty.json (на практике не используется, возвращает 400)
    """
    if q_type == "sku":
        return normalized
    if q_type == "vin":
        return "vin_" + hashlib.md5(normalized.encode("utf-8")).hexdigest()[:16]
    if q_type == "name":
        return "name_" + hashlib.md5(normalized.encode("utf-8")).hexdigest()[:16]
    return "empty"


def sources_for_query_type(q_type: QueryType) -> list[str]:
    """Какие источники поддерживают этот тип запроса.

    SKU поддерживается всеми (Exist ввод в #pcode, Autodoc прямой URL,
    Rossko q=). VIN/NAME — только Rossko (текстовый поиск).
    """
    if q_type == "sku":
        return ["exist", "autodoc", "rossko"]
    if q_type in ("vin", "name"):
        return ["rossko"]
    return []
