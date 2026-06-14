"""Synthetic-OI VOLATILITY-REGIME eval — PURE core (stdlib only, deterministic).

This is the *provable* half of a 0DTE, EXPLORATORY evaluation of synthetic-OI as a
VOLATILITY-REGIME predictor — NOT a directional one (the data-loading half is the
sibling runner ``run_synthetic_oi_regime_eval.py``, a separate later step). It mirrors
the ``hiro_eval.py`` (pure) + ``run_hiro_eval.py`` (runner) + ``test_*`` pattern exactly:
every function here is deterministic, does NO file IO, and is built from small stdlib
primitives (the per-minute synthetic-GEX *profile* is built UPSTREAM by the runner via
``analysis.harness.synthetic_oi_eval.synthetic_gex_by_strike`` — the sign-free aggregator —
and only its SIGN enters this module).

The hypothesis (regime, NOT direction)
======================================
Net dealer gamma is a *volatility-regime* indicator, not a price-direction one:

  * LONG-gamma  (Σ synthetic-GEX > 0, ``regime = +1``)  ⇒ dealers SUPPRESS volatility
    (they sell into rallies / buy dips to stay hedged) ⇒ SMALL subsequent moves.
  * SHORT-gamma (Σ synthetic-GEX < 0, ``regime = -1``)  ⇒ dealers AMPLIFY volatility
    (they chase the move) ⇒ LARGE subsequent moves.

So the OUTCOME is a SIGN-FREE realized MOVE MAGNITUDE ``|F_{t+k} − F_t|`` (NOT a signed
return — direction is explicitly not claimed), and the metric is the regime SEPARATION:

    sep = ( mean(move | short-gamma) − mean(move | long-gamma) ) / mean(move | all scored)

``sep > 0`` is the hypothesised ordering (short-gamma minutes move MORE than long-gamma
minutes). Because ``mean_all`` normalises out the day's overall volatility level, ``sep``
is comparable across days.

Why a RAW ``sep`` is NOT the headline (the control gap is)
----------------------------------------------------------
A day with ANY persistent volatility clustering can produce a non-zero ``sep`` even if
the regime label carries no information (e.g. if quiet minutes happen to cluster). The
INFORMATIVE quantity is therefore the GAP against a regime-label-shuffle null
(:func:`shuffle_regimes`): ``headline_gap = sep_real − mean(sep | shuffled-labels)``. The
shuffle preserves the multiset of regime labels and the move series but destroys the
ALIGNMENT between which minutes are long/short and which minutes moved — so a positive
``headline_gap`` is edge SPECIFICALLY from the regime labelling, not from clustering.

Look-ahead-free split (enforced by the RUNNER, not here)
--------------------------------------------------------
T-CAUSALITY is the RUNNER's responsibility: the regime PREDICTOR at minute ``t`` must be
built from a PRIOR-day OI anchor + aggressor flow accumulated ``<= t`` (the same
``synthetic_gex_by_strike`` inputs used elsewhere), while the OUTCOME ``|F_{t+k} − F_t|``
is realized strictly later (forwards ``> t``). This pure module only consumes the already-
split ``regimes`` (predictor signs) and ``forwards`` (outcome grid); it cannot leak.

EXPLORATORY: a few correlated 0DTE days, an option-derived forward (NOT a futures price),
descriptive only, NOT predictive-validated. The HEADLINE is the control GAP, never the
raw ``sep``. At small n the result is expected to be UNDETERMINED — do not read a verdict
out of this module.

Only the standard library is used. No file IO here.
"""
from __future__ import annotations

import math
import random
from typing import List, Mapping, Optional, Sequence

__all__ = [
    "DEFAULT_SHUFFLE_SEEDS",
    "regime_sign",
    "realized_move",
    "regime_separation",
    "shuffle_regimes",
    "headline_gap",
]

#: A small, FIXED panel of seeds for the regime-label-shuffle null. Base seed matches
#: analysis/ddoi.py / hiro_eval.py / synthetic_oi_eval.py so the falsification control is
#: the same reproducible family used elsewhere in the analysis tree.
DEFAULT_SHUFFLE_SEEDS = (20260612, 20260613, 20260614, 1, 7)


