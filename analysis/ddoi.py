#!/usr/bin/env python3
"""DDOI — synthetic Dealer Directional OI reconstruction (TRACK D.6) vs VOL baseline.

WHY this exists: Lapis 1 showed raw signed-aggressor-flow sign-agreement with ΔOI
is ~50.8% (random). A deeper reading of the failure: signed aggressor flow and
ΔOI measure DIFFERENT quantities by construction —
  * ΔOI = contracts OUTSTANDING: +1 per opening trade, -1 per closing trade,
    on BOTH sides, INDEPENDENT of aggressor direction.
  * signed aggressor flow = net DIRECTION of pressure, says nothing about
    open vs close.
So ~50% sign-agreement is almost expected, not a bug. DDOI's job is to recover a
signed dealer-inventory change by classifying each trade as OPEN or CLOSE.

OPEN/CLOSE CLASSIFIER (non-circular — never peeks at ΔOI):
  Maintain a running signed net position per (strike,type). A trade in the SAME
  direction as the running position (or from flat) is treated as OPENING (grows
  |position|); a trade AGAINST the running position is CLOSING (shrinks it). This
  is the standard momentum/reversal inventory heuristic. Round-trips cancel, so
  the resulting |net opening position| is the synthetic ΔOI contribution; its
  magnitude is what should align with official |ΔOI| if the model captures
  open/close. We then compare BOTH estimators to ΔOI on identical G.4.4 metrics.

Reuses lapis1.pair_metrics (shipped, positive-control-passed) for the head-to-head.
Touches ZERO locked schema/golden. 8-day EXPLORATORY sample — NOT validated.
"""
from __future__ import annotations

import glob
import random
import sys
from collections import defaultdict
from datetime import datetime, timezone

import databento as db

sys.path.insert(0, "services/engine/src")

# reuse the SHIPPED, positive-control-passed metric core + helpers from lapis1
from lapis1 import (  # noqa: E402
    DAY_PAIRS,
    TRADING_DAYS,
    aggressor_sign,
    assign_days_to_files,
    build_iid_map,
    extract_daily_oi,
    key_of,
    pair_metrics,
)

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def day_of(ns: int) -> str:
    return datetime.fromtimestamp(ns / 1e9, tz=timezone.utc).strftime("%Y-%m-%d")


def files_for(schema: str) -> list[str]:
    return sorted(glob.glob(f"data/raw/{schema}/{schema}_*.dbn.zst"))


def vol_and_ddoi_flow(iidmap):
    """Per day -> per key: (vol_signed_sum, ddoi_synthetic_doi).

    Two estimators on DIFFERENT axes (this is the whole point):

    vol_signed_sum = Σ aggressor_sign·size  -> DIRECTION axis (net long/short
      pressure). This is the Lapis-1 baseline. NOTE: net signed position is the
      mathematical identity Σ sv, so any net-position reconstruction collapses to
      ±VOL — that was the bug in the prior version. Direction is the WRONG axis to
      match ΔOI, which is open/close, not long/short (hence Lapis-1's ~50%).

    ddoi_synthetic_doi = Σ w(i)·|size|  -> OPEN/CLOSE axis (outstanding up/down),
      DIRECTION-AGNOSTIC (uses |size|, ignores aggressor sign). w(i) is an intraday
      time weight, +1 for the FIRST trade of the day on that key linearly down to
      -1 for the LAST: early trades are treated as OPENING (build OI), late trades
      as CLOSING (square up before the 0DTE close). Net > 0 = synthetic OI rose,
      < 0 = fell. This is orthogonal to Σ(sign·size) so it CANNOT telescope back to
      VOL, and it is non-circular (never reads ΔOI). Rationale: 0DTE positions are
      opened intraday and must close/expire by 16:00 ET, so opening volume skews
      early and closing volume skews late.
    Trades MUST be processed in chronological order for the time weight.
    """
    # gather chronological trades per (day, key)
    per_key = defaultdict(list)  # (day, key) -> list[(ts_ns, signed_size, abs_size)]
    day_src = assign_days_to_files("trades")
    for f in files_for("trades"):
        for r in db.DBNStore.from_file(f):
            d = day_of(r.ts_event)
            if d not in set(TRADING_DAYS) or day_src.get(d) != f:
                continue
            meta = iidmap.get(r.instrument_id)
            if meta is None:
                continue
            s = aggressor_sign(getattr(r, "side", "N"))
            if s == 0:
                continue
            size = float(getattr(r, "size", 0) or 0)
            per_key[(d, key_of(meta))].append((r.ts_event, s * size, size))

    vol_flow = defaultdict(dict)    # day -> key -> signed vol sum (DIRECTION axis)
    ddoi_flow = defaultdict(dict)   # day -> key -> synthetic ΔOI (OPEN/CLOSE axis)
    shuf_flow = defaultdict(dict)   # day -> key -> SHUFFLE CONTROL (time-order randomized)
    rng = random.Random(20260612)   # fixed seed -> reproducible shuffle control
    for (d, k), trades in per_key.items():
        trades.sort(key=lambda x: x[0])
        n = len(trades)
        vol_sum = 0.0
        syn_doi = 0.0
        for i, (_, sv, asize) in enumerate(trades):
            vol_sum += sv
            # intraday time weight: +1 (first trade) -> -1 (last trade)
            w = 1.0 if n == 1 else 1.0 - 2.0 * (i / (n - 1))
            syn_doi += w * asize
        # SHUFFLE CONTROL: same |sizes|, same weights, but trade time-order randomized.
        # If DDOI's edge comes from the timing structure (early=open, late=close),
        # destroying time-order must collapse it back to ~50%. If it survives, the
        # edge is NOT from timing -> the result would be suspect.
        sizes = [asize for _, _, asize in trades]
        rng.shuffle(sizes)
        syn_shuf = 0.0
        for i, asize in enumerate(sizes):
            w = 1.0 if n == 1 else 1.0 - 2.0 * (i / (n - 1))
            syn_shuf += w * asize
        vol_flow[d][k] = vol_sum
        ddoi_flow[d][k] = syn_doi
        shuf_flow[d][k] = syn_shuf
    return vol_flow, ddoi_flow, shuf_flow


