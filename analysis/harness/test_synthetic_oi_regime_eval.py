"""Unit tests for analysis.harness.synthetic_oi_regime_eval — the regime eval core.

These LOCK the behaviour of the EXPLORATORY synthetic-OI VOLATILITY-REGIME
discriminator against the agreed spec. They are PURE and deterministic: every
``regimes`` / ``moves`` / ``forwards`` array is hand-built with chosen values, and
every expected number is computed by hand in the comments. No databento, no disk,
no engine import needed — this module is stdlib-only (the per-minute synthetic-GEX
profile that feeds ``regime_sign`` is built UPSTREAM by the runner via
``synthetic_oi_eval.synthetic_gex_by_strike``; here we test the sign/score core).

WHY THIS FILE EXISTS — the load-bearing concern (same as test_hiro_eval): a real-data
regime run is only trustworthy if the harness can be PROVEN to DETECT a separation
when one genuinely exists. A metric that returns ``sep ~ 0`` regardless of input would
manufacture a false null and is worthless. The single most important test here is the
POSITIVE CONTROL (``test_positive_control_metric_is_alive``): a PLANTED series where
short-gamma minutes move large and long-gamma minutes move small must drive ``sep``
clearly ABOVE 0 and ``headline_gap`` ABOVE 0; flipping the planting must drive ``sep``
BELOW 0. A metric that can reach both signs on planted data is ALIVE; one stuck near 0
is broken — and that is what makes a real-data UNDETERMINED a trustworthy null rather
than a dead-harness artefact.

Style mirrors test_hiro_eval.py / test_synthetic_oi_eval.py: namespace import (no
__init__.py), no test classes, ``-> None`` functions, run via the repo-root .venv
python.
"""
from __future__ import annotations

from collections import Counter

import pytest

from analysis.harness.synthetic_oi_regime_eval import (
    DEFAULT_SHUFFLE_SEEDS,
    headline_gap,
    realized_move,
    regime_separation,
    regime_sign,
    shuffle_regimes,
)


# --------------------------------------------------------------------------- #
# 1. POSITIVE CONTROL — THE load-bearing test.
#
# Plant a perfect regime separation: every SHORT-gamma minute (regime -1) realizes
# a LARGE move, every LONG-gamma minute (regime +1) a SMALL move. Then sep MUST be
# clearly > 0 (short-gamma amplified, long-gamma suppressed = the hypothesis), and
# the control gap (sep_real - mean(shuffled-label sep)) MUST also be > 0. Flip the
# planting -> sep MUST be clearly < 0. A metric that reaches both signs on planted
# data is ALIVE (not stuck at 0); this is what makes a real-data null trustworthy.
# --------------------------------------------------------------------------- #
def test_positive_control_metric_is_alive() -> None:
    # 20 minutes, alternating short/long; short moves 10, long moves 1.
    regimes = [-1, +1] * 10                 # 10 short, 10 long
    moves = [10.0, 1.0] * 10                # short->10.0, long->1.0 (perfectly aligned)

    res = regime_separation(regimes, moves)
    # mean_short=10, mean_long=1, mean_all=(10*10 + 10*1)/20 = 110/20 = 5.5
    assert res["n_short"] == 10
    assert res["n_long"] == 10
    assert res["n_scored"] == 20
    assert res["mean_short"] == pytest.approx(10.0, abs=1e-12)
    assert res["mean_long"] == pytest.approx(1.0, abs=1e-12)
    assert res["mean_all"] == pytest.approx(5.5, abs=1e-12)
    # sep = (10 - 1) / 5.5 = 9/5.5 = 1.6363...  -> clearly > 0 (ALIVE upward).
    assert res["reason"] is None
    assert res["sep"] == pytest.approx(9.0 / 5.5, abs=1e-12)
    assert res["sep"] > 1.0

    # HEADLINE: shuffling the regime labels against the SAME moves destroys the
    # alignment, so the shuffle sep centers on 0 -> the gap stays clearly positive.
    hg = headline_gap(regimes, moves, seeds=DEFAULT_SHUFFLE_SEEDS)
    assert hg["sep_real"] == pytest.approx(9.0 / 5.5, abs=1e-12)
    assert hg["sep_shuffle_mean"] is not None
    assert hg["headline_gap"] is not None
    assert hg["n_seeds"] == len(DEFAULT_SHUFFLE_SEEDS)
    # the gap is the headline and it is POSITIVE (the planted edge survives the control).
    assert hg["headline_gap"] > 0.0
    # ...and the shuffle mean is far below the real sep (not just barely positive).
    assert hg["sep_shuffle_mean"] < res["sep"]


