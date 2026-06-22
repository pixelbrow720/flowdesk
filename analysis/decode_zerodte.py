#!/usr/bin/env python3
"""Decode the zerodte .dbn.zst archives -> per-day, per-instrument CSV cache.

A path-adapted sibling of ``analysis/decode.py`` tailored to THIS repo's on-disk
layout, which differs from the original case-study layout:

  * bbo-1m / statistics / trades archives live under
    ``data/raw/zerodte/<schema>/<YYYY-MM-DD>.dbn.zst`` (one file per day), NOT
    ``data/raw/<schema>/<schema>_<range>.dbn.zst``.
  * the definition archive is a single range pull under
    ``data/raw/_probe/definition_range_0605_0612.dbn.zst``.

It writes the cache the HistoricalSimAdapter + gen_session_snapshots.py expect:

    <OUT>/definition/<INSTR>_<DAY>_<DAY>.csv
    <OUT>/statistics/<INSTR>_<DAY>_<DAY>.csv
    <OUT>/trades/<INSTR>_<DAY>_<DAY>.csv
    <OUT>/bbo-1m/<INSTR>_<DAY>_<DAY>.csv

so each session date resolves to exactly one file per schema, no overlap.

Columns + units mirror ``analysis/decode.py`` (real units, ISO-8601 UTC). The
iid->root (ES/NQ) map is built once from the definition archive and reused for
the dated schemas. stdlib + databento only (no pandas) to bound memory on the
large bbo file.

Usage (run from repo root, in the .venv that has databento):
    python analysis/decode_zerodte.py            # all schemas, default dates
    python analysis/decode_zerodte.py bbo-1m     # one schema only
"""
from __future__ import annotations

import csv
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import databento as db

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

NY = ZoneInfo("America/New_York")
RAW = Path("data/raw/zerodte")
DEF_ARCHIVE = Path("data/raw/_probe/definition_range_0605_0612.dbn.zst")
OUT_ROOT = Path("data/cache")
PX_SCALE = 1e9
UNDEF = 9223372036854775807

# The 4 sessions present on disk (skip 06-09 — its CSV cache already exists).
TRADING_DAYS = ["2026-06-05", "2026-06-08", "2026-06-10"]

COLS = {
    "definition": ["instrument_id", "raw_symbol", "instrument_class",
                   "strike_price", "expiration", "underlying"],
    "statistics": ["ts_event", "instrument_id", "stat_type", "price", "quantity"],
    "trades": ["ts_event", "instrument_id", "price", "size", "side"],
    "bbo-1m": ["ts_event", "instrument_id", "bid_px_00", "ask_px_00"],
}


def et_day(ns: int) -> str:
    return datetime.fromtimestamp(ns / 1e9, tz=timezone.utc).astimezone(NY).strftime("%Y-%m-%d")


def iso_utc(ns: int) -> str:
    return datetime.fromtimestamp(ns / 1e9, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def px(v) -> str:
    if v is None or v == UNDEF:
        return ""
    return f"{float(v) / PX_SCALE:.9f}".rstrip("0").rstrip(".")


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
        lv = getattr(r, "levels", None)
        bid = ask = None
        if lv:
            bid = getattr(lv[0], "bid_px", None)
            ask = getattr(lv[0], "ask_px", None)
        return [iso_utc(r.ts_event), r.instrument_id, px(bid), px(ask)]
    raise ValueError(schema)


def build_iid_root() -> dict[int, str]:
    """instrument_id -> 'ES'|'NQ' from the definition archive (defs aren't daily)."""
    print(f"[decode] building iid->root map from {DEF_ARCHIVE.name}...")
    iid_root: dict[int, str] = {}
    for r in db.DBNStore.from_file(str(DEF_ARCHIVE)):
        und = str(getattr(r, "underlying", ""))
        root = "ES" if und.startswith("ES") else ("NQ" if und.startswith("NQ") else None)
        if root is None:
            rs = str(getattr(r, "raw_symbol", ""))
            root = "ES" if rs.startswith("ES") else ("NQ" if rs.startswith("NQ") else None)
        if root:
            iid_root[r.instrument_id] = root
    print(f"[decode] {len(iid_root)} instrument_ids mapped to ES/NQ")
    return iid_root


def write_definitions(iid_root: dict[int, str]) -> None:
    """Replicate the full definition set into every trading day's per-instr CSV."""
    schema = "definition"
    writers: dict[tuple, tuple] = {}
    counts: dict[tuple, int] = defaultdict(int)
    for r in db.DBNStore.from_file(str(DEF_ARCHIVE)):
        root = iid_root.get(r.instrument_id)
        if root is None:
            continue
        for day in TRADING_DAYS:
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
    print(f"\n[{schema}] rows per (root, day):")
    for day in TRADING_DAYS:
        print(f"    {day}: ES={counts.get(('ES', day), 0):>9,}  NQ={counts.get(('NQ', day), 0):>9,}")


def write_dated_schema(schema: str, iid_root: dict[int, str]) -> None:
    """Decode one per-day archive into ES/NQ CSVs for that day."""
    writers: dict[tuple, tuple] = {}
    counts: dict[tuple, int] = defaultdict(int)
    for day in TRADING_DAYS:
        src = RAW / schema / f"{day}.dbn.zst"
        if not src.exists():
            print(f"    [skip] {src} missing")
            continue
        for r in db.DBNStore.from_file(str(src)):
            # Only keep rows that fall on this ET session day (archives can spill
            # a few hours into the adjacent UTC day).
            if et_day(r.ts_event) != day:
                continue
            root = iid_root.get(r.instrument_id)
            if root is None:
                continue
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
    print(f"\n[{schema}] rows per (root, day):")
    for day in TRADING_DAYS:
        print(f"    {day}: ES={counts.get(('ES', day), 0):>9,}  NQ={counts.get(('NQ', day), 0):>9,}")


def main() -> int:
    schemas = sys.argv[1:] or list(COLS)
    iid_root = build_iid_root()
    for schema in schemas:
        if schema == "definition":
            write_definitions(iid_root)
        else:
            write_dated_schema(schema, iid_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
