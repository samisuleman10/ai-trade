"""Render deterministic Strategy 04 zone-reaction trade charts."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from ai_trade.strategy_01 import load_ohlcv_csv


def _escape(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _selected_indices(total: int, count: int) -> list[int]:
    if total <= count:
        return list(range(total))
    if count <= 1:
        return [0]
    return sorted({round(index * (total - 1) / (count - 1)) for index in range(count)})


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def render_chart(
    bars,
    trade: dict[str, str],
    signal: dict[str, str],
    trade_number: int,
    output: Path,
) -> None:
    by_time = {bar.timestamp: index for index, bar in enumerate(bars)}
    entry_index = by_time[trade["entry_timestamp"]]
    exit_index = by_time[trade["exit_timestamp"]]
    trigger_index = by_time[signal["trigger_timestamp"]]
    start = max(0, trigger_index - 20)
    end = min(len(bars), max(entry_index + 36, exit_index + 5))
    rows = bars[start:end]

    entry = float(trade["entry_price"])
    stop = float(trade["stop_price"])
    target = float(trade["target_price"])
    exit_price = float(trade["exit_price"])
    zone_lower = float(signal["zone_lower"])
    zone_upper = float(signal["zone_upper"])
    prices = [
        value
        for bar in rows
        for value in (bar.high, bar.low)
    ] + [entry, stop, target, exit_price, zone_lower, zone_upper]
    low, high = min(prices), max(prices)
    padding = max((high - low) * 0.08, 0.01)
    low, high = low - padding, high + padding

    width, height = 1300, 720
    left, right, top, bottom = 76, 135, 82, 70
    plot_width, plot_height = width - left - right, height - top - bottom
    x = lambda index: left + (index + 0.5) * plot_width / len(rows)
    y = lambda price: top + (high - price) * plot_height / (high - low)
    candle_width = max(1.2, min(14.0, plot_width / len(rows) * 0.58))
    side = trade["side"]
    zone_color = "#35c98f" if side == "long" else "#ef6673"
    zone_name = "DEMAND" if side == "long" else "SUPPLY"

    pieces = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1300" height="720" viewBox="0 0 1300 720">',
        '<style>.title{font:500 20px sans-serif;fill:#f4f6fa}.sub{font:13px sans-serif;fill:#aeb6c4}.tick{font:11px sans-serif;fill:#9ca6b6}.level{font:500 12px sans-serif}.grid{stroke:#303642;stroke-width:1}.meta{font:500 13px sans-serif}</style>',
        '<rect width="1300" height="720" fill="#11141a"/>',
        (
            f'<text x="{left}" y="30" class="title">Trade #{trade_number} · '
            f'{_escape(side.upper())} · {_escape(trade["exit_reason"].replace("_", " "))}</text>'
        ),
        (
            f'<text x="{left}" y="53" class="sub">Zone #{_escape(signal["zone_id"])} '
            f'{zone_name} Q{_escape(signal["qualified_score"])}/C{_escape(signal["current_score"])} · '
            f'Trigger {_escape(signal["trigger_timestamp"])} · Entry {_escape(trade["entry_timestamp"])} · '
            f'Exit {_escape(trade["exit_timestamp"])} · {float(trade["result_r"]):+.2f}R · '
            f'USD {float(trade["net_pnl"]):+.2f}</text>'
        ),
    ]

    for tick in range(6):
        value = low + (high - low) * tick / 5
        py = y(value)
        pieces.append(
            f'<line x1="{left}" x2="{width-right}" y1="{py:.1f}" y2="{py:.1f}" class="grid"/>'
        )
        pieces.append(
            f'<text x="{left-8}" y="{py+4:.1f}" text-anchor="end" class="tick">{value:.2f}</text>'
        )

    zone_start_x = x(max(0, trigger_index - start - 8))
    zone_end_x = width - right
    zone_top, zone_bottom = y(zone_upper), y(zone_lower)
    pieces.append(
        f'<rect x="{zone_start_x:.1f}" y="{zone_top:.1f}" width="{zone_end_x-zone_start_x:.1f}" '
        f'height="{max(zone_bottom-zone_top, 2):.1f}" fill="{zone_color}" fill-opacity="0.16" '
        f'stroke="{zone_color}" stroke-width="1.6"/>'
    )
    pieces.append(
        f'<text x="{zone_start_x+8:.1f}" y="{max(top+15, zone_top-7):.1f}" '
        f'fill="{zone_color}" class="meta">1h {zone_name} · Q{_escape(signal["qualified_score"])}/C{_escape(signal["current_score"])}</text>'
    )

    for index, bar in enumerate(rows):
        px = x(index)
        color = "#35ae82" if bar.close >= bar.open else "#e25d62"
        body_top = y(max(bar.open, bar.close))
        body_bottom = y(min(bar.open, bar.close))
        pieces.append(
            f'<line x1="{px:.1f}" x2="{px:.1f}" y1="{y(bar.high):.1f}" y2="{y(bar.low):.1f}" stroke="{color}"/>'
        )
        pieces.append(
            f'<rect x="{px-candle_width/2:.1f}" y="{body_top:.1f}" width="{candle_width:.1f}" '
            f'height="{max(body_bottom-body_top, 1.4):.1f}" fill="{color}"/>'
        )

    entry_x = x(entry_index - start)
    trigger_x = x(trigger_index - start)
    exit_x = x(exit_index - start)
    pieces.append(
        f'<line x1="{trigger_x:.1f}" x2="{trigger_x:.1f}" y1="{top}" y2="{height-bottom}" '
        f'stroke="#ffd166" stroke-width="1.7" stroke-dasharray="5 4"/>'
    )
    pieces.append(
        f'<text x="{trigger_x:.1f}" y="{top+17}" text-anchor="middle" fill="#ffd166" class="level">15m TRIGGER</text>'
    )
    pieces.append(
        f'<line x1="{entry_x:.1f}" x2="{entry_x:.1f}" y1="{top}" y2="{height-bottom}" '
        f'stroke="#f5f7fa" stroke-width="1.5" stroke-dasharray="5 4"/>'
    )
    pieces.append(
        f'<text x="{entry_x:.1f}" y="{top+34}" text-anchor="middle" fill="#f5f7fa" class="level">ENTRY</text>'
    )
    pieces.append(
        f'<line x1="{exit_x:.1f}" x2="{exit_x:.1f}" y1="{top}" y2="{height-bottom}" '
        f'stroke="#a98bf5" stroke-width="1.5" stroke-dasharray="5 4"/>'
    )
    pieces.append(
        f'<text x="{exit_x:.1f}" y="{top+51}" text-anchor="middle" fill="#a98bf5" class="level">EXIT</text>'
    )

    levels = [
        ("Entry", entry, "#f5f7fa"),
        ("Stop", stop, "#ef6673"),
        ("Target", target, "#35c98f"),
        ("Exit", exit_price, "#a98bf5"),
    ]
    for label, value, color in levels:
        py = y(value)
        pieces.append(
            f'<line x1="{entry_x:.1f}" x2="{width-right}" y1="{py:.1f}" y2="{py:.1f}" '
            f'stroke="{color}" stroke-width="1.4" stroke-dasharray="7 4"/>'
        )
        pieces.append(
            f'<text x="{width-right+8}" y="{py+4:.1f}" fill="{color}" class="level">{label} {value:.2f}</text>'
        )

    label_every = max(1, len(rows) // 6)
    for index in range(0, len(rows), label_every):
        stamp = rows[index].timestamp[5:16].replace("T", " ")
        pieces.append(
            f'<text x="{x(index):.1f}" y="{height-bottom+24}" text-anchor="middle" class="tick">{stamp}</text>'
        )
    pieces.append(
        f'<text x="{left}" y="{height-18}" class="sub">Stop buffer: {float(signal["stop_buffer"]):.3f} · '
        f'1h ATR: {float(signal["one_hour_atr"]):.3f} · Conservative collision rule: stop before target</text>'
    )
    pieces.append("</svg>")
    output.write_text("".join(pieces), encoding="utf-8")


def render_batch(
    bars_path: Path,
    signals_path: Path,
    trades_path: Path,
    output: Path,
    count: int,
) -> dict[str, object]:
    bars = load_ohlcv_csv(bars_path)
    signals = _read_csv(signals_path)
    trades = _read_csv(trades_path)
    if not trades:
        raise ValueError(f"No trades to visualize in {trades_path}")
    signals_by_key = {
        (row["decision_timestamp"], row["side"]): row
        for row in signals
    }
    output.mkdir(parents=True, exist_ok=True)
    selected = _selected_indices(len(trades), min(count, len(trades)))
    files: list[str] = []
    for index in selected:
        trade = trades[index]
        signal = signals_by_key[(trade["decision_timestamp"], trade["side"])]
        path = output / f"trade_{index+1:03d}.svg"
        render_chart(bars, trade, signal, index + 1, path)
        files.append(str(path))

    manifest = {
        "bars": str(bars_path),
        "signals": str(signals_path),
        "ledger": str(trades_path),
        "total_trades": len(trades),
        "selected_trade_numbers": [index + 1 for index in selected],
        "files": files,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    cards = "".join(
        f'<figure><img src="{Path(file).name}" alt="Strategy 04 trade chart"><figcaption>{Path(file).stem.replace("_", " ").title()}</figcaption></figure>'
        for file in files
    )
    (output / "index.html").write_text(
        (
            "<!doctype html><meta charset='utf-8'><title>Strategy 04 trade review</title>"
            "<style>body{margin:24px;background:#0f1117;color:#eef1f6;font:16px sans-serif}"
            "h1{font-size:24px}main{display:grid;gap:24px}figure{margin:0}img{width:100%;height:auto;"
            "border:1px solid #303745}figcaption{margin-top:6px;color:#aeb6c4}</style>"
            "<h1>Strategy 04 v1 · SPY 1h zones / 15m entries</h1><main>"
            + cards
            + "</main>"
        ),
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render Strategy 04 v1 one-hour-zone / 15-minute-entry charts."
    )
    parser.add_argument("--bars", type=Path, required=True)
    parser.add_argument("--signals", type=Path, required=True)
    parser.add_argument("--trades", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--count", type=int, default=10)
    args = parser.parse_args()
    manifest = render_batch(
        args.bars,
        args.signals,
        args.trades,
        args.output,
        args.count,
    )
    print(f"Saved {len(manifest['files'])} Strategy 04 trade charts to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

