"""Render deterministic Alligator trade-setup SVGs from any saved trade ledger."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from ai_trade.strategy_01 import Strategy01Parameters, alligator_points, load_ohlcv_csv


def _escape(value: object) -> str:
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _selected_indices(total: int, count: int) -> list[int]:
    if total <= count:
        return list(range(total))
    if count == 1:
        return [0]
    return sorted({round(i * (total - 1) / (count - 1)) for i in range(count)})


def _path(values: list[tuple[float, float] | None]) -> str:
    pieces: list[str] = []
    active = False
    for x, value in enumerate(values):
        if value is None:
            active = False
            continue
        px, py = value
        pieces.append(f"{'L' if active else 'M'}{px:.1f},{py:.1f}")
        active = True
    return " ".join(pieces)


def render_chart(bars, points, trade: dict[str, str], trade_number: int, output: Path) -> None:
    index_by_time = {bar.timestamp: index for index, bar in enumerate(bars)}
    entry_index = index_by_time[trade["entry_timestamp"]]
    exit_index = index_by_time[trade["exit_timestamp"]]
    start = max(0, entry_index - 18)
    end = min(len(bars), entry_index + 31)
    if exit_index < end:
        end = min(len(bars), max(end, exit_index + 5))
    rows, indicators = bars[start:end], points[start:end]

    levels = {
        "Entry": float(trade["entry_price"]), "Stop": float(trade["stop_price"]),
        "Target": float(trade["target_price"]), "Exit": float(trade["exit_price"]),
    }
    prices = [value for bar in rows for value in (bar.high, bar.low)] + list(levels.values())
    low, high = min(prices), max(prices)
    pad = max((high - low) * 0.08, 0.01)
    low, high = low - pad, high + pad
    width, height, left, right, top, bottom = 1200, 650, 70, 110, 64, 58
    plot_w, plot_h = width - left - right, height - top - bottom
    xx = lambda index: left + (index + 0.5) * plot_w / len(rows)
    yy = lambda value: top + (high - value) * plot_h / (high - low)
    candle_width = max(2.0, min(15.0, plot_w / len(rows) * 0.56))

    pieces = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="650" viewBox="0 0 1200 650">',
        '<style>.title{font:500 19px sans-serif;fill:#f2f2f2}.sub{font:13px sans-serif;fill:#b8b8b8}.tick{font:11px sans-serif;fill:#b8b8b8}.level{font:500 12px sans-serif}.grid{stroke:#3b3b3b;stroke-width:1}</style>',
        '<rect width="1200" height="650" fill="#171717"/>',
        f'<text x="{left}" y="26" class="title">Trade #{trade_number} · {_escape(trade["side"].upper())} · {_escape(trade["exit_reason"].replace("_", " "))}</text>',
        f'<text x="{left}" y="48" class="sub">Entry {_escape(trade["entry_timestamp"])} · Exit {_escape(trade["exit_timestamp"])} · {float(trade["result_r"]):+.2f}R · ${float(trade["net_pnl"]):+.2f}</text>',
    ]
    for tick in range(6):
        value = low + (high - low) * tick / 5
        py = yy(value)
        pieces.append(f'<line x1="{left}" x2="{width-right}" y1="{py:.1f}" y2="{py:.1f}" class="grid"/>')
        pieces.append(f'<text x="{left-8}" y="{py+4:.1f}" text-anchor="end" class="tick">{value:.2f}</text>')

    for index, bar in enumerate(rows):
        px = xx(index)
        color = "#35a77a" if bar.close >= bar.open else "#d76565"
        body_top, body_bottom = yy(max(bar.open, bar.close)), yy(min(bar.open, bar.close))
        pieces.append(f'<line x1="{px:.1f}" x2="{px:.1f}" y1="{yy(bar.high):.1f}" y2="{yy(bar.low):.1f}" stroke="{color}"/>')
        pieces.append(f'<rect x="{px-candle_width/2:.1f}" y="{body_top:.1f}" width="{candle_width:.1f}" height="{max(body_bottom-body_top,1.4):.1f}" fill="{color}"/>')

    for key, color in (("jaw", "#5898ff"), ("teeth", "#ff557f"), ("lips", "#62cf7c")):
        coordinates = []
        for index, point in enumerate(indicators):
            value = getattr(point, key)
            coordinates.append(None if value is None else (xx(index), yy(value)))
        pieces.append(f'<path d="{_path(coordinates)}" fill="none" stroke="{color}" stroke-width="2.2"/>')

    level_colors = {"Entry": "#f3f3f3", "Stop": "#d76565", "Target": "#35a77a", "Exit": "#a78bfa"}
    entry_x = xx(entry_index - start)
    for label, value in levels.items():
        py, color = yy(value), level_colors[label]
        pieces.append(f'<line x1="{entry_x:.1f}" x2="{width-right}" y1="{py:.1f}" y2="{py:.1f}" stroke="{color}" stroke-width="1.5" stroke-dasharray="6 4"/>')
        pieces.append(f'<text x="{width-right+8}" y="{py+4:.1f}" fill="{color}" class="level">{label} {value:.2f}</text>')
    pieces.append(f'<line x1="{entry_x:.1f}" x2="{entry_x:.1f}" y1="{top}" y2="{height-bottom}" stroke="#f3f3f3" stroke-dasharray="4 4"/>')
    pieces.append(f'<text x="{entry_x:.1f}" y="{top+15}" text-anchor="middle" fill="#f3f3f3" class="level">ENTRY</text>')
    if start <= exit_index < end:
        exit_x = xx(exit_index - start)
        pieces.append(f'<line x1="{exit_x:.1f}" x2="{exit_x:.1f}" y1="{top}" y2="{height-bottom}" stroke="#a78bfa" stroke-dasharray="4 4"/>')
        pieces.append(f'<text x="{exit_x:.1f}" y="{top+30}" text-anchor="middle" fill="#a78bfa" class="level">EXIT</text>')
    pieces.append('</svg>')
    output.write_text("".join(pieces), encoding="utf-8")


def render_batch(bars_path: Path, trades_path: Path, output: Path, count: int) -> dict[str, object]:
    bars = load_ohlcv_csv(bars_path)
    points = alligator_points(bars, Strategy01Parameters())
    with trades_path.open(newline="", encoding="utf-8") as handle:
        trades = list(csv.DictReader(handle))
    if not trades:
        raise ValueError(f"No trades to visualize in {trades_path}")
    output.mkdir(parents=True, exist_ok=True)
    selected = _selected_indices(len(trades), min(count, len(trades)))
    files = []
    for index in selected:
        path = output / f"trade_{index+1:03d}.svg"
        render_chart(bars, points, trades[index], index + 1, path)
        files.append(str(path))
    manifest = {"ledger": str(trades_path), "total_trades": len(trades), "selected_trade_numbers": [i + 1 for i in selected], "files": files}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a deterministic sample of trade setup SVG charts.")
    parser.add_argument("--bars", type=Path, required=True)
    parser.add_argument("--trades", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--count", type=int, default=10)
    args = parser.parse_args()
    manifest = render_batch(args.bars, args.trades, args.output, args.count)
    print(f"Saved {len(manifest['files'])} trade charts to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
