#!/usr/bin/env python3
"""DDOI diagnostics — attribute the +3.3pt edge to mechanism vs artefact.

Predetermined BEFORE seeing results; two of three outcomes KILL the DDOI edge.
This is attribution, not win-hunting. Product decision stays VOL regardless.

D1 BASE-RATE: % of matched keys with ΔOI>0. An always-positive predictor scores
   exactly this. If DDOI's value is positive for most keys (thin keys get weight
   +1 -> always positive) and base-rate ≈ 54%, the "edge" is just base-rate
   matching = NO signal.
D2 THIN-KEY: distribution of trades-per-key; fraction with n=1, n<=2, n<=5. Thin
   keys are immune to shuffle (can't reorder 1 element) -> would explain why the
   shuffle control barely moved.
D3 n>=10 FILTER: DDOI sign-agreement on keys with >=10 trades only. If the edge
   vanishes -> thin-key artefact confirmed.
D4 MULTI-PERM NULL (200x): clean null distribution + real p-value, vs the noisy
   single-shuffle from before.

Reuses lapis1 shipped machinery. Touches ZERO locked schema. 8-day sample.
"""
from __future__ import annotations

import glob
import random
import sys
from collections import defaultdict
from datetime import datetime, timezone

import databento as db

sys.path.insert(0, "services/engine/src")

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


def gather(iidmap):
    """day -> key -> list[abs_size] in chronological order."""
    per_key = defaultdict(list)  # (day,key) -> [(ts, abs_size)]
    day_src = assign_days_to_files("trades")
    for f in files_for("trades"):
        for r in db.DBNStore.from_file(f):
            d = day_of(r.ts_event)
            if d not in set(TRADING_DAYS) or day_src.get(d) != f:
                continue
            meta = iidmap.get(r.instrument_id)
            if meta is None:
                continue
            if aggressor_sign(getattr(r, "side", "N")) == 0:
                continue
            size = float(getattr(r, "size", 0) or 0)
            per_key[(d, key_of(meta))].append((r.ts_event, size))
    out = defaultdict(dict)  # day -> key -> [abs_size time-ordered]
    for (d, k), trades in per_key.items():
        trades.sort(key=lambda x: x[0])
        out[d][k] = [a for _, a in trades]
    return out


def weights(n):
    if n == 1:
        return [1.0]
    return [1.0 - 2.0 * (i / (n - 1)) for i in range(n)]


def ddoi_value(sizes):
    w = weights(len(sizes))
    return sum(wi * s for wi, s in zip(w, sizes))


def mean_sign_pct(daily_oi, flow_by_day):
    vals = []
    for prev, cur in DAY_PAIRS:
        m = pair_metrics(daily_oi.get(prev, {}), daily_oi.get(cur, {}), flow_by_day.get(cur, {}))
        if m["sign_pct"] is not None:
            vals.append(m["sign_pct"])
    return sum(vals) / len(vals) if vals else float("nan")


