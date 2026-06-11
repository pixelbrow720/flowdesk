"""Implied-volatility solver for Black-76 options on futures (FlowDesk).

Given an option MID price, recover the Black-76 implied volatility with a
Newton-Raphson iteration (seeded by the Brenner-Subrahmanyam ATM approximation)
that is *safeguarded* by a maintained bracket ``[IV_LOWER, IV_UPPER]``. Whenever
a Newton step would leave the bracket, or vega is non-positive / non-finite, the
iteration falls back to a bisection step on the bracket. This guarantees
convergence for any mid price that is strictly inside the no-arbitrage band.

Maps to PRD #12 acceptance T-02 (round-trip < 1e-6) and T-03 (thin liquidity
does not crash; typical convergence < 50 iterations).

Arbitrage bounds checked (return ``None`` if violated)
-----------------------------------------------------
With discount factor ``disc = exp(-r*T)`` and forward ``F``:
  * call: ``disc * max(F - K, 0)  <  mid  <  disc * F``
  * put : ``disc * max(K - F, 0)  <  mid  <  disc * K``
Mid prices at/below the discounted intrinsic (lower bound) imply a volatility
below ``IV_LOWER``; mid prices at/above the discounted forward/strike (upper
bound, the ``sigma -> inf`` limit) imply a volatility above ``IV_UPPER``. Both
are reported as unsolvable (``None``) so the caller can interpolate.

Only the standard library ``math`` is used (numpy stays pinned for the engine).
"""

from __future__ import annotations

import math
from typing import NamedTuple, Optional

from engine.black76 import OptionType, price, vega

__all__ = [
    "IV_LOWER",
    "IV_UPPER",
    "PRICE_TOL",
    "STEP_TOL",
    "MAX_ITERS",
    "IVResult",
    "implied_vol",
    "solve_iv",
    "is_iv_reliable",
]

#: Volatility search bracket (annualised, per 1.00).
IV_LOWER: float = 1e-4
IV_UPPER: float = 5.0
#: Convergence controls.
PRICE_TOL: float = 1e-6
STEP_TOL: float = 1e-8
MAX_ITERS: int = 100
#: Vega below this magnitude is treated as unusable for a Newton step.
_VEGA_FLOOR: float = 1e-12


class IVResult(NamedTuple):
    """Diagnostics-rich solver result.

    ``sigma`` is ``None`` when the mid price is invalid or violates the
    no-arbitrage bounds (i.e. the strike should be INTERPOLATED by the caller).
    """

    sigma: Optional[float]
    iterations: int
    method: str   # "newton", "newton+bisection", or "none"
    converged: bool
    reason: str


def _bs_seed(mid_price: float, disc: float, F: float, T: float) -> float:
    """Brenner-Subrahmanyam ATM seed: sigma ~ sqrt(2*pi/T) * (undisc_mid / F)."""
    undisc = mid_price / disc
    return math.sqrt(2.0 * math.pi / T) * (undisc / F)


