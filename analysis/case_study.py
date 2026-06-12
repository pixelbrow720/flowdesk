#!/usr/bin/env python3
"""Exploratory GEX case study (Jun 1-10) — DESCRIPTIVE, hypothesis-generating.

*** THIS IS NOT LAPIS 2. *** No walk-forward, no FDR verdict, no "validated"
claim. Single correlated 8-day episode => intuition + sanity check only.

Consumes the per-minute Snapshot JSONs produced by gen_session_snapshots.py
(the real engine path: Black-76 -> IV -> exposure -> levels). For each day &
instrument it reports:
  * net-GEX sign trajectory (open / midday / close)
  * gamma-flip location at open vs close, and whether it moved
  * call/put walls (static, from OI gamma-$)
  * price path: open, high, low, close (from snapshot.ohlc / forward)
  * flip vs close relationship; walls vs day range
H2 (wall reaction) gets an INDICATIVE hit-rate with explicit caveats.
H1 (pinning) & H3 (regime-vol) are shown as per-day DESCRIPTIVE observations
only — 8 correlated days cannot support a significance test.

Charts: one price-vs-levels overlay PNG per (instrument, day).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SNAP_DIR = Path("data/case_study/snapshots")
CHART_DIR = Path("analysis/charts")
TRADING_DAYS = ["2026-06-01", "2026-06-02", "2026-06-03", "2026-06-04",
                "2026-06-05", "2026-06-08", "2026-06-09", "2026-06-10"]
INSTRUMENTS = ["ES", "NQ"]
WALL_TOUCH_PCT = 0.0015   # within 0.15% of a wall counts as a "touch" (operational, caveated)


def load_day(instr: str, day: str) -> list[dict]:
    f = SNAP_DIR / f"{instr}_{day}.json"
    if not f.exists():
        return []
    return json.loads(f.read_text(encoding="utf-8"))


def price_path(frames: list[dict]) -> dict:
    """open/high/low/close of the forward across the session."""
    fwd = [fr["forward"] for fr in frames if fr.get("forward")]
    if not fwd:
        return {}
    return {"open": fwd[0], "high": max(fwd), "low": min(fwd),
            "close": fwd[-1], "range_pct": 100.0 * (max(fwd) - min(fwd)) / fwd[0]}


def net_gex_sign_traj(frames: list[dict]) -> tuple:
    """net_gamma sign at open / mid / close."""
    def sign(fr):
        return fr["regime"]["sign"]
    if not frames:
        return (None, None, None)
    mid = len(frames) // 2
    return (sign(frames[0]), sign(frames[mid]), sign(frames[-1]))


def flip_move(frames: list[dict]) -> tuple:
    o = frames[0]["levels"]["gamma_flip"] if frames else None
    c = frames[-1]["levels"]["gamma_flip"] if frames else None
    return (o, c)


def walls(frames: list[dict]) -> tuple:
    """Static walls (OI-based, constant intraday by design). Read from a
    REPRESENTATIVE mid-session frame, NOT frames[-1]: at minute 389 (16:00 ET)
    the 0DTE chain has expired, OI-gamma weights vanish, and walls collapse to
    []. Pick the frame with the most populated walls (earliest on ties)."""
    if not frames:
        return ([], [])
    best = None
    best_n = -1
    for fr in frames:
        lv = fr["levels"]
        n = len(lv.get("call_walls", [])) + len(lv.get("put_walls", []))
        if n > best_n:
            best_n = n
            best = lv
    return (best.get("call_walls", []), best.get("put_walls", [])) if best else ([], [])


def wall_touch_stats(frames: list[dict]) -> dict:
    """H2 INDICATIVE: count wall touches and 'rejections'. HEAVILY CAVEATED —
    intraday events within one correlated day are NOT independent."""
    cw, pw = walls(frames)
    all_walls = list(cw) + list(pw)
    if not all_walls or len(frames) < 10:
        return {"touches": 0, "rejections": 0}
    fwd = [fr["forward"] for fr in frames]
    touches = rejections = 0
    in_touch = False
    for i in range(1, len(fwd) - 1):
        near = any(abs(fwd[i] - w) / w <= WALL_TOUCH_PCT for w in all_walls)
        if near and not in_touch:
            touches += 1
            in_touch = True
            # 'rejection' = price moves away from the nearest wall over next 3 min
            w = min(all_walls, key=lambda x: abs(fwd[i] - x))
            j = min(i + 3, len(fwd) - 1)
            if abs(fwd[j] - w) > abs(fwd[i] - w):
                rejections += 1
        elif not near:
            in_touch = False
    return {"touches": touches, "rejections": rejections}


def chart(instr: str, day: str, frames: list[dict]) -> None:
    if not frames:
        return
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    x = list(range(len(frames)))
    fwd = [fr["forward"] for fr in frames]
    cw, pw = walls(frames)
    flips = [fr["levels"]["gamma_flip"] for fr in frames]
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(x, fwd, color="#111", lw=1.3, label="forward (F)")
    ax.plot(x, [f if f is not None else float("nan") for f in flips],
            color="#888", lw=0.9, ls="--", label="gamma flip")
    for w in cw:
        ax.axhline(w, color="#40E0D0", lw=1.0, alpha=0.7)
    for w in pw:
        ax.axhline(w, color="#E0183C", lw=1.0, alpha=0.7)
    ax.set_title(f"{instr} {day} — price vs levels (turquoise=call walls, crimson=put walls)")
    ax.set_xlabel("RTH minute"); ax.set_ylabel("index points")
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(CHART_DIR / f"{instr}_{day}.png", dpi=90)
    plt.close(fig)


def main() -> int:
    print("================ EXPLORATORY GEX CASE STUDY (DESCRIPTIVE) ================")
    print("NOT Lapis 2. Single correlated episode. Hypothesis-generating only.\n")
    for instr in INSTRUMENTS:
        print(f"\n########## {instr} ##########")
        print(f"  {'day':12s} {'sign(o/m/c)':>12s} {'flip o→c':>16s} "
              f"{'O/H/L/C':>28s} {'rng%':>5s} {'walls(C|P)':>20s} {'H2 touch/rej':>12s}")
        for day in TRADING_DAYS:
            fr = load_day(instr, day)
            if not fr:
                print(f"  {day:12s}  (no snapshots)")
                continue
            so, sm, sc = net_gex_sign_traj(fr)
            fo, fc = flip_move(fr)
            pp = price_path(fr)
            cw, pw = walls(fr)
            h2 = wall_touch_stats(fr)
            flip_s = f"{fo:.0f}→{fc:.0f}" if fo and fc else f"{fo}→{fc}"
            ohlc_s = (f"{pp['open']:.0f}/{pp['high']:.0f}/{pp['low']:.0f}/{pp['close']:.0f}"
                      if pp else "n/a")
            walls_s = f"{[round(w) for w in cw[:2]]}|{[round(w) for w in pw[:2]]}"
            print(f"  {day:12s} {f'{so}/{sm}/{sc}':>12s} {flip_s:>16s} {ohlc_s:>28s} "
                  f"{pp.get('range_pct', 0):>5.1f} {walls_s:>20s} "
                  f"{h2['touches']}/{h2['rejections']:>11}")
            chart(instr, day, fr)
    print(f"\nCharts -> {CHART_DIR}/<instr>_<day>.png")
    print("\nCAVEATS: H2 hit-rate is indicative only (intraday events within one "
          "8-day correlated episode are NOT independent; no random-level baseline "
          "tested here). H1/H3 NOT tested — per-day units, 8 days insufficient.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
