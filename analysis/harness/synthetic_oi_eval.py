"""Synthetic-OI #4 FLOW-TERM structural eval — PURE core (stdlib + locked engine).

This is the *provable* half of a 0DTE, STRUCTURAL (NOT predictive) controlled
evaluation of the ONE thing synthetic-OI #4 uniquely claims over pure OI-GEX (the
data-loading half is the sibling runner ``run_synthetic_oi_eval.py``). It mirrors the
``ddoi_divergence.py`` (pure) + ``run_ddoi_divergence.py`` (runner) + ``test_*`` pattern
exactly: every function here is deterministic, does NO file IO, and reuses the LOCKED
engine position model (``engine.synthetic_oi.q_per_leg``) rather than re-deriving any
greek/sign math.

The ONE question (structural, look-ahead-free, EOD)
===================================================
Synthetic-OI #4 per leg is ``Q = s_static·OI_open + (−net_aggressor_flow)·w`` (see
``engine/synthetic_oi.py``). At ``w=0`` it is PURE OI-GEX (SpotGamma-classic); at ``w=1``
the native-aggressor FLOW term ``(−flow)·w`` is fully added. The engine only ever emits a
SCALAR ``synthetic_gex`` (summed over strikes). This module asks, PER STRIKE:

    Does the native-aggressor FLOW term add per-strike STRUCTURE over pure OI-GEX, or is
    the ``w=1`` profile just a scalar rescale of the ``w=0`` profile (a null)?

OI here is END-OF-DAY settled only, so this is an END-OF-SESSION STRUCTURAL comparison —
there is NO predictive arm (intraday OI would be look-ahead) and therefore NO hit-rate /
NO "55%" for this structural arm. Nothing is scored against price.

The SIGN-FREE per-strike aggregator (why we do NOT reuse ddoi_divergence.gex_by_strike)
=======================================================================================
``ddoi_divergence.gex_by_strike`` RE-APPLIES ``DEALER_SIGN_PUT = −1`` to the put basis
(its flow map is unsigned). But the synthetic-OI ``Q`` ALREADY carries the dealer sign
(baked in at ``engine.synthetic_oi.q_per_leg``: ``q_put = DEALER_SIGN_PUT·OI + (−flow)·w``).
Feeding ``Q`` into ``gex_by_strike`` would DOUBLE-SIGN the puts and manufacture fake
divergence. So :func:`synthetic_gex_by_strike` is a NEW sign-free aggregator that consumes
``q_per_leg`` directly and adds NO further dealer sign.

CORRECTNESS ANCHOR (locked by the test-author): for any ``rows``/``net_flow``/``w``,

    sum(synthetic_gex_by_strike(rows, net_flow, M, F, w).values())
        == engine.synthetic_oi.synthetic_gex(rows, net_flow, M, F, w)   (math.isclose)

because both reuse the SAME ``q_per_leg`` Q, the SAME ``M·F²·GEX_PCT_SCALE`` scale, and
the SAME thin-skip rule. If that identity ever breaks, the aggregator is wrong.

The controls that make the comparison mean something
----------------------------------------------------
High similarity between the ``w=1`` and ``w=0`` profiles is EXPECTED — they share the
SAME per-strike gammas AND the SAME ``s_static·OI`` stock anchor; only the additive
``(−flow)·w`` term differs. So the meaningful quantities are:

  * ``residual_r2`` of the scalar-multiple fit ``gex ≈ c·static`` — HIGH ⇒ flow is just a
    rescale of OI (no new structure = a null).
  * ``flow_norm_ratio`` = ‖gex − static‖₂ / ‖static‖₂ — how big the flow term is relative
    to pure OI (the headline magnitude the DDOI metrics never compute).
  * ``argmax_distance`` — does the flow term MOVE the dominant strike?
  * SHUFFLE-FLOW control (:func:`shuffle_flow_signs`) — the aggressor SIGN of each trade is
    permuted, destroying flow DIRECTION while preserving its magnitude/timing/strike
    distribution. The real flow term must beat this same-magnitude random-sign NULL on
    ``flow_norm_ratio`` / ``argmax_distance`` to carry any directional structure.

EXPLORATORY: 4 correlated 0DTE days, EOD STRUCTURAL only, NOT predictive, NOT validated.
Do not read a verdict out of this module.

Only the standard library + the locked engine position model are used. No file IO here.
"""
from __future__ import annotations

