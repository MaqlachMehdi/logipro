"""Shared Plotly HTML rendering utilities."""

from __future__ import annotations

import json
import os


def write_html(output_file: str, html: str) -> None:
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)


def wrap_plotly_page(title: str, subtitle: str, chart_div_id: str,
                     stats_cards: list[tuple[str, str]],
                     plotly_js: str, note: str = "") -> str:
    """Return a full standalone HTML page with the dark theme from viz_3D.py.

    Parameters
    ----------
    stats_cards : list of (label, value) pairs rendered as metric cards.
    plotly_js   : raw JS that calls Plotly.newPlot on *chart_div_id*.
    """
    cards_html = "\n".join(
        f'<div class="card"><div class="card-label">{label}</div>'
        f'<div class="card-value">{value}</div></div>'
        for label, value in stats_cards
    )
    note_html = f'<div class="note">{note}</div>' if note else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", Tahoma, sans-serif;
      background: radial-gradient(circle at top, #1f355c 0%, #0d1526 55%, #070b14 100%);
      color: #eef3ff;
      min-height: 100vh;
    }}
    .page {{
      width: min(1400px, calc(100vw - 32px));
      margin: 24px auto;
      padding: 24px;
      border-radius: 24px;
      background: rgba(7, 13, 24, 0.78);
      border: 1px solid rgba(255, 255, 255, 0.08);
      box-shadow: 0 24px 80px rgba(0, 0, 0, 0.35);
      backdrop-filter: blur(16px);
    }}
    h1 {{ margin: 0 0 8px; font-size: 32px; }}
    p {{ margin: 0; color: #b8c6ea; }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin: 24px 0;
    }}
    .card {{
      padding: 16px;
      border-radius: 16px;
      background: linear-gradient(180deg, rgba(255,255,255,0.09), rgba(255,255,255,0.03));
      border: 1px solid rgba(255,255,255,0.08);
    }}
    .card-label {{ font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; color: #8ea4d8; }}
    .card-value {{ margin-top: 8px; font-size: 26px; font-weight: 700; color: #ffffff; }}
    .chart {{ height: 700px; border-radius: 18px; overflow: hidden; }}
    .note {{ margin-top: 14px; font-size: 14px; color: #90a5d1; }}
  </style>
</head>
<body>
  <div class="page">
    <h1>{title}</h1>
    <p>{subtitle}</p>
    <div class="stats">{cards_html}</div>
    <div id="{chart_div_id}" class="chart"></div>
    {note_html}
  </div>
  <script>
{plotly_js}
  </script>
</body>
</html>
"""
