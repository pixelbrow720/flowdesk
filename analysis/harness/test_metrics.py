"""Unit tests for analysis.harness.metrics — the PURE validation-metric core.

These exercise the metric math directly (no databento, no disk). They prove the
harness COMPUTES the defined descriptor; they say nothing about whether the signal
predicts price (that needs the operator's ~90-day forward run — see module docstring).
"""
from __future__ import annotations

import math

from analysis.harness.metrics import (
    distance_matched_levels,
    level_attraction,
    level_attraction_vs_baseline,
    magnitude_reconciliation,
    oi_walls,
    partial_spearman,
    pin_rate,
)


# --------------------------------------------------------------------------- #
# partial_spearman
# --------------------------------------------------------------------------- #
def test_partial_spearman_removes_shared_confound() -> None:
    # x and y are driven ENTIRELY by a common z; controlling for z -> ~0 partial.
    z = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
    x = [v * 2.0 for v in z]
    y = [v * 3.0 for v in z]
    pr = partial_spearman(x, y, z)
    assert abs(pr) < 1e-6 or math.isnan(pr)


def test_partial_spearman_keeps_independent_relation() -> None:
    # y tracks x; z is unrelated noise -> partial stays high.
    x = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    y = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    z = [5.0, 1.0, 4.0, 2.0, 6.0, 3.0]
    assert partial_spearman(x, y, z) > 0.9


def test_partial_spearman_too_few_points() -> None:
    assert math.isnan(partial_spearman([1.0, 2.0], [1.0, 2.0], [1.0, 2.0]))


# --------------------------------------------------------------------------- #
# magnitude_reconciliation
# --------------------------------------------------------------------------- #
def test_reconciliation_too_few_keys_is_na() -> None:
    oi = {("A", True): 10.0, ("B", True): 20.0}
    fl = {("A", True): 5.0, ("B", True): 8.0}
    m = magnitude_reconciliation(oi, fl, min_keys=5)
    assert m["n"] == 2 and m["rho"] is None and m["partial_rho"] is None


def test_reconciliation_detects_monotone_magnitude_relation() -> None:
    keys = [(k, True) for k in range(8)]
    oi = {k: float(i + 1) for i, k in enumerate(keys)}
    fl = {k: float(i + 1) for i, k in enumerate(keys)}
    m = magnitude_reconciliation(oi, fl, min_keys=5)
    assert m["n"] == 8 and math.isclose(m["rho"], 1.0, rel_tol=1e-9) and m["p"] < 0.05


def test_reconciliation_uses_absolute_flow_not_sign() -> None:
    keys = [(k, True) for k in range(6)]
    oi = {k: float(i + 1) for i, k in enumerate(keys)}
    fl = {k: -float(i + 1) for i, k in enumerate(keys)}  # all negative
    m = magnitude_reconciliation(oi, fl, min_keys=5)
    assert math.isclose(m["rho"], 1.0, rel_tol=1e-9)


def test_reconciliation_partial_strips_volume_confound() -> None:
    # |flow| and OI both perfectly track volume but are otherwise unrelated:
    # raw rho high, partial_rho ~0 once volume is controlled.
    keys = [(k, True) for k in range(7)]
    vol = {k: float(i + 1) for i, k in enumerate(keys)}
    oi = {k: float(i + 1) * 10.0 for i, k in enumerate(keys)}
    fl = {k: float(i + 1) * 2.0 for i, k in enumerate(keys)}
    m = magnitude_reconciliation(oi, fl, control=vol, min_keys=5)
    assert m["rho"] > 0.9                       # confounded raw correlation
    assert m["partial_rho"] is None or abs(m["partial_rho"]) < 1e-6


def test_reconciliation_skips_zero_and_unshared_keys() -> None:
    oi = {("A", True): 10.0, ("B", True): 0.0, ("C", True): 30.0, ("D", True): 5.0}
    fl = {("A", True): 2.0, ("B", True): 9.0, ("C", True): 6.0, ("X", True): 1.0}
    m = magnitude_reconciliation(oi, fl, min_keys=2)
    assert m["n"] == 2   # B zero-OI, D no-flow, X no-OI all dropped


