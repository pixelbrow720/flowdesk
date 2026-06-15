"""HIRO unification (worker <-> generator parity) — commit 3 unit coverage.

Covers the persistent accumulator wiring on :class:`MinuteWorker`:

  * Tier-1 restore — when Redis carries a same-day HIRO dump, a fresh worker
    process resumes accumulation instead of starting from scratch.
  * Tier-2 fallback — when Redis is empty / wrong date / malformed, the worker
    transparently starts a fresh accumulator (no crash).
  * Daily reset — when a tick crosses into a new ET session date, the
    accumulator drops the old state automatically.
  * Persist write — every HIRO-eligible LIVE tick writes the dump back to
    Redis (so the next restart can use Tier-1).

These are unit-level: a ``FakeFeed`` supplies a fixed list of trades, a
``FakeState`` records ``set_hiro_state`` calls, and we drive ``worker.tick``
directly. No engine FD or generator parity here — the parity proof itself
lives in ``test_hiro_parity.py`` (commit 4).
"""
from __future__ import annotations

import asyncio
import math
from datetime import datetime

from engine.black76 import price as bs_price
from engine.feed.base import ChainRow, OptionChainMinute
from engine.hiro import HiroTrade

from api.session import ET, SessionState, StaticCMECalendar
from api.worker import MinuteWorker

RATE = math.log(1.0 + 0.0531)
T_EXPIRY = 0.5 / 365.0


def _make_chain(ts_utc: datetime, forward: float = 5000.0) -> OptionChainMinute:
    rows: list[ChainRow] = []
    for strike in (4990.0, 5000.0, 5010.0):
        sigma = 0.20
        call = bs_price("call", forward, strike, T_EXPIRY, RATE, sigma)
        put = bs_price("put", forward, strike, T_EXPIRY, RATE, sigma)
        rows.append(
            ChainRow(strike=strike, type="call", bid=call * 0.99, ask=call * 1.01,
                     volume=100.0, oi=10.0)
        )
        rows.append(
            ChainRow(strike=strike, type="put", bid=put * 0.99, ask=put * 1.01,
                     volume=100.0, oi=10.0)
        )
    return OptionChainMinute(ts=ts_utc, forward=forward, rows=tuple(rows))


def _trade(strike: float, is_call: bool, side: str, size: float, iv: float = 0.21) -> HiroTrade:
    """A trade with explicit IV so the engine never solves IV from price."""
    return HiroTrade(
        strike=strike, is_call=is_call, price=10.0, size=size, side=side,
        t_expiry=T_EXPIRY, iv=iv,
    )


class HiroFeed:
    """FakeFeed that ALSO supplies signed trades (HIRO-eligible)."""

    def __init__(self, trades: list[HiroTrade]) -> None:
        self._trades = list(trades)
        self.calls: list[tuple[str, datetime]] = []
        self.trade_calls: list[tuple[str, datetime]] = []

    def get_chain(self, instrument: str, ts: datetime) -> OptionChainMinute:
        self.calls.append((instrument, ts))
        return _make_chain(ts)

    def get_hiro_trades(self, instrument: str, ts: datetime) -> list[HiroTrade]:
        self.trade_calls.append((instrument, ts))
        return list(self._trades)


class FakeRepo:
    def __init__(self) -> None:
        self.saved: list[object] = []

    async def save_snapshot(self, snapshot: object) -> None:
        self.saved.append(snapshot)


class HiroStateFake:
    """In-memory StateStore with HIRO Tier-1 surface (set_hiro_state / get_hiro_state)."""

    def __init__(self, *, hiro_seed: dict | None = None, raise_on_get: bool = False) -> None:
        self._now: dict[str, dict] = {}
        self.sessions: dict[str, str] = {}
        self.published: list[tuple[str, object]] = []
        self._hiro: dict[str, dict] = {"ES": hiro_seed} if hiro_seed is not None else {}
        self.hiro_writes: list[tuple[str, dict]] = []
        self._raise_on_get = raise_on_get

    async def get_now(self, instrument: str):
        return self._now.get(instrument)

    async def set_now(self, instrument: str, snapshot) -> str:
        if hasattr(snapshot, "model_dump"):
            payload = snapshot.model_dump(mode="json")
        else:
            payload = dict(snapshot)
        self._now[instrument] = payload
        self.published.append((instrument, payload))
        return ""

    async def set_session(self, instrument: str, state: str) -> None:
        self.sessions[instrument] = state

    async def set_hiro_state(self, instrument: str, payload) -> None:
        self.hiro_writes.append((instrument, dict(payload)))
        self._hiro[instrument] = dict(payload)

    async def get_hiro_state(self, instrument: str):
        if self._raise_on_get:
            raise RuntimeError("redis hiccup")
        return self._hiro.get(instrument)


