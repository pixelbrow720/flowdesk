"""Regression tests for ``MinuteWorker._net_flow_ddoi_for`` (DDOI synthetic-ΔOI map).

The DDOI lens builds a per-leg synthetic-ΔOI map from the timestamped tape by
weighting each leg's chronologically-sorted trades with
``ddoi_time_weight(i, n) = 1 − 2·(i/(n−1))`` (early=+1 opening, last=−1 closing)
times ``|size|``. Two properties are locked here:

  (a) VOL-orthogonality / sign-blindness — flipping every aggressor ``side``
      (B↔A) leaves the map IDENTICAL, because it uses ``abs(size)`` + a time
      weight and never reads the aggressor sign.
  (b) time-weight structure — a single leg with sizes [10, 20, 30] in time order
      yields ``+1·10 + 0·20 + (−1)·30 = −20``; trades with no ``ts`` are skipped;
      a single-trade leg gets weight +1; ``None``/empty input -> ``None``.

Uses the same in-memory fakes + worker construction as ``test_worker.py``; the
method ignores ``self`` so a minimally-constructed worker is sufficient.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

from engine.hiro import HiroTrade

from api.session import SessionState, StaticCMECalendar
from api.worker import MinuteWorker

T_EXPIRY = 0.5 / 365.0
_CAL = StaticCMECalendar()


class _FakeFeed:
    def get_chain(self, instrument: str, ts: datetime):  # pragma: no cover - unused
        raise NotImplementedError

    def get_forward(self, instrument: str, ts: datetime) -> float:  # pragma: no cover
        return 5000.0


class _FakeRepo:
    async def save_snapshot(self, snapshot: object) -> None:  # pragma: no cover
        ...


class _FakeState:
    async def set_now(self, instrument: str, snapshot) -> str:  # pragma: no cover
        return ""

    async def set_session(self, instrument: str, state: str) -> None:  # pragma: no cover
        ...


def _worker() -> MinuteWorker:
    now = datetime(2026, 6, 10, 9, 31, tzinfo=timezone.utc)
    return MinuteWorker(
        feed=_FakeFeed(), repo=_FakeRepo(), state_store=_FakeState(),
        instruments=("ES",), calendar=_CAL, clock=lambda: now,
        sofr_rate=0.0531, t_expiry=T_EXPIRY,
    )


def _ts(minute: int) -> datetime:
    return datetime(2026, 6, 10, 14, minute, tzinfo=timezone.utc)


def _trade(size: float, side: str, ts, strike: float = 5000.0, is_call: bool = True) -> HiroTrade:
    return HiroTrade(
        strike=strike, is_call=is_call, price=1.0, size=size, side=side,
        t_expiry=T_EXPIRY, ts=ts,
    )


def _flip(side: str) -> str:
    return {"B": "A", "A": "B"}[side]


def test_ddoi_known_per_leg_value() -> None:
    """Single leg, sizes [10, 20, 30] in time order -> +1·10 + 0·20 + (−1)·30 = −20."""
    worker = _worker()
    # Inserted out of chronological order to also exercise the internal sort.
    trades = [
        _trade(20.0, "B", _ts(31)),
        _trade(30.0, "A", _ts(32)),
        _trade(10.0, "B", _ts(30)),
    ]
    flow = worker._net_flow_ddoi_for(trades)
    assert flow == {(5000.0, True): -20.0}


def test_ddoi_single_trade_leg_weight_plus_one() -> None:
    """A leg with one trade gets weight +1 (ddoi_time_weight(0, 1) == 1)."""
    worker = _worker()
    flow = worker._net_flow_ddoi_for([_trade(17.0, "A", _ts(30))])
    assert flow == {(5000.0, True): 17.0}


def test_ddoi_sign_flip_invariance() -> None:
    """Flipping every aggressor side (B<->A) yields an IDENTICAL map (VOL-orthogonal)."""
    worker = _worker()
    trades = [
        _trade(10.0, "B", _ts(30), strike=5000.0, is_call=True),
        _trade(20.0, "A", _ts(31), strike=5000.0, is_call=True),
        _trade(30.0, "B", _ts(32), strike=5000.0, is_call=True),
        _trade(40.0, "A", _ts(30), strike=4990.0, is_call=False),
        _trade(15.0, "B", _ts(31), strike=4990.0, is_call=False),
    ]
    flipped = [
        _trade(t.size, _flip(t.side), t.ts, strike=t.strike, is_call=t.is_call)
        for t in trades
    ]
    base = worker._net_flow_ddoi_for(trades)
    other = worker._net_flow_ddoi_for(flipped)
    assert base == other
    # Sanity: the map is non-trivial so the equality is meaningful.
    assert base == {(5000.0, True): -20.0, (4990.0, False): 25.0}


def test_ddoi_skips_trades_without_timestamp() -> None:
    """Trades with ``ts=None`` cannot be time-ordered and are excluded."""
    worker = _worker()
    trades = [
        _trade(10.0, "B", _ts(30)),
        _trade(20.0, "B", None),     # skipped
        _trade(30.0, "A", _ts(32)),
    ]
    # Only the two timestamped trades remain: n=2, weights +1 and -1.
    # ddoi_time_weight(0, 2) = +1, (1, 2) = -1 -> +1·10 + (−1)·30 = −20.
    flow = worker._net_flow_ddoi_for(trades)
    assert flow == {(5000.0, True): -20.0}


def test_ddoi_none_and_empty_input_return_none() -> None:
    worker = _worker()
    assert worker._net_flow_ddoi_for(None) is None
    assert worker._net_flow_ddoi_for([]) is None
    # A tape of only timestamp-less trades collapses to an empty map -> None.
    assert worker._net_flow_ddoi_for([_trade(10.0, "B", None)]) is None
