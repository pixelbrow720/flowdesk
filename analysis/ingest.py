#!/usr/bin/env python3
"""Reusable Databento ingest for FlowDesk Track-G (Option B pull).

Anti-block contract (PRD #8 §9 / AC-A7): ONE request per schema over the full
[start, end) window, all symbols at once. With 4 schemas => exactly 4 get_range
calls. Before each pull we call metadata.get_cost() again and print a summary;
if the grand total spikes far above the approved estimate we ABORT before pulling.

Key is read from .env (DATABENTO_API_KEY) and NEVER printed or logged.
Writes raw archives following the existing on-disk convention:
    DATA_DIR/<schema>/<schema>_<START>_<END>.dbn.zst
No per-instrument CSV split here (we read the .dbn.zst directly downstream),
so we never load the multi-GB bbo-1m into a DataFrame.

Usage:
    python analysis/ingest.py --start 2026-06-02 --end 2026-06-11
    python analysis/ingest.py --cost-only           # estimate, no download
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

DATASET = "GLBX.MDP3"
SYMBOLS = ["ES.OPT", "ES.FUT", "NQ.OPT", "NQ.FUT"]
STYPE_IN = "parent"
STYPE_OUT = "instrument_id"
SCHEMAS = ["definition", "statistics", "trades", "bbo-1m"]

APPROVED_ESTIMATE = 48.35
ABORT_IF_TOTAL_OVER = 58.0   # ~20% buffer over approved; spike => stop & report
INTER_REQUEST_DELAY_S = 2.0


def load_key(env_path: str = ".env") -> str:
    """Read DATABENTO_API_KEY from .env. Never print the value."""
    with open(env_path, encoding="utf-8") as fh:
        for line in fh:
            s = line.strip()
            if s.startswith("DATABENTO_API_KEY="):
                return s.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("DATABENTO_API_KEY not found in .env")


def stem(schema: str, start: str, end: str) -> str:
    return f"{schema}_{start.replace('-', '')}_{end.replace('-', '')}"


def cost_summary(client, start: str, end: str):
    """Return (rows, total_cost). Each row: (schema, cost, records, bytes)."""
    rows = []
    total = 0.0
    for sch in SCHEMAS:
        kw = dict(dataset=DATASET, symbols=SYMBOLS, schema=sch,
                  start=start, end=end, stype_in=STYPE_IN)
        try:
            cost = client.metadata.get_cost(**kw)
        except Exception as e:
            cost = None
            print(f"  cost error {sch}: {type(e).__name__}: {e}")
        try:
            recs = client.metadata.get_record_count(**kw)
        except Exception:
            recs = None  # bbo-1m count sometimes 504s; non-fatal
        try:
            size = client.metadata.get_billable_size(**kw)
        except Exception:
            size = None
        rows.append((sch, cost, recs, size))
        if cost is not None:
            total += cost
    return rows, total


def print_cost(rows, total):
    print(f"  {'schema':12s} {'cost_usd':>10s} {'records':>14s} {'bytes':>16s}")
    print("  " + "-" * 56)
    for sch, cost, recs, size in rows:
        cstr = f"${cost:.4f}" if cost is not None else "ERR"
        rstr = f"{recs:,}" if recs is not None else "ERR"
        sstr = f"{size:,}" if size is not None else "ERR"
        print(f"  {sch:12s} {cstr:>10s} {rstr:>14s} {sstr:>16s}")
    print("  " + "-" * 56)
    print(f"  {'TOTAL':12s} ${total:>9.4f}   (approved ~${APPROVED_ESTIMATE})")


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--start", default="2026-06-02")
    p.add_argument("--end", default="2026-06-11")  # end-exclusive
    p.add_argument("--data-dir", default=os.environ.get("DATA_DIR", "data/raw"))
    p.add_argument("--cost-only", action="store_true")
    p.add_argument("--force", action="store_true")
    args = p.parse_args(argv)

    import databento as db

    key = load_key()
    print(f"key loaded from .env ({len(key)} chars, hidden)")
    client = db.Historical(key)

    print(f"\nCost re-check: {DATASET} {args.start}..{args.end} (end-exclusive)")
    rows, total = cost_summary(client, args.start, args.end)
    print_cost(rows, total)

    if total > ABORT_IF_TOTAL_OVER:
        print(f"\nABORT: total ${total:.2f} exceeds ceiling ${ABORT_IF_TOTAL_OVER}. "
              f"Spike vs approved ${APPROVED_ESTIMATE}. Not pulling.")
        return 3
    if args.cost_only:
        print("\n--cost-only: no download.")
        return 0

    data_dir = Path(args.data_dir)
    print(f"\nPulling {len(SCHEMAS)} schema(s) -> {data_dir}")
    written = []
    for i, sch in enumerate(SCHEMAS):
        sdir = data_dir / sch
        sdir.mkdir(parents=True, exist_ok=True)
        raw = sdir / f"{stem(sch, args.start, args.end)}.dbn.zst"
        if raw.exists() and not args.force:
            print(f"  [skip] {raw} exists")
            written.append(raw)
            continue
        print(f"  [{i+1}/{len(SCHEMAS)}] GET {sch} {args.start}..{args.end}")
        t0 = time.time()
        store = client.timeseries.get_range(
            dataset=DATASET, schema=sch, symbols=SYMBOLS,
            stype_in=STYPE_IN, stype_out=STYPE_OUT,
            start=args.start, end=args.end,
        )
        store.to_file(str(raw))
        print(f"      wrote {raw}  ({raw.stat().st_size:,} bytes, {time.time()-t0:.0f}s)")
        written.append(raw)
        if i < len(SCHEMAS) - 1:
            time.sleep(INTER_REQUEST_DELAY_S)
    print(f"\nDone. {len(written)} archive(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
