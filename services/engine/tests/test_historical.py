"""Tests for the feed layer (PRD #8 §8–§9).

Uses a small bundled synthetic Databento-shaped fixture (see gen_fixture.py).
Proves:
  * HistoricalSimAdapter parses the fixture into a well-formed chain;
  * both adapters share the one FeedAdapter interface (AC-A3);
  * the ingest plan is batched (one request per schema, AC-A7);
  * the chain is consumable by the engine (build_snapshot, PRD step 1.3).
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path

import gen_fixture
from engine.feed import make_adapter, to_engine_chain
from engine.feed.base import FeedAdapter, OptionChainMinute
from engine.feed.historical import HistoricalSimAdapter
from engine.feed.live import LiveAdapter, LiveFeedNotAvailable
from engine.snapshot import build_snapshot

DATA_DIR = Path(__file__).resolve().parent / "fixtures" / "raw"
INSTRUMENT = "ES"
# Sample minute: 09:31 ET == 13:31 UTC on the 0DTE session 2026-06-10.
TS = datetime(2026, 6, 10, 13, 31, tzinfo=timezone.utc)
STRIKES = [4990.0, 4995.0, 5000.0, 5005.0, 5010.0]


def _ensure_fixture() -> None:
    if not (DATA_DIR / "definition" / "ES_20260610_20260610.csv").exists():
        gen_fixture.generate()


def _adapter() -> HistoricalSimAdapter:
    _ensure_fixture()
    return HistoricalSimAdapter(DATA_DIR)


def test_get_chain_is_well_formed() -> None:
    chain = _adapter().get_chain(INSTRUMENT, TS)
    assert isinstance(chain, OptionChainMinute)
    assert chain.ts == TS
    assert chain.forward == 5000.0
    assert chain.strikes() == STRIKES
    by_strike = chain.by_strike()
    for k in STRIKES:
        legs = by_strike[k]
        assert set(legs) == {"call", "put"}, f"strike {k} missing a leg"
        for leg in legs.values():
            assert leg.mid is not None and leg.mid > 0
            assert leg.volume > 0
            assert leg.oi > 0


def test_cumulative_volume_excludes_pre_open() -> None:
    # The 5000 call has a pre-open (13:00Z) trade of size 999 that MUST be
    # excluded; only the 13:30:30Z RTH trade (500) counts at 13:31Z.
    chain = _adapter().get_chain(INSTRUMENT, TS)
    call_5000 = chain.by_strike()[5000.0]["call"]
    assert call_5000.volume == 500.0


def test_get_forward_matches_future_mid() -> None:
    assert _adapter().get_forward(INSTRUMENT, TS) == 5000.0


def test_adapters_share_one_interface() -> None:
    hist = make_adapter("historical", data_dir=DATA_DIR)
    live = make_adapter("live")
    assert isinstance(hist, FeedAdapter) and isinstance(hist, HistoricalSimAdapter)
    assert isinstance(live, FeedAdapter) and isinstance(live, LiveAdapter)
    assert hist.mode == "historical" and live.mode == "live"


def test_live_adapter_is_stub() -> None:
    live = LiveAdapter()
    for call in (lambda: live.get_chain(INSTRUMENT, TS), lambda: live.get_forward(INSTRUMENT, TS)):
        try:
            call()
        except LiveFeedNotAvailable:
            continue
        raise AssertionError("LiveAdapter should raise LiveFeedNotAvailable")


def test_unknown_instrument_rejected() -> None:
    try:
        _adapter().get_chain("SPX", TS)
    except ValueError:
        return
    raise AssertionError("unknown instrument should raise ValueError")


def test_ingest_plan_is_batched_one_request_per_schema() -> None:
    import importlib.util
    import sys

    script = Path(__file__).resolve().parents[1] / "scripts" / "ingest_databento.py"
    spec = importlib.util.spec_from_file_location("ingest_databento", script)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # required so frozen dataclasses resolve __module__
    spec.loader.exec_module(mod)

    schemas = ("definition", "statistics", "trades", "mbp-1")
    plan = mod.build_request_plan("2026-06-01", "2026-06-05", schemas=schemas)
    # AC-A7: number of requests == number of schemas (NOT per-day).
    assert len(plan) == len(schemas)
    for spec_item in plan:
        assert spec_item.start == "2026-06-01" and spec_item.end == "2026-06-05"
        assert spec_item.stype_in == "parent"
        assert spec_item.dataset == "GLBX.MDP3"
    assert len(mod.EXTREME_DAYS) >= 2  # 2-3 extreme days noted for the golden set


def test_chain_is_consumable_by_engine() -> None:
    adapter = _adapter()
    chain = adapter.get_chain(INSTRUMENT, TS)

    expiry = adapter.get_expiry(INSTRUMENT, TS)
    assert expiry is not None
    t_expiry = max((expiry - TS).total_seconds(), 0.0) / (365.0 * 24 * 3600)

    quotes = to_engine_chain(chain, t_expiry=t_expiry)
    assert len(quotes) == len(STRIKES)
    assert all(q.call_oi > 0 and q.put_oi > 0 for q in quotes)

    snap = build_snapshot(
        instrument=INSTRUMENT,
        ts_utc=TS,
        chain=quotes,
        forward=chain.forward,
        rate=math.log(1.0531),
        session_state="LIVE",
        axis={"strike_min": 4990, "strike_max": 5010, "step": 5},
    )
    assert snap.schema_version == 1
    assert snap.instrument == "ES"
    assert snap.minute_index == 1
    assert snap.forward == 5000.0
    assert len(snap.profile) == len(STRIKES)
    # OI-based walls must be present and exact relative to the fixture OI.
    assert snap.levels.call_walls[:1] == [5010.0]  # highest call OI above forward
    assert snap.levels.put_walls[:1] == [4990.0]   # highest put OI below forward
    assert snap.regime.sign in (-1, 0, 1)


# --------------------------------------------------------------------------- #
# HIRO signed-trade path (additive; does not disturb TRACE volume prefix-sums).
# --------------------------------------------------------------------------- #
def test_get_hiro_trades_signed_and_priced() -> None:
    from engine.hiro import hiro_series

    adapter = _adapter()
    trades = adapter.get_hiro_trades(INSTRUMENT, TS)
    # 5 calls (side B) + 5 puts (side A) within RTH; the 13:00Z pre-open trade
    # is excluded (HIRO resets at the open).
    assert len(trades) == 10
    assert all(t.t_expiry > 0.0 for t in trades)
    sides = {t.side for t in trades}
    assert sides == {"B", "A"}
    # Calls bought + puts sold => both push dealer hedging the SAME way:
    # buy call (s=+1, d>0) -> +, sell put (s=-1, d<0) -> + . Net positive.
    series = hiro_series(trades, 5000.0, 50.0, math.log(1.0531))
    assert series.final.total > 0.0
    assert series.skipped == 0


def test_get_hiro_trades_excludes_pre_open() -> None:
    adapter = _adapter()
    trades = adapter.get_hiro_trades(INSTRUMENT, TS)
    # The size-999 pre-open call trade must not appear.
    assert all(t.size != 999.0 for t in trades)