# --------------------------------------------------------------------------- #
# distance_matched_levels
# --------------------------------------------------------------------------- #
def test_distance_matched_selects_similar_distance_strikes() -> None:
    strikes = [4980.0, 4990.0, 5000.0, 5010.0, 5020.0]
    fwd = 5000.0
    # reference 5010 is 10 from fwd; band 2 -> strikes 10±2 away: 4990 and 5010(excl)
    out = distance_matched_levels(5010.0, strikes, fwd, band=2.0)
    assert 4990.0 in out and 5010.0 not in out and 5000.0 not in out


def test_distance_matched_empty_when_no_match() -> None:
    out = distance_matched_levels(5000.0, [5000.0, 5100.0], 5000.0, band=1.0)
    assert out == []   # only the ref (excluded) is at distance 0


# --------------------------------------------------------------------------- #
# level_attraction
# --------------------------------------------------------------------------- #
def test_attraction_full_pin_is_one() -> None:
    assert math.isclose(level_attraction(5010.0, 5000.0, 5000.0), 1.0, rel_tol=1e-12)


def test_attraction_moving_away_is_negative() -> None:
    assert math.isclose(level_attraction(5010.0, 5020.0, 5000.0), -1.0, rel_tol=1e-12)


def test_attraction_open_on_level_is_zero() -> None:
    assert level_attraction(5000.0, 5005.0, 5000.0) == 0.0


# --------------------------------------------------------------------------- #
# level_attraction_vs_baseline
# --------------------------------------------------------------------------- #
def test_attraction_excess_over_baseline() -> None:
    out = level_attraction_vs_baseline(5010.0, 5000.0, 5000.0, [4990.0, 5020.0])
    assert math.isclose(out["attraction"], 1.0, rel_tol=1e-12)
    assert out["n_baseline"] == 2
    assert out["excess"] == out["attraction"] - out["baseline_mean"]


def test_attraction_no_baseline_gives_none_excess() -> None:
    out = level_attraction_vs_baseline(5010.0, 5000.0, 5000.0, [])
    assert out["baseline_mean"] is None and out["excess"] is None and out["n_baseline"] == 0


# --------------------------------------------------------------------------- #
# pin_rate
# --------------------------------------------------------------------------- #
def test_pin_rate_counts_within_tolerance() -> None:
    closes = [5000.0, 5001.0, 5006.0, 4998.0, 5012.0]
    out = pin_rate(closes, level=5000.0, tolerance=5.0)
    assert math.isclose(out["pin_rate"], 0.6, rel_tol=1e-12) and out["n"] == 5


def test_pin_rate_empty_series() -> None:
    out = pin_rate([], level=5000.0, tolerance=5.0)
    assert out["pin_rate"] is None and out["n"] == 0


# --------------------------------------------------------------------------- #
# oi_walls
# --------------------------------------------------------------------------- #
def test_oi_walls_picks_top_oi_on_correct_side() -> None:
    fwd = 5000.0
    call_oi = {5010.0: 100.0, 5020.0: 500.0, 5030.0: 300.0, 4990.0: 999.0}
    put_oi = {4990.0: 400.0, 4980.0: 800.0, 4970.0: 200.0, 5020.0: 999.0}
    out = oi_walls(call_oi, put_oi, fwd, top_n=2)
    # call walls: only strikes ABOVE 5000, ranked by OI -> 5020 (500) > 5030 (300)
    assert out["call_walls"] == [5020.0, 5030.0]
    # put walls: only strikes BELOW 5000, ranked by OI -> 4980 (800) > 4990 (400)
    assert out["put_walls"] == [4980.0, 4990.0]


def test_oi_walls_excludes_wrong_side_and_zero_oi() -> None:
    fwd = 5000.0
    call_oi = {5010.0: 0.0, 5020.0: 100.0}   # 5010 zero-OI dropped
    put_oi = {4990.0: 50.0}
    out = oi_walls(call_oi, put_oi, fwd, top_n=3)
    assert out["call_walls"] == [5020.0]
    assert out["put_walls"] == [4990.0]


def test_oi_walls_empty_when_no_strikes() -> None:
    out = oi_walls({}, {}, 5000.0)
    assert out["call_walls"] == [] and out["put_walls"] == []
