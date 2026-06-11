"""Unit tests for engine.field and engine.levels (PRD #12, T-05 & T-06).

T-05: gamma-flip zero-crossing interpolation correctness.
T-06: Call/Put walls Top-3 above/below forward, exact vs a golden fixture.
Plus: field arrays satisfy the Snapshot contract invariants.
"""

from __future__ import annotations

import math
from collections import namedtuple

from engine.black76 import gamma as bs_gamma
from engine.exposure import ChainRow
from engine.field import (
    Axis,
    CLIP_PERCENTILE,
    FieldArrays,
    build_field,
    normalize_signed,
    percentile_abs,
    price_grid_from_axis,
)
from engine.levels import (
    StrikeOI,
    call_walls,
    compute_levels,
    gamma_flip,
    largest_dex,
    largest_gex,
    put_walls,
)

# Lightweight profile point (structurally matches ProfilePoint protocol).
PP = namedtuple("PP", "strike net_gex net_dex")


# --------------------------------------------------------------------------- #
# FIELD: contract invariants
# --------------------------------------------------------------------------- #
RATE = 0.05
M_ES = 50.0


def _one_call_chain(strike=5000.0, iv=0.2, T=0.01, vol=1000.0):
    """A single liquid call leg (no put) for exact projection checks."""
    return [
        ChainRow(
            strike=strike,
            call_gamma=0.0, put_gamma=0.0, call_delta=0.0, put_delta=0.0,
            call_vol=vol, put_vol=0.0,
            call_iv=iv, put_iv=None, t_expiry=T,
        )
    ]


def test_field_invariants_default_grid() -> None:
    axis = Axis(4990.0, 5010.0, 5.0)
    f = build_field(_one_call_chain(), axis, 5000.0, M_ES, RATE)
    assert isinstance(f, FieldArrays)
    assert f.price_grid == [4990.0, 4995.0, 5000.0, 5005.0, 5010.0]
    # contract: equal length, all finite
    assert len(f.price_grid) == len(f.gamma) == len(f.delta)
    assert all(math.isfinite(v) for v in f.gamma + f.delta + f.price_grid)


def test_field_reevaluates_bs_gamma_at_each_price() -> None:
    # B7: gamma[i] = +1 * bs_gamma(S_y, K, T, r, iv) * vol * M * S_y^2 * 0.01.
    # Asserts the field RE-EVALUATES Black-76 at each hypothetical spot, with
    # the locked dealer sign (+ call) and notional scaling — not a profile sample.
    K, iv, T, vol = 5000.0, 0.2, 0.01, 1000.0
    axis = Axis(4990.0, 5010.0, 5.0)
    f = build_field(_one_call_chain(K, iv, T, vol), axis, 5000.0, M_ES, RATE)
    for sy, g in zip(f.price_grid, f.gamma):
        expected = bs_gamma(sy, K, T, RATE, iv) * vol * M_ES * sy * sy * 0.01
        assert math.isclose(g, expected, rel_tol=1e-9)


def test_field_nonstrike_node_nonzero() -> None:
    # A single call at 5000 still produces non-zero gamma at the 4995 node:
    # its gamma bell reaches neighbouring prices. Proof of re-evaluation, not
    # discrete-profile interpolation (which would be flat between nodes).
    axis = Axis(4990.0, 5010.0, 5.0)
    f = build_field(_one_call_chain(5000.0), axis, 5000.0, M_ES, RATE)
    i = f.price_grid.index(4995.0)
    assert f.gamma[i] != 0.0


def test_field_bell_peaks_near_strike() -> None:
    # Black-76 gamma is bell-shaped in S, so |gamma| is largest at the grid
    # node nearest the strike — the topographic ridge.
    K = 5000.0
    axis = Axis(4950.0, 5050.0, 5.0)
    f = build_field(_one_call_chain(K), axis, 5000.0, M_ES, RATE)
    peak_i = max(range(len(f.gamma)), key=lambda i: abs(f.gamma[i]))
    assert abs(f.price_grid[peak_i] - K) <= 5.0


def test_field_thin_legs_contribute_zero() -> None:
    # IV None (thin) -> no reliable gamma curve to project -> zero contribution.
    rows = [
        ChainRow(
            strike=5000.0,
            call_gamma=0.0, put_gamma=0.0, call_delta=0.0, put_delta=0.0,
            call_vol=1000.0, put_vol=1000.0,
            call_iv=None, put_iv=None, t_expiry=0.01,
        )
    ]
    axis = Axis(4990.0, 5010.0, 5.0)
    f = build_field(rows, axis, 5000.0, M_ES, RATE)
    assert all(v == 0.0 for v in f.gamma)
    assert all(v == 0.0 for v in f.delta)


