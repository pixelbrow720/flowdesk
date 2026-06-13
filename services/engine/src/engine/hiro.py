"""HIRO — Hedging Impact of Real-time Options (FlowGreeks flow module).

Cumulative dealer **delta-notional** hedging flow, accumulated per trade since
the RTH open (reset daily). Where TRACE/GEX is *stock* (positioning), HIRO is
*flow* (what the dealer is being forced to do right now), so it leads.

Core formula (mega-riset §B3)
=============================
    HIRO_t = Σ_{trade k <= t}  s_k · δ_k · q_k · M · F_k

  * ``s_k``  = aggressor sign (±1): CME ``side`` field, ``B`` (buy-aggressor,
               lifted the ask) -> +1, ``A`` (sell-aggressor, hit the bid) -> -1,
               ``N`` (no aggressor) -> 0.
  * ``δ_k``  = Black-76 option delta at the trade (calls > 0, puts < 0).
  * ``q_k``  = traded contracts (size).
  * ``M``    = instrument multiplier (USD/pt): /ES 50, /NQ 20.
  * ``F_k``  = forward (futures) price at the trade.

Sign reading (mega-riset §B5): a customer BUYING a call (``s=+1``, ``δ>0``) makes
the term positive -> the dealer must BUY the underlying to stay hedged (upward
hedging pressure). A customer buying a PUT (``s=+1``, ``δ<0``) makes it negative
-> the dealer SELLS the underlying. So positive cumulative HIRO == net dealer
buying pressure (bullish), negative == selling pressure (bearish).

Breakdown (mega-riset §B8): Total, Calls, Puts, 0DTE (``T < 1/365``) and Retail.
**Retail is a heuristic proxy** (small odd-lot size) — the real SpotGamma
customer/dealer + retail classifier is proprietary; see :data:`RETAIL_MAX_SIZE`
and treat the retail line as indicative only (TODO: refine with block/multi-leg
filters).

This module is PURE and **isolated**: it does NOT touch the Snapshot contract
(``schema_version`` 1) — output lives in :class:`HiroSnapshot` / :class:`HiroSeries`
until a schema decision is taken (Divergence #5). The delta is priced with the
sibling :mod:`engine.black76` / :mod:`engine.iv` (IV solved from the trade price
unless an explicit per-trade IV is supplied), so HIRO reuses the exact same
pricing core as the rest of the engine.

Only the standard library + sibling ``engine`` modules are used.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Sequence

from engine.black76 import OptionType
from engine.black76 import delta as bs_delta
from engine.iv import implied_vol

__all__ = [
    "ZERO_DTE_T",
    "RETAIL_MAX_SIZE",
    "AggressorSide",
    "aggressor_sign",
    "HiroTrade",
    "HiroSnapshot",
    "HiroSeries",
    "signed_delta_notional",
    "HiroState",
    "hiro_series",
]

#: Year-fraction below which a contract counts as 0DTE for the breakdown line
#: (mega-riset §D: ``T < 1/365``).
ZERO_DTE_T: float = 1.0 / 365.0
#: Heuristic retail size ceiling: trades with ``size <= RETAIL_MAX_SIZE`` feed
#: the (proxy) retail line. PROPRIETARY in SpotGamma — this is an odd-lot proxy
#: only. ``0`` disables the retail breakdown.
RETAIL_MAX_SIZE: float = 5.0

#: CME aggressor side codes.
AggressorSide = str  # "B" | "A" | "N" (validated by aggressor_sign)


def aggressor_sign(side: str) -> int:
    """Map a CME aggressor ``side`` to a flow sign.

    ``B`` (buy-aggressor / at-ask) -> ``+1``; ``A`` (sell-aggressor / at-bid) ->
    ``-1``; ``N`` / unknown -> ``0`` (no directional contribution). Case- and
    whitespace-insensitive.
    """
    s = side.strip().upper()
    if s == "B":
        return 1
    if s == "A":
        return -1
    return 0


@dataclass(frozen=True)
class HiroTrade:
    """One option trade off the tape (engine input for HIRO).

    ``t_expiry`` is the year-fraction to expiry at the trade; ``iv`` may be
    supplied (e.g. from the per-minute surface) to skip the per-trade IV solve.
    """

    strike: float
    is_call: bool
    price: float
    size: float
    side: AggressorSide
    t_expiry: float
    iv: Optional[float] = None
    ts: Optional[datetime] = None
    """Trade timestamp (UTC). Optional; carried for time-decay-weighted lenses
    (synthetic-OI #5). HIRO itself does not use it."""


@dataclass(frozen=True)
class HiroSnapshot:
    """Cumulative HIRO at one instant (USD delta-notional), with breakdown."""

    total: float
    calls: float
    puts: float
    zerodte: float
    retail: float

    def to_dict(self) -> dict[str, float]:
        return {
            "total": self.total,
            "calls": self.calls,
            "puts": self.puts,
            "zerodte": self.zerodte,
            "retail": self.retail,
        }


@dataclass(frozen=True)
class HiroSeries:
    """A HIRO run: the final cumulative state plus the per-trade cumulative path.

    ``cumulative`` is the running ``total`` after each accepted trade (the line
    drawn on the chart); ``skipped`` counts trades whose delta could not be
    priced (IV unsolved) or that were neutral (``side == N``).
    """

    final: HiroSnapshot
    cumulative: List[float]
    skipped: int

    def to_dict(self) -> dict[str, object]:
        return {
            "final": self.final.to_dict(),
            "cumulative": list(self.cumulative),
            "skipped": self.skipped,
        }


def signed_delta_notional(
    trade: HiroTrade,
    F: float,
    M: float,
    rate: float,
) -> Optional[float]:
    """Per-trade signed dealer delta-notional ``s · δ · q · M · F``.

    Returns ``None`` when the trade is neutral (``side == N``) or its IV cannot
    be solved from the trade price (so the caller can count it as skipped rather
    than silently zeroing it). ``trade.iv`` short-circuits the IV solve.
    """
    s = aggressor_sign(trade.side)
    if s == 0:
        return None
    otype: OptionType = "call" if trade.is_call else "put"
    iv = trade.iv
    if iv is None:
        iv = implied_vol(otype, trade.price, F, float(trade.strike), trade.t_expiry, rate)
    if iv is None or iv <= 0.0:
        return None
    d = bs_delta(otype, F, float(trade.strike), trade.t_expiry, rate, iv)
    return s * d * float(trade.size) * M * F


class HiroState:
    """Mutable accumulator for cumulative HIRO since the RTH open (reset daily).

    Feed trades in chronological order via :meth:`add`; read the running totals
    via :meth:`snapshot`. ``F`` (forward) and ``rate`` are taken per-trade so the
    notional uses the forward in force at each trade (mega-riset §B3 ``F_k``).
    """

    def __init__(self, M: float, *, retail_max_size: float = RETAIL_MAX_SIZE) -> None:
        self._M = float(M)
        self._retail_max = float(retail_max_size)
        self._total = 0.0
        self._calls = 0.0
        self._puts = 0.0
        self._zerodte = 0.0
        self._retail = 0.0
        self.skipped = 0

    def add(self, trade: HiroTrade, F: float, rate: float) -> Optional[float]:
        """Accumulate one trade; return its delta-notional increment (or None)."""
        dn = signed_delta_notional(trade, float(F), self._M, rate)
        if dn is None:
            self.skipped += 1
            return None
        self._total += dn
        if trade.is_call:
            self._calls += dn
        else:
            self._puts += dn
        if trade.t_expiry < ZERO_DTE_T:
            self._zerodte += dn
        if self._retail_max > 0.0 and float(trade.size) <= self._retail_max:
            self._retail += dn
        return dn

    def snapshot(self) -> HiroSnapshot:
        """Current cumulative HIRO with the full breakdown."""
        return HiroSnapshot(
            total=self._total,
            calls=self._calls,
            puts=self._puts,
            zerodte=self._zerodte,
            retail=self._retail,
        )


def hiro_series(
    trades: Sequence[HiroTrade],
    F: float,
    M: float,
    rate: float,
    *,
    retail_max_size: float = RETAIL_MAX_SIZE,
) -> HiroSeries:
    """Accumulate HIRO over a (chronological) trade sequence at a single ``F``.

    Convenience wrapper around :class:`HiroState` for offline/demo use where one
    forward is representative for the window (e.g. one RTH minute). For full
    fidelity (forward moving trade-to-trade) drive :class:`HiroState` directly,
    passing the per-trade forward to :meth:`HiroState.add`.
    """
    state = HiroState(M, retail_max_size=retail_max_size)
    cumulative: List[float] = []
    for tr in trades:
        state.add(tr, F, rate)
        cumulative.append(state.snapshot().total)
    return HiroSeries(final=state.snapshot(), cumulative=cumulative, skipped=state.skipped)
