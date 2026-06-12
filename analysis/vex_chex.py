#!/usr/bin/env python3
"""VEX / CHEX exposure profiles (TRACK F.4) — analysis layer, NOT in Snapshot.

VEX  = Σ dealer_sign · vanna · VOL · M     (vol-of-delta exposure)
CHEX = Σ dealer_sign · charm · VOL · M     (time-decay-of-delta exposure)

Reuses the VALIDATED engine core unchanged: engine.black76.vanna/charm (locked
forms, FD-checked), engine.iv.implied_vol, the locked dealer signs (+1 call /
-1 put from engine.exposure) and the VOL basis (cumulative volume since RTH open,
matching GEX/DEX decision #1). Drives engine.feed.HistoricalSimAdapter over the
case-study CSVs, same 0DTE expiry selection as the snapshots. Touches ZERO locked
schema/golden — output stays in this analysis layer (Snapshot integration would
be schema_version+1, a human decision).

F.4 hypothesis (descriptive only): |CHEX| should BUILD toward 16:00 ET as charm
magnitude grows near expiry -> end-of-day pin pressure. We report the open vs
late-session |CHEX| ratio per day as an exploratory observation.

*** 8-day exploratory sample. NOT validated. Single correlated episode. ***
"""
from __future__ import annotations

import sys
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, "services/engine/src")

from engine.black76 import charm as b76_charm
from engine.black76 import vanna as b76_vanna
from engine.exposure import DEALER_SIGN_CALL, DEALER_SIGN_PUT
from engine.feed import to_engine_chain
from engine.feed.historical import HistoricalSimAdapter
from engine.iv import implied_vol
from engine.snapshot import MULTIPLIER, t_expiry_from_clock

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

NY = ZoneInfo("America/New_York")
RTH_OPEN = time(9, 30)
RTH_MINUTES = 390
DATA_DIR = "data/case_study/raw"
TRADING_DAYS = ["2026-06-01", "2026-06-02", "2026-06-03", "2026-06-04",
                "2026-06-05", "2026-06-08", "2026-06-09", "2026-06-10"]
INSTRUMENTS = ["ES", "NQ"]
SOFR = 0.0531
import math
RATE = math.log(1.0 + SOFR)
WINDOW_PCT = 0.03  # focus near the money (same as snapshot gen)


def vex_chex_at(adapter, instrument, ts, M):
    """Return (vex, chex, n_strikes) at one minute, or None if chain unavailable."""
    try:
        chain = adapter.get_chain(instrument, ts)
    except Exception:
        return None
    forward = float(getattr(chain, "forward"))
    if forward <= 0:
        return None
    t_exp = t_expiry_from_clock(ts)
    quotes = to_engine_chain(chain, t_expiry=t_exp)
    lo, hi = forward * (1 - WINDOW_PCT), forward * (1 + WINDOW_PCT)
    vex = chex = 0.0
    n = 0
    for q in quotes:
        K = float(q.strike)
        if not (lo <= K <= hi):
            continue
        T = q.t_expiry if q.t_expiry is not None else t_exp
        if T is None or T <= 0:
            continue
        for mid, vol, sign, otype in (
            (q.call_mid, q.call_vol, DEALER_SIGN_CALL, "call"),
            (q.put_mid, q.put_vol, DEALER_SIGN_PUT, "put"),
        ):
            if mid is None or mid <= 0 or vol <= 0:
                continue
            iv = implied_vol(otype, mid, forward, K, T, RATE)
            if iv is None or iv <= 0:
                continue
            vanna = b76_vanna(forward, K, T, RATE, iv)
            charm = b76_charm(otype, forward, K, T, RATE, iv)
            vex += sign * vanna * vol * M
            chex += sign * charm * vol * M
            n += 1
    return vex, chex, n


def main() -> int:
    print("================ VEX / CHEX EXPOSURE (TRACK F.4) ================")
    print("VEX=Σ sign·vanna·VOL·M  CHEX=Σ sign·charm·VOL·M  (validated black76 core)")
    print("*** 8-day EXPLORATORY sample — descriptive, NOT validated ***\n")
    for instrument in INSTRUMENTS:
        M = MULTIPLIER[instrument]
        adapter = HistoricalSimAdapter(DATA_DIR, quote_schema="bbo-1m")
        print(f"########## {instrument} ##########")
        print(f"  {'day':12s} {'VEX(open)':>14s} {'VEX(close)':>14s} "
              f"{'CHEX(open)':>14s} {'CHEX(late)':>14s} {'|CHEX|late/open':>16s}")
        for day in TRADING_DAYS:
            y, m, d = (int(x) for x in day.split("-"))
            open_ny = datetime(y, m, d, RTH_OPEN.hour, RTH_OPEN.minute, tzinfo=NY)
            samples = {}
            # sample open(min 5), close(min 385), and late(min 360) for the F.4 ratio
            for label, minute in (("open", 5), ("late", 360), ("close", 385)):
                ts = (open_ny + timedelta(minutes=minute)).astimezone(timezone.utc)
                r = vex_chex_at(adapter, instrument, ts, M)
                samples[label] = r
            o, l, c = samples["open"], samples["late"], samples["close"]
            if not o or not c:
                print(f"  {day:12s}  (incomplete)")
                continue
            ratio = (abs(l[1]) / abs(o[1])) if (l and o[1] != 0) else float("nan")
            print(f"  {day:12s} {o[0]:>14.3e} {c[0]:>14.3e} "
                  f"{o[1]:>14.3e} {l[1] if l else float('nan'):>14.3e} {ratio:>16.2f}")
    print("\nF.4 (descriptive): ratio >1 = |CHEX| builds into the close (charm grows "
          "near 0DTE expiry -> potential end-of-day pin). 8-day sample, NOT a test.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
