"""Build the local interactive visual used to inspect Strategy 01 backtest trades.

This is deliberately separate from the backtest engine: it only reads the saved
fixed-risk trade ledger and its market-data input, then packages the small chart
windows needed for an honest trade-by-trade review.
"""

from __future__ import annotations

import csv
import json
import argparse
from pathlib import Path

from ai_trade.strategy_01 import Strategy01Parameters, alligator_points, load_ohlcv_csv


ROOT = Path(__file__).resolve().parents[1]
VISUAL = Path(r"C:\Users\samip\.codex\visualizations\2026\07\15\019f671e-d752-7f91-a9cb-42065d6fdd28\strategy-01-trade-review.html")


def build_trade_windows(bars_path: Path, ledger_path: Path) -> list[dict[str, object]]:
    bars = load_ohlcv_csv(bars_path)
    alligator = alligator_points(bars, Strategy01Parameters())
    index_by_timestamp = {bar.timestamp: index for index, bar in enumerate(bars)}

    with ledger_path.open(newline="", encoding="utf-8") as handle:
        ledger = list(csv.DictReader(handle))

    windows: list[dict[str, object]] = []
    for number, trade in enumerate(ledger, start=1):
        entry_index = index_by_timestamp[trade["entry_timestamp"]]
        exit_index = index_by_timestamp[trade["exit_timestamp"]]
        start = max(0, entry_index - 12)
        end = min(len(bars), exit_index + 7)
        rows = []
        for index in range(start, end):
            bar, point = bars[index], alligator[index]
            # A Heikin-Ashi high/low uses the raw high/low plus HA open/close.
            rows.append(
                {
                    "t": bar.timestamp,
                    "o": round(point.ha_open, 4),
                    "h": round(max(bar.high, point.ha_open, point.ha_close), 4),
                    "l": round(min(bar.low, point.ha_open, point.ha_close), 4),
                    "c": round(point.ha_close, 4),
                    "jaw": None if point.jaw is None else round(point.jaw, 4),
                    "teeth": None if point.teeth is None else round(point.teeth, 4),
                    "lips": None if point.lips is None else round(point.lips, 4),
                }
            )
        windows.append(
            {
                "id": number,
                "side": trade["side"],
                "entry": trade["entry_timestamp"],
                "exit": trade["exit_timestamp"],
                "stop": float(trade["stop_price"]),
                "target": float(trade["target_price"]),
                "entryPrice": float(trade["entry_price"]),
                "exitPrice": float(trade["exit_price"]),
                "resultR": float(trade["result_r"]),
                "reason": trade["exit_reason"],
                "netPnl": float(trade["net_pnl"]),
                "entryIndex": entry_index - start,
                "exitIndex": exit_index - start,
                "rows": rows,
            }
        )
    return windows


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an interactive local trade-review visual.")
    parser.add_argument("--bars", type=Path, default=ROOT / "data/market_data/ibkr/SPY/spy_15m.csv")
    parser.add_argument("--trades", type=Path, default=ROOT / "outputs/strategy_01_backtest/fixed_trades.csv")
    parser.add_argument("--output", type=Path, default=VISUAL)
    parser.add_argument("--symbol", default="SPY")
    parser.add_argument("--timeframe", default="15-minute")
    parser.add_argument("--review-id", default="strategy-trade-review")
    args = parser.parse_args()
    trades = json.dumps(build_trade_windows(args.bars, args.trades), separators=(",", ":"))
    html = f'''<div class="space-y-4" id="{args.review_id}">
  <div class="flex flex-wrap items-end gap-3">
    <label class="form-label">
      Review a simulated trade
      <select id="trade-selector" class="form-select mt-1 w-full min-w-72"></select>
    </label>
    <div id="trade-summary"></div>
  </div>
  <div class="flex flex-wrap gap-x-4 gap-y-1 text-small text-muted">
    <span><span style="color:var(--viz-series-1)">■</span> bullish Heikin-Ashi</span>
    <span><span style="color:var(--destructive)">■</span> bearish Heikin-Ashi</span>
    <span><span style="color:var(--viz-series-2)">━</span> lips</span>
    <span><span style="color:var(--viz-series-3)">━</span> teeth</span>
    <span><span style="color:var(--viz-series-4)">━</span> jaw</span>
  </div>
  <div class="overflow-x-auto">
    <svg id="trade-chart" viewBox="0 0 1000 500" role="img" aria-label="Heikin-Ashi and Williams Alligator chart for the selected simulated trade" style="display:block;min-width:760px;width:100%;height:auto"></svg>
  </div>
  <p class="text-small text-muted">Each panel uses the fixed 0.15% risk ledger. Entry and exit markers identify backtest bars, not intrabar fill timestamps. RRMS uses the same paths but changes position sizing.</p>
</div>
<script>
(() => {{
  const root = document.getElementById('{args.review_id}');
  if (!root) return;
  const trades = {trades};
  const selector = document.getElementById('trade-selector');
  const summary = document.getElementById('trade-summary');
  const svg = document.getElementById('trade-chart');
  const NS = 'http://www.w3.org/2000/svg';
  const el = (name, attrs = {{}}, text) => {{ const node = document.createElementNS(NS, name); Object.entries(attrs).forEach(([k,v]) => node.setAttribute(k, v)); if (text !== undefined) node.textContent = text; return node; }};
  const utc = value => new Date(value).toLocaleString('en-GB', {{timeZone:'UTC', month:'short', day:'2-digit', hour:'2-digit', minute:'2-digit', hour12:false}}) + ' UTC';
  const fmt = number => Number(number).toFixed(2);
  const reason = value => value.replace('_', ' ');

  trades.forEach(t => {{
    const option = document.createElement('option');
    option.value = t.id - 1;
    option.textContent = `#${{t.id}} · ${{t.side.toUpperCase()}} · ${{reason(t.reason)}} · ${{t.resultR >= 0 ? '+' : ''}}${{t.resultR.toFixed(2)}}R · ${{utc(t.entry)}}`;
    selector.appendChild(option);
  }});

  function pathFor(rows, key, x, y) {{
    let path = ''; let started = false;
    rows.forEach((row, i) => {{
      if (row[key] == null) {{ started = false; return; }}
      path += `${{started ? 'L' : 'M'}}${{x(i).toFixed(1)}},${{y(row[key]).toFixed(1)}} `;
      started = true;
    }});
    return path;
  }}

  function render(index) {{
    const trade = trades[index];
    const rows = trade.rows;
    const W = 1000, H = 500, left = 64, right = 80, top = 42, bottom = 72;
    const pw = W - left - right, ph = H - top - bottom;
    const values = rows.flatMap(r => [r.h, r.l, r.jaw, r.teeth, r.lips]).filter(v => v != null);
    values.push(trade.stop, trade.target, trade.entryPrice, trade.exitPrice);
    const pad = (Math.max(...values) - Math.min(...values)) * .08 || 1;
    const low = Math.min(...values) - pad, high = Math.max(...values) + pad;
    const x = i => left + (i + .5) * pw / rows.length;
    const y = price => top + (high - price) * ph / (high - low);
    const candleWidth = Math.max(2, Math.min(13, pw / rows.length * .6));
    const labelX = W - right + 8;
    svg.replaceChildren();
    svg.appendChild(el('rect', {{x:0, y:0, width:W, height:H, fill:'transparent'}}));
    const colors = {{bull:'var(--viz-series-1)', bear:'var(--destructive)', lips:'var(--viz-series-2)', teeth:'var(--viz-series-3)', jaw:'var(--viz-series-4)', marker:'var(--primary)'}};
    svg.appendChild(el('text', {{x:left, y:22, fill:'var(--foreground)', 'font-size':'16', 'font-weight':'500'}}, `{args.symbol} · {args.timeframe} Heikin-Ashi · Trade #${{trade.id}}`));
    svg.appendChild(el('text', {{x:left, y:38, fill:'var(--muted-foreground)', 'font-size':'12'}}, `entry ${{utc(trade.entry)}}  ·  exit bar ${{utc(trade.exit)}}`));
    for (let i = 0; i <= 5; i++) {{
      const price = low + (high - low) * i / 5;
      const yy = y(price);
      svg.appendChild(el('line', {{x1:left, y1:yy, x2:W-right, y2:yy, stroke:'var(--border)', 'stroke-width':'1'}}));
      svg.appendChild(el('text', {{x:labelX, y:yy+4, fill:'var(--muted-foreground)', 'font-size':'11'}}, fmt(price)));
    }}
    const levels = [
      [trade.target, colors.bull, 'target'],
      [trade.entryPrice, colors.marker, 'entry'],
      [trade.stop, colors.bear, 'stop'],
      [trade.exitPrice, trade.resultR >= 0 ? colors.bull : colors.bear, 'exit']
    ];
    levels.forEach(([price, color, name]) => {{
      const yy = y(price);
      svg.appendChild(el('line', {{x1:left, y1:yy, x2:W-right, y2:yy, stroke:color, 'stroke-width':'1.5', 'stroke-dasharray':'5 4', opacity:'.9'}}));
      svg.appendChild(el('text', {{x:labelX, y:yy-4, fill:color, 'font-size':'11', 'font-weight':'600'}}, `${{name}} ${{fmt(price)}}`));
    }});
    rows.forEach((row, i) => {{
      const xx = x(i), up = row.c >= row.o, color = up ? colors.bull : colors.bear;
      svg.appendChild(el('line', {{x1:xx, y1:y(row.h), x2:xx, y2:y(row.l), stroke:color, 'stroke-width':'1.2'}}));
      const yy = y(Math.max(row.o, row.c)); const height = Math.max(1.5, Math.abs(y(row.o)-y(row.c)));
      svg.appendChild(el('rect', {{x:(xx-candleWidth/2).toFixed(1), y:yy.toFixed(1), width:candleWidth.toFixed(1), height:height.toFixed(1), fill:color, opacity:'.92'}}));
    }});
    [['jaw',colors.jaw], ['teeth',colors.teeth], ['lips',colors.lips]].forEach(([key,color]) => {{ svg.appendChild(el('path', {{d:pathFor(rows,key,x,y), fill:'none', stroke:color, 'stroke-width':'2.2'}})); }});
    [[trade.entryIndex, colors.marker, 'ENTRY'], [trade.exitIndex, trade.resultR >= 0 ? colors.bull : colors.bear, 'EXIT']].forEach(([i,color,name]) => {{
      const xx = x(i);
      svg.appendChild(el('line', {{x1:xx,y1:top,x2:xx,y2:top+ph,stroke:color,'stroke-width':'1.5','stroke-dasharray':'4 4'}}));
      svg.appendChild(el('text', {{x:xx, y:top+14, fill:color, 'font-size':'11', 'font-weight':'700','text-anchor':'middle'}}, name));
    }});
    [0, Math.floor((rows.length-1)/2), rows.length-1].forEach(i => {{
      svg.appendChild(el('text', {{x:x(i), y:H-28, fill:'var(--muted-foreground)', 'font-size':'11', 'text-anchor':'middle'}}, utc(rows[i].t).replace(' UTC','')));
    }});
    summary.replaceChildren();
    const chip = document.createElement('span');
    chip.textContent = `${{trade.side.toUpperCase()}} · ${{reason(trade.reason)}} · ${{trade.resultR >= 0 ? '+' : ''}}${{trade.resultR.toFixed(2)}}R · net $${{trade.netPnl >= 0 ? '+' : ''}}${{trade.netPnl.toFixed(2)}}`;
    chip.style.color = trade.resultR >= 0 ? 'var(--viz-series-1)' : 'var(--destructive)';
    chip.style.fontWeight = '500';
    summary.appendChild(chip);
  }}
  selector.addEventListener('change', () => render(Number(selector.value)));
  render(0);
}})();
</script>'''
    args.output.write_text(html, encoding="utf-8")
    print(f"Wrote {args.output} ({len(html):,} bytes)")


if __name__ == "__main__":
    main()
