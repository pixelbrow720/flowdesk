"""Black-76 model for European options on futures (FlowDesk pricing core).

Locked contract (PRD #0 / PRD #7):
  * Model: Black-76. Forward ``F`` = futures price (already a martingale under
    the risk-neutral measure), so the carry term that appears in
    Black-Scholes is absent from ``d1``/``d2``.
  * Discounting by ``exp(-r * T)`` where ``r = ln(1 + SOFR)`` (continuous).
  * ``d1 = (ln(F / K) + 0.5 * sigma**2 * T) / (sigma * sqrt(T))``
  * ``d2 = d1 - sigma * sqrt(T)``

All functions are PURE (no I/O, no globals mutated) and return well-defined
limits at the boundaries ``T -> 0`` and ``sigma -> 0`` (never ``NaN``/``inf``).

Units / conventions
-------------------
  * ``F``, ``K``        : index points (must be > 0).
  * ``T``               : year fraction to expiry.
  * ``r``               : continuous annual rate (``ln(1 + SOFR)``).
  * ``sigma``           : annualised volatility (per 1.00, i.e. 0.20 == 20%).
  * ``price``           : present value in index points (premium).
  * ``delta``           : d price / d F            (dimensionless).
  * ``gamma``           : d^2 price / d F^2         (per index point).
  * ``vega``            : d price / d sigma, per 1.00 of vol
                          (multiply by 0.01 for a per-1%-vol figure).
  * ``theta``           : d price / d t (calendar time) == -d price / d T,
                          in index points per year.

Only the standard library ``math`` is used (numpy is pinned for the wider
engine but is not required for scalar Black-76; this keeps the hot path exact
and allocation-free).
"""

from __future__ import annotations

import math
from typing import Literal

__all__ = [
    "OptionType",
    "norm_cdf",
    "norm_pdf",
    "d1_d2",
    "price",
    "delta",
    "gamma",
    "vega",
    "theta",
    "vanna",
    "charm",
]

#: Allowed option kinds.
OptionType = Literal["call", "put"]

_SQRT_2: float = math.sqrt(2.0)
_SQRT_2PI: float = math.sqrt(2.0 * math.pi)


# --------------------------------------------------------------------------- #
# Standard normal helpers
# --------------------------------------------------------------------------- #
def norm_cdf(x: float) -> float:
    """Standard normal CDF ``Phi(x)`` via the error function (exact, no tables)."""
    return 0.5 * (1.0 + math.erf(x / _SQRT_2))


def norm_pdf(x: float) -> float:
    """Standard normal PDF ``phi(x) = exp(-x^2 / 2) / sqrt(2*pi)``."""
    return math.exp(-0.5 * x * x) / _SQRT_2PI


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def _check_option_type(option_type: str) -> None:
    if option_type not in ("call", "put"):
        raise ValueError(
            f"option_type must be 'call' or 'put', got {option_type!r}"
        )


def _check_positive(name: str, value: float) -> None:
    if not (value > 0.0):
        raise ValueError(f"{name} must be > 0, got {value!r}")
    if math.isnan(value) or math.isinf(value):
        raise ValueError(f"{name} must be finite, got {value!r}")


# --------------------------------------------------------------------------- #
# d1 / d2
# --------------------------------------------------------------------------- #
def d1_d2(F: float, K: float, T: float, sigma: float) -> tuple[float, float]:
    """Return ``(d1, d2)`` for Black-76.

    ``r`` is intentionally absent: under Black-76 the forward is already the
    expected terminal value, so the rate only enters through discounting, not
    through ``d1``/``d2``.

    Requires ``T > 0`` and ``sigma > 0``; callers handle the degenerate limits
    separately (see :func:`price` et al.).
    """
    _check_positive("F", F)
    _check_positive("K", K)
    _check_positive("T", T)
    _check_positive("sigma", sigma)
    vol = sigma * math.sqrt(T)
    d1 = (math.log(F / K) + 0.5 * sigma * sigma * T) / vol
    d2 = d1 - vol
    return d1, d2


# --------------------------------------------------------------------------- #
# Internal degenerate-branch detection
# --------------------------------------------------------------------------- #
def _discount(r: float, T: float) -> float:
    """Discount factor; expired (``T <= 0``) contributes no discounting."""
    if T <= 0.0:
        return 1.0
    return math.exp(-r * T)


def _intrinsic(option_type: OptionType, F: float, K: float) -> float:
    if option_type == "call":
        return max(F - K, 0.0)
    return max(K - F, 0.0)


# --------------------------------------------------------------------------- #
# Price
# --------------------------------------------------------------------------- #
def price(
    option_type: OptionType,
    F: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
) -> float:
    """Black-76 present value of a European option on a future.

    Degenerate limits (well-defined, never NaN):
      * ``T <= 0`` (expired): discounted intrinsic with discount factor 1, i.e.
        ``max(F - K, 0)`` for a call, ``max(K - F, 0)`` for a put.
      * ``sigma <= 0`` with ``T > 0``: the forward is deterministic, so the
        value is ``exp(-r*T) * intrinsic``.
    """
    _check_option_type(option_type)
    _check_positive("F", F)
    _check_positive("K", K)

    disc = _discount(r, T)
    if T <= 0.0 or sigma <= 0.0:
        return disc * _intrinsic(option_type, F, K)

    d1, d2 = d1_d2(F, K, T, sigma)
    if option_type == "call":
        return disc * (F * norm_cdf(d1) - K * norm_cdf(d2))
    return disc * (K * norm_cdf(-d2) - F * norm_cdf(-d1))


