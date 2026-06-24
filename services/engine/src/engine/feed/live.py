"""LiveAdapter — realtime Databento feed with safety rail.

This is the ``FEED_MODE=live`` implementation. It is **gated** by an
explicit two-key arming rail because the Databento account on this project
has been locked twice in the past from runaway request patterns; see
``docs/architecture/live-feed-threat-model.md`` for the full threat model.

THE CONTRACT
------------
* The adapter is interface-compatible with :class:`HistoricalSimAdapter`
  (same :class:`~engine.feed.base.FeedAdapter` shape, same
  :class:`OptionChainMinute` output) so the engine, datastore, and frontend
  stay byte-for-byte unchanged when ``FEED_MODE`` flips.
* ``import databento`` happens **only** inside :meth:`_open_client`, which
  is unreachable unless the operator has explicitly set both
  ``FEED_MODE=live`` and ``LIVE_FEED_ARMED=1``. Tests substitute a
  hand-rolled :class:`FakeLiveClient` instead.
* If five consecutive ``_connect()`` failures land within a five-minute
  rolling window, the adapter's circuit breaker **opens**: subsequent
  calls raise :class:`LiveFeedDegraded` and the worker is expected to
  treat that as a hard switch back to historical for the rest of the
  process lifetime (no auto-recovery; humans only).

The minute-assembly logic (definition + OI + cumulative VOL + top-of-book
mid) is intentionally a small ``_LiveBook`` inner class so the test seam
can drive it with recorded fixtures instead of a live socket.
"""
from __future__ import annotations

import logging
import os
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Deque, Optional

from engine.feed.base import (
    FeedAdapter,
    OptionChainMinute,
    ensure_utc_minute,
)

__all__ = [
    "LiveAdapter",
    "LiveFeedNotAvailable",
    "LiveFeedNotArmed",
    "LiveFeedDegraded",
    "BREAKER_FAILURE_THRESHOLD",
    "BREAKER_WINDOW_SECONDS",
    "RECONNECT_MAX_ATTEMPTS",
    "RECONNECT_MAX_WALL_SECONDS",
]

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Tunables (also documented in docs/architecture/live-feed-threat-model.md).   #
# --------------------------------------------------------------------------- #
#: Number of consecutive ``_connect()`` failures that opens the breaker.
BREAKER_FAILURE_THRESHOLD: int = 5
#: Rolling window (seconds) over which BREAKER_FAILURE_THRESHOLD is counted.
BREAKER_WINDOW_SECONDS: int = 300
#: Max retries within a single ``_connect()`` invocation.
RECONNECT_MAX_ATTEMPTS: int = 5
#: Total wall-time cap (seconds) within a single ``_connect()`` invocation.
RECONNECT_MAX_WALL_SECONDS: int = 300


# --------------------------------------------------------------------------- #
# Errors.                                                                      #
# --------------------------------------------------------------------------- #
class LiveFeedNotAvailable(RuntimeError):
    """Raised when the live feed is requested but cannot be served.

    Generic catch-all that the worker's ``_produce_live`` already handles by
    falling back to ``_republish_stale``.
    """


class LiveFeedNotArmed(LiveFeedNotAvailable):
    """``FEED_MODE=live`` but ``LIVE_FEED_ARMED`` is not set.

    Refused at boot — the worker MUST NOT contact a real account without an
    explicit human ack. Distinct subclass so the boot wiring can refuse with
    a tailored message and the test suite can assert the exact failure mode.
    """


class LiveFeedDegraded(LiveFeedNotAvailable):
    """Circuit breaker has opened: too many failures in the rolling window.

    The worker must treat this as a permanent (process-lifetime) downgrade
    to ``historical``. There is no automatic recovery; a human restarts.
    """


# --------------------------------------------------------------------------- #
# Reconnect / breaker bookkeeping.                                             #
# --------------------------------------------------------------------------- #
@dataclass
class _BreakerState:
    """Track failures within a rolling window.

    Stores per-failure unix timestamps (monotonic) and exposes the number
    of failures that landed inside the configured window.
    """

    window_seconds: int = BREAKER_WINDOW_SECONDS
    threshold: int = BREAKER_FAILURE_THRESHOLD
    failures: Deque[float] = field(default_factory=deque)
    opened: bool = False

    def record_failure(self, now: float) -> None:
        cutoff = now - self.window_seconds
        while self.failures and self.failures[0] < cutoff:
            self.failures.popleft()
        self.failures.append(now)
        if len(self.failures) >= self.threshold:
            self.opened = True

    def record_success(self) -> None:
        # Successful connect resets the in-window counter (but the breaker,
        # once opened, stays open for the rest of the process — F6).
        self.failures.clear()


