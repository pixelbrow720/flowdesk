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


def test_instrument_of_underlying_rejects_lookalikes() -> None:
    """The settling future (`underlying`) is the reliable discriminator.

    Verified against real GLBX definitions for the 2026-06-26 expiry: micro
    E-mini (asset EX4, underlying MESU6) and Ether options (asset ETH,
    underlying ETHM6) share an `E`-rooted asset and a daily 0DTE expiry. The
    old asset-prefix heuristic mis-tagged both as ES, polluting the ES chain
    with a foreign strike grid. With the underlying they are rejected.
    """
    # Full-size daily 0DTE roots resolve correctly via underlying.
    assert instrument_of("EW4", "EW4M6 C6800", "ESU6") == "ES"
    assert instrument_of("E4D", "E4DM6 C6800", "ESU6") == "ES"
    assert instrument_of("QN4", "QN4M6 C25000", "NQU6") == "NQ"
    assert instrument_of("Q4D", "Q4DM6 C25000", "NQU6") == "NQ"
    # Look-alikes sharing an E-root + same expiry are REJECTED by underlying.
    assert instrument_of("EX4", "EX4M6 C6800", "MESU6") is None  # micro E-mini
    assert instrument_of("ETH", "ETHM6 C2500", "ETHM6") is None  # Ether option
    assert instrument_of("MQ4", "MQ4M6 C25000", "MNQU6") is None  # micro NQ
    # underlying takes precedence over a (would-be ES) asset prefix.
    assert instrument_of("E2B", "E2BM6 C5800", "MESU6") is None


def test_instrument_of_falls_back_without_underlying() -> None:
    """Absent an underlying (some futures defs), the asset/root heuristic stands
    so existing callers/tests that omit it keep working."""
    assert instrument_of("E2B", "E2BM6 C5800") == "ES"
    assert instrument_of("Q2B", "Q2BM6 P20000") == "NQ"
    assert instrument_of("ES", "ESM6", "") == "ES"


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


def test_micro_and_foreign_lookalikes_excluded_from_chain() -> None:
    """A real-data contamination case: micro E-mini (MESU6) and Ether (ETHM6)
    options share an E-root and the same 0DTE expiry as full-size ES. They must
    NOT appear in the ES chain. Reproduces the live-path gap where no upstream
    underlying filter exists (the historical CSV path is pre-filtered).
    """
    book = LiveBook()
    # Front future + a legit full-size ES 0DTE strike (underlying ESU6).
    book.add_definition(
        1, raw_symbol="ESU6", instrument_class="F", strike=None,
        expiration=_ns(datetime(2026, 9, 18, 13, 30, tzinfo=timezone.utc)),
        asset="ES", underlying="ESU6",
    )
    book.add_quote(1, ts=_ns(TS), bid=_px(5804.0), ask=_px(5806.0))
    book.add_definition(
        10, raw_symbol="EW4M6 C5800", instrument_class="C", strike=_px(5800.0),
        expiration=_ns(EXPIRY), asset="EW4", underlying="ESU6",
    )
    book.add_quote(10, ts=_ns(TS), bid=_px(10.0), ask=_px(12.0))
    # Contaminants: same ET expiry date, E-rooted asset, but foreign underlying.
    book.add_definition(
        20, raw_symbol="EX4M6 C5807", instrument_class="C", strike=_px(5807.0),
        expiration=_ns(EXPIRY), asset="EX4", underlying="MESU6",  # micro E-mini
    )
    book.add_quote(20, ts=_ns(TS), bid=_px(2.0), ask=_px(3.0))
    book.add_definition(
        30, raw_symbol="ETHM6 C2500", instrument_class="C", strike=_px(2500.0),
        expiration=_ns(EXPIRY), asset="ETH", underlying="ETHM6",  # Ether option
    )
    book.add_quote(30, ts=_ns(TS), bid=_px(5.0), ask=_px(6.0))
    chain = book.get_chain("ES", TS)
    # Only the full-size ES strike survives; micro 5807 + Ether 2500 are dropped.
    assert chain.strikes() == [5800.0]


