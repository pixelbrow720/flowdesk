"""LiveBook unit tests — pure assembly, NEVER contact Databento.

Exercises the per-minute chain assembler that the live adapter delegates to:
the DBN wire-format decoders and the OptionChainMinute assembly (0DTE expiry
selection, latest-quote-as-of-ts, cumulative VOL since RTH open, latest OI,
futures-mid / parity forward, signed FLUX trades). Mirrors the semantics proven
in test_historical.py but drives the book with synthetic in-memory records.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from engine.feed.base import OptionChainMinute
from engine.feed.live_book import (
    UNDEF_PRICE,
    LiveBook,
    decode_class,
    decode_px,
    decode_side,
    decode_ts,
    instrument_of,
)


def _ns(dt: datetime) -> int:
    """Epoch nanoseconds for an aware datetime (DBN ts_event encoding)."""
    return int(dt.timestamp() * 1e9)


def _px(value: float) -> int:
    """Fixed-point 1e-9 encoding of a real price (DBN price encoding)."""
    return int(round(value * 1e9))


SESSION = datetime(2026, 6, 9, tzinfo=timezone.utc).date()
# 14:30 UTC = 10:30 ET (EDT) — inside RTH (open 13:30 UTC = 09:30 ET).
TS = datetime(2026, 6, 9, 14, 30, tzinfo=timezone.utc)
RTH_OPEN_UTC = datetime(2026, 6, 9, 13, 30, tzinfo=timezone.utc)
EXPIRY = datetime(2026, 6, 9, 20, 0, tzinfo=timezone.utc)  # 16:00 ET close


# --------------------------------------------------------------------------- #
# Decoders.                                                                    #
# --------------------------------------------------------------------------- #
def test_decode_px_fixed_point() -> None:
    assert decode_px(_px(5800.25)) == pytest.approx(5800.25)


def test_decode_px_undef_sentinel_is_none() -> None:
    assert decode_px(UNDEF_PRICE) is None
    assert decode_px(-UNDEF_PRICE) is None


def test_decode_px_nonpositive_is_none() -> None:
    assert decode_px(0) is None
    assert decode_px(_px(-1.0)) is None


def test_decode_px_float_passthrough() -> None:
    # Already-real floats (test primitives / pretty CSV) are not re-scaled.
    assert decode_px(12.25) == pytest.approx(12.25)
    assert decode_px(0.0) is None


def test_decode_ts_epoch_ns() -> None:
    assert decode_ts(_ns(TS)) == TS


def test_decode_ts_iso_and_datetime() -> None:
    assert decode_ts("2026-06-09T14:30:00Z") == TS
    naive = datetime(2026, 6, 9, 14, 30)
    assert decode_ts(naive) == TS


def test_decode_class() -> None:
    assert decode_class("C") == "call"
    assert decode_class("put") == "put"
    assert decode_class("F") == "future"
    assert decode_class("X") is None


def test_decode_side_default_n() -> None:
    assert decode_side("B") == "B"
    assert decode_side("a") == "A"
    assert decode_side("") == "N"
    assert decode_side("?") == "N"


def test_instrument_of() -> None:
    assert instrument_of("ES", "ESM6") == "ES"
    assert instrument_of("NQ", "NQM6") == "NQ"
    assert instrument_of("E2B", "E2BM6 C5800") == "ES"
    assert instrument_of("Q2B", "Q2BM6 P20000") == "NQ"
    assert instrument_of("", "ESM6") == "ES"
    assert instrument_of("", "???") is None


# --------------------------------------------------------------------------- #
# Assembly: a small ES chain with a future + two strikes.                      #
# --------------------------------------------------------------------------- #
def _seed_basic_chain(book: LiveBook) -> None:
    # Front future.
    book.add_definition(
        1, raw_symbol="ESM6", instrument_class="F", strike=None,
        expiration=_ns(datetime(2026, 6, 19, 13, 30, tzinfo=timezone.utc)), asset="ES",
    )
    # Two 0DTE strikes, call + put each.
    book.add_definition(
        10, raw_symbol="E2BM6 C5800", instrument_class="C", strike=_px(5800.0),
        expiration=_ns(EXPIRY), asset="E2B",
    )
    book.add_definition(
        11, raw_symbol="E2BM6 P5800", instrument_class="P", strike=_px(5800.0),
        expiration=_ns(EXPIRY), asset="E2B",
    )
    book.add_definition(
        20, raw_symbol="E2BM6 C5810", instrument_class="C", strike=_px(5810.0),
        expiration=_ns(EXPIRY), asset="E2B",
    )
    book.add_definition(
        21, raw_symbol="E2BM6 P5810", instrument_class="P", strike=_px(5810.0),
        expiration=_ns(EXPIRY), asset="E2B",
    )
    # Future top-of-book -> forward = mid = 5805.0.
    book.add_quote(1, ts=_ns(TS), bid=_px(5804.0), ask=_px(5806.0))
    # Option quotes.
    book.add_quote(10, ts=_ns(TS), bid=_px(10.0), ask=_px(12.0))
    book.add_quote(11, ts=_ns(TS), bid=_px(8.0), ask=_px(10.0))
    book.add_quote(20, ts=_ns(TS), bid=_px(6.0), ask=_px(8.0))
    book.add_quote(21, ts=_ns(TS), bid=_px(11.0), ask=_px(13.0))
    # OI (statistics, stat_type 9).
    book.add_statistic(10, ts=_ns(TS), stat_type=9, price=None, quantity=500)
    book.add_statistic(11, ts=_ns(TS), stat_type=9, price=None, quantity=300)
    book.add_statistic(20, ts=_ns(TS), stat_type=9, price=None, quantity=700)
    book.add_statistic(21, ts=_ns(TS), stat_type=9, price=None, quantity=200)


def test_get_chain_shape_and_forward() -> None:
    book = LiveBook()
    _seed_basic_chain(book)
    chain = book.get_chain("ES", TS)
    assert isinstance(chain, OptionChainMinute)
    assert chain.ts == TS
    assert chain.forward == pytest.approx(5805.0)  # future mid
    assert chain.strikes() == [5800.0, 5810.0]
    by = chain.by_strike()
    assert by[5800.0]["call"].mid == pytest.approx(11.0)
    assert by[5800.0]["put"].mid == pytest.approx(9.0)
    assert by[5800.0]["call"].oi == 500
    assert by[5810.0]["put"].oi == 200


def test_cumulative_volume_since_rth_open() -> None:
    book = LiveBook()
    _seed_basic_chain(book)
    # Two trades inside RTH, one BEFORE the open (must be excluded).
    pre = datetime(2026, 6, 9, 13, 0, tzinfo=timezone.utc)  # 09:00 ET, pre-open
    t1 = datetime(2026, 6, 9, 13, 45, tzinfo=timezone.utc)
    t2 = datetime(2026, 6, 9, 14, 15, tzinfo=timezone.utc)
    book.add_trade(10, ts=_ns(pre), price=_px(11.0), size=5, side="B")
    book.add_trade(10, ts=_ns(t1), price=_px(11.0), size=3, side="B")
    book.add_trade(10, ts=_ns(t2), price=_px(11.0), size=4, side="A")
    chain = book.get_chain("ES", TS)
    call_5800 = chain.by_strike()[5800.0]["call"]
    assert call_5800.volume == pytest.approx(7.0)  # 3 + 4; pre-open 5 excluded


def test_quote_after_ts_is_ignored() -> None:
    book = LiveBook()
    _seed_basic_chain(book)
    # A newer quote that lands AFTER the requested minute must not be used.
    later = datetime(2026, 6, 9, 14, 45, tzinfo=timezone.utc)
    book.add_quote(10, ts=_ns(later), bid=_px(99.0), ask=_px(101.0))
    chain = book.get_chain("ES", TS)
    # latest as-of TS is the original 10/12 mid (11.0), not the 100 from 14:45.
    assert chain.by_strike()[5800.0]["call"].mid == pytest.approx(11.0)


def test_forward_parity_fallback_without_future_quote() -> None:
    book = LiveBook()
    _seed_basic_chain(book)
    # Drop the future quote so the forward must come from put-call parity.
    book._quotes.pop(1)
    chain = book.get_chain("ES", TS)
    # ATM-ish parity at the tightest |C-P|: strike 5800 (C=11,P=9 -> spread 2)
    # vs 5810 (C=7,P=12 -> spread 5). F = 5800 + (11 - 9) = 5802 (disc ~ 1).
    assert chain.forward == pytest.approx(5802.0, abs=0.05)


def test_get_flux_trades_signed_and_windowed() -> None:
    book = LiveBook()
    _seed_basic_chain(book)
    pre = datetime(2026, 6, 9, 13, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 6, 9, 13, 45, tzinfo=timezone.utc)
    book.add_trade(10, ts=_ns(pre), price=_px(11.0), size=5, side="B")  # excluded
    book.add_trade(10, ts=_ns(t1), price=_px(11.0), size=3, side="B")
    book.add_trade(11, ts=_ns(t1), price=_px(9.0), size=2, side="A")
    flux = book.get_flux_trades("ES", TS)
    assert len(flux) == 2  # pre-open excluded
    by_strike = {(tr.strike, tr.is_call): tr for tr in flux}
    assert by_strike[(5800.0, True)].side == "B"
    assert by_strike[(5800.0, True)].size == 3
    assert by_strike[(5800.0, False)].side == "A"


def test_0dte_expiry_selection_prefers_quoted_legs() -> None:
    """A same-day quarterly contaminant (definition but no quotes) is ignored."""
    book = LiveBook()
    _seed_basic_chain(book)
    # Contaminant: same ET date expiry, but NO quotes/trades.
    contaminant_exp = datetime(2026, 6, 9, 13, 30, tzinfo=timezone.utc)  # AM settle
    book.add_definition(
        99, raw_symbol="ESQ CONT", instrument_class="C", strike=_px(5800.0),
        expiration=_ns(contaminant_exp), asset="E2B",
    )
    chain = book.get_chain("ES", TS)
    # The quoted 16:00 expiry wins -> the contaminant strike is NOT double-counted.
    # 5800 + 5810 = 2 strikes only (the contaminant shares 5800 but maps to the
    # other expiry, which is not selected).
    assert chain.strikes() == [5800.0, 5810.0]


def test_reset_session_clears_volume_keeps_defs() -> None:
    book = LiveBook()
    _seed_basic_chain(book)
    t1 = datetime(2026, 6, 9, 13, 45, tzinfo=timezone.utc)
    book.add_trade(10, ts=_ns(t1), price=_px(11.0), size=3, side="B")
    book.reset_session()
    # Definitions survive a reset; trades/quotes/OI are cleared. Re-seed only the
    # future quote so the forward resolves (proving market state restarted clean).
    book.add_quote(1, ts=_ns(TS), bid=_px(5804.0), ask=_px(5806.0))
    chain = book.get_chain("ES", TS)
    assert chain.strikes() == [5800.0, 5810.0]  # defs kept
    assert chain.by_strike()[5800.0]["call"].volume == 0.0  # trades cleared
    assert chain.by_strike()[5800.0]["call"].oi == 0.0  # OI cleared
    assert chain.by_strike()[5800.0]["call"].mid is None  # option quotes cleared


def test_other_instrument_not_mixed_in() -> None:
    book = LiveBook()
    _seed_basic_chain(book)
    # Add an NQ strike; an ES chain must not include it.
    book.add_definition(
        30, raw_symbol="Q2BM6 C20000", instrument_class="C", strike=_px(20000.0),
        expiration=_ns(EXPIRY), asset="Q2B",
    )
    book.add_quote(30, ts=_ns(TS), bid=_px(50.0), ask=_px(52.0))
    es = book.get_chain("ES", TS)
    assert 20000.0 not in es.strikes()


# --------------------------------------------------------------------------- #
# Regression: bugs found validating against REAL DBN archives (2026-06-18).    #
# --------------------------------------------------------------------------- #
class _Enum:
    """Stand-in for a databento string/int enum: str(x) -> '<Name.X: v>', .value -> v."""

    def __init__(self, name: str, value: object) -> None:
        self._name = name
        self.value = value

    def __str__(self) -> str:  # mimics databento enum repr, NOT the bare value
        return f"<{self._name}: {self.value!r}>"


def test_decode_class_accepts_databento_enum() -> None:
    # Real DBN: instrument_class is <InstrumentClass.PUT: 'P'>, not a bare 'P'.
    assert decode_class(_Enum("InstrumentClass.PUT", "P")) == "put"
    assert decode_class(_Enum("InstrumentClass.CALL", "C")) == "call"
    assert decode_class(_Enum("InstrumentClass.FUTURE", "F")) == "future"


def test_decode_side_accepts_databento_enum() -> None:
    assert decode_side(_Enum("Side.BID", "B")) == "B"
    assert decode_side(_Enum("Side.ASK", "A")) == "A"
    assert decode_side(_Enum("Side.NONE", "N")) == "N"


def test_stat_open_interest_via_enum_is_recorded() -> None:
    """Regression: stat_type arrives as <StatType.OPEN_INTEREST: 9> (enum int).

    The pre-fix code did ``str(x).isdigit()`` which is False for the enum repr,
    so OI was silently never recorded (all walls would read OI=0).
    """
    from engine.feed.live_book import _stat_code, STAT_OPEN_INTEREST

    assert _stat_code(_Enum("StatType.OPEN_INTEREST", 9)) == STAT_OPEN_INTEREST
    book = LiveBook()
    book.add_definition(
        10, raw_symbol="E2BM6 C5800", instrument_class="C", strike=_px(5800.0),
        expiration=_ns(EXPIRY), asset="E2B",
    )
    book.add_definition(
        1, raw_symbol="ESM6", instrument_class="F", strike=None,
        expiration=_ns(datetime(2026, 6, 19, 13, 30, tzinfo=timezone.utc)), asset="ES",
    )
    book.add_quote(1, ts=_ns(TS), bid=_px(5804.0), ask=_px(5806.0))
    book.add_quote(10, ts=_ns(TS), bid=_px(10.0), ask=_px(12.0))
    book.add_statistic(10, ts=_ns(TS), stat_type=_Enum("StatType.OPEN_INTEREST", 9),
                       price=None, quantity=444)
    chain = book.get_chain("ES", TS)
    assert chain.by_strike()[5800.0]["call"].oi == 444


def test_decode_ts_rejects_undef_sentinels() -> None:
    # bbo-1m carries an UNDEF ts_event (uint64 max); int64 max also appears.
    assert decode_ts(2**64 - 1) is None
    assert decode_ts(2**63 - 1) is None
    assert decode_ts(0) is None
    assert decode_ts(-5) is None
    # a real epoch-ns still decodes
    assert decode_ts(_ns(TS)) == TS


def test_quote_with_undef_ts_is_skipped_not_crash() -> None:
    book = LiveBook()
    book.add_definition(
        10, raw_symbol="E2BM6 C5800", instrument_class="C", strike=_px(5800.0),
        expiration=_ns(EXPIRY), asset="E2B",
    )
    # UNDEF ts_event must be skipped silently (no crash, no quote recorded).
    book.add_quote(10, ts=2**64 - 1, bid=_px(10.0), ask=_px(12.0))
    assert 10 not in book._quotes  # the undecodable-ts quote was dropped
    # A subsequent valid quote (e.g. wrapper fell back to ts_recv) registers.
    book.add_quote(10, ts=_ns(TS), bid=_px(10.0), ask=_px(12.0))
    book.add_definition(
        1, raw_symbol="ESM6", instrument_class="F", strike=None,
        expiration=_ns(datetime(2026, 6, 19, 13, 30, tzinfo=timezone.utc)), asset="ES",
    )
    book.add_quote(1, ts=_ns(TS), bid=_px(5804.0), ask=_px(5806.0))
    assert book.get_chain("ES", TS).by_strike()[5800.0]["call"].mid == pytest.approx(11.0)


def test_decode_px_no_float_epsilon() -> None:
    """Regression: int*1e-9 leaks binary epsilon (15000000000*1e-9 != 15.0).

    Strikes must match the pretty-CSV values the historical adapter reads, or the
    two feeds disagree on otherwise-identical strikes.
    """
    assert decode_px(15_000_000_000) == 15.0
    assert decode_px(520_000_000_000_000) == 520000.0
    assert decode_px(5_800_000_000_000) == 5800.0


# --------------------------------------------------------------------------- #
# get_ohlc — front-future 1-minute candle (mirrors HistoricalSimAdapter).      #
# --------------------------------------------------------------------------- #
def _seed_front_future(book: LiveBook) -> None:
    """Register the front future (iid 1) with no trades yet."""
    book.add_definition(
        1, raw_symbol="ESM6", instrument_class="F", strike=None,
        expiration=_ns(datetime(2026, 6, 19, 13, 30, tzinfo=timezone.utc)), asset="ES",
    )


def test_get_ohlc_from_front_future_trades() -> None:
    """OHLC = (first, max, min, last) of front-future trades in [ts, ts+60s)."""
    book = LiveBook()
    _seed_front_future(book)
    # Four prints inside the TS minute, in arrival order.
    book.add_trade(1, ts=_ns(TS), price=_px(5805.0), size=2, side="N")
    book.add_trade(1, ts=_ns(TS.replace(second=10)), price=_px(5808.0), size=1, side="N")
    book.add_trade(1, ts=_ns(TS.replace(second=20)), price=_px(5802.0), size=1, side="N")
    book.add_trade(1, ts=_ns(TS.replace(second=50)), price=_px(5806.0), size=3, side="N")
    ohlc = book.get_ohlc("ES", TS)
    assert ohlc == pytest.approx((5805.0, 5808.0, 5802.0, 5806.0))


def test_get_ohlc_none_when_no_future_trade_in_minute() -> None:
    """None when the front future printed no trade in the minute (never fabricated)."""
    book = LiveBook()
    _seed_front_future(book)
    # A print one minute earlier — outside [ts, ts+60s).
    earlier = datetime(2026, 6, 9, 14, 29, tzinfo=timezone.utc)
    book.add_trade(1, ts=_ns(earlier), price=_px(5805.0), size=2, side="N")
    assert book.get_ohlc("ES", TS) is None


def test_get_ohlc_excludes_next_minute_print() -> None:
    """A print at exactly ts+60s belongs to the NEXT minute (half-open window)."""
    book = LiveBook()
    _seed_front_future(book)
    book.add_trade(1, ts=_ns(TS), price=_px(5805.0), size=2, side="N")
    next_min = datetime(2026, 6, 9, 14, 31, tzinfo=timezone.utc)
    book.add_trade(1, ts=_ns(next_min), price=_px(5999.0), size=2, side="N")
    ohlc = book.get_ohlc("ES", TS)
    assert ohlc == pytest.approx((5805.0, 5805.0, 5805.0, 5805.0))


def test_get_ohlc_none_without_front_future() -> None:
    """None when there is no front future at all (cannot build a candle)."""
    book = LiveBook()
    assert book.get_ohlc("ES", TS) is None

