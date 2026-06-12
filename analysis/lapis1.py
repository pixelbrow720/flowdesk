#!/usr/bin/env python3
"""Lapis 1 — ΔOI reconciliation (Track G.4). Read-only, no network.

Tests whether the DIRECTION of net aggressor option flow (a proxy for dealer
positioning) is consistent with the official daily change in open interest,
ΔOI = OI(T) − OI(T−1), matched per (root, type, strike, expiry) ACROSS DAYS
(never by instrument_id — ids can be reused across days).

Metrics (verified report G.4.3, criteria G.4.4):
  * sign-agreement rate      (random baseline 50%)
  * Spearman rank IC         |net_flow| vs |ΔOI|   (+ p-value)
  * weighted directional error (|ΔOI|-weighted fraction of sign disagreements)
  Verdict per key-pair-set: PASS  if sign≥60% AND Spearman≥0.2 (p<0.05)
                            MARGINAL 55–60% sign
                            FAIL  <55% sign

CRITICAL CAVEAT (open/close ambiguity): a buy-aggressor trade may OPEN or CLOSE a
position, so net aggressor flow is only a PROXY for ΔOI. This ambiguity is exactly
what DDOI (deferred v3) resolves. We therefore report magnitude correlation
(Spearman of |flow| vs |ΔOI|) alongside sign-agreement — under open/close
ambiguity the magnitude relationship is the more robust signal. This is a
CONFIRMATORY proxy test, not proof of the dealer-sign convention.
"""
from __future__ import annotations

import glob
import sys
from collections import defaultdict
from datetime import datetime, timezone

import databento as db
from scipy.stats import spearmanr

# Windows console/file defaults to cp1252, which cannot encode the Δ/Σ/→ symbols
# used in the report headers. Force UTF-8 so the harness is portable.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

TRADING_DAYS = ["2026-06-01", "2026-06-02", "2026-06-03", "2026-06-04",
                "2026-06-05", "2026-06-08", "2026-06-09", "2026-06-10"]
DAY_PAIRS = list(zip(TRADING_DAYS[:-1], TRADING_DAYS[1:]))  # 1→2 ... 9→10
STAT_OI = 9
RTH_OPEN_UTC_H = 13   # 09:30 ET = 13:30 UTC (DST); RTH gate refined in verify step
ROOTS = ("ES", "NQ")


def day_of(ns: int) -> str:
    return datetime.fromtimestamp(ns / 1e9, tz=timezone.utc).strftime("%Y-%m-%d")


def files_for(schema: str) -> list[str]:
    return sorted(glob.glob(f"data/raw/{schema}/{schema}_*.dbn.zst"))


def assign_days_to_files(schema: str) -> dict[str, str]:
    """Map each calendar day -> exactly ONE source file (de-dupe overlap).

    Filenames encode an END-EXCLUSIVE range ``{schema}_{START}_{END}.dbn.zst``
    (START/END = YYYYMMDD). Jun-9 lives in both the old ``..0609_0610`` file and
    the new ``..0602_0611`` pull, so without this a record's day could be counted
    from two files. On overlap we keep the file with the LATEST END (the freshest
    combined pull), so the Jun 8→9→10 chain is served from one contiguous file.
    """
    import re
    assignment: dict[str, tuple[int, str]] = {}  # day -> (end_key, file)
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
            d = date_add(d, 1)
    return {d: f for d, (_, f) in assignment.items()}


def date_add(d, days):
    from datetime import timedelta
    return d + timedelta(days=days)


def aggressor_sign(side: str) -> int:
    s = (side or "").strip().upper()
    return 1 if s == "B" else (-1 if s == "A" else 0)


def build_iid_map() -> dict[int, tuple]:
    """Cumulative {instrument_id: (root, kind, strike, expiry_iso)} across ALL
    definition records.

    Definition records are disseminated on the day an instrument is created/
    changed, NOT re-published every session — so an iid traded on Jun 10 may have
    its definition dated Jun 1. A per-ts_event-day map therefore fails to resolve
    most trades/OI (observed: ES-opt OI = 0 on every day). We build ONE cumulative
    map. ID reuse across the 8-day window should be zero; we DETECT conflicts
    (same iid -> different (root,kind,strike,expiry)) and report rather than
    assume. On conflict we keep the FIRST mapping and count the collision.
    """
    iidmap: dict[int, tuple] = {}
    conflicts = 0
    examples: list[tuple] = []
    for f in files_for("definition"):
        for r in db.DBNStore.from_file(f):
            ic = str(getattr(r, "instrument_class", ""))
            kind = {"C": "call", "P": "put", "F": "future"}.get(ic, ic)
            if kind not in ("call", "put"):
                continue
            strike = getattr(r, "strike_price", None)
            strike = round(float(strike) / 1e9, 4) if strike not in (None, 0) else None
            und = str(getattr(r, "underlying", ""))
            root = "ES" if und.startswith("ES") else ("NQ" if und.startswith("NQ") else und[:2])
            exp = getattr(r, "expiration", None)
            exp_iso = day_of(exp) if isinstance(exp, int) else str(exp)
            meta = (root, kind, strike, exp_iso)
            prev = iidmap.get(r.instrument_id)
            if prev is None:
                iidmap[r.instrument_id] = meta
            elif prev != meta:
                conflicts += 1
                if len(examples) < 3:
                    examples.append((r.instrument_id, prev, meta))
    print(f"[iid-map] {len(iidmap)} option instrument_ids resolved; "
          f"conflicts(reuse)={conflicts}")
    for iid, a, b in examples:
        print(f"          CONFLICT iid={iid}: {a}  vs  {b}")
    return iidmap