import math
import os
import random
import sys
from dataclasses import dataclass
from typing import List, Mapping, Optional, Sequence, Tuple

# Engine lives outside the pnpm/py package tree; put its src on the path RELATIVE TO
# THIS FILE (cwd-independent) so the locked position model + GEX scale import cleanly
# whether this module is imported from the repo root, a test, or the sibling runner.
# (Same idiom as ddoi_divergence.py / flux_eval.py.)
_ENGINE_SRC = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "services", "engine", "src")
)
if _ENGINE_SRC not in sys.path:
    sys.path.insert(0, _ENGINE_SRC)

from engine.exposure import GEX_PCT_SCALE  # noqa: E402  (locked GEX scale, not hardcoded)
from engine.synthetic_oi import (  # noqa: E402  (locked #4 per-leg Q + #6 size-tiering)
    BLOCK_MIN_SIZE,
    BLOCK_TIER_WEIGHT,
    RETAIL_MAX_SIZE,
    RETAIL_TIER_WEIGHT,
    q_per_leg,
    tier_weight,
)

__all__ = [
    "FlowKey",
    "FlowTrade",
    "DEFAULT_SHUFFLE_SEEDS",
    "net_flow_from_trades",
    "tiered_net_flow_from_trades",
    "synthetic_gex_by_strike",
    "flow_term_metrics",
    "shuffle_flow_signs",
    "eval_flow_term",
    "eval_tiered_term",
]

#: Per-leg key for the net-aggressor-flow map: (strike, is_call). Matches
#: engine.synthetic_oi.FlowKey exactly (strike is a float).
FlowKey = Tuple[float, bool]

#: A small, FIXED panel of seeds for the directional-destroying flow-sign shuffle. Base
#: seed matches analysis/ddoi.py / flux_eval.py so the falsification control is the same
#: reproducible family used elsewhere in the analysis tree.
DEFAULT_SHUFFLE_SEEDS = (20260612, 20260613, 20260614, 1, 7)


@dataclass(frozen=True)
class FlowTrade:
    """One aggressor-signed option trade for the EOD net-flow build.

    ``sign`` is the native CME aggressor sign in ``{-1, 0, +1}`` (B=+1, A=-1, N=0); the
    customer-aggressor convention is the engine's (``engine.synthetic_oi`` applies the
    ``-flow`` dealer-opposite inside ``q_per_leg``, so we do NOT negate here). ``size`` is
    the trade size (>= 0). The signed contribution to a leg's net flow is ``sign·size``.
    Carrying the per-trade sign (not a pre-summed net_flow) is what makes the per-trade
    :func:`shuffle_flow_signs` control faithful.
    """

    strike: float
    is_call: bool
    size: float
    sign: int


def net_flow_from_trades(trades: Sequence[FlowTrade]) -> dict:
    """Σ ``sign·size`` per ``(strike, is_call)`` leg — the #4 ``net_aggressor_flow`` map.

    Deterministic; keys are ``(float(strike), is_call)`` so they match the ``row.strike``
    lookup inside :func:`engine.synthetic_oi.q_per_leg`. This is the SAME quantity
    ``run_validation.flow_and_vol`` accumulates (Σ aggressor_sign·size since the RTH open),
    just built end-of-session from the whole-day tape.
    """
    out: dict = {}
    for t in trades:
        key = (float(t.strike), bool(t.is_call))
        out[key] = out.get(key, 0.0) + float(t.sign) * float(t.size)
    return out


def _resolve_block_min(instrument: str, block_min: Optional[float]) -> float:
    """Per-instrument block-size floor: explicit ``block_min`` wins, else the locked
    engine default ``engine.synthetic_oi.BLOCK_MIN_SIZE[instrument]`` (/ES 50, /NQ 25)."""
    if block_min is not None:
        return float(block_min)
    return float(BLOCK_MIN_SIZE[instrument])


