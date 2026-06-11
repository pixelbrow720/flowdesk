"""FlowDesk session calendar & state machine (PRD #9, T-07).

This module is the *single source of truth* for the PRD #9 session state. The
engine deliberately does NOT compute the calendar (see
``engine.snapshot.build_snapshot`` -- it accepts a pre-resolved ``session_state``
string); the worker resolves the state here and passes it down.

States (PRD #9): ``PREMARKET | LIVE | STALE | CLOSED | HOLIDAY``.

Canonical pseudocode (PRD #9, MANDATORY)::

    determine_state(now_et):
        if is_holiday(date(now_et)):       return HOLIDAY
        open_t  = 09:30 ET
        close_t = half_day_close(date) or 16:00 ET
        if now_et < open_t:                return PREMARKET
        if now_et >= close_t:              return CLOSED
        gap = now_et - last_snapshot_ts
        if gap > feed_gap_tolerance:       return STALE   # hold last frame
        return LIVE

Design notes
------------
* ``determine_state`` is a PURE function: no I/O, no clock reads, no globals.
  ``now`` MUST be a timezone-aware datetime (any zone); it is converted to
  America/New_York for the time-of-day boundaries and to UTC for the feed-gap
  delta, so callers can pass either UTC or ET safely.
* The calendar is injected via the :class:`MarketCalendar` protocol so the CME
  holiday/half-day table can be swapped or extended without touching the state
  machine. A pure, network-free :class:`StaticCMECalendar` ships as the default.
* Weekends are non-trading and resolve to ``HOLIDAY`` (PRD #9 lumps all
  non-trading days under the closed/holiday banner; the FE shows replay either
  way -- AC-S5).
"""
from __future__ import annotations

import enum
from datetime import date, datetime, time, timezone
from typing import Optional, Protocol, runtime_checkable
from zoneinfo import ZoneInfo

__all__ = [
    "SessionState",
    "ET",
    "RTH_OPEN",
    "RTH_CLOSE",
    "HALF_DAY_CLOSE",
    "FEED_GAP_TOLERANCE_S",
    "MarketCalendar",
    "StaticCMECalendar",
    "default_calendar",
    "determine_state",
]

#: Exchange wall-clock timezone for the regular trading hours (RTH) boundaries.
ET = ZoneInfo("America/New_York")

#: Regular trading hours for /ES & /NQ index options (locked contract, PRD #0).
RTH_OPEN: time = time(9, 30)
RTH_CLOSE: time = time(16, 0)

#: Early-close time on CME half-days (e.g. day after Thanksgiving, Christmas Eve).
HALF_DAY_CLOSE: time = time(13, 0)

#: Feed-gap tolerance (PRD #9): a missing minute within 1-2 min holds the last
#: frame; beyond this the session is flagged STALE. ">2 minutes" -> 120 seconds.
FEED_GAP_TOLERANCE_S: float = 120.0


class SessionState(str, enum.Enum):
    """PRD #9 session states. ``str`` mixin so ``.value`` round-trips to Redis."""

    PREMARKET = "PREMARKET"
    LIVE = "LIVE"
    STALE = "STALE"
    CLOSED = "CLOSED"
    HOLIDAY = "HOLIDAY"

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return self.value


@runtime_checkable
class MarketCalendar(Protocol):
    """Calendar contract consumed by :func:`determine_state`.

    Implementations decide which dates are holidays and which are half-days.
    Both methods are pure lookups on a ``date`` (already in ET).
    """

    def is_holiday(self, d: date) -> bool:
        """Return True if ``d`` is a full CME market holiday."""
        ...

    def half_day_close(self, d: date) -> Optional[time]:
        """Return the early-close ET time for ``d`` or ``None`` for a full day."""
        ...