# --------------------------------------------------------------------------- #
# LiveAdapter.                                                                 #
# --------------------------------------------------------------------------- #
class LiveAdapter(FeedAdapter):
    """Realtime feed adapter (gated by the two-key arming rail).

    Constructor never opens a network connection. The first ``get_chain`` /
    ``get_forward`` call triggers a lazy ``_connect()`` which runs through
    the arming gate, the breaker check, and finally the actual client
    open. Tests pass ``client_factory=`` to substitute a
    :class:`FakeLiveClient`.
    """

    mode = "live"

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        dataset: str = "GLBX.MDP3",
        client_factory: Optional[Callable[..., Any]] = None,
        time_source: Callable[[], float] = time.monotonic,
        rate: float = 0.0,
        quote_schema: str = "mbp-1",
    ) -> None:
        self.api_key = api_key
        self.dataset = dataset
        # Top-of-book schema to subscribe live. Defaults to mbp-1 (tick), but the
        # operator can pick the cheaper per-minute bbo-1m via QUOTE_SCHEMA — same
        # knob the historical adapter honors. Matching it live keeps the live
        # message volume in the envelope the operator sized for, which matters on
        # a rate-limited account (see live-feed-threat-model.md).
        self.quote_schema = quote_schema
        # Continuous risk-free rate, used only for the put-call parity forward
        # fallback inside the book (matches HistoricalSimAdapter); for 0DTE T is
        # tiny so the default 0.0 is negligible.
        self.rate = rate
        self._client: Any = None
        self._client_factory = client_factory
        self._time = time_source
        self._breaker = _BreakerState()

    # -- gating ------------------------------------------------------------ #
    @staticmethod
    def _is_armed() -> bool:
        """Whether the operator has explicitly armed live-feed contact."""
        return os.environ.get("LIVE_FEED_ARMED", "").strip() == "1"

    def _check_armed(self) -> None:
        if not self._is_armed():
            raise LiveFeedNotArmed(
                "LiveAdapter is not armed. Set LIVE_FEED_ARMED=1 to acknowledge "
                "real-account contact (see docs/architecture/live-feed-threat-model.md)."
            )

    def _check_breaker(self) -> None:
        if self._breaker.opened:
            raise LiveFeedDegraded(
                "live feed circuit breaker is OPEN; the session will hold the "
                "last frame and report STALE for the rest of the process "
                "lifetime (NO switch to historical data; human restart required)."
            )

    # -- connect ----------------------------------------------------------- #
    def _open_client(self) -> Any:
        """Open the underlying realtime client.

        IMPORTANT: this is the **only** place ``import databento`` is allowed
        in the worker code path, and it sits behind the arming check, the
        breaker check, AND the ``client_factory`` test seam. If a test ever
        reaches this branch without injecting a factory, that's a bug.
        """
        if self._client_factory is not None:
            return self._client_factory(
                api_key=self.api_key, dataset=self.dataset, quote_schema=self.quote_schema
            )

        if not self.api_key:
            raise LiveFeedNotAvailable(
                "DATABENTO_API_KEY missing; cannot open live feed."
            )
        # Real path: wrap the raw databento.Live stream in a client that owns a
        # pure LiveBook and a reader thread. The book's ASSEMBLY logic is unit-
        # tested (test_live_book.py); only the socket/threading shell below is
        # untested-against-live and pragma-excluded.
        return _DatabentoLiveClient(  # pragma: no cover - real network
            api_key=self.api_key,
            dataset=self.dataset,
            rate=self.rate,
            quote_schema=self.quote_schema,
        )

    def _connect(self) -> None:
        """Establish the realtime subscription, with bounded retries.

        Implements the per-call reconnect policy from the threat model
        (RECONNECT_MAX_ATTEMPTS retries, RECONNECT_MAX_WALL_SECONDS budget).
        Each failure increments the breaker counter; each retry sleeps with
        exponential backoff capped at 60s.
        """
        self._check_armed()
        self._check_breaker()

        if self._client is not None:
            return

        start = self._time()
        attempt = 0
        while True:
            attempt += 1
            try:
                self._client = self._open_client()
                self._breaker.record_success()
                log.info("live feed connected (attempt=%d)", attempt)
                return
            except LiveFeedNotAvailable:
                # Already-tagged, propagate without breaker increment if it's
                # an arming/degraded error — those are "don't retry" semantics.
                raise
            except Exception as exc:
                self._breaker.record_failure(self._time())
                self._check_breaker()  # may raise LiveFeedDegraded right here
                if attempt >= RECONNECT_MAX_ATTEMPTS:
                    raise LiveFeedNotAvailable(
                        f"live feed connect failed after {attempt} attempts: {exc}"
                    ) from exc
                if (self._time() - start) >= RECONNECT_MAX_WALL_SECONDS:
                    raise LiveFeedNotAvailable(
                        f"live feed connect exceeded {RECONNECT_MAX_WALL_SECONDS}s budget"
                    ) from exc
                # Backoff: 1, 2, 4, 8, 16, ..., capped at 60s.
                delay = min(2 ** (attempt - 1), 60)
                log.warning(
                    "live feed connect attempt %d failed: %s; retrying in %ds",
                    attempt, exc, delay,
                )
                self._sleep(delay)

    def _sleep(self, seconds: float) -> None:
        """Sleep hook — overridden by tests to skip wall time."""
        time.sleep(seconds)  # pragma: no cover - replaced in unit tests

    # -- public API (FeedAdapter) ----------------------------------------- #
    def get_chain(self, instrument: str, ts: datetime) -> OptionChainMinute:
        self._check_instrument(instrument)
        ensure_utc_minute(ts)
        self._connect()
        # Real assembly is delegated to the client; tests inject a fake that
        # carries a ``get_chain(instrument, ts)`` method.
        return self._client.get_chain(instrument, ts)

    def get_forward(self, instrument: str, ts: datetime) -> float:
        self._check_instrument(instrument)
        ensure_utc_minute(ts)
        self._connect()
        return self._client.get_forward(instrument, ts)

    # Optional method — exposed by the historical adapter; returning None
    # here keeps the worker's FLUX path on its degraded-feed branch until
    # the live trade pipe is wired.
    def get_flux_trades(self, instrument: str, ts: datetime) -> Optional[list]:
        self._check_instrument(instrument)
        ensure_utc_minute(ts)
        self._connect()
        getter = getattr(self._client, "get_flux_trades", None)
        if getter is None:
            return None
        return getter(instrument, ts)

    # Optional method — front-future 1-minute OHLC. Mirrors
    # HistoricalSimAdapter.get_ohlc; degrades to None when the client/book
    # cannot build a candle so the worker leaves ``ohlc`` null (never fails
    # the tick).
    def get_ohlc(
        self, instrument: str, ts: datetime
    ) -> Optional[tuple[float, float, float, float]]:
        self._check_instrument(instrument)
        ensure_utc_minute(ts)
        self._connect()
        getter = getattr(self._client, "get_ohlc", None)
        if getter is None:
            return None
        return getter(instrument, ts)


