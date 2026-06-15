"""FLUX t->t+k PREDICTIVE evaluation — PURE core (stdlib + locked engine pricing).

This is the *provable* half of a CONTROLLED look-ahead-free predictive test of FLUX
on 0DTE option flow (the data-loading half is the sibling runner ``run_hiro_eval.py``).
It mirrors the ``ddoi_divergence.py`` (pure) + ``run_ddoi_divergence.py`` (runner)
pattern exactly: every function here is deterministic, does NO file IO, and reuses the
locked engine pricing core (``engine.flux``) rather than re-deriving any greek math.

Why a FLUX t->t+k test is LEGITIMATELY look-ahead-free
======================================================
FLUX is, by construction, strictly *t-causal*:

    HIRO_t = Σ_{trade k <= t}  sign(aggressor_k) · δ_k · size_k · M · F_k

Each trade contributes only to minutes at-or-after the minute it printed in, and the
per-minute increment ``delta_hiro_t`` depends ONLY on trades that arrived during minute
``t`` (priced at minute ``t``'s frozen forward). So a test that scores the SIGN of
``delta_hiro_t`` against the SIGN of the FUTURE forward return ``F_{t+k} − F_t`` uses a
predictor built from information available by the close of minute ``t`` and an outcome
realized strictly later (minute ``t+k``). There is no leakage by construction — the
split is asserted in :func:`lead_lag_sign_agreement` (predictor uses ``<= t``, outcome
uses ``> t``). Contrast DDOI, whose ``Σw=0`` whole-day time weight is look-ahead-
contaminated per-minute; FLUX has no such normalization.

Why a RAW hit-rate is meaningless (the controls are the headline)
-----------------------------------------------------------------
A coin-flip predictor scores ~0.5; momentum/persistence alone can push a naive hit-rate
well above 0.5 on trending 0DTE sessions with NO information in the predictor. So the
INFORMATIVE quantities are the GAPS against controls, NOT the raw real hit-rate:

  * SHUFFLED-sign FLUX — same sizes/greeks/timing, aggressor signs permuted (directional
    content destroyed). ``real − mean(shuffle)`` is the directional edge over a predictor
    that has FLUX's magnitude structure but no real direction.
  * SIGNED-VOLUME (no greek) — Σ sign·size; isolates whether the greek (δ) weighting adds
    anything over plain signed order flow.
  * CONTEMPORANEOUS arm — ``delta_hiro_t`` vs the PAST return ``F_t − F_{t−k}``; if FLUX
    merely *reflects* the move that already happened, this scores high while the
    predictive arm does not. ``predictive − contemporaneous`` isolates lead from lag.
  * PERSISTENCE floor — ``sign(F_t − F_{t−k})`` vs ``sign(F_{t+k} − F_t)``; the pure
    momentum baseline a real predictor must beat.

EXPLORATORY: 4 correlated 0DTE days, an OPTION-DERIVED put-call-parity forward (NOT a
futures price). Descriptive only; NOT predictive-validated. The control GAP is the
headline, never the raw hit-rate. Do not read a verdict out of this module.

Only the standard library + the locked engine pricing core are used. No file IO here.
"""
from __future__ import annotations

import math
import os
import random
import sys
from dataclasses import dataclass, replace
from typing import Callable, List, Optional, Sequence

# Engine lives outside the pnpm/py package tree; put its src on the path RELATIVE TO
# THIS FILE (cwd-independent) so the locked pricing core imports cleanly whether this
# module is imported from the repo root, a test, or the sibling runner. (Same idiom as
# ddoi_divergence.py.)
_ENGINE_SRC = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "services", "engine", "src")
)
if _ENGINE_SRC not in sys.path:
    sys.path.insert(0, _ENGINE_SRC)

from engine.flux import (  # noqa: E402  (locked aggressor sign + per-trade greek notional)
    FluxTrade,
    aggressor_sign,
    signed_delta_notional,
)

__all__ = [
    "EvalTrade",
    "per_minute_hiro",
    "signed_volume_series",
    "lead_lag_sign_agreement",
    "contemporaneous_sign_agreement",
    "shuffle_signs",
    "eval_controls",
    "DEFAULT_SHUFFLE_SEEDS",
]

