"""Unit tests for engine.exposure (PRD #12, acceptance T-04).

T-04: signs match the locked dealer convention; units are USD-per-1% (GEX) and
USD notional (DEX); thin strikes are interpolated and flagged.
"""

from __future__ import annotations

import math

from engine.exposure import (
    ChainRow,
    build_profile,
    net_gamma,
    profile_to_dicts,
    strike_exposure,
)

REL = 1e-9


def _row(strike: float, **kw: float) -> ChainRow:
    base = dict(
        call_gamma=0.0,
        put_gamma=0.0,
        call_delta=0.0,
        put_delta=0.0,
        call_vol=0.0,
        put_vol=0.0,
    )
    base.update(kw)
    return ChainRow(strike=strike, **base)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# T-04: sign convention
# --------------------------------------------------------------------------- #
def test_sign_call_heavy_positive_gex() -> None:
    # Dealer LONG calls -> call gamma adds POSITIVE gex.
    row = _row(4500.0, call_gamma=0.002, call_vol=500.0)
    [e] = build_profile([row], M=50.0, F=4500.0)
    assert e.net_gex > 0.0


def test_sign_put_heavy_negative_gex() -> None:
    # Dealer SHORT puts -> put gamma adds NEGATIVE gex.
    row = _row(4500.0, put_gamma=0.002, put_vol=500.0)
    [e] = build_profile([row], M=50.0, F=4500.0)
    assert e.net_gex < 0.0


def test_sign_balanced_gamma_cancels() -> None:
    # Equal call/put gamma*vol -> net gex == 0 (long call vs short put cancel).
    row = _row(4500.0, call_gamma=0.002, put_gamma=0.002, call_vol=300.0, put_vol=300.0)
    [e] = build_profile([row], M=50.0, F=4500.0)
    assert abs(e.net_gex) < 1e-6


def test_sign_dealer_net_long_delta() -> None:
    # call_delta>0 and put_delta<0; long calls + short puts => net LONG delta.
    row = _row(
        4500.0,
        call_delta=0.60,
        put_delta=-0.40,
        call_vol=100.0,
        put_vol=100.0,
    )
    [e] = build_profile([row], M=50.0, F=4500.0)
    assert e.net_dex > 0.0
    # = (0.60*100 - (-0.40*100)) * 50 * 4500 = 100 * 225000 = 22_500_000
    assert math.isclose(e.net_dex, 22_500_000.0, rel_tol=REL)


# --------------------------------------------------------------------------- #
# T-04: units (USD-per-1% for GEX, USD notional for DEX)
# --------------------------------------------------------------------------- #
def test_units_gex_known_magnitude_es() -> None:
    # /ES: M=50, F=4500. Single call leg.
    # net_gex = 0.001 * 1000 * 50 * 4500^2 * 0.01 = 10,125,000 USD / 1% move.
    g, d = strike_exposure(
        call_gamma=0.001, put_gamma=0.0,
        call_delta=0.5, put_delta=0.0,
        call_vol=1000.0, put_vol=0.0,
        M=50.0, F=4500.0,
    )
    assert math.isclose(g, 10_125_000.0, rel_tol=REL)
    # net_dex = 0.5 * 1000 * 50 * 4500 = 112,500,000 USD notional.
    assert math.isclose(d, 112_500_000.0, rel_tol=REL)


def test_units_gex_known_magnitude_nq() -> None:
    # /NQ: M=20, F=15800. net_gex = 0.0005*2000*20*15800^2*0.01
    g, _ = strike_exposure(
        call_gamma=0.0005, put_gamma=0.0,
        call_delta=0.0, put_delta=0.0,
        call_vol=2000.0, put_vol=0.0,
        M=20.0, F=15800.0,
    )
    expected = 0.0005 * 2000.0 * 20.0 * (15800.0 ** 2) * 0.01
    assert math.isclose(g, expected, rel_tol=REL)
    assert g > 0.0


def test_build_profile_matches_strike_exposure() -> None:
    row = _row(
        4500.0,
        call_gamma=0.0012, put_gamma=0.0009,
        call_delta=0.55, put_delta=-0.45,
        call_vol=800.0, put_vol=650.0,
    )
    [e] = build_profile([row], M=50.0, F=4500.0)
    g, d = strike_exposure(
        0.0012, 0.0009, 0.55, -0.45, 800.0, 650.0, 50.0, 4500.0
    )
    assert math.isclose(e.net_gex, g, rel_tol=REL)
    assert math.isclose(e.net_dex, d, rel_tol=REL)


