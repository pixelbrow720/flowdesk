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
    "synthetic_gex",
    "build_synthetic_oi",
]

#: Per-leg key for the net-aggressor-flow map: (strike, is_call).
FlowKey = Tuple[float, bool]


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
        c_flow = float(net_flow.get((r.strike, True), 0.0))
        p_flow = float(net_flow.get((r.strike, False), 0.0))
        q_call = DEALER_SIGN_CALL * r.call_oi + (-c_flow) * w
        q_put = DEALER_SIGN_PUT * r.put_oi + (-p_flow) * w
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
