"""_LiveBook — pure per-minute chain assembler for the realtime Databento feed.

This is the compute core that the live :class:`engine.feed.live.LiveAdapter`
delegates to. It is deliberately split out from ``live.py`` and kept **pure +
network-free** so it can be unit-tested with synthetic records (no databento, no
socket) — the network/threading wrapper that actually pumps ``databento.Live``
records into it lives in ``live.py`` behind the two-key arming rail.

Why a separate book
===================
The historical adapter (:class:`engine.feed.historical.HistoricalSimAdapter`)
assembles the locked :class:`~engine.feed.base.OptionChainMinute` by reading four
pre-decoded CSV schemas off disk (definition / statistics / trades / quotes).
The live feed receives the SAME four record families as a realtime stream, so
this book mirrors that adapter's assembly semantics exactly — same 0DTE-expiry
selection, latest-quote-as-of-ts, cumulative-volume-since-RTH-open, latest-OI,
and futures-mid-then-put/call-parity forward — but accumulates the records in
memory as they arrive instead of binary-searching CSV columns. Output is the
byte-for-byte identical contract, so the engine/datastore/FE never change when
``FEED_MODE`` flips (AC-A3).

DBN wire-format decoding
========================
Raw ``databento.Live`` records carry fixed-point integers, not the pretty floats
the historical CSVs hold (those are written with ``price_type="float"`` by the
ingest script). The decode helpers here convert:

  * prices : int 1e-9 fixed-point  -> float index points (``UNDEF_PRICE`` -> None)
  * ts      : int epoch-nanoseconds -> aware UTC ``datetime``
  * class   : char ``'C'/'P'/'F'``  -> ``"call"/"put"/"future"`` (names also ok)
  * side    : char ``'B'/'A'/'N'``  -> aggressor side string (``'N'`` default)

They accept already-decoded values too (defensive), so the same book can be fed
either raw records or test primitives.

!! UNTESTED AGAINST A LIVE SOCKET !!
====================================
The *assembly* logic below is unit-tested with synthetic records. The actual
``databento.Live`` record field names / enum encodings are taken from the DBN
spec and the project's own ``convert_dbn_to_csv.py`` mapping, but have NOT been
exercised against a real stream in this environment (no network; the account is
locked; see docs/architecture/live-feed-threat-model.md). Treat the wire mapping
as provisional until an operator validates it through the runbook.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from typing import TYPE_CHECKING, Optional
from zoneinfo import ZoneInfo

from engine.feed.base import (
    ChainRow,
    OptionChainMinute,
    ensure_utc_minute,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from engine.flux import FluxTrade

__all__ = [
    "UNDEF_PRICE",
    "NY_TZ",
    "RTH_OPEN",
    "STAT_OPEN_INTEREST",
    "STAT_SETTLEMENT_PRICE",
    "decode_px",
    "decode_ts",
    "decode_class",
    "decode_side",
    "instrument_of",
    "LiveLegDef",
    "LiveBook",
]

NY_TZ = ZoneInfo("America/New_York")
RTH_OPEN = time(9, 30)  # 09:30 America/New_York (locked contract)

#: Databento INT64 "undefined" sentinel for an absent fixed-point price.
UNDEF_PRICE = 2**63 - 1
#: Fixed-point scale: DBN prices are integers in units of 1e-9.
_PX_SCALE = 1e-9
#: Databento "undefined" timestamp sentinels (int64 max, uint64 max). Real DBN
#: records use these when a field is absent (e.g. bbo-1m carries an UNDEF
#: ``ts_event`` and a valid ``ts_recv``). Decoding them as a real epoch yields a
#: garbage year-584942 datetime (and overflows on some platforms), so they are
#: rejected by ``decode_ts``.
_UNDEF_TS = frozenset({2**63 - 1, 2**64 - 1})

STAT_OPEN_INTEREST = 9
STAT_SETTLEMENT_PRICE = 3

_CLASS_CALL = {"C", "CALL"}
_CLASS_PUT = {"P", "PUT"}
_CLASS_FUTURE = {"F", "FUTURE"}

_YEAR_SECONDS = 365.0 * 24.0 * 3600.0
_T_FLOOR = 1.0 / _YEAR_SECONDS


# --------------------------------------------------------------------------- #
# Wire-format decoders (DBN -> engine primitives).                             #
# --------------------------------------------------------------------------- #
def decode_px(raw: object) -> Optional[float]:
    """Decode a DBN fixed-point price (int 1e-9) to float index points.

    Returns ``None`` for the ``UNDEF_PRICE`` sentinel, ``None``/empty, or a
    non-positive result. Already-float inputs pass through (scaled only when
    they look like raw fixed-point ints), so the book can be fed test floats.
    """
    if raw is None:
        return None
    if isinstance(raw, float):
        # Already a real price (e.g. test primitive or pretty CSV value).
        return raw if math.isfinite(raw) and raw > 0.0 else None
    if isinstance(raw, int):
        if raw == UNDEF_PRICE or raw == -UNDEF_PRICE:
            return None
        # Round to the fixed-point's own 1e-9 resolution: ``int * 1e-9`` carries
        # binary-float epsilon (e.g. 15000000000*1e-9 == 15.000000000000002),
        # which would make a strike differ from the pretty-CSV value the
        # historical adapter reads. round(.,9) is lossless for real DBN prices
        # and restores byte-for-byte parity with the historical path.
        val = round(raw * _PX_SCALE, 9)
        return val if val > 0.0 else None
    # Strings or anything else: best-effort parse.
    try:
        f = float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) and f > 0.0 else None


def decode_ts(raw: object) -> Optional[datetime]:
    """Decode a DBN timestamp (epoch-ns int, datetime, or ISO str) to aware UTC.

    Returns ``None`` for the Databento "undefined" sentinels (int64/uint64 max),
    non-positive values, or unparseable strings — verified against real DBN where
    e.g. ``bbo-1m`` carries an UNDEF ``ts_event`` and a valid ``ts_recv``. Callers
    skip a record whose resolved timestamp is ``None``.
    """
    if isinstance(raw, datetime):
        dt = raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    if isinstance(raw, (int, float)):
        n = int(raw)
        if n in _UNDEF_TS or n <= 0:
            return None
        try:
            return datetime.fromtimestamp(n / 1e9, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    s = str(raw).strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def decode_class(raw: object) -> Optional[str]:
    """Decode an instrument_class (enum / char / name) to ``"call"/"put"/"future"``.

    Real DBN exposes this as an ``InstrumentClass`` enum (``<InstrumentClass.PUT:
    'P'>``); ``.value`` gives the canonical char, so we prefer it over ``str()``.
    """
    val = getattr(raw, "value", raw)
    s = str(val).strip().upper()
    if s in _CLASS_CALL:
        return "call"
    if s in _CLASS_PUT:
        return "put"
    if s in _CLASS_FUTURE:
        return "future"
    return None


def decode_side(raw: object) -> str:
    """Decode an aggressor side (enum / char) to ``'B'`` / ``'A'`` / ``'N'``.

    Real DBN exposes this as a ``Side`` enum (``<Side.BID: 'B'>``); ``.value``
    gives the char. Defaults to ``'N'`` (no aggressor) for anything else.
    """
    val = getattr(raw, "value", raw)
    s = str(val).strip().upper()
    return s if s in ("B", "A", "N") else "N"


def instrument_of(asset: object, raw_symbol: object) -> Optional[str]:
    """Map a definition ``asset`` / ``raw_symbol`` to ``"ES"`` or ``"NQ"``.

    Mirrors ``scripts/convert_dbn_to_csv.py``: futures asset is literally ES/NQ;
    option roots start with ``E`` (-> ES) or ``Q`` (-> NQ). Falls back to the
    symbol root when the asset is ambiguous.
    """
    a = str(asset or "").strip().upper()
    if a == "ES":
        return "ES"
    if a == "NQ":
        return "NQ"
    if a.startswith("E"):
        return "ES"
    if a.startswith("Q"):
        return "NQ"
    root = str(raw_symbol or "").strip().upper().split(" ")[0]
    if root.startswith("ES"):
        return "ES"
    if root.startswith("NQ"):
        return "NQ"
    if root.startswith("E"):
        return "ES"
    if root.startswith("Q"):
        return "NQ"
    return None


# --------------------------------------------------------------------------- #
# Resolved leg definition.                                                     #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class LiveLegDef:
    """Resolved definition for one streamed Databento instrument_id."""

    instrument_id: int
    raw_symbol: str
    kind: str  # "call" | "put" | "future"
    strike: Optional[float]
    expiration: Optional[datetime]
    instrument: Optional[str]  # "ES" | "NQ" | None


# --------------------------------------------------------------------------- #
# The live book.                                                               #
# --------------------------------------------------------------------------- #
@dataclass
class LiveBook:
    """In-memory accumulator that assembles per-minute chains from a live stream.

    Thread-safety: the wrapper in ``live.py`` calls the ``add_*`` mutators from a
    single reader thread and the ``get_*`` readers from the worker thread. The
    mutators only append/replace dict entries (atomic at the CPython bytecode
    level for these simple operations); for stronger guarantees the wrapper holds
    a lock around the snapshot read. Kept lock-free here to stay pure/testable.
    """

    rate: float = 0.0
    _defs: dict[int, LiveLegDef] = field(default_factory=dict)
    # latest (ts, value) wins — the live stream is forward-only.
    _oi: dict[int, tuple[datetime, float]] = field(default_factory=dict)
    _settle: dict[int, tuple[datetime, float]] = field(default_factory=dict)
    # full per-leg quote history (sorted by arrival; stream is forward-only) so
    # get_chain can resolve the latest quote as-of any minute window — mbp-1 is
    # sub-minute, so a single "latest" slot would drop within-minute updates.
    _quotes: dict[int, list[tuple[datetime, Optional[float], Optional[float]]]] = field(
        default_factory=dict
    )
    # full per-leg trade history this session (for cumulative VOL + FLUX).
    _opt_trades: dict[int, list[tuple[datetime, float, float, str]]] = field(
        default_factory=dict
    )
    _fut_trades: dict[int, list[tuple[datetime, float]]] = field(default_factory=dict)

    # -- session lifecycle ------------------------------------------------- #
    def reset_session(self) -> None:
        """Clear per-session trade/quote/OI state at the RTH-open rollover.

        Definitions are kept (they span the whole expiry range and rarely
        change intraday); volumes/quotes/OI reset so cumulative VOL restarts.
        """
        self._oi.clear()
        self._settle.clear()
        self._quotes.clear()
        self._opt_trades.clear()
        self._fut_trades.clear()

    # -- mutators (fed by the stream reader; accept decoded primitives) ---- #
    def add_definition(
        self,
        instrument_id: int,
        *,
        raw_symbol: str,
        instrument_class: object,
        strike: object,
        expiration: object,
        asset: object = "",
    ) -> None:
        """Register/replace one instrument definition."""
        kind = decode_class(instrument_class)
        if kind is None:
            return
        strike_f = decode_px(strike) if kind in ("call", "put") else None
        exp = decode_ts(expiration) if expiration not in (None, "", 0) else None
        self._defs[int(instrument_id)] = LiveLegDef(
            instrument_id=int(instrument_id),
            raw_symbol=str(raw_symbol or ""),
            kind=kind,
            strike=strike_f,
            expiration=exp,
            instrument=instrument_of(asset, raw_symbol),
        )

    def add_statistic(
        self, instrument_id: int, *, ts: object, stat_type: object, price: object,
        quantity: object,
    ) -> None:
        """Ingest a statistics record (OPEN_INTEREST or SETTLEMENT_PRICE)."""
        iid = int(instrument_id)
        code = _stat_code(stat_type)
        event = decode_ts(ts)
        if event is None:
            return  # undecodable / sentinel timestamp -> cannot place in time
        if code == STAT_OPEN_INTEREST:
            qty = _to_float(quantity) or 0.0
            prev = self._oi.get(iid)
            if prev is None or event >= prev[0]:
                self._oi[iid] = (event, qty)
        elif code == STAT_SETTLEMENT_PRICE:
            px = decode_px(price)
            if px is not None:
                prev = self._settle.get(iid)
                if prev is None or event >= prev[0]:
                    self._settle[iid] = (event, px)

    def add_trade(
        self, instrument_id: int, *, ts: object, price: object, size: object,
        side: object = "N",
    ) -> None:
        """Ingest one trade print (routed to futures or option history by def)."""
        iid = int(instrument_id)
        d = self._defs.get(iid)
        if d is None:
            return  # cannot classify a trade with no definition yet
        event = decode_ts(ts)
        px = decode_px(price)
        sz = _to_float(size) or 0.0
        if px is None or event is None:
            return
        if d.kind == "future":
            self._fut_trades.setdefault(iid, []).append((event, px))
        elif d.kind in ("call", "put"):
            self._opt_trades.setdefault(iid, []).append(
                (event, px, sz, decode_side(side))
            )

    def add_quote(
        self, instrument_id: int, *, ts: object, bid: object, ask: object
    ) -> None:
        """Ingest a top-of-book quote (full history; latest as-of-ts wins on read).

        ``ts`` MUST be a usable timestamp; for ``bbo-1m`` the wrapper passes
        ``ts_recv`` because ``ts_event`` is the UNDEF sentinel. An undecodable ts
        is skipped (a quote that cannot be placed in time is useless).
        """
        iid = int(instrument_id)
        event = decode_ts(ts)
        if event is None:
            return
        self._quotes.setdefault(iid, []).append((event, decode_px(bid), decode_px(ask)))

    # -- readers (mirror HistoricalSimAdapter assembly) -------------------- #
    def get_chain(self, instrument: str, ts: datetime) -> OptionChainMinute:
        """Assemble the locked :class:`OptionChainMinute` for ``instrument``@``ts``."""
        instr = instrument.upper()
        ts = ensure_utc_minute(ts)
        expiry = self._select_0dte_expiry(instr, ts)
        rth_open = _rth_open_utc(ts)

        rows: list[ChainRow] = []
        for iid, d in self._defs.items():
            if d.instrument != instr or d.kind not in ("call", "put"):
                continue
            if d.strike is None:
                continue
            if expiry is not None and d.expiration is not None and d.expiration != expiry:
                continue
            bid, ask = self._latest_quote(iid, ts)
            rows.append(
                ChainRow(
                    strike=d.strike,
                    type=d.kind,  # type: ignore[arg-type]
                    bid=bid,
                    ask=ask,
                    volume=self._cumulative_volume(iid, rth_open, ts),
                    oi=self._open_interest(iid),
                )
            )
        rows.sort(key=lambda r: (r.strike, r.type))
        forward = self._forward(instr, ts, expiry)
        return OptionChainMinute(ts=ts, forward=forward, rows=tuple(rows))

    def get_forward(self, instrument: str, ts: datetime) -> float:
        instr = instrument.upper()
        ts = ensure_utc_minute(ts)
        return self._forward(instr, ts, self._select_0dte_expiry(instr, ts))

    def get_ohlc(
        self, instrument: str, ts: datetime
    ) -> Optional[tuple[float, float, float, float]]:
        """Front-future OHLC over the minute ``[ts, ts+60s)`` from trade prices.

        Returns ``(open, high, low, close)`` in index points, or ``None`` when no
        futures trade printed in that minute (caller leaves ``ohlc`` null — never
        fabricated). Mirrors :meth:`HistoricalSimAdapter.get_ohlc`: the future
        chosen is the front contract (same as :meth:`_forward`) so the candle
        close aligns with the snapshot forward.
        """
        instr = instrument.upper()
        ts = ensure_utc_minute(ts)
        end = ts + timedelta(minutes=1)
        for fut in self._front_future(instr, ts):
            series = self._fut_trades.get(fut.instrument_id)
            if not series:
                continue
            window = [px for (event, px) in series if ts <= event < end]
            if window:
                return (window[0], max(window), min(window), window[-1])
        return None

    def get_flux_trades(self, instrument: str, ts: datetime) -> list["FluxTrade"]:
        """Signed option trades over ``[RTH open, ts]`` for FLUX (chronological)."""
        from engine.flux import FluxTrade

        instr = instrument.upper()
        ts = ensure_utc_minute(ts)
        rth_open = _rth_open_utc(ts)
        end = ts + timedelta(minutes=1)
        out: list[tuple[datetime, FluxTrade]] = []
        for iid, series in self._opt_trades.items():
            d = self._defs.get(iid)
            if d is None or d.instrument != instr or d.kind not in ("call", "put"):
                continue
            if d.strike is None:
                continue
            is_call = d.kind == "call"
            for event, price, size, side in series:
                if event < rth_open or event >= end:
                    continue
                out.append(
                    (
                        event,
                        FluxTrade(
                            strike=float(d.strike),
                            is_call=is_call,
                            price=float(price),
                            size=float(size),
                            side=side,
                            t_expiry=_year_fraction(d.expiration, event),
                            ts=event,
                        ),
                    )
                )
        out.sort(key=lambda r: r[0])
        return [tr for _, tr in out]

    # -- internals --------------------------------------------------------- #
    def _select_0dte_expiry(self, instr: str, ts: datetime) -> Optional[datetime]:
        session_date = ts.astimezone(NY_TZ).date()
        opt_defs = [
            d
            for d in self._defs.values()
            if d.instrument == instr and d.kind in ("call", "put") and d.expiration
        ]
        expiries = sorted({d.expiration for d in opt_defs if d.expiration})
        if not expiries:
            return None
        same_day = [e for e in expiries if e.astimezone(NY_TZ).date() == session_date]
        if same_day:
            if len(same_day) > 1:
                # Disambiguate same-day expiries (weekly vs AM-settled vs
                # quarterly contaminant): pick the one with the most QUOTED legs
                # — a contaminant carries a definition but no market data. Ties
                # break on latest expiry (RTH close beats AM settle).
                def _coverage(exp: datetime) -> tuple[int, datetime]:
                    n = sum(
                        1
                        for d in opt_defs
                        if d.expiration == exp and d.instrument_id in self._quotes
                    )
                    return (n, exp)

                return max(same_day, key=_coverage)
            return same_day[0]
        future = [e for e in expiries if e.astimezone(NY_TZ).date() >= session_date]
        return future[0] if future else expiries[-1]

    def _latest_quote(
        self, iid: int, ts: datetime
    ) -> tuple[Optional[float], Optional[float]]:
        series = self._quotes.get(iid)
        if not series:
            return (None, None)
        # Latest quote with event <= ts (mirror HistoricalSimAdapter). The stream
        # is forward-only so the list is time-ordered; scan from the end.
        best: Optional[tuple[datetime, Optional[float], Optional[float]]] = None
        for entry in series:
            if entry[0] <= ts and (best is None or entry[0] >= best[0]):
                best = entry
        if best is None:
            return (None, None)
        return (best[1], best[2])

    def _cumulative_volume(self, iid: int, rth_open: datetime, ts: datetime) -> float:
        series = self._opt_trades.get(iid)
        if not series:
            return 0.0
        # Trades in [rth_open, ts] (matches HistoricalSimAdapter's volume window).
        return sum(sz for (event, _px, sz, _side) in series if rth_open <= event <= ts)

    def _open_interest(self, iid: int) -> float:
        entry = self._oi.get(iid)
        return entry[1] if entry is not None else 0.0

    def _front_future(self, instr: str, ts: datetime) -> list[LiveLegDef]:
        futures = [
            d for d in self._defs.values() if d.instrument == instr and d.kind == "future"
        ]
        dated = sorted(
            (d for d in futures if d.expiration is not None),
            key=lambda d: d.expiration,  # type: ignore[arg-type,return-value]
        )
        return [d for d in dated if d.expiration and d.expiration >= ts] or dated or futures

    def _forward(self, instr: str, ts: datetime, expiry: Optional[datetime]) -> float:
        # 1) Front-future top-of-book mid (preferred).
        for fut in self._front_future(instr, ts):
            bid, ask = self._latest_quote(fut.instrument_id, ts)
            if bid is not None and ask is not None and ask >= bid > 0:
                return (bid + ask) / 2.0
        # 2) Front-future last trade price <= ts.
        for fut in self._front_future(instr, ts):
            series = self._fut_trades.get(fut.instrument_id)
            if series:
                px = None
                for event, p in series:
                    if event <= ts:
                        px = p
                if px is not None:
                    return px
        # 3) Last futures settlement <= ts.
        for fut in self._front_future(instr, ts):
            s = self._settle.get(fut.instrument_id)
            if s is not None and s[0] <= ts:
                return s[1]
        # 4) Put-call parity from the option chain (options-only fallback).
        fwd = self._forward_from_parity(instr, ts, expiry)
        if fwd is not None:
            return fwd
        raise ValueError(
            f"could not determine forward for {instr} @ {ts.isoformat()}: "
            "no futures quote/trade/settlement and no put-call pair"
        )

    def _forward_from_parity(
        self, instr: str, ts: datetime, expiry: Optional[datetime]
    ) -> Optional[float]:
        disc = 1.0
        if expiry is not None:
            disc = math.exp(self.rate * _year_fraction(expiry, ts))
        calls: dict[float, float] = {}
        puts: dict[float, float] = {}
        for iid, d in self._defs.items():
            if d.instrument != instr or d.kind not in ("call", "put") or d.strike is None:
                continue
            if expiry is not None and d.expiration is not None and d.expiration != expiry:
                continue
            bid, ask = self._latest_quote(iid, ts)
            if bid is None or ask is None or not (ask >= bid > 0):
                continue
            mid = (bid + ask) / 2.0
            (calls if d.kind == "call" else puts)[float(d.strike)] = mid
        best_strike: Optional[float] = None
        best_spread = float("inf")
        for strike, c_mid in calls.items():
            p_mid = puts.get(strike)
            if p_mid is None:
                continue
            spread = abs(c_mid - p_mid)
            if spread < best_spread:
                best_spread = spread
                best_strike = strike
        if best_strike is None:
            return None
        return best_strike + disc * (calls[best_strike] - puts[best_strike])


# --------------------------------------------------------------------------- #
# Module-level pure helpers.                                                    #
# --------------------------------------------------------------------------- #
def _rth_open_utc(ts: datetime) -> datetime:
    session_date = ts.astimezone(NY_TZ).date()
    return datetime.combine(session_date, RTH_OPEN, tzinfo=NY_TZ).astimezone(timezone.utc)


def _year_fraction(expiration: Optional[datetime], at: datetime) -> float:
    """Year-fraction from ``at`` to ``expiration`` (365-day; floored > 0)."""
    if expiration is None:
        return _T_FLOOR
    frac = (expiration - at).total_seconds() / _YEAR_SECONDS
    return frac if frac > _T_FLOOR else _T_FLOOR


def _stat_code(raw: object) -> Optional[int]:
    # Real DBN exposes stat_type as a StatType enum (``<StatType.OPEN_INTEREST:
    # 9>``); ``.value`` is the canonical int code, so prefer it over ``str()``
    # (whose repr is ``'<StatType...: 9>'`` and would fail an isdigit() check).
    val = getattr(raw, "value", raw)
    if isinstance(val, int) and not isinstance(val, bool):
        return val
    s = str(val).strip().upper()
    if s.isdigit():
        return int(s)
    return {
        "OPEN_INTEREST": STAT_OPEN_INTEREST,
        "SETTLEMENT_PRICE": STAT_SETTLEMENT_PRICE,
    }.get(s)


def _to_float(raw: object) -> Optional[float]:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        f = float(raw)
        return f if math.isfinite(f) else None
    s = str(raw).strip()
    if s == "" or s.lower() in {"nan", "null", "none"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None