# --------------------------------------------------------------------------- #
# net_gamma aggregate
# --------------------------------------------------------------------------- #
def test_net_gamma_is_sum_of_net_gex() -> None:
    chain = [
        _row(4490.0, call_gamma=0.001, call_vol=300.0),
        _row(4500.0, put_gamma=0.002, put_vol=400.0),
        _row(4510.0, call_gamma=0.0015, call_vol=200.0),
    ]
    profile = build_profile(chain, M=50.0, F=4500.0)
    assert math.isclose(
        net_gamma(profile), sum(e.net_gex for e in profile), rel_tol=REL
    )
    # Mixed book: middle put leg drags the aggregate; verify it is finite.
    assert math.isfinite(net_gamma(profile))


# --------------------------------------------------------------------------- #
# Interpolation
# --------------------------------------------------------------------------- #
def test_interpolation_midpoint() -> None:
    M, F = 50.0, 4500.0
    lo = _row(4490.0, call_gamma=0.0010, put_gamma=0.0012, call_delta=0.55, put_delta=-0.45, call_vol=10.0, put_vol=10.0)
    mid = ChainRow(
        strike=4500.0,
        call_gamma=float("nan"), put_gamma=float("nan"),  # garbage from thin IV
        call_delta=float("nan"), put_delta=float("nan"),
        call_vol=800.0, put_vol=700.0,
        thin=True,
    )
    hi = _row(4510.0, call_gamma=0.0014, put_gamma=0.0016, call_delta=0.60, put_delta=-0.40, call_vol=10.0, put_vol=10.0)

    profile = build_profile([lo, mid, hi], M, F)
    by_strike = {e.strike: e for e in profile}

    assert by_strike[4490.0].interpolated is False
    assert by_strike[4510.0].interpolated is False
    assert by_strike[4500.0].interpolated is True

    # Midpoint greeks: cg=0.0012, pg=0.0014, cd=0.575, pd=-0.425; vols are the
    # row's own observed 800 / 700 (NOT interpolated).
    g_exp, d_exp = strike_exposure(0.0012, 0.0014, 0.575, -0.425, 800.0, 700.0, M, F)
    e = by_strike[4500.0]
    assert math.isfinite(e.net_gex) and math.isfinite(e.net_dex)
    assert math.isclose(e.net_gex, g_exp, rel_tol=1e-9)
    assert math.isclose(e.net_dex, d_exp, rel_tol=1e-9)


def test_interpolation_boundary_flat() -> None:
    M, F = 50.0, 4500.0
    thin = ChainRow(
        strike=4500.0,
        call_gamma=999.0, put_gamma=999.0, call_delta=9.0, put_delta=9.0,
        call_vol=100.0, put_vol=100.0, thin=True,
    )
    n1 = _row(4510.0, call_gamma=0.0014, put_gamma=0.0016, call_delta=0.60, put_delta=-0.40, call_vol=5.0, put_vol=5.0)
    n2 = _row(4520.0, call_gamma=0.0018, put_gamma=0.0020, call_delta=0.65, put_delta=-0.35, call_vol=5.0, put_vol=5.0)

    profile = build_profile([thin, n1, n2], M, F)
    e = next(x for x in profile if x.strike == 4500.0)
    assert e.interpolated is True
    # Flat-carry nearest neighbour (4510) greeks; garbage 999 must NOT be used.
    g_exp, d_exp = strike_exposure(0.0014, 0.0016, 0.60, -0.40, 100.0, 100.0, M, F)
    assert math.isclose(e.net_gex, g_exp, rel_tol=1e-9)
    assert math.isclose(e.net_dex, d_exp, rel_tol=1e-9)


def test_interpolation_all_thin_defaults_zero() -> None:
    rows = [
        ChainRow(strike=4500.0, call_gamma=1.0, put_gamma=1.0, call_delta=1.0, put_delta=1.0, call_vol=100.0, put_vol=100.0, thin=True),
        ChainRow(strike=4510.0, call_gamma=1.0, put_gamma=1.0, call_delta=1.0, put_delta=1.0, call_vol=100.0, put_vol=100.0, thin=True),
    ]
    profile = build_profile(rows, M=50.0, F=4500.0)
    for e in profile:
        assert e.interpolated is True
        assert e.net_gex == 0.0 and e.net_dex == 0.0


def test_profile_to_dicts_shape() -> None:
    row = _row(4500.0, call_gamma=0.001, call_vol=100.0)
    dicts = profile_to_dicts(build_profile([row], M=50.0, F=4500.0))
    assert dicts and set(dicts[0]) == {"strike", "net_gex", "net_dex", "interpolated"}


def test_build_profile_sorts_by_strike() -> None:
    chain = [_row(4510.0, call_gamma=0.001, call_vol=1.0), _row(4490.0, call_gamma=0.001, call_vol=1.0)]
    profile = build_profile(chain, M=50.0, F=4500.0)
    assert [e.strike for e in profile] == [4490.0, 4510.0]