CAL = StaticCMECalendar()


def _make_worker(feed, repo, state, now):
    return MinuteWorker(
        feed=feed, repo=repo, state_store=state, instruments=("ES",),
        calendar=CAL, clock=lambda: now, sofr_rate=0.0531, t_expiry=T_EXPIRY,
    )


# --------------------------------------------------------------------------- #
# Persist: each HIRO-eligible LIVE tick writes the dump back to Redis.
# --------------------------------------------------------------------------- #
def test_hiro_dump_is_persisted_on_each_live_tick() -> None:
    feed = HiroFeed([_trade(5000.0, True, "B", 10.0)])
    repo, state = FakeRepo(), HiroStateFake()
    now = datetime(2026, 6, 10, 9, 31, tzinfo=ET)  # 09:31 ET -> LIVE
    worker = _make_worker(feed, repo, state, now)

    asyncio.run(worker.tick(now))

    assert len(state.hiro_writes) == 1
    instr, payload = state.hiro_writes[0]
    assert instr == "ES"
    # Carries the running totals + the meta we need for restart recovery.
    assert payload["consumed"] == 1.0
    assert payload["date_et"] == "2026-06-10"
    assert "total" in payload and "calls" in payload and "puts" in payload


# --------------------------------------------------------------------------- #
# Tier-1 restore: a fresh worker process picks up where the previous one left off.
# --------------------------------------------------------------------------- #
def test_hiro_tier1_restores_from_same_day_redis_dump() -> None:
    seed = {
        "M": 50.0, "retail_max": 5.0,
        "total": 1234.5, "calls": 1234.5, "puts": 0.0, "zerodte": 0.0, "retail": 0.0,
        "skipped": 0.0,
        "consumed": 3.0,                # the upstream tape already had 3 trades
        "date_et": "2026-06-10",
    }
    # Same-day tape WIDER than the seed (3 already-consumed + 1 new) so we can
    # observe the suffix-feed semantics: only the NEW trade increments total.
    feed = HiroFeed([
        _trade(5000.0, True, "B", 10.0),
        _trade(5000.0, True, "B", 10.0),
        _trade(5000.0, True, "B", 10.0),
        _trade(5010.0, True, "B", 5.0),  # the only NEW one
    ])
    repo, state = FakeRepo(), HiroStateFake(hiro_seed=seed)
    now = datetime(2026, 6, 10, 9, 31, tzinfo=ET)
    worker = _make_worker(feed, repo, state, now)

    asyncio.run(worker.tick(now))

    # After restore + suffix-feed: total > seed (one new trade priced),
    # consumed advanced to len(tape)=4.
    assert len(state.hiro_writes) == 1
    _, payload = state.hiro_writes[0]
    assert payload["consumed"] == 4.0
    assert payload["total"] > 1234.5, "Tier-1 restore preserved running total + added new trade"
    # The internal accumulator carries the restored seed state (M survives).
    assert worker._hiro_states["ES"]._M == 50.0  # /ES multiplier survived


