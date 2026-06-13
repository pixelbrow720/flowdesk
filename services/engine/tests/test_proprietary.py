"""Unit tests for engine.proprietary (reverse-engineered SpotGamma-style levels).

These are INFERRED approximations (NOT official SpotGamma). The tests pin the math
of the inference: the cumulative OI-gamma zero-crossing (volatility trigger), the
total/net OI-gamma argmax strikes (absolute gamma / hedge wall), the locked dealer
signs, and the THIN-strike skip (gamma unsolved -> excluded, never fabricated).
"""
from __future__ import annotations

import math

from engine.exposure import ChainRow
from engine.proprietary import (
    absolute_gamma_strike,
    build_proprietary,
    hedge_wall,
    net_oi_gamma_profile,
    volatility_trigger,
)


def _row(strike, cg, pg, coi, poi, thin=False):
    return ChainRow(
        strike=strike, call_gamma=cg, put_gamma=pg, call_delta=0.0, put_delta=0.0,
        call_vol=0.0, put_vol=0.0, call_oi=coi, put_oi=poi, thin=thin,
    )


def test_net_oi_gamma_profile_signs_and_skip() -> None:
    # net = +call_gamma*call_oi - put_gamma*put_oi (locked dealer signs).
    rows = [
        _row(100.0, cg=0.01, pg=0.02, coi=1000.0, poi=500.0),   # +10 - 10 = 0
        _row(105.0, cg=0.01, pg=0.00, coi=2000.0, poi=0.0),     # +20
        _row(110.0, cg=0.00, pg=0.05, coi=0.0, poi=400.0, thin=True),  # skipped
    ]
    prof = net_oi_gamma_profile(rows)
    assert [k for k, _ in prof] == [100.0, 105.0]  # thin 110 excluded
    assert math.isclose(prof[0][1], 0.0, abs_tol=1e-12)
    assert math.isclose(prof[1][1], 20.0, rel_tol=1e-12)


def test_volatility_trigger_zero_crossing_interpolated() -> None:
    # cumulative net OI-gamma: put-heavy low strikes (negative) -> call-heavy high.
    rows = [
        _row(100.0, cg=0.0, pg=0.01, coi=0.0, poi=1000.0),   # net -10, cum -10
        _row(110.0, cg=0.01, pg=0.0, coi=2000.0, poi=0.0),   # net +20, cum +10
    ]
    # crossing between 100 (cum -10) and 110 (cum +10): frac = 10/20 = 0.5 -> 105
    vt = volatility_trigger(rows)
    assert vt is not None and math.isclose(vt, 105.0, rel_tol=1e-9)


def test_volatility_trigger_none_when_no_cross() -> None:
    # all net positive -> cumulative never crosses zero.
    rows = [
        _row(100.0, cg=0.01, pg=0.0, coi=1000.0, poi=0.0),
        _row(105.0, cg=0.01, pg=0.0, coi=2000.0, poi=0.0),
    ]
    assert volatility_trigger(rows) is None
    assert volatility_trigger([rows[0]]) is None  # <2 points


def test_absolute_gamma_strike_max_total() -> None:
    rows = [
        _row(100.0, cg=0.01, pg=0.01, coi=1000.0, poi=1000.0),  # |10|+|10| = 20
        _row(105.0, cg=0.02, pg=0.0, coi=2000.0, poi=0.0),      # |40|+0   = 40
        _row(110.0, cg=0.0, pg=0.01, coi=0.0, poi=500.0),       # 0+|5|    = 5
    ]
    assert absolute_gamma_strike(rows) == 105.0


def test_hedge_wall_max_abs_net() -> None:
    rows = [
        _row(100.0, cg=0.01, pg=0.01, coi=1000.0, poi=1000.0),  # net 0
        _row(105.0, cg=0.0, pg=0.03, coi=0.0, poi=1000.0),      # net -30 -> |30|
        _row(110.0, cg=0.01, pg=0.0, coi=1500.0, poi=0.0),      # net +15
    ]
    assert hedge_wall(rows) == 105.0


def test_thin_strikes_excluded_everywhere() -> None:
    rows = [_row(100.0, cg=0.9, pg=0.9, coi=1e6, poi=1e6, thin=True)]
    assert net_oi_gamma_profile(rows) == []
    assert volatility_trigger(rows) is None
    assert absolute_gamma_strike(rows) is None
    assert hedge_wall(rows) is None


def test_build_proprietary_keys() -> None:
    rows = [
        _row(100.0, cg=0.0, pg=0.01, coi=0.0, poi=1000.0),
        _row(110.0, cg=0.01, pg=0.0, coi=2000.0, poi=0.0),
    ]
    snap = build_proprietary(rows)
    assert set(snap.to_dict()) == {"volatility_trigger", "abs_gamma_strike", "hedge_wall"}
    assert snap.volatility_trigger is not None
