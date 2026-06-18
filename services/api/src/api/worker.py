"""FlowDesk per-minute worker (PRD #9 / #12 T-08).

The worker is the heartbeat of the terminal. Once per wall-clock minute (aligned
to the ET minute boundary) it, for each instrument:

  1. resolves the PRD #9 session state via :func:`api.session.determine_state`;
  2. **LIVE**     -> pulls the chain from the :class:`FeedAdapter`
     (``FEED_MODE`` selects historical/live), runs ``engine.build_snapshot``,
     persists to TimescaleDB (``SnapshotRepository.save_snapshot``) and writes
     the now-state to Redis (``StateStore.set_now`` -> publishes to the WS);
  3. **STALE**    -> re-publishes the last stored snapshot with ``stale=true``
     (holds the last frame, does NOT advance the snapshot ts -- AC of PRD #9);
  4. **CLOSED / HOLIDAY / PREMARKET** -> idle (only records the session state).

Testability
-----------
Every side-effecting dependency is injected: ``clock`` (a callable returning an
aware datetime), the ``feed`` adapter, the ``repo`` and the ``state_store`` (and
a ``sleeper`` for the loop). :meth:`MinuteWorker.tick` runs exactly one cycle so
a single tick can be unit-tested deterministically (T-08) without a real clock,
feed, database or Redis.

Nothing here imports FastAPI, asyncpg or redis at import time, so the module
loads (and its logic runs) in minimal/offline environments.
"""
from __future__ import annotations

import asyncio
import logging
import math
import os
from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from api.session import (
    MarketCalendar,
    SessionState,
    default_calendar,
    determine_state,
)

__all__ = [
    "STRIKE_STEP",
    "DEFAULT_SOFR_RATE",
    "DEFAULT_T_EXPIRY",
    "rate_from_sofr",
    "FeedLike",
    "RepoLike",
    "StateLike",
    "MinuteWorker",
    "build_worker_from_env",
]

log = logging.getLogger("flowdesk.worker")

#: Locked strike granularity per instrument (PRD #0): /ES = 5 pts, /NQ = 10 pts.
STRIKE_STEP: dict[str, float] = {"ES": 5.0, "NQ": 10.0}

#: Default SOFR (decimal) when ``SOFR_RATE`` is unset. FINAL value is owner-set.
DEFAULT_SOFR_RATE: float = 0.0531

#: Legacy FIXED 0DTE year-fraction (~half a day). Superseded as the default by
#: the real-clock day-count (Divergence #3 -> option A): the worker now computes
#: ``t_expiry`` per tick from the wall clock to 16:00 ET via
#: ``engine.snapshot.t_expiry_from_clock``. Pass an explicit ``t_expiry=`` to
#: :class:`MinuteWorker` to pin this fixed value instead (used by unit tests).
DEFAULT_T_EXPIRY: float = 0.5 / 365.0


def rate_from_sofr(sofr: float) -> float:
    """Continuous annual rate ``r = ln(1 + SOFR)`` (locked contract, PRD #7)."""
    return math.log(1.0 + float(sofr))


# --------------------------------------------------------------------------- #
# Structural typing for the injected collaborators (duck-typed, no imports).   #
# --------------------------------------------------------------------------- #
class FeedLike:  # pragma: no cover - documentation only
    """Shape of an ``engine.feed.FeedAdapter``: ``get_chain(instrument, ts)``."""


class RepoLike:  # pragma: no cover - documentation only
    """Shape of ``db.repo.SnapshotRepository``: ``await save_snapshot(snap)``."""


class StateLike:  # pragma: no cover - documentation only
    """Shape of ``api.state.StateStore``.

    Requires ``await get_now(instrument)``, ``await set_now(instrument, snap)``
    and ``await set_session(instrument, state)``.
    """


Clock = Callable[[], datetime]
Sleeper = Callable[[float], Awaitable[None]]


