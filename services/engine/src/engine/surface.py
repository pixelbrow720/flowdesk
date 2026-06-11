"""Volatility surface — raw SVI slice fit + expected move (FlowGreeks vol module).

A single-expiry **raw SVI** (Stochastic Volatility Inspired, Gatheral 2004)
parameterisation of the total-variance smile, plus the 0DTE **expected move**.
Isolated and additive: this module does NOT touch the Snapshot contract
(``schema_version`` 1); its output lives in :class:`VolSlice` until a schema
decision is taken. It reuses the engine's own :mod:`engine.iv` solver upstream
(the caller passes already-solved per-strike IVs) so the surface is consistent
with the rest of the pricing core.

Raw SVI (mega-riset §SVI)
=========================
In log-moneyness ``k = ln(K / F)`` the total implied variance is

    w(k) = a + b * ( rho * (k - m) + sqrt((k - m)**2 + sigma**2) )

with the five raw parameters

  * ``a``      vertical level (min variance floor as ``k -> -+inf`` slopes meet),
  * ``b >= 0`` overall slope/wing tightness,
  * ``|rho| < 1`` skew (rotation), ``rho < 0`` = put skew (typical equity),
  * ``m``      horizontal shift of the smile minimum,
  * ``sigma > 0`` smoothness of the ATM curvature.

The Black-76 implied vol at ``k`` is ``sqrt(max(w(k), 0) / T)``. Gatheral's
sufficient no-butterfly conditions used here: ``b >= 0``, ``|rho| < 1``,
``sigma > 0`` and ``a + b*sigma*sqrt(1 - rho**2) >= 0`` (so ``w >= 0``
everywhere). A finer ``g(k) >= 0`` density check is provided separately.

Expected move (mega-riset §EM)
==============================
Two equivalent estimators of the 1-sigma move to expiry:
  * lognormal:  ``EM ~= F * sigma_ATM * sqrt(T)`` (:func:`expected_move`);
  * ATM straddle: ``EM ~= 0.85 * straddle_mid`` (:func:`expected_move_from_straddle`),
    the standard front-month rule of thumb.

The fitter is a self-contained Nelder-Mead simplex (no numpy/scipy) so the
module keeps the engine's allocation-light, stdlib-only hot path.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence

#: Nelder-Mead objective: maps a parameter vector to a scalar loss.
Objective = Callable[[List[float]], float]

__all__ = [
    "SVIParams",
    "VolSlice",
    "total_variance",
    "svi_vol",
    "is_butterfly_arbitrage_free",
    "fit_svi",
    "expected_move",
    "expected_move_from_straddle",
]

#: ATM straddle -> 1-sigma move rule-of-thumb factor (mega-riset §EM).
STRADDLE_EM_FACTOR: float = 0.85
#: Fitter controls.
_MAX_ITERS: int = 2000
_TOL: float = 1e-12
_RHO_CAP: float = 0.999    # keep |rho| < 1 strictly
_SIGMA_FLOOR: float = 1e-6
_B_FLOOR: float = 0.0


@dataclass(frozen=True)
class SVIParams:
    """Raw-SVI parameters for one expiry slice (in log-moneyness ``k``)."""

    a: float
    b: float
    rho: float
    m: float
    sigma: float

    def to_dict(self) -> dict[str, float]:
        return {"a": self.a, "b": self.b, "rho": self.rho, "m": self.m, "sigma": self.sigma}


@dataclass(frozen=True)
class VolSlice:
    """A fitted vol slice: SVI params, ATM vol, expected move, fit quality."""

    params: SVIParams
    forward: float
    t_expiry: float
    atm_vol: float
    expected_move: float
    rmse: float
    arb_free: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "params": self.params.to_dict(),
            "forward": self.forward,
            "t_expiry": self.t_expiry,
            "atm_vol": self.atm_vol,
            "expected_move": self.expected_move,
            "rmse": self.rmse,
            "arb_free": self.arb_free,
        }


def total_variance(params: SVIParams, k: float) -> float:
    """Raw-SVI total implied variance ``w(k)`` at log-moneyness ``k``."""
    dk = k - params.m
    return params.a + params.b * (params.rho * dk + math.sqrt(dk * dk + params.sigma * params.sigma))


def svi_vol(params: SVIParams, k: float, T: float) -> float:
    """Black-76 implied vol from the SVI slice at ``k`` (``sqrt(w/T)``)."""
    if not (T > 0.0):
        raise ValueError(f"T must be > 0, got {T!r}")
    w = total_variance(params, k)
    if w <= 0.0:
        return 0.0
    return math.sqrt(w / T)


def is_butterfly_arbitrage_free(params: SVIParams) -> bool:
    """Gatheral's sufficient no-butterfly conditions for a raw-SVI slice.

    ``b >= 0``, ``|rho| < 1``, ``sigma > 0`` and ``a + b*sigma*sqrt(1-rho**2) >= 0``
    (the smile minimum total variance is non-negative). Sufficient, not
    necessary — a slice failing this may still be arb-free, but a passing slice
    is guaranteed convex enough for a non-negative risk-neutral density.
    """
    if not (params.b >= 0.0):
        return False
    if not (abs(params.rho) < 1.0):
        return False
    if not (params.sigma > 0.0):
        return False
    floor = params.a + params.b * params.sigma * math.sqrt(1.0 - params.rho * params.rho)
    return floor >= -1e-12


def _objective(
    p: Sequence[float],
    ks: Sequence[float],
    ws: Sequence[float],
    weights: Sequence[float],
) -> float:
    """Weighted SSE in total variance with soft penalties for constraint breaks."""
    a, b, rho, m, sigma = p
    penalty = 0.0
    if b < _B_FLOOR:
        penalty += 1e6 * (_B_FLOOR - b) ** 2
        b = _B_FLOOR
    if sigma < _SIGMA_FLOOR:
        penalty += 1e6 * (_SIGMA_FLOOR - sigma) ** 2
        sigma = _SIGMA_FLOOR
    if abs(rho) > _RHO_CAP:
        over = abs(rho) - _RHO_CAP
        penalty += 1e6 * over * over
        rho = math.copysign(_RHO_CAP, rho)
    params = SVIParams(a=a, b=b, rho=rho, m=m, sigma=sigma)
    sse = 0.0
    for k, w_obs, wt in zip(ks, ws, weights):
        diff = total_variance(params, k) - w_obs
        sse += wt * diff * diff
    # discourage a negative variance floor (keeps w >= 0)
    floor = a + b * sigma * math.sqrt(max(1.0 - rho * rho, 0.0))
    if floor < 0.0:
        penalty += 1e6 * floor * floor
    return sse + penalty


def _nelder_mead(
    f: "Objective",
    x0: List[float],
    *,
    max_iters: int = _MAX_ITERS,
    tol: float = _TOL,
) -> List[float]:
    """Minimise ``f`` from ``x0`` with a standard Nelder-Mead simplex (stdlib)."""
    n = len(x0)
    alpha, gamma, rho_c, sigma_c = 1.0, 2.0, 0.5, 0.5
    simplex: List[List[float]] = [list(x0)]
    for i in range(n):
        pt = list(x0)
        step = 0.05 if x0[i] == 0.0 else 0.05 * abs(x0[i])
        pt[i] += step if step != 0.0 else 0.05
        simplex.append(pt)
    fvals = [f(p) for p in simplex]

    for _ in range(max_iters):
        order = sorted(range(n + 1), key=lambda j: fvals[j])
        simplex = [simplex[j] for j in order]
        fvals = [fvals[j] for j in order]
        if abs(fvals[-1] - fvals[0]) <= tol * (abs(fvals[0]) + abs(fvals[-1]) + tol):
            break

        centroid = [sum(simplex[j][d] for j in range(n)) / n for d in range(n)]
        worst = simplex[-1]
        refl = [centroid[d] + alpha * (centroid[d] - worst[d]) for d in range(n)]
        f_refl = f(refl)

        if fvals[0] <= f_refl < fvals[-2]:
            simplex[-1], fvals[-1] = refl, f_refl
            continue
        if f_refl < fvals[0]:
            expd = [centroid[d] + gamma * (refl[d] - centroid[d]) for d in range(n)]
            f_exp = f(expd)
            if f_exp < f_refl:
                simplex[-1], fvals[-1] = expd, f_exp
            else:
                simplex[-1], fvals[-1] = refl, f_refl
            continue
        contr = [centroid[d] + rho_c * (worst[d] - centroid[d]) for d in range(n)]
        f_con = f(contr)
        if f_con < fvals[-1]:
            simplex[-1], fvals[-1] = contr, f_con
            continue
        best = simplex[0]
        for j in range(1, n + 1):
            simplex[j] = [best[d] + sigma_c * (simplex[j][d] - best[d]) for d in range(n)]
            fvals[j] = f(simplex[j])

    best_idx = min(range(n + 1), key=lambda j: fvals[j])
    return simplex[best_idx]


def _clamp_params(p: Sequence[float]) -> SVIParams:
    a, b, rho, m, sigma = p
    b = max(b, _B_FLOOR)
    sigma = max(sigma, _SIGMA_FLOOR)
    rho = max(-_RHO_CAP, min(_RHO_CAP, rho))
    return SVIParams(a=a, b=b, rho=rho, m=m, sigma=sigma)


def fit_svi(
    strikes: Sequence[float],
    vols: Sequence[float],
    forward: float,
    t_expiry: float,
    *,
    weights: Optional[Sequence[float]] = None,
) -> VolSlice:
    """Fit a raw-SVI slice to ``(strike, implied_vol)`` pairs at one expiry.

    ``vols`` are Black-76 implied vols (annualised, per 1.00) already solved by
    :mod:`engine.iv`; strikes with no reliable IV should be dropped by the caller
    before calling. Needs at least 5 points for a determined 5-parameter fit
    (fewer raises ``ValueError``). Returns a :class:`VolSlice` carrying the fitted
    params, the ATM vol (``k = 0``), the expected move and the fit RMSE (in vol).
    """
    if not (forward > 0.0):
        raise ValueError(f"forward must be > 0, got {forward!r}")
    if not (t_expiry > 0.0):
        raise ValueError(f"t_expiry must be > 0, got {t_expiry!r}")
    if len(strikes) != len(vols):
        raise ValueError("strikes and vols must have equal length")
    if len(strikes) < 5:
        raise ValueError(f"raw SVI needs >= 5 strikes, got {len(strikes)}")

    ks: List[float] = [math.log(float(K) / forward) for K in strikes]
    ws: List[float] = [float(v) * float(v) * t_expiry for v in vols]
    wts: List[float] = list(weights) if weights is not None else [1.0] * len(ks)
    if len(wts) != len(ks):
        raise ValueError("weights length must match strikes")

    w_min = min(ws)
    w_max = max(ws)
    k_span = max((max(ks) - min(ks)), 1e-3)
    a0 = max(w_min, 1e-8)
    b0 = max((w_max - w_min) / k_span, 1e-4)
    x0 = [a0, b0, -0.3, 0.0, max(0.1 * k_span, 1e-2)]

    def obj(p: List[float]) -> float:
        return _objective(p, ks, ws, wts)

    best = _nelder_mead(obj, x0)
    params = _clamp_params(best)

    sse = 0.0
    for K, v in zip(strikes, vols):
        k = math.log(float(K) / forward)
        model_vol = svi_vol(params, k, t_expiry)
        sse += (model_vol - float(v)) ** 2
    rmse = math.sqrt(sse / len(strikes))

    atm_vol = svi_vol(params, 0.0, t_expiry)
    em = expected_move(forward, atm_vol, t_expiry)
    return VolSlice(
        params=params,
        forward=forward,
        t_expiry=t_expiry,
        atm_vol=atm_vol,
        expected_move=em,
        rmse=rmse,
        arb_free=is_butterfly_arbitrage_free(params),
    )


def expected_move(forward: float, sigma_atm: float, t_expiry: float) -> float:
    """1-sigma lognormal expected move ``F * sigma_ATM * sqrt(T)`` (index points)."""
    if not (forward > 0.0):
        raise ValueError(f"forward must be > 0, got {forward!r}")
    if sigma_atm < 0.0 or t_expiry < 0.0:
        raise ValueError("sigma_atm and t_expiry must be non-negative")
    return forward * sigma_atm * math.sqrt(t_expiry)


def expected_move_from_straddle(straddle_mid: float, *, factor: float = STRADDLE_EM_FACTOR) -> float:
    """Expected move from the ATM straddle: ``factor * straddle_mid`` (default 0.85)."""
    if straddle_mid < 0.0:
        raise ValueError(f"straddle_mid must be >= 0, got {straddle_mid!r}")
    return factor * straddle_mid