#: A small, FIXED panel of seeds for the directional-destroying shuffle control. Base
#: seed matches analysis/ddoi.py's SHUFFLE_SEED so the falsification control is the same
#: reproducible family used elsewhere in the analysis tree.
DEFAULT_SHUFFLE_SEEDS = (20260612, 20260613, 20260614, 1, 7)


@dataclass(frozen=True)
class EvalTrade:
    """One option trade tagged with its RTH MINUTE INDEX (the look-ahead-free clock).

    ``minute`` is the 0-based RTH minute the trade printed in (minute 0 == the bar
    [09:30, 09:31) ET). ``trade`` is the locked-engine :class:`engine.flux.FluxTrade`
    carrying ``strike``/``is_call``/``price``/``size``/``side``/``t_expiry`` — i.e. the
    pricing core consumes it directly via :func:`engine.flux.signed_delta_notional`,
    no greek re-implementation here.
    """

    minute: int
    trade: FluxTrade


# --------------------------------------------------------------------------- #
# 1. Per-minute incremental FLUX (the t-causal predictor)
# --------------------------------------------------------------------------- #
def per_minute_hiro(
    eval_trades: Sequence[EvalTrade],
    minute_forwards: Sequence[Optional[float]],
    M: float,
    rate: float,
) -> dict:
    """Per-minute cumulative FLUX and its per-minute increment, built INCREMENTALLY.

    LOOK-AHEAD-FREE CONTRACT (load-bearing): a trade that printed in minute ``m``
    contributes ONLY to minute ``m``'s increment and, cumulatively, to every minute
    ``>= m`` — never to an earlier minute. Each trade is priced at the FROZEN forward of
    the minute it printed in (``minute_forwards[m]``), the "freeze-per-minute-forward"
    rule: this forward is observable by the close of minute ``m`` (contemporaneous with
    the trade), so the increment ``delta[m]`` is fully determined by information
    available at the end of minute ``m``. No future forward ever enters ``delta[m]``.

    FLUX is an additive sum, so the within-minute trade order does not change either the
    end-of-minute cumulative value or the per-minute increment (commutative).

    Parameters
    ----------
    eval_trades      : chronological :class:`EvalTrade` sequence (any order is fine for
                       the SUM, but chronological keeps it deterministic + auditable).
    minute_forwards  : per-minute forward grid (``None`` where no clean forward exists);
                       its length defines the number of RTH minutes ``n``.
    M, rate          : instrument multiplier and continuous rate, passed straight to
                       :func:`engine.flux.signed_delta_notional` (no hardcoding).

    Returns a dict:
      * ``cumulative`` — ``HIRO_t`` (delta-notional, USD) at the END of each minute.
      * ``delta``      — ``delta_hiro_t = HIRO_t − HIRO_{t−1}`` per minute (the predictor).
      * ``n_trades`` / ``n_used`` / ``n_neutral`` / ``n_iv_skip`` / ``n_no_forward`` —
        accounting so the runner can surface skipped-trade and aggressor-neutral
        fractions (a structurally-meaningless test must be SURFACED, not hidden).

    A trade is skipped (and counted) when: its minute has no forward (``n_no_forward``),
    its aggressor side is neutral ``N`` (``n_neutral``), or its IV cannot be solved from
    the trade price (``n_iv_skip``). Skipped trades contribute 0 to that minute.
    """
    n = len(minute_forwards)
    delta = [0.0] * n
    n_trades = 0
    n_used = 0
    n_neutral = 0
    n_iv_skip = 0
    n_no_forward = 0

    for et in eval_trades:
        m = et.minute
        if m < 0 or m >= n:
            continue
        n_trades += 1
        F = minute_forwards[m]
        if F is None:
            n_no_forward += 1
            continue
        # Distinguish neutral (no aggressor direction) from IV-unsolved, using the locked
        # engine sign map (not a re-impl) so the accounting is honest.
        if aggressor_sign(et.trade.side) == 0:
            n_neutral += 1
            continue
        dn = signed_delta_notional(et.trade, float(F), M, rate)
        if dn is None:
            n_iv_skip += 1
            continue
        delta[m] += dn
        n_used += 1

    cumulative = [0.0] * n
    running = 0.0
    for m in range(n):
        running += delta[m]
        cumulative[m] = running

    return {
        "cumulative": cumulative,
        "delta": delta,
        "n_trades": n_trades,
        "n_used": n_used,
        "n_neutral": n_neutral,
        "n_iv_skip": n_iv_skip,
        "n_no_forward": n_no_forward,
    }


