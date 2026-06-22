"""Volatility expansion — standard deviation of implied volatility across strikes.

EXPERIMENTAL / NOT PRICE-VALIDATED. Measures how wide the implied-volatility
distribution is across the strike chain at a given minute. Wider distribution
= more vol expansion (uncertainty across strikes); tighter = vol contraction
(market agreement on where fair value is).

What it is
==========
For each minute, collect all non-thin strikes' implied volatilities (call and
put), then compute:

  vol_expansion = std(call_ivs + put_ivs)

This is a simple proxy for how much disagreement there is across strikes about
what the fair volatility is. High values = market is uncertain/expanding;
low values = market is compressed/agreeing.

Sign reading
============
We don't assign a sign — vol expansion is a magnitude (always positive). The
sign is implicit: high = expansion, low = contraction. The FE can color-code
based on thresholds (e.g. > 0.10 = crimson expansion, < 0.05 = turquoise
contraction).

Thin strikes (ChainRow.thin — IV unsolved upstream) are SKIPPED: we do NOT
fabricate IVs where the solver failed. ``None`` is returned if the chain has
fewer than 2 non-thin strikes (can't compute std dev with 1 or 0 samples).

Implementation notes
===================
Naive O(n) — compute mean, then sum of squared deviations, then sqrt. For
n ≈ 50 strikes per side (100 total) this is trivial.

The returned value is in vol units (same as ``atm_vol`` in the SVI surface),
so it's comparable across time but not directly comparable to GEX/DEX (which
are in dollar terms).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence

from engine.exposure import ChainRow

__all__ = [
    "VolExpansionSnapshot",
    "vol_expansion",
    "build_vol_expansion",
]


@dataclass(frozen=True)
class VolExpansionSnapshot:
    """Volatility expansion metric (EXPERIMENTAL — NOT price-validated).

    ``expansion`` is the standard deviation of implied volatilities across all
    non-thin strikes (call + put), in vol units (same as ``atm_vol``).
    ``None`` if the chain has fewer than 2 non-thin strikes.
    """

    expansion: Optional[float]

    def to_dict(self) -> dict[str, Optional[float]]:
        return {"expansion": self.expansion}


def vol_expansion(rows: Sequence[ChainRow]) -> Optional[float]:
    """Standard deviation of implied volatilities across strikes.

    Collects all non-thin call_iv and put_iv values, computes std dev. Returns
    ``None`` if fewer than 2 samples.
    """
    ivs: list[float] = []
    for r in rows:
        if r.thin:
            continue
        if r.call_iv is not None:
            ivs.append(r.call_iv)
        if r.put_iv is not None:
            ivs.append(r.put_iv)
    
    if len(ivs) < 2:
        return None
    
    mean = sum(ivs) / len(ivs)
    variance = sum((iv - mean) ** 2 for iv in ivs) / len(ivs)
    return math.sqrt(variance)


def build_vol_expansion(rows: Sequence[ChainRow]) -> VolExpansionSnapshot:
    """Build the vol-expansion snapshot (EXPERIMENTAL)."""
    return VolExpansionSnapshot(expansion=vol_expansion(rows))