def _utc_minute(now: datetime) -> datetime:
    """Convert an aware datetime to UTC truncated to the minute."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("worker clock must return a timezone-aware datetime")
    return now.astimezone(UTC).replace(second=0, microsecond=0)


def _parse_aware(ts: Any) -> datetime | None:
    """Parse a snapshot ``ts`` (ISO-8601 ...Z) into an aware UTC datetime."""
    if ts is None:
        return None
    if isinstance(ts, datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=UTC)
    s = str(ts).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _axis_from_chain(instrument: str, chain: Any) -> dict[str, float]:
    """Derive the shared strike axis from a chain (locked step per instrument)."""
    step = STRIKE_STEP[instrument]
    strikes = list(chain.strikes()) if hasattr(chain, "strikes") else []
    if strikes:
        return {"strike_min": float(min(strikes)), "strike_max": float(max(strikes)), "step": step}
    f = float(getattr(chain, "forward", 0.0))
    return {"strike_min": f, "strike_max": f, "step": step}


class MinuteWorker:
    """Drives one snapshot cycle per minute for the configured instruments."""

    def __init__(
        self,
        *,
        feed: Any,
        repo: Any,
        state_store: Any,
        instruments: Sequence[str] = ("ES", "NQ"),
        calendar: MarketCalendar | None = None,
        clock: Clock | None = None,
        sleeper: Sleeper | None = None,
        sofr_rate: float = DEFAULT_SOFR_RATE,
        t_expiry: float | None = None,
        feed_gap_tolerance_s: float | None = None,
        build_snapshot: Callable[..., Any] | None = None,
        to_engine_chain: Callable[..., Any] | None = None,
    ) -> None:
        self._feed = feed
        self._repo = repo
        self._state = state_store
        self._instruments = tuple(instruments)
        self._calendar = calendar or default_calendar()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._sleeper = sleeper or asyncio.sleep
        self._rate = rate_from_sofr(sofr_rate)
        # None => real-clock day-count per tick (Divergence #3 -> option A,
        # the default). A float pins a FIXED year-fraction (legacy / tests).
        self._t_expiry: float | None = (
            None if t_expiry is None else float(t_expiry)
        )
        self._gap_kwargs = (
            {} if feed_gap_tolerance_s is None else {"feed_gap_tolerance_s": feed_gap_tolerance_s}
        )
        # Engine entry points are injected lazily so the module imports without
        # the engine present (e.g. for isolated worker unit tests).
        self._build_snapshot = build_snapshot
        self._to_engine_chain = to_engine_chain
        self._stop = asyncio.Event()
        # Persistent FLUX accumulators per instrument (worker <-> generator
        # parity, docs/architecture/flux-unification.md). Populated lazily on
        # first FLUX-eligible tick; survive worker restarts via Redis Tier-1.
        self._flux_states: dict[str, Any] = {}
        self._hiro_consumed: dict[str, int] = {}
        self._hiro_session_date: dict[str, Any] = {}

    # -- engine lazy binding ---------------------------------------------- #
    def _engine(self) -> tuple[Callable[..., Any], Callable[..., Any]]:
        if self._build_snapshot is None or self._to_engine_chain is None:
            from engine.feed import to_engine_chain as _tec
            from engine.snapshot import build_snapshot as _bs

            self._build_snapshot = self._build_snapshot or _bs
            self._to_engine_chain = self._to_engine_chain or _tec
        return self._build_snapshot, self._to_engine_chain

    # -- single cycle ----------------------------------------------------- #
    async def tick(self, now: datetime | None = None) -> dict[str, SessionState]:
        """Run exactly one cycle for every instrument; return resolved states."""
        now = now or self._clock()
        out: dict[str, SessionState] = {}
        for instrument in self._instruments:
            try:
                out[instrument] = await self._tick_instrument(instrument, now)
            except Exception:  # one bad instrument must not skip the others
                log.exception("tick failed for %s", instrument)
        return out

    async def _tick_instrument(self, instrument: str, now: datetime) -> SessionState:
        last = await self._state.get_now(instrument)
        last_ts = _parse_aware(last.get("ts")) if isinstance(last, Mapping) else None
        state = determine_state(
            now, self._calendar, last_snapshot_ts=last_ts, **self._gap_kwargs
        )

        if state is SessionState.LIVE:
            produced = await self._produce_live(instrument, now)
            if not produced and last is not None:
                # Feed hiccup inside RTH: hold the last frame (don't blank).
                # determine_state will flip to STALE once the gap exceeds the
                # tolerance on a subsequent tick.
                log.warning("feed produced nothing for %s; holding last frame", instrument)
        elif state is SessionState.STALE:
            # STALE means determine_state saw a feed-gap (> tolerance) since the
            # last stored ts. ALWAYS attempt a live recovery first: pull the
            # feed and try to produce a fresh snapshot. If the feed comes back
            # (e.g. first 09:30 tick after overnight/restart, or an in-session
            # gap that has just resolved), _produce_live advances ts and we
            # mark the session LIVE for this tick. Only when the feed is still
            # down do we fall back to _republish_stale to hold the last frame.
            recovered = await self._produce_live(instrument, now)
            if recovered:
                await self._state.set_session(instrument, SessionState.LIVE.value)
                return SessionState.LIVE
            await self._republish_stale(instrument, last)
        # PREMARKET / CLOSED / HOLIDAY -> idle.

        await self._state.set_session(instrument, state.value)
        return state

    # -- day-count resolution --------------------------------------------- #
    def _t_expiry_for(self, ts_utc: datetime) -> float:
        """Year-fraction to 0DTE settlement for this minute.

        Divergence #3 -> option A (default): when ``t_expiry`` was not pinned at
        construction, compute the real-clock fraction from ``ts`` to 16:00 ET via
        ``engine.snapshot.t_expiry_from_clock`` so gamma/theta/charm sharpen
        correctly through the afternoon. A pinned float (legacy / tests) is
        returned unchanged.
        """
        if self._t_expiry is not None:
            return self._t_expiry
        from engine.snapshot import t_expiry_from_clock

        return t_expiry_from_clock(ts_utc)

    def _fetch_signed_trades(self, instrument: str, ts_utc: datetime) -> Any:
        """The signed per-trade tape for this minute, or ``None`` if unavailable.

        Fetched ONCE per tick and shared by FLUX + synthetic-OI (both consume the
        same ``get_flux_trades`` list) to avoid a redundant per-minute scan. The
        live stub / test fakes lack ``get_flux_trades`` -> ``None`` -> both fields
        degrade to None, mirroring the ``ohlc`` precedent.
        """
        get_trades = getattr(self._feed, "get_flux_trades", None)
        if get_trades is None:
            return None
        return get_trades(instrument, ts_utc)

    # -- FLUX persistent accumulator (worker <-> generator parity) -------- #
    @staticmethod
    def _et_date_of(ts_utc: datetime) -> Any:
        """Calendar date in America/New_York for a UTC timestamp.

        Used to drive the daily reset-at-RTH-open: the accumulator's state-date
        is compared against this to detect a session rollover.
        """
        from api.session import ET

        return ts_utc.astimezone(ET).date()

    async def _maybe_restore_hiro(self, instrument: str, ts_utc: datetime) -> None:
        """Tier-1 restore: pull the accumulator dump from Redis on first use.

        Called the first time we touch FLUX for an instrument (state dict miss).
        If the persisted dump's session date matches today's ET date we reseed
        the in-memory ``FluxState`` and ``_hiro_consumed`` so cumulative FLUX
        survives a worker restart within the same RTH session. On any miss
        (no key, expired, malformed, date mismatch, or storage error) we fall
        back to a fresh accumulator — Tier 2 (see
        ``docs/architecture/flux-unification.md`` §4.4).
        """
        from engine.flux import FluxState
        from engine.snapshot import MULTIPLIER

        today_et = self._et_date_of(ts_utc)
        try:
            payload = await self._state.get_flux_state(instrument)
        except Exception as exc:  # storage hiccup -> Tier 2 fallback (silent)
            log.warning("flux restore failed for %s: %s; starting fresh", instrument, exc)
            payload = None

        if payload is not None:
            stored_date = payload.get("date_et")
            if stored_date == today_et.isoformat():
                try:
                    state = FluxState.from_dict(payload)
                    consumed = int(payload.get("consumed", 0))
                    self._flux_states[instrument] = state
                    self._hiro_consumed[instrument] = consumed
                    self._hiro_session_date[instrument] = today_et
                    log.info(
                        "flux restored for %s (consumed=%d, total=%.2f)",
                        instrument, consumed, state.snapshot().total,
                    )
                    return
                except Exception as exc:
                    log.warning(
                        "flux payload malformed for %s: %s; starting fresh",
                        instrument, exc,
                    )

        # Tier-2 fallback: fresh accumulator.
        self._flux_states[instrument] = FluxState(MULTIPLIER[instrument])
        self._hiro_consumed[instrument] = 0
        self._hiro_session_date[instrument] = today_et

    def _maybe_reset_hiro_for_session(self, instrument: str, ts_utc: datetime) -> None:
        """Reset accumulator if the ET session date has rolled over.

        Triggered when ``_hiro_session_date[instrument]`` differs from today's
        ET date (the **b** option from §4.3). Drops the in-memory state, resets
        ``_hiro_consumed``, and updates the session date. The Redis dump from
        the previous day is left to expire by TTL (or be overwritten on the
        next persist).
        """
        from engine.flux import FluxState
        from engine.snapshot import MULTIPLIER

        today_et = self._et_date_of(ts_utc)
        if self._hiro_session_date.get(instrument) == today_et:
            return
        log.info("flux reset for %s (new session %s)", instrument, today_et.isoformat())
        self._flux_states[instrument] = FluxState(MULTIPLIER[instrument])
        self._hiro_consumed[instrument] = 0
        self._hiro_session_date[instrument] = today_et

    async def _hiro_for(
        self,
        instrument: str,
        ts_utc: datetime,
        forward: float,
        trades: Any = None,
    ) -> Any:
        """Cumulative FLUX snapshot via the **persistent accumulator**.

        Worker <-> generator parity (see
        ``docs/architecture/flux-unification.md``): per session, hold one
        ``FluxState`` and feed only the NEW suffix of trades each minute at the
        **current minute's forward**. This freezes each trade's increment at
        its arrival forward — economically correct (hedging happens at the
        price prevailing then) and identical to ``gen_session_snapshots.py``.

        Returns ``None`` when the feed cannot supply signed per-trade data
        (live stub / test fakes), mirroring the ``ohlc`` precedent.
        """
        if trades is None:
            trades = self._fetch_signed_trades(instrument, ts_utc)
        if trades is None:
            return None

        # Tier-1 restore on first touch this process for this instrument.
        if instrument not in self._flux_states:
            await self._maybe_restore_hiro(instrument, ts_utc)
        # Daily reset at RTH-open rollover.
        self._maybe_reset_hiro_for_session(instrument, ts_utc)

        state = self._flux_states[instrument]
        consumed = self._hiro_consumed[instrument]
        # Defensive: if the upstream window shrank (replay restart, timezone
        # quirk, fixture rebuild) the suffix index is stale — start over from
        # zero rather than IndexError. Worst case is one tick of re-priced
        # increments at the current forward.
        if consumed > len(trades):
            log.warning(
                "flux consumed (%d) > trade window (%d) for %s; resetting accumulator",
                consumed, len(trades), instrument,
            )
            from engine.flux import FluxState
            from engine.snapshot import MULTIPLIER

            state = FluxState(MULTIPLIER[instrument])
            self._flux_states[instrument] = state
            consumed = 0

        # Feed only the NEW suffix at the current minute's forward.
        for tr in trades[consumed:]:
            state.add(tr, float(forward), self._rate)
        self._hiro_consumed[instrument] = len(trades)

        # Persist Tier-1 dump for restart recovery (best-effort, never fail tick).
        payload = state.to_dict()
        payload["consumed"] = float(self._hiro_consumed[instrument])
        payload["date_et"] = self._hiro_session_date[instrument].isoformat()
        try:
            await self._state.set_flux_state(instrument, payload)
        except Exception as exc:
            log.warning("flux persist failed for %s: %s", instrument, exc)

        return state.snapshot()

    def _net_flow_for(self, trades: Any) -> Any:
        """Per-(strike, is_call) net aggressor-signed flow for synthetic-OI, or None.

        Aggregates ``Sum(aggressor_sign * size)`` from the SAME ``trades`` tape FLUX
        consumes (B=+1, A=-1, N=0). Returns ``None`` when no signed tape is available
        (live stub / fakes) so ``synthetic_oi`` degrades to None like ``flux``.
        """
        if trades is None:
            return None
        from engine.flux import aggressor_sign

        flow: dict[tuple[float, bool], float] = {}
        for tr in trades:
            s = aggressor_sign(tr.side)
            if s == 0:
                continue
            key = (float(tr.strike), bool(tr.is_call))
            flow[key] = flow.get(key, 0.0) + s * float(tr.size)
        return flow or None

    def _net_flow_tiered_for(self, trades: Any, instrument: str) -> Any:
        """Size-TIERED per-leg net aggressor flow for synthetic-OI #6, or None.

        Same as ``_net_flow_for`` but each trade's signed size is multiplied by a
        size-tier weight (retail odd-lots downweighted, institutional blocks up)
        BEFORE summing — EXPERIMENTAL, thresholds unvalidated. Block floor is
        per-instrument. Reduces to ``_net_flow_for`` when the tier weights are all 1.
        """
        if trades is None:
            return None
        from engine.flux import aggressor_sign
        from engine.synthetic_oi import BLOCK_MIN_SIZE, tier_weight

        block_min = BLOCK_MIN_SIZE.get(instrument, 50.0)
        flow: dict[tuple[float, bool], float] = {}
        for tr in trades:
            s = aggressor_sign(tr.side)
            if s == 0:
                continue
            g = tier_weight(float(tr.size), block_min=block_min)
            if g == 0.0:
                continue
            key = (float(tr.strike), bool(tr.is_call))
            flow[key] = flow.get(key, 0.0) + s * float(tr.size) * g
        return flow or None

    def _net_flow_decay_for(self, trades: Any, ts_utc: datetime) -> Any:
        """Time-DECAY-weighted per-leg net aggressor flow for synthetic-OI #5, or None.

        Same as ``_net_flow_for`` but each trade's signed size is multiplied by
        ``exp(-ln2 * age / half_life)`` BEFORE summing, where ``age`` is the trade's
        age in minutes at the snapshot eval time ``ts_utc`` — recent flow outweighs
        old flow. EXPERIMENTAL, half-life unvalidated. Trades with no timestamp are
        skipped (cannot age them). Reduces to ``_net_flow_for`` when decay is off.
        """
        if trades is None:
            return None
        from engine.flux import aggressor_sign
        from engine.synthetic_oi import decay_weight

        flow: dict[tuple[float, bool], float] = {}
        for tr in trades:
            s = aggressor_sign(tr.side)
            if s == 0:
                continue
            tr_ts = getattr(tr, "ts", None)
            if tr_ts is None:
                continue  # cannot age a trade with no timestamp -> exclude
            age_min = (ts_utc - tr_ts).total_seconds() / 60.0
            g = decay_weight(age_min)
            key = (float(tr.strike), bool(tr.is_call))
            flow[key] = flow.get(key, 0.0) + s * float(tr.size) * g
        return flow or None

    def _net_flow_ddoi_for(self, trades: Any) -> Any:
        """Per-leg synthetic ΔOI (open/close-classified) for the DDOI lens, or None.

        Groups trades per (strike, is_call), orders them chronologically, and sums
        ``ddoi_time_weight(i, n) * |size|`` — early trades treated as OPENING (+),
        late as CLOSING (−). DIRECTION-AGNOSTIC (uses |size|, ignores aggressor sign)
        so it cannot telescope back to VOL; non-circular (never reads ΔOI). Trades
        with no timestamp are skipped (cannot order them). EXPERIMENTAL heuristic.
        """
        if trades is None:
            return None
        from engine.ddoi import ddoi_time_weight

        per_leg: dict[tuple[float, bool], list] = {}
        for tr in trades:
            tr_ts = getattr(tr, "ts", None)
            if tr_ts is None:
                continue  # cannot time-order a trade with no timestamp
            key = (float(tr.strike), bool(tr.is_call))
            per_leg.setdefault(key, []).append((tr_ts, abs(float(tr.size))))
        flow: dict[tuple[float, bool], float] = {}
        for key, leg in per_leg.items():
            leg.sort(key=lambda x: x[0])  # chronological for the time weight
            n = len(leg)
            flow[key] = sum(ddoi_time_weight(i, n) * sz for i, (_, sz) in enumerate(leg))
        return flow or None

    async def _produce_live(self, instrument: str, now: datetime) -> bool:
        """Pull -> build -> store -> publish. Returns True if a snapshot shipped."""
        ts_utc = _utc_minute(now)
        build_snapshot, to_engine_chain = self._engine()
        try:
            chain = self._feed.get_chain(instrument, ts_utc)
        except Exception as exc:  # feed gap / not available -> hold last frame
            log.warning("feed.get_chain failed for %s @ %s: %s", instrument, ts_utc, exc)
            return False

        quotes = to_engine_chain(chain, t_expiry=self._t_expiry_for(ts_utc))
        forward = float(chain.forward)
        axis = _axis_from_chain(instrument, chain)
        # Front-future OHLC for the minute (mirrors the offline generator at
        # scripts/gen_session_snapshots.py). LiveAdapter has no get_ohlc / can
        # raise; guard like get_chain above and degrade to None on miss --
        # never fail the whole tick on a missing OHLC.
        try:
            ohlc = self._feed.get_ohlc(instrument, ts_utc)
        except Exception as exc:
            log.debug("feed.get_ohlc unavailable for %s @ %s: %s", instrument, ts_utc, exc)
            ohlc = None
        # Fetch the signed tape ONCE; FLUX and synthetic-OI both consume it.
        trades = self._fetch_signed_trades(instrument, ts_utc)
        snapshot = build_snapshot(
            instrument,
            ts_utc,
            quotes,
            forward,
            self._rate,
            SessionState.LIVE.value,
            axis,
            t_expiry=self._t_expiry_for(ts_utc),
            stale=False,
            expired=False,
            ohlc=ohlc,
            flux=await self._hiro_for(instrument, ts_utc, forward, trades),
            net_flow=self._net_flow_for(trades),
            net_flow_tiered=self._net_flow_tiered_for(trades, instrument),
            net_flow_decay=self._net_flow_decay_for(trades, ts_utc),
            net_flow_ddoi=self._net_flow_ddoi_for(trades),
            with_exposure_ext=True,
            with_surface=True,
            with_proprietary=True,
            with_iv_smile=True,
        )
        # Publish to Redis FIRST so the live terminal/WS stay healthy even when
        # Timescale is down; the durable write is best-effort and must never undo
        # or prevent the live publish.
        await self._state.set_now(instrument, snapshot)
        try:
            await self._repo.save_snapshot(snapshot)
        except Exception as exc:
            log.warning("save_snapshot failed for %s @ %s: %s", instrument, ts_utc, exc)
        return True

    async def _republish_stale(self, instrument: str, last: Any) -> bool:
        """Hold the last snapshot as ``stale=true`` (FALLBACK only).

        Invoked from the STALE branch of :meth:`_tick_instrument` ONLY when a
        live recovery attempt (``_produce_live``) failed in this tick — i.e.
        the feed is still down. Re-publishes the last stored frame with
        ``stale=true`` and ``state=STALE``; ts/minute_index are intentionally
        left unchanged so the feed-gap delta keeps growing and the session
        stays STALE until the feed recovers. ``set_now`` only — no
        ``save_snapshot`` (replay records only genuinely produced minutes).
        """
        if not isinstance(last, Mapping):
            log.warning("STALE for %s but no last snapshot to hold", instrument)
            return False
        held = dict(last)
        held["stale"] = True
        held["state"] = SessionState.STALE.value
        # NOTE: ts/minute_index are intentionally left unchanged so the feed-gap
        # delta keeps growing and the session stays STALE until the feed
        # recovers. We publish (set_now) but do NOT save_snapshot -- the replay
        # store records only genuinely produced minutes.
        await self._state.set_now(instrument, held)
        return True

    # -- scheduler loop --------------------------------------------------- #
    def stop(self) -> None:
        """Signal :meth:`run` to exit after the current sleep."""
        self._stop.set()

    async def run(self, *, max_ticks: int | None = None) -> int:
        """Run the aligned per-minute loop. Returns the number of ticks executed.

        Aligns to the wall-clock minute boundary (sleeps the remainder of the
        current minute after each tick). ``max_ticks`` bounds the loop for tests
        and one-shot runs; :meth:`stop` requests a graceful exit.
        """
        self._stop.clear()
        ticks = 0
        while not self._stop.is_set():
            now = self._clock()
            try:
                await self.tick(now)
            except Exception:  # never let one bad minute kill the heartbeat
                log.exception("worker tick failed")
            ticks += 1
            if max_ticks is not None and ticks >= max_ticks:
                break
            await self._sleeper(self._seconds_to_next_minute(self._clock()))
        return ticks

    @staticmethod
    def _seconds_to_next_minute(now: datetime) -> float:
        """Seconds remaining until the next wall-clock minute boundary."""
        frac = now.second + now.microsecond / 1_000_000.0
        remaining = 60.0 - frac
        if remaining <= 0.0:
            return 0.0
        return remaining


# --------------------------------------------------------------------------- #
# Production wiring (env-driven). Imported lazily to keep this module offline-  #
# friendly; only used by the real service entrypoint.                          #
# --------------------------------------------------------------------------- #
async def build_worker_from_env() -> MinuteWorker:
    """Construct a :class:`MinuteWorker` from the 12-key env contract.

    Reads ``FEED_MODE``/``DATA_DIR``/``DATABENTO_API_KEY`` (feed),
    ``TIMESCALE_DSN`` (repo), ``REDIS_URL`` (state) and ``SOFR_RATE`` (rate).
    """
    from engine.feed import make_adapter

    from api.state import create_state_store
    from db.repo import SnapshotRepository, create_pool

    feed_mode = os.environ.get("FEED_MODE", "historical").strip().lower()
    armed = os.environ.get("LIVE_FEED_ARMED", "").strip() == "1"
    # Loud boot log so operators can spot a misconfigured live flip in
    # the first line of the worker's stdout. The two-key arming rail is
    # enforced inside make_adapter (see engine/feed/__init__.py).
    log.warning(
        "flowdesk worker boot: feed_mode=%s live_armed=%s "
        "(see docs/architecture/live-feed-threat-model.md)",
        feed_mode, armed,
    )
    feed = make_adapter(
        feed_mode,
        data_dir=os.environ.get("DATA_DIR"),
        api_key=os.environ.get("DATABENTO_API_KEY"),
    )
    pool = await create_pool(os.environ["TIMESCALE_DSN"])
    repo = SnapshotRepository(pool)
    state_store = create_state_store(os.environ["REDIS_URL"])
    sofr = float(os.environ.get("SOFR_RATE", DEFAULT_SOFR_RATE))
    return MinuteWorker(feed=feed, repo=repo, state_store=state_store, sofr_rate=sofr)


async def _amain() -> None:  # pragma: no cover - operational entrypoint
    logging.basicConfig(level=logging.INFO)
    worker = await build_worker_from_env()
    log.info("flowdesk worker starting (instruments=%s)", worker._instruments)
    await worker.run()


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(_amain())
