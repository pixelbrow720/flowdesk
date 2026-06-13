"""Proprietary-style key levels (REVERSE-ENGINEERED APPROXIMATIONS — EXPERIMENTAL).

EXPERIMENTAL / NOT OFFICIAL. These are FlowDesk's best-effort reverse-engineering of
SpotGamma's *named* proprietary levels (Volatility Trigger™, Absolute Gamma, Hedge
Wall). SpotGamma does NOT publish their exact formulas — the definitions here are
INFERRED from public descriptions (docs/research/archive/riset-spotgamma.md §C12/§444)
and will NOT match SpotGamma's numbers. They are additive research overlays that live
ALONGSIDE the locked VOL-based product levels (``engine.levels``) and do NOT replace
or modify them. Consumers/FE MUST label these as approximations, not authoritative.

Basis: **open-interest gamma** (carried-in OI × Black-76 gamma), NOT cumulative VOL —
SpotGamma's levels are OI/positioning-based and STATIC for the day, distinct from the
engine's dynamic VOL-based ``gamma_flip``/``largest_gex``. Locked dealer signs reused
(``+1`` call / ``-1`` put). The dollar scale ``M·F²·0.01`` is constant across strikes,
so it does not change any argmax or zero-crossing and is omitted here.

Levels (all INFERRED):
  * **Volatility Trigger** — the price where the *cumulative* net OI-gamma crosses
    zero (ascending by strike), linearly interpolated. Below it dealers are net short
    gamma (vol-amplifying), above it net long (vol-suppressing). The OI/static analogue
    of the VOL-based ``gamma_flip``. ``None`` if it never crosses.
  * **Absolute Gamma strike** — the strike with the largest TOTAL OI-gamma
    concentration ``call_gamma·call_oi + put_gamma·put_oi`` (both sides add; the single
    biggest hedging node by raw magnitude). ``None`` for an empty/thin chain.
  * **Hedge Wall** — the strike with the largest ``|net OI-gamma|`` (signed by dealer
    convention); the dominant *net* dealer hedging node. ``None`` for empty/thin.

Thin strikes (gamma unsolved upstream) are SKIPPED, never fabricated.
Only the standard library + sibling ``engine.exposure`` constants are used.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from engine.exposure import DEALER_SIGN_CALL, DEALER_SIGN_PUT, ChainRow

__all__ = [
    "ProprietaryLevels",
    "net_oi_gamma_profile",
    "volatility_trigger",
    "absolute_gamma_strike",
    "hedge_wall",
    "build_proprietary",
]


@dataclass(frozen=True)
class ProprietaryLevels:
    """Reverse-engineered SpotGamma-style levels (EXPERIMENTAL — NOT official).

    All in index points (price levels), ``None`` when not computable. These are
    INFERRED approximations on the OI-gamma basis, NOT SpotGamma's published values.
    """

    volatility_trigger: Optional[float]
    abs_gamma_strike: Optional[float]
    hedge_wall: Optional[float]

    def to_dict(self) -> dict[str, Optional[float]]:
        return {
            "volatility_trigger": self.volatility_trigger,
            "abs_gamma_strike": self.abs_gamma_strike,
            "hedge_wall": self.hedge_wall,
        }


def net_oi_gamma_profile(rows: Sequence[ChainRow]) -> List[Tuple[float, float]]:
    """``[(strike, net_oi_gamma)]`` ascending by strike, skipping thin strikes.

    ``net_oi_gamma = SIGN_C·call_gamma·call_oi + SIGN_P·put_gamma·put_oi`` (locked
    dealer signs; the constant ``M·F²·0.01`` scale is omitted — it changes no
    argmax/zero-crossing). Thin strikes (gamma unsolved) contribute nothing.
    """
    out: List[Tuple[float, float]] = []
    for r in sorted(rows, key=lambda r: r.strike):
        if r.thin:
            continue
        g = (
            DEALER_SIGN_CALL * r.call_gamma * r.call_oi
            + DEALER_SIGN_PUT * r.put_gamma * r.put_oi
        )
        out.append((r.strike, g))
    return out


def volatility_trigger(rows: Sequence[ChainRow]) -> Optional[float]:
    """Zero-crossing of the cumulative net OI-gamma (linear-interpolated), or ``None``.

    The OI/static analogue of the VOL-based gamma flip: scanning strikes ascending,
    the price where the running sum of net OI-gamma crosses zero.
    """
    prof = net_oi_gamma_profile(rows)
    if len(prof) < 2:
        return None
    cum = 0.0
    prev_k: Optional[float] = None
    prev_cum = 0.0
    for k, g in prof:
        cum += g
        if prev_k is not None and prev_cum != 0.0 and (prev_cum < 0.0) != (cum < 0.0):
            # linear interpolation of the crossing between prev_k and k
            span = cum - prev_cum
            frac = 0.0 if span == 0.0 else -prev_cum / span
            return prev_k + (k - prev_k) * frac
        prev_k, prev_cum = k, cum
    return None


def absolute_gamma_strike(rows: Sequence[ChainRow]) -> Optional[float]:
    """Strike of the largest TOTAL OI-gamma ``call_gamma·call_oi + put_gamma·put_oi``."""
    best_k: Optional[float] = None
    best_v = -1.0
    for r in rows:
        if r.thin:
            continue
        total = abs(r.call_gamma * r.call_oi) + abs(r.put_gamma * r.put_oi)
        if total > best_v:
            best_v, best_k = total, r.strike
    return best_k


def hedge_wall(rows: Sequence[ChainRow]) -> Optional[float]:
    """Strike of the largest ``|net OI-gamma|`` (dominant net dealer hedging node)."""
    best_k: Optional[float] = None
    best_v = -1.0
    for k, g in net_oi_gamma_profile(rows):
        if abs(g) > best_v:
            best_v, best_k = abs(g), k
    return best_k


def build_proprietary(rows: Sequence[ChainRow]) -> ProprietaryLevels:
    """Build the reverse-engineered proprietary levels (EXPERIMENTAL approximations)."""
    return ProprietaryLevels(
        volatility_trigger=volatility_trigger(rows),
        abs_gamma_strike=absolute_gamma_strike(rows),
        hedge_wall=hedge_wall(rows),
    )
