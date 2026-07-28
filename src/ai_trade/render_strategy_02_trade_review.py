"""Render deterministic SVG candlestick reviews from Strategy 02 trade logs."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from ai_trade.strategy_01 import load_ohlcv_csv


def _escape(value: object) -> str:
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _panel(rows, trade: dict[str, str], x0: int, y0: int, width: int, height: int, number: int) -> str:
    entry_index = next(i for i, bar in enumerate(rows) if bar.timestamp == trade["entry_timestamp"])
    exit_index = next(i for i, bar in enumerate(rows) if bar.timestamp == trade["exit_timestamp"])
    start, end = max(0, entry_index - 10), min(len(rows), exit_index + 11)
    bars = rows[start:end]
    prices = [value for bar in bars for value in (bar.high, bar.low)] + [
        float(trade["entry_price"]), float(trade["stop_price"]), float(trade["target_price"]), float(trade["exit_price"])
    ]
    low, high = min(prices), max(prices)
    pad = max((high - low) * 0.08, 0.20)
    low, high = low - pad, high + pad
    margin = {"left": 38, "right": 58, "top": 30, "bottom": 28}
    plot_w, plot_h = width - margin["left"] - margin["right"], height - margin["top"] - margin["bottom"]
    xx = lambda index: x0 + margin["left"] + (index + 0.5) * plot_w / len(bars)
    yy = lambda value: y0 + margin["top"] + (high - value) * plot_h / (high - low)
    side = trade["side"]
    fill_up, fill_down = "#35a77a", "#d76565"
    pieces = [f'<g><text x="{x0 + 4}" y="{y0 + 15}" class="label">#{number} {_escape(side.upper())} · {_escape(trade["exit_reason"].replace("_", " "))}</text>']
    for tick in range(4):
        value = low + (high - low) * tick / 3
        py = yy(value)
        pieces.append(f'<line x1="{x0 + margin["left"]}" x2="{x0 + width - margin["right"]}" y1="{py:.1f}" y2="{py:.1f}" class="grid"/>')
        pieces.append(f'<text x="{x0 + margin["left"] - 4}" y="{py + 3:.1f}" text-anchor="end" class="tick">{value:.2f}</text>')
    for index, bar in enumerate(bars):
        px, rising = xx(index), bar.close >= bar.open
        color = fill_up if rising else fill_down
        top, bottom = yy(max(bar.open, bar.close)), yy(min(bar.open, bar.close))
        candle_width = max(1.0, plot_w / len(bars) * 0.55)
        pieces.append(f'<line x1="{px:.1f}" x2="{px:.1f}" y1="{yy(bar.high):.1f}" y2="{yy(bar.low):.1f}" stroke="{color}"/>')
        pieces.append(f'<rect x="{px - candle_width / 2:.1f}" y="{top:.1f}" width="{candle_width:.1f}" height="{max(bottom-top, 1.2):.1f}" fill="{color}"/>')
    levels = [("Entry", float(trade["entry_price"]), "#ffffff"), ("Stop", float(trade["stop_price"]), "#d76565"),
              ("Target", float(trade["target_price"]), "#35a77a"), ("Exit", float(trade["exit_price"]), "#a78bfa")]
    entry_x, exit_x = xx(entry_index - start), xx(exit_index - start)
    for label, value, color in levels:
        py = yy(value)
        pieces.append(f'<line x1="{entry_x:.1f}" x2="{x0 + width - margin["right"]}" y1="{py:.1f}" y2="{py:.1f}" stroke="{color}" stroke-width="1.25"/>')
        pieces.append(f'<text x="{x0 + width - margin["right"] + 3}" y="{py + 3:.1f}" fill="{color}" class="tick">{label}</text>')
    pieces.append(f'<line x1="{entry_x:.1f}" x2="{entry_x:.1f}" y1="{y0 + margin["top"]}" y2="{y0 + height-margin["bottom"]}" class="marker"/>')
    pieces.append(f'<line x1="{exit_x:.1f}" x2="{exit_x:.1f}" y1="{y0 + margin["top"]}" y2="{y0 + height-margin["bottom"]}" class="exit"/>')
    pieces.append(f'<text x="{x0 + 4}" y="{y0 + height - 7}" class="tick">Entry {_escape(trade["entry_timestamp"][:16])} · Exit {_escape(trade["exit_timestamp"][:16])} · Net ${float(trade["net_pnl"]):+.2f}</text></g>')
    return "".join(pieces)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars", type=Path, default=Path("data/market_data/ibkr/SPY/v4_2y/spy_15m.csv"))
    parser.add_argument("--trades", type=Path, default=Path("strategies/strategy_02/v1_5/results/backtest/fixed_trades.csv"))
    parser.add_argument("--output", type=Path, default=Path("strategies/strategy_02/v1_5/results/backtest/trade_review.svg"))
    args = parser.parse_args()
    bars = load_ohlcv_csv(args.bars)
    with args.trades.open(newline="", encoding="utf-8") as handle:
        trades = list(csv.DictReader(handle))
    # Target win, Friday close win, stop loss, Friday close loss.
    selected = [trades[0], trades[1], trades[10], trades[7]]
    panels = "".join(_panel(bars, trade, 0 if i % 2 == 0 else 600, 0 if i < 2 else 330, 580, 310, trades.index(trade) + 1)
                     for i, trade in enumerate(selected))
    document = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="640" viewBox="0 0 1200 640">
<style>.grid{{stroke:#555;stroke-width:.6}}.label{{fill:#eee;font:16px sans-serif}}.tick{{fill:#c4c4c4;font:11px sans-serif}}.marker{{stroke:#fff;stroke-dasharray:4 3}}.exit{{stroke:#a78bfa;stroke-dasharray:3 3}}</style>
<rect width="1200" height="640" fill="#171717"/>{panels}</svg>'''
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(document, encoding="utf-8")
    print(f"Saved {args.output}")


if __name__ == "__main__":
    main()
