"""FLUX worker <-> generator parity (Phase 2 Item 3 commit 4).

The locked claim from ``docs/architecture/flux-unification.md``:

    For any RTH session, the api-layer ``MinuteWorker`` and the offline
    ``gen_session_snapshots.py`` generator produce IDENTICAL cumulative FLUX
    values when fed the same trade tape.

This test drives a multi-minute session and proves it. The oracle is a
direct re-implementation of the generator's loop (``FluxState`` with
suffix-feed semantics, see ``gen_session_snapshots.py:75-112``), running
inside the test process so we don't need a fixture data dir.

Equality is asserted on the *cumulative* line minute-by-minute (the
contract that matters for the FE chart).
"""
from __future__ import annotations

import asyncio
import math
from datetime import datetime, timedelta

from engine.black76 import price as bs_price
from engine.feed.base import ChainRow, OptionChainMinute
from engine.flux import FluxState, FluxTrade
from engine.snapshot import MULTIPLIER

from api.session import ET, StaticCMECalendar
from api.worker import MinuteWorker

RATE = math.log(1.0 + 0.0531)
T_EXPIRY = 0.5 / 365.0


def _make_chain(forward: float) -> OptionChainMinute:
    rows: list[ChainRow] = []
    for strike in (4980.0, 4990.0, 5000.0, 5010.0, 5020.0):
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
    # ts is set by caller (per-minute); placeholder here.
    return OptionChainMinute(ts=datetime(2026, 6, 10), forward=forward, rows=tuple(rows))


# Six minutes of varying trade flow + slowly drifting forward. Forward CHANGES
# minute to minute so the parity test actually exercises the freeze-at-arrival
# semantics — a constant forward could not distinguish the persistent path
# from the (broken) re-price-the-whole-day path.
SCRIPT: list[tuple[float, list[FluxTrade]]] = [
    # (forward at this minute, NEW trades arriving this minute)
    (5000.0, [
        FluxTrade(strike=5000.0, is_call=True, price=10.0, size=10.0, side="B",
                  t_expiry=T_EXPIRY, iv=0.21),
        FluxTrade(strike=4990.0, is_call=False, price=8.0, size=4.0, side="B",
                  t_expiry=T_EXPIRY, iv=0.22),
    ]),
    (5005.0, [
        FluxTrade(strike=5010.0, is_call=True, price=7.0, size=2.0, side="A",
                  t_expiry=T_EXPIRY, iv=0.21),
    ]),
    (5012.0, []),                                    # zero-trade minute
    (5008.0, [
        FluxTrade(strike=5000.0, is_call=False, price=9.0, size=20.0, side="B",
                  t_expiry=T_EXPIRY, iv=0.21),
        FluxTrade(strike=5020.0, is_call=True, price=4.0, size=5.0, side="B",
                  t_expiry=T_EXPIRY, iv=0.21),
        FluxTrade(strike=5020.0, is_call=True, price=4.0, size=3.0, side="N",
                  t_expiry=T_EXPIRY, iv=0.21),  # neutral
    ]),
    (5015.0, []),                                    # another zero-trade minute
    (5020.0, [
        FluxTrade(strike=5010.0, is_call=False, price=2.0, size=8.0, side="A",
                  t_expiry=T_EXPIRY, iv=0.21),
    ]),
]


def _generator_oracle(instrument: str) -> list[float]:
    """Re-implements ``gen_session_snapshots.py:75-112`` in-process.

    Drives a fresh ``FluxState`` over the SCRIPT, suffix-feeding only the new
    trades each minute at that minute's forward. Returns the running
    ``snapshot().total`` after each minute — the line a generator-produced
    fixture file would carry.
    """
    state = FluxState(MULTIPLIER[instrument])
    cumulative_tape: list[FluxTrade] = []  # the [open, ts] window at each step
    consumed = 0
    out: list[float] = []
    for forward, new_trades in SCRIPT:
        cumulative_tape.extend(new_trades)
        for tr in cumulative_tape[consumed:]:
            state.add(tr, forward, RATE)
        consumed = len(cumulative_tape)
        out.append(state.snapshot().total)
    return out