def tiered_net_flow_from_trades(
    trades: Sequence[FlowTrade],
    instrument: str,
    *,
    retail_max: float = RETAIL_MAX_SIZE,
    block_min: Optional[float] = None,
    retail_weight: float = RETAIL_TIER_WEIGHT,
    block_weight: float = BLOCK_TIER_WEIGHT,
) -> dict:
    """Σ ``sign·size·tier_weight(size)`` per leg — the synthetic-OI #6 size-TIERED flow map.

    The size-tier multiplier is the LOCKED ``engine.synthetic_oi.tier_weight`` (imported,
    NOT reimplemented): ``size <= retail_max`` -> ``retail_weight``; ``size >= block_min``
    -> ``block_weight``; else ``1.0``. ``block_min`` defaults per-instrument from the engine
    ``BLOCK_MIN_SIZE`` (/ES 50, /NQ 25); the weight defaults are the engine constants.

    DEGENERACY WARNING (the engine's actual default behaviour): ``retail_weight == 0.0``
    DELETES every retail trade (size <= retail_max) outright — it is NOT a reweight. On a
    0DTE tape dominated by small lots this can erase most of the flow, collapsing the tiered
    flow term toward zero (so ``gex_tiered`` -> ``gex_static`` pure OI). The runner reports the
    surviving-leg/trade count per day so this collapse is VISIBLE, not hidden.

    With ``retail_weight == block_weight == 1.0`` every ``tier_weight`` is 1.0, so this reduces
    EXACTLY to :func:`net_flow_from_trades` (locked by the reduction-property test). Keys are
    ``(float(strike), is_call)`` to match ``q_per_leg``'s lookup.
    """
    bmin = _resolve_block_min(instrument, block_min)
    out: dict = {}
    for t in trades:
        tw = tier_weight(
            float(t.size),
            retail_max=retail_max,
            block_min=bmin,
            retail_weight=retail_weight,
            block_weight=block_weight,
        )
        key = (float(t.strike), bool(t.is_call))
        out[key] = out.get(key, 0.0) + float(t.sign) * float(t.size) * tw
    return out


def synthetic_gex_by_strike(
    rows: Sequence,
    net_flow: Mapping[FlowKey, float],
    M: float,
    F: float,
    w: float,
) -> dict:
    """SIGN-FREE per-strike synthetic-OI #4 GEX at weight ``w``. Skips thin strikes.

    For each NON-thin row with solved gamma::

        q_call, q_put = engine.synthetic_oi.q_per_leg(row, net_flow, w)
        gex_strike    = (call_gamma·q_call + put_gamma·q_put) · M · F² · GEX_PCT_SCALE

    The dealer sign (+1 call / −1 put) and the ``-flow`` dealer-opposite are ALREADY inside
    ``q_per_leg`` (``Q = s_static·OI + (−flow)·w``), so this aggregator adds NO further
    dealer sign — that is the whole point (see module docstring on the double-sign trap).
    Thin strikes (gamma unsolved upstream) are SKIPPED, never fabricated.

    By reusing the engine's ``q_per_leg`` + the locked ``M·F²·GEX_PCT_SCALE`` scale + the
    same thin-skip, ``sum(...).values()`` equals the engine's scalar ``synthetic_gex`` to
    float tolerance (the correctness anchor the test-author locks).
    """
    scale = M * F * F * GEX_PCT_SCALE
    out: dict = {}
    for r in rows:
        if getattr(r, "thin", False):
            continue  # gamma unsolved upstream -> do not fabricate a contribution
        q_call, q_put = q_per_leg(r, net_flow, w)
        out[float(r.strike)] = (
            float(r.call_gamma) * q_call + float(r.put_gamma) * q_put
        ) * scale
    return out


