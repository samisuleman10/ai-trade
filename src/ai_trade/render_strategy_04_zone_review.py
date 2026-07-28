"""Render deterministic Strategy 04 one-hour zone qualification charts."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ai_trade.strategy_01 import load_ohlcv_csv


UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


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
    if count == 1:
        return [0]
    return sorted({round(i * (total - 1) / (count - 1)) for i in range(count)})


def _bar_close(timestamp: str) -> str:
    value = datetime.strptime(timestamp, UTC_FORMAT).replace(tzinfo=timezone.utc)
    return (value + timedelta(hours=1)).strftime(UTC_FORMAT)


def _render_chart(
    bars,
    close_index: dict[str, int],
    events: list[dict[str, str]],
    qualified: dict[str, str],
    output: Path,
) -> None:
    zone_id = qualified["zone_id"]
    anchor = close_index[qualified["timestamp"]]
    start, end = max(0, anchor - 24), min(len(bars), anchor + 37)
    rows = bars[start:end]
    lower, upper = float(qualified["lower"]), float(qualified["upper"])
    prices = [value for bar in rows for value in (bar.high, bar.low)] + [lower, upper]
    minimum, maximum = min(prices), max(prices)
    pad = max((maximum - minimum) * 0.08, 0.01)
    minimum, maximum = minimum - pad, maximum + pad
    width, height, left, right, top, bottom = 1200, 650, 74, 125, 70, 65
    plot_w, plot_h = width - left - right, height - top - bottom
    xx = lambda index: left + (index + 0.5) * plot_w / max(len(rows), 1)
    yy = lambda value: top + (maximum - value) * plot_h / (maximum - minimum)
    candle_width = max(2.0, min(14.0, plot_w / max(len(rows), 1) * 0.56))
    side = qualified["side"]
    zone_color = "#2db784" if side == "demand" else "#dc5b69"
    pieces = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="650" viewBox="0 0 1200 650">',
        '<style>.title{font:500 19px sans-serif;fill:#f2f2f2}.sub{font:13px sans-serif;fill:#b8b8b8}.tick{font:11px sans-serif;fill:#b8b8b8}.label{font:500 11px sans-serif}.grid{stroke:#353535;stroke-width:1}</style>',
        '<rect width="1200" height="650" fill="#171717"/>',
        f'<text x="{left}" y="27" class="title">Zone #{zone_id} · {_escape(side.upper())} · qualified score {_escape(qualified["score"])}</text>',
        f'<text x="{left}" y="50" class="sub">{_escape(qualified["timestamp"])} · {_escape(qualified["details"])}</text>',
    ]
    for tick in range(6):
        value = minimum + (maximum - minimum) * tick / 5
        py = yy(value)
        pieces.append(
            f'<line x1="{left}" x2="{width-right}" y1="{py:.1f}" y2="{py:.1f}" class="grid"/>'
        )
        pieces.append(
            f'<text x="{left-8}" y="{py+4:.1f}" text-anchor="end" class="tick">{value:.2f}</text>'
        )

    qualification_x = xx(anchor - start)
    pieces.append(
        f'<rect x="{qualification_x:.1f}" y="{yy(upper):.1f}" width="{width-right-qualification_x:.1f}" '
        f'height="{max(yy(lower)-yy(upper),1.5):.1f}" fill="{zone_color}" fill-opacity="0.22" '
        f'stroke="{zone_color}" stroke-width="1.6"/>'
    )

    for index, bar in enumerate(rows):
        px = xx(index)
        color = "#35a77a" if bar.close >= bar.open else "#d76565"
        body_top, body_bottom = yy(max(bar.open, bar.close)), yy(min(bar.open, bar.close))
        pieces.append(
            f'<line x1="{px:.1f}" x2="{px:.1f}" y1="{yy(bar.high):.1f}" y2="{yy(bar.low):.1f}" stroke="{color}"/>'
        )
        pieces.append(
            f'<rect x="{px-candle_width/2:.1f}" y="{body_top:.1f}" width="{candle_width:.1f}" '
            f'height="{max(body_bottom-body_top,1.4):.1f}" fill="{color}"/>'
        )

    pieces.append(
        f'<line x1="{qualification_x:.1f}" x2="{qualification_x:.1f}" y1="{top}" y2="{height-bottom}" '
        'stroke="#f2f2f2" stroke-width="1.4" stroke-dasharray="5 4"/>'
    )
    pieces.append(
        f'<text x="{qualification_x+5:.1f}" y="{top+16}" fill="#f2f2f2" class="label">AVAILABLE / QUALIFIED</text>'
    )

    event_labels = {
        "touch": ("T", "#f4c95d"),
        "rejection": ("R", "#62cf7c"),
        "broken": ("B", "#ff6b6b"),
        "role_flip_retest": ("F", "#a78bfa"),
        "evidence_upgrade": ("U", "#60a5fa"),
    }
    for event in events:
        if event["zone_id"] != zone_id or event["event"] not in event_labels:
            continue
        event_index = close_index.get(event["timestamp"])
        if event_index is None or not start <= event_index < end:
            continue
        label, color = event_labels[event["event"]]
        px = xx(event_index - start)
        price = float(event["lower"]) if event["side"] == "demand" else float(event["upper"])
        py = yy(price)
        pieces.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="5" fill="{color}"/>')
        pieces.append(
            f'<text x="{px:.1f}" y="{py-9:.1f}" text-anchor="middle" fill="{color}" class="label">{label}</text>'
        )

    for index in range(0, len(rows), max(1, len(rows) // 6)):
        pieces.append(
            f'<text x="{xx(index):.1f}" y="{height-bottom+24}" text-anchor="middle" class="tick">'
            f'{_escape(rows[index].timestamp[5:16].replace("T", " "))}</text>'
        )
    pieces.append(
        f'<text x="{width-right+8}" y="{yy(upper)+4:.1f}" fill="{zone_color}" class="label">Upper {upper:.2f}</text>'
    )
    pieces.append(
        f'<text x="{width-right+8}" y="{yy(lower)+4:.1f}" fill="{zone_color}" class="label">Lower {lower:.2f}</text>'
    )
    pieces.append(
        f'<text x="{left}" y="{height-15}" class="sub">T touch · R rejection · B broken · F role flip · U later evidence upgrade</text>'
    )
    pieces.append("</svg>")
    output.write_text("".join(pieces), encoding="utf-8")


def render_review(
    bars_path: Path,
    events_path: Path,
    output: Path,
    count: int = 12,
) -> dict[str, object]:
    bars = load_ohlcv_csv(bars_path)
    close_index = {_bar_close(bar.timestamp): index for index, bar in enumerate(bars)}
    with events_path.open(newline="", encoding="utf-8") as handle:
        events = list(csv.DictReader(handle))
    qualified = [
        event
        for event in events
        if event["event"] == "qualified" and event["timestamp"] in close_index
    ]
    if not qualified:
        raise ValueError("No qualified zones are available to visualize")
    selected = [qualified[index] for index in _selected_indices(len(qualified), count)]
    output.mkdir(parents=True, exist_ok=True)
    files: list[str] = []
    for event in selected:
        path = output / f"zone_{int(event['zone_id']):04d}.svg"
        _render_chart(bars, close_index, events, event, path)
        files.append(str(path))

    cards = "\n".join(
        f'<figure><img src="{Path(path).name}" alt="Strategy 04 zone review chart"><figcaption>{Path(path).stem}</figcaption></figure>'
        for path in files
    )
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Strategy 04 one-hour zone review</title>
<style>body{{font-family:system-ui;background:#111;color:#eee;margin:24px}}main{{display:grid;gap:24px}}figure{{margin:0}}img{{width:100%;height:auto;border:1px solid #333}}figcaption{{color:#aaa;margin-top:6px}}</style>
</head><body><h1>Strategy 04 · SPY one-hour zone review</h1><main>{cards}</main></body></html>"""
    (output / "index.html").write_text(html, encoding="utf-8")
    manifest = {
        "bars": str(bars_path),
        "events": str(events_path),
        "qualified_zone_count": len(qualified),
        "selected_zone_ids": [int(event["zone_id"]) for event in selected],
        "files": files,
        "index": str(output / "index.html"),
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render Strategy 04 one-hour zone qualification charts."
    )
    parser.add_argument("--bars", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--count", type=int, default=12)
    args = parser.parse_args()
    manifest = render_review(args.bars, args.events, args.output, args.count)
    print(f"Saved {len(manifest['files'])} zone charts to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
