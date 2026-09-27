"""Интерактивный поиск деталей.

Запуск:
    py tools/interactive_search.py

Что делает:
1. Спрашивает артикул у пользователя
2. Парсит 3 источника через Playwright (rate-limit 15-30 сек между)
3. Агрегирует через aggregator.py
4. Печатает красивую карточку через Rich

Команды в REPL:
    <SKU>          — поиск
    /sources       — показать включённые источники
    /toggle NAME  — вкл/выкл источник (exist, autodoc, rossko)
    /delay MIN MAX — паузы между запросами (по умолчанию 15-30)
    /quit, /q     — выход
"""

from __future__ import annotations

import os
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

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE / "tools"))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from rate_limited_parser import (  # noqa: E402
    parse_exist, parse_autodoc, parse_rossko,
    UA,
)
from aggregator import aggregate  # noqa: E402
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout  # noqa: E402

console = Console()

DEFAULT_SOURCES = {"exist", "autodoc", "rossko"}


def normalize_sku(sku: str) -> str:
    """Канонизация: убираем пробелы, дефисы, верхний регистр."""
    return sku.replace(" ", "").replace("-", "").replace("/", "").strip().upper()


def print_card(card: dict[str, Any]) -> None:
    """Красивый вывод карточки."""
    if card.get("best_price"):
        bp = card["best_price"]
        title = (
            f"[bold cyan]{card['sku']}[/bold cyan]  ·  "
            f"[green]{bp['price']:.0f} ₽[/green]  ·  "
            f"{bp['source']}/{bp['brand']}"
        )
        console.print(Panel(title, border_style="cyan"))

    table = Table(show_header=True, header_style="bold magenta", title="Все офферы")
    table.add_column("Цена", justify="right", style="green")
    table.add_column("Бренд", style="cyan")
    table.add_column("Источник", style="yellow")
    table.add_column("В наличии", justify="center")
    table.add_column("Оригинал", justify="center")
    table.add_column("Вариантов", justify="right")

    # Достаём все офферы из brands (агрегатор не хранит flat list, поэтому собираем из файла)
    # Это упрощение — реальные офферы в JSONL на диске, но для интерактива покажем brand-summary
    for b in card.get("brands", []):
        original = "[bold]✓[/bold]" if b["is_original"] else ""
        sources = ",".join(b.get("sources", []))
        table.add_row(
            f"{b['min_price']:.0f}–{b['max_price']:.0f}",
            b["brand"],
            sources,
            "✓" if b.get("in_stock") else "?",
            original,
            str(b["offers_count"]),
        )
    console.print(table)

    # Сводка
    summary = (
        f"[dim]Офферов: {card['offers_count']}  ·  "
        f"Брендов: {card['brands_count']}  ·  "
        f"Диапазон: {card['min_price']:.0f}–{card['max_price']:.0f} ₽[/dim]"
    )
    console.print(summary)

    if card.get("best_original"):
        bo = card["best_original"]
        console.print(
            f"\n[bold green]★ Лучший ОРИГИНАЛ:[/bold green] "
            f"{bo['brand']} — {bo['price']:.0f} ₽ ({bo['source']})"
        )
    if card.get("best_in_stock") and card["best_in_stock"] != card["best_price"]:
        bis = card["best_in_stock"]
        console.print(
            f"[bold]★ Лучший в наличии:[/bold] "
            f"{bis['brand']} — {bis['price']:.0f} ₽ ({bis['source']})"
        )


def run_one(sku: str, sources: set[str], min_delay: float, max_delay: float,
            browser, page) -> list[dict[str, Any]]:
    """Парсит один SKU по списку источников. Возвращает плоский список офферов."""
    records: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc).isoformat()

    parsers = {
        "exist": lambda: _parse_exist(page, sku, now, records),
        "autodoc": lambda: _parse_autodoc(page, sku, now, records),
        "rossko": lambda: _parse_rossko(page, sku, now, records),
    }

    for i, src in enumerate(sources):
        if i > 0:
            delay = min_delay + (max_delay - min_delay) * (0.5 + 0.5 * (hash(sku) % 100) / 100)
            console.print(f"[dim]Пауза {delay:.1f}с...[/dim]")
            time.sleep(delay)
        console.print(f"[yellow]>>> Парсим {src}...[/yellow]")
        try:
            parsers[src]()
            console.print(f"[green]✓ {src} готово[/green]")
        except PWTimeout as e:
            console.print(f"[red]✗ {src} timeout: {e}[/red]")
        except Exception as e:
            console.print(f"[red]✗ {src} fail: {e}[/red]")
    return records


def _parse_exist(page, sku: str, now: str, records: list) -> None:
    parsed = parse_exist(page, sku)
    for off in parsed.get("offers", []):
        for v in off.get("variants", []):
            if v.get("price_value") is None:
                continue
            records.append({
                "source": "exist",
                "sku": sku,
                "brand": off.get("brand") or off.get("art"),
                "name": off.get("descr"),
                "price_value": v["price_value"],
                "price_text": v.get("price_text"),
                "is_best_offer": v.get("is_best_offer"),
                "flags": None,
                "url": parsed.get("url"),
                "scraped_at": now,
            })