# --------------------------------------------------------------------------- #
# pure structural primitives (stdlib only — mirror the TRANSFERABLE half of
# ddoi_divergence.divergence_metrics; the SIGN-FLIP detectors magnitude_pearson/
# neg_pearson are deliberately NOT carried — they detect the DDOI Σw=0 sign flip,
# which CANNOT occur here since w=0 and w=1 share the same s_static·OI anchor).
# --------------------------------------------------------------------------- #
def _sign(v: float) -> int:
    return 1 if v > 0.0 else (-1 if v < 0.0 else 0)


def _argmax_abs_strike(by_strike: Mapping[float, float]):
    """Strike carrying the largest |gex| (the dominant strike). None if empty."""
    if not by_strike:
        return None
    return max(by_strike, key=lambda s: abs(by_strike[s]))


def _ls_scalar_through_origin(g: Sequence[float], s: Sequence[float]) -> float:
    """Least-squares scalar ``c`` minimizing ‖g − c·s‖² (no intercept): c = Σ(g·s)/Σ(s²).

    NaN when ``s`` is all-zero (Σs² == 0, the regressor carries no energy). Identical
    formula to ``ddoi_divergence._ls_scalar_through_origin`` (transferable primitive).
    """
    sss = sum(x * x for x in s)
    if sss == 0.0:
        return float("nan")
    sgs = sum(a * b for a, b in zip(g, s))
    return sgs / sss


def _residual_r2(g: Sequence[float], s: Sequence[float], c: float) -> float:
    """Fraction of ``g``'s variance explained by the scalar fit ``c·s`` (through origin).

    ``residual = g − c·s``; ``r2 = 1 − Σresidual² / Σ(g − mean_g)²``. NaN when ``c`` is
    NaN or ``g`` is constant (zero total variance => undefined). DIRECTION (load-bearing):
    here ``g`` = the w=1 (OI+flow) profile and ``s`` = the w=0 (pure OI) profile, so
    ``residual_r2 ≈ 1`` means ``gex ≈ c·static`` ⇒ the FLOW TERM ADDS NOTHING structural
    (just a scalar rescale of OI = a null). Only a LARGE structured residual
    (``residual_r2`` well below 1) leaves room for genuine per-strike re-weighting by flow.
    Identical formula to ``ddoi_divergence._residual_r2`` (transferable primitive).
    """
    if math.isnan(c):
        return float("nan")
    n = len(g)
    if n == 0:
        return float("nan")
    mg = sum(g) / n
    sstot = sum((x - mg) ** 2 for x in g)
    if sstot == 0.0:
        return float("nan")
    ssres = sum((a - c * b) ** 2 for a, b in zip(g, s))
    return 1.0 - ssres / sstot


def _l2(xs: Sequence[float]) -> float:
    return math.sqrt(sum(x * x for x in xs))


