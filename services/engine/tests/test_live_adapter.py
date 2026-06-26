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
    LiveFeedCrashLoop,
    LiveFeedDegraded,
    LiveFeedNotArmed,
    LiveFeedNotAvailable,
    _CrashLoopGuard,
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


def _isolated_guard() -> "_CrashLoopGuard":
    """Create a crash-loop guard with an isolated temp path for testing."""
    import tempfile
    from pathlib import Path

    log_path = Path(tempfile.mkdtemp()) / "arm-attempts.log"
    return _CrashLoopGuard(path=str(log_path))


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
    adapter = LiveAdapter(client_factory=lambda **_: fake, crash_loop_guard=_isolated_guard())
    chain = adapter.get_chain(INSTRUMENT, TS)
    assert isinstance(chain, OptionChainMinute)
    assert chain.ts == TS
    assert fake.calls == 1


# --------------------------------------------------------------------------- #
# get_ohlc — front-future candle, delegated to the client/book.               #
# --------------------------------------------------------------------------- #
class FakeOhlcClient(FakeLiveClient):
    """FakeLiveClient that also exposes get_ohlc (like the real LiveBook)."""

    def get_ohlc(
        self, instrument: str, ts: datetime
    ) -> tuple[float, float, float, float]:
        return (5000.0, 5010.0, 4995.0, 5005.0)


