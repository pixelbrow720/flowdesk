"""FLUX — Hedging Impact of Real-time Options (FlowGreeks flow module).

Cumulative dealer **delta-notional** hedging flow, accumulated per trade since
the RTH open (reset daily). Where TRACE/GEX is *stock* (positioning), FLUX is
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
-> the dealer SELLS the underlying. So positive cumulative FLUX == net dealer
buying pressure (bullish), negative == selling pressure (bearish).

Breakdown (mega-riset §B8): Total, Calls, Puts, 0DTE (``T < 1/365``) and Retail.
**Retail is a heuristic proxy** (small odd-lot size) — the real SpotGamma
customer/dealer + retail classifier is proprietary; see :data:`RETAIL_MAX_SIZE`
and treat the retail line as indicative only (TODO: refine with block/multi-leg
filters).

This module is PURE and **isolated**: it does NOT touch the Snapshot contract
(``schema_version`` 2) — output lives in :class:`FluxSnapshot` / :class:`FluxSeries`
until a schema decision is taken (Divergence #5). The delta is priced with the
sibling :mod:`engine.black76` / :mod:`engine.iv` (IV solved from the trade price
unless an explicit per-trade IV is supplied), so FLUX reuses the exact same
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
    "FluxTrade",
    "FluxSnapshot",
    "FluxSeries",
    "signed_delta_notional",
    "FluxState",
    "flux_series",
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
class FluxTrade:
    """One option trade off the tape (engine input for FLUX).

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
    (synthetic-OI #5). FLUX itself does not use it."""


@dataclass(frozen=True)
class FluxSnapshot:
    """Cumulative FLUX at one instant (USD delta-notional), with breakdown."""

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
class FluxSeries:
    """A FLUX run: the final cumulative state plus the per-trade cumulative path.

    ``cumulative`` is the running ``total`` after each accepted trade (the line
    drawn on the chart); ``skipped`` counts trades whose delta could not be
    priced (IV unsolved) or that were neutral (``side == N``).
    """

    final: FluxSnapshot
    cumulative: List[float]
    skipped: int

    def to_dict(self) -> dict[str, object]:
        return {
            "final": self.final.to_dict(),
            "cumulative": list(self.cumulative),
            "skipped": self.skipped,
        }


def signed_delta_notional(
    trade: FluxTrade,
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


class FluxState:
    """Mutable accumulator for cumulative FLUX since the RTH open (reset daily).

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

    def add(self, trade: FluxTrade, F: float, rate: float) -> Optional[float]:
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

    def snapshot(self) -> FluxSnapshot:
        """Current cumulative FLUX with the full breakdown."""
        return FluxSnapshot(
            total=self._total,
            calls=self._calls,
            puts=self._puts,
            zerodte=self._zerodte,
            retail=self._retail,
        )

    def to_dict(self) -> dict[str, float]:
        """Serialise the accumulator state for durable storage (Redis snapshot).

        Captures everything needed to resume accumulation across a worker restart:
        the five running totals, the skipped count, and the construction params
        (``M``, ``retail_max``). The output is plain JSON-friendly scalars; pair
        with :meth:`from_dict` to round-trip. NOT part of the locked snapshot
        contract — internal worker state only.
        """
        return {
            "M": self._M,
            "retail_max": self._retail_max,
            "total": self._total,
            "calls": self._calls,
            "puts": self._puts,
            "zerodte": self._zerodte,
            "retail": self._retail,
            "skipped": float(self.skipped),
        }

    @classmethod
    def from_dict(cls, data: dict[str, float]) -> "FluxState":
        """Reseed an accumulator from a :meth:`to_dict` payload.

        Used by the api-layer worker to restore FLUX state after a pod restart
        within the same RTH session (see ``docs/architecture/flux-unification.md``
        §4.4 Tier 1). Missing/bad fields default to ``0.0`` / sentinel — callers
        that detect a malformed payload should fall back to a fresh ``FluxState``.
        """
        state = cls(
            M=float(data.get("M", 0.0)),
            retail_max_size=float(data.get("retail_max", RETAIL_MAX_SIZE)),
        )
        state._total = float(data.get("total", 0.0))
        state._calls = float(data.get("calls", 0.0))
        state._puts = float(data.get("puts", 0.0))
        state._zerodte = float(data.get("zerodte", 0.0))
        state._retail = float(data.get("retail", 0.0))
        state.skipped = int(data.get("skipped", 0))
        return state


def flux_series(
    trades: Sequence[FluxTrade],
    F: float,
    M: float,
    rate: float,
    *,
    retail_max_size: float = RETAIL_MAX_SIZE,
) -> FluxSeries:
    """Accumulate FLUX over a (chronological) trade sequence at a single ``F``.

    Convenience wrapper around :class:`FluxState` for offline/demo use where one
    forward is representative for the window (e.g. one RTH minute). For full
    fidelity (forward moving trade-to-trade) drive :class:`FluxState` directly,
    passing the per-trade forward to :meth:`FluxState.add`.
    """
    state = FluxState(M, retail_max_size=retail_max_size)
    cumulative: List[float] = []
    for tr in trades:
        state.add(tr, F, rate)
        cumulative.append(state.snapshot().total)
    return FluxSeries(final=state.snapshot(), cumulative=cumulative, skipped=state.skipped)