def key_of(meta: tuple) -> tuple:
    """Cross-day matching key: (root, kind, strike, expiry) — NOT instrument_id."""
    root, kind, strike, exp = meta
    return (root, kind, strike, exp)


def extract_daily_oi(iidmap: dict[int, tuple]) -> dict[str, dict[tuple, float]]:
    """day -> {key: final_OI}.

    DEDUP (confirmed via verify.py): duplicate OI rows share identical stat_flags
    (0) and update_action (1) — those do NOT distinguish publications. The
    distinguishing field is ts_recv; the FINAL settlement is the LATEST ts_recv
    per (day, iid). Exact-duplicate rows (same ts_recv) seen on Jun 9 come from the
    old/new FILE OVERLAP, removed here by the day->file assignment. So dedup =
    day->file (kills cross-file dupes) + max-ts_recv (picks final settlement).
    """
    # gather all OI records per (day, iid): (ts_recv, qty)
    raw: dict[tuple, list[tuple]] = defaultdict(list)
    day_src = assign_days_to_files("statistics")
    for f in files_for("statistics"):
        for r in db.DBNStore.from_file(f):
            if int(getattr(r, "stat_type", -1)) != STAT_OI:
                continue
            d = day_of(r.ts_event)
            if day_src.get(d) != f:   # de-dupe overlap
                continue
            raw[(d, r.instrument_id)].append(
                (getattr(r, "ts_recv", 0) or 0, float(getattr(r, "quantity", 0) or 0))
            )
    out: dict[str, dict[tuple, float]] = defaultdict(dict)
    for (d, iid), recs in raw.items():
        meta = iidmap.get(iid)
        if meta is None:
            continue
        recs.sort(key=lambda x: x[0])     # by ts_recv ascending
        final_oi = recs[-1][1]            # final settlement = latest ts_recv
        out[d][key_of(meta)] = final_oi   # key collisions within a day: last wins
    return out


def net_aggressor_flow(iidmap: dict[int, tuple]) -> dict[str, dict[tuple, float]]:
    """day -> {key: Σ aggressor_sign * size} over option trades (full session)."""
    flow: dict[str, dict[tuple, float]] = defaultdict(lambda: defaultdict(float))
    day_src = assign_days_to_files("trades")
    for f in files_for("trades"):
        for r in db.DBNStore.from_file(f):
            d = day_of(r.ts_event)
            if day_src.get(d) != f:   # de-dupe overlap (Jun 9 in two files)
                continue
            meta = iidmap.get(r.instrument_id)
            if meta is None:
                continue
            s = aggressor_sign(getattr(r, "side", "N"))
            if s == 0:
                continue
            size = float(getattr(r, "size", 0) or 0)
            flow[d][key_of(meta)] += s * size
    return flow


def pair_metrics(oi_p: dict, oi_c: dict, fl_c: dict) -> dict:
    """Pure metric core for ONE day-pair. Returns the reconciliation metrics so
    both reconcile() and the positive-control harness exercise the SAME code.

    keys = (strike,type,expiry) present in both days' OI and in the flow.
    Drops keys with zero ΔOI or zero flow (no directional information).
    """
    keys = (set(oi_p) & set(oi_c)) & set(fl_c)
    dois, flows = [], []
    agree = 0
    wde_num = wde_den = 0.0
    n = 0
    for k in keys:
        doi = oi_c[k] - oi_p[k]
        fv = fl_c[k]
        if doi == 0 or fv == 0:
            continue
        n += 1
        dois.append(doi)
        flows.append(fv)
        same = (doi > 0) == (fv > 0)
        agree += 1 if same else 0
        wde_den += abs(doi)
        if not same:
            wde_num += abs(doi)
    if n < 5:
        return {"n": n, "sign_pct": None, "rho": None, "p": None,
                "wde": None, "verdict": "n/a (too few keys)"}
    sign_pct = 100.0 * agree / n
    rho, p = spearmanr([abs(x) for x in flows], [abs(x) for x in dois])
    wde = wde_num / wde_den if wde_den else float("nan")
    verdict = ("PASS" if sign_pct >= 60 and rho >= 0.2 and p < 0.05
               else "MARGINAL" if sign_pct >= 55 else "FAIL")
    return {"n": n, "sign_pct": sign_pct, "rho": rho, "p": p,
            "wde": wde, "verdict": verdict}


def reconcile(daily_oi, flow):
    print("================ LAPIS 1 — ΔOI RECONCILIATION ================")
    print("Match key = (root, type, strike, expiry); flow = Σ aggressor_sign·size\n")
    print(f"  {'pair':>14s} {'n_keys':>7s} {'sign%':>7s} {'spearman':>9s} {'p':>9s} {'wDE':>7s}  verdict")
    print("  " + "-" * 70)
    agg_signs = []
    for prev, cur in DAY_PAIRS:
        m = pair_metrics(daily_oi.get(prev, {}), daily_oi.get(cur, {}), flow.get(cur, {}))
        if m["sign_pct"] is None:
            print(f"  {prev[5:]}→{cur[5:]:>5} {m['n']:>7} {'  ' + m['verdict']:>40}")
            continue
        print(f"  {prev[5:]}→{cur[5:]:>5} {m['n']:>7} {m['sign_pct']:>6.1f} "
              f"{m['rho']:>9.3f} {m['p']:>9.3g} {m['wde']:>7.3f}  {m['verdict']}")
        agg_signs.append(m["sign_pct"])
    if agg_signs:
        print("  " + "-" * 70)
        print(f"  mean sign-agreement across pairs: {sum(agg_signs)/len(agg_signs):.1f}%")


def main() -> int:
    iidmap = build_iid_map()
    daily_oi = extract_daily_oi(iidmap)
    flow = net_aggressor_flow(iidmap)
    reconcile(daily_oi, flow)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