def main() -> int:
    iidmap = build_iid_map()
    daily_oi = extract_daily_oi(iidmap)
    sizes_by_day = gather(iidmap)

    # real DDOI flow
    ddoi_flow = defaultdict(dict)
    for d, keys in sizes_by_day.items():
        for k, sizes in keys.items():
            ddoi_flow[d][k] = ddoi_value(sizes)

    print("================ DDOI DIAGNOSTICS (attribution) ================\n")

    # ---- D2: trade-count distribution over MATCHED keys ----
    matched_ns = []
    for prev, cur in DAY_PAIRS:
        oi_p, oi_c = daily_oi.get(prev, {}), daily_oi.get(cur, {})
        keys = (set(oi_p) & set(oi_c)) & set(ddoi_flow.get(cur, {}))
        for k in keys:
            doi = oi_c[k] - oi_p[k]
            if doi == 0 or ddoi_flow[cur][k] == 0:
                continue
            n = len(sizes_by_day[cur][k])
            matched_ns.append(n)
    total = len(matched_ns)
    n1 = sum(1 for n in matched_ns if n == 1)
    n2 = sum(1 for n in matched_ns if n <= 2)
    n5 = sum(1 for n in matched_ns if n <= 5)
    print("D2 THIN-KEY distribution (matched keys across all pairs):")
    print(f"   total matched keys = {total}")
    print(f"   n==1 : {n1:>5} ({100*n1/total:.1f}%)   <-- immune to shuffle")
    print(f"   n<=2 : {n2:>5} ({100*n2/total:.1f}%)")
    print(f"   n<=5 : {n5:>5} ({100*n5/total:.1f}%)")

    # ---- D1: base rate + DDOI-positive rate ----
    pos_doi = 0
    pos_ddoi = 0
    for prev, cur in DAY_PAIRS:
        oi_p, oi_c = daily_oi.get(prev, {}), daily_oi.get(cur, {})
        keys = (set(oi_p) & set(oi_c)) & set(ddoi_flow.get(cur, {}))
        for k in keys:
            doi = oi_c[k] - oi_p[k]
            if doi == 0 or ddoi_flow[cur][k] == 0:
                continue
            if doi > 0:
                pos_doi += 1
            if ddoi_flow[cur][k] > 0:
                pos_ddoi += 1
    print("\nD1 BASE-RATE:")
    print(f"   % matched keys with ΔOI>0  = {100*pos_doi/total:.1f}%  "
          f"(score of an ALWAYS-POSITIVE predictor)")
    print(f"   % matched keys with DDOI>0 = {100*pos_ddoi/total:.1f}%  "
          f"(if ~100%, DDOI ≈ always-positive -> edge is just base-rate)")

    # ---- D3: n>=10 filter ----
    ddoi_flow_thick = defaultdict(dict)
    for d, keys in sizes_by_day.items():
        for k, sizes in keys.items():
            if len(sizes) >= 10:
                ddoi_flow_thick[d][k] = ddoi_value(sizes)
    full = mean_sign_pct(daily_oi, ddoi_flow)
    thick = mean_sign_pct(daily_oi, ddoi_flow_thick)
    print("\nD3 n>=10 FILTER (drop thin keys):")
    print(f"   DDOI sign% all keys   = {full:.1f}%")
    print(f"   DDOI sign% n>=10 only = {thick:.1f}%   "
          f"(if ~50%, the edge was a thin-key artefact)")

    # ---- D4: 200-permutation null ----
    rng = random.Random(20260612)
    null_means = []
    for _ in range(200):
        shuf_flow = defaultdict(dict)
        for d, keys in sizes_by_day.items():
            for k, sizes in keys.items():
                s = list(sizes)
                rng.shuffle(s)
                shuf_flow[d][k] = ddoi_value(s)
        null_means.append(mean_sign_pct(daily_oi, shuf_flow))
    null_mean = sum(null_means) / len(null_means)
    null_sd = (sum((x - null_mean) ** 2 for x in null_means) / len(null_means)) ** 0.5
    p = sum(1 for x in null_means if x >= full) / len(null_means)
    print("\nD4 MULTI-PERM NULL (200 shuffles):")
    print(f"   observed DDOI       = {full:.1f}%")
    print(f"   null (shuffled) mean= {null_mean:.1f}%  sd={null_sd:.2f}")
    print(f"   p-value (null>=obs) = {p:.3f}   "
          f"({'NOT significant' if p > 0.05 else 'significant'} at 0.05)")

    print("\n================ READ ================")
    print("If DDOI>0 rate ≈ 100% AND base-rate ≈ observed -> edge = base-rate, NO signal.")
    print("If n>=10 collapses to ~50% -> thin-key artefact.")
    print("If null mean ≈ observed (p>0.05) -> timing structure explains ~nothing.")
    print("Product decision is VOL regardless — this only explains what +3.3 was.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
