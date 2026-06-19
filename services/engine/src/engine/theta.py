"""Net theta decay — VOL-based 0DTE aggregate (EXPERIMENTAL).

Additive lens that lives ALONGSIDE the locked VOL-based profile. Net theta is the
rate of change of the dealer's net delta per unit time — for a 0DTE book this is
the dominant intraday risk because theta becomes unbounded as T → 0.

What it is
==========
Cumulative-since-open dealer theta, computed leg-by-leg on the SAME VOL basis and
dealer signs (``+1`` call / ``-1`` put, cumulative volume since RTH open):

  net_theta = (sign_c*theta_c*cvol + sign_p*theta_p*pvol) * M * F * (1/365)

Sign reading: ``theta_call`` is negative (long calls lose value as time passes).
A dealer net long calls (long-gamma customer flow) thus carries net-negative theta
— they bleed value every minute; for the 0DTE book this is exactly the risk
being hedged.

Scaling
======
``M * F`` dollarises a delta-derivative into USD dollar-delta (SAME as the locked
DEX and the existing VEX/CHEX — the ``M·F`` pattern is one ``F`` because theta,
charm, vanna are derivatives w.r.t. time/vol, NOT w.r.t. ``F``).
``THETA_DAY_SCALE = 1/365`` converts ``black76.theta`` (per YEAR) to per CALENDAR DAY
— the natural horizon for 0DTE. Mirrors ``CHEX_DAY_SCALE`` in ``engine.exposure_ext``.

Thin strikes (``ChainRow.thin`` — IV unsolved upstream) are SKIPPED, matching
``engine.exposure_ext``. We do NOT fabricate greeks where IV was unsolvable.

EXPERIMENTAL / NOT PRICE-VALIDATED. Structural only — ``black76.theta`` is FD-
validated, but its aggregate behaviour has never been checked against price.
Consumers/FE MUST treat ``theta_decay`` as experimental, not authoritative.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from engine.black76 import theta as bs_theta
from engine.exposure import DEALER_SIGN_CALL, DEALER_SIGN_PUT, ChainRow

__all__ = [
    "THETA_DAY_SCALE",
    "ThetaDecaySnapshot",
    "net_theta",
    "build_theta_decay",
]

#: Theta scale: ``black76.theta`` (per year) -> per calendar day (0DTE horizon).
THETA_DAY_SCALE: float = 1.0 / 365.0


@dataclass(frozen=True)
class ThetaDecaySnapshot:
    """Net cumulative theta for one minute (EXPERIMENTAL — NOT price-validated).

    ``net_theta`` is USD dollar-delta change per calendar day on the VOL basis
    with locked dealer signs. ``theta_sign`` follows the locked sign convention
    (``+1`` turquoise / time decay on the bullish side, ``-1`` crimson / decay
    working against the bearish side).
    """

    net_theta: float
    theta_sign: int

    def to_dict(self) -> dict[str, float]:
        return {
            "net_theta": self.net_theta,
            "theta_sign": self.theta_sign,
        }


def net_theta(
    rows: Sequence[ChainRow],
    M: float,
    F: float,
    rate: float,
) -> float:
    """Net cumulative theta on the VOL basis. Skips thin strikes.

    Re-evaluates theta per leg from the carried per-leg IV + ``t_expiry`` (set by
    the snapshot solve) at the supplied ``rate``; thin rows (IV unsolved)
    contribute nothing rather than fabricating a greek.
    """
    scale = M * F * THETA_DAY_SCALE
    s = 0.0
    for r in rows:
        if r.thin or r.call_iv is None or r.put_iv is None or r.t_expiry is None:
            continue  # IV unsolved upstream -> do not fabricate
        T = r.t_expiry
        th_call = bs_theta("call", F, r.strike, T, rate, r.call_iv)
        th_put = bs_theta("put", F, r.strike, T, rate, r.put_iv)
        s += (
            DEALER_SIGN_CALL * th_call * r.call_vol
            + DEALER_SIGN_PUT * th_put * r.put_vol
        )
    return s * scale


def build_theta_decay(
    rows: Sequence[ChainRow],
    M: float,
    F: float,
    rate: float,
) -> ThetaDecaySnapshot:
    """Build the net-theta aggregate (VOL basis, dealer-signed)."""
    v = net_theta(rows, M, F, rate)
    return ThetaDecaySnapshot(
        net_theta=v,
        theta_sign=1 if v > 0.0 else (-1 if v < 0.0 else 0),
    )