def flow_term_metrics(
    profile_gex: Mapping[float, float],
    profile_static: Mapping[float, float],
) -> dict:
    """STRUCTURAL comparison of the #4 ``w=1`` profile vs the ``w=0`` pure-OI profile.

    Cross-sectional over the strikes SHARED by both profiles (sorted ascending), PURE and
    deterministic. Inputs are ``{strike: gex}`` dicts from :func:`synthetic_gex_by_strike`
    (``profile_gex`` at the operating ``w``; ``profile_static`` at ``w=0``).

    Returns a dict with:
      * ``n``               — number of shared strikes compared.
      * ``best_fit_scalar_c`` — least-squares ``c = Σ(g·s)/Σ(s²)`` (through origin) for
                              ``gex ≈ c·static``.
      * ``residual_r2``     — variance of ``gex`` explained by ``c·static`` (THE REDUNDANCY
                              DETECTOR). HIGH ⇒ flow is a scalar rescale of OI (no new
                              structure = null); LOW ⇒ structured residual ⇒ flow may add
                              per-strike structure. See :func:`_residual_r2` on direction.
      * ``flow_norm_ratio`` — ‖gex − static‖₂ / ‖static‖₂. THE HEADLINE MAGNITUDE: how big
                              the additive flow term is relative to pure OI. ~0 ⇒ flow is
                              negligible; large ⇒ flow materially reshapes the profile. NaN
                              if the static profile has zero energy.
      * ``argmax_distance`` — ``|argmax_strike(|gex|) − argmax_strike(|static|)|`` in strike
                              points: does the flow term MOVE the dominant strike?
      * ``sign_agreement``  — fraction of strikes where ``sign(gex) == sign(static)`` (per-
                              strike structural sign match; context, not a verdict).
      * ``gex_argmax_strike`` / ``static_argmax_strike`` — dominant (|max|) strike each.
    """
    strikes = sorted(set(profile_gex) & set(profile_static))
    n = len(strikes)
    if n == 0:
        return {
            "n": 0,
            "best_fit_scalar_c": float("nan"),
            "residual_r2": float("nan"),
            "flow_norm_ratio": float("nan"),
            "argmax_distance": None,
            "sign_agreement": float("nan"),
            "gex_argmax_strike": None,
            "static_argmax_strike": None,
        }
    g = [float(profile_gex[k]) for k in strikes]
    s = [float(profile_static[k]) for k in strikes]

    c = _ls_scalar_through_origin(g, s)
    rr2 = _residual_r2(g, s, c)

    static_norm = _l2(s)
    diff_norm = _l2([a - b for a, b in zip(g, s)])
    flow_norm_ratio = diff_norm / static_norm if static_norm > 0.0 else float("nan")

    g_arg = _argmax_abs_strike({k: profile_gex[k] for k in strikes})
    s_arg = _argmax_abs_strike({k: profile_static[k] for k in strikes})
    argmax_distance = (
        abs(float(g_arg) - float(s_arg)) if (g_arg is not None and s_arg is not None) else None
    )

    sign_hits = sum(1 for a, b in zip(g, s) if _sign(a) == _sign(b))

    return {
        "n": n,
        "best_fit_scalar_c": c,
        "residual_r2": rr2,
        "flow_norm_ratio": flow_norm_ratio,
        "argmax_distance": argmax_distance,
        "sign_agreement": sign_hits / n,
        "gex_argmax_strike": g_arg,
        "static_argmax_strike": s_arg,
    }


def shuffle_flow_signs(trades: Sequence[FlowTrade], seed: int) -> dict:
    """Directional-destroying control: permute the aggressor SIGN across trades, re-net.

    PER-TRADE shuffle (the faithful choice, documented): mirrors ``flux_eval.shuffle_signs``
    — a single seeded :class:`random.Random` permutes the multiset of per-trade aggressor
    signs over the whole (day, instrument) population and reassigns them to trades in order.
    Every trade KEEPS its ``strike``/``is_call``/``size`` and the global sign multiset is
    PRESERVED; only the DIRECTION moves. Re-aggregating ``sign·size`` per leg yields a
    net-flow map of the SAME per-leg magnitude scale but RANDOM direction — the NULL the
    real flow term must beat on ``flow_norm_ratio`` / ``argmax_distance``.

    (Alternative considered: shuffle the SIGN of each leg's pre-summed net_flow. Rejected —
    it cannot reshuffle WITHIN a leg's trades, so it destroys less of the directional
    structure and is a weaker null. Per-trade is more faithful.)

    Returns a fresh ``{(strike, is_call): net_flow}`` map (does not mutate ``trades``).
    """
    signs = [int(t.sign) for t in trades]
    perm = list(signs)
    random.Random(seed).shuffle(perm)
    out: dict = {}
    for t, sgn in zip(trades, perm):
        key = (float(t.strike), bool(t.is_call))
        out[key] = out.get(key, 0.0) + float(sgn) * float(t.size)
    return out


def _mean(vals: Sequence[float]) -> float:
    clean = [v for v in vals if not (isinstance(v, float) and math.isnan(v))]
    return sum(clean) / len(clean) if clean else float("nan")