# --------------------------------------------------------------------------- #
# 1. Regime label from a per-minute synthetic-GEX profile (the predictor sign)
# --------------------------------------------------------------------------- #
def regime_sign(profile_gex_by_strike: Mapping[float, float]) -> int:
    """Volatility-regime label = ``sign( Σ synthetic-GEX )`` in ``{-1, 0, +1}``.

    The runner builds the per-minute, sign-free synthetic-GEX *profile* via
    :func:`analysis.harness.synthetic_oi_eval.synthetic_gex_by_strike` (which already
    carries the dealer sign inside ``q_per_leg``); this function only takes the SIGN of
    its total net dealer gamma:

      * ``+1`` — LONG-gamma (Σ > 0): dealers SUPPRESS volatility ⇒ small moves expected.
      * ``-1`` — SHORT-gamma (Σ < 0): dealers AMPLIFY volatility ⇒ large moves expected.
      * ``0``  — flat / empty profile: UNSCORED (no regime call this minute).

    Pure: an empty mapping sums to ``0.0`` ⇒ ``0`` (correctly unscored), never an error.
    """
    total = sum(profile_gex_by_strike.values())
    return 1 if total > 0.0 else (-1 if total < 0.0 else 0)


# --------------------------------------------------------------------------- #
# pure return / move primitives (mirror hiro_eval._window_return semantics)
# --------------------------------------------------------------------------- #
def _window_return(forwards: Sequence[Optional[float]], a: int, b: int) -> Optional[float]:
    """Forward return ``forwards[b] − forwards[a]``; None if an endpoint is OOB/missing.

    Byte-for-byte the same semantics as :func:`analysis.harness.hiro_eval._window_return`
    (re-declared locally so this module stays stdlib-only and self-contained, the same way
    ``hiro_eval`` and ``synthetic_oi_eval`` each carry their own tiny ``_sign`` primitive).
    """
    n = len(forwards)
    if a < 0 or b < 0 or a >= n or b >= n:
        return None
    fa = forwards[a]
    fb = forwards[b]
    if fa is None or fb is None:
        return None
    return fb - fa


def realized_move(
    forwards: Sequence[Optional[float]], t: int, k: int
) -> Optional[float]:
    """SIGN-FREE realized move magnitude ``|F_{t+k} − F_t|`` (the regime OUTCOME).

    Reuses the :func:`_window_return` semantics (``forwards[t+k] − forwards[t]``) then takes
    the absolute value: direction is explicitly NOT part of this hypothesis, only SIZE.
    Returns ``None`` when either endpoint is out-of-bounds or missing — propagated so the
    minute is skipped in :func:`regime_separation`, never counted as a zero move.
    """
    r = _window_return(forwards, t, t + k)
    return abs(r) if r is not None else None


# --------------------------------------------------------------------------- #
# 2. The core separation metric (regime vs realized move magnitude)
# --------------------------------------------------------------------------- #
def _mean(vals: Sequence[float]) -> Optional[float]:
    """Arithmetic mean, or None for an empty group (so degenerate arms are explicit)."""
    return (sum(vals) / len(vals)) if vals else None


def regime_separation(
    regimes: Sequence[int], moves: Sequence[Optional[float]]
) -> dict:
    """Volatility separation of SHORT-gamma vs LONG-gamma minutes (the core metric).

    A minute ``i`` is SCORED only when its regime is directional (``regimes[i] != 0``) AND
    its outcome move is defined (``moves[i] is not None``). Over the scored minutes::

        sep = ( mean(move | regime < 0)  −  mean(move | regime > 0) ) / mean(move | all)

    ``sep > 0`` is the hypothesised ordering: short-gamma (``regime < 0``) minutes move MORE
    than long-gamma (``regime > 0``) minutes (dealers amplify vs suppress). ``mean_all``
    normalises out the day's overall volatility so ``sep`` is comparable across days.

    DEGENERATE arms return ``sep = None`` with a human-readable ``reason`` (never a fake
    number): no short-gamma minutes, no long-gamma minutes, no scored minutes at all, or a
    zero ``mean_all`` (every scored move is exactly 0 ⇒ the ratio is undefined). Callers
    (e.g. :func:`headline_gap`) must treat ``sep is None`` as "this arm did not score".

    Returns ``{sep, reason, n_short, n_long, n_scored, mean_short, mean_long, mean_all}``.
    ``mean_short`` / ``mean_long`` are ``None`` for an empty side; ``reason`` is ``None``
    when ``sep`` is a real number.
    """
    short_moves: List[float] = []
    long_moves: List[float] = []
    all_moves: List[float] = []
    for reg, mv in zip(regimes, moves):
        if reg == 0 or mv is None:
            continue
        m = float(mv)
        all_moves.append(m)
        if reg < 0:
            short_moves.append(m)
        else:
            long_moves.append(m)

    n_short = len(short_moves)
    n_long = len(long_moves)
    n_scored = len(all_moves)
    mean_short = _mean(short_moves)
    mean_long = _mean(long_moves)
    mean_all = _mean(all_moves)

    reason: Optional[str] = None
    if n_scored == 0:
        reason = "no scored minutes (every minute is regime 0 or has no move)"
    elif n_short == 0:
        reason = "no short-gamma minutes (cannot estimate the amplified arm)"
    elif n_long == 0:
        reason = "no long-gamma minutes (cannot estimate the suppressed arm)"
    elif mean_all == 0.0:
        reason = "mean_all is zero (every scored move is exactly 0; ratio undefined)"

    sep: Optional[float]
    if reason is not None:
        sep = None
    else:
        # all three means are real numbers here (guarded above).
        sep = (mean_short - mean_long) / mean_all  # type: ignore[operator]

    return {
        "sep": sep,
        "reason": reason,
        "n_short": n_short,
        "n_long": n_long,
        "n_scored": n_scored,
        "mean_short": mean_short,
        "mean_long": mean_long,
        "mean_all": mean_all,
    }