def _parse_autodoc(page, sku: str, now: str, records: list) -> None:
    parsed = parse_autodoc(page, sku)
    c = parsed.get("card") or {}
    if c.get("price_value") is not None:
        records.append({
            "source": "autodoc",
            "sku": sku,
            "brand": c.get("brand"),
            "name": c.get("name"),
            "price_value": c["price_value"],
            "price_text": c.get("price_text"),
            "is_available": True,
            "flags": None,
            "url": parsed.get("url"),
            "scraped_at": now,
        })


def _parse_rossko(page, sku: str, now: str, records: list) -> None:
    parsed = parse_rossko(page, sku)
    for off in parsed.get("offers", []):
        if off.get("price_value") is None:
            continue
        records.append({
            "source": "rossko",
            "sku": sku,
            "brand": off.get("brand"),
            "name": off.get("name"),
            "price_value": off["price_value"],
            "price_text": off.get("price_text"),
            "is_available": off.get("is_available"),
            "flags": off.get("flags"),
            "url": parsed.get("url"),
            "scraped_at": now,
        })


def main() -> int:
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--sku", help="Один SKU (если задан — без REPL, сразу парсим и выходим)")
    p.add_argument("--no-exist", action="store_true")
    p.add_argument("--no-autodoc", action="store_true")
    p.add_argument("--no-rossko", action="store_true")
    p.add_argument("--min-delay", type=float, default=15.0)
    p.add_argument("--max-delay", type=float, default=30.0)
    args = p.parse_args()

    sources = set(DEFAULT_SOURCES)
    if args.no_exist:
        sources.discard("exist")
    if args.no_autodoc:
        sources.discard("autodoc")
    if args.no_rossko:
        sources.discard("rossko")

    if not sources:
        console.print("[red]Все источники выключены[/red]")
        return 1

    console.print(Panel.fit(
        f"[bold]Auto Parts Meta-Search[/bold]\n"
        f"Источники: {', '.join(sorted(sources))}\n"
        f"Паузы: {args.min_delay}-{args.max_delay}с",
        border_style="cyan",
    ))

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
        )
        ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        page = ctx.new_page()

        try:
            # Если передан --sku, делаем один запрос и выходим
            if args.sku:
                sku = normalize_sku(args.sku)
                console.print(f"[cyan]Ищу SKU = {sku}[/cyan]")
                t0 = time.monotonic()
                records = run_one(sku, sources, args.min_delay, args.max_delay, browser, page)
                elapsed = time.monotonic() - t0
                if not records:
                    console.print(f"[red]Нет данных по {sku}[/red]")
                    return 1
                result = aggregate(records)
                console.print(f"[dim]{len(records)} офферов за {elapsed:.1f}с[/dim]")
                for card in result["cards"]:
                    print_card(card)
                return 0

            # REPL
            console.print(
                "Введите артикул (например, 6RU698151).\n"
                "Команды: /sources · /toggle NAME · /delay MIN MAX · /q"
            )
            while True:
                try:
                    raw = console.input("\n[bold]SKU>[/bold] ").strip()
                except (EOFError, KeyboardInterrupt):
                    break
                if not raw:
                    continue
                if raw in ("/q", "/quit", "exit"):
                    break
                if raw == "/sources":
                    console.print(f"[dim]Источники: {sorted(sources)}[/dim]")
                    continue
                if raw.startswith("/toggle "):
                    name = raw.split()[1]
                    if name in DEFAULT_SOURCES:
                        if name in sources:
                            sources.discard(name)
                            console.print(f"[yellow]- {name} выключен[/yellow]")
                        else:
                            sources.add(name)
                            console.print(f"[green]+ {name} включён[/green]")
                    else:
                        console.print(f"[red]Неизвестный: {name}. Доступные: {DEFAULT_SOURCES}[/red]")
                    continue
                if raw.startswith("/delay "):
                    parts = raw.split()
                    if len(parts) == 3:
                        args.min_delay = float(parts[1])
                        args.max_delay = float(parts[2])
                        console.print(f"[dim]Паузы: {args.min_delay}-{args.max_delay}с[/dim]")
                    continue

                sku = normalize_sku(raw)
                console.print(f"[cyan]Ищу SKU = {sku}[/cyan]")

                t0 = time.monotonic()
                records = run_one(sku, sources, args.min_delay, args.max_delay, browser, page)
                elapsed = time.monotonic() - t0

                if not records:
                    console.print(f"[red]Нет данных по {sku}[/red]")
                    continue

                result = aggregate(records)
                console.print(f"[dim]{len(records)} офферов за {elapsed:.1f}с[/dim]")

                for card in result["cards"]:
                    print_card(card)
        finally:
            browser.close()

    console.print("\n[dim]До свидания.[/dim]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
