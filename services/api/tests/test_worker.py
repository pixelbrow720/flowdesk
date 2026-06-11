"""T-08: one worker tick produces + stores + publishes a snapshot (PRD #12 §2).

Uses in-memory fakes for the feed, repo and state store (no DB, no Redis, no
network). The fake feed prices each leg with Black-76 so the engine's IV solver
round-trips exactly and ``build_snapshot`` runs the full real pipeline.

Covered:
  * LIVE tick -> save_snapshot called once + set_now published once; the
    published payload validates under the engine schema (instrument/state/ts).
  * STALE tick -> last frame re-published with ``stale=true``, ts unchanged,
    and NO new row stored (hold semantics).
  * CLOSED tick -> idle (no save, no publish), session recorded.
"""
from __future__ import annotations

import asyncio
import math
from datetime import date, datetime, time, timezone

from engine.black76 import price as bs_price
from engine.feed.base import ChainRow, OptionChainMinute
from engine.schema import parse_snapshot

from api.session import ET, SessionState, StaticCMECalendar
from api.worker import MinuteWorker

RATE = math.log(1.0 + 0.0531)
T_EXPIRY = 0.5 / 365.0


def _make_chain(ts_utc: datetime, forward: float = 5000.0) -> OptionChainMinute:
    """Deterministic, IV-solvable chain (legs priced with Black-76)."""
    rows: list[ChainRow] = []
    for strike in (4980.0, 4990.0, 5000.0, 5010.0, 5020.0):
        sigma = 0.20
        call = bs_price("call", forward, strike, T_EXPIRY, RATE, sigma)
        put = bs_price("put", forward, strike, T_EXPIRY, RATE, sigma)
        rows.append(
            ChainRow(
                strike=strike, type="call", bid=call * 0.99, ask=call * 1.01,
                volume=100.0 + strike, oi=10.0 + strike,
            )
        )
        rows.append(
            ChainRow(
                strike=strike, type="put", bid=put * 0.99, ask=put * 1.01,
                volume=120.0 + strike, oi=12.0 + strike,
            )
        )
    return OptionChainMinute(ts=ts_utc, forward=forward, rows=tuple(rows))


class FakeFeed:
    def __init__(self) -> None:
        self.calls: list[tuple[str, datetime]] = []

    def get_chain(self, instrument: str, ts: datetime) -> OptionChainMinute:
        self.calls.append((instrument, ts))
        return _make_chain(ts)

    def get_forward(self, instrument: str, ts: datetime) -> float:
        return 5000.0


class FakeRepo:
    def __init__(self) -> None:
        self.saved: list[object] = []

    async def save_snapshot(self, snapshot: object) -> None:
        self.saved.append(snapshot)


class FakeState:
    """In-memory StateStore stand-in. ``set_now`` records published payloads."""

    def __init__(self) -> None:
        self._now: dict[str, dict] = {}
        self.sessions: dict[str, str] = {}
        self.published: list[tuple[str, object]] = []

    def seed(self, instrument: str, payload: dict) -> None:
        self._now[instrument] = payload

    async def get_now(self, instrument: str):
        return self._now.get(instrument)

    async def set_now(self, instrument: str, snapshot) -> str:
        # Mirror the real StateStore: accept a model or a dict, store the dict.
        if hasattr(snapshot, "model_dump"):
            payload = snapshot.model_dump(mode="json")
        elif hasattr(snapshot, "to_json"):
            import json as _json

            payload = _json.loads(snapshot.to_json())
        else:
            payload = dict(snapshot)
        self._now[instrument] = payload
        self.published.append((instrument, payload))
        return ""

    async def set_session(self, instrument: str, state: str) -> None:
        self.sessions[instrument] = state


CAL = StaticCMECalendar()  # no holidays/half-days for 2026-06-10 (a Wednesday)


def _worker(feed, repo, state, now):
    return MinuteWorker(
        feed=feed, repo=repo, state_store=state, instruments=("ES",),
        calendar=CAL, clock=lambda: now, sofr_rate=0.0531, t_expiry=T_EXPIRY,
    )


def test_live_tick_produces_stores_publishes() -> None:
    feed, repo, state = FakeFeed(), FakeRepo(), FakeState()
    now = datetime(2026, 6, 10, 9, 31, tzinfo=ET)  # 09:31 ET -> LIVE
    worker = _worker(feed, repo, state, now)

    states = asyncio.run(worker.tick(now))

    assert states["ES"] is SessionState.LIVE
    assert len(feed.calls) == 1
    assert len(repo.saved) == 1, "snapshot must be stored to Timescale"
    assert len(state.published) == 1, "snapshot must be published to Redis/WS"
    assert state.sessions["ES"] == "LIVE"

    instrument, payload = state.published[0]
    snap = parse_snapshot(payload)  # validates under the engine contract
    assert snap.instrument == "ES"
    assert snap.state == "LIVE"
    assert snap.stale is False
    assert snap.ts.endswith("Z")
    # ts aligned to the wall-clock minute in UTC (09:31 ET == 13:31 UTC, June).
    assert snap.ts == "2026-06-10T13:31:00Z"


def test_stale_tick_holds_last_frame() -> None:
    feed, repo, state = FakeFeed(), FakeRepo(), FakeState()
    now = datetime(2026, 6, 10, 12, 0, tzinfo=ET)
    # Seed a last snapshot that is 3 minutes old -> gap > tolerance -> STALE.
    old_ts = "2026-06-10T15:57:00Z"  # 11:57 ET, 3 min before 12:00 ET (16:00 UTC)
    state.seed("ES", {"instrument": "ES", "ts": old_ts, "minute_index": 147,
                       "state": "LIVE", "stale": False})
    worker = _worker(feed, repo, state, now)

    states = asyncio.run(worker.tick(now))

    assert states["ES"] is SessionState.STALE
    assert feed.calls == [], "STALE must not pull the feed"
    assert repo.saved == [], "STALE holds the frame; nothing new is stored"
    assert len(state.published) == 1, "STALE re-publishes the held frame"
    _, payload = state.published[0]
    assert payload["stale"] is True
    assert payload["state"] == "STALE"
    assert payload["ts"] == old_ts, "ts unchanged so the gap keeps growing"
    assert state.sessions["ES"] == "STALE"


def test_closed_tick_is_idle() -> None:
    feed, repo, state = FakeFeed(), FakeRepo(), FakeState()
    now = datetime(2026, 6, 10, 16, 30, tzinfo=ET)  # after close -> CLOSED
    worker = _worker(feed, repo, state, now)

    states = asyncio.run(worker.tick(now))

    assert states["ES"] is SessionState.CLOSED
    assert feed.calls == []
    assert repo.saved == []
    assert state.published == []
    assert state.sessions["ES"] == "CLOSED"


def test_run_loop_is_bounded_and_aligned() -> None:
    """The scheduler loop honours max_ticks and sleeps toward the next minute."""
    feed, repo, state = FakeFeed(), FakeRepo(), FakeState()
    now = datetime(2026, 6, 10, 9, 31, 20, tzinfo=ET)  # 20s into the minute
    slept: list[float] = []

    async def fake_sleep(secs: float) -> None:
        slept.append(secs)

    worker = MinuteWorker(
        feed=feed, repo=repo, state_store=state, instruments=("ES",),
        calendar=CAL, clock=lambda: now, sleeper=fake_sleep, t_expiry=T_EXPIRY,
    )
    ticks = asyncio.run(worker.run(max_ticks=2))
    assert ticks == 2
    # One sleep between the two ticks; ~40s remain until the next minute.
    assert len(slept) == 1
    assert abs(slept[0] - 40.0) < 1e-6