# --------------------------------------------------------------------------- #
# 2. ANTI control — flip the planting -> sep clearly < 0.
#
# Short-gamma minutes now move SMALL, long-gamma minutes LARGE: the OPPOSITE of the
# hypothesis. sep = (mean_short - mean_long)/mean_all must be clearly negative.
# --------------------------------------------------------------------------- #
def test_anti_control_flipped_planting_is_negative() -> None:
    regimes = [-1, +1] * 10
    moves = [1.0, 10.0] * 10                # short->1.0, long->10.0 (anti-aligned)

    res = regime_separation(regimes, moves)
    # mean_short=1, mean_long=10, mean_all=5.5 -> sep = (1-10)/5.5 = -9/5.5 = -1.6363...
    assert res["mean_short"] == pytest.approx(1.0, abs=1e-12)
    assert res["mean_long"] == pytest.approx(10.0, abs=1e-12)
    assert res["sep"] == pytest.approx(-9.0 / 5.5, abs=1e-12)
    assert res["sep"] < -1.0


# --------------------------------------------------------------------------- #
# 3. NULL — regime-shuffle of a FLAT-move series -> headline_gap == 0.
#
# When every scored move is identical, mean_short == mean_long == mean_all for ANY
# labeling, so sep is identically 0 for the real labels AND every shuffle. The gap
# is therefore exactly 0: the metric manufactures NO separation from a flat series.
# --------------------------------------------------------------------------- #
def test_null_flat_move_series_zero_headline_gap() -> None:
    regimes = [-1, +1, -1, +1, -1, +1, -1, +1]
    moves = [4.0] * 8                       # FLAT: every scored move equal

    res = regime_separation(regimes, moves)
    # mean_short = mean_long = mean_all = 4.0 -> sep = (4-4)/4 = 0 exactly.
    assert res["sep"] == pytest.approx(0.0, abs=1e-12)

    hg = headline_gap(regimes, moves, seeds=DEFAULT_SHUFFLE_SEEDS)
    # sep_real == 0 and every shuffle sep == 0 -> gap ~ 0 within tolerance.
    assert hg["sep_real"] == pytest.approx(0.0, abs=1e-12)
    assert hg["sep_shuffle_mean"] == pytest.approx(0.0, abs=1e-12)
    assert hg["headline_gap"] is not None
    assert abs(hg["headline_gap"]) < 1e-9


# --------------------------------------------------------------------------- #
# 4. regime_separation degenerate arms -> sep None with a reason (never a number).
# --------------------------------------------------------------------------- #
def test_regime_separation_all_long_is_degenerate() -> None:
    res = regime_separation([+1, +1, +1], [5.0, 6.0, 7.0])
    assert res["sep"] is None
    assert res["n_short"] == 0
    assert res["n_long"] == 3
    assert "short" in res["reason"]


def test_regime_separation_all_short_is_degenerate() -> None:
    res = regime_separation([-1, -1, -1], [5.0, 6.0, 7.0])
    assert res["sep"] is None
    assert res["n_long"] == 0
    assert res["n_short"] == 3
    assert "long" in res["reason"]


def test_regime_separation_mean_all_zero_is_degenerate() -> None:
    # both sides present, but every scored move is 0 -> mean_all == 0 -> ratio undefined.
    res = regime_separation([-1, +1], [0.0, 0.0])
    assert res["sep"] is None
    assert res["n_short"] == 1
    assert res["n_long"] == 1
    assert res["mean_all"] == 0.0
    assert "mean_all" in res["reason"]


