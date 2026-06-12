#!/usr/bin/env python3
"""Positive control for the Lapis 1 reconciliation metric (harness v1).

PURPOSE: prove the SHIPPED metric core (lapis1.pair_metrics) can DETECT a true
ΔOI↔flow relationship when one exists. Without this, a FAIL on real data is
ambiguous — it could mean "no signal" OR "broken/dead metric". By feeding
synthetic data with a KNOWN, injected signal through the exact same code path,
we certify the metric discriminates. Three tiers bracket the behaviour:

  PERFECT : flow == ΔOI            -> expect sign≈100%, rho≈1.0, verdict PASS
  STRONG  : 85% sign-aligned + mag -> expect sign≈85%,  rho high, verdict PASS
  NULL    : independent random     -> expect sign≈50%,  rho≈0,   verdict FAIL

If PERFECT/STRONG PASS and NULL FAILs, the metric is sound and the real-data
result (~50.8% sign, = NULL bracket) is a genuine finding about the VOL/static-
sign methodology — NOT a harness artefact. Deterministic (seeded).
"""
from __future__ import annotations

import random
import sys

from lapis1 import pair_metrics  # exercise the SHIPPED metric core

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

N_KEYS = 400  # mirror real per-pair key counts (394–619)


def synth(sign_align_prob: float, mag_corr: float, seed: int):
    """Build (oi_prev, oi_cur, flow) dicts with an injected ΔOI↔flow relationship.

    sign_align_prob: P(flow sign == ΔOI sign).
    mag_corr: weight of |ΔOI| in |flow| (1.0 = magnitude tracks ΔOI; 0.0 = noise).
    """
    rng = random.Random(seed)
    oi_p, oi_c, flow = {}, {}, {}
    for i in range(N_KEYS):
        k = ("ES", "call", 5000.0 + 5 * i, "2026-06-18")
        base = rng.uniform(100, 5000)
        doi = rng.gauss(0.0, 500.0)
        if abs(doi) < 1.0:
            doi = 1.0  # avoid exact-zero drop
        oi_p[k] = base
        oi_c[k] = base + doi
        aligned = rng.random() < sign_align_prob
        fsign = (1 if doi > 0 else -1) * (1 if aligned else -1)
        mag = abs(doi) * mag_corr + rng.uniform(0.0, 1000.0) * (1.0 - mag_corr)
        flow[k] = fsign * (mag if mag != 0 else 1.0)
    return oi_p, oi_c, flow


def main() -> int:
    print("================ LAPIS 1 — POSITIVE CONTROL (harness v1) ================")
    print("Synthetic data with KNOWN injected signal through the shipped pair_metrics().\n")
    print(f"  {'tier':>8s} {'n':>5s} {'sign%':>7s} {'spearman':>9s} {'p':>9s} {'verdict':>9s}  {'expect':>8s}")
    print("  " + "-" * 64)

    cases = [
        ("PERFECT", 1.00, 1.00, "PASS"),
        ("STRONG", 0.85, 0.80, "PASS"),
        ("NULL", 0.50, 0.00, "FAIL"),
    ]
    ok = True
    results = {}
    for name, sp, mc, expect in cases:
        oi_p, oi_c, flow = synth(sp, mc, seed=hash(name) & 0xFFFF)
        m = pair_metrics(oi_p, oi_c, flow)
        results[name] = m
        got = m["verdict"]
        flag = "OK" if got == expect else "*** MISMATCH ***"
        if got != expect:
            ok = False
        print(f"  {name:>8s} {m['n']:>5} {m['sign_pct']:>6.1f} {m['rho']:>9.3f} "
              f"{m['p']:>9.3g} {got:>9s}  {expect:>8s} {flag}")

    print("  " + "-" * 64)
    if ok:
        print("\nPOSITIVE CONTROL PASSED: the metric detects injected signal (PERFECT/STRONG"
              " -> PASS) and rejects noise (NULL -> FAIL).")
        print("=> Real-data FAIL (~50.8% sign) sits in the NULL bracket and is a GENUINE"
              " finding about the VOL + static-sign methodology, not a dead/buggy metric.")
    else:
        print("\n*** POSITIVE CONTROL FAILED *** — metric did not behave as expected on"
              " synthetic signal. Do NOT trust the real-data verdict until resolved.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
