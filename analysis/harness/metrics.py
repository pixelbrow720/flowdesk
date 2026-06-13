"""Validation-harness metrics — PURE core (stdlib + scipy only, NO databento, NO disk).

This module is the *provable* half of the FlowDesk validation harness (docs gap #1):
small, deterministic, unit-tested functions that take already-extracted per-session
data and return metric dicts. The data-loading half (dbn streaming) lives in
``run_validation.py`` and is intentionally kept out of here so these metrics can be
tested without market data.

HONEST SCOPE — read before trusting any number this produces
============================================================
1. **Sample size.** FlowDesk has 4 correctly-structured 0DTE sessions
   (Jun 5/8/9/10 2026), one of them a crash day. Every metric here is therefore
   **mechanism, not evidence**: it tells you the harness *computes a defined
   descriptor*, NOT that the signal predicts anything. Real validation is the
   operator's ~90-day forward test; these functions are what that test will call.

2. **ΔOI reconciliation is MAGNITUDE-ONLY on 0DTE, and CONFOUNDED BY VOLUME.**
   Lapis-1 (the quarterly-data harness) matched contracts across consecutive days
   and used the *sign* of ``ΔOI = OI(T) − OI(T−1)``. 0DTE contracts are listed and
   expire the SAME session, so they start at OI=0 and ``ΔOI_session ≡ OI_settle ≥ 0``
   — the sign is constant, so a sign-agreement test carries ZERO information here.
   Only the **magnitude** relationship is testable. EVEN THAT is confounded: a leg
   that trades heavily has both large |flow| AND large settled OI simply because it
   is an active strike. ``magnitude_reconciliation`` therefore takes an optional
   ``control`` (cumulative traded volume) and reports the **partial** Spearman of
   |flow| vs OI *holding volume fixed* — the part NOT explained by raw activity.
   The raw rho is reported too, clearly labelled as the confounded one.

3. **Price-interaction tests need a DISTANCE-MATCHED baseline.** "Price was attracted
   to the gamma flip" is meaningless without "...more than to other strikes the SAME
   distance away." Levels like the gamma flip sit near the forward by construction,
   so a near-strike's normalized attraction is mechanically larger-variance than a
   far strike's — averaging over ALL strikes (mostly far) is an unfair comparator.
   ``distance_matched_levels`` selects baseline strikes at a comparable distance from
   the open forward, and ``level_attraction_vs_baseline`` consumes that.

4. **Significance is non-binding here.** At n=200–470 legs the p<0.05 bar is cleared
   by almost any weak correlation, AND legs within a session are not independent
   (call/put at a strike, adjacent strikes co-move), so the effective n is far
   smaller and p is anticonservative. We report rho/p as a DESCRIPTOR, never as a
   significance credential, and emit no optimistic verdict string.
"""
from __future__ import annotations

import math
from typing import Mapping, Sequence

from scipy.stats import spearmanr

__all__ = [
    "partial_spearman",
    "magnitude_reconciliation",
    "distance_matched_levels",
    "level_attraction",
    "level_attraction_vs_baseline",
    "pin_rate",
    "oi_walls",
]


def partial_spearman(
    x: Sequence[float], y: Sequence[float], z: Sequence[float]
) -> float:
    """Partial Spearman correlation of x,y controlling for z (NaN if degenerate).

    Rank-based partial correlation: Spearman is Pearson on ranks, so the partial is
    ``(r_xy − r_xz·r_yz) / sqrt((1−r_xz²)(1−r_yz²))`` on the pairwise Spearman rhos.
    Used to strip the shared-volume confound out of the |flow|-vs-OI relationship.
    """
    if len(x) < 3:
        return float("nan")
    r_xy, _ = spearmanr(x, y)
    r_xz, _ = spearmanr(x, z)
    r_yz, _ = spearmanr(y, z)
    denom = math.sqrt((1.0 - r_xz ** 2) * (1.0 - r_yz ** 2))
    if not math.isfinite(denom) or denom == 0.0:
        return float("nan")
    val = (r_xy - r_xz * r_yz) / denom
    return float(val)


def magnitude_reconciliation(
    settle_oi: Mapping[object, float],
    net_flow: Mapping[object, float],
    *,
    control: Mapping[object, float] | None = None,
    min_keys: int = 5,
) -> dict:
    """|net aggressor flow| vs settled OI per leg — the only ΔOI reconciliation valid
    on same-session 0DTE (see module docstring §2).

    Returns the raw Spearman ``rho``/``p`` (CONFOUNDED by activity) and, when a
    ``control`` map (e.g. cumulative volume per leg) is supplied, the ``partial_rho``
    holding volume fixed — the activity-independent part. No verdict string is
    emitted: on this sample neither number is evidence, and a label would invite
    out-of-context misreading.
    """
    keys = [
        k for k in (set(settle_oi) & set(net_flow))
        if settle_oi[k] != 0.0 and net_flow[k] != 0.0
        and (control is None or k in control)
    ]
    n = len(keys)
    if n < min_keys:
        return {"n": n, "rho": None, "p": None, "partial_rho": None}
    flow_abs = [abs(float(net_flow[k])) for k in keys]
    oi_abs = [abs(float(settle_oi[k])) for k in keys]
    rho, p = spearmanr(flow_abs, oi_abs)
    out = {"n": n, "rho": float(rho), "p": float(p), "partial_rho": None}
    if control is not None:
        vol = [abs(float(control[k])) for k in keys]
        pr = partial_spearman(flow_abs, oi_abs, vol)
        out["partial_rho"] = None if math.isnan(pr) else pr
    return out