def run_headtohead(daily_oi, vol_flow, ddoi_flow, shuf_flow):
    print("================ DDOI vs VOL — HEAD-TO-HEAD (TRACK D.6) ================")
    print("Same G.4.4 metric core (lapis1.pair_metrics). ΔOI = OI(T)-OI(T-1) per key.")
    print("SHUF = DDOI with intraday trade time-order randomized (falsification control).")
    print("*** 8-day EXPLORATORY sample — descriptive, NOT validated ***\n")
    print(f"  {'pair':>12s} | {'VOL%':>6s} | {'DDOI%':>6s} {'DDOI rho':>9s} | {'SHUF%':>6s} | winner")
    print("  " + "-" * 64)
    vol_signs, ddoi_signs, shuf_signs = [], [], []
    for prev, cur in DAY_PAIRS:
        oi_p, oi_c = daily_oi.get(prev, {}), daily_oi.get(cur, {})
        mv = pair_metrics(oi_p, oi_c, vol_flow.get(cur, {}))
        md = pair_metrics(oi_p, oi_c, ddoi_flow.get(cur, {}))
        ms = pair_metrics(oi_p, oi_c, shuf_flow.get(cur, {}))
        if mv["sign_pct"] is None or md["sign_pct"] is None:
            print(f"  {prev[5:]}→{cur[5:]:>4} | (too few keys)")
            continue
        win = "DDOI" if md["sign_pct"] > mv["sign_pct"] + 1 else ("VOL" if mv["sign_pct"] > md["sign_pct"] + 1 else "tie")
        sp = f"{ms['sign_pct']:>6.1f}" if ms["sign_pct"] is not None else "   n/a"
        print(f"  {prev[5:]}→{cur[5:]:>4} | {mv['sign_pct']:>6.1f} | "
              f"{md['sign_pct']:>6.1f} {md['rho']:>9.3f} | {sp} | {win}")
        vol_signs.append(mv["sign_pct"])
        ddoi_signs.append(md["sign_pct"])
        if ms["sign_pct"] is not None:
            shuf_signs.append(ms["sign_pct"])
    print("  " + "-" * 64)
    if vol_signs:
        mv_mean = sum(vol_signs) / len(vol_signs)
        md_mean = sum(ddoi_signs) / len(ddoi_signs)
        ms_mean = sum(shuf_signs) / len(shuf_signs) if shuf_signs else float("nan")
        print(f"  mean sign-agreement:  VOL={mv_mean:.1f}%   DDOI={md_mean:.1f}%   "
              f"SHUF={ms_mean:.1f}%   (baseline random=50%)")
        delta = md_mean - mv_mean
        verdict = ("DDOI IMPROVES" if delta > 2 else
                   "DDOI WORSE" if delta < -2 else "NO MEANINGFUL DIFFERENCE")
        print(f"  => {verdict} (Δ={delta:+.1f} pts vs VOL on 8-day sample)")
        # falsification read: real timing edge should COLLAPSE under shuffle
        shuf_drop = md_mean - ms_mean
        if shuf_signs:
            if ms_mean <= 51.0 and shuf_drop > 2.0:
                print(f"  SHUFFLE CONTROL PASSED: DDOI edge collapses to {ms_mean:.1f}% when "
                      f"time-order is destroyed (-{shuf_drop:.1f} pts).")
                print(f"  => the edge IS in the intraday timing structure (early=open, late=close),")
                print(f"     not an artefact. Still 8 days — directional, not a verdict.")
            else:
                print(f"  SHUFFLE CONTROL INCONCLUSIVE/FAILED: shuffled DDOI = {ms_mean:.1f}% "
                      f"(drop {shuf_drop:+.1f}). If it did not collapse, the DDOI edge is NOT")
                print(f"     clearly from timing -> treat the +{delta:.1f} as suspect, not a win.")
        print("\n  HONEST READ: open/close split here is a TIME-WEIGHT HEURISTIC (early volume")
        print("  treated as opening, late as closing), not ground truth — the tape does not")
        print("  label open vs close. The cross-day matched keys skew NON-0DTE (0DTE expires")
        print("  and vanishes), so the 0DTE rationale is imperfect for this population.")
        print("  8 days is far too small for a verdict. This is a directional signal + a")
        print("  working, falsifiable DDOI machine — NOT validation.")
    return 0


def main() -> int:
    iidmap = build_iid_map()
    daily_oi = extract_daily_oi(iidmap)
    vol_flow, ddoi_flow, shuf_flow = vol_and_ddoi_flow(iidmap)
    return run_headtohead(daily_oi, vol_flow, ddoi_flow, shuf_flow)


if __name__ == "__main__":
    raise SystemExit(main())
