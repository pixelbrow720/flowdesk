#!/usr/bin/env python3
"""Phase A planning (READ-ONLY): availability + cost for 90-day def/stat/trades.

NO data pull, NO batch submit. Only metadata calls (cheap, do NOT trigger bans):
  - get_dataset_range  -> latest available date
  - get_cost x3        -> def/stat/trades cost over the 90-trading-day window
Reports the exact request plan so the pull can be approved before any submit.
Key from .env (never printed). Calls spaced with a small delay to be gentle.
"""
from __future__ import annotations

import sys
import time
from datetime import date, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

DATASET = "GLBX.MDP3"
SYMBOLS = ["ES.OPT", "ES.FUT", "NQ.OPT", "NQ.FUT"]
STYPE_IN = "parent"
PHASE_A = ["definition", "statistics", "trades"]
# ~90 trading days ≈ 130 calendar days. Generous start; weekends/holidays empty.
TARGET_TRADING_DAYS = 90
CAL_SPAN = 130


def load_key(p: str = ".env") -> str:
    with open(p, encoding="utf-8") as fh:
        for line in fh:
            s = line.strip()
            if s.startswith("DATABENTO_API_KEY="):
                return s.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("DATABENTO_API_KEY not found in .env")


def main() -> int:
    import databento as db

    key = load_key()
    print(f"key loaded from .env ({len(key)} chars, hidden)")
    client = db.Historical(key)

    # 1) available range (1 metadata call)
    rng = client.metadata.get_dataset_range(dataset=DATASET)
    print(f"dataset range raw: {rng}")
    # rng is a dict with 'start'/'end' (ISO). Parse the end date.
    end_iso = rng["end"] if isinstance(rng, dict) else getattr(rng, "end", None)
    start_iso = rng["start"] if isinstance(rng, dict) else getattr(rng, "start", None)
    print(f"available: {start_iso} .. {end_iso}")

    # latest available calendar day (end is exclusive-ish; use its date)
    end_day = date.fromisoformat(str(end_iso)[:10])
    # pull window end-exclusive = end_day (so last included day = end_day - 1),
    # but if end_day has partial data we still capture full prior days.
    win_end = end_day
    win_start = win_end - timedelta(days=CAL_SPAN)
    start_s, end_s = win_start.isoformat(), win_end.isoformat()
    print(f"\nPROPOSED Phase A window: {start_s} .. {end_s} (end-exclusive, ~{TARGET_TRADING_DAYS} trading days)")
    print(f"symbols={SYMBOLS} stype_in={STYPE_IN}\n")

    print(f"  {'schema':12s} {'cost_usd':>10s} {'records':>14s} {'GB(billable)':>14s}")
    print("  " + "-" * 54)
    total = 0.0
    for sch in PHASE_A:
        kw = dict(dataset=DATASET, symbols=SYMBOLS, schema=sch,
                  start=start_s, end=end_s, stype_in=STYPE_IN)
        try:
            cost = client.metadata.get_cost(**kw)
        except Exception as e:
            cost = None; print(f"  cost err {sch}: {e}")
        try:
            size = client.metadata.get_billable_size(**kw)
        except Exception:
            size = None
        try:
            recs = client.metadata.get_record_count(**kw)
        except Exception:
            recs = None
        cstr = f"${cost:.4f}" if cost is not None else "ERR"
        rstr = f"{recs:,}" if recs is not None else "n/a"
        gstr = f"{size/1e9:.2f}" if size is not None else "n/a"
        print(f"  {sch:12s} {cstr:>10s} {rstr:>14s} {gstr:>14s}")
        if cost is not None:
            total += cost
        time.sleep(1.0)  # gentle spacing between metadata calls
    print("  " + "-" * 54)
    print(f"  {'TOTAL A':12s} ${total:>9.4f}")
    print("\n(READ-ONLY: no data pulled, no batch submitted.)")
    print("Next, if approved: submit 3 batch jobs (1 per schema, full range), "
          "paced, server-side — the rate-limit-safe path.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
