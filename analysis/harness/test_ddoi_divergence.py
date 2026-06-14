"""Unit tests for analysis.harness.ddoi_divergence — the BIAS-DETECTOR core.

These LOCK the behaviour of the structural-divergence discriminator against the
agreed spec. They are PURE and deterministic: every profile is a hand-built
``{strike: gex}`` dict with chosen values, and every expected number is computed
by hand in the comments. No databento, no disk, no engine snapshot — just the
math the auditors flagged.

WHY THIS FILE EXISTS: two auditors proved the raw SIGNED pearson (−0.34 on real
data) is a MECHANICAL SIGN-FLIP artefact of the zero-summing DDOI time weight
(``Σ w = 0`` ⇒ back-loaded legs flip ddoi_leg negative), NOT new positioning
information. The discriminator fields (``magnitude_pearson`` + ``residual_r2``)
exist specifically to catch that. These tests lock that they DO: a pure scalar
multiple of VOL (sign-flip / redundant) must read magnitude_pearson≈+1 &
residual_r2≈1, while a genuine strike reshuffle must read both clearly below 1.

Style mirrors test_metrics.py / test_provenance.py: namespace import (no
__init__.py), no test classes, ``-> None`` functions, run via the repo-root
.venv python.
"""
from __future__ import annotations

import math

import pytest

from analysis.harness.ddoi_divergence import (
    divergence_metrics,
    ddoi_leg_value,
    leg_timing_diagnostic,
)

# The full key set divergence_metrics must always return (back-compat + the new
# discriminator fields). Read off ddoi_divergence.divergence_metrics directly.
_ORIGINAL_KEYS = {
    "n",
    "pearson",
    "spearman",
    "sign_agreement",
    "ddoi_argmax_strike",
    "vol_argmax_strike",
    "argmax_distance",
    "ddoi_net_sign",
    "vol_net_sign",
    "net_sign_agreement",
}
_DISCRIMINATOR_KEYS = {
    "magnitude_pearson",
    "neg_pearson",
    "best_fit_scalar_c",
    "residual_r2",
}


# --------------------------------------------------------------------------- #
# divergence_metrics — THE SIGN-FLIP CASE (load-bearing)
#
# A mechanical sign flip is ddoi == c·vol with c<0. It is REDUNDANT with VOL
# (same per-strike shape, opposite sign) and MUST NOT be read as divergence.
# --------------------------------------------------------------------------- #
def test_sign_flip_is_flagged_redundant_not_divergent() -> None:
    # Non-constant VOL profile (signed GEX). Varied per-strike, NOT constant, so
    # both pearson and |.|-pearson are well-defined.
    vol = {5000.0: 10.0, 5010.0: -4.0, 5020.0: 6.0, 5030.0: -2.0}
    # ddoi = -2 * vol  ->  exact scalar multiple, negative scalar = sign flip.
    #   {5000: -20, 5010: +8, 5020: -12, 5030: +4}
    ddoi = {k: -2.0 * v for k, v in vol.items()}

    # well-definedness preconditions (make the equalities load-bearing).
    assert len(set(vol.values())) > 1                      # signed profile varies
    assert len({abs(v) for v in vol.values()}) > 1         # |.| profile varies too

    m = divergence_metrics(ddoi, vol)

    # signed pearson: d = -2v exactly => perfect NEGATIVE linear => -1.
    assert m["pearson"] == pytest.approx(-1.0, abs=1e-9)
    # magnitude_pearson: |d| = 2|v| exactly => perfect POSITIVE => +1.
    #   THE SIGN-FLIP DETECTOR: same |shape|, so this is +1 while signed is -1.
    assert m["magnitude_pearson"] == pytest.approx(1.0, abs=1e-9)
    # neg_pearson: pearson(d, -v); d = 2*(-v) => +1.
    assert m["neg_pearson"] == pytest.approx(1.0, abs=1e-9)
    # least-squares scalar c = Σ(d·v)/Σ(v²); d=-2v => -2·Σv²/Σv² = -2.
    assert m["best_fit_scalar_c"] == pytest.approx(-2.0, abs=1e-9)
    # residual_r2: d == c·v exactly => zero residual => r2 = 1 (REDUNDANT).
    assert m["residual_r2"] == pytest.approx(1.0, abs=1e-9)
    # sign(d) is opposite sign(v) at every (non-zero) strike => 0 agreement.
    assert m["sign_agreement"] == pytest.approx(0.0, abs=1e-9)
    # |d| peaks where |v| peaks (both at 5000) => dominant strike unchanged.
    assert m["argmax_distance"] == 0.0