def distance_matched_levels(
    reference: float,
    all_strikes: Sequence[float],
    forward: float,
    *,
    band: float,
) -> list:
    """Strikes whose |strike − forward| is within ``band`` of |reference − forward|.

    The fair baseline set for ``reference`` (a real level): same distance-from-spot
    regime, so normalized attraction is comparable. Excludes the reference strike
    itself.
    """
    ref_d = abs(reference - forward)
    return [
        s for s in all_strikes
        if s != reference and abs(abs(s - forward) - ref_d) <= band
    ]


def level_attraction(forward_open: float, forward_close: float, level: float) -> float:
    """Signed shrink in distance from ``level`` over the session, normalized.

    ``+1`` = price moved ALL the way onto the level by the close; ``0`` = no net
    change in distance; negative = price moved AWAY. Defined as
    ``(|open−level| − |close−level|) / |open−level|``. Undefined when price opened
    exactly on the level (returns ``0.0``).
    """
    d_open = abs(forward_open - level)
    d_close = abs(forward_close - level)
    if d_open == 0.0:
        return 0.0
    return (d_open - d_close) / d_open


def level_attraction_vs_baseline(
    forward_open: float,
    forward_close: float,
    level: float,
    baseline_levels: Sequence[float],
) -> dict:
    """``level_attraction`` for the real level vs the MEAN over baseline levels.

    ``baseline_levels`` MUST be distance-matched (see ``distance_matched_levels``) for
    ``excess`` to be meaningful — otherwise the comparison is biased by how far the
    level sits from spot. ``excess`` > 0 is the only direction that would (eventually,
    with enough sessions) support a pinning claim. ``baseline_mean`` is ``None`` when
    no matched baseline exists, and ``excess`` is then ``None`` (not a fake 0).
    """
    real = level_attraction(forward_open, forward_close, level)
    base_vals = [
        level_attraction(forward_open, forward_close, b) for b in baseline_levels
    ]
    if not base_vals:
        return {"level": level, "attraction": real, "baseline_mean": None,
                "excess": None, "n_baseline": 0}
    baseline = sum(base_vals) / len(base_vals)
    return {
        "level": level,
        "attraction": real,
        "baseline_mean": baseline,
        "excess": real - baseline,
        "n_baseline": len(base_vals),
    }


def pin_rate(closes: Sequence[float], level: float, tolerance: float) -> dict:
    """Fraction of session closes landing within ``tolerance`` of ``level``.

    ``closes`` is the per-minute forward series; ``tolerance`` is in index points
    (e.g. one strike step). Descriptive only — report alongside a baseline pin rate
    for arbitrary levels before reading anything into it.
    """
    if not closes:
        return {"pin_rate": None, "n": 0, "tolerance": tolerance}
    hits = sum(1 for c in closes if abs(c - level) <= tolerance)
    return {"pin_rate": hits / len(closes), "n": len(closes), "tolerance": tolerance}


def oi_walls(
    call_oi: Mapping[float, float],
    put_oi: Mapping[float, float],
    forward: float,
    *,
    top_n: int = 3,
) -> dict:
    """Top-N call/put strikes by raw open interest, on the correct side of spot.

    Call walls = highest-call-OI strikes ABOVE the forward; put walls =
    highest-put-OI strikes BELOW. This is the SpotGamma-classic **raw-OI** wall —
    deliberately NOT the product's intraday gamma-dollar wall (`gamma·OI`), because
    in the cross-day harness test we only have the prior session's settled OI, not
    its gamma. The caller MUST pass the PRIOR session's settle-OI and test it
    against the CURRENT session's price, so the levels are pre-committed (no
    look-ahead). Returns strikes ordered by OI descending (index 0 = rank 1).
    """
    calls = sorted(
        (k for k, v in call_oi.items() if k > forward and v > 0.0),
        key=lambda k: call_oi[k], reverse=True,
    )
    puts = sorted(
        (k for k, v in put_oi.items() if k < forward and v > 0.0),
        key=lambda k: put_oi[k], reverse=True,
    )
    return {"call_walls": calls[:top_n], "put_walls": puts[:top_n]}
