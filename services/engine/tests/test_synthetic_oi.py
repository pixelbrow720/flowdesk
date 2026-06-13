"""Unit tests for engine.synthetic_oi (#4 hybrid OI-anchored + flow-update).

Verifies the formula at w=0 (pure OI) and w=1 (flow-updated), and the locked
red-team decision: THIN strikes are SKIPPED (gamma unsolved upstream -> they must
contribute zero synthetic-GEX even when they carry real OI), matching the
validated analysis/synthetic_oi_v4.py rather than the VOL profile's interpolation.
"""
from __future__ import annotations

import math

from engine.exposure import ChainRow, GEX_PCT_SCALE
from engine.synthetic_oi import build_synthetic_oi, synthetic_gex

M = 50.0  # /ES multiplier
F = 100.0
SCALE = M * F * F * GEX_PCT_SCALE  # 5000.0


def _row(strike, cg, pg, coi, poi, thin=False):
    return ChainRow(
        strike=strike, call_gamma=cg, put_gamma=pg, call_delta=0.0, put_delta=0.0,
        call_vol=0.0, put_vol=0.0, call_oi=coi, put_oi=poi, thin=thin,
    )


def test_pure_oi_w0_uses_static_dealer_sign() -> None:
    # w=0 -> Q = +1*call_oi / -1*put_oi (no flow term). gex_static must match.
    rows = [_row(100.0, cg=0.01, pg=0.01, coi=1000.0, poi=500.0)]
    gex0 = synthetic_gex(rows, {}, M, F, 0.0)
    # (0.01*(+1*1000) + 0.01*(-1*500)) * 5000 = (10 - 5)*5000 = 25000
    assert math.isclose(gex0, 25000.0, rel_tol=1e-9)


def test_flow_update_w1_shifts_position() -> None:
    rows = [_row(100.0, cg=0.01, pg=0.01, coi=1000.0, poi=500.0)]
    flow = {(100.0, True): 200.0, (100.0, False): -100.0}  # net aggressor flow
    gex1 = synthetic_gex(rows, flow, M, F, 1.0)
    # q_call = 1000 + (-200) = 800 ; q_put = -500 + (-(-100)) = -400
    # (0.01*800 + 0.01*(-400))*5000 = (8 - 4)*5000 = 20000
    assert math.isclose(gex1, 20000.0, rel_tol=1e-9)


def test_thin_strike_is_skipped_even_with_real_oi() -> None:
    # A thin strike (gamma unsolved upstream) with LARGE OI must contribute ZERO,
    # not a fabricated number. This is the red-team-mandated behavior.
    rows = [_row(100.0, cg=0.05, pg=0.05, coi=99999.0, poi=99999.0, thin=True)]
    flow = {(100.0, True): 5000.0, (100.0, False): 5000.0}
    assert synthetic_gex(rows, flow, M, F, 1.0) == 0.0
    # mixed: one thin + one solved -> only the solved one counts
    rows2 = [
        _row(100.0, cg=0.05, pg=0.05, coi=99999.0, poi=99999.0, thin=True),
        _row(105.0, cg=0.01, pg=0.01, coi=1000.0, poi=500.0, thin=False),
    ]
    only_solved = synthetic_gex([rows2[1]], {}, M, F, 0.0)
    assert math.isclose(synthetic_gex(rows2, {}, M, F, 0.0), only_solved, rel_tol=1e-9)


def test_build_synthetic_oi_aggregate_and_sign() -> None:
    rows = [_row(100.0, cg=0.01, pg=0.01, coi=1000.0, poi=500.0)]
    flow = {(100.0, True): 200.0, (100.0, False): -100.0}
    snap = build_synthetic_oi(rows, flow, M, F, w=1.0)
    assert math.isclose(snap.gex, 20000.0, rel_tol=1e-9)
    assert math.isclose(snap.gex_static, 25000.0, rel_tol=1e-9)  # w=0 baseline
    assert snap.sign == 1 and snap.w == 1.0
    d = snap.to_dict()
    assert set(d) == {"gex", "sign", "gex_static", "w"}


def test_w_out_of_range_rejected() -> None:
    rows = [_row(100.0, cg=0.01, pg=0.01, coi=1000.0, poi=500.0)]
    for bad in (-0.1, 1.5):
        try:
            build_synthetic_oi(rows, {}, M, F, w=bad)
            assert False, f"w={bad} should have raised"
        except ValueError:
            pass