def test_no_same_day_expiry_yields_empty_chain_not_wrong_grid() -> None:
    """No same-day 0DTE expiry seeded -> empty option chain (awaiting data),
    NOT a silent fall-back to a far future / quarterly expiry.

    Reproduces the 2026-06-26 live bug: when today's $5 0DTE definitions were
    never seeded, _select_0dte_expiry fell back to ``future[0]`` and emitted the
    WRONG expiry's grid (ES a 4-day-out $5 expiry; NQ a 3-month $250 quarterly).
    For a 0DTE product the only valid expiry is today's; absent it, the chain
    must be empty so the UI shows awaiting-data instead of a wrong grid.
    """
    book = LiveBook()
    # Front future so the forward still resolves (awaiting OPTION data, not forward).
    book.add_definition(
        1, raw_symbol="ESM6", instrument_class="F", strike=None,
        expiration=_ns(datetime(2026, 6, 19, 13, 30, tzinfo=timezone.utc)), asset="ES",
    )
    book.add_quote(1, ts=_ns(TS), bid=_px(5804.0), ask=_px(5806.0))
    # ONLY a far-future expiry (4 trading days out), WITH quotes — mirrors the
    # live ES case where today's 0DTE was never seeded so a future expiry won.
    future_exp = datetime(2026, 6, 30, 20, 0, tzinfo=timezone.utc)
    iid = 100
    for strike in (5800.0, 5805.0, 5810.0):
        book.add_definition(
            iid, raw_symbol=f"E2BM6 C{int(strike)}", instrument_class="C",
            strike=_px(strike), expiration=_ns(future_exp), asset="E2B",
        )
        book.add_quote(iid, ts=_ns(TS), bid=_px(10.0), ask=_px(12.0))
        iid += 1
    # The selector must REFUSE (no same-day expiry), not pick the far expiry.
    assert book._select_0dte_expiry("ES", TS) is None
    # And get_chain must emit no option rows (empty = awaiting data).
    chain = book.get_chain("ES", TS)
    assert chain.strikes() == []


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


# --------------------------------------------------------------------------- #
# describe_definitions — read-only seed diagnostic for the $5-vs-$25 bug.       #
# The decisive question: was the $5 daily-0DTE grid SEEDED, and is it SELECTED, #
# or only a coarse $25 quarterly grid? Encodes the 2026-06-25 diagnosis.        #
# --------------------------------------------------------------------------- #
def _seed_five_dollar_grid(book: LiveBook) -> None:
    """Seed a clean $5 daily-0DTE grid (5800..5820) with quotes, plus a front future."""
    book.add_definition(
        1, raw_symbol="ESM6", instrument_class="F", strike=None,
        expiration=_ns(datetime(2026, 6, 19, 13, 30, tzinfo=timezone.utc)), asset="ES",
    )
    book.add_quote(1, ts=_ns(TS), bid=_px(5804.0), ask=_px(5806.0))  # forward ~5805
    iid = 100
    for strike in (5800.0, 5805.0, 5810.0, 5815.0, 5820.0):
        book.add_definition(
            iid, raw_symbol=f"E2BM6 C{int(strike)}", instrument_class="C",
            strike=_px(strike), expiration=_ns(EXPIRY), asset="E2B",
        )
        book.add_quote(iid, ts=_ns(TS), bid=_px(10.0), ask=_px(12.0))
        iid += 1


def test_describe_definitions_reports_five_dollar_spacing_and_selected() -> None:
    """A seeded $5 daily grid is reported with $5 spacing and flagged SELECTED."""
    book = LiveBook()
    _seed_five_dollar_grid(book)
    out = book.describe_definitions("ES", TS)
    # Header names the instrument and the expiry the book WOULD select.
    assert "[live-diag] ES" in out
    assert "selected_expiry=2026-06-09" in out
    # The same-day $5 expiry line shows 5.0 spacing, has quotes, and is SELECTED.
    line = next(ln for ln in out.splitlines() if "exp 2026-06-09" in ln)
    assert "same_day=True" in line
    assert "(5.0," in line  # near-money spacing mode is $5
    assert "quoted_legs=5" in line
    assert "<-- SELECTED" in line


def test_describe_definitions_exposes_quarterly_contaminant_spacing() -> None:
    """A $25 quarterly grid on a DIFFERENT expiry is reported with $25 spacing.

    This is the diagnostic tell for the live bug: when the $5 daily grid is NOT
    seeded, only the coarse $25 expiry remains and the chain falls back to it.
    """
    book = LiveBook()
    _seed_five_dollar_grid(book)
    # A later quarterly expiry, $25 grid, NO quotes (definition-only contaminant).
    quarterly_exp = datetime(2026, 6, 19, 20, 0, tzinfo=timezone.utc)
    iid = 200
    for strike in (5775.0, 5800.0, 5825.0, 5850.0):
        book.add_definition(
            iid, raw_symbol=f"ESM6 C{int(strike)}", instrument_class="C",
            strike=_px(strike), expiration=_ns(quarterly_exp), asset="ES",
        )
        iid += 1
    out = book.describe_definitions("ES", TS)
    q_line = next(ln for ln in out.splitlines() if "exp 2026-06-19" in ln)
    assert "same_day=False" in q_line
    assert "(25.0," in q_line  # quarterly $25 spacing tell
    assert "quoted_legs=0" in q_line
    assert "<-- SELECTED" not in q_line  # the quoted same-day $5 grid wins
    # And the same-day $5 grid is still the SELECTED one.
    daily_line = next(ln for ln in out.splitlines() if "exp 2026-06-09" in ln)
    assert "<-- SELECTED" in daily_line


def test_describe_definitions_empty_book_is_safe() -> None:
    """No definitions -> a header with zero legs and no selected expiry (no crash)."""
    book = LiveBook()
    out = book.describe_definitions("ES", TS)
    assert "total_opt_legs=0" in out
    assert "selected_expiry=None" in out