# --------------------------------------------------------------------------- #
# 3. Regime-label-shuffle null (the falsification control)
# --------------------------------------------------------------------------- #
def shuffle_regimes(regimes: Sequence[int], seed: int) -> List[int]:
    """Deterministic permutation of the regime LABELS (the regime-label-shuffle null).

    Mirrors :func:`analysis.harness.hiro_eval.shuffle_signs` (a single seeded
    :class:`random.Random`). The multiset of regime labels ``{-1, 0, +1}`` over the day is
    PRESERVED but reassigned to different minutes, so the moves series and the per-day
    counts of long/short/flat minutes are invariant while the ALIGNMENT between regime and
    realized move is destroyed. Feeding the shuffled labels through :func:`regime_separation`
    against the SAME (unshuffled) moves yields the regime-label null ``sep``; the real
    ``sep`` must beat its mean for any regime edge to exist.

    Deterministic per ``seed`` and does not mutate the input.
    """
    perm = list(regimes)
    random.Random(seed).shuffle(perm)
    return perm


# --------------------------------------------------------------------------- #
# 4. The headline control GAP (never the raw sep)
# --------------------------------------------------------------------------- #
def _pstdev(vals: Sequence[float], mean: float) -> float:
    """Population standard deviation about ``mean`` (0.0 for a single value)."""
    return math.sqrt(sum((v - mean) ** 2 for v in vals) / len(vals)) if vals else float("nan")


def headline_gap(
    regimes: Sequence[int],
    moves: Sequence[Optional[float]],
    seeds: Sequence[int] = DEFAULT_SHUFFLE_SEEDS,
) -> dict:
    """The HEADLINE control gap: ``sep_real − mean( sep | regime-label shuffle )``.

    Computes the real :func:`regime_separation` ``sep``, then re-computes ``sep`` once per
    seed on :func:`shuffle_regimes`-permuted labels (against the SAME moves), and reports
    the gap. This — NOT the raw ``sep`` — is the only quantity worth reading: it is the
    regime-labelling edge over a null that keeps the day's volatility clustering but
    scrambles which minutes are long/short.

    Shuffle ``sep`` values that come back ``None`` (a degenerate shuffle arm) are SKIPPED
    in the mean/std. If ``sep_real is None`` or no shuffle scored, ``headline_gap`` is
    ``None`` (the arm is UNDETERMINED — expected at small n).

    Returns ``{sep_real, sep_shuffle_mean, sep_shuffle_std, headline_gap, n_seeds}``.
    """
    sep_real = regime_separation(regimes, moves)["sep"]

    shuffle_seps: List[float] = []
    for sd in seeds:
        s = regime_separation(shuffle_regimes(regimes, sd), moves)["sep"]
        if s is not None:
            shuffle_seps.append(s)

    sep_shuffle_mean = _mean(shuffle_seps)
    sep_shuffle_std = (
        _pstdev(shuffle_seps, sep_shuffle_mean)
        if sep_shuffle_mean is not None
        else None
    )

    gap: Optional[float]
    if sep_real is None or sep_shuffle_mean is None:
        gap = None
    else:
        gap = sep_real - sep_shuffle_mean

    return {
        "sep_real": sep_real,
        "sep_shuffle_mean": sep_shuffle_mean,
        "sep_shuffle_std": sep_shuffle_std,
        "headline_gap": gap,
        "n_seeds": len(seeds),
    }