# --------------------------------------------------------------------------- #
# divergence_metrics — IDENTICAL CASE
# --------------------------------------------------------------------------- #
def test_identical_profiles_are_perfectly_redundant() -> None:
    vol = {5000.0: 10.0, 5010.0: -4.0, 5020.0: 6.0, 5030.0: -2.0}
    ddoi = dict(vol)  # ddoi == vol

    assert len(set(vol.values())) > 1

    m = divergence_metrics(ddoi, vol)

    assert m["pearson"] == pytest.approx(1.0, abs=1e-9)
    assert m["magnitude_pearson"] == pytest.approx(1.0, abs=1e-9)
    # c = Σ(v·v)/Σ(v²) = 1.
    assert m["best_fit_scalar_c"] == pytest.approx(1.0, abs=1e-9)
    assert m["residual_r2"] == pytest.approx(1.0, abs=1e-9)
    # identical signs everywhere => full agreement.
    assert m["sign_agreement"] == pytest.approx(1.0, abs=1e-9)
    assert m["argmax_distance"] == 0.0


# --------------------------------------------------------------------------- #
# divergence_metrics — GENUINE DIVERGENCE CASE
#
# Permute which strikes carry the big values so |ddoi| NO LONGER tracks |vol|.
# This is a real strike re-weighting and MUST NOT be mislabeled redundant:
# magnitude_pearson and residual_r2 must both fall clearly below 1.
# --------------------------------------------------------------------------- #
def test_genuine_reshuffle_is_not_redundant() -> None:
    # strikes sorted: 5000, 5010, 5020, 5030.
    vol = {5000.0: 10.0, 5010.0: 1.0, 5020.0: 2.0, 5030.0: 3.0}   # v = [10,1,2,3]
    # move the dominant magnitude off 5000 onto 5010 (different SHAPE):
    ddoi = {5000.0: 1.0, 5010.0: 10.0, 5020.0: 3.0, 5030.0: 2.0}  # d = [1,10,3,2]

    m = divergence_metrics(ddoi, vol)

    # magnitude_pearson hand-check (all positive, so |.| == value):
    #   |d|=[1,10,3,2], |v|=[10,1,2,3]; mean=4 each.
    #   dev d=[-3,6,-1,-2], dev v=[6,-3,-2,-1]
    #   cov = -18-18+2+2 = -32 ; var = 50 each ; r = -32/50 = -0.64
    assert m["magnitude_pearson"] == pytest.approx(-0.64, abs=1e-9)
    assert m["magnitude_pearson"] < 0.9          # clearly NOT a redundant +1

    # residual_r2 hand-check:
    #   c = Σ(d·v)/Σ(v²) = (10+10+6+6)/(100+1+4+9) = 32/114
    #   mean_d=4, sstot=Σ(d-4)²=50
    #   ssres=Σ(d - c·v)² ≈ 105.01 ; r2 = 1 - 105.01/50 ≈ -1.10
    c = 32.0 / 114.0
    assert m["best_fit_scalar_c"] == pytest.approx(c, abs=1e-9)
    assert m["residual_r2"] < 0.9                # structured residual => NOT scalar·VOL
    # the dominant strike actually moved (5000 -> 5010): a real re-weighting.
    assert m["argmax_distance"] == pytest.approx(10.0, abs=1e-9)


# --------------------------------------------------------------------------- #
# divergence_metrics — back-compat key surface
# --------------------------------------------------------------------------- #
def test_metrics_keys_are_back_compatible() -> None:
    vol = {5000.0: 10.0, 5010.0: -4.0, 5020.0: 6.0}
    ddoi = {5000.0: 1.0, 5010.0: 2.0, 5020.0: -1.0}
    m = divergence_metrics(ddoi, vol)
    # every original key still present...
    assert _ORIGINAL_KEYS <= set(m.keys())
    # ...alongside the new discriminator keys.
    assert _DISCRIMINATOR_KEYS <= set(m.keys())


# --------------------------------------------------------------------------- #
# divergence_metrics — degenerate (empty / no shared strikes)
# --------------------------------------------------------------------------- #
def test_empty_profiles_return_n_zero_defined() -> None:
    m = divergence_metrics({}, {})
    assert m["n"] == 0
    assert math.isnan(m["pearson"])
    assert math.isnan(m["magnitude_pearson"])
    assert math.isnan(m["residual_r2"])
    assert math.isnan(m["best_fit_scalar_c"])
    assert math.isnan(m["sign_agreement"])
    assert m["ddoi_argmax_strike"] is None
    assert m["vol_argmax_strike"] is None
    assert m["argmax_distance"] is None
    assert m["ddoi_net_sign"] == 0
    assert m["vol_net_sign"] == 0
    assert m["net_sign_agreement"] is False


def test_no_shared_strikes_is_also_n_zero() -> None:
    # disjoint strike keys => empty intersection => same n==0 branch.
    m = divergence_metrics({5000.0: 1.0}, {6000.0: 1.0})
    assert m["n"] == 0
    assert math.isnan(m["pearson"])
    assert m["argmax_distance"] is None


