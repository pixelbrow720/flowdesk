#!/usr/bin/env python3
"""Synthetic OI engine — dealer positioning from 4-way trade reconstruction.

This is the REAL synthetic-OI approach (what GEXBot/OptionsDepth/SpotGamma do in
spirit), NOT the failed DDOI proxy. It reconstructs a signed dealer position per
leg from the option accounting identity + aggressor direction, then forms a
"synthetic-OI GEX" to compare structurally against the locked VOL-GEX.

THE ACCOUNTING IDENTITY (derivable, not vendor-proprietary):
  Per leg per day, with O = both-sides-open vol, C = both-sides-close, M = mixed:
      Volume = O + C + M
      ΔOI    = O − C
  Two equations, three unknowns -> UNDERDETERMINED. Vendors close this gap with
  proprietary inventory models. We make the simplest EXPLICIT assumption:
      M = 0  ->  Opens = (V + ΔOI)/2,  Closes = (V − ΔOI)/2
  This is an ASSUMPTION, clearly labeled — not ground truth.

DIRECTION vs MAGNITUDE (the honest circular/non-circular split):
  * direction of the dealer position comes from the AGGRESSOR side (B/A), the
    CME-native customer-direction proxy -> NON-CIRCULAR (independent of ΔOI).
  * magnitude (opening contracts) uses ΔOI -> CIRCULAR w.r.t. a ΔOI test.
  => Therefore we DO NOT test synthetic-OI accuracy against ΔOI (Lapis 1) — that
     would be tautological. We only (a) show its GEX STRUCTURE vs VOL-GEX, and
     (b) measure the NON-CIRCULAR thing: how often flow-direction DISAGREES with
     the static call=+1/put=−1 sign convention (the bias D.5.4 flags). True
     accuracy needs a PRICE test (Lapis 2, ~90 days) — deferred.

Reuses validated engine.black76 (gamma via engine.iv), the locked MULTIPLIER, and
lapis1's ΔOI extraction. Touches ZERO locked schema. 8-day EXPLORATORY.
"""
from __future__ import annotations

import glob
import math
import sys
from collections import defaultdict
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import databento as db

sys.path.insert(0, "services/engine/src")

from engine.black76 import gamma as b76_gamma
from engine.exposure import DEALER_SIGN_CALL, DEALER_SIGN_PUT
from engine.feed import to_engine_chain
from engine.feed.historical import HistoricalSimAdapter
from engine.iv import implied_vol
from engine.snapshot import MULTIPLIER, t_expiry_from_clock

from lapis1 import (  # noqa: E402
    TRADING_DAYS,
    aggressor_sign,
    assign_days_to_files,
    build_iid_map,
    extract_daily_oi,
    key_of,
)

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

NY = ZoneInfo("America/New_York")
RTH_OPEN = time(9, 30)
DATA_DIR = "data/case_study/raw"
INSTRUMENTS = ["ES", "NQ"]
RATE = math.log(1.0 + 0.0531)
GEX_PCT = 0.01
WINDOW_PCT = 0.03


def day_of(ns):
    return datetime.fromtimestamp(ns / 1e9, tz=timezone.utc).strftime("%Y-%m-%d")


def files_for(schema):
    return sorted(glob.glob(f"data/raw/{schema}/{schema}_*.dbn.zst"))


def leg_volume_and_direction(iidmap, instrument):
    """day -> key -> (volume, net_aggressor_dir) for this instrument's legs.

    volume = total traded size; net_aggressor_dir = sign(Σ aggressor·size).
    """
    vol = defaultdict(lambda: defaultdict(float))
    signed = defaultdict(lambda: defaultdict(float))
    day_src = assign_days_to_files("trades")
    for f in files_for("trades"):
        for r in db.DBNStore.from_file(f):
            d = day_of(r.ts_event)
            if d not in set(TRADING_DAYS) or day_src.get(d) != f:
                continue
            meta = iidmap.get(r.instrument_id)
            if meta is None or meta[0] != instrument:
                continue
            s = aggressor_sign(getattr(r, "side", "N"))
            size = float(getattr(r, "size", 0) or 0)
            k = key_of(meta)
            vol[d][k] += size
            signed[d][k] += s * size
    return vol, signed


def gamma_per_leg(adapter, instrument, day):
    """key(strike,type,expiry) -> gamma, from the midday 0DTE chain via IV."""
    y, m, dd = (int(x) for x in day.split("-"))
    ts = (datetime(y, m, dd, 9, 30, tzinfo=NY) + timedelta(minutes=195)).astimezone(timezone.utc)
    try:
        chain = adapter.get_chain(instrument, ts)
    except Exception:
        return {}, None, None
    forward = float(getattr(chain, "forward"))
    t_exp = t_expiry_from_clock(ts)
    quotes = to_engine_chain(chain, t_expiry=t_exp)
    expiry = adapter.get_expiry(instrument, ts)
    exp_iso = day_of(int(expiry.timestamp() * 1e9)) if expiry else None
    out = {}
    lo, hi = forward * (1 - WINDOW_PCT), forward * (1 + WINDOW_PCT)
    for q in quotes:
        K = float(q.strike)
        if not (lo <= K <= hi):
            continue
        T = q.t_expiry if q.t_expiry is not None else t_exp
        if not T or T <= 0:
            continue
        for mid, otype in ((q.call_mid, "call"), (q.put_mid, "put")):
            if mid is None or mid <= 0:
                continue
            iv = implied_vol(otype, mid, forward, K, T, RATE)
            if iv and iv > 0:
                g = b76_gamma(forward, K, T, RATE, iv)
                out[(instrument, otype, K, exp_iso)] = g
    return out, forward, exp_iso


