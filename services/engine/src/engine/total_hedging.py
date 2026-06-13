"""Synthetic-OI #7 — total-hedging map (gamma + charm + vanna on the Q base).

EXPERIMENTAL / NOT PRICE-VALIDATED. Additive research lens alongside the locked
VOL-based GEX/DEX (does NOT replace or modify them). Structural only — the greeks
are FD-validated in ``engine.black76``, but the aggregate has never been checked
against price. Consumers/FE MUST treat ``total_hedging`` as experimental.

What it is
==========
Dealer hedging pressure for 0DTE is not gamma-only: **charm** (delta decay, which
explodes into the 16:00 ET bell) and **vanna** (delta sensitivity to vol) also move
the hedge. This lens applies all three greeks to the SAME synthetic dealer position
``Q`` that synthetic-OI #4 builds (``engine.synthetic_oi.q_per_leg``):

    Q(strike, leg) = s_static * OI_open + (-net_aggressor_flow) * w     (dealer sign BAKED IN)

    gamma_hedge = Σ Γ·Q·M·F²·0.01          # USD per 1% PRICE move  (== #4 synthetic GEX)
    charm_hedge = Σ charm·Q·M·F·(1/365)     # USD dealer dollar-delta drift per DAY
    vanna_hedge = Σ vanna·Q·M·F·0.01        # USD dealer dollar-delta per 1% IV (vol-point)

THREE SEPARATE fields — never a blended scalar. The three carry DIFFERENT units
(price-move / time / vol), so summing them is dimensionally invalid.

Scaling — identical to the locked refs (this is VEX/CHEX/GEX on Q instead of VOL)
=================================================================================
``Q`` already carries the locked dealer sign (+1 call / -1 put) from ``q_per_leg``,
so greeks are weighted by ``Q`` DIRECTLY and the dealer sign is NOT re-applied here
(this differs from ``engine.exposure_ext``, which is VOL-based and applies the sign
itself). The per-greek scale constants are reused verbatim:
  * gamma: ``M·F²·GEX_PCT_SCALE`` — the locked GEX scale (per 1% price move).
  * charm: ``M·F·CHEX_DAY_SCALE`` — per calendar day (charm is per-year; ·1/365).
  * vanna: ``M·F·VEX_VOL_PT_SCALE`` — per 1% IV (a VOL-POINT 0.01, distinct from
    the gamma price-move 0.01 — same trap documented in ``engine.exposure_ext``).

Thin strikes (``ChainRow.thin`` — IV unsolved) are SKIPPED, not fabricated.

Only the standard library + sibling ``engine`` modules are used.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from engine.black76 import charm as bs_charm
from engine.black76 import vanna as bs_vanna
from engine.exposure import GEX_PCT_SCALE, ChainRow
from engine.exposure_ext import CHEX_DAY_SCALE, VEX_VOL_PT_SCALE
from engine.synthetic_oi import FlowKey, q_per_leg

__all__ = [
    "TotalHedgingSnapshot",
    "total_hedging",
    "build_total_hedging",
]


@dataclass(frozen=True)
class TotalHedgingSnapshot:
    """Total-hedging aggregate for one minute (EXPERIMENTAL).

    Three dealer-hedging dimensions on the synthetic-OI ``Q`` base, each in its own
    units (see module docstring). ``gamma_hedge`` equals the #4 synthetic GEX at the
    same ``w``; ``charm_hedge`` / ``vanna_hedge`` are the afternoon-decay and
    vol-sensitivity dimensions a gamma-only map misses.
    """

    gamma_hedge: float
    charm_hedge: float
    vanna_hedge: float
    w: float

    def to_dict(self) -> dict[str, float]:
        return {
            "gamma_hedge": self.gamma_hedge,
            "charm_hedge": self.charm_hedge,
            "vanna_hedge": self.vanna_hedge,
            "w": self.w,
        }


def total_hedging(
    rows: Sequence[ChainRow],
    net_flow: Mapping[FlowKey, float],
    M: float,
    F: float,
    rate: float,
    w: float,
) -> tuple[float, float, float]:
    """Aggregate ``(gamma_hedge, charm_hedge, vanna_hedge)`` on the Q base.

    Greeks are re-evaluated per non-thin leg from the carried per-leg IV +
    ``t_expiry`` at ``rate``; thin rows (IV unsolved) contribute nothing. ``Q``
    carries the dealer sign, so no sign is applied to the greek terms here.
    """
    gamma_scale = M * F * F * GEX_PCT_SCALE
    charm_scale = M * F * CHEX_DAY_SCALE
    vanna_scale = M * F * VEX_VOL_PT_SCALE
    g_term = c_term = v_term = 0.0
    for r in rows:
        if r.thin or r.call_iv is None or r.put_iv is None or r.t_expiry is None:
            continue
        q_call, q_put = q_per_leg(r, net_flow, w)
        T = r.t_expiry
        g_term += r.call_gamma * q_call + r.put_gamma * q_put
        c_term += (
            bs_charm("call", F, r.strike, T, rate, r.call_iv) * q_call
            + bs_charm("put", F, r.strike, T, rate, r.put_iv) * q_put
        )
        v_term += (
            bs_vanna(F, r.strike, T, rate, r.call_iv) * q_call
            + bs_vanna(F, r.strike, T, rate, r.put_iv) * q_put
        )
    return g_term * gamma_scale, c_term * charm_scale, v_term * vanna_scale


def build_total_hedging(
    rows: Sequence[ChainRow],
    net_flow: Mapping[FlowKey, float],
    M: float,
    F: float,
    rate: float,
    *,
    w: float = 1.0,
) -> TotalHedgingSnapshot:
    """Build the total-hedging aggregate (gamma + charm + vanna on the Q base)."""
    if not (0.0 <= w <= 1.0):
        raise ValueError(f"w must be in [0, 1], got {w!r}")
    g, c, v = total_hedging(rows, net_flow, M, F, rate, w)
    return TotalHedgingSnapshot(gamma_hedge=g, charm_hedge=c, vanna_hedge=v, w=w)
