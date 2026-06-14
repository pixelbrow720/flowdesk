"""DDOI-GEX vs VOL-GEX per-strike STRUCTURAL DIVERGENCE — PURE core (stdlib + engine consts).

This is the *provable* half of the EOD collapse/divergence evaluation (the data-loading
half is the sibling runner ``run_ddoi_divergence.py``). It answers ONE contemporaneous,
look-ahead-free question on real 0DTE data:

    Is the DDOI-GEX per-strike profile STRUCTURALLY DIFFERENT from the locked VOL-GEX
    per-strike profile, or does it collapse to ~±VOL?

This is NOT a predictive test. The DDOI intraday time-weight ``w(i) = 1 − 2·(i/(n−1))``
is WHOLE-DAY-NORMALIZED (it needs ``n`` = the full-session trade count on a leg to know
where "late" is), so any per-minute predictive use is look-ahead-contaminated and is
explicitly OUT OF SCOPE. Here every number is computed AT END OF SESSION over the whole
day's trades and no outcome is scored, so there is no t→t+k leakage by construction.

What is reused (no greek re-derivation, no locked-file edits)
============================================================
* The intraday time weight is imported from :func:`engine.ddoi.ddoi_time_weight` and
  re-exposed as :func:`ddoi_leg_weight` — byte-identical to what the engine applies.
* The dealer signs + GEX scale are imported from :mod:`engine.exposure`
  (``DEALER_SIGN_CALL``/``DEALER_SIGN_PUT``/``GEX_PCT_SCALE``); ``M`` is passed in by the
  caller from ``engine.snapshot.MULTIPLIER``. Nothing is hardcoded.
* Per-strike gammas are the SAME ones ``build_snapshot``/``engine.exposure`` solve: the
  caller hands us the already-solved ``rows`` (``ChainRow``-shaped objects carrying
  ``strike``/``call_gamma``/``put_gamma``/``thin``/``call_vol``/``put_vol``). Thin strikes
  (gamma unsolved upstream) are SKIPPED, never fabricated.

The per-strike GEX template is the locked one, identical for VOL and DDOI — only the
per-leg *basis* (the ``flow`` map) changes:

    gex_strike = (SIGN_C·γ_call·flow_call + SIGN_P·γ_put·flow_put) · M · F² · 0.01

  * VOL basis : flow = cumulative unsigned volume per leg (Σ|size|)         → engine.exposure
  * DDOI basis: flow = Σ w(i)·|size_i| per leg (open/close time-weighted)   → engine.ddoi

NOTE on the controls (read before interpreting any divergence number)
---------------------------------------------------------------------
High correlation between DDOI and VOL is EXPECTED — they share the SAME per-strike
gammas, so a strike that is gamma-heavy is heavy in both. The meaningful quantity is the
RESIDUAL of real-DDOI vs the controls, NOT the raw DDOI-vs-VOL correlation:

  * UNIFORM-DDOI (``w ≡ 1``) reduces EXACTLY to Σ|size| = the VOL basis, so uniform-vs-VOL
    is ~identical by construction (a builder self-check, r≈1). It isolates that the ONLY
    thing the real DDOI adds over VOL is the intraday TIMING weight.
  * SHUFFLE-DDOI (same |sizes|, same weights, trade time-order randomized) destroys the
    timing structure. real-DDOI vs shuffle-DDOI isolates STRUCTURED timing from random.

EXPLORATORY: 4 correlated 0DTE days. Structural-divergence only, NOT predictive, NOT
validated. Do not read a verdict out of this module.

Only the standard library + the locked engine constants/weight are used. No file IO here.
"""
from __future__ import annotations

import math
import os
import sys
from typing import Mapping, Sequence, Tuple

# Engine lives outside the pnpm/py package tree; put its src on the path RELATIVE TO
# THIS FILE (cwd-independent) so the locked constants + time weight import cleanly when
# this module is imported from the repo root, a test, or the sibling runner.
_ENGINE_SRC = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "services", "engine", "src")
)
if _ENGINE_SRC not in sys.path:
    sys.path.insert(0, _ENGINE_SRC)