class StaticCMECalendar:
    """Pure, network-free CME calendar backed by an explicit holiday table.

    The sandbox has no internet and no exchange-calendar package, so the holiday
    and half-day sets are passed in (or default to the documented baseline).
    Owners can extend/override the table without touching the state machine; the
    authoritative CME schedule is a TODO-FROM-OWNER (see README).
    """

    def __init__(
        self,
        holidays: Optional[set[date]] = None,
        half_days: Optional[dict[date, time]] = None,
    ) -> None:
        self._holidays: frozenset[date] = frozenset(holidays or set())
        self._half_days: dict[date, time] = dict(half_days or {})

    def is_holiday(self, d: date) -> bool:
        return d in self._holidays

    def half_day_close(self, d: date) -> Optional[time]:
        return self._half_days.get(d)

    # convenience for ops/debugging ---------------------------------------
    @property
    def holidays(self) -> frozenset[date]:
        return self._holidays

    @property
    def half_days(self) -> dict[date, time]:
        return dict(self._half_days)


#: Baseline US equity-index holidays + half-days for 2026 (NOT authoritative --
#: see TODO-FROM-OWNER). Used only when no calendar is injected.
_2026_HOLIDAYS: set[date] = {
    date(2026, 1, 1),    # New Year's Day
    date(2026, 1, 19),   # Martin Luther King Jr. Day
    date(2026, 2, 16),   # Washington's Birthday
    date(2026, 4, 3),    # Good Friday
    date(2026, 5, 25),   # Memorial Day
    date(2026, 6, 19),   # Juneteenth
    date(2026, 7, 3),    # Independence Day (observed)
    date(2026, 9, 7),    # Labor Day
    date(2026, 11, 26),  # Thanksgiving
    date(2026, 12, 25),  # Christmas Day
}
_2026_HALF_DAYS: dict[date, time] = {
    date(2026, 11, 27): HALF_DAY_CLOSE,  # day after Thanksgiving
    date(2026, 12, 24): HALF_DAY_CLOSE,  # Christmas Eve
}


def default_calendar() -> StaticCMECalendar:
    """Return the shipped baseline calendar (2026 holidays/half-days)."""
    return StaticCMECalendar(holidays=set(_2026_HOLIDAYS), half_days=dict(_2026_HALF_DAYS))


def _require_aware(now: datetime) -> datetime:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("determine_state requires a timezone-aware datetime for `now`")
    return now


def session_close(d: date, calendar: MarketCalendar) -> time:
    """Resolve the RTH close time for ``d`` (half-day aware)."""
    return calendar.half_day_close(d) or RTH_CLOSE


def determine_state(
    now: datetime,
    calendar: MarketCalendar,
    *,
    last_snapshot_ts: Optional[datetime] = None,
    feed_gap_tolerance_s: float = FEED_GAP_TOLERANCE_S,
) -> SessionState:
    """Resolve the PRD #9 session state for ``now`` (pure, T-07).

    Parameters
    ----------
    now : timezone-aware datetime (UTC or any zone). Converted to ET for the
        09:30/close boundaries and to UTC for the feed-gap delta.
    calendar : injected :class:`MarketCalendar` (holiday + half-day lookups).
    last_snapshot_ts : timezone-aware ts of the last *stored* snapshot, or None.
        Drives the feed-gap -> STALE transition while the market is open. When
        None (first tick of the session) the state is LIVE.
    feed_gap_tolerance_s : seconds of feed silence tolerated before STALE.

    Returns
    -------
    SessionState
    """
    now = _require_aware(now)
    now_et = now.astimezone(ET)
    d = now_et.date()

    # Weekend or full holiday -> non-trading.
    if now_et.weekday() >= 5 or calendar.is_holiday(d):
        return SessionState.HOLIDAY

    open_t = RTH_OPEN
    close_t = session_close(d, calendar)
    t = now_et.timetz().replace(tzinfo=None)

    if t < open_t:
        return SessionState.PREMARKET
    if t >= close_t:
        return SessionState.CLOSED

    # Within RTH: healthy unless the feed has gone silent for too long.
    if last_snapshot_ts is not None:
        last = _require_aware(last_snapshot_ts).astimezone(timezone.utc)
        gap_s = (now.astimezone(timezone.utc) - last).total_seconds()
        if gap_s > feed_gap_tolerance_s:
            return SessionState.STALE
    return SessionState.LIVE
