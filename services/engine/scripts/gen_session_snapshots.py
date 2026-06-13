#!/usr/bin/env python3
"""Generate validated per-minute Snapshot JSON for a real session (offline).

Mirrors the production worker (api/worker.py::_produce_live) but writes the
snapshots to JSON files the frontend can load, instead of Redis/Timescale. No
network: reads the cached Databento CSVs under DATA_DIR via HistoricalSimAdapter.

For each instrument + RTH minute (09:30..16:00 ET = minute_index 0..389) it does
the same pull -> to_engine_chain -> build_snapshot path the worker runs, so the
output is exactly what the live backend would publish for that session.

Usage:
    PYTHONPATH=src python scripts/gen_session_snapshots.py \
        --date 2026-06-01 --data-dir <DATA_DIR> --out <OUT_DIR> [--quote-schema bbo-1m]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
RTH_OPEN = time(9, 30)
RTH_MINUTES = 390  # 09:30..16:00 ET inclusive of open, exclusive of close
STRIKE_STEP = {"ES": 5.0, "NQ": 10.0}
DEFAULT_SOFR = 0.0531


def rate_from_sofr(sofr: float) -> float:
    return math.log(1.0 + float(sofr))


def axis_from_chain(instrument: str, chain) -> dict:
    step = STRIKE_STEP[instrument]
    strikes = list(chain.strikes()) if hasattr(chain, "strikes") else []
    if strikes:
        return {"strike_min": float(min(strikes)), "strike_max": float(max(strikes)), "step": step}
    f = float(getattr(chain, "forward", 0.0))
    return {"strike_min": f, "strike_max": f, "step": step}


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--date", required=True, help="session date YYYY-MM-DD (ET)")
    p.add_argument("--data-dir", required=True)
    p.add_argument("--out", required=True, help="output dir for <INSTR>_<date>.json")
    p.add_argument("--quote-schema", default="bbo-1m")
    p.add_argument("--instruments", nargs="*", default=["ES", "NQ"])
    p.add_argument("--rate", type=float, default=rate_from_sofr(DEFAULT_SOFR))
    p.add_argument(
        "--window-pct", type=float, default=0.03,
        help="keep strikes within +/- this fraction of the forward (PRD #5 zoom ~2-3%%). 0 = no window.",
    )
    args = p.parse_args(argv)

    from engine.feed import to_engine_chain
    from engine.feed.historical import HistoricalSimAdapter
    from engine.hiro import HiroState
    from engine.snapshot import MULTIPLIER, build_snapshot, t_expiry_from_clock

    adapter = HistoricalSimAdapter(args.data_dir, quote_schema=args.quote_schema)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    y, m, d = (int(x) for x in args.date.split("-"))
    session_open_ny = datetime(y, m, d, RTH_OPEN.hour, RTH_OPEN.minute, tzinfo=NY)

    for instrument in args.instruments:
        frames: list[dict] = []
        ok = fail = 0
        # One HIRO accumulator per session, fed each minute's NEW trades only
        # (the adapter returns the chronological [open, ts] window, so the new
        # trades are the suffix past the count already consumed). This keeps the
        # per-minute `hiro` scalar O(1) instead of re-pricing the whole day.
        hiro_state = HiroState(MULTIPLIER[instrument])
        hiro_consumed = 0
        for minute in range(RTH_MINUTES):
            ts = (session_open_ny + timedelta(minutes=minute)).astimezone(timezone.utc)
            try:
                chain = adapter.get_chain(instrument, ts)
                t_expiry = t_expiry_from_clock(ts)
                quotes = to_engine_chain(chain, t_expiry=t_expiry)
                forward = float(getattr(chain, "forward"))
                # Window the strikes to +/- window-pct of the forward so the field
                # is focused on the money (real chains span far-OTM strikes that
                # are mostly empty and bloat the payload / flatten the heatmap).
                if args.window_pct > 0:
                    lo, hi = forward * (1 - args.window_pct), forward * (1 + args.window_pct)
                    quotes = [q for q in quotes if lo <= float(q.strike) <= hi]
                strikes = [float(q.strike) for q in quotes]
                step = STRIKE_STEP[instrument]
                axis = (
                    {"strike_min": min(strikes), "strike_max": max(strikes), "step": step}
                    if strikes
                    else axis_from_chain(instrument, chain)
                )
                ohlc = None
                get_ohlc = getattr(adapter, "get_ohlc", None)
                if get_ohlc is not None:
                    ohlc = get_ohlc(instrument, ts)
                # HIRO: cumulative signed dealer delta-notional since the RTH
                # open (Divergence #5 -> option A; optional snapshot field).
                # Feed only this minute's NEW trades into the running accumulator.
                trades = adapter.get_hiro_trades(instrument, ts)
                for tr in trades[hiro_consumed:]:
                    hiro_state.add(tr, forward, args.rate)
                hiro_consumed = len(trades)
                hiro = hiro_state.snapshot()
                snap = build_snapshot(
                    instrument, ts, quotes, forward, args.rate,
                    "LIVE", axis, t_expiry=t_expiry, stale=False, expired=False,
                    ohlc=ohlc, hiro=hiro, with_exposure_ext=True,
                )
                frames.append(json.loads(snap.model_dump_json()))
                ok += 1
            except Exception as exc:  # noqa: BLE001
                fail += 1
                if fail <= 3:
                    print(f"  {instrument} m={minute}: {type(exc).__name__}: {exc}")
        out = out_dir / f"{instrument}_{args.date}.json"
        out.write_text(json.dumps(frames), encoding="utf-8")
        size_mb = out.stat().st_size / 1e6
        print(f"{instrument}: wrote {ok} frames ({fail} failed) -> {out}  ({size_mb:.1f} MB)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
