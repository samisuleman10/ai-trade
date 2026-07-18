"""Generate a compact all-trades timeline from saved bars and a trade ledger."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from ai_trade.strategy_01 import load_ohlcv_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an interactive all-trades timeline.")
    parser.add_argument("--bars", required=True, type=Path)
    parser.add_argument("--trades", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--title", default="All simulated trades")
    parser.add_argument("--review-id", default="trade-timeline")
    args = parser.parse_args()

    bars = load_ohlcv_csv(args.bars)
    with args.trades.open(newline="", encoding="utf-8") as handle:
        ledger = list(csv.DictReader(handle))
    prices = json.dumps([[bar.timestamp, round(bar.close, 4)] for bar in bars], separators=(",", ":"))
    trades = json.dumps(
        [
            {
                "id": number,
                "entry": row["entry_timestamp"],
                "exit": row["exit_timestamp"],
                "entryPrice": float(row["entry_price"]),
                "exitPrice": float(row["exit_price"]),
                "r": float(row["result_r"]),
                "pnl": float(row["net_pnl"]),
                "reason": row["exit_reason"].replace("_", " "),
            }
            for number, row in enumerate(ledger, start=1)
        ],
        separators=(",", ":"),
    )
    html = f'''<div id="{args.review_id}" class="space-y-3">
  <div class="viz-controls">
    <label class="form-label">Highlight trade
      <select class="form-select" id="timeline-selector"><option value="all">All 17 trades</option></select>
    </label>
    <span id="timeline-detail" class="text-small text-muted"></span>
  </div>
  <svg id="timeline-chart" viewBox="0 0 1000 470" role="img" aria-label="{args.symbol} price timeline showing all simulated Strategy 01 trades" style="display:block;width:100%;height:auto"></svg>
</div>
<script>
(() => {{
  const root = document.getElementById('{args.review_id}');
  const prices = {prices};
  const trades = {trades};
  const selector = root.querySelector('#timeline-selector');
  const detail = root.querySelector('#timeline-detail');
  const svg = root.querySelector('#timeline-chart');
  const timestampIndex = new Map(prices.map(([t], i) => [t, i]));
  const NS = 'http://www.w3.org/2000/svg';
  const el = (name, attrs = {{}}, label) => {{ const node = document.createElementNS(NS, name); for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value); if (label !== undefined) node.textContent = label; return node; }};
  const money = value => `${{value >= 0 ? '+' : '-'}}$${{Math.abs(value).toFixed(2)}}`;
  const shortDate = value => new Date(value).toLocaleDateString('en-GB', {{timeZone:'UTC', year:'numeric', month:'short', day:'numeric'}});
  trades.forEach(t => {{ const option = document.createElement('option'); option.value = t.id; option.textContent = `#${{t.id}} · ${{shortDate(t.entry)}} · ${{t.r >= 0 ? '+' : ''}}${{t.r.toFixed(2)}}R`; selector.appendChild(option); }});
  function render(selected) {{
    const W=1000,H=470,L=64,R=72,T=42,B=62,pw=W-L-R,ph=H-T-B;
    const min=Math.min(...prices.map(p=>p[1])), max=Math.max(...prices.map(p=>p[1])), pad=(max-min)*.05;
    const x=i=>L+i*pw/(prices.length-1), y=p=>T+(max+pad-p)*ph/(max-min+pad*2);
    svg.replaceChildren();
    svg.appendChild(el('title', {{}}, '{args.title}'));
    svg.appendChild(el('text', {{x:L,y:22,fill:'var(--foreground)','font-size':'16','font-weight':'500'}}, '{args.symbol} · {args.title}'));
    for(let i=0;i<=4;i++){{const p=min+(max-min)*i/4,yy=y(p);svg.appendChild(el('line',{{x1:L,y1:yy,x2:W-R,y2:yy,stroke:'var(--border)','stroke-width':'1'}}));svg.appendChild(el('text',{{x:W-R+8,y:yy+4,fill:'var(--muted-foreground)','font-size':'11'}},p.toFixed(0)));}}
    svg.appendChild(el('path', {{d:prices.map((p,i)=>`${{i?'L':'M'}}${{x(i).toFixed(1)}},${{y(p[1]).toFixed(1)}}`).join(' '), fill:'none',stroke:'var(--muted-foreground)','stroke-width':'1.5'}}));
    const shown = selected === 'all' ? trades : trades.filter(t => String(t.id) === selected);
    shown.forEach(t => {{
      const a=timestampIndex.get(t.entry), b=timestampIndex.get(t.exit); if(a===undefined || b===undefined) return;
      const positive=t.r>=0, color=positive?'var(--viz-series-1)':'var(--destructive)', opacity=selected==='all'?'.8':'1';
      const ya=y(t.entryPrice), yb=y(t.exitPrice), xa=x(a), xb=x(b);
      svg.appendChild(el('line',{{x1:xa,y1:ya,x2:xb,y2:yb,stroke:color,'stroke-width':selected==='all'?'1.5':'3',opacity}}));
      svg.appendChild(el('circle',{{cx:xa,cy:ya,r:selected==='all'?'3':'6',fill:'var(--primary)'}}));
      svg.appendChild(el('path',{{d:`M ${{xb-4}},${{yb-4}} L ${{xb+4}},${{yb+4}} M ${{xb+4}},${{yb-4}} L ${{xb-4}},${{yb+4}}`,stroke:color,'stroke-width':selected==='all'?'1.5':'3'}}));
      if(selected !== 'all'){{svg.appendChild(el('text',{{x:xa,y:ya-10,fill:'var(--foreground)','font-size':'12','text-anchor':'middle'}},`entry $${{t.entryPrice.toFixed(2)}}`));svg.appendChild(el('text',{{x:xb,y:yb-10,fill:'var(--foreground)','font-size':'12','text-anchor':'middle'}},`exit $${{t.exitPrice.toFixed(2)}}`));}}
    }});
    [0, Math.floor(prices.length/2), prices.length-1].forEach(i=>svg.appendChild(el('text',{{x:x(i),y:H-28,fill:'var(--muted-foreground)','font-size':'11','text-anchor':'middle'}},shortDate(prices[i][0]))));
    if(selected === 'all') detail.textContent = '● entry   × exit   green = profitable trade   red = losing trade';
    else {{const t=shown[0];detail.textContent = `#${{t.id}} · ${{t.reason}} · ${{t.r>=0?'+':''}}${{t.r.toFixed(2)}}R · ${{money(t.pnl)}}`;}}
  }}
  selector.addEventListener('change', () => render(selector.value));
  render('all');
}})();
</script>'''
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding="utf-8")
    print(f"Wrote {args.output} ({len(html):,} bytes)")


if __name__ == "__main__":
    main()