def eval_flow_term(
    rows: Sequence,
    trades: Sequence[FlowTrade],
    M: float,
    F: float,
    *,
    w: float = 1.0,
    seeds: Sequence[int] = DEFAULT_SHUFFLE_SEEDS,
) -> dict:
    """Full FLOW-TERM structural panel for one (day, instrument): real vs shuffle-flow NULL.

    Builds (on the SAME solved gammas + same ``s_static·OI`` anchor, only the additive
    ``(−flow)·w`` differs):
      * ``profile_gex``    — synthetic #4 GEX at the operating ``w`` (OI + flow).
      * ``profile_static`` — synthetic #4 GEX at ``w=0`` (PURE OI-GEX). NOTE the flow term
                             vanishes at w=0, so ``profile_static`` is INVARIANT to any flow
                             shuffle — it is the correct fixed reference for every arm.
      * ``real``           — :func:`flow_term_metrics` (profile_gex vs profile_static).
      * SHUFFLE arm        — for each seed, re-net with permuted signs, rebuild the w=``w``
                             profile, and compare it to the SAME ``profile_static``; collect
                             ``flow_norm_ratio`` + ``argmax_distance`` -> mean + [min,max].

    HEADLINE GAPS (the only things worth reading at n=4):
      * ``norm_ratio_gap`` = real ``flow_norm_ratio`` − mean(shuffle ``flow_norm_ratio``).
      * ``argmax_gap``     = real ``argmax_distance`` − mean(shuffle ``argmax_distance``).

    READ (both are nulls): if real ≈ shuffle, the flow term carries NO structure beyond what
    random-sign flow of the same magnitude would; if ``residual_r2 ≈ 1``, the flow term is
    just a scalar rescale of OI. Returns a flat NaN-safe dict.
    """
    net_flow = net_flow_from_trades(trades)
    profile_static = synthetic_gex_by_strike(rows, net_flow, M, F, 0.0)
    profile_gex = synthetic_gex_by_strike(rows, net_flow, M, F, w)
    real = flow_term_metrics(profile_gex, profile_static)

    shuf_norm: List[float] = []
    shuf_argmax: List[float] = []
    for sd in seeds:
        shuf_flow = shuffle_flow_signs(trades, sd)
        shuf_gex = synthetic_gex_by_strike(rows, shuf_flow, M, F, w)
        sm = flow_term_metrics(shuf_gex, profile_static)
        shuf_norm.append(sm["flow_norm_ratio"])
        if sm["argmax_distance"] is not None:
            shuf_argmax.append(float(sm["argmax_distance"]))

    valid_norm = [x for x in shuf_norm if not (isinstance(x, float) and math.isnan(x))]
    shuffle_norm_mean = _mean(valid_norm)
    shuffle_norm_min = min(valid_norm) if valid_norm else float("nan")
    shuffle_norm_max = max(valid_norm) if valid_norm else float("nan")
    shuffle_argmax_mean = _mean(shuf_argmax) if shuf_argmax else float("nan")

    real_norm = real["flow_norm_ratio"]
    norm_ratio_gap = (
        real_norm - shuffle_norm_mean
        if not (
            (isinstance(real_norm, float) and math.isnan(real_norm))
            or math.isnan(shuffle_norm_mean)
        )
        else float("nan")
    )
    real_argmax = real["argmax_distance"]
    argmax_gap = (
        float(real_argmax) - shuffle_argmax_mean
        if (real_argmax is not None and not math.isnan(shuffle_argmax_mean))
        else float("nan")
    )

    return {
        "w": w,
        "n": real["n"],
        "best_fit_scalar_c": real["best_fit_scalar_c"],
        "residual_r2": real["residual_r2"],
        "flow_norm_ratio": real_norm,
        "argmax_distance": real_argmax,
        "sign_agreement": real["sign_agreement"],
        "gex_argmax_strike": real["gex_argmax_strike"],
        "static_argmax_strike": real["static_argmax_strike"],
        "shuffle_norm_mean": shuffle_norm_mean,
        "shuffle_norm_min": shuffle_norm_min,
        "shuffle_norm_max": shuffle_norm_max,
        "shuffle_argmax_mean": shuffle_argmax_mean,
        "norm_ratio_gap": norm_ratio_gap,
        "argmax_gap": argmax_gap,
        "n_seeds": len(seeds),
    }