# --------------------------------------------------------------------------- #
# leg_timing_diagnostic
# --------------------------------------------------------------------------- #
def test_leg_timing_fraction_backloaded_and_mean_late() -> None:
    # exactly 2 of 4 legs have ddoi_leg < 0 => frac == 0.5.
    # late_half_share mean = (0.3+0.7+0.4+0.6)/4 = 2.0/4 = 0.5.
    legs = [
        (+5.0, 10.0, 0.3),   # opening (ddoi>0)
        (-3.0, 8.0, 0.7),    # back-loaded (ddoi<0)
        (+2.0, 4.0, 0.4),    # opening
        (-1.0, 6.0, 0.6),    # back-loaded
    ]
    out = leg_timing_diagnostic(legs)
    assert out["n_legs"] == 4
    assert out["frac_legs_backloaded"] == pytest.approx(0.5, abs=1e-12)
    assert out["mean_late_share"] == pytest.approx(0.5, abs=1e-12)


def test_leg_timing_ols_recovers_linear_slope() -> None:
    # ddoi = 2 * vol exactly => OLS of (ddoi ~ vol) slope=2, r2=1.
    legs = [
        (2.0, 1.0, 0.5),
        (4.0, 2.0, 0.5),
        (6.0, 3.0, 0.5),
        (8.0, 4.0, 0.5),
    ]
    out = leg_timing_diagnostic(legs)
    assert out["ols_slope"] == pytest.approx(2.0, abs=1e-9)
    assert out["ols_r2"] == pytest.approx(1.0, abs=1e-9)


def test_leg_timing_empty_is_defined() -> None:
    out = leg_timing_diagnostic([])
    assert out["n_legs"] == 0
    assert math.isnan(out["frac_legs_backloaded"])
    assert math.isnan(out["mean_late_share"])
    assert math.isnan(out["ols_slope"])
    assert math.isnan(out["ols_r2"])


# --------------------------------------------------------------------------- #
# ddoi_leg_value — uniform control == cumulative volume
# --------------------------------------------------------------------------- #
def test_ddoi_leg_value_uniform_equals_sum_abs_size() -> None:
    # uniform=True => w≡1 => Σ|size| exactly, aggressor sign stripped via abs.
    # |10|+|-20|+|30|+|-5| = 10+20+30+5 = 65.
    trades = [10.0, -20.0, 30.0, -5.0]
    assert ddoi_leg_value(trades, uniform=True) == pytest.approx(65.0, abs=1e-9)


# --------------------------------------------------------------------------- #
# ddoi_leg_value — SIGN locks the Σw=0 timing-skew property
#
# ddoi_leg is a de-meaned timing statistic, NOT a volume total: front-loaded
# volume => positive, back-loaded => negative, symmetric => ~0 (because Σw=0).
# --------------------------------------------------------------------------- #
def test_ddoi_leg_value_front_loaded_is_positive() -> None:
    # sizes [100,100,1,1], n=4 => w=[+1, +1/3, -1/3, -1].
    #   100·1 + 100·(1/3) + 1·(-1/3) + 1·(-1)
    #   = 99 + 99/3 = 99 + 33 = 132.0  (>0: volume centroid EARLY).
    trades = [100.0, 100.0, 1.0, 1.0]
    val = ddoi_leg_value(trades)
    assert val > 0.0
    assert val == pytest.approx(132.0, abs=1e-9)


def test_ddoi_leg_value_back_loaded_is_negative() -> None:
    # sizes [1,1,100,100] (the reversal) => exact negative of the front case.
    #   1·1 + 1·(1/3) + 100·(-1/3) + 100·(-1) = -132.0  (<0: centroid LATE).
    trades = [1.0, 1.0, 100.0, 100.0]
    val = ddoi_leg_value(trades)
    assert val < 0.0
    assert val == pytest.approx(-132.0, abs=1e-9)


def test_ddoi_leg_value_symmetric_is_zero() -> None:
    # equal sizes => Σ w·s = s·Σw = s·0 = 0 exactly (Σw=0 for any n>1).
    trades = [50.0, 50.0, 50.0, 50.0]
    assert ddoi_leg_value(trades) == pytest.approx(0.0, abs=1e-9)


def test_ddoi_leg_value_two_trade_leg_uses_engine_pm1_weights() -> None:
    # n=2 => engine weights [+1, -1] => ddoi = |s0| - |s1|.
    # tuple form (ts, size): last element is the size; |30|-|10| = 20.
    trades = [(1, 30.0), (2, 10.0)]
    assert ddoi_leg_value(trades) == pytest.approx(20.0, abs=1e-9)
