"""Extended dealer exposure — VEX (vanna) and CHEX (charm), VOL-based, 0DTE.

EXPERIMENTAL / NOT PRICE-VALIDATED. Additive research lens that lives ALONGSIDE
the locked VOL-based GEX/DEX (it does NOT replace or modify ``engine.exposure``).
Structural only — the higher-order greek exposures are FD-validated in
``engine.black76``, but their aggregate behaviour has never been checked against
price. Consumers/FE MUST treat ``exposure_ext`` as experimental, not authoritative.

What it is
==========
Dealer second-order hedging pressure, on the SAME VOL basis and dealer signs as
the locked GEX/DEX profile (``+1`` call / ``-1`` put, cumulative volume since the
RTH open):

  VEX (vanna exposure) — change in dealer dollar-delta per **1 vol-point (1% IV)**
      net_vex = (sign_c*vanna_c*cvol + sign_p*vanna_p*pvol) * M * F * 0.01

  CHEX (charm exposure) — change in dealer dollar-delta per **calendar day**
      net_chex = (sign_c*charm_c*cvol + sign_p*charm_p*pvol) * M * F * (1/365)

Scaling — read carefully (the two ``0.01``s are NOT the same physics)
=====================================================================
``M * F`` dollarises a delta-derivative into USD dollar-delta (this is the SAME
dolarisation as the locked DEX ``M * F`` in ``engine.exposure``; vanna and charm
differentiate delta w.r.t. vol/time, NOT w.r.t. ``F``, so each takes exactly ONE
``F`` — unlike GEX's ``F^2``).

  * ``VEX_VOL_PT_SCALE = 0.01`` is a **vol-point** scale: ``black76.vanna`` returns
    delta per 1.00 of vol, so ``* 0.01`` makes it per-1%-IV. This is DELIBERATELY
    a different ``0.01`` from the locked ``GEX_PCT_SCALE`` (a 1%-PRICE-MOVE scale).
    VEX is "USD dollar-delta per 1% IV move" and is NOT directly comparable to
    GEX's "USD dollar-delta per 1% price move".
  * ``CHEX_DAY_SCALE = 1/365`` converts ``black76.charm`` (per YEAR) to per DAY —
    the natural horizon for a 0DTE book whose charm builds into the 16:00 ET bell.
    This is a presentation choice (per-day is interpretable; per-year is a huge
    unintuitive number) and is documented in CONTRACT.md.

Thin strikes (``ChainRow.thin`` — IV unsolved upstream) are SKIPPED, matching
``engine.synthetic_oi``: we do NOT fabricate greeks where IV was unsolvable.

Only the standard library + sibling ``engine`` modules are used.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from engine.black76 import charm as bs_charm
from engine.black76 import vanna as bs_vanna
from engine.exposure import DEALER_SIGN_CALL, DEALER_SIGN_PUT, ChainRow

__all__ = [
    "VEX_VOL_PT_SCALE",
    "CHEX_DAY_SCALE",
    "ExposureExtSnapshot",
    "net_vex_chex",
    "build_exposure_ext",
]

#: VEX scale: ``black76.vanna`` (delta per 1.00 vol) -> per 1% IV (vol-point).
#: DISTINCT from the locked ``GEX_PCT_SCALE`` (a 1% PRICE-move scale).
VEX_VOL_PT_SCALE: float = 0.01
#: CHEX scale: ``black76.charm`` (per year) -> per calendar day (0DTE horizon).
CHEX_DAY_SCALE: float = 1.0 / 365.0


@dataclass(frozen=True)
class ExposureExtSnapshot:
    """Extended-exposure aggregate for one minute (EXPERIMENTAL).

    ``net_vex`` is USD dealer dollar-delta change per 1% IV move; ``net_chex`` is
    USD dealer dollar-delta drift per calendar day. Signs follow the locked GEX
    convention (``> 0`` turquoise / stabilising, ``< 0`` crimson / destabilising).
    """

    net_vex: float
    vex_sign: int
    net_chex: float
    chex_sign: int

    def to_dict(self) -> dict[str, float]:
        return {
            "net_vex": self.net_vex,
            "vex_sign": self.vex_sign,
            "net_chex": self.net_chex,
            "chex_sign": self.chex_sign,
        }


def net_vex_chex(
    rows: Sequence[ChainRow],
    M: float,
    F: float,
    rate: float,
) -> tuple[float, float]:
    """Aggregate (net_vex, net_chex) on the VOL basis. Skips thin strikes.

    Re-evaluates vanna/charm per leg from the carried per-leg IV + ``t_expiry``
    (set by the snapshot solve) at the supplied ``rate``; thin rows (IV unsolved)
    contribute nothing rather than fabricating a greek.
    """
    vex_scale = M * F * VEX_VOL_PT_SCALE
    chex_scale = M * F * CHEX_DAY_SCALE
    vex_term = 0.0
    chex_term = 0.0
    for r in rows:
        if r.thin or r.call_iv is None or r.put_iv is None or r.t_expiry is None:
            continue  # IV unsolved upstream -> do not fabricate a contribution
        T = r.t_expiry
        v_call = bs_vanna(F, r.strike, T, rate, r.call_iv)
        v_put = bs_vanna(F, r.strike, T, rate, r.put_iv)
        ch_call = bs_charm("call", F, r.strike, T, rate, r.call_iv)
        ch_put = bs_charm("put", F, r.strike, T, rate, r.put_iv)
        vex_term += (
            DEALER_SIGN_CALL * v_call * r.call_vol
            + DEALER_SIGN_PUT * v_put * r.put_vol
        )
        chex_term += (
            DEALER_SIGN_CALL * ch_call * r.call_vol
            + DEALER_SIGN_PUT * ch_put * r.put_vol
        )
    return vex_term * vex_scale, chex_term * chex_scale


def build_exposure_ext(
    rows: Sequence[ChainRow],
    M: float,
    F: float,
    rate: float,
) -> ExposureExtSnapshot:
    """Build the extended-exposure aggregate (net VEX + net CHEX, VOL-based)."""
    net_vex, net_chex = net_vex_chex(rows, M, F, rate)
    vex_sign = 1 if net_vex > 0.0 else (-1 if net_vex < 0.0 else 0)
    chex_sign = 1 if net_chex > 0.0 else (-1 if net_chex < 0.0 else 0)
    return ExposureExtSnapshot(
        net_vex=net_vex,
        vex_sign=vex_sign,
        net_chex=net_chex,
        chex_sign=chex_sign,
    )