def _shuffle_trades(trades: Sequence[FlowTrade], seed: int) -> List[FlowTrade]:
    """Permute the aggressor SIGN across trades (keep strike/is_call/size), return new trades.

    The SAME seeded permutation as :func:`shuffle_flow_signs` (identical
    ``random.Random(seed).shuffle`` call), but returns the re-signed :class:`FlowTrade`
    list so a PER-TRADE size weighting (tier_weight) can be re-applied AFTER the shuffle —
    :func:`shuffle_flow_signs` nets immediately and so cannot feed the tiered constructor.
    For a given seed both produce the same sign assignment, so the #4 and #6 shuffle nulls
    are the SAME directional null, just with vs without the size tier.
    """
    signs = [int(t.sign) for t in trades]
    perm = list(signs)
    random.Random(seed).shuffle(perm)
    return [
        FlowTrade(strike=t.strike, is_call=t.is_call, size=t.size, sign=sgn)
        for t, sgn in zip(trades, perm)
    ]


def eval_tiered_term(
    rows: Sequence,
    trades: Sequence[FlowTrade],
    instrument: str,
    M: float,
    F: float,
    *,
    w: float = 1.0,
    seeds: Sequence[int] = DEFAULT_SHUFFLE_SEEDS,
    retail_max: float = RETAIL_MAX_SIZE,
    block_min: Optional[float] = None,
    retail_weight: float = RETAIL_TIER_WEIGHT,
    block_weight: float = BLOCK_TIER_WEIGHT,
) -> dict:
    """Synthetic-OI #6 size-TIERED arm: does size-tiering add STRUCTURE OVER the plain #4 flow?

    Builds, on the SAME solved gammas + same ``s_static·OI`` anchor as :func:`eval_flow_term`:
      * ``profile_static`` — synthetic #4 GEX at ``w=0`` (PURE OI-GEX), context reference.
      * ``profile_plain``  — synthetic #4 GEX at ``w`` from the PLAIN net flow. THIS is the
                             tiered arm's fixed reference: the #6 headline asks whether tiering
                             moves the profile OVER (beyond) the plain flow term, not over OI.
      * ``profile_tiered`` — synthetic #6 GEX at ``w`` from the size-TIERED net flow
                             (:func:`tiered_net_flow_from_trades`; ``tier_weight`` imported).

    HEADLINE (``real``) = :func:`flow_term_metrics`\\(profile_tiered, profile_plain): does the
    tiered profile add per-strike structure OVER the plain flow profile?
      * ``residual_r2`` ≈ 1 ⇒ tiered ≈ c·plain ⇒ tiering is just a rescale of plain flow (a
        null — adds NO new shape).
      * ``flow_norm_ratio`` = ‖tiered − plain‖₂ / ‖plain‖₂ — how far tiering moves the profile
        relative to the plain flow profile.
      * ``argmax_distance`` — does tiering MOVE the dominant strike off where plain put it.

    SHUFFLE-SIGN control: for each seed, permute the per-trade aggressor sign
    (:func:`_shuffle_trades`), rebuild the TIERED flow + its profile, and compare to the SAME
    fixed ``profile_plain``. The real tiered profile must beat this same-magnitude random-sign
    tiered null on ``flow_norm_ratio`` / ``argmax_distance`` to carry directional structure
    that the plain flow term does not already have.

    DEGENERACY (reported, never hidden): with ``retail_weight == 0.0`` (the engine default) the
    tiered constructor DELETES every retail trade. On a small-lot 0DTE tape this can erase most
    of the flow, collapsing ``profile_tiered`` toward ``profile_static`` (pure OI). The returned
    ``n_surviving_trades`` / ``n_surviving_legs`` / ``n_deleted_trades`` expose that collapse so
    a near-zero tiered flow term is visible as the finding, not mistaken for "adds structure".
    ``vs_static_norm_ratio`` (tiered vs pure-OI) gives the magnitude context.

    Returns a flat dict whose gap/shuffle/metric keys MIRROR :func:`eval_flow_term` so the
    runner's sign-consistency + single-day-domination + MIN_DAYS gate applies UNCHANGED, plus
    the tiered-specific degeneracy fields.
    """
    bmin = _resolve_block_min(instrument, block_min)
    tier_kw = dict(
        retail_max=retail_max,
        block_min=bmin,
        retail_weight=retail_weight,
        block_weight=block_weight,
    )

    net_plain = net_flow_from_trades(trades)
    net_tiered = tiered_net_flow_from_trades(trades, instrument, **tier_kw)

    profile_static = synthetic_gex_by_strike(rows, net_plain, M, F, 0.0)
    profile_plain = synthetic_gex_by_strike(rows, net_plain, M, F, w)
    profile_tiered = synthetic_gex_by_strike(rows, net_tiered, M, F, w)

    real = flow_term_metrics(profile_tiered, profile_plain)
    vs_static = flow_term_metrics(profile_tiered, profile_static)

    shuf_norm: List[float] = []
    shuf_argmax: List[float] = []
    for sd in seeds:
        shuf_tr = _shuffle_trades(trades, sd)
        shuf_tiered = tiered_net_flow_from_trades(shuf_tr, instrument, **tier_kw)
        shuf_gex = synthetic_gex_by_strike(rows, shuf_tiered, M, F, w)
        sm = flow_term_metrics(shuf_gex, profile_plain)
        shuf_norm.append(sm["flow_norm_ratio"])
        if sm["argmax_distance"] is not None:
            shuf_argmax.append(float(sm["argmax_distance"]))

    valid_norm = [x for x in shuf_norm if not (isinstance(x, float) and math.isnan(x))]
    shuffle_norm_mean = _mean(valid_norm)
    shuffle_norm_min = min(valid_norm) if valid_norm else float("nan")
    shuffle_norm_max = max(valid_norm) if valid_norm else float("nan")
    shuffle_argmax_mean = _mean(shuf_argmax) if shuf_argmax else float("nan")

    real_norm = real["flow_norm_ratio"]
    norm_ratio_gap = (
        real_norm - shuffle_norm_mean
        if not (
            (isinstance(real_norm, float) and math.isnan(real_norm))
            or math.isnan(shuffle_norm_mean)
        )
        else float("nan")
    )
    real_argmax = real["argmax_distance"]
    argmax_gap = (
        float(real_argmax) - shuffle_argmax_mean
        if (real_argmax is not None and not math.isnan(shuffle_argmax_mean))
        else float("nan")
    )

    # ---- DEGENERACY bookkeeping: how much survives the retail rule (the STOP-check) -------
    n_deleted = sum(
        1 for t in trades if tier_weight(float(t.size), **tier_kw) == 0.0
    )
    n_surviving_trades = len(trades) - n_deleted
    n_surviving_legs = sum(1 for v in net_tiered.values() if v != 0.0)
    n_plain_legs = sum(1 for v in net_plain.values() if v != 0.0)

    return {
        "w": w,
        "n": real["n"],
        "best_fit_scalar_c": real["best_fit_scalar_c"],
        "residual_r2": real["residual_r2"],
        "flow_norm_ratio": real_norm,
        "argmax_distance": real_argmax,
        "sign_agreement": real["sign_agreement"],
        "gex_argmax_strike": real["gex_argmax_strike"],
        "static_argmax_strike": real["static_argmax_strike"],
        "shuffle_norm_mean": shuffle_norm_mean,
        "shuffle_norm_min": shuffle_norm_min,
        "shuffle_norm_max": shuffle_norm_max,
        "shuffle_argmax_mean": shuffle_argmax_mean,
        "norm_ratio_gap": norm_ratio_gap,
        "argmax_gap": argmax_gap,
        "n_seeds": len(seeds),
        # ---- tiered-specific (the reference is the PLAIN flow profile, not OI) ----
        "vs_static_norm_ratio": vs_static["flow_norm_ratio"],
        "n_trades": len(trades),
        "n_deleted_trades": n_deleted,
        "n_surviving_trades": n_surviving_trades,
        "n_surviving_legs": n_surviving_legs,
        "n_plain_legs": n_plain_legs,
    }