class ScriptedFeed:
    """Feed adapter that walks the SCRIPT minute by minute.

    Each ``get_chain`` / ``get_flux_trades`` call consumes the next minute's
    entry. The tape returned by ``get_flux_trades`` is the cumulative
    [open, ts] window — same shape as the historical adapter.
    """

    def __init__(self) -> None:
        self._minute = 0
        self._tape: list[FluxTrade] = []

    def _advance(self) -> tuple[float, list[FluxTrade]]:
        forward, new = SCRIPT[self._minute]
        self._tape.extend(new)
        return forward, list(self._tape)

    def get_chain(self, instrument: str, ts: datetime) -> OptionChainMinute:
        forward, _ = SCRIPT[self._minute]
        return _make_chain(forward)

    def get_flux_trades(self, instrument: str, ts: datetime) -> list[FluxTrade]:
        _, tape = self._advance()
        # advance the cursor AFTER both get_chain + get_flux_trades have been
        # served for this minute — the worker calls get_chain first.
        self._minute += 1
        return tape


class FakeRepo:
    async def save_snapshot(self, snapshot: object) -> None:
        pass


class FakeStateForParity:
    """Empty StateStore — no Tier-1 seed; we want a fresh accumulator path."""

    def __init__(self) -> None:
        self._published: dict[str, dict] = {}
        self.published_totals: list[float] = []
        self.sessions: dict[str, str] = {}

    async def get_now(self, instrument: str):
        return self._published.get(instrument)

    async def set_now(self, instrument: str, snapshot) -> str:
        if hasattr(snapshot, "model_dump"):
            payload = snapshot.model_dump(mode="json")
        else:
            payload = dict(snapshot)
        self._published[instrument] = payload
        # The worker ships the FLUX scalar inside payload["flux"]["total"]
        # (FluxSnapshot.to_dict() shape, see engine.flux).
        flux = payload.get("flux")
        if flux is not None:
            self.published_totals.append(float(flux["total"]))
        return ""

    async def set_session(self, instrument: str, state: str) -> None:
        self.sessions[instrument] = state

    async def set_flux_state(self, instrument: str, payload) -> None:
        pass

    async def get_flux_state(self, instrument: str):
        return None


def test_worker_hiro_matches_generator_minute_by_minute() -> None:
    """The cumulative FLUX line must be IDENTICAL on both paths."""
    instrument = "ES"
    feed, repo, state = ScriptedFeed(), FakeRepo(), FakeStateForParity()
    cal = StaticCMECalendar()
    open_et = datetime(2026, 6, 10, 9, 31, tzinfo=ET)

    worker = MinuteWorker(
        feed=feed, repo=repo, state_store=state, instruments=(instrument,),
        calendar=cal, clock=lambda: open_et, sofr_rate=0.0531, t_expiry=T_EXPIRY,
    )

    # Drive one tick per minute (clock rebound each iteration).
    for i in range(len(SCRIPT)):
        now = open_et + timedelta(minutes=i)
        worker._clock = lambda now=now: now
        asyncio.run(worker.tick(now))

    oracle = _generator_oracle(instrument)
    worker_line = state.published_totals

    assert len(worker_line) == len(oracle), (
        f"worker shipped {len(worker_line)} FLUX frames, oracle expected {len(oracle)}"
    )
    for i, (w, o) in enumerate(zip(worker_line, oracle, strict=False)):
        assert abs(w - o) < 1e-9, (
            f"PARITY BROKEN at minute {i}: worker={w!r} != generator={o!r} "
            f"(diff={w - o!r})"
        )


def test_parity_oracle_actually_grows() -> None:
    """Sanity: the oracle line is non-trivial (not all zeros)."""
    line = _generator_oracle("ES")
    assert any(abs(v) > 1.0 for v in line), "oracle line should grow with the script"
    # Zero-trade minutes must NOT change the value (freeze-at-arrival).
    assert line[1] == line[2] is False or line[1] != line[2] or line[2] == line[1]
    # The minute after a zero-trade minute must equal the previous (no flow).
    assert line[2] == line[1], (
        "minute 2 had no new trades -> cumulative must hold flat (freeze-at-arrival)"
    )
    assert line[4] == line[3], (
        "minute 4 had no new trades -> cumulative must hold flat (freeze-at-arrival)"
    )
