"""Unit tests for engine.iv (PRD #12, acceptance T-02 & T-03).

T-02: price -> iv -> price round-trips within 1e-6 across a grid.
T-03: thin-liquidity quotes return None / flag without crashing;
      typical inputs converge in < 50 iterations.
"""

from __future__ import annotations

import math

import pytest

from engine.black76 import price
from engine.iv import (
    IV_LOWER,
    IV_UPPER,
    PRICE_TOL,
    implied_vol,
    is_iv_reliable,
    solve_iv,
)

ABS = 1e-6


def _bounds(option_type: str, F: float, K: float, T: float, r: float):
    disc = math.exp(-r * T)
    if option_type == "call":
        return disc * max(F - K, 0.0), disc * F
    return disc * max(K - F, 0.0), disc * K


# Grid spanning index scale (/ES, /NQ), moneyness, tenor, rate and vol.
_FS = [100.0, 4500.0, 15800.0]
_MONEYNESS = [0.90, 0.95, 1.00, 1.05, 1.10]
_TENORS = [1.0 / 252.0, 0.05, 0.25, 1.0]
_RATES = [0.0, 0.045]
_VOLS = [0.08, 0.20, 0.50, 1.00]
_TYPES = ["call", "put"]


def _grid():
    for ot in _TYPES:
        for F in _FS:
            for m in _MONEYNESS:
                K = F * m
                for T in _TENORS:
                    for r in _RATES:
                        for sigma in _VOLS:
                            yield ot, F, K, T, r, sigma


# --------------------------------------------------------------------------- #
# T-02: round trip
# --------------------------------------------------------------------------- #
def test_round_trip_grid() -> None:
    solved = 0
    skipped = 0
    for ot, F, K, T, r, sigma in _grid():
        mid = price(ot, F, K, T, r, sigma)
        lower, upper = _bounds(ot, F, K, T, r)
        # Skip mids that are legitimately unsolvable inside the [1e-4, 5.0]
        # bracket (too close to intrinsic / upper bound -> caller interpolates).
        if mid <= lower + PRICE_TOL or mid >= upper - PRICE_TOL:
            skipped += 1
            continue
        iv = implied_vol(ot, mid, F, K, T, r)
        assert iv is not None, (ot, F, K, T, r, sigma, mid)
        assert IV_LOWER <= iv <= IV_UPPER
        recon = price(ot, F, K, T, r, iv)
        assert abs(recon - mid) < ABS, (ot, F, K, T, r, sigma, mid, iv, recon)
        solved += 1
    # The vast majority of the grid must be solvable.
    assert solved > 800, (solved, skipped)


def test_round_trip_recovers_sigma_atm() -> None:
    # Well-conditioned ATM cases recover the true sigma tightly.
    for F in _FS:
        for r in _RATES:
            for sigma in _VOLS:
                ot, K, T = "call", F, 0.25
                mid = price(ot, F, K, T, r, sigma)
                iv = implied_vol(ot, mid, F, K, T, r)
                assert iv is not None
                assert abs(iv - sigma) < 1e-6


def test_call_put_same_iv() -> None:
    # Call and put at the same strike imply (numerically) the same vol.
    F, K, T, r, sigma = 4500.0, 4550.0, 0.10, 0.045, 0.30
    c = price("call", F, K, T, r, sigma)
    p = price("put", F, K, T, r, sigma)
    iv_c = implied_vol("call", c, F, K, T, r)
    iv_p = implied_vol("put", p, F, K, T, r)
    assert iv_c is not None and iv_p is not None
    assert abs(iv_c - iv_p) < 1e-6
    assert abs(iv_c - sigma) < 1e-6


# --------------------------------------------------------------------------- #
# T-03: convergence speed on normal inputs
# --------------------------------------------------------------------------- #
def test_convergence_under_50_iters() -> None:
    worst = 0
    for ot in _TYPES:
        for F in [100.0, 4500.0, 15800.0]:
            for m in [0.95, 1.0, 1.05]:
                K = F * m
                for T in [0.05, 0.25, 1.0]:
                    for sigma in [0.15, 0.30, 0.60]:
                        r = 0.045
                        mid = price(ot, F, K, T, r, sigma)
                        res = solve_iv(ot, mid, F, K, T, r)
                        assert res.sigma is not None and res.converged
                        assert res.iterations < 50, (ot, F, K, T, sigma, res)
                        worst = max(worst, res.iterations)
    # Newton dominates: typical worst case is single digits.
    assert worst < 50


