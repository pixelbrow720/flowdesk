"""TRACE-style field projection for FlowDesk (heatmap right panel).

Projects the dealer-exposure surface onto a price grid, producing the
index-aligned ``field{price_grid[], gamma[], delta[]}`` arrays of the Snapshot
contract (``schema_version`` 1).

Projection model (TRACE / SpotGamma B7 — re-evaluate, do NOT smear)
==================================================================
The heatmap is a true exposure *field*: ``gamma[i]`` is the dealer net gamma
exposure felt **if the underlying were trading at the hypothetical spot**
``price_grid[i]`` — NOT the per-strike profile sampled/interpolated at that
price. For every hypothetical spot ``S_y`` we RE-EVALUATE each contract's
Black-76 greek at ``S_y`` (holding each strike's solved IV fixed — sticky-strike)
and sum under the locked dealer convention:

    gamma[i] = ( Σ  +call_gamma(S_y)·call_vol  −put_gamma(S_y)·put_vol ) · M · S_y² · 0.01
    delta[i] = ( Σ  +call_delta(S_y)·call_vol  −put_delta(S_y)·put_vol ) · M · S_y

This is the same locked formula as :mod:`engine.exposure` (VOL-based, dealer
long-call / short-put), but evaluated across the price axis instead of only at
the forward. The bell shape of Black-76 gamma in ``S`` is what produces the
smooth "topographic" ridges/valleys — the smoothing is intrinsic to the math,
not an artificial blur. At ``S_y == F`` the field equals the sum of the
per-strike profile (a useful sanity check).

Thin legs (IV unsolved upstream) carry ``call_iv``/``put_iv == None`` and
contribute zero — they have no reliable gamma curve to project.

**Row/col ordering:** arrays are row-major over the price index ``i`` in
**strictly ascending price order**; ``price_grid[i]`` corresponds 1:1 to
``gamma[i]`` and ``delta[i]``. This satisfies the contract invariant
``len(price_grid) == len(gamma) == len(delta)``.

An optional zero-phase **Gaussian** pass (``smoothing_bw`` > 0, bandwidth in
index points) further smooths the curve for the heatmap without breaking the
contract invariants.

Only the standard library + sibling ``engine`` modules are used.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Protocol, Sequence

import numpy as np
from scipy.special import ndtr  # standard-normal CDF == 0.5*(1+erf(x/sqrt2))

from engine.exposure import (
    DEALER_SIGN_CALL,
    DEALER_SIGN_PUT,
    GEX_PCT_SCALE,
    ChainRow,
)

__all__ = [
    "AxisLike",
    "Axis",
    "FieldArrays",
    "CLIP_PERCENTILE",
    "price_grid_from_axis",
    "percentile_abs",
    "normalize_signed",
    "build_field",
]


class AxisLike(Protocol):
    """Structural type for the shared strike axis (matches schema ``Axis``)."""

    strike_min: float
    strike_max: float
    step: float


@dataclass(frozen=True)
class Axis:
    """Convenience concrete axis. ``step`` must be > 0."""

    strike_min: float
    strike_max: float
    step: float


#: Percentile used to clip the heatmap colour scale (anti-skew §6G): a single
#: 0DTE gamma spike must not burn the whole field to neutral. The engine
#: produces the RAW exposure field (``build_field``); this is the canonical
#: clip used for *display normalisation*, mirrored byte-for-byte by the FE
#: ``apps/web/lib/heatmap/field-2d.ts`` (``CLIP_PERCENTILE``). Kept here so the
#: normalisation has one tested definition shared across the stack.
CLIP_PERCENTILE: float = 0.98


@dataclass(frozen=True)
class FieldArrays:
    """Index-aligned projection arrays. Matches the Snapshot ``field`` contract."""

    price_grid: List[float]
    gamma: List[float]
    delta: List[float]

    def to_dict(self) -> dict:
        return {
            "price_grid": list(self.price_grid),
            "gamma": list(self.gamma),
            "delta": list(self.delta),
        }


def price_grid_from_axis(axis: AxisLike) -> List[float]:
    """Default price grid: strike nodes ``strike_min .. strike_max`` by ``step``.

    Ascending, inclusive of both ends; the final point is clamped to
    ``strike_max`` to absorb floating-point drift.
    """
    step = float(axis.step)
    if not (step > 0.0):
        raise ValueError("axis.step must be > 0")
    lo, hi = float(axis.strike_min), float(axis.strike_max)
    if hi < lo:
        raise ValueError("axis.strike_max must be >= axis.strike_min")
    n = int(round((hi - lo) / step))
    grid = [lo + i * step for i in range(n + 1)]
    if grid:
        grid[-1] = hi
    return grid


def percentile_abs(values: Sequence[float], p: float = CLIP_PERCENTILE) -> float:
    """``p``-th percentile of ``|values|`` (the colour-scale clip magnitude).

    Mirrors the FE ``percentileAbs`` exactly: take ``abs`` of every value, sort
    ascending, index with ``floor(p * (n - 1))`` clamped to ``[0, n-1]``. Empty
    input -> ``0.0``. ``p`` is clamped to ``[0, 1]``.

    Pass the NON-ZERO field magnitudes (as the FE does — it filters ``v != 0``)
    when you want the clip to ignore empty strikes; this function itself does no
    filtering so it stays a pure percentile.
    """
    if not values:
        return 0.0
    p = 0.0 if p < 0.0 else (1.0 if p > 1.0 else p)
    arr = sorted(abs(float(v)) for v in values)
    idx = int(math.floor(p * (len(arr) - 1)))
    idx = 0 if idx < 0 else (len(arr) - 1 if idx > len(arr) - 1 else idx)
    return arr[idx]


def normalize_signed(value: float, max_abs: float) -> float:
    """Map a signed exposure to ``[0, 1]`` for the diverging shader.

    ``+max_abs -> 0`` (turquoise), ``0 -> 0.5`` (neutral), ``-max_abs -> 1``
    (crimson); clamped to ``[0, 1]``. ``max_abs <= 0`` -> ``0.5`` (neutral).
    Mirrors the FE ``normalizeSigned`` byte-for-byte so engine-side previews and
    the browser agree on colour.
    """
    if max_abs <= 0.0:
        return 0.5
    t = 0.5 - 0.5 * (value / max_abs)
    return 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)


def _gaussian_smooth(
    grid: Sequence[float], vals: Sequence[float], bw: float
) -> List[float]:
    """Zero-phase Nadaraya-Watson Gaussian smoother over the price grid."""
    if bw <= 0.0 or len(vals) < 2:
        return [float(v) for v in vals]
    out: List[float] = []
    for pi in grid:
        wsum = 0.0
        vsum = 0.0
        for pj, vj in zip(grid, vals):
            w = math.exp(-0.5 * ((pi - pj) / bw) ** 2)
            wsum += w
            vsum += w * vj
        out.append(vsum / wsum if wsum > 0.0 else 0.0)
    return out


def build_field(
    rows: Sequence[ChainRow],
    axis: AxisLike,
    F: float,
    M: float,
    rate: float,
    price_grid: Optional[Sequence[float]] = None,
    *,
    smoothing_bw: float = 0.0,
) -> FieldArrays:
    """Project the dealer exposure surface onto the price grid (TRACE B7).

    For each hypothetical spot ``S_y`` in the grid, re-evaluate every contract's
    Black-76 gamma/delta at ``S_y`` (sticky-strike IV) and sum under the locked
    dealer convention, scaled by the locked notional factors.

    Parameters
    ----------
    rows : solved chain rows (strike, call/put IV, t_expiry, call/put VOL).
    axis : shared strike axis; used to derive the default grid.
    F : forward (futures) price — kept for symmetry / future use; the projection
        evaluates at each grid price, not at ``F``.
    M : instrument contract multiplier (USD per index point).
    rate : continuous annual rate ``r = ln(1 + SOFR)``.
    price_grid : optional explicit price grid (index points); defaults to the
        axis strike nodes. Sorted ascending.
    smoothing_bw : optional Gaussian bandwidth (index points). ``0`` (default)
        keeps the pure re-evaluated field.

    Returns
    -------
    FieldArrays with ``len(price_grid) == len(gamma) == len(delta)`` and all
    values finite — the contract invariants.
    """
    grid = (
        sorted(float(p) for p in price_grid)
        if price_grid is not None
        else price_grid_from_axis(axis)
    )

    # Vectorized over the price grid: for each contract, evaluate Black-76
    # gamma/delta at EVERY grid price at once (numpy), instead of a Python loop
    # per (contract, price). Replicates engine.black76 exactly (same d1, same
    # exp(-rT) discount, same normal pdf/cdf via scipy ndtr) so the field stays
    # within 1e-9 of the scalar greeks — just ~grid-size faster.
    grid_arr = np.asarray(grid, dtype=float)
    n = grid_arr.size
    g_acc = np.zeros(n)
    d_acc = np.zeros(n)
    pos = grid_arr > 0.0  # log/divide only defined for positive spot
    log_sy = np.zeros(n)
    log_sy[pos] = np.log(grid_arr[pos])
    inv_sqrt_2pi = 1.0 / math.sqrt(2.0 * math.pi)

    for r in rows:
        T = r.t_expiry
        if T is None or T <= 0.0:
            continue
        K = float(r.strike)
        sqrt_t = math.sqrt(T)
        log_k = math.log(K)
        disc = math.exp(-rate * T)
        for iv, vol, sign, is_call in (
            (r.call_iv, r.call_vol, DEALER_SIGN_CALL, True),
            (r.put_iv, r.put_vol, DEALER_SIGN_PUT, False),
        ):
            if iv is None or iv <= 0.0:
                continue
            v = float(vol)
            if v == 0.0:
                continue
            vol_t = iv * sqrt_t
            d1 = np.zeros(n)
            d1[pos] = (log_sy[pos] - log_k + 0.5 * iv * iv * T) / vol_t
            pdf = inv_sqrt_2pi * np.exp(-0.5 * d1 * d1)
            gam = np.zeros(n)
            gam[pos] = disc * pdf[pos] / (grid_arr[pos] * vol_t)
            cdf = ndtr(d1)
            dlt = disc * cdf if is_call else disc * (cdf - 1.0)
            dlt = np.where(pos, dlt, 0.0)
            g_acc += sign * gam * v
            d_acc += sign * dlt * v

    gamma = (g_acc * M * grid_arr * grid_arr * GEX_PCT_SCALE).tolist()
    delta = (d_acc * M * grid_arr).tolist()

    if smoothing_bw > 0.0:
        gamma = _gaussian_smooth(grid, gamma, smoothing_bw)
        delta = _gaussian_smooth(grid, delta, smoothing_bw)

    # Enforce contract invariants defensively.
    if not (len(grid) == len(gamma) == len(delta)):
        raise ValueError("field arrays must be index-aligned and equal length")
    for seq_name, seq in (("gamma", gamma), ("delta", delta), ("price_grid", grid)):
        if any(not math.isfinite(v) for v in seq):
            raise ValueError(f"field.{seq_name} contains non-finite values")

    return FieldArrays(price_grid=grid, gamma=gamma, delta=delta)