def test_get_ohlc_refuses_without_arming(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LIVE_FEED_ARMED", raising=False)
    adapter = LiveAdapter(client_factory=lambda **_: FakeOhlcClient(), crash_loop_guard=_isolated_guard())
    with pytest.raises(LiveFeedNotArmed):
        adapter.get_ohlc(INSTRUMENT, TS)


def test_get_ohlc_delegates_to_client(monkeypatch: pytest.MonkeyPatch) -> None:
    _arm(monkeypatch)
    adapter = LiveAdapter(client_factory=lambda **_: FakeOhlcClient(), crash_loop_guard=_isolated_guard())
    assert adapter.get_ohlc(INSTRUMENT, TS) == (5000.0, 5010.0, 4995.0, 5005.0)


def test_get_ohlc_none_when_client_lacks_method(monkeypatch: pytest.MonkeyPatch) -> None:
    """A client without get_ohlc degrades to None (never raises)."""
    _arm(monkeypatch)
    adapter = LiveAdapter(client_factory=lambda **_: FakeLiveClient(), crash_loop_guard=_isolated_guard())
    assert adapter.get_ohlc(INSTRUMENT, TS) is None


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

    adapter = LiveAdapter(client_factory=factory, time_source=clock, crash_loop_guard=_isolated_guard())
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

    adapter = LiveAdapter(client_factory=factory, time_source=clock, crash_loop_guard=_isolated_guard())
    monkeypatch.setattr(adapter, "_sleep", lambda s: clock.advance(s))
    chain = adapter.get_chain(INSTRUMENT, TS)
    assert isinstance(chain, OptionChainMinute)
    assert adapter._breaker.opened is False
    # Successful connect resets the counter.
    assert len(adapter._breaker.failures) == 0


def test_breaker_open_persists_across_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Once OPEN, no auto-recovery — even the test cannot reset it."""
    _arm(monkeypatch)
    adapter = LiveAdapter(client_factory=lambda **_: FakeLiveClient(), crash_loop_guard=_isolated_guard())
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

    adapter = LiveAdapter(client_factory=factory, time_source=clock, crash_loop_guard=_isolated_guard())
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

    adapter = LiveAdapter(client_factory=factory, time_source=clock, crash_loop_guard=_isolated_guard())

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

    adapter = LiveAdapter(client_factory=factory, crash_loop_guard=_isolated_guard())
    adapter.get_chain(INSTRUMENT, TS)
    adapter.get_chain(INSTRUMENT, TS)
    adapter.get_forward(INSTRUMENT, TS)
    assert factory_calls["n"] == 1
    assert fake.calls == 3


# --------------------------------------------------------------------------- #
# Anti-account-lock invariant: no real databento import in the test path.      #
# --------------------------------------------------------------------------- #
def test_module_does_not_eagerly_import_databento() -> None:
    """The 'databento' package is imported inside _open_client only.

    Checked in a SUBPROCESS on purpose: importlib.reload() of engine.feed.live
    swaps the module's class objects in place, which breaks isinstance() for any
    LiveAdapter built afterwards (the test file's top-level import keeps the old
    class). A subprocess verifies the invariant without polluting this process's
    sys.modules / class identities.
    """
    import subprocess
    import sys

    code = (
        "import sys, engine.feed.live\n"
        "assert 'databento' not in sys.modules, 'databento imported eagerly'\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_open_client_uses_factory_when_provided(monkeypatch: pytest.MonkeyPatch) -> None:
    """Defensive: factory is called instead of the real databento.Live."""
    _arm(monkeypatch)
    sentinel = FakeLiveClient()
    captured = {}

    def factory(**kw: Any) -> Any:
        captured.update(kw)
        return sentinel

    adapter = LiveAdapter(api_key="not-a-real-key", client_factory=factory, crash_loop_guard=_isolated_guard())
    chain = adapter.get_chain(INSTRUMENT, TS)
    assert chain.ts == TS
    # Factory received api_key + dataset + quote_schema kwargs only; we never
    # tried to actually authenticate against Databento.
    assert captured == {
        "api_key": "not-a-real-key",
        "dataset": "GLBX.MDP3",
        "quote_schema": "mbp-1",
    }


# --------------------------------------------------------------------------- #
# Quote schema plumbing (account-safety): the live client must subscribe to    #
# the operator-chosen QUOTE_SCHEMA, not always the high-volume mbp-1 tick       #
# stream. bbo-1m is the cheaper per-minute BBO the historical adapter uses.     #
# --------------------------------------------------------------------------- #
def test_live_adapter_passes_quote_schema_to_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    """A quote_schema given to LiveAdapter reaches the client factory."""
    _arm(monkeypatch)
    captured: dict[str, Any] = {}

    def factory(**kw: Any) -> Any:
        captured.update(kw)
        return FakeLiveClient()

    adapter = LiveAdapter(
        api_key="not-a-real-key", client_factory=factory, quote_schema="bbo-1m", crash_loop_guard=_isolated_guard()
    )
    adapter.get_chain(INSTRUMENT, TS)
    assert captured["quote_schema"] == "bbo-1m"


def test_live_adapter_default_quote_schema_is_mbp1(monkeypatch: pytest.MonkeyPatch) -> None:
    """Back-compatible default: mbp-1 when no quote_schema is supplied."""
    _arm(monkeypatch)
    captured: dict[str, Any] = {}

    def factory(**kw: Any) -> Any:
        captured.update(kw)
        return FakeLiveClient()

    adapter = LiveAdapter(api_key="not-a-real-key", client_factory=factory, crash_loop_guard=_isolated_guard())
    adapter.get_chain(INSTRUMENT, TS)
    assert captured["quote_schema"] == "mbp-1"


def test_make_adapter_live_threads_quote_schema_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """make_adapter('live') honors QUOTE_SCHEMA env, mirroring the historical path."""
    from engine.feed import make_adapter

    _arm(monkeypatch)
    monkeypatch.setenv("QUOTE_SCHEMA", "bbo-1m")
    adapter = make_adapter("live", api_key="not-a-real-key")
    assert isinstance(adapter, LiveAdapter)
    assert adapter.quote_schema == "bbo-1m"


def test_make_adapter_live_explicit_quote_schema_wins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An explicit quote_schema arg overrides the env var."""
    from engine.feed import make_adapter

    _arm(monkeypatch)
    monkeypatch.setenv("QUOTE_SCHEMA", "mbp-1")
    adapter = make_adapter("live", api_key="not-a-real-key", quote_schema="bbo-1m")
    assert isinstance(adapter, LiveAdapter)
    assert adapter.quote_schema == "bbo-1m"


# --------------------------------------------------------------------------- #
# Seed-query regression (live.py _seed_definitions + _SYMBOLS).                #
# --------------------------------------------------------------------------- #
# ROOT CAUSE (verified against real GLBX definitions 2026-06-26): today's 0DTE
# definitions are NOT served by `ES.OPT`/`EW.OPT` (those resolve to quarterly /
# standard-weekly only) and the `definition` schema is a POINT-IN-TIME change
# stream, so a `now - 1 day` seed window catches only sparse near-money
# increments of today's grid. The fix has two parts: (1) enumerate the full
# daily/weekly parent families, (2) widen the seed lookback to span the listing
# /re-publish of today's expiry.
def test_seed_symbols_cover_daily_and_weekly_families() -> None:
    """The subscription/seed symbol set MUST include the daily + weekly 0DTE
    parent families for BOTH instruments, not just ES.OPT/NQ.OPT/EW.OPT.

    Real GLBX data: Fri 2026-06-26 0DTE lives under parent `EW4` (ES) / `QN4`
    (NQ); Mon-Thu dailies under `E{w}{A..D}` / `Q{w}{A..D}`. Without these the
    seed never receives today's $5 grid and the chain falls back to the wrong
    far/quarterly expiry.
    """
    from engine.feed.live import _DatabentoLiveClient

    syms = set(_DatabentoLiveClient._SYMBOLS)
    # Futures + quarterly options still present.
    assert {"ES.FUT", "NQ.FUT", "ES.OPT", "NQ.OPT"} <= syms
    # Daily families (a representative sample across weekdays/weeks).
    assert "E4D.OPT" in syms  # ES Thursday daily
    assert "EW4.OPT" in syms  # ES Friday weekly (today's 2026-06-26 root)
    assert "Q4D.OPT" in syms  # NQ Thursday daily
    assert "QN4.OPT" in syms  # NQ Friday weekly
    # Full Mon-Thu daily coverage for both instruments (5 weeks x 4 days).
    for w in range(1, 6):
        for d in ("A", "B", "C", "D"):
            assert f"E{w}{d}.OPT" in syms, f"missing ES daily root E{w}{d}"
            assert f"Q{w}{d}.OPT" in syms, f"missing NQ daily root Q{w}{d}"


def test_seed_window_spans_listing_publication_history() -> None:
    """The seed window MUST look back far enough to include the listing /
    re-publish dates of today's 0DTE definitions.

    The `definition` schema is a point-in-time change stream: `get_range`
    returns only records PUBLISHED in [start, end). Today's daily grid is listed
    ~2-3 weeks ahead and re-published weekly, so a `now - 1 day` window catches
    only sparse increments. This test verifies the source uses the multi-week
    SEED_LOOKBACK_DAYS constant, not a 1-day offset.
    """
    import inspect

    from engine.feed.live import SEED_LOOKBACK_DAYS, _DatabentoLiveClient

    assert SEED_LOOKBACK_DAYS >= 21, (
        "seed lookback must span ~2-3 weeks of definition publication history; "
        f"got {SEED_LOOKBACK_DAYS}"
    )
    src = inspect.getsource(_DatabentoLiveClient._seed_definitions)
    assert "SEED_LOOKBACK_DAYS" in src, (
        "_seed_definitions must compute start from SEED_LOOKBACK_DAYS, not a "
        "fixed 1-day offset (which misses the listing-date publication of "
        "today's 0DTE grid)."
    )
    assert "timedelta(days=1)" not in src, (
        "_seed_definitions still uses the disproven 1-day window; the daily 0DTE "
        "grid is published weeks ahead and a 1-day window misses it."
    )

# --------------------------------------------------------------------------- #
# Record-router regression (databento_dbn 0.80 class names).                   #
# --------------------------------------------------------------------------- #
# databento_dbn names the records ``InstrumentDefMsg`` / ``StatMsg`` /
# ``TradeMsg`` and, for top-of-book, the ALL-CAPS ``MBP1Msg`` / ``BBOMsg``.
# The router in ``_DatabentoLiveClient._on_record`` keys on the class name; a
# case-SENSITIVE ``"Mbp1" in rtype`` check silently dropped every quote on 0.80
# (chain ends up with no bid/ask -> no IV). This guards the case-insensitive fix.
class _RecHd:
    def __init__(self, iid: int) -> None:
        self.instrument_id = iid


class _RecordingBook:
    """Captures which LiveBook mutator the router dispatched to."""

    def __init__(self) -> None:
        self.routed: list[str] = []

    def add_definition(self, iid: int, **kw: Any) -> None:
        self.routed.append("definition")

    def add_statistic(self, iid: int, **kw: Any) -> None:
        self.routed.append("statistic")

    def add_trade(self, iid: int, **kw: Any) -> None:
        self.routed.append("trade")

    def add_quote(self, iid: int, **kw: Any) -> None:
        self.routed.append("quote")


def _make_record(class_name: str, **fields: Any) -> Any:
    """Build a stub DBN record whose ``type().__name__`` is *class_name*."""
    fields.setdefault("hd", _RecHd(1))
    fields.setdefault("ts_event", int(TS.timestamp() * 1_000_000_000))
    return type(class_name, (), fields)()


@pytest.mark.parametrize(
    ("class_name", "expected"),
    [
        ("InstrumentDefMsg", "definition"),
        ("StatMsg", "statistic"),
        ("TradeMsg", "trade"),
        ("MBP1Msg", "quote"),   # 0.80 top-of-book (was silently dropped)
        ("BBOMsg", "quote"),    # 0.80 per-minute BBO
        ("CMBP1Msg", "quote"),
        ("CBBOMsg", "quote"),
    ],
)
def test_on_record_routes_databento_080_class_names(class_name: str, expected: str) -> None:
    """Each real databento_dbn 0.80 record name routes to the right book mutator."""
    import threading

    from engine.feed.live import _DatabentoLiveClient

    stub = _DatabentoLiveClient.__new__(_DatabentoLiveClient)  # bypass network __init__
    stub._lock = threading.Lock()
    stub._book = _RecordingBook()

    record = _make_record(
        class_name,
        bid_px_00=int(5804.0 * 1_000_000_000),
        ask_px_00=int(5806.0 * 1_000_000_000),
    )
    _DatabentoLiveClient._on_record(stub, record)

    assert stub._book.routed == [expected]


# --------------------------------------------------------------------------- #
# Crash-loop detector (F3 — k8s restart storm defense).                        #
# --------------------------------------------------------------------------- #
class TestCrashLoopGuard:
    """Unit tests for _CrashLoopGuard: the on-disk arm-attempt ledger.

    The ledger is append-only and survives process restarts — exactly the
    point of the F3 defense (catches a Kubernetes restart storm before the
    in-process breaker can even spin up). Each test uses an isolated tmpdir
    so the operator's real ledger at ~/.flowdesk/ is never touched.
    """

    def test_allows_arms_within_threshold(self, tmp_path: Any) -> None:
        """Up to max_arms entries inside the window is fine."""
        from engine.feed.live import CRASH_LOOP_MAX_ARMS

        log = tmp_path / "arms.log"
        guard = _CrashLoopGuard(path=str(log))
        # Exactly max_arms attempts should NOT trip the detector.
        for _ in range(CRASH_LOOP_MAX_ARMS):
            guard.check_and_record()  # must not raise
        assert log.exists()

    def test_refuses_when_over_threshold(self, tmp_path: Any) -> None:
        """One more arm past the threshold raises LiveFeedCrashLoop."""
        from engine.feed.live import CRASH_LOOP_MAX_ARMS

        log = tmp_path / "arms.log"
        guard = _CrashLoopGuard(path=str(log))
        # Push one entry past the threshold -> refuse on the 4th call.
        for _ in range(CRASH_LOOP_MAX_ARMS):
            guard.check_and_record()
        with pytest.raises(LiveFeedCrashLoop) as exc_info:
            guard.check_and_record()
        assert "crash-loop detected" in str(exc_info.value)

    def test_old_entries_outside_window_dont_count(self, tmp_path: Any) -> None:
        """Arms older than CRASH_LOOP_WINDOW_SECONDS are dropped from the roll."""
        from engine.feed.live import CRASH_LOOP_MAX_ARMS, CRASH_LOOP_WINDOW_SECONDS

        log = tmp_path / "arms.log"
        # Pre-seed the log with CRASH_LOOP_MAX_ARMS ancient entries.
        with log.open("w") as fh:
            for i in range(CRASH_LOOP_MAX_ARMS):
                fh.write(f"{float(i)}\n")  # timestamps from 1970, way outside window

        # Inject a clock that's far past the window so all seeded entries are ancient.
        now = [float(CRASH_LOOP_WINDOW_SECONDS * 20)]
        guard = _CrashLoopGuard(path=str(log), wall_clock=lambda: now[0])
        # max_arms fresh calls should succeed: the ancient entries are all dropped.
        for _ in range(CRASH_LOOP_MAX_ARMS):
            guard.check_and_record()
        # The (max_arms+1)th call trips it: now we have max_arms+1 recent entries.
        with pytest.raises(LiveFeedCrashLoop):
            guard.check_and_record()

    def test_fails_open_on_read_error(self, tmp_path: Any, caplog: Any) -> None:
        """If the log can't be read, don't refuse — fail open with a warning."""
        import logging
        from unittest.mock import patch

        log = tmp_path / "arms.log"
        guard = _CrashLoopGuard(path=str(log))
        with patch("builtins.open", side_effect=OSError("disk I/O")):
            with caplog.at_level(logging.WARNING, logger="engine.feed.live"):
                # Must NOT raise LiveFeedCrashLoop.
                guard.check_and_record()
        assert any("failing open" in r.message for r in caplog.records)

    def test_fails_open_on_append_error(self, tmp_path: Any, caplog: Any) -> None:
        """If the log can't be written, don't refuse — fail open with a warning."""
        import logging
        from unittest.mock import patch

        log = tmp_path / "arms.log"
        guard = _CrashLoopGuard(path=str(log))
        real_open = __builtins__["open"] if isinstance(__builtins__, dict) else open  # type: ignore[index]

        def selective_open(path, mode="r", *a, **kw):  # type: ignore[no-untyped-def]
            if "a" in mode:
                raise OSError("disk I/O")
            return real_open(path, mode, *a, **kw)

        with patch("builtins.open", side_effect=selective_open):
            with caplog.at_level(logging.WARNING, logger="engine.feed.live"):
                # Must NOT raise LiveFeedCrashLoop — fail open.
                guard.check_and_record()
        assert any("failing open" in r.message for r in caplog.records)

    def test_creates_parent_directory(self, tmp_path: Any) -> None:
        """If the ledger's parent dir doesn't exist, create it on first append."""
        log = tmp_path / "deep" / "nested" / "dir" / "arms.log"
        guard = _CrashLoopGuard(path=str(log))
        guard.check_and_record()
        assert log.exists()
        assert log.read_text().strip() != ""

    def test_tolerates_garbage_lines(self, tmp_path: Any) -> None:
        """Human-edited / partial lines are dropped, not crashed on."""
        from engine.feed.live import CRASH_LOOP_MAX_ARMS

        log = tmp_path / "arms.log"
        # Pre-seed garbage; the parser drops it, not crash, and the roll is 0.
        log.write_text("# comment\n   \nnot-a-number\n")
        guard = _CrashLoopGuard(path=str(log))
        for _ in range(CRASH_LOOP_MAX_ARMS):
            guard.check_and_record()  # must not raise


# --------------------------------------------------------------------------- #
# Crash-loop integration with LiveAdapter.                                     #
# --------------------------------------------------------------------------- #
def test_live_adapter_refuses_when_crash_loop_trips(monkeypatch: pytest.MonkeyPatch) -> None:
    """A fresh LiveAdapter refuses to connect if the ledger is already hot.

    Simulates the k8s-restart-storm scenario: the operator's ledger file
    already has CRASH_LOOP_MAX_ARMS recent entries. The next boot must
    refuse BEFORE opening any client.
    """
    import tempfile
    from pathlib import Path

    from engine.feed.live import CRASH_LOOP_MAX_ARMS

    _arm(monkeypatch)
    log = Path(tempfile.mkdtemp()) / "arms.log"
    # Pre-seed the ledger with max_arms recent entries.
    import time as _time

    now = _time.time()
    with log.open("w") as fh:
        for i in range(CRASH_LOOP_MAX_ARMS):
            fh.write(f"{now + i}\n")

    guard = _CrashLoopGuard(path=str(log))
    adapter = LiveAdapter(
        client_factory=lambda **_: FakeLiveClient(),
        crash_loop_guard=guard,
    )
    with pytest.raises(LiveFeedCrashLoop):
        adapter.get_chain(INSTRUMENT, TS)


def test_unarmed_boot_does_not_pollute_ledger(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unarmed boot must never touch the arm-attempt log (F1, F4).

    Stray/unarmed boots shouldn't pollute the ledger — otherwise a CI run
    or a FEED_MODE=historical boot could accidentally trip the detector
    for the next real-armed boot.
    """
    import tempfile
    from pathlib import Path

    monkeypatch.delenv("LIVE_FEED_ARMED", raising=False)
    log = Path(tempfile.mkdtemp()) / "arms.log"
    guard = _CrashLoopGuard(path=str(log))
    adapter = LiveAdapter(
        client_factory=lambda **_: FakeLiveClient(),
        crash_loop_guard=guard,
    )
    with pytest.raises(LiveFeedNotArmed):
        adapter.get_chain(INSTRUMENT, TS)
    # Ledger must not have been touched.
    assert not log.exists()


def test_live_arm_log_path_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """LIVE_ARM_LOG_PATH env var overrides the default ledger path."""
    import tempfile
    from pathlib import Path

    from engine.feed.live import _default_arm_log_path

    override = str(Path(tempfile.mkdtemp()) / "custom-arms.log")
    monkeypatch.setenv("LIVE_ARM_LOG_PATH", override)
    assert _default_arm_log_path() == override


def test_live_arm_log_path_defaults_to_flowdesk_dir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without LIVE_ARM_LOG_PATH, the ledger lives under ~/.flowdesk/."""
    from engine.feed.live import _default_arm_log_path

    monkeypatch.delenv("LIVE_ARM_LOG_PATH", raising=False)
    assert _default_arm_log_path().endswith(
        os.path.join(".flowdesk", "live-arm-attempts.log")
    )


# `os` is needed for os.path.join above.
import os  # noqa: E402