# --------------------------------------------------------------------------- #
# 2. Signed-volume control (NO greek)
# --------------------------------------------------------------------------- #
def signed_volume_series(
    eval_trades: Sequence[EvalTrade],
    n_minutes: int,
) -> dict:
    """Per-minute signed order-flow controls that use NO greek (the δ-free baseline).

    Two predictors, both built minute-causally (a trade contributes only to its own
    minute's increment), reusing the locked :func:`engine.flux.aggressor_sign`:

      * ``signed_vol``    = Σ sign(aggressor)·size       — plain signed order flow. Its
        per-minute delta isolates whether the Black-76 δ weighting in FLUX adds anything
        over raw signed volume.
      * ``sign_dir_vol``  = Σ sign(aggressor)·size·dir   — where ``dir = +1`` for a call,
        ``−1`` for a put. A cheap directional proxy (buying calls is bullish, buying puts
        bearish) that mimics the SIGN of FLUX's δ weighting without its magnitude.

    Returns a dict with the per-minute cumulative and delta arrays for both predictors:
    ``cum_signed_vol`` / ``delta_signed_vol`` and ``cum_sign_dir_vol`` /
    ``delta_sign_dir_vol``.
    """
    delta_sv = [0.0] * n_minutes
    delta_sdv = [0.0] * n_minutes
    for et in eval_trades:
        m = et.minute
        if m < 0 or m >= n_minutes:
            continue
        s = aggressor_sign(et.trade.side)
        if s == 0:
            continue
        size = float(et.trade.size)
        delta_sv[m] += s * size
        dir_sign = 1.0 if et.trade.is_call else -1.0
        delta_sdv[m] += s * size * dir_sign

    def _cumsum(arr: List[float]) -> List[float]:
        out = [0.0] * len(arr)
        run = 0.0
        for i, v in enumerate(arr):
            run += v
            out[i] = run
        return out

    return {
        "cum_signed_vol": _cumsum(delta_sv),
        "delta_signed_vol": delta_sv,
        "cum_sign_dir_vol": _cumsum(delta_sdv),
        "delta_sign_dir_vol": delta_sdv,
    }


# --------------------------------------------------------------------------- #
# pure sign / return primitives
# --------------------------------------------------------------------------- #
def _sign(x: Optional[float]) -> Optional[int]:
    """Sign in {−1,0,+1}, or None for a missing value (so callers can skip it)."""
    if x is None:
        return None
    return 1 if x > 0.0 else (-1 if x < 0.0 else 0)


def _window_return(forwards: Sequence[Optional[float]], a: int, b: int) -> Optional[float]:
    """Forward return ``forwards[b] − forwards[a]``; None if an endpoint is OOB/missing."""
    n = len(forwards)
    if a < 0 or b < 0 or a >= n or b >= n:
        return None
    fa = forwards[a]
    fb = forwards[b]
    if fa is None or fb is None:
        return None
    return fb - fa


def _agree(
    predictor: Sequence[Optional[float]],
    outcome_fn: Callable[[int], Optional[float]],
    n: int,
) -> dict:
    """Sign-agreement hit-rate of ``predictor[t]`` vs ``outcome_fn(t)`` over t in [0, n).

    The single scoring kernel behind every arm. A minute ``t`` is SCORED only when both
    the predictor sign and the outcome sign are well-defined and NON-ZERO; a zero or
    missing sign on either side is SKIPPED (documented choice: a zero predictor is "no
    directional call", a zero outcome is "no realized direction" — neither is a hit or a
    miss). Returns ``{"hit_rate", "n", "hits"}`` (``hit_rate`` NaN when ``n == 0``).
    """
    hits = 0
    cnt = 0
    for t in range(n):
        ps = _sign(predictor[t]) if t < len(predictor) else None
        if ps is None or ps == 0:
            continue
        rs = _sign(outcome_fn(t))
        if rs is None or rs == 0:
            continue
        cnt += 1
        if ps == rs:
            hits += 1
    return {"hit_rate": hits / cnt if cnt else float("nan"), "n": cnt, "hits": hits}