def test_regime_separation_no_scored_minutes_is_degenerate() -> None:
    # all regime-0 minutes, plus a None move -> nothing is scored.
    res = regime_separation([0, 0, -1], [5.0, 6.0, None])
    assert res["sep"] is None
    assert res["n_scored"] == 0
    assert "scored" in res["reason"]


# --------------------------------------------------------------------------- #
# 5. realized_move — |F_{t+k} - F_t|, hand-computed incl. None at boundaries.
# --------------------------------------------------------------------------- #
def test_realized_move_hand_computed_and_boundaries() -> None:
    #            idx:  0      1      2     3      4
    forwards =       [100.0, 103.0, 101.0, None, 105.0]

    # |F1 - F0| = |103 - 100| = 3.0
    assert realized_move(forwards, 0, 1) == pytest.approx(3.0, abs=1e-12)
    # |F2 - F1| = |101 - 103| = 2.0  (abs makes a down-move positive)
    assert realized_move(forwards, 1, 1) == pytest.approx(2.0, abs=1e-12)
    # |F2 - F0| = |101 - 100| = 1.0  (k=2 span)
    assert realized_move(forwards, 0, 2) == pytest.approx(1.0, abs=1e-12)

    # endpoint is None -> None (missing forward, NOT a zero move).
    assert realized_move(forwards, 2, 1) is None      # F3 is None
    assert realized_move(forwards, 1, 2) is None       # F3 is None
    # t+k out of bounds (n=5, index 5 invalid) -> None.
    assert realized_move(forwards, 4, 1) is None
    # negative start index -> None (defensive boundary).
    assert realized_move(forwards, -1, 1) is None


# --------------------------------------------------------------------------- #
# 6. regime_sign — sign of the summed profile, in {-1, 0, +1}.
# --------------------------------------------------------------------------- #
def test_regime_sign_long_short_flat_and_empty() -> None:
    assert regime_sign({5000.0: 10.0, 5010.0: -3.0}) == 1     # sum +7 -> long-gamma
    assert regime_sign({5000.0: -10.0, 5010.0: 3.0}) == -1    # sum -7 -> short-gamma
    assert regime_sign({5000.0: 5.0, 5010.0: -5.0}) == 0      # sum 0 -> flat (unscored)
    assert regime_sign({}) == 0                                # empty -> 0, never errors


# --------------------------------------------------------------------------- #
# 7. shuffle_regimes — deterministic per seed + multiset PRESERVED.
#
# A valid label-null must DESTROY the regime<->move alignment while PRESERVING the
# multiset of labels (count of -1/0/+1), and be deterministic per seed.
# --------------------------------------------------------------------------- #
def test_shuffle_regimes_preserves_multiset() -> None:
    regimes = [-1, +1, 0, -1, +1, +1, 0, -1]   # multiset: 3×-1, 3×+1, 2×0
    shuffled = shuffle_regimes(regimes, 20260612)

    assert len(shuffled) == len(regimes)
    assert Counter(shuffled) == Counter(regimes)
    assert Counter(regimes) == Counter({-1: 3, 1: 3, 0: 2})   # the planted multiset


def test_shuffle_regimes_deterministic_per_seed_and_varies_across_seeds() -> None:
    regimes = [-1, +1, 0, -1, +1, +1, 0, -1]

    # same seed -> byte-identical permutation (reproducible).
    a = shuffle_regimes(regimes, 20260612)
    b = shuffle_regimes(regimes, 20260612)
    assert a == b

    # input is not mutated.
    assert regimes == [-1, +1, 0, -1, +1, +1, 0, -1]

    # different seeds -> generally different permutations (not a constant map).
    variants = {tuple(shuffle_regimes(regimes, sd)) for sd in DEFAULT_SHUFFLE_SEEDS}
    assert len(variants) > 1
