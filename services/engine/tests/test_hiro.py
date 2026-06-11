"""Tests for engine.hiro (HIRO delta-notional flow accumulator).

HIRO is an ISOLATED flow module: it does not touch the Snapshot contract. These
tests pin the core formula (s · δ · q · M · F), the aggressor sign map, the
breakdown lines, and the cumulative path — all priced with the same Black-76 /
IV core as the rest of the engine.
"""

from __future__ import annotations

import math

from engine.black76 import delta as bs_delta
from engine.black76 import price as bs_price
from engine.hiro import (
    HiroState,
    HiroTrade,
    aggressor_sign,
    hiro_series,
    signed_delta_notional,
)

RATE = math.log(1.0517)
M_ES = 50.0
F = 5000.0
T = 0.02


def _priced(strike: float, is_call: bool, side: str, size: float, iv: float, t: float = T) -> HiroTrade:
    """A trade whose price is consistent with `iv` so the IV solve round-trips."""
    otype = "call" if is_call else "put"
    px = bs_price(otype, F, strike, t, RATE, iv)
    return HiroTrade(strike=strike, is_call=is_call, price=px, size=size, side=side, t_expiry=t)


# --------------------------------------------------------------------------- #
# Aggressor sign map
# --------------------------------------------------------------------------- #
def test_aggressor_sign() -> None:
    assert aggressor_sign("B") == 1
    assert aggressor_sign("A") == -1
    assert aggressor_sign("N") == 0
    assert aggressor_sign(" b ") == 1     # case/space-insensitive
    assert aggressor_sign("x") == 0       # unknown -> neutral


# --------------------------------------------------------------------------- #
# Core formula: signed_delta_notional == s * delta * q * M * F
# --------------------------------------------------------------------------- #
def test_signed_delta_notional_matches_formula() -> None:
    iv = 0.21
    tr = _priced(5000.0, True, "B", 10.0, iv)
    dn = signed_delta_notional(tr, F, M_ES, RATE)
    assert dn is not None
    d = bs_delta("call", F, 5000.0, T, RATE, iv)
    assert math.isclose(dn, 1.0 * d * 10.0 * M_ES * F, rel_tol=1e-6)


def test_buy_call_positive_sell_call_negative() -> None:
    # Buy call (s=+1, delta>0) -> dealer buys underlying -> +; sell call -> -.
    buy = signed_delta_notional(_priced(5000.0, True, "B", 10.0, 0.21), F, M_ES, RATE)
    sell = signed_delta_notional(_priced(5000.0, True, "A", 10.0, 0.21), F, M_ES, RATE)
    assert buy is not None and sell is not None
    assert buy > 0.0 and sell < 0.0
    assert math.isclose(buy, -sell, rel_tol=1e-9)


def test_buy_put_negative() -> None:
    # Buy put (s=+1, delta<0) -> dealer sells underlying -> negative flow.
    dn = signed_delta_notional(_priced(5000.0, False, "B", 10.0, 0.21), F, M_ES, RATE)
    assert dn is not None and dn < 0.0


def test_neutral_side_returns_none() -> None:
    assert signed_delta_notional(_priced(5000.0, True, "N", 10.0, 0.21), F, M_ES, RATE) is None


def test_unsolvable_iv_returns_none() -> None:
    # Price above the no-arbitrage upper bound -> IV unsolvable -> None.
    bad = HiroTrade(strike=5000.0, is_call=True, price=F * 2.0, size=10.0, side="B", t_expiry=T)
    assert signed_delta_notional(bad, F, M_ES, RATE) is None


def test_explicit_iv_skips_solve() -> None:
    # Even with a nonsense price, an explicit IV is used directly.
    tr = HiroTrade(strike=5000.0, is_call=True, price=-1.0, size=10.0, side="B", t_expiry=T, iv=0.21)
    dn = signed_delta_notional(tr, F, M_ES, RATE)
    assert dn is not None
    d = bs_delta("call", F, 5000.0, T, RATE, 0.21)
    assert math.isclose(dn, d * 10.0 * M_ES * F, rel_tol=1e-12)


# --------------------------------------------------------------------------- #
# Accumulator + breakdown
# --------------------------------------------------------------------------- #
def test_state_breakdown_and_cumulative() -> None:
    trades = [
        _priced(5000.0, True, "B", 10.0, 0.21),    # +calls
        _priced(5010.0, False, "B", 8.0, 0.22),    # -puts (buy put)
        _priced(4990.0, True, "A", 3.0, 0.23),     # -calls (sell call), retail (size<=5)
        _priced(5000.0, True, "N", 100.0, 0.21),   # neutral -> skipped
    ]
    series = hiro_series(trades, F, M_ES, RATE)
    assert series.skipped == 1
    # cumulative has one entry per trade (neutral logs the unchanged running total)
    assert len(series.cumulative) == 4
    # total == calls + puts (every accepted trade is one or the other)
    s = series.final
    assert math.isclose(s.total, s.calls + s.puts, rel_tol=1e-9)
    # the size-3 sell-call is the only retail-sized accepted trade -> retail < 0
    assert s.retail < 0.0
    # last cumulative equals final total
    assert math.isclose(series.cumulative[-1], s.total, rel_tol=1e-12)


def test_zerodte_breakdown() -> None:
    # T < 1/365 counts toward the 0DTE line; a longer-dated trade does not.
    st = HiroState(M_ES)
    st.add(_priced(5000.0, True, "B", 10.0, 0.21, t=0.5 / 365.0), F, RATE)  # 0DTE
    st.add(_priced(5000.0, True, "B", 10.0, 0.21, t=10.0 / 365.0), F, RATE)  # not 0DTE
    snap = st.snapshot()
    assert snap.zerodte > 0.0
    assert snap.zerodte < snap.total  # only the first trade is in the 0DTE line


def test_empty_series() -> None:
    series = hiro_series([], F, M_ES, RATE)
    assert series.final.total == 0.0
    assert series.cumulative == []
    assert series.skipped == 0
