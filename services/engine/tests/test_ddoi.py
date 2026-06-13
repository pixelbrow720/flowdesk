"""Unit tests for engine.ddoi (synthetic Dealer Directional OI GEX, EXPERIMENTAL).

Verifies the intraday open/close time weight, the locked dealer-sign + gamma + scale
application on the synthetic-ΔOI basis, and the red-team-mandated THIN-strike skip
(gamma unsolved -> zero contribution, never fabricated). The open/close classifier
itself is a heuristic carried from the validated analysis/ddoi.py.
"""
from __future__ import annotations

import math

from engine.ddoi import build_ddoi, ddoi_gex, ddoi_time_weight
from engine.exposure import ChainRow, GEX_PCT_SCALE

M = 50.0  # /ES multiplier
F = 100.0
SCALE = M * F * F * GEX_PCT_SCALE  # 5000.0


def _row(strike, cg, pg, thin=False):
    return ChainRow(
        strike=strike, call_gamma=cg, put_gamma=pg, call_delta=0.0, put_delta=0.0,
        call_vol=0.0, put_vol=0.0, thin=thin,
    )


def test_time_weight_first_open_last_close() -> None:
    # +1 for the first of n, -1 for the last, 0 at the midpoint.
    assert ddoi_time_weight(0, 5) == 1.0
    assert ddoi_time_weight(4, 5) == -1.0
    assert math.isclose(ddoi_time_weight(2, 5), 0.0, abs_tol=1e-12)
    # single trade -> opening
    assert ddoi_time_weight(0, 1) == 1.0
    # monotone decreasing across the day
    ws = [ddoi_time_weight(i, 6) for i in range(6)]
    assert all(ws[i] > ws[i + 1] for i in range(len(ws) - 1))


def test_ddoi_gex_applies_locked_signs_and_scale() -> None:
    # one strike, ddoi_call=+800 (net opening), ddoi_put=-300 (net closing).
    rows = [_row(100.0, cg=0.01, pg=0.02)]
    flow = {(100.0, True): 800.0, (100.0, False): -300.0}
    # (+1*0.01*800 + -1*0.02*(-300)) * 5000 = (8 + 6)*5000 = 70000
    assert math.isclose(ddoi_gex(rows, flow, M, F), 70000.0, rel_tol=1e-9)


def test_ddoi_thin_strike_skipped() -> None:
    rows = [_row(100.0, cg=0.05, pg=0.05, thin=True)]
    flow = {(100.0, True): 9999.0, (100.0, False): 9999.0}
    assert ddoi_gex(rows, flow, M, F) == 0.0
    # mixed: only the solved strike contributes
    rows2 = [
        _row(100.0, cg=0.05, pg=0.05, thin=True),
        _row(105.0, cg=0.01, pg=0.01),
    ]
    flow2 = {(105.0, True): 100.0, (105.0, False): -50.0}
    only = ddoi_gex([rows2[1]], flow2, M, F)
    assert math.isclose(ddoi_gex(rows2, flow2, M, F), only, rel_tol=1e-9)


def test_ddoi_empty_flow_is_zero() -> None:
    rows = [_row(100.0, cg=0.01, pg=0.01)]
    assert ddoi_gex(rows, {}, M, F) == 0.0


def test_build_ddoi_sign_and_keys() -> None:
    rows = [_row(100.0, cg=0.01, pg=0.02)]
    flow = {(100.0, True): 800.0, (100.0, False): -300.0}
    snap = build_ddoi(rows, flow, M, F)
    assert math.isclose(snap.gex, 70000.0, rel_tol=1e-9)
    assert snap.sign == 1
    assert set(snap.to_dict()) == {"gex", "sign"}
    # negative basis flips the sign
    neg = build_ddoi([_row(100.0, cg=0.01, pg=0.0)], {(100.0, True): -500.0}, M, F)
    assert neg.sign == -1