# --------------------------------------------------------------------------- #
# 3. The core lead-lag metric (STRICTLY t -> t+k)
# --------------------------------------------------------------------------- #
def lead_lag_sign_agreement(
    predictor_delta: Sequence[Optional[float]],
    forward_prices: Sequence[Optional[float]],
    k: int,
) -> dict:
    """PREDICTIVE sign agreement: ``sign(predictor_delta_t)`` vs ``sign(F_{t+k} − F_t)``.

    STRICTLY t -> t+k and LOOK-AHEAD-FREE by construction: the predictor at minute ``t``
    is built from trades with arrival ``<= t`` (see :func:`per_minute_hiro`), while the
    outcome forward return ``F_{t+k} − F_t`` is realized at minute ``t+k > t``. The two
    information sets never overlap. ``k`` is in MINUTES on the per-minute grid.

    Zero/missing signs are skipped (see :func:`_agree`). Returns ``{"hit_rate","n","hits"}``.
    """
    n = len(forward_prices)
    return _agree(predictor_delta, lambda t: _window_return(forward_prices, t, t + k), n)


def contemporaneous_sign_agreement(
    predictor_delta: Sequence[Optional[float]],
    forward_prices: Sequence[Optional[float]],
    k: int,
) -> dict:
    """CONTEMPORANEOUS (lag) arm: ``sign(predictor_delta_t)`` vs the PAST return.

    Scores the predictor at minute ``t`` against ``sign(F_t − F_{t−k})`` — the move that
    ALREADY happened. This is deliberately NOT predictive: if FLUX merely *reflects* the
    realized move (dealers hedging after the fact), this arm scores high while the
    forward-looking :func:`lead_lag_sign_agreement` does not. ``predictive −
    contemporaneous`` therefore isolates genuine lead from mechanical lag.
    """
    n = len(forward_prices)
    return _agree(predictor_delta, lambda t: _window_return(forward_prices, t - k, t), n)


# --------------------------------------------------------------------------- #
# 4. Directional-destroying control: per-trade aggressor-sign shuffle
# --------------------------------------------------------------------------- #
def shuffle_signs(eval_trades: Sequence[EvalTrade], seed: int) -> List[EvalTrade]:
    """Deterministic per-trade aggressor-SIGN permutation (the falsification control).

    Mirrors the ddoi shuffle pattern (a single seeded :class:`random.Random`). The
    multiset of aggressor signs over the day is PRESERVED but reassigned to different
    trades, so every trade keeps its own ``size``/greek inputs (``strike``/``is_call``/
    ``price``/``t_expiry``) and its ``minute`` — only the DIRECTION is randomized. This
    destroys the alignment between flow direction and the option's δ while leaving FLUX's
    magnitude structure intact, so ``real − mean(shuffle)`` measures the directional edge
    specifically. Signs are re-encoded back to CME side codes (``+1->"B"``, ``−1->"A"``,
    ``0->"N"``) so the shuffled trades feed the SAME locked pricing path unchanged.
    """
    signs = [aggressor_sign(et.trade.side) for et in eval_trades]
    perm = list(signs)
    random.Random(seed).shuffle(perm)
    out: List[EvalTrade] = []
    for et, sgn in zip(eval_trades, perm):
        side = "B" if sgn > 0 else ("A" if sgn < 0 else "N")
        out.append(EvalTrade(et.minute, replace(et.trade, side=side)))
    return out


