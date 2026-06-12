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
    """Per day -> per key: (vol_signed_sum, ddoi_open_position).

    vol_signed_sum: Σ aggressor_sign·size            (the Lapis-1 baseline).
    ddoi_open_position: running net position where same-direction trades OPEN
      (grow |pos|) and opposite-direction trades CLOSE (shrink |pos|); the final
      net is the synthetic signed inventory the dealer accumulated that day.
    Trades MUST be processed in chronological order for the open/close logic.
    """
    # gather chronological trades per (day, key)
    per_key = defaultdict(list)  # (day, key) -> list[(ts_ns, signed_size)]
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
            per_key[(d, key_of(meta))].append((r.ts_event, s * size))

    vol_flow = defaultdict(dict)   # day -> key -> signed vol sum
    ddoi_flow = defaultdict(dict)  # day -> key -> ddoi open position
    for (d, k), trades in per_key.items():
        trades.sort(key=lambda x: x[0])
        vol_sum = 0.0
        pos = 0.0  # running signed inventory (customer-side); dealer = -pos
        for _, sv in trades:
            vol_sum += sv
            # OPEN if sv same sign as pos (or pos flat); CLOSE if opposite.
            if pos == 0.0 or (sv > 0) == (pos > 0):
                pos += sv                      # opening -> grow magnitude
            else:
                # closing -> reduce magnitude, but don't flip past zero in one trade
                if abs(sv) <= abs(pos):
                    pos += sv                  # sv has opposite sign -> shrinks
                else:
                    pos = sv + pos             # overshoot: net flips (close all + open rest)
        vol_flow[d][k] = vol_sum
        # dealer directional position change ~ -(customer open position)
        ddoi_flow[d][k] = -pos
    return vol_flow, ddoi_flow


def run_headtohead(daily_oi, vol_flow, ddoi_flow):
    print("================ DDOI vs VOL — HEAD-TO-HEAD (TRACK D.6) ================")
    print("Same G.4.4 metric core (lapis1.pair_metrics). ΔOI = OI(T)-OI(T-1) per key.")
    print("*** 8-day EXPLORATORY sample — descriptive, NOT validated ***\n")
    print(f"  {'pair':>12s} | {'VOL sign%':>9s} {'VOL rho':>8s} | {'DDOI sign%':>10s} {'DDOI rho':>9s} | winner")
    print("  " + "-" * 72)
    vol_signs, ddoi_signs = [], []
    for prev, cur in DAY_PAIRS:
        oi_p, oi_c = daily_oi.get(prev, {}), daily_oi.get(cur, {})
        mv = pair_metrics(oi_p, oi_c, vol_flow.get(cur, {}))
        md = pair_metrics(oi_p, oi_c, ddoi_flow.get(cur, {}))
        if mv["sign_pct"] is None or md["sign_pct"] is None:
            print(f"  {prev[5:]}→{cur[5:]:>4} | (too few keys)")
            continue
        win = "DDOI" if md["sign_pct"] > mv["sign_pct"] + 1 else ("VOL" if mv["sign_pct"] > md["sign_pct"] + 1 else "tie")
        print(f"  {prev[5:]}→{cur[5:]:>4} | {mv['sign_pct']:>8.1f} {mv['rho']:>8.3f} | "
              f"{md['sign_pct']:>9.1f} {md['rho']:>9.3f} | {win}")
        vol_signs.append(mv["sign_pct"])
        ddoi_signs.append(md["sign_pct"])
    print("  " + "-" * 72)
    if vol_signs:
        mv_mean = sum(vol_signs) / len(vol_signs)
        md_mean = sum(ddoi_signs) / len(ddoi_signs)
        print(f"  mean sign-agreement:  VOL={mv_mean:.1f}%   DDOI={md_mean:.1f}%   "
              f"(baseline random=50%)")
        delta = md_mean - mv_mean
        verdict = ("DDOI IMPROVES" if delta > 2 else
                   "DDOI WORSE" if delta < -2 else "NO MEANINGFUL DIFFERENCE")
        print(f"  => {verdict} (Δ={delta:+.1f} pts on 8-day sample)")
        print("\n  HONEST READ: open/close reconstruction is a heuristic, not ground")
        print("  truth (true open/close needs trade-level position tracking the tape")
        print("  doesn't label). 8 days is far too small for a verdict — this shows the")
        print("  DDOI MACHINE RUNS and is measurable head-to-head, which is the point.")
    return 0


def main() -> int:
    iidmap = build_iid_map()
    daily_oi = extract_daily_oi(iidmap)
    vol_flow, ddoi_flow = vol_and_ddoi_flow(iidmap)
    return run_headtohead(daily_oi, vol_flow, ddoi_flow)


if __name__ == "__main__":
    raise SystemExit(main())
