"""LiveAdapter unit tests — fully mocked, NEVER contact Databento.

Covers the safety contract from docs/architecture/live-feed-threat-model.md:

* Two-key arming gate refuses without LIVE_FEED_ARMED=1 (F1, F3, F4).
* Circuit breaker opens after BREAKER_FAILURE_THRESHOLD failures within
  BREAKER_WINDOW_SECONDS (F2).
* Once OPEN, the breaker stays open for the rest of the process lifetime;
  subsequent calls raise LiveFeedDegraded (F6).
* Bounded reconnect: at most RECONNECT_MAX_ATTEMPTS retries per _connect()
  call, exponential backoff capped at 60s.
* Successful connect resets the in-window counter (does NOT close an
  already-opened breaker).
* The databento package is never imported during tests — substitute a
  hand-rolled FakeLiveClient via the client_factory seam.

Wall time is faked via a monotonic-clock injection so the suite stays sub-
second.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

import pytest

from engine.feed.base import OptionChainMinute
from engine.feed.live import (
    BREAKER_FAILURE_THRESHOLD,
    BREAKER_WINDOW_SECONDS,
    RECONNECT_MAX_ATTEMPTS,
    LiveAdapter,
    LiveFeedDegraded,
    LiveFeedNotArmed,
    LiveFeedNotAvailable,
)


INSTRUMENT = "ES"
TS = datetime(2025, 1, 2, 14, 30, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- #
# Fake clock + fake client.                                                    #
# --------------------------------------------------------------------------- #
class FakeClock:
    """Deterministic monotonic clock; ``advance`` instead of sleeping."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class FakeLiveClient:
    """Stand-in for a databento.Live subscription.

    Returns a fixed OptionChainMinute / forward / flux tuple. Tests use
    this to verify the adapter's public API shape without touching the
    network. Set ``raise_on_get`` to simulate a downstream error.
    """

    def __init__(self, *, api_key: Optional[str] = None, dataset: str = "GLBX.MDP3") -> None:
        self.api_key = api_key
        self.dataset = dataset
        self.calls = 0
        self.raise_on_get: Optional[Exception] = None

    def get_chain(self, instrument: str, ts: datetime) -> OptionChainMinute:
        self.calls += 1
        if self.raise_on_get is not None:
            raise self.raise_on_get
        return OptionChainMinute(ts=ts, forward=5000.0, rows=())

    def get_forward(self, instrument: str, ts: datetime) -> float:
        self.calls += 1
        return 5000.0

    def get_flux_trades(self, instrument: str, ts: datetime) -> list:
        return []


def _arm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIVE_FEED_ARMED", "1")