# --------------------------------------------------------------------------- #
# 5. The full control panel for one (day, instrument, k)
# --------------------------------------------------------------------------- #
def eval_controls(
    eval_trades: Sequence[EvalTrade],
    minute_forwards: Sequence[Optional[float]],
    M: float,
    rate: float,
    k: int,
    *,
    seeds: Sequence[int] = DEFAULT_SHUFFLE_SEEDS,
) -> dict:
    """Compute the REAL hit-rate plus every control and the two HEADLINE GAPS for one k.

    Arms (all on the SAME per-minute forward grid, all STRICTLY t->t+k where predictive):
      * REAL           — ``delta_hiro_t`` (greek-weighted) -> future return.
      * SHUFFLE        — REAL pipeline on sign-shuffled trades, once per seed; reported as
                         mean + [min, max] spread (the directional-null band).
      * SIGNED-VOLUME  — Σ sign·size (no greek) -> future return.
      * SIGN-DIR-VOL   — Σ sign·size·dir (no greek magnitude) -> future return.
      * CONTEMPORANEOUS— ``delta_hiro_t`` vs the PAST return ``F_t − F_{t−k}``.
      * PERSISTENCE    — ``sign(F_{t−k}->F_t)`` -> future return (pure momentum floor).

    HEADLINE GAPS (the only things worth reading at n=4):
      * ``real_minus_shuffle``        = real − mean(shuffle).
      * ``predictive_minus_contemp``  = real − contemporaneous.

    Returns a flat dict (NaN-safe) plus the trade-accounting fractions so the runner can
    surface skipped-trade and aggressor-neutral fractions and the per-row sample size.
    """
    n = len(minute_forwards)

    real = per_minute_hiro(eval_trades, minute_forwards, M, rate)
    real_score = lead_lag_sign_agreement(real["delta"], minute_forwards, k)

    shuffle_hits: List[float] = []
    for sd in seeds:
        sh = shuffle_signs(eval_trades, sd)
        shp = per_minute_hiro(sh, minute_forwards, M, rate)
        shuffle_hits.append(
            lead_lag_sign_agreement(shp["delta"], minute_forwards, k)["hit_rate"]
        )
    valid_sh = [h for h in shuffle_hits if not math.isnan(h)]
    shuffle_mean = sum(valid_sh) / len(valid_sh) if valid_sh else float("nan")
    shuffle_min = min(valid_sh) if valid_sh else float("nan")
    shuffle_max = max(valid_sh) if valid_sh else float("nan")

    sv = signed_volume_series(eval_trades, n)
    sv_score = lead_lag_sign_agreement(sv["delta_signed_vol"], minute_forwards, k)
    sdv_score = lead_lag_sign_agreement(sv["delta_sign_dir_vol"], minute_forwards, k)

    contemp = contemporaneous_sign_agreement(real["delta"], minute_forwards, k)

    persist_pred: List[Optional[float]] = [
        _window_return(minute_forwards, t - k, t) for t in range(n)
    ]
    persist = lead_lag_sign_agreement(persist_pred, minute_forwards, k)

    real_hit = real_score["hit_rate"]
    real_minus_shuffle = (
        real_hit - shuffle_mean
        if not (math.isnan(real_hit) or math.isnan(shuffle_mean))
        else float("nan")
    )
    contemp_hit = contemp["hit_rate"]
    predictive_minus_contemp = (
        real_hit - contemp_hit
        if not (math.isnan(real_hit) or math.isnan(contemp_hit))
        else float("nan")
    )

    n_trades = real["n_trades"]
    skipped = real["n_neutral"] + real["n_iv_skip"] + real["n_no_forward"]
    return {
        "k": k,
        "n": real_score["n"],
        "real_hit": real_hit,
        "shuffle_hits": shuffle_hits,
        "shuffle_mean": shuffle_mean,
        "shuffle_min": shuffle_min,
        "shuffle_max": shuffle_max,
        "signed_vol_hit": sv_score["hit_rate"],
        "signed_vol_n": sv_score["n"],
        "sign_dir_vol_hit": sdv_score["hit_rate"],
        "contemp_hit": contemp_hit,
        "contemp_n": contemp["n"],
        "persistence_hit": persist["hit_rate"],
        "persistence_n": persist["n"],
        "real_minus_shuffle": real_minus_shuffle,
        "predictive_minus_contemp": predictive_minus_contemp,
        "n_trades": n_trades,
        "n_used": real["n_used"],
        "skipped_frac": (skipped / n_trades) if n_trades else float("nan"),
        "neutral_frac": (real["n_neutral"] / n_trades) if n_trades else float("nan"),
        "no_forward_frac": (real["n_no_forward"] / n_trades) if n_trades else float("nan"),
    }
