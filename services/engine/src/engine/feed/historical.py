"""HistoricalSimAdapter — builds per-minute chains from cached Databento exports.

Reads PRE-DOWNLOADED Databento GLBX.MDP3 data from ``DATA_DIR`` and assembles
the locked :class:`~engine.feed.base.OptionChainMinute` for a requested minute,
by combining four schemas:

    definition  -> instrument_id -> (strike, type, expiration); identifies the
                   future used for the forward.
    statistics  -> open interest (OI) per leg                 -> ``rows[].oi``
    trades      -> cumulative traded size since the RTH open  -> ``rows[].volume``
    mbp-1/bbo   -> top-of-book bid/ask (mid)                  -> ``rows[].bid/ask``

This adapter performs NO network calls; it only reads local files produced by
``scripts/ingest_databento.py``.

========================= EXPECTED ON-DISK LAYOUT =========================

    DATA_DIR/
      definition/<INSTR>_<START>_<END>.csv
      statistics/<INSTR>_<START>_<END>.csv
      trades/<INSTR>_<START>_<END>.csv
      mbp-1/<INSTR>_<START>_<END>.csv        # or set quote_schema="bbo-1m"

  * ``<INSTR>``   = ES | NQ
  * ``<START>``/``<END>`` = YYYYMMDD (inclusive UTC date range of the cache file)
  * Files are the DECODED Databento exports written by the ingest script via
    ``DBNStore.to_csv(pretty_px=True, pretty_ts=True)``: prices are in real
    units (e.g. 5000.0, 12.25) and timestamps are ISO-8601 UTC. The raw
    ``.dbn.zst`` archives may live beside the CSVs but are NOT required here.

  Columns consumed per schema (any extra Databento columns are ignored):
    definition : instrument_id, raw_symbol, instrument_class, strike_price,
                 expiration, underlying
    statistics : ts_event, instrument_id, stat_type, price, quantity
    trades     : ts_event, instrument_id, price, size
    mbp-1/bbo  : ts_event, instrument_id, bid_px_00, ask_px_00

Databento enum encodings handled (both numeric codes and names are accepted):
  * instrument_class: 'C' = call, 'P' = put, 'F' = future
  * statistics.stat_type: 9 = OPEN_INTEREST, 3 = SETTLEMENT_PRICE
===========================================================================
"""
from __future__ import annotations

import bisect
import csv
import re
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Optional
from zoneinfo import ZoneInfo