def solve_iv(
    option_type: OptionType,
    mid_price: Optional[float],
    F: float,
    K: float,
    T: float,
    r: float,
) -> IVResult:
    """Solve for Black-76 implied vol, returning full diagnostics.

    See :func:`implied_vol` for the thin (sigma-only) wrapper.
    """
    if option_type not in ("call", "put"):
        raise ValueError(
            f"option_type must be 'call' or 'put', got {option_type!r}"
        )

    # --- input / liquidity guards ---------------------------------------- #
    if mid_price is None:
        return IVResult(None, 0, "none", False, "mid_missing")
    if not math.isfinite(mid_price) or mid_price <= 0.0:
        return IVResult(None, 0, "none", False, "mid_nonpositive_or_nan")
    if not (F > 0.0 and K > 0.0):
        return IVResult(None, 0, "none", False, "nonpositive_F_or_K")
    if not (T > 0.0) or not math.isfinite(T):
        return IVResult(None, 0, "none", False, "nonpositive_T")
    if not math.isfinite(r):
        return IVResult(None, 0, "none", False, "nonfinite_r")

    # --- no-arbitrage bounds --------------------------------------------- #
    disc = math.exp(-r * T)
    if option_type == "call":
        lower, upper = disc * max(F - K, 0.0), disc * F
    else:
        lower, upper = disc * max(K - F, 0.0), disc * K
    if mid_price <= lower + PRICE_TOL:
        return IVResult(None, 0, "none", False, "mid_at_or_below_intrinsic")
    if mid_price >= upper - PRICE_TOL:
        return IVResult(None, 0, "none", False, "mid_at_or_above_upper_bound")

    def f(sigma: float) -> float:
        return price(option_type, F, K, T, r, sigma) - mid_price

    # --- ensure the root is bracketed by [IV_LOWER, IV_UPPER] ------------ #
    f_lo = f(IV_LOWER)
    f_hi = f(IV_UPPER)
    if f_lo > 0.0:
        return IVResult(None, 0, "none", False, "iv_below_bracket")
    if f_hi < 0.0:
        return IVResult(None, 0, "none", False, "iv_above_bracket")
    if abs(f_lo) < PRICE_TOL:
        return IVResult(IV_LOWER, 1, "newton", True, "price_tol")
    if abs(f_hi) < PRICE_TOL:
        return IVResult(IV_UPPER, 1, "newton", True, "price_tol")

    lo, hi = IV_LOWER, IV_UPPER   # invariant: f(lo) <= 0 <= f(hi)
    sigma = _bs_seed(mid_price, disc, F, T)
    if not (lo < sigma < hi):
        sigma = 0.5 * (lo + hi)

    method = "newton"
    iters = 0
    for i in range(1, MAX_ITERS + 1):
        iters = i
        diff = f(sigma)
        if abs(diff) < PRICE_TOL:
            return IVResult(sigma, iters, method, True, "price_tol")

        # tighten the bracket around the sign change
        if diff > 0.0:
            hi = sigma
        else:
            lo = sigma

        v = vega(F, K, T, r, sigma)
        use_bisection = (v <= _VEGA_FLOOR) or not math.isfinite(v)
        if not use_bisection:
            cand = sigma - diff / v
            if not math.isfinite(cand) or not (lo < cand < hi):
                use_bisection = True
        if use_bisection:
            cand = 0.5 * (lo + hi)
            method = "newton+bisection"

        step = abs(cand - sigma)
        sigma = cand
        if step < STEP_TOL:
            # negligible step: accept only if price is also within tolerance,
            # otherwise collapse to a bisection step and keep shrinking.
            if abs(f(sigma)) < PRICE_TOL:
                return IVResult(sigma, iters, method, True, "step_tol")
            sigma = 0.5 * (lo + hi)
            method = "newton+bisection"

    converged = abs(f(sigma)) < PRICE_TOL
    return IVResult(
        sigma if converged else None,
        MAX_ITERS,
        method,
        converged,
        "max_iters" if converged else "no_convergence",
    )


def implied_vol(
    option_type: OptionType,
    mid_price: Optional[float],
    F: float,
    K: float,
    T: float,
    r: float,
) -> Optional[float]:
    """Black-76 implied volatility from an option MID price.

    Returns the volatility (annualised, per 1.00) or ``None`` when the mid price
    is missing/invalid or violates the no-arbitrage bounds documented in the
    module docstring. Never raises for ordinary numeric inputs, so a thin /
    crossed quote simply yields ``None`` (the caller marks the strike for
    interpolation).
    """
    return solve_iv(option_type, mid_price, F, K, T, r).sigma


def is_iv_reliable(
    mid_price: Optional[float],
    *,
    bid: Optional[float] = None,
    ask: Optional[float] = None,
) -> bool:
    """Predicate: is this strike's quote good enough to trust a solved IV?

    Returns ``False`` (=> the caller in step 1.3 should INTERPOLATE the IV from
    liquid neighbours) when liquidity is thin, specifically when:
      * ``mid_price`` is missing (``None``), ``NaN``, or ``<= 0`` (no premium);
      * a two-sided quote is provided and it is **crossed** (``bid > ask``) or
        the ``ask`` is non-positive / either side is non-finite;
      * a one-sided quote is provided and that side is non-finite or, for the
        ask, non-positive (for the bid, negative).

    Returns ``True`` only when the mid is a finite positive premium and any
    supplied bid/ask form a sane (non-crossed) market. This is a cheap quote
    quality gate; the harder no-arbitrage check lives in :func:`implied_vol`,
    which also returns ``None`` for unsolvable mids.
    """
    if mid_price is None or not math.isfinite(mid_price) or mid_price <= 0.0:
        return False
    if bid is not None and ask is not None:
        if not (math.isfinite(bid) and math.isfinite(ask)):
            return False
        if bid < 0.0 or ask <= 0.0 or bid > ask:
            return False
    elif bid is not None:
        if not math.isfinite(bid) or bid < 0.0:
            return False
    elif ask is not None:
        if not math.isfinite(ask) or ask <= 0.0:
            return False
    return True