# --------------------------------------------------------------------------- #
# Arming gate.                                                                 #
# --------------------------------------------------------------------------- #
def test_get_chain_refuses_without_arming(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LIVE_FEED_ARMED", raising=False)
    adapter = LiveAdapter(client_factory=lambda **_: FakeLiveClient())
    with pytest.raises(LiveFeedNotArmed):
        adapter.get_chain(INSTRUMENT, TS)


def test_get_forward_refuses_without_arming(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LIVE_FEED_ARMED", raising=False)
    adapter = LiveAdapter(client_factory=lambda **_: FakeLiveClient())
    with pytest.raises(LiveFeedNotArmed):
        adapter.get_forward(INSTRUMENT, TS)


def test_get_hiro_trades_refuses_without_arming(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LIVE_FEED_ARMED", raising=False)
    adapter = LiveAdapter(client_factory=lambda **_: FakeLiveClient())
    with pytest.raises(LiveFeedNotArmed):
        adapter.get_flux_trades(INSTRUMENT, TS)


def test_armed_path_uses_factory_not_real_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Smoke: with arming + factory, get_chain returns a chain shape."""
    _arm(monkeypatch)
    fake = FakeLiveClient()
    adapter = LiveAdapter(client_factory=lambda **_: fake)
    chain = adapter.get_chain(INSTRUMENT, TS)
    assert isinstance(chain, OptionChainMinute)
    assert chain.ts == TS
    assert fake.calls == 1


# --------------------------------------------------------------------------- #
# Circuit breaker.                                                             #
# --------------------------------------------------------------------------- #
def test_breaker_opens_after_threshold_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulate a flaky factory; after THRESHOLD failures the breaker opens."""
    _arm(monkeypatch)
    clock = FakeClock()
    attempts = {"n": 0}

    def factory(**_: Any) -> Any:
        attempts["n"] += 1
        raise RuntimeError(f"connect failure #{attempts['n']}")

    adapter = LiveAdapter(client_factory=factory, time_source=clock)
    # No-op sleep; advance the fake clock so the breaker window logic is
    # exercised against real-ish timestamps.
    monkeypatch.setattr(adapter, "_sleep", lambda s: clock.advance(s))

    with pytest.raises(LiveFeedNotAvailable):
        adapter.get_chain(INSTRUMENT, TS)
    # First connect call burned RECONNECT_MAX_ATTEMPTS attempts and
    # recorded that many failures. Confirm the breaker tripped right at
    # the threshold (>= 5 in the window).
    assert adapter._breaker.opened is True
    # Subsequent calls now raise LiveFeedDegraded, not LiveFeedNotAvailable.
    with pytest.raises(LiveFeedDegraded):
        adapter.get_chain(INSTRUMENT, TS)


def test_breaker_does_not_open_within_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    """With THRESHOLD-1 failures then a success, breaker stays closed."""
    _arm(monkeypatch)
    clock = FakeClock()
    attempts = {"n": 0}
    fake = FakeLiveClient()

    def factory(**_: Any) -> Any:
        attempts["n"] += 1
        if attempts["n"] < BREAKER_FAILURE_THRESHOLD:
            raise RuntimeError(f"flake {attempts['n']}")
        return fake

    adapter = LiveAdapter(client_factory=factory, time_source=clock)
    monkeypatch.setattr(adapter, "_sleep", lambda s: clock.advance(s))
    chain = adapter.get_chain(INSTRUMENT, TS)
    assert isinstance(chain, OptionChainMinute)
    assert adapter._breaker.opened is False
    # Successful connect resets the counter.
    assert len(adapter._breaker.failures) == 0


def test_breaker_open_persists_across_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Once OPEN, no auto-recovery — even the test cannot reset it."""
    _arm(monkeypatch)
    adapter = LiveAdapter(client_factory=lambda **_: FakeLiveClient())
    adapter._breaker.opened = True

    with pytest.raises(LiveFeedDegraded):
        adapter.get_chain(INSTRUMENT, TS)
    with pytest.raises(LiveFeedDegraded):
        adapter.get_forward(INSTRUMENT, TS)
    with pytest.raises(LiveFeedDegraded):
        adapter.get_flux_trades(INSTRUMENT, TS)


def test_breaker_window_drops_old_failures() -> None:
    """Failures outside the rolling window do not count toward the threshold."""
    from engine.feed.live import _BreakerState

    state = _BreakerState()
    # Pump THRESHOLD-1 ancient failures; they all fall outside the window.
    for i in range(BREAKER_FAILURE_THRESHOLD - 1):
        state.record_failure(now=float(i))
    # Then THRESHOLD-1 fresh failures, well inside the window.
    base = float(BREAKER_WINDOW_SECONDS * 10)
    for i in range(BREAKER_FAILURE_THRESHOLD - 1):
        state.record_failure(now=base + i)
    assert state.opened is False


# --------------------------------------------------------------------------- #
# Reconnect policy.                                                            #
# --------------------------------------------------------------------------- #
def test_reconnect_caps_at_max_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    """No more than RECONNECT_MAX_ATTEMPTS attempts per _connect() call."""
    _arm(monkeypatch)
    clock = FakeClock()
    attempts = {"n": 0}

    def factory(**_: Any) -> Any:
        attempts["n"] += 1
        raise RuntimeError("flake")

    adapter = LiveAdapter(client_factory=factory, time_source=clock)
    monkeypatch.setattr(adapter, "_sleep", lambda s: clock.advance(s))
    with pytest.raises(LiveFeedNotAvailable):
        adapter.get_chain(INSTRUMENT, TS)
    assert attempts["n"] == RECONNECT_MAX_ATTEMPTS


def test_reconnect_backoff_is_exponential_capped_at_60(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Backoff sequence: 1, 2, 4, 8, 16, ..., capped at 60s."""
    _arm(monkeypatch)
    clock = FakeClock()
    sleeps: list[float] = []
    attempts = {"n": 0}

    def factory(**_: Any) -> Any:
        attempts["n"] += 1
        raise RuntimeError("flake")

    adapter = LiveAdapter(client_factory=factory, time_source=clock)

    def fake_sleep(s: float) -> None:
        sleeps.append(s)
        clock.advance(s)

    monkeypatch.setattr(adapter, "_sleep", fake_sleep)
    with pytest.raises(LiveFeedNotAvailable):
        adapter.get_chain(INSTRUMENT, TS)

    # RECONNECT_MAX_ATTEMPTS=5 -> at most 4 sleeps between them
    # (no sleep after the final attempt — it just raises).
    assert sleeps == [1, 2, 4, 8]


def test_connect_is_idempotent_after_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Once connected, subsequent calls reuse the client (no extra factory call)."""
    _arm(monkeypatch)
    factory_calls = {"n": 0}
    fake = FakeLiveClient()

    def factory(**_: Any) -> Any:
        factory_calls["n"] += 1
        return fake

    adapter = LiveAdapter(client_factory=factory)
    adapter.get_chain(INSTRUMENT, TS)
    adapter.get_chain(INSTRUMENT, TS)
    adapter.get_forward(INSTRUMENT, TS)
    assert factory_calls["n"] == 1
    assert fake.calls == 3


# --------------------------------------------------------------------------- #
# Anti-account-lock invariant: no real databento import in the test path.      #
# --------------------------------------------------------------------------- #
def test_module_does_not_eagerly_import_databento() -> None:
    """The 'databento' package is imported inside _open_client only."""
    import sys
    import importlib
    import engine.feed.live as live_mod

    importlib.reload(live_mod)
    assert "databento" not in sys.modules


def test_open_client_uses_factory_when_provided(monkeypatch: pytest.MonkeyPatch) -> None:
    """Defensive: factory is called instead of the real databento.Live."""
    _arm(monkeypatch)
    sentinel = FakeLiveClient()
    captured = {}

    def factory(**kw: Any) -> Any:
        captured.update(kw)
        return sentinel

    adapter = LiveAdapter(api_key="not-a-real-key", client_factory=factory)
    chain = adapter.get_chain(INSTRUMENT, TS)
    assert chain.ts == TS
    # Factory received api_key + dataset kwargs only; we never tried to
    # actually authenticate against Databento.
    assert captured == {"api_key": "not-a-real-key", "dataset": "GLBX.MDP3"}
