"""Key-level detection for FlowDesk (overlay on the heatmap / profile).

Produces the Snapshot ``levels`` block (``schema_version`` 1):
``{call_walls[], put_walls[], gamma_flip, largest_gex, largest_dex}``.

Locked semantics (PRD #0 §2, Divergence #2 resolved -> option B, gamma-dollar)
=============================================================================
* **Call / Put Wall — by GAMMA-DOLLAR (IV-weighted), STATIC for the day.**
  Each strike's wall weight is ``gamma_side * OI_side`` (the dollar scale
  ``M * F^2 * 0.01`` is constant across strikes within a snapshot, so it does not
  change the ranking and is omitted here). ``gamma_side`` is the Black-76 gamma
  from the IV-solved smile; ``OI_side`` is the day's open interest for that leg.
  This supersedes the original "largest raw OI" rule (Divergence #2, approved
  option B): research shows the dealer hedging wall sits at the largest gamma-$
  concentration, not the largest head-count of contracts. A strike with huge OI
  but negligible gamma (deep ITM / far OTM) no longer mis-ranks as a wall.
  - Call walls: the Top-N strikes **strictly above** the forward with the
    largest *call* gamma-$ (``call_gamma * call_oi``).
  - Put walls : the Top-N strikes **strictly below** the forward with the
    largest *put* gamma-$ (``put_gamma * put_oi``).
  Returned rank-ordered (index 0 = rank 1 = largest gamma-$). **Deterministic**
  tie-break: ``(weight desc, |strike - forward| asc, strike asc)``. Thin strikes
  (gamma unsolved -> 0) carry zero weight and never rank as walls.

  Degenerate case: when the points carry no gamma (the convenience
  :class:`StrikeOI` defaults ``call_gamma == put_gamma == 1.0``) the weight
  collapses to raw OI, so OI-only fixtures rank exactly as before.
* **Gamma Flip — by VOLUME, dynamic.** The zero-crossing strike of the
  *cumulative* net gamma (running sum of ``net_gex`` over ascending strikes),
  linearly interpolated at the crossing. ``None`` if cumulative net gamma never
  crosses zero.
* **Largest GEX / Largest DEX — by VOLUME, dynamic.** The strike maximising
  ``|net_gex|`` / ``|net_dex|`` respectively. ``None`` for an empty profile.

Gamma-$ (OI) drives ONLY the walls; every VOL-based level is derived from the
volume-based exposure profile. Only the standard library is used.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Protocol, Sequence

__all__ = [
    "ProfilePoint",
    "OIPoint",
    "StrikeOI",
    "call_walls",
    "put_walls",
    "gamma_flip",
    "largest_gex",
    "largest_dex",
    "compute_levels",
]


class ProfilePoint(Protocol):
    """Structural type for a VOL-based profile row (matches ``StrikeExposure``)."""

    strike: float
    net_gex: float
    net_dex: float


class OIPoint(Protocol):
    """Structural type for a per-strike OI + gamma row (matches ``ChainRow``).

    ``call_gamma`` / ``put_gamma`` are the Black-76 per-leg gammas from the
    IV-solved smile; combined with OI they give the gamma-$ wall weight. A row
    that exposes only OI (no gamma) is handled by :class:`StrikeOI`, whose gamma
    defaults to ``1.0`` so the weight collapses to raw OI.
    """

    strike: float
    call_oi: float
    put_oi: float
    call_gamma: float
    put_gamma: float


@dataclass(frozen=True)
class StrikeOI:
    """Convenience concrete OI row for standalone use / fixtures.

    ``call_gamma`` / ``put_gamma`` default to ``1.0`` so that, absent real
    greeks, the gamma-$ wall weight (``gamma * OI``) reduces to plain OI — the
    pre-Divergence-#2 behaviour, kept for OI-only fixtures and back-compat.
    """

    strike: float
    call_oi: float
    put_oi: float
    call_gamma: float = 1.0
    put_gamma: float = 1.0


def _walls(
    oi: Sequence[OIPoint],
    forward: float,
    *,
    side: str,
    top_n: int,
) -> List[float]:
    """Shared wall logic by GAMMA-DOLLAR. ``side`` is "call" (above) or "put" (below).

    Weight = ``gamma_side * OI_side`` (dollar scale ``M*F^2*0.01`` is constant
    across strikes, so it is omitted — it cannot change the ranking). Strikes
    with non-positive weight (zero OI or thin/zero gamma) are excluded.
    """
    if side == "call":
        cand = [r for r in oi if r.strike > forward]
        def weight_of(r: OIPoint) -> float:
            return float(r.call_gamma) * float(r.call_oi)
    else:
        cand = [r for r in oi if r.strike < forward]
        def weight_of(r: OIPoint) -> float:
            return float(r.put_gamma) * float(r.put_oi)
    # Deterministic: gamma-$ desc, then nearer-to-forward first, then strike asc.
    ranked = [(weight_of(r), r) for r in cand]
    ranked = [(w, r) for w, r in ranked if w > 0.0]
    ranked.sort(key=lambda wr: (-wr[0], abs(float(wr[1].strike) - forward), float(wr[1].strike)))
    return [float(r.strike) for _, r in ranked[:top_n]]


def call_walls(
    oi: Sequence[OIPoint], forward: float, top_n: int = 3
) -> List[float]:
    """Top-N call gamma-$ strikes strictly ABOVE the forward, rank-ordered."""
    return _walls(oi, forward, side="call", top_n=top_n)


def put_walls(
    oi: Sequence[OIPoint], forward: float, top_n: int = 3
) -> List[float]:
    """Top-N put gamma-$ strikes strictly BELOW the forward, rank-ordered."""
    return _walls(oi, forward, side="put", top_n=top_n)


def gamma_flip(
    profile: Sequence[ProfilePoint], forward: Optional[float] = None
) -> Optional[float]:
    """Zero-crossing strike of cumulative net gamma (interpolated).

    Cumulative net gamma ``C_k = sum_{j<=k} net_gex_j`` over ascending strikes.
    A crossing between strikes ``k-1`` and ``k`` (where ``C`` changes sign) is
    linearly interpolated:
        flip = s[k-1] + (s[k]-s[k-1]) * (0 - C[k-1]) / (C[k] - C[k-1]).
    Exact nodes (``C_k == 0``) are returned as the strike itself.

    When several crossings exist the one nearest ``forward`` is returned (if
    ``forward`` is given), else the lowest-strike crossing. ``None`` if no
    crossing exists.
    """
    rows = sorted(profile, key=lambda p: p.strike)
    n = len(rows)
    if n == 0:
        return None
    xs = [float(p.strike) for p in rows]

    cum: List[float] = []
    running = 0.0
    for p in rows:
        running += float(p.net_gex)
        cum.append(running)

    candidates: List[float] = []
    # Exact zero at a node.
    for i in range(n):
        if cum[i] == 0.0:
            candidates.append(xs[i])
    # Sign change strictly between two nodes.
    for i in range(1, n):
        a, b = cum[i - 1], cum[i]
        if a == 0.0 or b == 0.0:
            continue
        if (a < 0.0 < b) or (a > 0.0 > b):
            candidates.append(xs[i - 1] + (xs[i] - xs[i - 1]) * (0.0 - a) / (b - a))

    if not candidates:
        return None
    candidates = sorted(set(candidates))
    if forward is not None:
        return min(candidates, key=lambda x: (abs(x - forward), x))
    return candidates[0]


def largest_gex(
    profile: Sequence[ProfilePoint], forward: Optional[float] = None
) -> Optional[float]:
    """Strike with the largest ``|net_gex|``. ``None`` if profile is empty."""
    return _argmax_abs(profile, lambda p: float(p.net_gex), forward)


def largest_dex(
    profile: Sequence[ProfilePoint], forward: Optional[float] = None
) -> Optional[float]:
    """Strike with the largest ``|net_dex|``. ``None`` if profile is empty."""
    return _argmax_abs(profile, lambda p: float(p.net_dex), forward)


def _argmax_abs(
    profile: Sequence[ProfilePoint],
    value,
    forward: Optional[float],
) -> Optional[float]:
    """Strike maximising ``|value|``; tie-break nearer-forward then strike asc."""
    if not profile:
        return None
    f = forward if forward is not None else 0.0
    best = max(
        profile,
        key=lambda p: (
            abs(value(p)),
            -abs(float(p.strike) - f),
            -float(p.strike),
        ),
    )
    return float(best.strike)


def compute_levels(
    profile: Sequence[ProfilePoint],
    oi: Sequence[OIPoint],
    forward: float,
    top_n: int = 3,
) -> dict:
    """Assemble the Snapshot ``levels`` block.

    ``call_walls`` / ``put_walls`` are STATIC (OI); the caller computes them once
    at/after the RTH open and reuses them all day. ``gamma_flip`` /
    ``largest_gex`` / ``largest_dex`` are dynamic (VOL) and recomputed each
    minute.
    """
    return {
        "call_walls": call_walls(oi, forward, top_n),
        "put_walls": put_walls(oi, forward, top_n),
        "gamma_flip": gamma_flip(profile, forward),
        "largest_gex": largest_gex(profile, forward),
        "largest_dex": largest_dex(profile, forward),
    }
