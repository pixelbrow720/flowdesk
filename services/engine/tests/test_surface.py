"""Tests for the isolated vol-surface module (SVI slice + expected move).

The module is additive and does NOT touch the Snapshot contract; these tests
prove the SVI fit recovers a known smile, the no-butterfly guard behaves, and
the two expected-move estimators agree with their closed forms.
"""
from __future__ import annotations

import math

from engine.surface import (
    STRADDLE_EM_FACTOR,
    SVIParams,
    expected_move,
    expected_move_from_straddle,
    fit_svi,
    is_butterfly_arbitrage_free,
    svi_vol,
    total_variance,
)

FORWARD = 5000.0
T = 6.5 / (365.0 * 24.0)  # ~6.5h to settlement, a 0DTE afternoon slice


def _truth() -> SVIParams:
    # A typical equity put-skew smile (negative rho), comfortably arb-free.
    return SVIParams(a=0.0008, b=0.04, rho=-0.4, m=0.0, sigma=0.05)


def test_total_variance_and_vol_roundtrip() -> None:
    p = _truth()
    w = total_variance(p, 0.0)
    assert w > 0.0
    assert math.isclose(svi_vol(p, 0.0, T), math.sqrt(w / T), rel_tol=1e-12)


def test_svi_vol_zero_when_variance_nonpositive() -> None:
    # a very negative => w(k) < 0 at the floor; vol clamps to 0 (no NaN).
    p = SVIParams(a=-1.0, b=0.0, rho=0.0, m=0.0, sigma=0.1)
    assert svi_vol(p, 0.0, T) == 0.0


def test_fit_recovers_known_smile() -> None:
    p = _truth()
    strikes = [4900.0, 4950.0, 4975.0, 5000.0, 5025.0, 5050.0, 5100.0]
    vols = [svi_vol(p, math.log(K / FORWARD), T) for K in strikes]

    sl = fit_svi(strikes, vols, FORWARD, T)
    # Fit reproduces every input vol to sub-0.1-vol-point accuracy.
    assert sl.rmse < 1e-3
    for K, v in zip(strikes, vols):
        got = svi_vol(sl.params, math.log(K / FORWARD), T)
        assert abs(got - v) < 2e-3
    assert sl.arb_free
    assert sl.atm_vol > 0.0


def test_fit_exposes_skew_sign() -> None:
    p = _truth()  # rho < 0 => downside vol higher than upside
    strikes = [4900.0, 4950.0, 5000.0, 5050.0, 5100.0]
    vols = [svi_vol(p, math.log(K / FORWARD), T) for K in strikes]
    sl = fit_svi(strikes, vols, FORWARD, T)
    down = svi_vol(sl.params, math.log(4900.0 / FORWARD), T)
    up = svi_vol(sl.params, math.log(5100.0 / FORWARD), T)
    assert down > up


def test_fit_requires_five_strikes() -> None:
    try:
        fit_svi([1.0, 2.0, 3.0, 4.0], [0.2, 0.2, 0.2, 0.2], FORWARD, T)
    except ValueError:
        return
    raise AssertionError("fit_svi should require >= 5 strikes")


def test_butterfly_guard() -> None:
    assert is_butterfly_arbitrage_free(_truth())
    assert not is_butterfly_arbitrage_free(SVIParams(0.0, -1.0, 0.0, 0.0, 0.1))  # b<0
    assert not is_butterfly_arbitrage_free(SVIParams(0.0, 0.04, 1.5, 0.0, 0.1))  # |rho|>1
    assert not is_butterfly_arbitrage_free(SVIParams(0.0, 0.04, 0.0, 0.0, 0.0))  # sigma<=0
    # negative variance floor (a too negative for the wing)
    assert not is_butterfly_arbitrage_free(SVIParams(-1.0, 0.04, 0.0, 0.0, 0.1))


def test_expected_move_lognormal() -> None:
    em = expected_move(FORWARD, 0.20, T)
    assert math.isclose(em, FORWARD * 0.20 * math.sqrt(T), rel_tol=1e-12)
    assert em > 0.0


def test_expected_move_from_straddle() -> None:
    assert math.isclose(expected_move_from_straddle(40.0), 0.85 * 40.0, rel_tol=1e-12)
    assert math.isclose(
        expected_move_from_straddle(40.0, factor=1.0), 40.0, rel_tol=1e-12
    )
    assert STRADDLE_EM_FACTOR == 0.85


def test_expected_move_estimators_relationship() -> None:
    # The two estimators measure different things, by convention:
    #   * expected_move      = 1-sigma lognormal move  = F*sigma*sqrt(T).
    #   * 0.85 * ATM straddle. The Black-76 ATM straddle is
    #       2*phi(0)*F*sigma*sqrt(T) = sqrt(2/pi)*F*sigma*sqrt(T) ~= 0.798*(...),
    #     i.e. the expected ABSOLUTE move; scaling by 0.85 gives ~0.68*(1-sigma).
    # So the straddle EM should sit at ~0.6-0.75 of the lognormal 1-sigma EM.
    sigma = 0.20
    em_log = expected_move(FORWARD, sigma, T)
    straddle = math.sqrt(2.0 / math.pi) * FORWARD * sigma * math.sqrt(T)
    em_str = expected_move_from_straddle(straddle)
    ratio = em_str / em_log
    assert 0.6 < ratio < 0.75
    expected_ratio = STRADDLE_EM_FACTOR * math.sqrt(2.0 / math.pi)
    assert math.isclose(ratio, expected_ratio, rel_tol=1e-9)
