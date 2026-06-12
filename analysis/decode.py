#!/usr/bin/env python3
"""Decode .dbn.zst archives -> per-DAY, per-instrument CSVs for the case study.

Why isolated single-day files: HistoricalSimAdapter._resolve_file matches CSVs by
INCLUSIVE [START,END] in the filename and returns the FIRST sorted match. The old
CSVs are end-exclusive-named (ES_20260601_20260602.csv holds only Jun-1), so mixing
new data into data/raw would let a Jun-2 lookup match an empty-for-Jun-2 file.
We therefore write data/case_study/raw/<schema>/<INSTR>_<DAY>_<DAY>.csv (single day),
so each session date resolves to exactly one file with no overlap ambiguity.

Columns match what HistoricalSimAdapter consumes (historical.py docstring):
  definition : instrument_id, raw_symbol, instrument_class, strike_price, expiration, underlying
  statistics : ts_event, instrument_id, stat_type, price, quantity
  trades     : ts_event, instrument_id, price, size, side
  bbo-1m     : ts_event, instrument_id, bid_px_00, ask_px_00

Prices are emitted in REAL units (strike/px / 1e9 fixed-point) and timestamps as
ISO-8601 UTC, matching the adapter's pretty decode expectations. Day assignment
de-dupes the old/new file overlap (Jun 9) by preferring the newest pull.
stdlib + databento only (no pandas) to bound memory on the 28M-row bbo file.
"""
from __future__ import annotations

import csv
import glob
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import databento as db

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

NY = ZoneInfo("America/New_York")
OUT_ROOT = Path("data/case_study/raw")
PX_SCALE = 1e9  # Databento fixed-point -> real units
UNDEF = 9223372036854775807  # INT64_MAX sentinel used for undefined px/strike

TRADING_DAYS = ["2026-06-01", "2026-06-02", "2026-06-03", "2026-06-04",
                "2026-06-05", "2026-06-08", "2026-06-09", "2026-06-10"]

# columns to emit per schema
COLS = {
    "definition": ["instrument_id", "raw_symbol", "instrument_class",
                   "strike_price", "expiration", "underlying"],
    "statistics": ["ts_event", "instrument_id", "stat_type", "price", "quantity"],
    "trades": ["ts_event", "instrument_id", "price", "size", "side"],
    "bbo-1m": ["ts_event", "instrument_id", "bid_px_00", "ask_px_00"],
}


def files_for(schema: str) -> list[str]:
    return sorted(glob.glob(f"data/raw/{schema}/{schema}_*.dbn.zst"))


def et_day(ns: int) -> str:
    return datetime.fromtimestamp(ns / 1e9, tz=timezone.utc).astimezone(NY).strftime("%Y-%m-%d")


def iso_utc(ns: int) -> str:
    return datetime.fromtimestamp(ns / 1e9, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def px(v) -> str:
    if v is None or v == UNDEF:
        return ""
    return f"{float(v) / PX_SCALE:.9f}".rstrip("0").rstrip(".")


def assign_days_to_files(schema: str) -> dict[str, str]:
    """day(ET) -> ONE source file; on overlap prefer the file with the latest END."""
    assignment: dict[str, tuple[int, str]] = {}
    for f in files_for(schema):
        m = re.search(r"_(\d{8})_(\d{8})\.dbn", f)
        if not m:
            continue
        start = datetime.strptime(m.group(1), "%Y%m%d").date()
        end = datetime.strptime(m.group(2), "%Y%m%d").date()  # exclusive
        end_key = int(m.group(2))
        d = start
        while d < end:
            ds = d.isoformat()
            if ds not in assignment or end_key > assignment[ds][0]:
                assignment[ds] = (end_key, f)
            d = d + timedelta(days=1)
    return {d: f for d, (_, f) in assignment.items()}


def row_for(schema: str, r) -> list:
    if schema == "definition":
        return [r.instrument_id, getattr(r, "raw_symbol", ""),
                getattr(r, "instrument_class", ""),
                px(getattr(r, "strike_price", None)),
                iso_utc(r.expiration) if isinstance(getattr(r, "expiration", None), int) else "",
                getattr(r, "underlying", "")]
    if schema == "statistics":
        return [iso_utc(r.ts_event), r.instrument_id, int(getattr(r, "stat_type", -1)),
                px(getattr(r, "price", None)), getattr(r, "quantity", "")]
    if schema == "trades":
        return [iso_utc(r.ts_event), r.instrument_id, px(getattr(r, "price", None)),
                getattr(r, "size", ""), getattr(r, "side", "N")]
    if schema == "bbo-1m":
        # MBP1Msg: quotes live in r.levels[0].bid_px/.ask_px (raw int /1e9),
        # NOT a flat bid_px_00 attribute (that only exists in to_csv/to_df output).
        lv = getattr(r, "levels", None)
        bid = ask = None
        if lv:
            bid = getattr(lv[0], "bid_px", None)
            ask = getattr(lv[0], "ask_px", None)
        return [iso_utc(r.ts_event), r.instrument_id, px(bid), px(ask)]
    raise ValueError(schema)


def root_of(iidmap: dict, iid: int) -> str | None:
    return iidmap.get(iid)


def main() -> int:
    schemas = sys.argv[1:] or list(COLS)
    # cumulative iid -> root (ES/NQ) from ALL definitions (defs are not re-published daily)
    print("[decode] building iid->root map from definitions...")
    iid_root: dict[int, str] = {}
    for f in files_for("definition"):
        for r in db.DBNStore.from_file(f):
            und = str(getattr(r, "underlying", ""))
            root = "ES" if und.startswith("ES") else ("NQ" if und.startswith("NQ") else None)
            # futures have empty underlying; map by raw_symbol root instead
            if root is None:
                rs = str(getattr(r, "raw_symbol", ""))
                root = "ES" if rs.startswith("ES") else ("NQ" if rs.startswith("NQ") else None)
            if root:
                iid_root[r.instrument_id] = root
    print(f"[decode] {len(iid_root)} instrument_ids mapped to ES/NQ")

    for schema in schemas:
        day_src = assign_days_to_files(schema)
        # open writers lazily: (root, day) -> csv.writer
        writers: dict[tuple, tuple] = {}
        counts: dict[tuple, int] = defaultdict(int)
        for f in files_for(schema):
            for r in db.DBNStore.from_file(f):
                d = et_day(r.ts_event) if schema != "definition" else None
                if schema != "definition":
                    if d not in TRADING_DAYS or day_src.get(d) != f:
                        continue
                root = iid_root.get(r.instrument_id)
                if root is None:
                    continue
                # definition rows: replicate into every trading day's file so each
                # session can resolve its chain (defs aren't dated per session)
                days = TRADING_DAYS if schema == "definition" else [d]
                for day in days:
                    key = (root, day)
                    if key not in writers:
                        dd = OUT_ROOT / schema
                        dd.mkdir(parents=True, exist_ok=True)
                        stamp = day.replace("-", "")
                        fh = open(dd / f"{root}_{stamp}_{stamp}.csv", "w", newline="", encoding="utf-8")
                        w = csv.writer(fh)
                        w.writerow(COLS[schema])
                        writers[key] = (fh, w)
                    writers[key][1].writerow(row_for(schema, r))
                    counts[key] += 1
        for fh, _ in writers.values():
            fh.close()
        # report per-day totals
        print(f"\n[{schema}] rows per (root, day):")
        for day in TRADING_DAYS:
            es = counts.get(("ES", day), 0)
            nq = counts.get(("NQ", day), 0)
            print(f"    {day}: ES={es:>9,}  NQ={nq:>9,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
