"""Synthetic-OI #4 — dealer positioning from carried-in OI updated by aggressor flow.

EXPERIMENTAL / NOT PRICE-VALIDATED. This is an additive research lens that lives
ALONGSIDE the locked VOL-based product GEX (it does NOT replace or modify it). It
is structural only — validated on a single 4-day correlated episode, never against
price. Consumers/FE MUST treat ``synthetic_oi`` as experimental, not authoritative.

Formula #4 (see analysis/synthetic_oi_v4.py + docs/research/empirical/synthetic-oi-0dte.md):

    Q(strike, type) = s_static * OI_open  +  (-net_aggressor_flow) * w

  * ``s_static`` = locked dealer convention (+1 call / -1 put), used for the
    DIRECTION of carried-in open interest (unknowable from the tape — the same
    irreducible assumption every vendor makes).
  * ``OI_open``  = prior-session settled open interest per leg (the stock anchor).
  * ``net_aggressor_flow`` = Sum(aggressor_sign * size) per leg since the RTH open
    (B=+1, A=-1, N=0). Native CME aggressor side — the edge over Lee-Ready vendors.
    The dealer takes the OPPOSITE of the customer aggressor, hence ``-flow``.
  * ``w`` in [0, 1] = the open/close weight (the one proprietary knob). ``w=0`` is
    pure OI-GEX (SpotGamma-classic); ``w=1`` fully updates the OI anchor by flow.

    synthetic-GEX = Sum_over_strikes Gamma * Q * M * F^2 * 0.01

Thin strikes (``ChainRow.thin`` — IV unsolved -> gamma forced to 0 upstream) are
SKIPPED, matching the validated analysis/synthetic_oi_v4.py. We do NOT interpolate
gamma here (the VOL ``net_gex`` profile does, for its own purpose); fabricating
gamma where IV was unsolvable would put an invented number into a paid product.

Only the standard library + sibling ``engine.exposure`` constants are used.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence, Tuple

from engine.exposure import (
    DEALER_SIGN_CALL,
    DEALER_SIGN_PUT,
    GEX_PCT_SCALE,
    ChainRow,
)

__all__ = [
    "FlowKey",
    "SyntheticOiSnapshot",
    "q_per_leg",
    "synthetic_gex",
    "build_synthetic_oi",
    "tier_weight",
    "decay_weight",
    "BLOCK_MIN_SIZE",
    "RETAIL_MAX_SIZE",
    "RETAIL_TIER_WEIGHT",
    "BLOCK_TIER_WEIGHT",
    "DEFAULT_HALF_LIFE_MIN",
]

#: Per-leg key for the net-aggressor-flow map: (strike, is_call).
FlowKey = Tuple[float, bool]

# --- Synthetic-OI #6 size-tiering (EXPERIMENTAL — thresholds are UNVALIDATED) --- #
# The idea (docs/research/empirical/synthetic-oi-roadmap.md #6): large trades are
# institutional/dealer-relevant, small odd-lots are retail noise; weight each
# trade's signed flow by a size tier before it enters the synthetic-OI Q. These
# constants are STARTING GUESSES that MUST be swept on the real tape — do not treat
# them as calibrated. With all weights == 1.0 the tiered model reduces exactly to #4.
#: Retail size ceiling (odd-lot proxy); matches engine.hiro.RETAIL_MAX_SIZE.
RETAIL_MAX_SIZE: float = 5.0
#: Per-instrument block-size floor (institutional). /NQ trades thinner than /ES.
BLOCK_MIN_SIZE = {"ES": 50.0, "NQ": 25.0}
#: Tier weights: retail downweighted toward 0 (noise), block upweighted.
RETAIL_TIER_WEIGHT: float = 0.0
BLOCK_TIER_WEIGHT: float = 1.5


def tier_weight(
    size: float,
    *,
    retail_max: float = RETAIL_MAX_SIZE,
    block_min: float = 50.0,
    retail_weight: float = RETAIL_TIER_WEIGHT,
    block_weight: float = BLOCK_TIER_WEIGHT,
) -> float:
    """Size-tier multiplier for one trade's signed flow (synthetic-OI #6).

    ``size <= retail_max`` -> ``retail_weight`` (retail noise, default 0);
    ``size >= block_min``  -> ``block_weight`` (institutional block, default 1.5);
    otherwise ``1.0``. With ``retail_weight == block_weight == 1.0`` this is the
    identity (the tiered model then reduces exactly to #4). Thresholds are
    EXPERIMENTAL guesses (see module constants) — sweep them on the tape.
    """
    if size <= retail_max:
        return retail_weight
    if size >= block_min:
        return block_weight
    return 1.0


# --- Synthetic-OI #5 decay-weighting (EXPERIMENTAL — half-life is UNVALIDATED) -- #
# The idea (docs/research/empirical/synthetic-oi-roadmap.md #5): recent flow should
# outweigh old flow, so an intraday round-trip (buy then sell of the same lot) nets
# toward zero as both legs age — mitigating the double-count the VOL basis suffers.
# Each trade's signed flow is multiplied by exp(-lambda * age) before entering Q,
# with lambda = ln2 / half_life. The half-life is the proprietary knob (UNVALIDATED).
#: Default flow half-life in minutes (a STARTING GUESS — sweep on the tape).
DEFAULT_HALF_LIFE_MIN: float = 30.0


def decay_weight(age_minutes: float, *, half_life_min: float = DEFAULT_HALF_LIFE_MIN) -> float:
    """Exponential time-decay multiplier for one trade's signed flow (synthetic-OI #5).

    ``weight = exp(-ln2 * age / half_life)`` — a trade ``half_life`` minutes old gets
    weight 0.5, a fresh trade gets 1.0. ``age_minutes`` is the trade's age at the
    snapshot eval time (clamped to >= 0). ``half_life_min <= 0`` disables decay
    (returns 1.0), so #5 then reduces exactly to #4. Half-life is an EXPERIMENTAL
    knob (as unobservable as ``w``) — sweep it; do not treat it as calibrated.
    """
    if half_life_min <= 0.0:
        return 1.0
    age = max(0.0, age_minutes)
    return math.exp(-math.log(2.0) * age / half_life_min)


def q_per_leg(
    row: ChainRow,
    net_flow: Mapping[FlowKey, float],
    w: float,
) -> Tuple[float, float]:
    """Synthetic dealer position ``(q_call, q_put)`` for one strike row.

    ``Q = s_static * OI + (-net_flow) * w`` per leg. The dealer sign (+1 call /
    -1 put) is BAKED IN here, so downstream aggregations weight greeks by ``Q``
    directly and must NOT re-apply a dealer sign. Single source of truth for the
    #4 position model, reused by ``synthetic_gex`` and ``engine.total_hedging``.
    """
    c_flow = float(net_flow.get((row.strike, True), 0.0))
    p_flow = float(net_flow.get((row.strike, False), 0.0))
    q_call = DEALER_SIGN_CALL * row.call_oi + (-c_flow) * w
    q_put = DEALER_SIGN_PUT * row.put_oi + (-p_flow) * w
    return q_call, q_put


@dataclass(frozen=True)
class SyntheticOiSnapshot:
    """Synthetic-OI aggregate for one minute (EXPERIMENTAL).

    ``gex`` is the synthetic-OI GEX at weight ``w``; ``gex_static`` is the ``w=0``
    pure-OI baseline. A sign divergence between them flags where intraday flow has
    flipped the dealer's positioning vs. the morning stock. USD per 1% move.
    """

    gex: float
    sign: int
    gex_static: float
    w: float

    def to_dict(self) -> dict[str, float]:
        return {
            "gex": self.gex,
            "sign": self.sign,
            "gex_static": self.gex_static,
            "w": self.w,
        }


def synthetic_gex(
    rows: Sequence[ChainRow],
    net_flow: Mapping[FlowKey, float],
    M: float,
    F: float,
    w: float,
) -> float:
    """Synthetic-OI GEX at weight ``w``. Skips thin strikes (gamma unsolved).

    ``Q = s_static * OI + (-net_flow) * w`` per leg; GEX = Sum Gamma*Q*M*F^2*0.01.
    """
    scale = M * F * F * GEX_PCT_SCALE
    total = 0.0
    for r in rows:
        if r.thin:
            continue  # gamma unsolved upstream -> do not fabricate a contribution
        q_call, q_put = q_per_leg(r, net_flow, w)
        total += (r.call_gamma * q_call + r.put_gamma * q_put) * scale
    return total


def build_synthetic_oi(
    rows: Sequence[ChainRow],
    net_flow: Mapping[FlowKey, float],
    M: float,
    F: float,
    *,
    w: float = 1.0,
) -> SyntheticOiSnapshot:
    """Build the synthetic-OI aggregate (``gex`` at ``w`` + ``gex_static`` at w=0)."""
    if not (0.0 <= w <= 1.0):
        raise ValueError(f"w must be in [0, 1], got {w!r}")
    gex = synthetic_gex(rows, net_flow, M, F, w)
    sign = 1 if gex > 0.0 else (-1 if gex < 0.0 else 0)
    gex_static = synthetic_gex(rows, net_flow, M, F, 0.0)
    return SyntheticOiSnapshot(gex=gex, sign=sign, gex_static=gex_static, w=w)
