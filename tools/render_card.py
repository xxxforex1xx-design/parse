"""Рендерит HTML-карточку из aggregated-demo.json.

Использование:
    py tools/render_card.py tools/fixtures/aggregated-demo.json
    py tools/render_card.py tools/fixtures/aggregated-demo.json --out card.html

Потом открыть card.html в браузере или сделать скриншот.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

from jinja2 import Environment, FileSystemLoader, select_autoescape  # noqa: E402

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

# Шаблон карточки — лежит рядом со скриптом
CARD_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <title>{{ sku }} — Auto Parts Meta-Search</title>
  <style>
    :root {
      --bg: #0f1419;
      --card-bg: #1a2128;
      --card-bg-2: #232b34;
      --text: #e6edf3;
      --text-muted: #8b949e;
      --accent: #2f81f7;
      --accent-2: #1f6feb;
      --border: #30363d;
      --good: #3fb950;
      --warn: #d29922;
      --bad: #f85149;
      --best: #ffd700;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      padding: 24px;
      line-height: 1.5;
    }
    .container { max-width: 1100px; margin: 0 auto; }
    header {
      border-bottom: 1px solid var(--border);
      padding-bottom: 16px;
      margin-bottom: 24px;
    }
    h1 { font-size: 24px; font-weight: 600; }
    .sku { color: var(--text-muted); font-family: ui-monospace, monospace; }
    .summary {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 12px;
      margin-bottom: 24px;
    }
    .stat {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
    }
    .stat-label {
      font-size: 12px;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 4px;
    }
    .stat-value { font-size: 22px; font-weight: 600; }
    .stat-value.best { color: var(--best); }
    .best-section {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 12px;
      margin-bottom: 24px;
    }
    .best-card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-left: 4px solid var(--accent);
      border-radius: 8px;
      padding: 16px;
    }
    .best-card.original { border-left-color: var(--good); }
    .best-card.instock { border-left-color: var(--warn); }
    .best-card .source {
      font-size: 11px;
      color: var(--text-muted);
      text-transform: uppercase;
      margin-bottom: 8px;
    }
    .best-card .price {
      font-size: 24px;
      font-weight: 700;
      color: var(--best);
      margin-bottom: 8px;
    }
    .best-card .brand {
      font-size: 14px;
      color: var(--accent);
      font-weight: 600;
    }
    .best-card .meta {
      font-size: 11px;
      color: var(--text-muted);
      margin-top: 8px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      overflow: hidden;
    }
    th {
      background: var(--card-bg-2);
      text-align: left;
      padding: 12px 16px;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: var(--text-muted);
      font-weight: 600;
      border-bottom: 1px solid var(--border);
    }
    td {
      padding: 12px 16px;
      border-bottom: 1px solid var(--border);
      font-size: 14px;
    }
    tr:last-child td { border-bottom: none; }
    tr:hover td { background: var(--card-bg-2); }
    .source-badge {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
    }
    .source-exist { background: #1f3d5c; color: #79c0ff; }
    .source-autodoc { background: #5c3d1f; color: #ffa657; }
    .source-rossko { background: #1f5c3d; color: #7ee787; }
    .original-badge {
      display: inline-block;
      padding: 2px 6px;
      border-radius: 3px;
      font-size: 10px;
      font-weight: 600;
      background: var(--good);
      color: #000;
      margin-left: 4px;
    }
    .price-cell { font-weight: 600; color: var(--best); }
    .footer {
      margin-top: 32px;
      padding-top: 16px;
      border-top: 1px solid var(--border);
      font-size: 12px;
      color: var(--text-muted);
      text-align: center;
    }
  </style>
</head>
<body>
<div class="container">
  <header>
    <h1>Карточка запчасти</h1>
    <div class="sku">SKU: {{ sku }}</div>
  </header>

  <div class="summary">
    <div class="stat">
      <div class="stat-label">Офферов</div>
      <div class="stat-value">{{ card.offers_count }}</div>
    </div>
    <div class="stat">
      <div class="stat-label">Брендов</div>
      <div class="stat-value">{{ card.brands_count }}</div>
    </div>
    <div class="stat">
      <div class="stat-label">Мин. цена</div>
      <div class="stat-value">{{ "%.0f"|format(card.min_price) }} ₽</div>
    </div>
    <div class="stat">
      <div class="stat-label">Макс. цена</div>
      <div class="stat-value">{{ "%.0f"|format(card.max_price) }} ₽</div>
    </div>
  </div>

  <div class="best-section">
    <div class="best-card instock">
      <div class="source">Лучшая цена</div>
      <div class="price">{{ "%.0f"|format(card.best_price.price) }} ₽</div>
      <div class="brand">{{ card.best_price.brand }}</div>
      <div class="meta">
        <span class="source-badge source-{{ card.best_price.source }}">{{ card.best_price.source }}</span>
        {% if card.best_price.is_original %}<span class="original-badge">ОРИГИНАЛ</span>{% endif %}
      </div>
    </div>
    {% if card.best_original %}
    <div class="best-card original">
      <div class="source">Лучший оригинал</div>
      <div class="price">{{ "%.0f"|format(card.best_original.price) }} ₽</div>
      <div class="brand">{{ card.best_original.brand }}</div>
      <div class="meta">
        <span class="source-badge source-{{ card.best_original.source }}">{{ card.best_original.source }}</span>
        <span class="original-badge">ОРИГИНАЛ</span>
      </div>
    </div>
    {% endif %}
    {% if card.best_in_stock %}
    <div class="best-card">
      <div class="source">Лучшее в наличии</div>
      <div class="price">{{ "%.0f"|format(card.best_in_stock.price) }} ₽</div>
      <div class="brand">{{ card.best_in_stock.brand }}</div>
      <div class="meta">
        <span class="source-badge source-{{ card.best_in_stock.source }}">{{ card.best_in_stock.source }}</span>
        {% if card.best_in_stock.is_original %}<span class="original-badge">ОРИГИНАЛ</span>{% endif %}
      </div>
    </div>
    {% endif %}
  </div>

  <h2 style="margin-bottom:12px; font-size:18px;">Все бренды</h2>
  <table>
    <thead>
      <tr>
        <th>Бренд</th>
        <th>Мин. цена</th>
        <th>Макс. цена</th>
        <th>Офферов</th>
        <th>Источники</th>
        <th>Оригинал</th>
      </tr>
    </thead>
    <tbody>
      {% for b in card.brands %}
      <tr>
        <td>
          <strong>{{ b.brand }}</strong>
          {% if b.is_original %}<span class="original-badge">ОРИГИНАЛ</span>{% endif %}
        </td>
        <td class="price-cell">{{ "%.0f"|format(b.min_price) }} ₽</td>
        <td>{{ "%.0f"|format(b.max_price) }} ₽</td>
        <td>{{ b.offers_count }}</td>
        <td>
          {% for src in b.sources %}
          <span class="source-badge source-{{ src }}">{{ src }}</span>
          {% endfor %}
        </td>
        <td>{{ "да" if b.is_original else "—" }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>

  <div class="footer">
    Auto Parts Meta-Search · {{ card.sources|length }} источника:
    {{ card.sources|join(", ") }} ·
    Сгенерировано из {{ source_file }}
  </div>
</div>
</body>
</html>
"""


def render(data: dict, source_file: str) -> str:
    cards = data.get("cards", [])
    if not cards:
        return "<h1>Нет данных</h1>"
    card = cards[0]
    sku = card.get("sku", "?")
    env = Environment(autoescape=select_autoescape(("html",)))
    tpl = env.from_string(CARD_TEMPLATE)
    return tpl.render(card=card, sku=sku, source_file=source_file)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("json_file", type=Path)
    p.add_argument("--out", type=Path, default=None,
                   help="Куда сохранить HTML (по умолчанию — рядом с JSON)")
    args = p.parse_args()

    if not args.json_file.exists():
        print(f"[!] Не найден {args.json_file}", file=sys.stderr)
        return 1

    data = json.loads(args.json_file.read_text(encoding="utf-8"))
    html = render(data, args.json_file.name)

    out = args.out or args.json_file.with_suffix(".html")
    out.write_text(html, encoding="utf-8")
    print(f"[+] HTML: {out}")
    print(f"[i] Открой в браузере: file:///{out.as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
