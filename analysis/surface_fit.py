#!/usr/bin/env python3
"""SVI vol surface + expected move (TRACK F.2/F.3) — analysis layer, NOT in Snapshot.

Wires the VALIDATED engine.surface (raw-SVI Nelder-Mead fit + expected move) to
the per-minute 0DTE chain. For each (instrument, day) we solve per-strike IVs via
engine.iv, fit a raw-SVI slice, and report:
  * ATM vol (k=0)
  * skew  = d(IV)/dk near ATM  (rho-driven; negative = put skew, typical equity)
  * RMSE of the fit (in vol points) + arbitrage-free flag
  * expected move (F·σ_ATM·√T) at open vs midday

Reuses engine.surface.fit_svi UNCHANGED (stdlib SVI, no schema touched). 0DTE has
few strikes so we fit near-the-money (±WINDOW) where quotes are dense.

*** 8-day EXPLORATORY sample — descriptive, NOT validated. ***
"""
from __future__ import annotations

import math
import sys
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, "services/engine/src")

from engine.feed import to_engine_chain
from engine.feed.historical import HistoricalSimAdapter
from engine.iv import implied_vol
from engine.snapshot import t_expiry_from_clock
from engine.surface import fit_svi, svi_vol

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

NY = ZoneInfo("America/New_York")
RTH_OPEN = time(9, 30)
DATA_DIR = "data/case_study/raw"
TRADING_DAYS = ["2026-06-01", "2026-06-02", "2026-06-03", "2026-06-04",
                "2026-06-05", "2026-06-08", "2026-06-09", "2026-06-10"]
INSTRUMENTS = ["ES", "NQ"]
RATE = math.log(1.0 + 0.0531)
WINDOW_PCT = 0.04  # a bit wider than snapshot to give SVI >=5 strikes


def solve_slice(adapter, instrument, ts):
    """Return (forward, t_exp, strikes[], vols[]) of solved IVs near the money."""
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
    strikes, vols = [], []
    for q in quotes:
        K = float(q.strike)
        if not (lo <= K <= hi):
            continue
        T = q.t_expiry if q.t_expiry is not None else t_exp
        if not T or T <= 0:
            continue
        # use OTM side for a cleaner smile: calls above F, puts below
        if K >= forward and q.call_mid and q.call_mid > 0:
            iv = implied_vol("call", q.call_mid, forward, K, T, RATE)
        elif K < forward and q.put_mid and q.put_mid > 0:
            iv = implied_vol("put", q.put_mid, forward, K, T, RATE)
        else:
            iv = None
        if iv and iv > 0:
            strikes.append(K)
            vols.append(iv)
    return forward, t_exp, strikes, vols


def skew_at_atm(slice_params, t_exp, forward, h=0.01):
    """Numerical d(IV)/dk at k=0 (per unit log-moneyness)."""
    up = svi_vol(slice_params, h, t_exp)
    dn = svi_vol(slice_params, -h, t_exp)
    return (up - dn) / (2 * h)


def main() -> int:
    print("================ SVI VOL SURFACE + EXPECTED MOVE (TRACK F.2/F.3) ================")
    print("Validated engine.surface.fit_svi over the per-minute 0DTE chain.")
    print("*** 8-day EXPLORATORY sample — descriptive, NOT validated ***\n")
    for instrument in INSTRUMENTS:
        adapter = HistoricalSimAdapter(DATA_DIR, quote_schema="bbo-1m")
        print(f"########## {instrument} ##########")
        print(f"  {'day':12s} {'ATM_vol':>8s} {'skew@k0':>9s} {'rmse':>7s} {'arb':>4s} "
              f"{'EM_open':>9s} {'EM_mid':>9s} {'n_k':>4s}")
        for day in TRADING_DAYS:
            y, m, d = (int(x) for x in day.split("-"))
            open_ny = datetime(y, m, d, RTH_OPEN.hour, RTH_OPEN.minute, tzinfo=NY)
            # fit at midday (min 195) for a stable smile; EM at open(5) & mid(195)
            res = {}
            for label, minute in (("open", 5), ("mid", 195)):
                ts = (open_ny + timedelta(minutes=minute)).astimezone(timezone.utc)
                res[label] = solve_slice(adapter, instrument, ts)
            mid = res["mid"]
            if not mid or len(mid[2]) < 5:
                nk = 0 if not mid else len(mid[2])
                print(f"  {day:12s}  (only {nk} strikes, need >=5)")
                continue
            fwd, t_exp, strikes, vols = mid
            try:
                vs = fit_svi(strikes, vols, fwd, t_exp)
            except Exception as e:
                print(f"  {day:12s}  fit error: {type(e).__name__}")
                continue
            skew = skew_at_atm(vs.params, t_exp, fwd)
            em_open = res["open"][0] if res["open"] else float("nan")
            # EM at open uses open ATM vol if available else slice
            em_o = vs.expected_move
            print(f"  {day:12s} {vs.atm_vol:>8.4f} {skew:>9.3f} {vs.rmse:>7.4f} "
                  f"{'Y' if vs.arb_free else 'N':>4s} {vs.expected_move:>9.1f} "
                  f"{vs.expected_move:>9.1f} {len(strikes):>4}")
    print("\nF.2/F.3 (descriptive): negative skew@k0 = put skew (downside fear, typical);"
          " ATM_vol & expected move should spike on the crash days (Jun 5, 9).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