from engine.feed.base import (
    ChainRow,
    FeedAdapter,
    OptionChainMinute,
    ensure_utc_minute,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from engine.hiro import HiroTrade

__all__ = [
    "NY_TZ",
    "RTH_OPEN",
    "STAT_OPEN_INTEREST",
    "STAT_SETTLEMENT_PRICE",
    "InstrumentDef",
    "HistoricalSimAdapter",
]

NY_TZ = ZoneInfo("America/New_York")
RTH_OPEN = time(9, 30)  # 09:30 America/New_York (locked contract)

STAT_OPEN_INTEREST = 9
STAT_SETTLEMENT_PRICE = 3

_DATE_LEN = 8  # YYYYMMDD
_CLASS_CALL = {"C", "CALL"}
_CLASS_PUT = {"P", "PUT"}
_CLASS_FUTURE = {"F", "FUTURE"}

_TS_FRAC = re.compile(r"\.(\d+)")


def _parse_ts(raw: str) -> datetime:
    """Parse a Databento ISO-8601 timestamp (handles nanosecond precision)."""
    s = raw.strip()
    if not s:
        raise ValueError("empty timestamp")
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    # Python's fromisoformat accepts at most microseconds; trim ns -> us.
    m = _TS_FRAC.search(s)
    if m and len(m.group(1)) > 6:
        frac = m.group(1)[:6]
        s = s[: m.start() + 1] + frac + s[m.start() + 1 + len(m.group(1)) :]
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _to_float(raw: Optional[str]) -> Optional[float]:
    if raw is None:
        return None
    s = raw.strip()
    if s == "" or s.lower() in {"nan", "null", "none"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _stat_type_code(raw: str) -> Optional[int]:
    s = raw.strip().upper()
    if s.isdigit():
        return int(s)
    return {
        "OPEN_INTEREST": STAT_OPEN_INTEREST,
        "SETTLEMENT_PRICE": STAT_SETTLEMENT_PRICE,
    }.get(s)


@dataclass(frozen=True)
class InstrumentDef:
    """Resolved definition for one Databento instrument_id."""

    instrument_id: int
    raw_symbol: str
    kind: str  # "call" | "put" | "future"
    strike: Optional[float]
    expiration: Optional[datetime]


class HistoricalSimAdapter(FeedAdapter):
    """Read cached Databento files and emit per-minute chains for /ES & /NQ."""

    mode = "historical"

    def __init__(
        self,
        data_dir: str | Path,
        *,
        quote_schema: str = "mbp-1",
    ) -> None:
        self.data_dir = Path(data_dir)
        self.quote_schema = quote_schema
        # Memoised per (instrument, session_date) parsed payloads.
        self._cache: dict[tuple[str, str], dict[str, object]] = {}

    # ------------------------------------------------------------------ API
    def get_chain(self, instrument: str, ts: datetime) -> OptionChainMinute:
        instr = self._check_instrument(instrument)
        ts = ensure_utc_minute(ts)
        data = self._load(instr, ts)
        defs: dict[int, InstrumentDef] = data["defs"]  # type: ignore[assignment]

        expiry = self._select_0dte_expiry(defs, ts)
        rth_open = self._rth_open_utc(ts)

        rows: list[ChainRow] = []
        for iid, d in defs.items():
            if d.kind not in ("call", "put") or d.strike is None:
                continue
            if expiry is not None and d.expiration is not None and d.expiration != expiry:
                continue
            bid, ask = self._latest_quote(data, iid, ts)
            rows.append(
                ChainRow(
                    strike=d.strike,
                    type=d.kind,  # type: ignore[arg-type]
                    bid=bid,
                    ask=ask,
                    volume=self._cumulative_volume(data, iid, rth_open, ts),
                    oi=self._open_interest(data, iid, ts),
                )
            )
        rows.sort(key=lambda r: (r.strike, r.type))
        forward = self._forward_from(data, ts)
        return OptionChainMinute(ts=ts, forward=forward, rows=tuple(rows))

    def get_forward(self, instrument: str, ts: datetime) -> float:
        instr = self._check_instrument(instrument)
        ts = ensure_utc_minute(ts)
        return self._forward_from(self._load(instr, ts), ts)

    def get_expiry(self, instrument: str, ts: datetime) -> Optional[datetime]:
        """Return the selected 0DTE expiry datetime for the session (convenience).

        The orchestrator turns this into the snapshot-level ``t_expiry``
        year-fraction; see :func:`engine.feed.base.to_engine_chain`.
        """
        instr = self._check_instrument(instrument)
        ts = ensure_utc_minute(ts)
        return self._select_0dte_expiry(self._load(instr, ts)["defs"], ts)  # type: ignore[arg-type]

    def get_ohlc(
        self, instrument: str, ts: datetime
    ) -> Optional[tuple[float, float, float, float]]:
        """Front-future OHLC over the minute ``[ts, ts+60s)`` from trade prices.

        Returns ``(open, high, low, close)`` in index points, or ``None`` when no
        futures trade printed in that minute (caller leaves ``ohlc`` null — never
        fabricated). The future chosen matches :meth:`_forward_from` (front
        contract) so the candle close aligns with the snapshot forward.
        """
        instr = self._check_instrument(instrument)
        ts = ensure_utc_minute(ts)
        data = self._load(instr, ts)
        fut_prices: dict[int, list[tuple[datetime, float]]] = data["fut_prices"]  # type: ignore[assignment]
        fid = self._front_future_iid(data, ts)
        if fid is None:
            return None
        series = fut_prices.get(fid)
        if not series:
            return None
        end = ts + timedelta(minutes=1)
        lo = bisect.bisect_left(series, ts, key=lambda r: r[0])
        hi = bisect.bisect_left(series, end, key=lambda r: r[0])
        window = series[lo:hi]
        if not window:
            return None
        prices = [px for _, px in window]
        return (prices[0], max(prices), min(prices), prices[-1])

    def get_hiro_trades(
        self, instrument: str, ts: datetime
    ) -> list["HiroTrade"]:
        """Signed option trades for HIRO over the RTH window ``[open, ts]``.

        Joins each tape trade's ``(price, size, side)`` with its leg's strike /
        type / expiry from the definition cache and the year-fraction to that
        leg's expiry at the trade time (365-day convention, matching the engine).
        Chronologically ordered, ready to feed :class:`engine.hiro.HiroState` /
        :func:`engine.hiro.hiro_series`. Trades before the RTH open are excluded
        (HIRO resets daily). Local import keeps the feed layer import-light.
        """
        from engine.hiro import HiroTrade  # local import: no import-time coupling

        instr = self._check_instrument(instrument)
        ts = ensure_utc_minute(ts)
        data = self._load(instr, ts)
        defs: dict[int, InstrumentDef] = data["defs"]  # type: ignore[assignment]
        opt_trades: dict[int, list[tuple[datetime, float, float, str]]]
        opt_trades = data["opt_trades"]  # type: ignore[assignment]
        rth_open = self._rth_open_utc(ts)
        end = ts + timedelta(minutes=1)  # include trades within the current minute

        out: list[tuple[datetime, HiroTrade]] = []
        for iid, series in opt_trades.items():
            d = defs.get(iid)
            if d is None or d.kind not in ("call", "put") or d.strike is None:
                continue
            is_call = d.kind == "call"
            for event, price, size, side in series:
                if event < rth_open or event >= end:
                    continue
                t_expiry = self._year_fraction(d.expiration, event)
                out.append(
                    (
                        event,
                        HiroTrade(
                            strike=float(d.strike),
                            is_call=is_call,
                            price=float(price),
                            size=float(size),
                            side=side,
                            t_expiry=t_expiry,
                        ),
                    )
                )
        out.sort(key=lambda r: r[0])
        return [tr for _, tr in out]

    @staticmethod
    def _year_fraction(expiration: Optional[datetime], at: datetime) -> float:
        """Year-fraction from ``at`` to ``expiration`` (365-day; floored > 0)."""
        floor = 1.0 / (365.0 * 24.0 * 3600.0)
        if expiration is None:
            return floor
        seconds = (expiration - at).total_seconds()
        frac = seconds / (365.0 * 24.0 * 3600.0)
        return frac if frac > floor else floor

    def _front_future_iid(
        self, data: dict[str, object], ts: datetime
    ) -> Optional[int]:
        """instrument_id of the front future (nearest expiry >= ts; else earliest)."""
        defs: dict[int, InstrumentDef] = data["defs"]  # type: ignore[assignment]
        futures = [d for d in defs.values() if d.kind == "future"]
        if not futures:
            return None
        dated = sorted(
            (d for d in futures if d.expiration is not None),
            key=lambda d: d.expiration,  # type: ignore[arg-type,return-value]
        )
        ordered = [d for d in dated if d.expiration and d.expiration >= ts] or dated or futures
        return ordered[0].instrument_id

    # ------------------------------------------------------------- internals
    def _rth_open_utc(self, ts: datetime) -> datetime:
        session_date = ts.astimezone(NY_TZ).date()
        local_open = datetime.combine(session_date, RTH_OPEN, tzinfo=NY_TZ)
        return local_open.astimezone(timezone.utc)

    def _select_0dte_expiry(
        self, defs: dict[int, InstrumentDef], ts: datetime
    ) -> Optional[datetime]:
        session_date = ts.astimezone(NY_TZ).date()
        expiries = sorted(
            {
                d.expiration
                for d in defs.values()
                if d.kind in ("call", "put") and d.expiration
            }
        )
        if not expiries:
            return None
        same_day = [e for e in expiries if e.astimezone(NY_TZ).date() == session_date]
        if same_day:
            return same_day[0]
        future = [e for e in expiries if e.astimezone(NY_TZ).date() >= session_date]
        return future[0] if future else expiries[-1]

    def _latest_quote(
        self, data: dict[str, object], iid: int, ts: datetime
    ) -> tuple[Optional[float], Optional[float]]:
        quotes: dict[int, list[tuple[datetime, Optional[float], Optional[float]]]]
        quotes = data["quotes"]  # type: ignore[assignment]
        series = quotes.get(iid)
        if not series:
            return (None, None)
        # series is time-sorted: last entry with q_ts <= ts (binary search).
        idx = bisect.bisect_right(series, ts, key=lambda r: r[0]) - 1
        if idx < 0:
            return (None, None)
        return (series[idx][1], series[idx][2])

    def _cumulative_volume(
        self, data: dict[str, object], iid: int, rth_open: datetime, ts: datetime
    ) -> float:
        trades: dict[int, tuple[list[datetime], list[float]]] = data["trades"]  # type: ignore[assignment]
        entry = trades.get(iid)
        if not entry:
            return 0.0
        # (time-sorted timestamps, prefix sums). Range sum over [rth_open, ts]
        # in O(log n) via two bisects: prefix[hi] - prefix[lo].
        ts_list, prefix = entry
        lo = bisect.bisect_left(ts_list, rth_open)
        hi = bisect.bisect_right(ts_list, ts)
        return prefix[hi] - prefix[lo]

    def _open_interest(self, data: dict[str, object], iid: int, ts: datetime) -> float:
        oi_series: dict[int, list[tuple[datetime, float]]] = data["oi"]  # type: ignore[assignment]
        series = oi_series.get(iid)
        if not series:
            return 0.0
        # Last OI value with s_ts <= ts (binary search on the time-sorted series).
        idx = bisect.bisect_right(series, ts, key=lambda r: r[0]) - 1
        if idx >= 0:
            return series[idx][1]
        # No OI on/before ts: OI is a prior-session settle; fall back to first.
        return series[0][1]

    def _forward_from(self, data: dict[str, object], ts: datetime) -> float:
        defs: dict[int, InstrumentDef] = data["defs"]  # type: ignore[assignment]
        futures = [d for d in defs.values() if d.kind == "future"]
        if not futures:
            raise ValueError("no future instrument found in definition cache")
        # Front future = nearest expiration on/after ts (fallback: earliest).
        dated = sorted(
            (d for d in futures if d.expiration is not None),
            key=lambda d: d.expiration,  # type: ignore[arg-type,return-value]
        )
        ordered = [d for d in dated if d.expiration and d.expiration >= ts] or dated or futures
        for fut in ordered:
            bid, ask = self._latest_quote(data, fut.instrument_id, ts)
            if bid is not None and ask is not None and ask >= bid > 0:
                return (bid + ask) / 2.0
        # Fallback: latest settlement price <= ts.
        settle: dict[int, list[tuple[datetime, float]]] = data["settle"]  # type: ignore[assignment]
        for fut in ordered:
            series = settle.get(fut.instrument_id)
            if series:
                val = None
                for s_ts, px in series:
                    if s_ts <= ts:
                        val = px
                if val is not None:
                    return val
        raise ValueError("could not determine forward: no future quote or settlement")

    # ----------------------------------------------------------- file loading
    def _load(self, instrument: str, ts: datetime) -> dict[str, object]:
        session_date = ts.astimezone(NY_TZ).date().isoformat()
        key = (instrument, session_date)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        defs = self._load_definitions(instrument, ts)
        oi, settle = self._load_statistics(instrument, ts)
        futures_iids = frozenset(
            iid for iid, d in defs.items() if d.kind == "future"
        )
        option_iids = frozenset(
            iid for iid, d in defs.items() if d.kind in ("call", "put")
        )
        trades, fut_prices, opt_trades = self._load_trades(
            instrument, ts, futures_iids, option_iids
        )
        quotes = self._load_quotes(instrument, ts)
        payload: dict[str, object] = {
            "defs": defs,
            "oi": oi,
            "settle": settle,
            "trades": trades,
            "fut_prices": fut_prices,
            "opt_trades": opt_trades,
            "quotes": quotes,
        }
        self._cache[key] = payload
        return payload

    def _resolve_file(self, schema: str, instrument: str, ts: datetime) -> Path:
        day = ts.astimezone(NY_TZ).date()
        schema_dir = self.data_dir / schema
        if not schema_dir.is_dir():
            raise FileNotFoundError(f"missing schema directory: {schema_dir}")
        candidates: list[Path] = []
        for path in sorted(schema_dir.glob(f"{instrument}_*.csv")):
            # filename layout: <INSTR>_<START>_<END>.csv  (START/END = YYYYMMDD)
            parts = path.stem.split("_")
            if len(parts) != 3 or parts[0] != instrument:
                continue
            start_s, end_s = parts[1], parts[2]
            if not (
                len(start_s) == _DATE_LEN
                and start_s.isdigit()
                and len(end_s) == _DATE_LEN
                and end_s.isdigit()
            ):
                continue
            start = datetime.strptime(start_s, "%Y%m%d").date()
            end = datetime.strptime(end_s, "%Y%m%d").date()
            if start <= day <= end:
                candidates.append(path)
        if not candidates:
            raise FileNotFoundError(
                f"no {schema} cache for {instrument} covering {day.isoformat()} "
                f"under {schema_dir}"
            )
        return candidates[0]

    def _read_csv(self, schema: str, instrument: str, ts: datetime) -> list[dict[str, str]]:
        path = self._resolve_file(schema, instrument, ts)
        with path.open(newline="") as fh:
            return list(csv.DictReader(fh))

    def _load_definitions(self, instrument: str, ts: datetime) -> dict[int, InstrumentDef]:
        defs: dict[int, InstrumentDef] = {}
        for row in self._read_csv("definition", instrument, ts):
            iid = int(row["instrument_id"])
            klass = row.get("instrument_class", "").strip().upper()
            if klass in _CLASS_CALL:
                kind = "call"
            elif klass in _CLASS_PUT:
                kind = "put"
            elif klass in _CLASS_FUTURE:
                kind = "future"
            else:
                continue
            exp_raw = row.get("expiration", "").strip()
            expiration = _parse_ts(exp_raw) if exp_raw else None
            defs[iid] = InstrumentDef(
                instrument_id=iid,
                raw_symbol=row.get("raw_symbol", "").strip(),
                kind=kind,
                strike=_to_float(row.get("strike_price")),
                expiration=expiration,
            )
        return defs

    def _load_statistics(
        self, instrument: str, ts: datetime
    ) -> tuple[dict[int, list[tuple[datetime, float]]], dict[int, list[tuple[datetime, float]]]]:
        oi: dict[int, list[tuple[datetime, float]]] = {}
        settle: dict[int, list[tuple[datetime, float]]] = {}
        for row in self._read_csv("statistics", instrument, ts):
            if not (row.get("ts_event") or "").strip():
                continue  # malformed row (empty timestamp) -> skip
            code = _stat_type_code(row.get("stat_type", ""))
            iid = int(row["instrument_id"])
            event = _parse_ts(row["ts_event"])
            if code == STAT_OPEN_INTEREST:
                qty = _to_float(row.get("quantity")) or 0.0
                oi.setdefault(iid, []).append((event, qty))
            elif code == STAT_SETTLEMENT_PRICE:
                px = _to_float(row.get("price"))
                if px is not None:
                    settle.setdefault(iid, []).append((event, px))
        for series in (*oi.values(), *settle.values()):
            series.sort(key=lambda x: x[0])
        return oi, settle

    def _load_trades(
        self,
        instrument: str,
        ts: datetime,
        futures_iids: frozenset[int],
        option_iids: frozenset[int] = frozenset(),
    ) -> tuple[
        dict[int, tuple[list[datetime], list[float]]],
        dict[int, list[tuple[datetime, float]]],
        dict[int, list[tuple[datetime, float, float, str]]],
    ]:
        """Per-leg trade volume (sorted ts, prefix sums) + futures trade prices
        + per-option SIGNED trades for HIRO.

        ``prefix[k]`` = sum of the first ``k`` trade sizes, so a range sum over
        [lo, hi) is ``prefix[hi] - prefix[lo]`` in O(1) after two bisects. In the
        SAME CSV pass we also collect ``(ts, price)`` for futures instrument_ids
        (``futures_iids``) so the OHLC candle view can be built without re-reading
        the (large) trades file, and ``(ts, price, size, side)`` for option
        instrument_ids (``option_iids``) so HIRO can consume the aggressor
        ``side`` per trade. The TRACE volume prefix-sums are UNCHANGED — the
        signed path is additive and isolated.
        """
        raw: dict[int, list[tuple[datetime, float]]] = {}
        fut_prices: dict[int, list[tuple[datetime, float]]] = {}
        opt_trades: dict[int, list[tuple[datetime, float, float, str]]] = {}
        for row in self._read_csv("trades", instrument, ts):
            if not (row.get("ts_event") or "").strip():
                continue  # malformed row (empty timestamp) -> skip
            iid = int(row["instrument_id"])
            event = _parse_ts(row["ts_event"])
            size = _to_float(row.get("size")) or 0.0
            raw.setdefault(iid, []).append((event, size))
            if iid in futures_iids:
                px = _to_float(row.get("price"))
                if px is not None and px > 0.0:
                    fut_prices.setdefault(iid, []).append((event, px))
            elif iid in option_iids:
                px = _to_float(row.get("price"))
                side = (row.get("side") or "").strip().upper() or "N"
                if px is not None and px > 0.0:
                    opt_trades.setdefault(iid, []).append((event, px, size, side))
        trades: dict[int, tuple[list[datetime], list[float]]] = {}
        for iid, series in raw.items():
            series.sort(key=lambda x: x[0])
            ts_list = [t for t, _ in series]
            prefix = [0.0]
            for _, size in series:
                prefix.append(prefix[-1] + size)
            trades[iid] = (ts_list, prefix)
        for series in fut_prices.values():
            series.sort(key=lambda x: x[0])
        for opt_series in opt_trades.values():
            opt_series.sort(key=lambda x: x[0])
        return trades, fut_prices, opt_trades

    def _load_quotes(
        self, instrument: str, ts: datetime
    ) -> dict[int, list[tuple[datetime, Optional[float], Optional[float]]]]:
        quotes: dict[int, list[tuple[datetime, Optional[float], Optional[float]]]] = {}
        for row in self._read_csv(self.quote_schema, instrument, ts):
            if not (row.get("ts_event") or "").strip():
                continue  # malformed row (empty timestamp) -> skip, don't crash
            iid = int(row["instrument_id"])
            quotes.setdefault(iid, []).append(
                (
                    _parse_ts(row["ts_event"]),
                    _to_float(row.get("bid_px_00")),
                    _to_float(row.get("ask_px_00")),
                )
            )
        for series in quotes.values():
            series.sort(key=lambda x: x[0])
        return quotes
