"""DDOI — synthetic Dealer Directional Open-Interest GEX basis (EXPERIMENTAL).

EXPERIMENTAL / NOT PRICE-VALIDATED. Additive research lens that lives ALONGSIDE the
locked VOL-based product GEX (it does NOT replace or modify ``engine.exposure``).
On the validated 8-day exploratory run this read FLAT vs the VOL baseline
(sign-agreement 49.2% vs 50.8%, Δ within noise) — the *machine* is sound, the edge
is not proven. Consumers/FE MUST treat ``ddoi`` as experimental, not authoritative.

The idea (docs/research/empirical/track-f-ddoi-exposure-vol.md, TRACK D.6)
=========================================================================
Cumulative VOL and official ΔOI measure DIFFERENT things: VOL is net *direction* of
pressure (``Σ aggressor_sign·size``); ΔOI is contracts *outstanding* (open minus
close), direction-agnostic. So VOL-vs-ΔOI sign-agreement is ~50% by construction.
DDOI estimates a signed per-leg **synthetic ΔOI** by classifying each trade OPEN vs
CLOSE from its intraday TIME position — early trades treated as opening (build OI),
late trades as closing (square up before the 0DTE 16:00 ET expiry) — then drives the
SAME locked dealer-sign + gamma GEX template with that basis instead of VOL:

    ddoi_gex = (SIGN_C·γ_call·ddoi_call + SIGN_P·γ_put·ddoi_put) · M · F² · 0.01

where ``ddoi_leg = Σ_i w(i)·|size_i|`` with the intraday time weight
``w(i) = 1 − 2·(i/(n−1))`` (+1 for the first trade of the day on that leg, linearly
to −1 for the last). ``ddoi_leg > 0`` ⇒ net OPENING (synthetic OI rose), ``< 0`` ⇒
net CLOSING. This is:
  * **non-circular** — never reads official ΔOI;
  * **orthogonal to VOL** — uses ``|size|`` + a time weight, NOT the aggressor sign,
    so it cannot telescope back to ±VOL (the bug in an earlier net-position version);
  * a **TIME-WEIGHT HEURISTIC**, not ground truth — the tape does not label open vs
    close. Honest limitation, carried from the validated analysis/ddoi.py.

The per-leg ``ddoi_flow`` map is built caller-side (the worker, from the timestamped
trade tape, chronologically ordered); this engine module just applies the locked
dealer signs + gamma + scale, skipping thin strikes (gamma unsolved upstream).

Only the standard library + sibling ``engine.exposure`` constants are used.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from engine.exposure import (
    DEALER_SIGN_CALL,
    DEALER_SIGN_PUT,
    GEX_PCT_SCALE,
    ChainRow,
)
from engine.synthetic_oi import FlowKey

__all__ = [
    "DdoiSnapshot",
    "ddoi_time_weight",
    "ddoi_gex",
    "build_ddoi",
]


def ddoi_time_weight(i: int, n: int) -> float:
    """Intraday open/close time weight for the ``i``-th of ``n`` chronological trades.

    ``+1`` for the FIRST trade of the day on a leg (treated as opening), linearly to
    ``-1`` for the LAST (treated as closing): ``w = 1 − 2·(i/(n−1))``. A single trade
    (``n == 1``) gets ``+1`` (opening). Rationale: 0DTE positions open intraday and
    must close/expire by 16:00 ET, so opening volume skews early, closing late. This
    is a HEURISTIC — the tape does not label open vs close. ``i`` is 0-based.
    """
    if n <= 1:
        return 1.0
    return 1.0 - 2.0 * (i / (n - 1))


@dataclass(frozen=True)
class DdoiSnapshot:
    """DDOI aggregate for one minute (EXPERIMENTAL).

    ``gex`` is the synthetic-ΔOI GEX (USD per 1% move) on the open/close-classified
    basis; ``sign`` is its sign. A divergence from the locked VOL-GEX sign flags
    where the open/close reconstruction disagrees with raw traded volume. NOT
    price-validated; read flat vs VOL on the 8-day exploratory sample.
    """

    gex: float
    sign: int

    def to_dict(self) -> dict[str, float]:
        return {"gex": self.gex, "sign": self.sign}


def ddoi_gex(
    rows: Sequence[ChainRow],
    ddoi_flow: Mapping[FlowKey, float],
    M: float,
    F: float,
) -> float:
    """Synthetic-ΔOI GEX on the locked dealer-sign + gamma template. Skips thin strikes.

    ``ddoi_flow[(strike, is_call)]`` is the per-leg synthetic ΔOI (signed open/close
    estimate, built caller-side). GEX = ``Σ (SIGN_C·γ_call·ddoi_call +
    SIGN_P·γ_put·ddoi_put) · M·F²·0.01`` — identical scaling/signs to the locked
    VOL-GEX, with the synthetic-ΔOI basis in place of cumulative VOL.
    """
    scale = M * F * F * GEX_PCT_SCALE
    total = 0.0
    for r in rows:
        if r.thin:
            continue  # gamma unsolved upstream -> do not fabricate a contribution
        c = float(ddoi_flow.get((r.strike, True), 0.0))
        p = float(ddoi_flow.get((r.strike, False), 0.0))
        total += (
            DEALER_SIGN_CALL * r.call_gamma * c
            + DEALER_SIGN_PUT * r.put_gamma * p
        ) * scale
    return total


def build_ddoi(
    rows: Sequence[ChainRow],
    ddoi_flow: Mapping[FlowKey, float],
    M: float,
    F: float,
) -> DdoiSnapshot:
    """Build the DDOI aggregate (synthetic-ΔOI GEX + sign)."""
    gex = ddoi_gex(rows, ddoi_flow, M, F)
    sign = 1 if gex > 0.0 else (-1 if gex < 0.0 else 0)
    return DdoiSnapshot(gex=gex, sign=sign)