def test_field_empty_chain_is_zero() -> None:
    axis = Axis(4990.0, 5000.0, 5.0)
    f = build_field([], axis, 4995.0, M_ES, RATE)
    assert f.price_grid == [4990.0, 4995.0, 5000.0]
    assert f.gamma == [0.0, 0.0, 0.0]
    assert f.delta == [0.0, 0.0, 0.0]


def test_field_finite_with_smoothing() -> None:
    axis = Axis(4990.0, 5010.0, 5.0)
    grid = [4980.0, 5000.0, 5020.0]  # ends outside the strike range
    f = build_field(
        _one_call_chain(), axis, 5000.0, M_ES, RATE, grid, smoothing_bw=5.0
    )
    assert len(f.price_grid) == len(f.gamma) == len(f.delta) == 3
    assert all(math.isfinite(v) for v in f.gamma + f.delta)


def test_price_grid_from_axis_nq_step() -> None:
    grid = price_grid_from_axis(Axis(15800.0, 15840.0, 10.0))
    assert grid == [15800.0, 15810.0, 15820.0, 15830.0, 15840.0]


# --------------------------------------------------------------------------- #
# Percentile clip + signed normalize (anti-skew §6G; FE-parity helpers)
# --------------------------------------------------------------------------- #
def _fe_percentile_abs(values, p):
    """Reference reimplementation of the FE field-2d.ts percentileAbs."""
    if len(values) == 0:
        return 0.0
    arr = sorted(abs(v) for v in values)
    idx = min(len(arr) - 1, max(0, math.floor(p * (len(arr) - 1))))
    return arr[idx]


def _fe_normalize_signed(value, max_abs):
    """Reference reimplementation of the FE field-2d.ts normalizeSigned."""
    if max_abs <= 0:
        return 0.5
    t = 0.5 - 0.5 * (value / max_abs)
    return max(0.0, min(1.0, t))


def test_clip_percentile_constant_matches_fe() -> None:
    # FE field-2d.ts pins CLIP_PERCENTILE = 0.98; the engine must agree.
    assert CLIP_PERCENTILE == 0.98


def test_percentile_abs_empty_is_zero() -> None:
    assert percentile_abs([]) == 0.0


def test_percentile_abs_matches_fe_algorithm() -> None:
    vals = [5.0, -100.0, 2.0, -3.0, 1.0, 50.0, -7.0, 0.5, 9.0, -1000.0]
    for p in (0.0, 0.5, 0.9, 0.98, 1.0):
        assert percentile_abs(vals, p) == _fe_percentile_abs(vals, p)


def test_percentile_abs_clips_single_spike() -> None:
    # 9 small magnitudes + 1 huge spike: the 98th percentile ignores the spike,
    # so a lone 0DTE gamma spike can't define (and flatten) the whole scale.
    vals = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1_000_000.0]
    assert percentile_abs(vals, 0.98) == 1.0


def test_percentile_abs_p_clamped() -> None:
    vals = [1.0, 2.0, 3.0]
    assert percentile_abs(vals, -5.0) == 1.0   # floor at index 0
    assert percentile_abs(vals, 5.0) == 3.0    # ceil at last index


def test_normalize_signed_anchors() -> None:
    assert normalize_signed(10.0, 10.0) == 0.0    # +max -> turquoise
    assert normalize_signed(0.0, 10.0) == 0.5     # neutral
    assert normalize_signed(-10.0, 10.0) == 1.0   # -max -> crimson
    assert normalize_signed(5.0, 0.0) == 0.5      # degenerate scale -> neutral


def test_normalize_signed_clamps_beyond_clip() -> None:
    assert normalize_signed(50.0, 10.0) == 0.0    # beyond +clip clamps to 0
    assert normalize_signed(-50.0, 10.0) == 1.0   # beyond -clip clamps to 1


def test_normalize_signed_matches_fe() -> None:
    for value, mx in [(3.0, 10.0), (-4.0, 8.0), (0.0, 5.0), (7.0, 0.0), (-99.0, 12.0)]:
        assert normalize_signed(value, mx) == _fe_normalize_signed(value, mx)