# --------------------------------------------------------------------------- #
# Greeks
# --------------------------------------------------------------------------- #
def delta(
    option_type: OptionType,
    F: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
) -> float:
    """``d price / d F``.

    Degenerate limit (``T <= 0`` or ``sigma <= 0``): the discounted Heaviside
    step, with the at-the-money point assigned the sub-gradient midpoint
    (``+/- 0.5 * disc``) so the result is always finite.
    """
    _check_option_type(option_type)
    _check_positive("F", F)
    _check_positive("K", K)

    disc = _discount(r, T)
    if T <= 0.0 or sigma <= 0.0:
        if F == K:
            step = 0.5
        elif F > K:
            step = 1.0
        else:
            step = 0.0
        if option_type == "call":
            return disc * step
        return disc * (step - 1.0)

    d1, _ = d1_d2(F, K, T, sigma)
    if option_type == "call":
        return disc * norm_cdf(d1)
    return disc * (norm_cdf(d1) - 1.0)


def gamma(F: float, K: float, T: float, r: float, sigma: float) -> float:
    """``d^2 price / d F^2`` (identical for calls and puts).

    Degenerate limit (``T <= 0`` or ``sigma <= 0``): returns ``0.0``. The true
    limit is a Dirac spike at ``F == K`` and zero elsewhere; ``0.0`` is the
    finite, NaN-free representative used throughout the engine.
    """
    _check_positive("F", F)
    _check_positive("K", K)
    if T <= 0.0 or sigma <= 0.0:
        return 0.0
    disc = _discount(r, T)
    d1, _ = d1_d2(F, K, T, sigma)
    return disc * norm_pdf(d1) / (F * sigma * math.sqrt(T))


def vega(F: float, K: float, T: float, r: float, sigma: float) -> float:
    """``d price / d sigma`` per 1.00 of vol (identical for calls and puts).

    Degenerate limit (``T <= 0`` or ``sigma <= 0``): returns ``0.0``.
    Multiply by 0.01 to express sensitivity per 1 vol point.
    """
    _check_positive("F", F)
    _check_positive("K", K)
    if T <= 0.0 or sigma <= 0.0:
        return 0.0
    disc = _discount(r, T)
    d1, _ = d1_d2(F, K, T, sigma)
    return disc * F * norm_pdf(d1) * math.sqrt(T)


def theta(
    option_type: OptionType,
    F: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
) -> float:
    """``d price / d t`` (calendar time) == ``-d price / d T``, per year.

    Closed form (using the identity ``F * phi(d1) == K * phi(d2)``):

        theta = r * price - exp(-r*T) * F * phi(d1) * sigma / (2 * sqrt(T))

    The first term is the discounting carry on the premium; the second is the
    (always non-positive) time-decay of optionality. With ``r == 0`` the call
    and put thetas coincide.

    Degenerate limits (well-defined, never NaN):
      * ``T <= 0`` (expired): ``0.0``.
      * ``sigma <= 0`` with ``T > 0``: optionality decay vanishes, leaving
        ``r * price`` (the carry on discounted intrinsic).
    """
    _check_option_type(option_type)
    _check_positive("F", F)
    _check_positive("K", K)

    if T <= 0.0:
        return 0.0

    disc = math.exp(-r * T)
    if sigma <= 0.0:
        return r * disc * _intrinsic(option_type, F, K)

    d1, _ = d1_d2(F, K, T, sigma)
    decay = -disc * F * norm_pdf(d1) * sigma / (2.0 * math.sqrt(T))
    return r * price(option_type, F, K, T, r, sigma) + decay


def vanna(F: float, K: float, T: float, r: float, sigma: float) -> float:
    """``d delta / d sigma == d^2 price / (d F d sigma)`` (call == put).

    Closed form (using ``d d1 / d sigma == -d2 / sigma``):

        vanna = -exp(-r*T) * phi(d1) * d2 / sigma

    Per 1.00 of vol (multiply by 0.01 for a per-1%-vol figure), in units of
    delta per vol. Identical for calls and puts because the put delta differs
    from the call delta only by the sigma-independent ``-exp(-r*T)`` term.

    Degenerate limit (``T <= 0`` or ``sigma <= 0``): returns ``0.0`` (the finite,
    NaN-free representative, matching :func:`gamma` / :func:`vega`).
    """
    _check_positive("F", F)
    _check_positive("K", K)
    if T <= 0.0 or sigma <= 0.0:
        return 0.0
    disc = _discount(r, T)
    d1, d2 = d1_d2(F, K, T, sigma)
    return -disc * norm_pdf(d1) * d2 / sigma


def charm(
    option_type: OptionType,
    F: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
) -> float:
    """``d delta / d t`` (calendar time) ``== -d delta / d T``, per year.

    Closed form (using ``d d1 / d T == -d2 / (2 T)``):

        charm_call = exp(-r*T) * [ r*Phi(d1)       + phi(d1) * d2 / (2 T) ]
        charm_put  = exp(-r*T) * [ r*(Phi(d1) - 1) + phi(d1) * d2 / (2 T) ]

    so ``charm_call - charm_put == r * exp(-r*T)`` (delta parity differentiated).
    Sign convention mirrors :func:`theta`: ``+ d delta / d t`` as calendar time
    advances (i.e. as ``T`` shrinks toward expiry). Per year — multiply by a day
    fraction (e.g. ``1/365``) for a per-day figure.

    Degenerate limit (``T <= 0`` or ``sigma <= 0``): returns ``0.0``.
    """
    _check_option_type(option_type)
    _check_positive("F", F)
    _check_positive("K", K)
    if T <= 0.0 or sigma <= 0.0:
        return 0.0
    disc = _discount(r, T)
    d1, d2 = d1_d2(F, K, T, sigma)
    n_d1 = norm_cdf(d1) if option_type == "call" else norm_cdf(d1) - 1.0
    return disc * (r * n_d1 + norm_pdf(d1) * d2 / (2.0 * T))
