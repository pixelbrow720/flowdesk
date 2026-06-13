"""Unit tests for engine.total_hedging (#7 — gamma+charm+vanna on the Q base).

Strongest anchor: ``gamma_hedge`` MUST equal the #4 synthetic GEX at the same ``w``
(both apply Gamma to the SAME Q via the shared ``q_per_leg``). charm/vanna terms are
cross-checked against the black76 primitives. Thin strikes are skipped, never
fabricated. black76 vanna/charm correctness itself is covered by FD checks in
test_black76.py; here we verify the AGGREGATION + scaling + reduction property.
"""
from __future__ import annotations

import math

from engine.black76 import charm as bs_charm
from engine.black76 import vanna as bs_vanna
from engine.exposure import GEX_PCT_SCALE, ChainRow
from engine.exposure_ext import CHEX_DAY_SCALE, VEX_VOL_PT_SCALE
from engine.synthetic_oi import synthetic_gex
from engine.total_hedging import build_total_hedging, total_hedging

M = 50.0  # /ES multiplier
F = 5000.0
R = 0.04
T = 6.5 / (365.0 * 24.0)  # ~6.5h to the bell, year-fraction
IV_C = 0.20
IV_P = 0.22


def _row(strike, *, cvol=0.0, pvol=0.0, coi=0.0, poi=0.0,
         cg=0.0, pg=0.0, iv_c=IV_C, iv_p=IV_P, t=T, thin=False):
    return ChainRow(
        strike=strike, call_gamma=cg, put_gamma=pg, call_delta=0.0, put_delta=0.0,
        call_vol=cvol, put_vol=pvol, call_oi=coi, put_oi=poi, thin=thin,
        call_iv=(None if thin else iv_c), put_iv=(None if thin else iv_p),
        t_expiry=(None if thin else t),
    )


def test_gamma_hedge_equals_synthetic_gex_reduction() -> None:
    # THE anchor: total_hedging's gamma term must be byte-identical to synthetic_oi
    # #4's GEX at the same w — both weight Gamma by the same Q.
    rows = [
        _row(4990.0, coi=800.0, poi=300.0, cg=0.010, pg=0.011),
        _row(5000.0, coi=1200.0, poi=1100.0, cg=0.013, pg=0.013),
        _row(5010.0, coi=400.0, poi=900.0, cg=0.009, pg=0.012),
    ]
    flow = {(5000.0, True): 250.0, (5000.0, False): -120.0, (4990.0, True): 80.0}
    for w in (0.0, 0.5, 1.0):
        g, _c, _v = total_hedging(rows, flow, M, F, R, w)
        assert math.isclose(g, synthetic_gex(rows, flow, M, F, w), rel_tol=1e-12)


def test_charm_vanna_terms_match_primitives() -> None:
    rows = [
        _row(4990.0, coi=800.0, poi=300.0, cg=0.010, pg=0.011),
        _row(5000.0, coi=1200.0, poi=1100.0, cg=0.013, pg=0.013),
    ]
    flow = {(5000.0, True): 250.0, (5000.0, False): -120.0}
    w = 1.0
    from engine.synthetic_oi import q_per_leg
    c_exp = v_exp = 0.0
    for r in rows:
        qc, qp = q_per_leg(r, flow, w)
        c_exp += (bs_charm("call", F, r.strike, r.t_expiry, R, r.call_iv) * qc
                  + bs_charm("put", F, r.strike, r.t_expiry, R, r.put_iv) * qp)
        v_exp += (bs_vanna(F, r.strike, r.t_expiry, R, r.call_iv) * qc
                  + bs_vanna(F, r.strike, r.t_expiry, R, r.put_iv) * qp)
    c_exp *= M * F * CHEX_DAY_SCALE
    v_exp *= M * F * VEX_VOL_PT_SCALE
    _g, c, v = total_hedging(rows, flow, M, F, R, w)
    assert math.isclose(c, c_exp, rel_tol=1e-12)
    assert math.isclose(v, v_exp, rel_tol=1e-12)


def test_thin_strike_skipped_all_three_terms() -> None:
    # Thin strike with huge OI must contribute ZERO to every term.
    thin = [_row(5000.0, coi=1e6, poi=1e6, cg=0.05, pg=0.05, thin=True)]
    assert total_hedging(thin, {}, M, F, R, 1.0) == (0.0, 0.0, 0.0)
    # mixed: thin + solved -> only the solved leg counts (all three terms)
    mixed = [
        _row(5000.0, coi=1e6, poi=1e6, cg=0.05, pg=0.05, thin=True),
        _row(5010.0, coi=400.0, poi=300.0, cg=0.009, pg=0.010),
    ]
    only = total_hedging([mixed[1]], {}, M, F, R, 0.0)
    got = total_hedging(mixed, {}, M, F, R, 0.0)
    for a, b in zip(got, only):
        assert math.isclose(a, b, rel_tol=1e-12)


def test_gamma_scale_constant_matches_locked() -> None:
    # gamma term uses the locked GEX scale (M*F^2*0.01), proving it's GEX-on-Q.
    rows = [_row(5000.0, coi=1000.0, poi=0.0, cg=0.02, pg=0.0)]
    g, _c, _v = total_hedging(rows, {}, M, F, R, 0.0)
    # Q_call = +1*1000; gamma term = 0.02*1000 * M*F^2*0.01
    expected = 0.02 * 1000.0 * M * F * F * GEX_PCT_SCALE
    assert math.isclose(g, expected, rel_tol=1e-12)


def test_build_keys_and_w_validation() -> None:
    rows = [_row(5000.0, coi=1000.0, poi=500.0, cg=0.01, pg=0.01)]
    snap = build_total_hedging(rows, {}, M, F, R, w=0.5)
    assert set(snap.to_dict()) == {"gamma_hedge", "charm_hedge", "vanna_hedge", "w"}
    assert snap.w == 0.5
    for bad in (-0.1, 1.5):
        try:
            build_total_hedging(rows, {}, M, F, R, w=bad)
            assert False, f"w={bad} should have raised"
        except ValueError:
            pass