# --------------------------------------------------------------------------- #
# T-05: gamma-flip zero-crossing interpolation
# --------------------------------------------------------------------------- #
def test_flip_interpolated_between_nodes() -> None:
    # net_gex chosen so cumulative = [-30, -10, +20, +50].
    prof = [
        PP(4990.0, -30.0, 0.0),
        PP(4995.0, 20.0, 0.0),    # cum -10
        PP(5000.0, 30.0, 0.0),    # cum +20
        PP(5005.0, 30.0, 0.0),    # cum +50
    ]
    # crossing between 4995 (cum -10) and 5000 (cum +20):
    # 4995 + 5 * (0 - (-10)) / (20 - (-10)) = 4995 + 5*10/30 = 4996.666...
    flip = gamma_flip(prof)
    assert flip is not None
    assert math.isclose(flip, 4995.0 + 5.0 * 10.0 / 30.0, rel_tol=1e-12)


def test_flip_exact_node_zero() -> None:
    # cumulative = [-10, 0, +25] -> exact zero at the middle strike.
    prof = [
        PP(4990.0, -10.0, 0.0),
        PP(4995.0, 10.0, 0.0),    # cum 0
        PP(5000.0, 25.0, 0.0),    # cum 25
    ]
    assert gamma_flip(prof) == 4995.0


def test_flip_none_when_no_crossing() -> None:
    prof = [PP(4990.0, 5.0, 0.0), PP(4995.0, 7.0, 0.0), PP(5000.0, 3.0, 0.0)]
    assert gamma_flip(prof) is None


def test_flip_multiple_crossings_picks_nearest_forward() -> None:
    # cumulative = [+10, -5, +5] -> crossings near 4992.5 and 4997.5.
    prof = [
        PP(4990.0, 10.0, 0.0),    # cum +10
        PP(4995.0, -15.0, 0.0),   # cum -5
        PP(5000.0, 10.0, 0.0),    # cum +5
    ]
    # First crossing (4990->4995): 4990 + 5*(0-10)/(-5-10) = 4990 + 5*(-10)/(-15)=4993.333
    # Second (4995->5000): 4995 + 5*(0-(-5))/(5-(-5)) = 4995 + 2.5 = 4997.5
    c1 = 4990.0 + 5.0 * (0.0 - 10.0) / (-5.0 - 10.0)
    c2 = 4997.5
    assert math.isclose(gamma_flip(prof, forward=4990.0), c1, rel_tol=1e-12)
    assert math.isclose(gamma_flip(prof, forward=5005.0), c2, rel_tol=1e-12)
    # No forward -> lowest-strike crossing.
    assert math.isclose(gamma_flip(prof), c1, rel_tol=1e-12)


# --------------------------------------------------------------------------- #
# Largest GEX / DEX (by VOL)
# --------------------------------------------------------------------------- #
def test_largest_gex_dex_by_abs() -> None:
    prof = [
        PP(4990.0, -120e6, 34e6),
        PP(5000.0, 560e6, 22e6),
        PP(5010.0, -330e6, 9e6),
    ]
    assert largest_gex(prof) == 5000.0     # |560e6| is largest
    assert largest_dex(prof) == 4990.0     # |34e6| is largest
    assert largest_gex([]) is None
    assert largest_dex([]) is None


# --------------------------------------------------------------------------- #
# T-06: Call/Put walls vs golden fixture
# --------------------------------------------------------------------------- #
def _golden_oi():
    # forward = 5000.25; strikes around it with engineered OI.
    # call OI (above): 5015->900, 5025->1500, 5050->1200, 5005->300, 5010->100
    # put  OI (below): 4985->700, 4975->1100, 4950->1600, 4995->200, 4990->50
    return [
        StrikeOI(4950.0, call_oi=10.0, put_oi=1600.0),
        StrikeOI(4975.0, call_oi=10.0, put_oi=1100.0),
        StrikeOI(4985.0, call_oi=10.0, put_oi=700.0),
        StrikeOI(4990.0, call_oi=10.0, put_oi=50.0),
        StrikeOI(4995.0, call_oi=10.0, put_oi=200.0),
        StrikeOI(5005.0, call_oi=300.0, put_oi=10.0),
        StrikeOI(5010.0, call_oi=100.0, put_oi=10.0),
        StrikeOI(5015.0, call_oi=900.0, put_oi=10.0),
        StrikeOI(5025.0, call_oi=1500.0, put_oi=10.0),
        StrikeOI(5050.0, call_oi=1200.0, put_oi=10.0),
    ]


def test_call_walls_top3_above_forward_exact() -> None:
    fwd = 5000.25
    # Ranked by call OI desc: 5025(1500), 5050(1200), 5015(900) [, 5005, 5010]
    assert call_walls(_golden_oi(), fwd, top_n=3) == [5025.0, 5050.0, 5015.0]


