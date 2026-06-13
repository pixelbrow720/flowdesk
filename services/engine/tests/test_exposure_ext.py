"""Unit tests for engine.exposure_ext (VEX / CHEX, VOL-based, EXPERIMENTAL).

Verifies the aggregation, the locked dealer signs, the two scale constants
(VEX = vol-point M*F*0.01, CHEX = per-day M*F/365), and the red-team-mandated
THIN-strike skip (greeks unsolved upstream must contribute zero, never fabricated).
black76.vanna/charm correctness itself is covered by finite-difference checks in
test_black76.py; here we cross-check the AGGREGATION against those primitives.
"""
from __future__ import annotations

import math

from engine.black76 import charm as bs_charm
from engine.black76 import vanna as bs_vanna
from engine.exposure import DEALER_SIGN_CALL, DEALER_SIGN_PUT, ChainRow
from engine.exposure_ext import (
    CHEX_DAY_SCALE,
    VEX_VOL_PT_SCALE,
    build_exposure_ext,
    net_vex_chex,
)

M = 50.0  # /ES multiplier
F = 5000.0
R = 0.04
T = 6.5 / (365.0 * 24.0)  # ~6.5h to the bell, year-fraction
IV_C = 0.20
IV_P = 0.22


def _row(strike, *, cvol, pvol, iv_c=IV_C, iv_p=IV_P, t=T, thin=False):
    return ChainRow(
        strike=strike, call_gamma=0.0, put_gamma=0.0, call_delta=0.0, put_delta=0.0,
        call_vol=cvol, put_vol=pvol, thin=thin,
        call_iv=(None if thin else iv_c), put_iv=(None if thin else iv_p),
        t_expiry=(None if thin else t),
    )


def _expected(rows):
    """Reference aggregation straight from the black76 primitives."""
    vex = chex = 0.0
    for r in rows:
        if r.thin or r.call_iv is None or r.put_iv is None or r.t_expiry is None:
            continue
        v_c = bs_vanna(F, r.strike, r.t_expiry, R, r.call_iv)
        v_p = bs_vanna(F, r.strike, r.t_expiry, R, r.put_iv)
        ch_c = bs_charm("call", F, r.strike, r.t_expiry, R, r.call_iv)
        ch_p = bs_charm("put", F, r.strike, r.t_expiry, R, r.put_iv)
        vex += DEALER_SIGN_CALL * v_c * r.call_vol + DEALER_SIGN_PUT * v_p * r.put_vol
        chex += DEALER_SIGN_CALL * ch_c * r.call_vol + DEALER_SIGN_PUT * ch_p * r.put_vol
    return vex * M * F * VEX_VOL_PT_SCALE, chex * M * F * CHEX_DAY_SCALE


def test_scale_constants_locked() -> None:
    assert VEX_VOL_PT_SCALE == 0.01           # vol-point (per 1% IV), NOT price-move
    assert math.isclose(CHEX_DAY_SCALE, 1.0 / 365.0, rel_tol=1e-12)  # per calendar day


def test_aggregation_matches_black76_primitives() -> None:
    rows = [
        _row(4990.0, cvol=300.0, pvol=120.0),
        _row(5000.0, cvol=800.0, pvol=600.0),
        _row(5010.0, cvol=150.0, pvol=900.0),
    ]
    vex, chex = net_vex_chex(rows, M, F, R)
    exp_vex, exp_chex = _expected(rows)
    assert math.isclose(vex, exp_vex, rel_tol=1e-12)
    assert math.isclose(chex, exp_chex, rel_tol=1e-12)


def test_thin_or_unsolved_strike_skipped() -> None:
    # Thin strike with huge volume must contribute ZERO (greeks unsolved upstream).
    rows = [_row(5000.0, cvol=1e6, pvol=1e6, thin=True)]
    vex, chex = net_vex_chex(rows, M, F, R)
    assert vex == 0.0 and chex == 0.0
    # mixed: thin + solved -> only the solved leg counts
    mixed = [
        _row(5000.0, cvol=1e6, pvol=1e6, thin=True),
        _row(5010.0, cvol=200.0, pvol=200.0),
    ]
    only_solved = net_vex_chex([mixed[1]], M, F, R)
    got = net_vex_chex(mixed, M, F, R)
    assert math.isclose(got[0], only_solved[0], rel_tol=1e-12)
    assert math.isclose(got[1], only_solved[1], rel_tol=1e-12)


def test_zero_volume_yields_zero() -> None:
    rows = [_row(5000.0, cvol=0.0, pvol=0.0)]
    assert net_vex_chex(rows, M, F, R) == (0.0, 0.0)


def test_build_aggregate_signs_and_keys() -> None:
    rows = [
        _row(4990.0, cvol=300.0, pvol=120.0),
        _row(5000.0, cvol=800.0, pvol=600.0),
    ]
    snap = build_exposure_ext(rows, M, F, R)
    exp_vex, exp_chex = _expected(rows)
    assert math.isclose(snap.net_vex, exp_vex, rel_tol=1e-12)
    assert math.isclose(snap.net_chex, exp_chex, rel_tol=1e-12)
    assert snap.vex_sign == (1 if exp_vex > 0 else (-1 if exp_vex < 0 else 0))
    assert snap.chex_sign == (1 if exp_chex > 0 else (-1 if exp_chex < 0 else 0))
    assert set(snap.to_dict()) == {"net_vex", "vex_sign", "net_chex", "chex_sign"}