def test_even_extreme_inputs_bounded_iters() -> None:
    # Deep ITM/OTM and very short tenor still finish within the 100 budget.
    for ot in _TYPES:
        for m in [0.80, 1.20]:
            F, K = 15800.0, 15800.0 * m
            T, r, sigma = 1.0 / 252.0, 0.045, 0.45
            mid = price(ot, F, K, T, r, sigma)
            res = solve_iv(ot, mid, F, K, T, r)
            if res.sigma is not None:
                assert res.iterations <= 100
                assert abs(price(ot, F, K, T, r, res.sigma) - mid) < ABS


# --------------------------------------------------------------------------- #
# T-03: thin liquidity / arbitrage -> None, no crash
# --------------------------------------------------------------------------- #
def test_thin_liquidity_returns_none() -> None:
    F, K, T, r = 100.0, 100.0, 0.25, 0.045
    assert implied_vol("call", None, F, K, T, r) is None      # missing
    assert implied_vol("call", 0.0, F, K, T, r) is None       # zero
    assert implied_vol("call", -1.0, F, K, T, r) is None      # negative
    assert implied_vol("call", float("nan"), F, K, T, r) is None
    assert implied_vol("call", float("inf"), F, K, T, r) is None


def test_arbitrage_bounds_return_none() -> None:
    F, T, r = 100.0, 1.0, 0.0
    # Call below intrinsic (F=100, K=90 -> intrinsic 10) is arbitrage.
    assert implied_vol("call", 5.0, F, 90.0, T, r) is None
    # Call above the discounted forward (upper bound = F = 100).
    assert implied_vol("call", 150.0, F, 100.0, T, r) is None
    # Put above the discounted strike (upper bound = K = 110).
    assert implied_vol("put", 150.0, F, 110.0, T, r) is None
    # Put below intrinsic (K=120, F=100 -> intrinsic 20).
    assert implied_vol("put", 5.0, F, 120.0, T, r) is None


def test_degenerate_inputs_do_not_crash() -> None:
    for T in [0.0, -1.0]:
        assert implied_vol("call", 5.0, 100.0, 100.0, T, 0.045) is None
    assert implied_vol("call", 5.0, 0.0, 100.0, 1.0, 0.045) is None   # F<=0
    assert implied_vol("call", 5.0, 100.0, 0.0, 1.0, 0.045) is None   # K<=0
    assert implied_vol("call", 5.0, 100.0, 100.0, 1.0, float("nan")) is None
    with pytest.raises(ValueError):
        implied_vol("forward", 5.0, 100.0, 100.0, 1.0, 0.045)         # bad type


def test_is_iv_reliable_predicate() -> None:
    # Good quotes
    assert is_iv_reliable(5.0) is True
    assert is_iv_reliable(5.0, bid=4.5, ask=5.5) is True
    assert is_iv_reliable(5.0, bid=5.0, ask=5.0) is True   # locked but not crossed
    # Thin / bad quotes -> interpolate
    assert is_iv_reliable(None) is False                   # missing
    assert is_iv_reliable(0.0) is False                    # zero
    assert is_iv_reliable(-2.0) is False                   # negative
    assert is_iv_reliable(float("nan")) is False
    assert is_iv_reliable(5.0, bid=6.0, ask=5.0) is False  # crossed
    assert is_iv_reliable(5.0, ask=0.0) is False           # no offer
    assert is_iv_reliable(5.0, bid=-1.0, ask=5.5) is False # bad bid
    assert is_iv_reliable(5.0, bid=float("inf")) is False


def test_reliable_quote_solves() -> None:
    # Integration: a reliable mid both passes the predicate and solves.
    F, K, T, r, sigma = 4500.0, 4500.0, 0.05, 0.045, 0.22
    mid = price("call", F, K, T, r, sigma)
    assert is_iv_reliable(mid, bid=mid - 0.5, ask=mid + 0.5) is True
    iv = implied_vol("call", mid, F, K, T, r)
    assert iv is not None and abs(iv - sigma) < 1e-6
