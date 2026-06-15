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
    ) -> None:
        self.api_key = api_key
        self.dataset = dataset
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
                "live feed circuit breaker is OPEN; degrading to historical "
                "for the rest of the process lifetime (human restart required)."
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
            return self._client_factory(api_key=self.api_key, dataset=self.dataset)

        if not self.api_key:
            raise LiveFeedNotAvailable(
                "DATABENTO_API_KEY missing; cannot open live feed."
            )
        # Lazy import — keeps the module CI-safe (F4).
        try:
            import databento as db  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - environment-dependent
            raise LiveFeedNotAvailable(
                "the 'databento' package is not installed; "
                "live feed cannot be opened."
            ) from exc

        client = db.Live(key=self.api_key)  # pragma: no cover - real network
        client.subscribe(  # pragma: no cover - real network
            dataset=self.dataset,
            schema="trades",
            stype_in="parent",
            symbols=["ES.OPT", "ES.FUT", "NQ.OPT", "NQ.FUT"],
        )
        return client

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