# --------------------------------------------------------------------------- #
# Tier-2 fallback: redis miss / wrong date / malformed -> fresh accumulator, no crash.
# --------------------------------------------------------------------------- #
def test_hiro_tier2_falls_back_when_redis_seed_is_for_a_different_date() -> None:
    # Yesterday's dump in Redis -> ignored, fresh state used instead.
    seed = {
        "M": 50.0, "retail_max": 5.0,
        "total": 999_999.0, "calls": 999_999.0, "puts": 0.0, "zerodte": 0.0, "retail": 0.0,
        "skipped": 0.0,
        "consumed": 99.0,
        "date_et": "2026-06-09",  # YESTERDAY
    }
    feed = HiroFeed([_trade(5000.0, True, "B", 10.0)])
    repo, state = FakeRepo(), HiroStateFake(hiro_seed=seed)
    now = datetime(2026, 6, 10, 9, 31, tzinfo=ET)
    worker = _make_worker(feed, repo, state, now)

    asyncio.run(worker.tick(now))

    # Stale running total NOT carried; the new tick computed from scratch on 1 trade.
    _, payload = state.hiro_writes[0]
    assert payload["total"] != 999_999.0
    assert payload["consumed"] == 1.0
    assert payload["date_et"] == "2026-06-10"


def test_hiro_tier2_falls_back_when_redis_get_raises() -> None:
    # Redis storage hiccup MUST NOT propagate to the tick (worker survives).
    feed = HiroFeed([_trade(5000.0, True, "B", 10.0)])
    repo, state = FakeRepo(), HiroStateFake(raise_on_get=True)
    now = datetime(2026, 6, 10, 9, 31, tzinfo=ET)
    worker = _make_worker(feed, repo, state, now)

    states = asyncio.run(worker.tick(now))

    assert states["ES"] is SessionState.LIVE
    assert len(state.hiro_writes) == 1
    assert state.hiro_writes[0][1]["consumed"] == 1.0


# --------------------------------------------------------------------------- #
# Daily reset: a tick on a NEW ET session date drops the prior accumulator.
# --------------------------------------------------------------------------- #
def test_hiro_resets_across_session_rollover() -> None:
    feed = HiroFeed([_trade(5000.0, True, "B", 10.0)])
    repo, state = FakeRepo(), HiroStateFake()

    # Day 1 tick: build some accumulator state.
    now1 = datetime(2026, 6, 10, 9, 31, tzinfo=ET)
    worker = _make_worker(feed, repo, state, now1)
    asyncio.run(worker.tick(now1))
    day1_total = worker._hiro_states["ES"].snapshot().total
    assert day1_total > 0.0

    # Day 2 tick on the SAME worker process (e.g. long-lived service that
    # spans midnight): forcibly rebind the clock and re-tick.
    now2 = datetime(2026, 6, 11, 9, 31, tzinfo=ET)
    worker._clock = lambda: now2
    asyncio.run(worker.tick(now2))

    # The accumulator was reset for the new ET session date -> the new tick
    # built up only the day-2 trades (one trade), so total < day1+day2.
    day2_total = worker._hiro_states["ES"].snapshot().total
    assert worker._hiro_session_date["ES"].isoformat() == "2026-06-11"
    # Single fresh trade priced at the same forward -> total ~= day1_total
    # (NOT day1_total + day2_total). Within FP epsilon.
    assert abs(day2_total - day1_total) < 1e-6


# --------------------------------------------------------------------------- #
# Defensive: shrunken upstream window (e.g. fixture rebuild) -> reset to 0.
# --------------------------------------------------------------------------- #
def test_hiro_resets_when_upstream_window_shrinks() -> None:
    seed = {
        "M": 50.0, "retail_max": 5.0,
        "total": 5000.0, "calls": 5000.0, "puts": 0.0, "zerodte": 0.0, "retail": 0.0,
        "skipped": 0.0,
        "consumed": 99.0,                 # claims 99 already consumed
        "date_et": "2026-06-10",
    }
    feed = HiroFeed([_trade(5000.0, True, "B", 10.0)])  # only 1 trade in tape
    repo, state = FakeRepo(), HiroStateFake(hiro_seed=seed)
    now = datetime(2026, 6, 10, 9, 31, tzinfo=ET)
    worker = _make_worker(feed, repo, state, now)

    # Should NOT raise (consumed=99 > len(trades)=1 -> defensive reset to 0).
    states = asyncio.run(worker.tick(now))
    assert states["ES"] is SessionState.LIVE
    _, payload = state.hiro_writes[0]
    assert payload["consumed"] == 1.0
    # The huge stale total was dropped on reset; the new total is fresh.
    assert payload["total"] != 5000.0
