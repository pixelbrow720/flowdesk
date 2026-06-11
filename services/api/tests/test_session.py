"""T-07: session state machine boundaries (PRD #9, PRD #12 §2).

Verifies the canonical boundaries:
  * 09:30 ET open      -> LIVE
  * 16:00 ET close     -> CLOSED
  * 13:00 ET half-day  -> CLOSED (early close)
  * holiday / weekend  -> HOLIDAY
  * feed-gap > 2 min   -> STALE (and <= 2 min holds LIVE)

Network-free: uses a :class:`StaticCMECalendar` with explicit holiday/half-day
dates and timezone-aware ET datetimes.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from api.session import (
    ET,
    FEED_GAP_TOLERANCE_S,
    SessionState,
    StaticCMECalendar,
    determine_state,
)

# A normal trading Wednesday, a holiday, and a half-day.
TRADING_DAY = date(2026, 6, 10)   # Wednesday
HOLIDAY = date(2026, 12, 25)      # Christmas (Friday)
HALF_DAY = date(2026, 11, 27)     # day after Thanksgiving
WEEKEND = date(2026, 6, 13)       # Saturday

CAL = StaticCMECalendar(
    holidays={HOLIDAY},
    half_days={HALF_DAY: time(13, 0)},
)


def _et(d: date, h: int, m: int, s: int = 0) -> datetime:
    return datetime(d.year, d.month, d.day, h, m, s, tzinfo=ET)


def test_premarket_before_open() -> None:
    assert determine_state(_et(TRADING_DAY, 9, 0), CAL) is SessionState.PREMARKET
    assert determine_state(_et(TRADING_DAY, 9, 29, 59), CAL) is SessionState.PREMARKET


def test_open_boundary_is_live() -> None:
    # 09:30:00 ET exactly -> LIVE (>= open). First tick: last_snapshot_ts None.
    assert determine_state(_et(TRADING_DAY, 9, 30), CAL) is SessionState.LIVE


def test_close_boundary_is_closed() -> None:
    # 16:00:00 ET exactly -> CLOSED (>= close).
    assert determine_state(_et(TRADING_DAY, 16, 0), CAL) is SessionState.CLOSED
    assert determine_state(_et(TRADING_DAY, 15, 59, 59), CAL) is SessionState.LIVE


def test_half_day_early_close() -> None:
    # 13:00 ET on a half-day -> CLOSED; one second before -> LIVE.
    assert determine_state(_et(HALF_DAY, 13, 0), CAL) is SessionState.CLOSED
    assert determine_state(_et(HALF_DAY, 12, 59, 59), CAL) is SessionState.LIVE
    # The same wall time on a FULL day is still open.
    assert determine_state(_et(TRADING_DAY, 13, 0), CAL) is SessionState.LIVE


def test_holiday_and_weekend() -> None:
    assert determine_state(_et(HOLIDAY, 11, 0), CAL) is SessionState.HOLIDAY
    assert determine_state(_et(WEEKEND, 11, 0), CAL) is SessionState.HOLIDAY


def test_feed_gap_transitions_to_stale() -> None:
    now = _et(TRADING_DAY, 12, 0)
    # Fresh feed (60s old) -> LIVE.
    fresh = now - timedelta(seconds=60)
    assert determine_state(now, CAL, last_snapshot_ts=fresh) is SessionState.LIVE
    # Exactly at tolerance (120s) -> still LIVE (strict greater-than).
    at_tol = now - timedelta(seconds=FEED_GAP_TOLERANCE_S)
    assert determine_state(now, CAL, last_snapshot_ts=at_tol) is SessionState.LIVE
    # Beyond tolerance (3 min) -> STALE + hold.
    stale = now - timedelta(seconds=180)
    assert determine_state(now, CAL, last_snapshot_ts=stale) is SessionState.STALE


def test_feed_gap_ignored_outside_rth() -> None:
    # A long gap before the open is still PREMARKET, not STALE.
    pre = _et(TRADING_DAY, 9, 0)
    old = pre - timedelta(hours=20)
    assert determine_state(pre, CAL, last_snapshot_ts=old) is SessionState.PREMARKET


def test_accepts_utc_input() -> None:
    # 13:30 UTC == 09:30 ET in June (EDT, UTC-4) -> LIVE at the open.
    utc_open = datetime(2026, 6, 10, 13, 30, tzinfo=timezone.utc)
    assert determine_state(utc_open, CAL) is SessionState.LIVE


def test_naive_now_rejected() -> None:
    try:
        determine_state(datetime(2026, 6, 10, 9, 30), CAL)
    except ValueError:
        return
    raise AssertionError("expected ValueError for naive datetime")
