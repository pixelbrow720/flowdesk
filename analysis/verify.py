#!/usr/bin/env python3
"""Post-pull verification for the Jun 1-10 contiguous dataset (read-only, no network).

Checks, per schema:
  * each trading day (Jun 1,2,3,4,5,8,9,10) is readable & non-empty
  * first/last ts_event per day (contiguity evidence)
Plus:
  * instrument_id -> (root, type, strike, expiry) resolution PER DAY from definition
    (instrument_id may be reused across days -> always remap per day)
  * statistics: OPEN_INTEREST (stat_type=9) present per-strike for ES & NQ each day
  * Jun 9 OI duplicate publications: inspect distinguishing fields (ts_recv,
    stat_flags, update_action) and show how to pick the FINAL settlement

Strike encoding: Databento fixed-point 1e-9 -> strike = strike_price / 1e9.
"""
from __future__ import annotations

import glob
from collections import defaultdict
from datetime import datetime, timezone

import databento as db

STAT_OI = 9
TRADING_DAYS = ["2026-06-01", "2026-06-02", "2026-06-03", "2026-06-04",
                "2026-06-05", "2026-06-08", "2026-06-09", "2026-06-10"]
SCHEMAS = ["definition", "statistics", "trades", "bbo-1m"]


def day_of(ns: int) -> str:
    return datetime.fromtimestamp(ns / 1e9, tz=timezone.utc).strftime("%Y-%m-%d")


def hms(ns: int) -> str:
    return datetime.fromtimestamp(ns / 1e9, tz=timezone.utc).strftime("%H:%M:%S")


def files_for(schema: str) -> list[str]:
    return sorted(glob.glob(f"data/raw/{schema}/{schema}_*.dbn.zst"))


def scan_days(schema: str) -> dict[str, tuple[int, int, int]]:
    """day -> (count, first_ns, last_ns) merged across all files for the schema."""
    acc: dict[str, list[int]] = defaultdict(lambda: [0, None, None])
    for f in files_for(schema):
        for r in db.DBNStore.from_file(f):
            t = r.ts_event
            d = day_of(t)
            a = acc[d]
            a[0] += 1
            if a[1] is None or t < a[1]:
                a[1] = t
            if a[2] is None or t > a[2]:
                a[2] = t
    return {d: tuple(v) for d, v in acc.items()}


def build_def_map_per_day() -> dict[str, dict[int, tuple]]:
    """day -> {instrument_id: (root, kind, strike, expiry_ns)} from definition records."""
    per_day: dict[str, dict[int, tuple]] = defaultdict(dict)
    for f in files_for("definition"):
        for r in db.DBNStore.from_file(f):
            d = day_of(r.ts_event)
            ic = getattr(r, "instrument_class", "")
            kind = {"C": "call", "P": "put", "F": "future"}.get(str(ic), str(ic))
            strike = getattr(r, "strike_price", None)
            strike = float(strike) / 1e9 if strike not in (None, 0) else None
            per_day[d][r.instrument_id] = (
                str(getattr(r, "underlying", "")),
                kind,
                strike,
                getattr(r, "expiration", None),
            )
    return per_day


def main() -> int:
    print("================ PER-SCHEMA / PER-DAY CONTIGUITY ================")
    for sch in SCHEMAS:
        print(f"\n--- {sch} ---  files: {[f.split(chr(47))[-1] for f in files_for(sch)]}")
        days = scan_days(sch)
        for d in TRADING_DAYS:
            if d in days:
                cnt, lo, hi = days[d]
                print(f"  {d}: {cnt:>10,} rec   first={hms(lo)}  last={hms(hi)}")
            else:
                print(f"  {d}: *** MISSING / EMPTY ***")
        extra = sorted(set(days) - set(TRADING_DAYS))
        if extra:
            print(f"  (extra non-trading days present: {extra})")

    print("\n================ INSTRUMENT RESOLUTION (per day) ================")
    defmap = build_def_map_per_day()
    for d in TRADING_DAYS:
        m = defmap.get(d, {})
        es = sum(1 for v in m.values() if v[0].startswith("ES") and v[1] in ("call", "put"))
        nq = sum(1 for v in m.values() if v[0].startswith("NQ") and v[1] in ("call", "put"))
        print(f"  {d}: {len(m):>6} defs  ES-opt={es:>5}  NQ-opt={nq:>5}")

    print("\n================ OI (stat_type=9) PER DAY ================")
    oi_rows = defaultdict(list)  # (day) -> list of (iid, qty, ts_recv, flags, action)
    for f in files_for("statistics"):
        for r in db.DBNStore.from_file(f):
            if int(getattr(r, "stat_type", -1)) != STAT_OI:
                continue
            d = day_of(r.ts_event)
            oi_rows[d].append((
                r.instrument_id,
                getattr(r, "quantity", None),
                getattr(r, "ts_recv", None),
                getattr(r, "stat_flags", None),
                getattr(r, "update_action", None),
            ))
    for d in TRADING_DAYS:
        rows = oi_rows.get(d, [])
        per_iid = defaultdict(int)
        for iid, *_ in rows:
            per_iid[iid] += 1
        dup = sum(1 for c in per_iid.values() if c > 1)
        m = defmap.get(d, {})
        es = sum(1 for iid in per_iid if iid in m and m[iid][0].startswith("ES") and m[iid][1] in ("call", "put"))
        nq = sum(1 for iid in per_iid if iid in m and m[iid][0].startswith("NQ") and m[iid][1] in ("call", "put"))
        print(f"  {d}: {len(rows):>6} OI rec  {len(per_iid):>5} iids  dup-iids={dup:>4}  ES-opt={es:>5} NQ-opt={nq:>5}")
        if dup:
            # show one duplicated instrument's distinguishing fields
            for iid, c in per_iid.items():
                if c > 1:
                    samples = [r for r in rows if r[0] == iid][:3]
                    print(f"      dup iid={iid}: " + " | ".join(
                        f"qty={s[1]} ts_recv={s[2]} flags={s[3]} action={s[4]}" for s in samples))
                    break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
