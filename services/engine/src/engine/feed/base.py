"""Feed adapter interface + the shared per-minute chain contract (PRD #8 §8).

LOCKED CONTRACT (PRD #8 §8): the canonical per-minute option-chain payload is
:class:`OptionChainMinute` with fields ``ts``, ``forward`` and ``rows`` where
each row carries exactly ``strike, type, bid, ask, volume, oi``. BOTH feed
implementations (historical-sim and live) MUST emit this identical shape so the
engine, datastore and frontend never change when ``FEED_MODE`` flips
(historical ↔ live) — AC-A3.

This module is dependency-light (stdlib only). The engine bridge
:func:`to_engine_chain` performs a *local* import of
``engine.snapshot.ChainQuote`` so there is no import-time coupling between the
feed layer and the compute engine.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Literal, Optional

if TYPE_CHECKING:  # pragma: no cover - typing only
    from engine.snapshot import ChainQuote

__all__ = [
    "INSTRUMENTS",
    "OptionType",
    "ChainRow",
    "OptionChainMinute",
    "FeedAdapter",
    "ensure_utc_minute",
    "to_engine_chain",
]

# Instruments supported by FlowDesk (locked contract: /ES & /NQ only).
INSTRUMENTS: tuple[str, ...] = ("ES", "NQ")

# Option leg type, as stored in the locked ``rows[].type`` field.
OptionType = Literal["call", "put"]


def ensure_utc_minute(ts: datetime) -> datetime:
    """Return ``ts`` as a timezone-aware UTC datetime truncated to the minute.

    Naive datetimes are assumed to already be UTC. Seconds and microseconds are
    dropped so a chain is addressed by whole minutes (cadence = 1 min).
    """
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    ts = ts.astimezone(timezone.utc)
    return ts.replace(second=0, microsecond=0)


@dataclass(frozen=True)
class ChainRow:
    """One raw per-leg quote row (locked ``OptionChainMinute.rows`` element).

    Fields are exactly those mandated by PRD #8 §8:
    ``strike, type, bid, ask, volume, oi``.

    * ``volume`` is the cumulative traded contracts for this leg since the RTH
      open (drives every VOL-based metric downstream).
    * ``oi`` is the day's open interest for this leg (drives the STATIC walls).
    * ``bid`` / ``ask`` may be ``None`` when no top-of-book quote is available;
      :attr:`mid` is then ``None`` and the engine treats the strike as thin.
    """

    strike: float
    type: OptionType
    bid: Optional[float]
    ask: Optional[float]
    volume: float
    oi: float

    @property
    def mid(self) -> Optional[float]:
        """Mid price ``(bid + ask) / 2`` or ``None`` if either side is missing."""
        if self.bid is None or self.ask is None:
            return None
        if self.bid <= 0.0 or self.ask <= 0.0:
            return None
        if self.ask < self.bid:  # crossed book -> unusable
            return None
        return (self.bid + self.ask) / 2.0


@dataclass(frozen=True)
class OptionChainMinute:
    """The locked per-minute chain payload (PRD #8 §8).

    ``ts`` is a timezone-aware UTC, minute-aligned timestamp. ``forward`` is the
    underlying futures price F at ``ts``. ``rows`` is the (immutable) collection
    of per-leg :class:`ChainRow` entries.
    """

    ts: datetime
    forward: float
    rows: tuple[ChainRow, ...]

    def strikes(self) -> list[float]:
        """Sorted unique strikes present in this chain."""
        return sorted({r.strike for r in self.rows})

    def by_strike(self) -> dict[float, dict[str, ChainRow]]:
        """Group rows as ``{strike: {"call": row?, "put": row?}}``."""
        out: dict[float, dict[str, ChainRow]] = {}
        for r in self.rows:
            out.setdefault(r.strike, {})[r.type] = r
        return out


class FeedAdapter(ABC):
    """Abstract feed source: one interface, two implementations.

    Concrete adapters (historical-sim, live) implement :meth:`get_chain` and
    :meth:`get_forward`. Selecting the implementation is driven solely by the
    ``FEED_MODE`` env var (see :func:`engine.feed.make_adapter`); nothing else
    in the stack changes when the mode flips (AC-A3).
    """

    #: Human-readable mode label (e.g. "historical", "live").
    mode: str = "abstract"

    @abstractmethod
    def get_chain(self, instrument: str, ts: datetime) -> OptionChainMinute:
        """Return the assembled option chain for ``instrument`` at minute ``ts``."""
        raise NotImplementedError

    @abstractmethod
    def get_forward(self, instrument: str, ts: datetime) -> float:
        """Return the underlying futures price F for ``instrument`` at ``ts``."""
        raise NotImplementedError

    # -- shared validation helpers (used by both implementations) ----------
    @staticmethod
    def _check_instrument(instrument: str) -> str:
        key = instrument.upper()
        if key not in INSTRUMENTS:
            raise ValueError(
                f"unknown instrument {instrument!r}; expected one of {INSTRUMENTS}"
            )
        return key


def to_engine_chain(
    chain: OptionChainMinute,
    *,
    t_expiry: Optional[float] = None,
) -> list["ChainQuote"]:
    """Bridge a locked :class:`OptionChainMinute` to engine ``ChainQuote`` rows.

    Groups the per-leg rows by strike and maps call/put legs onto the engine's
    per-strike input. ``t_expiry`` (year-fraction to the 0DTE expiry) is stamped
    on every quote; when ``None`` the snapshot-level ``t_expiry`` passed to
    ``build_snapshot`` is used instead. The result is directly consumable by
    ``engine.snapshot.build_snapshot`` (engine 0.8 / PRD step 1.3).
    """
    from engine.snapshot import ChainQuote  # local import: no import-time cycle

    grouped = chain.by_strike()
    quotes: list[ChainQuote] = []
    for strike in sorted(grouped):
        legs = grouped[strike]
        call = legs.get("call")
        put = legs.get("put")
        quotes.append(
            ChainQuote(
                strike=strike,
                call_mid=call.mid if call else None,
                put_mid=put.mid if put else None,
                call_vol=call.volume if call else 0.0,
                put_vol=put.volume if put else 0.0,
                call_oi=call.oi if call else 0.0,
                put_oi=put.oi if put else 0.0,
                call_bid=call.bid if call else None,
                call_ask=call.ask if call else None,
                put_bid=put.bid if put else None,
                put_ask=put.ask if put else None,
                t_expiry=t_expiry,
            )
        )
    return quotes