from engine.ddoi import ddoi_time_weight  # noqa: E402  (locked intraday weight)
from engine.exposure import (  # noqa: E402  (locked dealer signs + GEX scale)
    DEALER_SIGN_CALL,
    DEALER_SIGN_PUT,
    GEX_PCT_SCALE,
)

__all__ = [
    "ddoi_leg_weight",
    "ddoi_leg_value",
    "gex_by_strike",
    "per_strike_profiles",
    "divergence_metrics",
    "leg_timing_diagnostic",
]

#: A leg's flow map is keyed by (strike, is_call) -> basis value, matching the engine's
#: ``ddoi_flow`` / VOL convention.
FlowKey = Tuple[float, bool]


def ddoi_leg_weight(i: int, n: int) -> float:
    """Intraday open/close time weight for the ``i``-th of ``n`` chronological trades.

    Thin delegate to :func:`engine.ddoi.ddoi_time_weight` (REUSED, not re-implemented),
    so the weight is byte-identical to what the engine applies: ``+1`` for the first
    trade of the day on a leg (treated as opening), linearly to ``-1`` for the last
    (treated as closing); ``n == 1`` → ``+1``. ``i`` is 0-based.
    """
    return ddoi_time_weight(i, n)


def ddoi_leg_value(sorted_trades: Sequence, *, uniform: bool = False) -> float:
    """Σ w(i)·|size_i| over ONE leg's chronologically-sorted trades.

    ORDERING CONTRACT: ``sorted_trades`` MUST already be in ascending trade-time order —
    the time weight is positional and whole-day-normalized, so order is load-bearing. Each
    element is either a bare size (number) or a tuple/list whose LAST element is the size
    (e.g. ``(ts, size)`` or ``(ts, signed_size)``); the magnitude ``|size|`` is used in
    both cases, so the aggressor sign never enters DDOI (it stays orthogonal to VOL).

    With ``uniform=True`` the weight is ``w ≡ 1``, so the result reduces EXACTLY to
    Σ|size| = the leg's cumulative volume (the VOL basis) — this is the timing-free
    control.
    """
    sizes = []
    for t in sorted_trades:
        size = float(t[-1]) if isinstance(t, (tuple, list)) else float(t)
        sizes.append(abs(size))
    n = len(sizes)
    total = 0.0
    for i, s in enumerate(sizes):
        w = 1.0 if uniform else ddoi_leg_weight(i, n)
        total += w * s
    return total


def gex_by_strike(
    rows: Sequence,
    flow: Mapping[FlowKey, float],
    M: float,
    F: float,
) -> dict:
    """Per-strike GEX on the locked dealer-sign + gamma template for an ARBITRARY basis.

    ``rows`` are already-solved ``ChainRow``-shaped objects (``strike``/``call_gamma``/
    ``put_gamma``/``thin``); ``flow[(strike, is_call)]`` is the per-leg basis (VOL volume,
    DDOI synthetic-ΔOI, uniform, or shuffle). Returns ``{strike: gex}`` over NON-thin
    strikes only (thin → gamma unsolved upstream → skipped, never fabricated). Identical
    scaling/signs to ``engine.exposure``/``engine.ddoi``:

        gex = (SIGN_C·γ_call·flow_call + SIGN_P·γ_put·flow_put) · M · F² · GEX_PCT_SCALE
    """
    scale = M * F * F * GEX_PCT_SCALE
    out: dict = {}
    for r in rows:
        if getattr(r, "thin", False):
            continue
        k = float(r.strike)
        c = float(flow.get((k, True), 0.0))
        p = float(flow.get((k, False), 0.0))
        out[k] = (
            DEALER_SIGN_CALL * float(r.call_gamma) * c
            + DEALER_SIGN_PUT * float(r.put_gamma) * p
        ) * scale
    return out