def test_put_walls_top3_below_forward_exact() -> None:
    fwd = 5000.25
    # Ranked by put OI desc: 4950(1600), 4975(1100), 4985(700) [, 4995, 4990]
    assert put_walls(_golden_oi(), fwd, top_n=3) == [4950.0, 4975.0, 4985.0]


def test_walls_exclude_strikes_at_or_wrong_side_of_forward() -> None:
    fwd = 5000.0
    oi = [
        StrikeOI(5000.0, call_oi=9999.0, put_oi=9999.0),  # at forward -> excluded both
        StrikeOI(5005.0, call_oi=100.0, put_oi=0.0),
        StrikeOI(4995.0, call_oi=0.0, put_oi=100.0),
    ]
    assert call_walls(oi, fwd) == [5005.0]
    assert put_walls(oi, fwd) == [4995.0]


def test_walls_tie_break_deterministic() -> None:
    # Equal call OI above forward -> nearer-to-forward first, then strike asc.
    fwd = 5000.0
    oi = [
        StrikeOI(5005.0, call_oi=500.0, put_oi=0.0),
        StrikeOI(5010.0, call_oi=500.0, put_oi=0.0),
        StrikeOI(5020.0, call_oi=500.0, put_oi=0.0),
    ]
    assert call_walls(oi, fwd, top_n=3) == [5005.0, 5010.0, 5020.0]


# --------------------------------------------------------------------------- #
# Divergence #2 -> option B: walls by GAMMA-DOLLAR (gamma * OI), not raw OI.
# --------------------------------------------------------------------------- #
def test_walls_gamma_dollar_beats_raw_oi() -> None:
    # 5050 has the largest raw call OI (5000) but negligible gamma (far OTM),
    # while 5010 has modest OI (800) and high gamma. Under gamma-$ the wall is
    # 5010, NOT 5050 — the discriminating case that motivates Divergence #2.
    fwd = 5000.0
    oi = [
        StrikeOI(5010.0, call_oi=800.0, put_oi=0.0, call_gamma=0.020, put_gamma=0.0),
        StrikeOI(5050.0, call_oi=5000.0, put_oi=0.0, call_gamma=0.0002, put_gamma=0.0),
    ]
    # raw OI would rank 5050 first (5000 > 800); gamma-$: 5010=16.0 vs 5050=1.0.
    assert call_walls(oi, fwd, top_n=2) == [5010.0, 5050.0]


def test_walls_zero_gamma_excluded() -> None:
    # A thin strike (gamma solved to 0) carries zero gamma-$ weight and is
    # excluded entirely, even with large OI.
    fwd = 5000.0
    oi = [
        StrikeOI(5005.0, call_oi=100.0, put_oi=0.0, call_gamma=0.01, put_gamma=0.0),
        StrikeOI(5010.0, call_oi=9999.0, put_oi=0.0, call_gamma=0.0, put_gamma=0.0),
    ]
    assert call_walls(oi, fwd, top_n=3) == [5005.0]


def test_walls_default_gamma_reduces_to_oi() -> None:
    # StrikeOI gamma defaults to 1.0 -> gamma-$ weight == raw OI, so OI-only
    # fixtures (no greeks) rank exactly as the pre-#2 behaviour.
    fwd = 5000.0
    oi = [
        StrikeOI(5005.0, call_oi=300.0, put_oi=0.0),
        StrikeOI(5010.0, call_oi=900.0, put_oi=0.0),
        StrikeOI(5015.0, call_oi=600.0, put_oi=0.0),
    ]
    assert call_walls(oi, fwd, top_n=3) == [5010.0, 5015.0, 5005.0]


def test_compute_levels_shape_matches_contract() -> None:
    fwd = 5000.25
    prof = [
        PP(4990.0, -120e6, 34e6),
        PP(4995.0, -40e6, 28e6),
        PP(5000.0, 560e6, 22e6),
        PP(5005.0, 210e6, 18e6),
        PP(5010.0, -330e6, 9e6),
    ]
    lv = compute_levels(prof, _golden_oi(), fwd, top_n=3)
    assert set(lv) == {
        "call_walls",
        "put_walls",
        "gamma_flip",
        "largest_gex",
        "largest_dex",
    }
    assert lv["call_walls"] == [5025.0, 5050.0, 5015.0]
    assert lv["put_walls"] == [4950.0, 4975.0, 4985.0]
    assert lv["largest_gex"] == 5000.0
    assert lv["largest_dex"] == 4990.0
    assert lv["gamma_flip"] is None or math.isfinite(lv["gamma_flip"])