# --------------------------------------------------------------------------- #
# Real databento.Live wrapper (UNTESTED AGAINST A LIVE SOCKET).                #
# --------------------------------------------------------------------------- #
# Everything below is the network/threading shell. It is pragma-excluded from   #
# coverage and is NEVER reached in tests (the suite injects FakeLiveClient via  #
# the client_factory seam). The per-minute ASSEMBLY logic it relies on lives in #
# engine.feed.live_book.LiveBook, which IS unit-tested with synthetic records.  #
# Field names / enum encodings follow the DBN spec + scripts/convert_dbn_to_csv #
# .py, but have NOT been validated against a real stream here — an operator     #
# must confirm them through docs/architecture/live-feed-threat-model.md before  #
# trusting live numbers.                                                        #
class _DatabentoLiveClient:  # pragma: no cover - real network / threading
    """Adapts a raw ``databento.Live`` subscription onto a :class:`LiveBook`.

    Subscribes to the four record families the chain needs (definition /
    statistics / trades / quotes), routes each incoming record into the book
    from databento's reader thread, and exposes the historical-compatible
    ``get_chain`` / ``get_forward`` / ``get_flux_trades`` readers (lock-guarded).
    """

    # Parent symbols cover both options (.OPT) and futures (.FUT) for ES & NQ.
    _SYMBOLS = ["ES.OPT", "ES.FUT", "NQ.OPT", "NQ.FUT"]
    _QUOTE_SCHEMA_DEFAULT = "mbp-1"

    def __init__(
        self,
        *,
        api_key: Optional[str],
        dataset: str,
        rate: float = 0.0,
        quote_schema: str = "mbp-1",
    ) -> None:
        import threading

        import databento as db  # type: ignore[import-not-found]

        from engine.feed.live_book import LiveBook

        if not api_key:
            raise LiveFeedNotAvailable(
                "DATABENTO_API_KEY missing; cannot open live feed."
            )
        self._api_key = api_key
        self._dataset = dataset
        # Operator-chosen top-of-book schema (mbp-1 tick OR bbo-1m per-minute).
        # bbo-1m is far lower volume — the right default on a rate-limited account.
        self._quote_schema = quote_schema or self._QUOTE_SCHEMA_DEFAULT
        self._book = LiveBook(rate=rate)
        self._lock = threading.Lock()
        self._session_date: Any = None

        # CRITICAL (verified 2026-06-18 against the real feed): a live stream does
        # NOT deliver InstrumentDefMsg for instruments that ALREADY exist when the
        # subscription opens mid-session. Without definitions, incoming trades and
        # quotes cannot be classified (no strike / call-put / underlying) and the
        # chain stays empty ("could not determine forward"). So we seed today's
        # definitions ONCE from the Historical API (a bounded HTTP request, NOT a
        # stream — safe for the rate-limited account) before going live.
        seeded = self._seed_definitions()
        log.warning("live feed: seeded %d instrument definitions from Historical", seeded)

        self._client = db.Live(key=api_key)
        # Live-stream the DYNAMIC schemas only. We also keep a live `definition`
        # subscription: it won't resend existing instruments (hence the seed
        # above), but it DOES deliver NEWLY-listed strikes created after we
        # connect (common as 0DTE price drifts), so the chain stays complete.
        for schema in ("definition", "statistics", "trades", self._quote_schema):
            self._client.subscribe(
                dataset=dataset,
                schema=schema,
                stype_in="parent",
                symbols=self._SYMBOLS,
            )
        self._client.add_callback(self._on_record)
        self._client.start()

    # -- definition seeding (bounded Historical HTTP pull, not a stream) --- #
    def _seed_definitions(self) -> int:
        """Pull today's instrument definitions once via the Historical API.

        Returns the number of legs loaded into the book. Raises
        :class:`LiveFeedNotAvailable` on failure (the live feed is useless
        without definitions). Uses a bounded ``get_range`` HTTP request scoped to
        the current UTC day — NOT a streaming subscription — so it does not add
        to the live-stream request budget.
        """
        import databento as db  # type: ignore[import-not-found]
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        # The Databento Historical API has a publishing lag (observed ~10–20 min).
        # Requesting end=now can return 422 because the dataset hasn't caught up
        # yet. Buffer the end by 20 minutes so the seed succeeds even during the
        # lag window — definitions from earlier today are still valid for the
        # rest of the session.
        try:
            from datetime import timedelta
        except ImportError:
            pass
        end = now - timedelta(minutes=20)
        try:
            hist = db.Historical(key=self._api_key)
            data = hist.timeseries.get_range(
                dataset=self._dataset,
                schema="definition",
                stype_in="parent",
                symbols=self._SYMBOLS,
                start=start.strftime("%Y-%m-%dT%H:%M"),
                end=end.strftime("%Y-%m-%dT%H:%M"),
            )
        except Exception as exc:
            raise LiveFeedNotAvailable(
                f"failed to seed instrument definitions from Historical: {exc}"
            ) from exc

        n = 0
        for r in data:
            iid = getattr(getattr(r, "hd", r), "instrument_id", None)
            if iid is None:
                continue
            self._book.add_definition(
                iid,
                raw_symbol=getattr(r, "raw_symbol", ""),
                instrument_class=getattr(r, "instrument_class", ""),
                strike=getattr(r, "strike_price", None),
                expiration=getattr(r, "expiration", None),
                asset=getattr(r, "asset", ""),
            )
            n += 1
        if n == 0:
            raise LiveFeedNotAvailable(
                "definition seed returned 0 legs; refusing to start a live feed "
                "that can never assemble a chain (check market date / entitlement)."
            )
        return n

    # -- stream reader (databento thread) --------------------------------- #
    def _on_record(self, record: Any) -> None:
        """Route one DBN record into the book by its record type."""
        rtype = type(record).__name__
        iid = getattr(getattr(record, "hd", record), "instrument_id", None)
        if iid is None:
            return
        ts = self._record_ts(record)
        with self._lock:
            if "InstrumentDef" in rtype:
                self._book.add_definition(
                    iid,
                    raw_symbol=getattr(record, "raw_symbol", ""),
                    instrument_class=getattr(record, "instrument_class", ""),
                    strike=getattr(record, "strike_price", None),
                    expiration=getattr(record, "expiration", None),
                    asset=getattr(record, "asset", ""),
                )
            elif "Stat" in rtype:
                self._book.add_statistic(
                    iid,
                    ts=ts,
                    stat_type=getattr(record, "stat_type", None),
                    price=getattr(record, "price", None),
                    quantity=getattr(record, "quantity", None),
                )
            elif "Trade" in rtype:
                self._book.add_trade(
                    iid,
                    ts=ts,
                    price=getattr(record, "price", None),
                    size=getattr(record, "size", 0),
                    side=getattr(record, "side", "N"),
                )
            elif "mbp" in rtype.lower() or "bbo" in rtype.lower():
                # databento_dbn 0.80 names the top-of-book records ``MBP1Msg`` /
                # ``BBOMsg`` (also CBBOMsg / CMBP1Msg / MBP10Msg). Match
                # case-INSENSITIVELY: the older spec exposed mixed-case names and a
                # case-sensitive ``in`` check silently dropped every quote on 0.80,
                # leaving the chain with no bid/ask (no IV). Validated against the
                # installed databento_dbn class names, not a live socket.
                bid, ask = self._top_of_book(record)
                self._book.add_quote(iid, ts=ts, bid=bid, ask=ask)

    @staticmethod
    def _record_ts(record: Any) -> Any:
        """Best usable timestamp for a record: ``ts_event`` unless it is the
        UNDEF sentinel (e.g. ``bbo-1m`` carries UNDEF ``ts_event`` + valid
        ``ts_recv``), then fall back to ``ts_recv``. Returns the raw value;
        ``LiveBook`` decoders reject any remaining sentinel/garbage.
        """
        from engine.feed.live_book import _UNDEF_TS

        for attr in ("ts_event", "ts_recv"):
            val = getattr(record, attr, None)
            if val is None:
                val = getattr(getattr(record, "hd", None), attr, None)
            if isinstance(val, int) and val not in _UNDEF_TS and val > 0:
                return val
        return getattr(record, "ts_recv", None)

    @staticmethod
    def _top_of_book(record: Any) -> tuple[Any, Any]:
        """Extract bid/ask from an mbp-1/bbo record (levels[0] or *_px_00)."""
        levels = getattr(record, "levels", None)
        if levels:
            lvl = levels[0]
            return getattr(lvl, "bid_px", None), getattr(lvl, "ask_px", None)
        return getattr(record, "bid_px_00", None), getattr(record, "ask_px_00", None)

    # -- session rollover -------------------------------------------------- #
    def _maybe_reset(self, ts: datetime) -> None:
        from engine.feed.live_book import NY_TZ

        et_date = ts.astimezone(NY_TZ).date()
        if self._session_date is not None and et_date != self._session_date:
            self._book.reset_session()
        self._session_date = et_date

    # -- readers (worker thread) ------------------------------------------ #
    def get_chain(self, instrument: str, ts: datetime) -> OptionChainMinute:
        with self._lock:
            self._maybe_reset(ts)
            return self._book.get_chain(instrument, ts)

    def get_forward(self, instrument: str, ts: datetime) -> float:
        with self._lock:
            return self._book.get_forward(instrument, ts)

    def get_ohlc(
        self, instrument: str, ts: datetime
    ) -> Optional[tuple[float, float, float, float]]:
        with self._lock:
            self._maybe_reset(ts)
            return self._book.get_ohlc(instrument, ts)

    def get_flux_trades(self, instrument: str, ts: datetime) -> list[Any]:
        with self._lock:
            return self._book.get_flux_trades(instrument, ts)
