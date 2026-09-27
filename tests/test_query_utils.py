"""Тесты query_utils.py — нормализация пользовательского ввода."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE / "tools"))

from query_utils import (  # noqa: E402
    normalize_query, cache_key_for_query, sources_for_query_type,
)


# ── normalize_query: SKU ────────────────────────────────────────────────


def test_normalize_query_sku_basic():
    """Простой артикул: 6RU698151."""
    assert normalize_query("6RU698151") == ("sku", "6RU698151")


def test_normalize_query_sku_with_spaces_and_dashes():
    """'6RU 698 151' и '04465-33450' нормализуются."""
    assert normalize_query("6RU 698 151") == ("sku", "6RU698151")
    assert normalize_query("04465-33450") == ("sku", "0446533450")
    assert normalize_query("04465/33450") == ("sku", "0446533450")


def test_normalize_query_sku_lowercase_uppercased():
    """Нижний регистр приводится к верхнему."""
    assert normalize_query("6ru698151") == ("sku", "6RU698151")


def test_normalize_query_too_short_is_name():
    """Короче 4 символов — это name (например, '6RU')."""
    q_type, _ = normalize_query("6RU")
    assert q_type == "name"


def test_normalize_query_too_long_is_name():
    """Длиннее 20 символов без пробелов — name."""
    q_type, _ = normalize_query("ABCDEFGHIJKLMNOPQRSTU")  # 21
    assert q_type == "name"


# ── normalize_query: VIN ────────────────────────────────────────────────


def test_normalize_query_vin_basic():
    """17 символов alnum → VIN."""
    vin = "WBA3A5C57CF256789"
    assert normalize_query(vin) == ("vin", vin)


def test_normalize_query_vin_lowercase_uppercased():
    vin = "wba3a5c57cf256789"
    assert normalize_query(vin) == ("vin", "WBA3A5C57CF256789")


def test_normalize_query_vin_with_dashes():
    """VIN с дефисами/пробелами тоже ок."""
    assert normalize_query("WBA3A5C5-7CF256789") == ("vin", "WBA3A5C57CF256789")


def test_normalize_query_not_vin_if_too_long():
    """21 alnum символ — не VIN, и не SKU (>20). Это name."""
    q_type, _ = normalize_query("ABCDEFGHIJKLMNOPQRSTU")  # 21
    assert q_type == "name"


def test_normalize_query_with_spaces_is_name():
    """С пробелами — текстовый поиск."""
    assert normalize_query("тормозные колодки") == ("name", "тормозные колодки")
    assert normalize_query("масляный фильтр VW Polo") == (
        "name", "масляный фильтр VW Polo"
    )


# ── normalize_query: edge cases ─────────────────────────────────────────


def test_normalize_query_empty():
    assert normalize_query("") == ("empty", "")
    assert normalize_query("   ") == ("empty", "")
    assert normalize_query("\t\n") == ("empty", "")


def test_normalize_query_only_separators():
    """Если только пробелы/дефисы — empty."""
    assert normalize_query("---") == ("empty", "")
    assert normalize_query("   ") == ("empty", "")


def test_normalize_query_russian_text():
    """Кириллица — name."""
    assert normalize_query("тормозные колодки") == ("name", "тормозные колодки")


def test_normalize_query_special_chars_is_name():
    """Спецсимволы (не alnum) → name."""
    q_type, val = normalize_query("6RU@698151")
    assert q_type == "name"
    assert val == "6RU@698151"


# ── cache_key_for_query ─────────────────────────────────────────────────


def test_cache_key_for_sku_is_plain():
    """SKU → plain filename."""
    assert cache_key_for_query("sku", "6RU698151") == "6RU698151"


def test_cache_key_for_vin_is_hashed():
    """VIN → vin_<md5[:16]>."""
    key = cache_key_for_query("vin", "WBA3A5C57CF256789")
    assert key.startswith("vin_")
    assert len(key) == 4 + 16
    # детерминированность
    assert key == cache_key_for_query("vin", "WBA3A5C57CF256789")
    # разные VIN → разные ключи
    assert key != cache_key_for_query("vin", "XW7BF4FK50S123456")


def test_cache_key_for_name_is_hashed():
    key = cache_key_for_query("name", "тормозные колодки")
    assert key.startswith("name_")
    assert len(key) == 5 + 16


def test_cache_key_name_is_deterministic():
    """Один и тот же текст → один ключ."""
    k1 = cache_key_for_query("name", "тормозные колодки")
    k2 = cache_key_for_query("name", "тормозные колодки")
    assert k1 == k2


def test_cache_key_different_texts_different_keys():
    """Разный текст → разные ключи."""
    k1 = cache_key_for_query("name", "тормозные колодки")
    k2 = cache_key_for_query("name", "масляный фильтр")
    assert k1 != k2


# ── sources_for_query_type ──────────────────────────────────────────────


def test_sources_for_sku_all_three():
    assert sources_for_query_type("sku") == ["exist", "autodoc", "rossko"]


def test_sources_for_vin_only_rossko():
    assert sources_for_query_type("vin") == ["rossko"]


def test_sources_for_name_only_rossko():
    assert sources_for_query_type("name") == ["rossko"]


def test_sources_for_empty_none():
    assert sources_for_query_type("empty") == []