def main():
    print("================ SYNTHETIC-OI GEX vs VOL-GEX (4-way reconstruction) ================")
    print("Opens=(V+ΔOI)/2 [M=0 assumption]; direction from aggressor (non-circular);")
    print("magnitude from |ΔOI| (circular -> NOT accuracy-tested here, only structure).")
    print("*** 8-day EXPLORATORY — engine demo, NOT validated. Accuracy needs Lapis 2. ***\n")

    iidmap = build_iid_map()
    daily_oi = extract_daily_oi(iidmap)
    # day-pairs for ΔOI (need prior day)
    pairs = list(zip(TRADING_DAYS[:-1], TRADING_DAYS[1:]))

    for instrument in INSTRUMENTS:
        M = MULTIPLIER[instrument]
        adapter = HistoricalSimAdapter(DATA_DIR, quote_schema="bbo-1m")
        vol, signed = leg_volume_and_direction(iidmap, instrument)
        print(f"########## {instrument} ##########")
        print(f"  {'day':12s} {'VOLgex sign':>11s} {'SYNgex sign':>11s} "
              f"{'flip agree?':>11s} {'dir≠static%':>11s} {'n_legs':>7s}")
        for prev, cur in pairs:
            gmap, forward, exp_iso = gamma_per_leg(adapter, instrument, cur)
            if not gmap or forward is None:
                print(f"  {cur:12s}  (no chain)")
                continue
            oi_p, oi_c = daily_oi.get(prev, {}), daily_oi.get(cur, {})
            vol_gex = syn_gex = 0.0
            disagree = n = 0
            # per-strike accumulation for flip
            vol_prof, syn_prof = defaultdict(float), defaultdict(float)
            for k, g in gmap.items():
                _, otype, K, _ = k
                V = vol.get(cur, {}).get(k, 0.0)
                dOI = (oi_c.get(k, 0.0) - oi_p.get(k, 0.0)) if (k in oi_c and k in oi_p) else 0.0
                netdir = signed.get(cur, {}).get(k, 0.0)
                # --- VOL-GEX: static dealer sign by option type ---
                static_sign = DEALER_SIGN_CALL if otype == "call" else DEALER_SIGN_PUT
                vol_term = static_sign * g * V * M * forward * forward * GEX_PCT
                vol_gex += vol_term
                vol_prof[K] += vol_term
                # --- SYNTHETIC-OI: dealer position from 4-way reconstruction ---
                opens = max((V + dOI) / 2.0, 0.0)            # M=0 assumption
                cust_dir = 1.0 if netdir > 0 else (-1.0 if netdir < 0 else 0.0)
                dealer_pos = -cust_dir * opens               # dealer = opposite of customer opening
                syn_term = dealer_pos * g * M * forward * forward * GEX_PCT
                syn_gex += syn_term
                syn_prof[K] += syn_term
                # non-circular diagnostic: does flow direction contradict the
                # static dealer sign? Static: dealer long call(+1)/short put(-1).
                # Flow: dealer is short what the customer net-buys. Disagreement =
                # flow-implied dealer position contradicts the static assumption.
                if netdir != 0:
                    n += 1
                    if otype == "call" and cust_dir > 0:
                        disagree += 1   # customer net-buying calls -> dealer SHORT (static says long)
                    elif otype == "put" and cust_dir < 0:
                        disagree += 1   # customer net-selling puts -> dealer LONG (static says short)
            def flip(prof):
                xs = sorted(prof)
                cum = 0.0
                prev_c = None
                for x in xs:
                    cum += prof[x]
                    if prev_c is not None and (prev_c < 0 <= cum or prev_c > 0 >= cum):
                        return x
                    prev_c = cum
                return None
            vf, sf = flip(vol_prof), flip(syn_prof)
            flip_agree = "yes" if (vf is not None and sf is not None and abs(vf - sf) <= (5 if instrument == "ES" else 10)) else "no"
            dis_pct = (100.0 * disagree / n) if n else float("nan")
            print(f"  {cur:12s} {('+' if vol_gex>=0 else '-'):>11s} {('+' if syn_gex>=0 else '-'):>11s} "
                  f"{flip_agree:>11s} {dis_pct:>10.1f}% {n:>7}")
    print("\nREAD: 'dir≠static%' = fraction of legs where reconstructed flow direction")
    print("contradicts the locked static dealer sign — the D.5.4 bias, measured. This is")
    print("the NON-CIRCULAR finding. SYNgex sign/flip differences show the engine produces")
    print("a genuinely different positioning map; whether it's MORE correct needs Lapis 2.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
