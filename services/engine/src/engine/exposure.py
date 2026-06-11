"""Per-strike GEX / DEX aggregation for FlowDesk (VOL-based, 0DTE).

Consumes a per-strike option-chain row whose IV + greeks have already been
computed (step 1.2, via :mod:`engine.black76` / :mod:`engine.iv`) and produces
the exposure *profile* used by the snapshot builder (step 1.3) and the regime
classifier.

Locked dealer convention (PRD #0 / PRD #7)
==========================================
The street/dealer is assumed **LONG calls** and **SHORT puts**:

    DEALER_SIGN_CALL = +1.0     # dealer long calls
    DEALER_SIGN_PUT  = -1.0     # dealer short puts

Every exposure is ``sum over {call, put} of dealer_sign * greek * VOL`` scaled
into dollars, where ``VOL`` is the *cumulative volume since the RTH open* for
that option leg (NOT open interest — FlowDesk is volume-based).

Gamma exposure (GEX) — units USD per 1% move
-------------------------------------------
    GEX_strike = gamma * VOL * M * F^2 * 0.01            (locked formula)
    net_gex    = ( +1 * call_gamma * call_vol
                   -1 * put_gamma  * put_vol  ) * M * F^2 * 0.01

Black-76 gamma is >= 0 for BOTH calls and puts, therefore:
  * call term = +call_gamma*call_vol >= 0  -> adds POSITIVE gex
  * put  term = -put_gamma *put_vol  <= 0  -> adds NEGATIVE gex
So ``Net GEX > 0`` => dealers net long gamma => PINNING regime (turquoise);
``Net GEX < 0`` => VOLATILE regime (crimson). The ``F^2 * 0.01`` factor converts
dollar-gamma into the change in dealer dollar-delta for a 1% move in ``F``.

Delta exposure (DEX) — units USD notional
-----------------------------------------
    net_dex = ( +1 * call_delta * call_vol
                -1 * put_delta  * put_vol ) * M * F

Call delta lies in (0, 1) and put delta in (-1, 0). With the SAME dealer signs:
  * call term = +call_delta*call_vol >= 0
  * put  term = -put_delta *put_vol  >= 0   (because put_delta < 0)
Hence a long-call / short-put dealer book is **net LONG delta** (net_dex >= 0).
The convention is therefore: *dealer dollar-delta*, positive when the dealer is
long the underlying. ``M * F`` converts (delta * contracts) into USD notional.

Thin / illiquid strikes
=======================
Strikes flagged ``thin`` upstream (step 1.2: mid missing/zero/crossed, so the
IV — and hence the IV-derived gamma/delta — is unreliable) have their
**greeks linearly interpolated by strike from the nearest non-thin neighbours**
before the exposure is computed; the resulting profile entry is marked
``interpolated=True``. Observed ``VOL`` is real market data and is never
interpolated. At a boundary (only one non-thin neighbour) the nearest neighbour
value is carried flat; if no non-thin strike exists at all the greeks default to
zero (still flagged interpolated).

Only the standard library is used.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass
from typing import List, Sequence, Tuple

__all__ = [
    "DEALER_SIGN_CALL",
    "DEALER_SIGN_PUT",
    "GEX_PCT_SCALE",
    "ChainRow",
    "StrikeExposure",
    "strike_exposure",
    "build_profile",
    "net_gamma",
    "profile_to_dicts",
]

#: Locked dealer convention.
DEALER_SIGN_CALL: float = 1.0    # dealer LONG calls
DEALER_SIGN_PUT: float = -1.0    # dealer SHORT puts
#: GEX scaling: dollar-gamma -> USD change in dealer dollar-delta per 1% move.
GEX_PCT_SCALE: float = 0.01

#: Greek fields interpolated for thin strikes (order matters — see _interp_greeks).
_GREEK_FIELDS: Tuple[str, str, str, str] = (
    "call_gamma",
    "put_gamma",
    "call_delta",
    "put_delta",
)


@dataclass(frozen=True)
class ChainRow:
    """One per-strike option-chain row after IV + greeks are computed.

    ``call_vol`` / ``put_vol`` are the cumulative volumes since the RTH open for
    each leg. ``call_oi`` / ``put_oi`` are carried for the OI-based wall logic in
    a later task and are unused here. ``multiplier`` / ``forward`` are optional
    per-row echoes; the instrument-level ``M`` and snapshot-level ``F`` passed to
    :func:`build_profile` are authoritative.
    """

    strike: float
    call_gamma: float
    put_gamma: float
    call_delta: float
    put_delta: float
    call_vol: float
    put_vol: float
    call_oi: float = 0.0
    put_oi: float = 0.0
    thin: bool = False
    multiplier: float | None = None
    forward: float | None = None
    # Per-leg IV + year-fraction, carried so the TRACE-style field projection
    # (engine.field.build_field) can RE-EVALUATE Black-76 gamma/delta at each
    # hypothetical spot. None when the leg is thin / IV unsolved -> contributes 0.
    call_iv: float | None = None
    put_iv: float | None = None
    t_expiry: float | None = None


@dataclass(frozen=True)
class StrikeExposure:
    """Profile entry. Field names match the Snapshot ``profile[]`` contract."""

    strike: float
    net_gex: float
    net_dex: float
    interpolated: bool


def strike_exposure(
    call_gamma: float,
    put_gamma: float,
    call_delta: float,
    put_delta: float,
    call_vol: float,
    put_vol: float,
    M: float,
    F: float,
) -> Tuple[float, float]:
    """Pure (net_gex, net_dex) for a single strike under the locked convention.

    net_gex [USD / 1% move] = (sign_c*cg*cvol + sign_p*pg*pvol) * M * F^2 * 0.01
    net_dex [USD notional]  = (sign_c*cd*cvol + sign_p*pd*pvol) * M * F
    """
    gamma_term = (
        DEALER_SIGN_CALL * call_gamma * call_vol
        + DEALER_SIGN_PUT * put_gamma * put_vol
    )
    delta_term = (
        DEALER_SIGN_CALL * call_delta * call_vol
        + DEALER_SIGN_PUT * put_delta * put_vol
    )
    net_gex = gamma_term * M * F * F * GEX_PCT_SCALE
    net_dex = delta_term * M * F
    return net_gex, net_dex


def _interp_greeks(
    strike: float,
    non_thin: Sequence[ChainRow],
    nt_strikes: Sequence[float],
) -> Tuple[float, float, float, float]:
    """Linear-in-strike interpolation of greeks from nearest non-thin neighbours.

    Boundary: only one neighbour -> carry flat. No neighbours -> zeros.
    """
    if not non_thin:
        return (0.0, 0.0, 0.0, 0.0)

    i = bisect.bisect_left(nt_strikes, strike)
    if i <= 0:
        lo = hi = non_thin[0]
    elif i >= len(non_thin):
        lo = hi = non_thin[-1]
    else:
        lo, hi = non_thin[i - 1], non_thin[i]

    sa, sb = lo.strike, hi.strike
    span = sb - sa

    def lerp(attr: str) -> float:
        va = float(getattr(lo, attr))
        vb = float(getattr(hi, attr))
        if span == 0.0:
            return va
        return va + (vb - va) * (strike - sa) / span

    return (
        lerp("call_gamma"),
        lerp("put_gamma"),
        lerp("call_delta"),
        lerp("put_delta"),
    )


def build_profile(
    chain: Sequence[ChainRow],
    M: float,
    F: float,
) -> List[StrikeExposure]:
    """Build the per-strike exposure profile (ascending by strike).

    For thin strikes the greeks are interpolated from non-thin neighbours and the
    entry is flagged ``interpolated=True``; observed volumes are kept as-is.
    """
    rows = sorted(chain, key=lambda r: r.strike)
    non_thin = [r for r in rows if not r.thin]
    nt_strikes = [r.strike for r in non_thin]

    profile: List[StrikeExposure] = []
    for r in rows:
        if r.thin:
            cg, pg, cd, pd = _interp_greeks(r.strike, non_thin, nt_strikes)
            interpolated = True
        else:
            cg, pg, cd, pd = (
                r.call_gamma,
                r.put_gamma,
                r.call_delta,
                r.put_delta,
            )
            interpolated = False

        net_gex, net_dex = strike_exposure(
            cg, pg, cd, pd, r.call_vol, r.put_vol, M, F
        )
        profile.append(
            StrikeExposure(
                strike=r.strike,
                net_gex=net_gex,
                net_dex=net_dex,
                interpolated=interpolated,
            )
        )
    return profile


def net_gamma(profile: Sequence[StrikeExposure]) -> float:
    """Aggregate net gamma for the regime classifier = sum of per-strike net_gex.

    Units USD per 1% move. Sign drives the regime: > 0 pinning, < 0 volatile.
    """
    return sum(e.net_gex for e in profile)


def profile_to_dicts(
    profile: Sequence[StrikeExposure],
) -> List[dict]:
    """Serialise to the Snapshot ``profile[]`` dict shape (for step 1.3)."""
    return [
        {
            "strike": e.strike,
            "net_gex": e.net_gex,
            "net_dex": e.net_dex,
            "interpolated": e.interpolated,
        }
        for e in profile
    ]
