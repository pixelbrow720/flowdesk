"""Max pain — strike that minimises total option-holder payoff at expiry.

EXPERIMENTAL / METHODOLOGICALLY CONTROVERSIAL. The "max pain" hypothesis says
options expire worthless near a price that hurts the most holders; it is a
popular retail heuristic and some dealer-hedging tools use it as a magnet.
It is NOT a validated price-magnet predictor (no published statistical edge in
academic literature; see docs/research for context). Provided here as a
research overlay — consumers MUST label ``max_pain`` as an INFERRED retail
heuristic, not an authoritative level.

What it is
==========
For each candidate strike K, compute the payoff at expiry to all option
holders (assuming they exercise ITM):

  payoff(K) = Σ over each leg:
                |S - K| × OI_side,    summed across call + put

(The call leg pays ``max(F - K, 0) · call_oi`` and the put leg pays
``max(K - F, 0) · put_oi``; we sum both for every candidate K.)

Max pain = the strike K that MINIMISES ``payoff(K)`` (the strike where option
holders collectively lose the most, so dealers owe the least).

The dollar scale (``M``) is constant across K, so it is omitted — it does not
change the argmin.

Thin strikes (ChainRow.thin — IV unsolved upstream) are SKIPPED: we do NOT
fabricate OI contributions for them. ``None`` is returned if the chain has no
non-thin strikes.

Implementation notes
===================
Naive O(m^2) — for m non-thin strikes, compute payoff at each. For a 0DTE book
with ~50 strikes per side this is ~2500 operations per minute — trivial. No
precomputation needed; the loop below is the whole thing.

The dollar scale is intentionally OMITTED from the returned strike (the level is
in INDEX POINTS, same convention as all other level fields in the snapshot —
see ``engine.levels.Levels``).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from engine.exposure import ChainRow

__all__ = [
    "MaxPainSnapshot",
    "compute_payoff",
    "max_pain",
    "build_max_pain",
]


@dataclass(frozen=True)
class MaxPainSnapshot:
    """Max-pain strike (EXPERIMENTAL retail heuristic — NOT validated).

    ``strike`` is in INDEX POINTS (same convention as ``levels.call_walls`` etc.).
    ``None`` if the chain has no non-thin strikes to evaluate.
    """

    strike: Optional[float]

    def to_dict(self) -> dict[str, Optional[float]]:
        return {"strike": self.strike}


def compute_payoff(F: float, K: float, call_oi: float, put_oi: float) -> float:
    """Total option-holder payoff at expiry if the underlying settles at ``F``
    and the strike in question is ``K``.

    ``max(F - K, 0) · call_oi + max(K - F, 0) · put_oi``. Multiplier ``M`` is
    omitted because it is constant across ``K`` and does not change the argmin.
    """
    return max(F - K, 0.0) * call_oi + max(K - F, 0.0) * put_oi


def max_pain(F: float, rows: Sequence[ChainRow]) -> Optional[float]:
    """Return the strike that minimises total option-holder payoff at expiry.

    ``None`` if the chain has no non-thin strikes.
    """
    # Only non-thin rows contribute to payoff (thins have IV unsolved; OI may
    # still be valid but we can't reliably include them — engine-level policy
    # elsewhere skips thins for any greek or OI-aggregate computation).
    candidates = [r for r in rows if not r.thin and (r.call_oi > 0 or r.put_oi > 0)]
    if not candidates:
        return None

    # Candidate K = union of all strikes from both sides. Cheap (m ≈ 50).
    ks: list[float] = []
    seen: set[float] = set()
    for r in candidates:
        if r.strike not in seen:
            seen.add(r.strike)
            ks.append(r.strike)

    # OI lookup indexed by strike.
    oi_by_strike: dict[float, tuple[float, float]] = {}
    for r in candidates:
        oi_by_strike[r.strike] = (r.call_oi, r.put_oi)

    best_k: Optional[float] = None
    best_payoff = float("inf")
    for K in ks:
        total = 0.0
        for r in candidates:
            co, po = oi_by_strike[r.strike]
            total += compute_payoff(F, K, co, po)
        if total < best_payoff:
            best_payoff = total
            best_k = K
    return best_k


def build_max_pain(F: float, rows: Sequence[ChainRow]) -> MaxPainSnapshot:
    """Build the max-pain snapshot (EXPERIMENTAL retail heuristic)."""
    return MaxPainSnapshot(strike=max_pain(F, rows))
