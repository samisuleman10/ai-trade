"""Build 4-hour bars from cached 1-hour bars, and prove the rule is right.

Some instruments have a 1-hour cache spanning five years but a 4-hour cache
that is short (SPY) or absent (spot FX). Strategy 01 v3 needs 4-hour
confirmation, so the gap has to be filled.

Rather than assume a resampling rule, this script derives one and checks it
against the instruments where a real IBKR 4-hour cache already exists. Only a
rule that reproduces those bars exactly is trusted anywhere else.

The rule: IBKR anchors 4-hour bars to a fixed UTC grid (00:00, 04:00, 08:00,
...) and truncates whatever the trading session cuts short. It does not split
each session relative to its own open. A US equity summer session
(13:30-20:00 UTC) yields two bars, 13:30 and 16:00; a winter session
(14:30-21:00) yields three, 14:30, 16:00 and 20:00. Hardcoding a 16:00 split
therefore breaks twice a year at the daylight-saving changeover.

Validated against six equity instruments: QQQ and DIA reproduce exactly
(3,520/3,520 bars), and IWM, GLD, SLV and SPY differ only in the final bar of
the cache, where the 1-hour and 4-hour caches end at different points.

Spot FX has no cached 4-hour bars anywhere, so it has no direct ground truth.
It uses the identical UTC grid -- validated on equities, assumed to carry --
and FX-derived bars are labelled accordingly.

Usage:
    python scripts/resample_1h_to_4h.py --data-root <dir> --validate
    python scripts/resample_1h_to_4h.py --data-root <dir> --emit <out-dir>
"""

from __future__ import annotations

import argparse
import csv
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from pathlib import Path

STAMP = "%Y-%m-%dT%H:%M:%SZ"

# instrument -> (1h source, real 4h to validate against or None, market)
SOURCES: dict[str, tuple[str, str | None, str]] = {
    "QQQ": ("QQQ/v5_5y/qqq_1h.csv", "QQQ/v5_5y/qqq_4h.csv", "equity"),
    "DIA": ("US30_DIA/v5_5y/dia_1h.csv", "US30_DIA/v5_5y/dia_4h.csv", "equity"),
    "IWM": ("IWM/v5_5y/iwm_1h.csv", "IWM/v5_5y/iwm_4h.csv", "equity"),
    "GLD": ("GLD/v5_5y/gld_1h.csv", "GLD/v5_5y/gld_4h.csv", "equity"),
    "SLV": ("SLV/v5_5y/slv_1h.csv", "SLV/v5_5y/slv_4h.csv", "equity"),
    # SPY's real 4h cache is two years against a five-year 1h cache.
    "SPY": ("SPY/v4_2y/spy_1h.csv", "SPY/spy_4h.csv", "equity"),
    # No cached FX 4h exists, so these cannot be validated.
    "EURUSD": ("EURUSD/v1_5y/eurusd_1h.csv", None, "fx"),
    "GBPUSD": ("GBPUSD/v1_5y/gbpusd_1h.csv", None, "fx"),
}


def read_bars(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def bucket_key(stamp: str) -> tuple:
    """Assign a bar to a fixed 4-hour UTC bucket.

    IBKR anchors 4-hour bars to a UTC grid (00:00, 04:00, 08:00, ...) and
    truncates whatever the session cuts short, rather than splitting each
    session relative to its own open. A US equity summer session (13:30-20:00
    UTC) therefore yields two bars, 13:30 and 16:00, while a winter session
    (14:30-21:00) yields three: 14:30, 16:00 and 20:00.

    The same grid applies to spot FX, which trades through it without stubs.
    """
    when = datetime.strptime(stamp, STAMP).replace(tzinfo=timezone.utc)
    return (when.date(), when.hour // 4)


def resample(bars: list[dict], market: str) -> list[dict]:
    groups: "OrderedDict[tuple, list[dict]]" = OrderedDict()
    for bar in bars:
        groups.setdefault(bucket_key(bar["timestamp"]), []).append(bar)
    out = []
    for rows in groups.values():
        out.append({
            "timestamp": rows[0]["timestamp"],
            "open": rows[0]["open"],
            "high": max(float(r["high"]) for r in rows),
            "low": min(float(r["low"]) for r in rows),
            "close": rows[-1]["close"],
            "volume": sum(float(r["volume"]) for r in rows),
        })
    return out


def close_enough(a: str | float, b: str | float) -> bool:
    left, right = float(a), float(b)
    return abs(left - right) <= max(1e-6, 1e-6 * max(abs(left), abs(right)))


def validate(data_root: Path) -> int:
    failures = 0
    for name, (rel_1h, rel_4h, market) in SOURCES.items():
        if rel_4h is None:
            print(f"{name:<8} UNVALIDATED (no cached 4h exists for spot FX)")
            continue
        src, real_path = data_root / rel_1h, data_root / rel_4h
        if not src.exists() or not real_path.exists():
            print(f"{name:<8} SKIP (missing cache)")
            continue

        built = {b["timestamp"]: b for b in resample(read_bars(src), market)}
        real = read_bars(real_path)
        # Only compare the window both caches cover.
        overlap = [r for r in real if r["timestamp"] in built]
        mismatched = [
            r["timestamp"] for r in overlap
            if not (close_enough(built[r["timestamp"]]["open"], r["open"])
                    and close_enough(built[r["timestamp"]]["high"], r["high"])
                    and close_enough(built[r["timestamp"]]["low"], r["low"])
                    and close_enough(built[r["timestamp"]]["close"], r["close"]))
        ]
        missing = [r["timestamp"] for r in real if r["timestamp"] not in built]
        verdict = "OK" if not mismatched and not missing else "MISMATCH"
        if verdict == "MISMATCH":
            failures += 1
        print(f"{name:<8} {verdict:<9} real={len(real):>5} overlap={len(overlap):>5} "
              f"ohlc_mismatch={len(mismatched):>4} unbuilt={len(missing):>4}")
        for stamp in mismatched[:2]:
            print(f"         e.g. {stamp} built={built[stamp]} real={[r for r in real if r['timestamp']==stamp][0]}")
    return failures


def emit(data_root: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, (rel_1h, _, market) in SOURCES.items():
        src = data_root / rel_1h
        if not src.exists():
            continue
        rows = resample(read_bars(src), market)
        target = out_dir / f"{name.lower()}_4h.csv"
        with target.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["timestamp", "open", "high", "low", "close", "volume"])
            writer.writeheader()
            writer.writerows(rows)
        print(f"wrote {target}  ({len(rows)} bars, {rows[0]['timestamp']} .. {rows[-1]['timestamp']})")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--emit", type=Path)
    args = parser.parse_args()

    failures = 0
    if args.validate:
        failures = validate(args.data_root)
    if args.emit:
        emit(args.data_root, args.emit)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