def per_strike_profiles(
    rows: Sequence,
    ddoi_flow: Mapping[FlowKey, float],
    vol_flow: Mapping[FlowKey, float],
    M: float,
    F: float,
) -> Tuple[dict, dict]:
    """Aligned per-strike DDOI-GEX and VOL-GEX dicts from the SAME solved gammas.

    Convenience over :func:`gex_by_strike`: builds both profiles from the identical
    ``rows`` (so they are strike-aligned and share gammas exactly) — only the per-leg
    basis differs. Returns ``(ddoi_gex_by_strike, vol_gex_by_strike)``. The VOL profile
    here equals the locked ``engine.exposure`` profile (``build_snapshot``'s ``profile``)
    when ``vol_flow`` is the per-leg cumulative volume.
    """
    ddoi_by_strike = gex_by_strike(rows, ddoi_flow, M, F)
    vol_by_strike = gex_by_strike(rows, vol_flow, M, F)
    return ddoi_by_strike, vol_by_strike


# --------------------------------------------------------------------------- #
# pure correlation primitives (stdlib only — NO scipy here)
# --------------------------------------------------------------------------- #
def _pearson(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Pearson r (NaN if <2 points or a degenerate constant series)."""
    n = len(xs)
    if n < 2:
        return float("nan")
    mx = sum(xs) / n
    my = sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    den = math.sqrt(sxx * syy)
    if den == 0.0:
        return float("nan")
    return sxy / den


def _ranks(vals: Sequence[float]) -> list:
    """Average (tie-corrected) 1-based ranks, deterministic."""
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    ranks = [0.0] * len(vals)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0  # mean of 1-based ranks i+1..j+1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _spearman(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Spearman rho = Pearson on average ranks (NaN if degenerate)."""
    if len(xs) < 2:
        return float("nan")
    return _pearson(_ranks(xs), _ranks(ys))


def _ls_scalar_through_origin(d: Sequence[float], v: Sequence[float]) -> float:
    """Least-squares scalar ``c`` minimizing ‖d − c·v‖² (no intercept): c = Σ(d·v)/Σ(v²).

    NaN when ``v`` is all-zero (Σv² == 0, the regressor carries no energy).
    """
    svv = sum(x * x for x in v)
    if svv == 0.0:
        return float("nan")
    sdv = sum(a * b for a, b in zip(d, v))
    return sdv / svv


def _residual_r2(d: Sequence[float], v: Sequence[float], c: float) -> float:
    """Fraction of ``d``'s variance explained by the scalar fit ``c·v``.

    ``residual = d − c·v``; ``r2 = 1 − Σresidual² / Σ(d − mean_d)²``. NaN when ``c`` is
    NaN or ``d`` is constant (zero total variance => the ratio is undefined). r2≈1 means
    ``d`` is ~a pure scalar multiple of ``v`` (redundant); a large structured residual
    drives r2 down and is the ONLY route to genuine divergence.
    """
    if math.isnan(c):
        return float("nan")
    n = len(d)
    if n == 0:
        return float("nan")
    md = sum(d) / n
    sstot = sum((x - md) ** 2 for x in d)
    if sstot == 0.0:
        return float("nan")
    ssres = sum((a - c * b) ** 2 for a, b in zip(d, v))
    return 1.0 - ssres / sstot


def _ols(x: Sequence[float], y: Sequence[float]) -> Tuple[float, float]:
    """Ordinary least-squares ``(slope, r2)`` of ``y ~ a + b·x`` (with intercept).

    Returns ``(nan, nan)`` if <2 points or ``x`` is constant (slope undefined). r2 is the
    coefficient of determination of the fitted line; for a single regressor r2 == r².
    """
    n = len(x)
    if n < 2:
        return float("nan"), float("nan")
    mx = sum(x) / n
    my = sum(y) / n
    sxx = sum((xi - mx) ** 2 for xi in x)
    if sxx == 0.0:
        return float("nan"), float("nan")
    sxy = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    slope = sxy / sxx
    syy = sum((yi - my) ** 2 for yi in y)
    if syy == 0.0:
        return slope, float("nan")
    intercept = my - slope * mx
    ssres = sum((yi - (intercept + slope * xi)) ** 2 for xi, yi in zip(x, y))
    r2 = 1.0 - ssres / syy
    return slope, r2


def _sign(v: float) -> int:
    return 1 if v > 0.0 else (-1 if v < 0.0 else 0)


def _argmax_abs_strike(by_strike: Mapping[float, float]):
    """Strike carrying the largest |gex| (the dominant strike). None if empty."""
    if not by_strike:
        return None
    return max(by_strike, key=lambda s: abs(by_strike[s]))


def divergence_metrics(
    ddoi_profile: Mapping[float, float],
    vol_profile: Mapping[float, float],
) -> dict:
    """The COLLAPSE test core: how STRUCTURALLY different is DDOI-GEX from VOL-GEX?

    Cross-sectional over the strikes SHARED by both profiles (sorted ascending), PURE and
    deterministic. Inputs are ``{strike: gex}`` dicts (see :func:`per_strike_profiles`).

    Returns a dict with:
      * ``n``                  — number of shared strikes compared.
      * ``pearson``            — cross-sectional Pearson r of the two SIGNED GEX profiles.
                                 NOTE: a strongly NEGATIVE pearson is NOT evidence of
                                 structural divergence — see ``magnitude_pearson``.
      * ``spearman``           — Spearman rho (rank), robust to scale/outliers.
      * ``magnitude_pearson``  — Pearson of ``|ddoi|`` vs ``|vol|``. THE SIGN-FLIP
                                 DETECTOR: if this is ≈+1 while signed ``pearson`` is
                                 negative, DDOI is the SAME per-strike SHAPE with a flipped
                                 sign (the ``Σw = 0`` de-meaning artefact) = REDUNDANT with
                                 VOL, NOT a genuine strike re-weighting.
      * ``neg_pearson``        — Pearson of ``ddoi`` vs ``−vol`` (convenience; ≈ −``pearson``,
                                 reported explicitly so a sign flip reads as ≈+1 directly).
      * ``best_fit_scalar_c``  — least-squares scalar ``c = Σ(d·v)/Σ(v²)`` (through origin,
                                 no intercept) fitting ``ddoi ≈ c·vol``.
      * ``residual_r2``        — variance of ``ddoi`` explained by ``c·vol``
                                 (``1 − Σ(d−c·v)²/Σ(d−mean_d)²``). THE REDUNDANCY DETECTOR:
                                 high ``|c|`` with ``residual_r2 ≈ 1`` ⇒ DDOI is ~a scalar
                                 multiple of VOL (redundant, no new structure). Only a
                                 LARGE STRUCTURED residual (``residual_r2`` well below 1)
                                 leaves room for genuine divergence.
      * ``sign_agreement``     — fraction of strikes where ``sign(ddoi)==sign(vol)`` (in
                                 {-1,0,+1}); per-strike structural sign match.
      * ``ddoi_argmax_strike`` / ``vol_argmax_strike`` — dominant (|max|) strike each.
      * ``argmax_distance``    — ``|ddoi_argmax − vol_argmax|`` in strike points
                                 (aggregate-level "do they peak at the same strike?").
      * ``ddoi_net_sign`` / ``vol_net_sign`` — sign of the summed profile (aggregate GEX).
      * ``net_sign_agreement`` — whether the two aggregate net signs match (bool).

    READ: the INFORMATIVE quantities are ``magnitude_pearson`` (sign-flip detector) +
    ``residual_r2`` (redundancy detector) + ``argmax_distance`` (does the dominant strike
    move?), NOT the raw SIGNED ``pearson``. A signed pearson of ~−1 with
    ``magnitude_pearson``≈+1 and ``residual_r2``≈1 is the documented MECHANICAL SIGN FLIP
    (``w(i)=1−2·i/(n−1)`` sums to 0 ⇒ back-loaded legs flip ddoi_leg negative), i.e. DDOI
    is redundant with VOL, not structurally divergent.
    """
    strikes = sorted(set(ddoi_profile) & set(vol_profile))
    n = len(strikes)
    if n == 0:
        return {
            "n": 0, "pearson": float("nan"), "spearman": float("nan"),
            "magnitude_pearson": float("nan"), "neg_pearson": float("nan"),
            "best_fit_scalar_c": float("nan"), "residual_r2": float("nan"),
            "sign_agreement": float("nan"),
            "ddoi_argmax_strike": None, "vol_argmax_strike": None,
            "argmax_distance": None,
            "ddoi_net_sign": 0, "vol_net_sign": 0, "net_sign_agreement": False,
        }
    d = [float(ddoi_profile[s]) for s in strikes]
    v = [float(vol_profile[s]) for s in strikes]

    sign_hits = sum(1 for a, b in zip(d, v) if _sign(a) == _sign(b))
    d_arg = _argmax_abs_strike({s: ddoi_profile[s] for s in strikes})
    v_arg = _argmax_abs_strike({s: vol_profile[s] for s in strikes})
    d_net = _sign(sum(d))
    v_net = _sign(sum(v))

    neg_v = [-x for x in v]
    c = _ls_scalar_through_origin(d, v)

    return {
        "n": n,
        "pearson": _pearson(d, v),
        "spearman": _spearman(d, v),
        "magnitude_pearson": _pearson([abs(x) for x in d], [abs(x) for x in v]),
        "neg_pearson": _pearson(d, neg_v),
        "best_fit_scalar_c": c,
        "residual_r2": _residual_r2(d, v, c),
        "sign_agreement": sign_hits / n,
        "ddoi_argmax_strike": d_arg,
        "vol_argmax_strike": v_arg,
        "argmax_distance": abs(d_arg - v_arg),
        "ddoi_net_sign": d_net,
        "vol_net_sign": v_net,
        "net_sign_agreement": d_net == v_net,
    }


def leg_timing_diagnostic(legs: Sequence) -> dict:
    """Reproducible per-LEG back-loading diagnostic (the quant-greeks auditor's hand check).

    PURE and deterministic. ``legs`` is an ITERABLE of per-leg tuples, one element per
    option leg that traded, each shaped ``(ddoi_leg, vol_leg, late_half_share)``:

      * ``ddoi_leg``        — the leg's ``Σ w(i)·|size_i|`` (signed; can be negative, which
                              is the whole point of this diagnostic).
      * ``vol_leg``         — the leg's ``Σ|size_i|`` (≥ 0).
      * ``late_half_share`` — the leg's fraction of |size| traded in the SECOND HALF of the
                              session by time (the direct back-loading evidence; in [0, 1],
                              where >0.5 means volume is centroid-late).

    Returns:
      * ``n_legs``               — number of legs supplied.
      * ``frac_legs_backloaded`` — fraction with ``ddoi_leg < 0``. Because ``Σw = 0``
                                   EXACTLY, ``ddoi_leg`` is a de-meaned covariance of |size|
                                   with trade time-position; a NEGATIVE value means the
                                   leg's volume centroid is LATE. A high fraction here is
                                   the mechanical driver of the negative GEX correlation.
      * ``mean_late_share``      — mean of ``late_half_share`` over legs (the independent,
                                   weight-free confirmation that volume is back-loaded).
      * ``ols_slope`` / ``ols_r2`` — slope ``β`` and R² of ``ddoi_leg ~ vol_leg`` (with
                                   intercept). A consistently late centroid drives ``β`` < 0
                                   (bigger legs ⇒ more negative ddoi_leg) — the signature
                                   that the negative DDOI-vs-VOL GEX correlation is
                                   MECHANICAL back-loading, not positioning information.

    READ: consistently-late centroid (``mean_late_share`` > 0.5, ``frac_legs_backloaded``
    high) together with a NEGATIVE ``ols_slope`` ⇒ the negative GEX correlation is the
    ``Σw=0`` timing-skew artefact, NOT directional positioning signal.
    """
    dd: list = []
    vv: list = []
    ls: list = []
    for leg in legs:
        ddoi_leg, vol_leg, late_half_share = leg
        dd.append(float(ddoi_leg))
        vv.append(float(vol_leg))
        ls.append(float(late_half_share))
    n = len(dd)
    if n == 0:
        return {
            "n_legs": 0,
            "frac_legs_backloaded": float("nan"),
            "mean_late_share": float("nan"),
            "ols_slope": float("nan"),
            "ols_r2": float("nan"),
        }
    frac_back = sum(1 for x in dd if x < 0.0) / n
    mean_late = sum(ls) / n
    slope, r2 = _ols(vv, dd)
    return {
        "n_legs": n,
        "frac_legs_backloaded": frac_back,
        "mean_late_share": mean_late,
        "ols_slope": slope,
        "ols_r2": r2,
    }
