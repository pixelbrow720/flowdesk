#!/usr/bin/env python3
"""Convert raw DBN archives to per-instrument CSV layout for HistoricalSimAdapter.

The adapter expects:
    DATA_DIR/
        definition/<INSTR>_<START>_<END>.csv
        statistics/<INSTR>_<START>_<END>.csv
        trades/<INSTR>_<START>_<END>.csv
        bbo-1m/<INSTR>_<START>_<END>.csv

But our raw data is organized by date with all instruments combined:
    DATA_DIR/
        zerodte/bbo-1m/2026-06-09.dbn.zst
        zerodte/statistics/2026-06-09.dbn.zst
        zerodte/trades/2026-06-09.dbn.zst
        _probe/definition_range_0605_0612.dbn.zst

This script:
1. Loads definition DBN, dedupes by raw_symbol, splits into ES/NQ CSVs.
2. For each date+schema DBN, joins by symbol to definition, writes per-instrument CSV.

Symbol mapping (CME GLBX.MDP3):
    ES options: root starts with 'E' (E1A, E2B, EW1, EW2, ...)
    NQ options: root starts with 'Q' (Q1A, Q2B, QW1, QW2, ...)
    ES futures: symbol starts with 'ES'
    NQ futures: symbol starts with 'NQ'

Usage:
    python scripts/convert_dbn_to_csv.py --date 2026-06-09 --raw-dir data/raw/zerodte --def-db data/raw/_probe/definition_range_0605_0612.dbn.zst --out-dir data/cache
"""
from __future__ import annotations

import argparse
from pathlib import Path

INSTRUMENTS = ("ES", "NQ")


def instrument_from_asset(asset: str) -> str | None:
    """Map definition `asset` column to ES or NQ.

    For futures: asset is literally 'ES' or 'NQ'.
    For options: asset is the weekly root code (E2B, Q2B, EW1, ...).
        Option roots starting with 'E' → ES, 'Q' → NQ.
    """
    a = str(asset).strip().upper()
    if a == "ES":
        return "ES"
    if a == "NQ":
        return "NQ"
    if a.startswith("E"):
        return "ES"
    if a.startswith("Q"):
        return "NQ"
    return None


def instrument_from_symbol(symbol: str) -> str | None:
    """Map a market data symbol to ES or NQ.

    Option symbols: 'E2BM6 C5800' → root 'E2BM6' → starts with E → ES.
    Future symbols: 'ESM6' → starts with ES → ES.
    """
    s = str(symbol).strip().upper()
    root = s.split(" ")[0] if " " in s else s
    # futures
    if root.startswith("ES"):
        return "ES"
    if root.startswith("NQ"):
        return "NQ"
    # option roots
    if root.startswith("E"):
        return "ES"
    if root.startswith("Q"):
        return "NQ"
    return None


def convert_definition(def_path: Path, out_dir: Path, start: str, end: str) -> dict[str, set[str]]:
    """Convert definition DBN → per-instrument CSV. Return {INSTR: set(symbol)}."""
    import databento as db

    store = db.DBNStore.from_file(str(def_path))
    df = store.to_df(pretty_ts=True).reset_index()
    print(f"  definition: {len(df)} rows, deduping by raw_symbol...")

    # Dedupe: keep the latest row per raw_symbol (sorted by ts_event desc)
    df = df.sort_values("ts_event", ascending=False).drop_duplicates(
        subset=["raw_symbol"], keep="first"
    )
    print(f"  definition: {len(df)} unique symbols after dedupe")

    stem_range = f"{start.replace('-', '')}_{end.replace('-', '')}"
    symbol_sets: dict[str, set[str]] = {}

    for instr in INSTRUMENTS:
        mask = df["asset"].astype(str).apply(lambda a: instrument_from_asset(a) == instr)
        sub = df[mask].copy()
        schema_dir = out_dir / "definition"
        schema_dir.mkdir(parents=True, exist_ok=True)
        out = schema_dir / f"{instr}_{stem_range}.csv"
        sub.to_csv(out, index=False)
        print(f"  definition: {instr} → {out}  ({len(sub)} rows)")
        symbol_sets[instr] = set(sub["raw_symbol"].astype(str).unique())

    return symbol_sets


def convert_schema(
    schema: str,
    date: str,
    raw_dir: Path,
    out_dir: Path,
    symbol_sets: dict[str, set[str]],
) -> None:
    """Convert a per-date schema DBN → per-instrument CSVs."""
    import databento as db

    in_path = raw_dir / schema / f"{date}.dbn.zst"
    if not in_path.exists():
        print(f"  {schema}: SKIP (no file {in_path})")
        return

    store = db.DBNStore.from_file(str(in_path))
    df = store.to_df(price_type="float", pretty_ts=True).reset_index()
    print(f"  {schema}: {len(df)} rows")

    # For bbo-1m/statistics/trades, the file is per-date so stem_range = date_date
    stem_range = f"{date.replace('-', '')}_{date.replace('-', '')}"

    for instr in INSTRUMENTS:
        syms = symbol_sets[instr]
        mask = df["symbol"].astype(str).isin(syms)
        sub = df[mask].copy()
        schema_dir = out_dir / schema
        schema_dir.mkdir(parents=True, exist_ok=True)
        out = schema_dir / f"{instr}_{stem_range}.csv"
        sub.to_csv(out, index=False)
        print(f"  {schema}: {instr} → {out}  ({len(sub)} rows)")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Convert DBN archives to per-instrument CSV layout.")
    p.add_argument("--date", required=True, help="session date YYYY-MM-DD")
    p.add_argument("--raw-dir", required=True, help="dir with zerodte/{bbo-1m,statistics,trades}/<date>.dbn.zst")
    p.add_argument("--def-db", required=True, help="path to definition DBN file")
    p.add_argument("--out-dir", required=True, help="output dir for CSV cache")
    args = p.parse_args(argv)

    raw_dir = Path(args.raw_dir)
    def_path = Path(args.def_db)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Converting definition: {def_path}")
    # Extract date range from definition filename: definition_range_0605_0612.dbn.zst
    stem = def_path.stem  # definition_range_0605_0612
    parts = stem.replace("definition_range_", "").split("_")
    if len(parts) == 2 and all(len(x) == 4 and x.isdigit() for x in parts):
        m1, d1 = parts[0][:2], parts[0][2:]
        m2, d2 = parts[1][:2], parts[1][2:]
        # assume 2026
        start = f"2026-{m1}-{d1}"
        end = f"2026-{m2}-{d2}"
    else:
        start = args.date
        end = args.date
    symbol_sets = convert_definition(def_path, out_dir, start, end)

    for schema in ("bbo-1m", "statistics", "trades"):
        print(f"Converting {schema}: {args.date}")
        convert_schema(schema, args.date, raw_dir, out_dir, symbol_sets)

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
