"""Unit tests for analysis.harness.flux_eval — the PREDICTIVE FLUX eval core.

These LOCK the behaviour of the look-ahead-free t->t+k FLUX discriminator against
the agreed spec. They are PURE and deterministic: every EvalTrade list and every
``minute_forwards`` array is hand-built with chosen values, and every expected
number is computed by hand in the comments. No databento, no disk — only the math
plus the locked engine pricing core (``engine.flux`` / ``engine.black76`` /
``engine.iv``) the runner also uses.

WHY THIS FILE EXISTS — the load-bearing concern: the real-data run produced a NULL
(FLUX shows no directional edge over the shuffled control, hit-rate ~0.50). A null
is only trustworthy if the harness can be PROVEN to DETECT a signal when one
genuinely exists. A metric that returns ~0.5 regardless of input would manufacture
a false null and is worthless. The single most important test here is therefore the
POSITIVE CONTROL (``test_positive_control_metric_is_alive``): a PLANTED perfect
signal must drive ``lead_lag_sign_agreement`` to ~1.0, and a PLANTED anti-signal to
~0.0. A metric that can hit both extremes on planted data is ALIVE; one stuck near
0.5 is broken — and that is exactly what makes the real-data ~0.50 a trustworthy
null rather than a dead-harness artefact.

Style mirrors test_ddoi_divergence.py / test_provenance.py: namespace import (no
__init__.py), no test classes, ``-> None`` functions, run via the repo-root .venv
python. Importing ``analysis.harness.flux_eval`` first puts the engine ``src`` on
``sys.path`` (its import side-effect), so the subsequent ``engine.flux`` import
resolves without extra path wiring.
"""
from __future__ import annotations

from collections import Counter

import pytest

from analysis.harness.flux_eval import (
    EvalTrade,
    contemporaneous_sign_agreement,
    lead_lag_sign_agreement,
    per_minute_hiro,
    shuffle_signs,
    signed_volume_series,
)

# flux_eval's import added the engine src to sys.path; this now resolves.
from engine.flux import FluxTrade, aggressor_sign  # noqa: E402

# Instrument multiplier (/ES = 50) and a flat zero rate keep the hand arithmetic
# clean. The exact greek MAGNITUDE never enters a sign test; only that the trade
# PRICES (IV solves) and that a call's delta is > 0, a put's < 0.
M = 50.0
RATE = 0.0
# A modest tenor (~a week) so the Black-76 IV solve is rock-solid for every
# fixture forward; nothing here depends on the 0DTE day-count, only on solvability.
T = 0.02


def _trade(
    minute: int,
    side: str,
    *,
    is_call: bool = True,
    strike: float = 5000.0,
    price: float = 50.0,
    size: float = 1.0,
    t_expiry: float = T,
) -> EvalTrade:
    """A single EvalTrade. Default = an ~ATM /ES call priced well inside the
    no-arb band (lower=disc·max(F-K,0), upper=disc·F) for any forward near 5000,
    so :func:`engine.flux.signed_delta_notional` always solves an IV and returns a
    non-None increment whose SIGN equals the aggressor sign (call δ > 0)."""
    return EvalTrade(
        minute,
        FluxTrade(
            strike=strike,
            is_call=is_call,
            price=price,
            size=size,
            side=side,
            t_expiry=t_expiry,
        ),
    )


# --------------------------------------------------------------------------- #
# 1. POSITIVE CONTROL — THE load-bearing test.
#
# Plant a PERFECT lead: at minute t put a single ~ATM call whose aggressor side
# makes sign(delta_hiro_t) equal sign(F_{t+1}-F_t). Then the metric MUST read
# ~1.0. Flip every side -> a PERFECT anti-lead -> the metric MUST read ~0.0. A
# metric that reaches BOTH 1.0 and 0.0 on planted data is ALIVE (it is not a
# coin-flip stuck at 0.5); this is what makes the real-data ~0.50 a real null and
# not a dead-harness artefact.
#
# call + side "B" => s=+1, δ>0 => increment > 0  (delta_hiro_t > 0)
# call + side "A" => s=-1, δ>0 => increment < 0  (delta_hiro_t < 0)
# --------------------------------------------------------------------------- #
def test_positive_control_metric_is_alive() -> None:
    k = 1
    # Forwards wiggle ±1 around 5000 so K=5000 calls stay ~ATM and price at every
    # minute (intrinsic <= 1 << premium 50). length n=7 -> 6 scored minutes (t6's
    # t+1 is OOB).
    fwd = [5000.0, 5001.0, 5000.0, 5001.0, 5000.0, 5001.0, 5000.0]
    # forward returns F_{t+1}-F_t for t=0..5 (t6 OOB):
    #   +1, -1, +1, -1, +1, -1
    # PLANT a perfect lead: side "B" where return>0, "A" where return<0.
    pos_sides = ["B", "A", "B", "A", "B", "A", "B"]  # t6 side irrelevant (OOB)
    pos_trades = [_trade(t, s) for t, s in enumerate(pos_sides)]

    pm = per_minute_hiro(pos_trades, fwd, M, RATE)
    # every trade must have priced — otherwise a silent skip would zero a delta
    # and quietly drag the hit-rate down (make the 1.0 below load-bearing).
    assert pm["n_used"] == 7
    assert pm["n_iv_skip"] == 0 and pm["n_neutral"] == 0 and pm["n_no_forward"] == 0
    # delta signs are exactly the planted aggressor signs (call δ>0 => sign = s).
    assert [1 if d > 0 else (-1 if d < 0 else 0) for d in pm["delta"]] == [
        1, -1, 1, -1, 1, -1, 1
    ]

    score = lead_lag_sign_agreement(pm["delta"], fwd, k)
    # all 6 scored minutes are hits by construction.
    assert score["n"] == 6
    assert score["hits"] == 6
    assert score["hit_rate"] == pytest.approx(1.0, abs=1e-12)

    # ANTI-correlated: flip every side -> sign(delta_hiro_t) == -sign(return).
    anti_sides = ["A", "B", "A", "B", "A", "B", "A"]
    anti_trades = [_trade(t, s) for t, s in enumerate(anti_sides)]
    apm = per_minute_hiro(anti_trades, fwd, M, RATE)
    assert apm["n_used"] == 7
    anti = lead_lag_sign_agreement(apm["delta"], fwd, k)
    assert anti["n"] == 6
    assert anti["hits"] == 0
    assert anti["hit_rate"] == pytest.approx(0.0, abs=1e-12)

    # ALIVE: the planted-signal span is the full [0,1], not a dead band at 0.5.
    assert score["hit_rate"] - anti["hit_rate"] == pytest.approx(1.0, abs=1e-12)


# --------------------------------------------------------------------------- #
# 2. lead_lag_sign_agreement — exact hit/n/hits + the three skip semantics.
#
# Drive the metric with SYNTHETIC predictor + forward arrays (it decouples the
# two), so every score is hand-computable. Exercises, on DISTINCT minutes:
#   * a predictor-zero minute  -> skipped (no directional call),
#   * an outcome-zero minute    -> skipped (no realized direction),
#   * a tail minute where t+k is OOB -> skipped.
# --------------------------------------------------------------------------- #
def test_lead_lag_exact_counts_and_skip_semantics() -> None:
    k = 1
    #            idx: 0     1     2     3     4     5     6
    fwd =           [100.0, 101.0, 101.0, 100.0, 102.0, 100.0, 100.0]
    # future return F_{t+1}-F_t:
    #   t0:+1  t1:0(skip-out)  t2:-1  t3:+2  t4:-2  t5:0(skip-out)  t6:OOB(skip)
    pred =          [+5.0,  +4.0,  +2.0,  -3.0,  +1.0,   0.0,  +9.0]
    # scoring:
    #   t0: pred+ , out+1  -> HIT
    #   t1: pred+ , out 0  -> SKIP (outcome zero, predictor nonzero)
    #   t2: pred+ , out-1  -> MISS
    #   t3: pred- , out+2  -> MISS
    #   t4: pred+ , out-2  -> MISS
    #   t5: pred 0         -> SKIP (predictor zero)
    #   t6: out OOB        -> SKIP (t+k past end)
    # => scored = {t0,t2,t3,t4} = 4 ; hits = {t0} = 1 ; hit_rate = 1/4 = 0.25
    out = lead_lag_sign_agreement(pred, fwd, k)
    assert out["n"] == 4
    assert out["hits"] == 1
    assert out["hit_rate"] == pytest.approx(0.25, abs=1e-12)


# --------------------------------------------------------------------------- #
# 3. LOOK-AHEAD GUARD (behavioural) — the strongest anti-leak lock.
#
# per_minute_hiro prices each trade at the FROZEN forward of its OWN minute, so
# delta[t] depends ONLY on minute_forwards[<=t]. Build two forward series that
# agree on [0..3] and DIFFER on [4..]; mutating those FUTURE forwards must leave
# delta[:4] and cumulative[:4] byte-for-byte unchanged. (And the mutation must
# actually bite downstream, else the test is vacuous.)
# --------------------------------------------------------------------------- #
def test_look_ahead_guard_future_forwards_do_not_touch_past() -> None:
    n = 6
    split = 3  # forwards agree on [0..split], differ on [split+1..]
    # one priced ~ATM call per minute so every delta[:4] is genuinely non-zero.
    trades = [_trade(t, "B") for t in range(n)]

    fwd_a = [5000.0, 5000.0, 5000.0, 5000.0, 5000.0, 5000.0]
    # identical up to & including index 3, then DIVERGE at 4 and 5:
    fwd_b = [5000.0, 5000.0, 5000.0, 5000.0, 5050.0, 4950.0]

    pa = per_minute_hiro(trades, fwd_a, M, RATE)
    pb = per_minute_hiro(trades, fwd_b, M, RATE)

    # past (<= split) is UNTOUCHED by future-forward mutation...
    assert pa["delta"][: split + 1] == pb["delta"][: split + 1]
    assert pa["cumulative"][: split + 1] == pb["cumulative"][: split + 1]
    # ...and those past deltas are actually non-zero (not a vacuous 0==0 match).
    assert all(d != 0.0 for d in pa["delta"][: split + 1])
    # ...while the mutation DID bite at/after the divergence (proves the inputs
    # really differ; F enters the notional, so delta[4] must change).
    assert pa["delta"][split + 1] != pb["delta"][split + 1]
    assert pa["cumulative"][split + 1] != pb["cumulative"][split + 1]


# --------------------------------------------------------------------------- #
# 4. contemporaneous vs predictive — the gap separates LEAD from LAG.
#
# Plant a predictor that = sign(PAST move) at every minute: it COINCIDES with the
# move that already happened but carries no forward information. The
# contemporaneous arm must then read ~1.0 while the predictive arm reads ~chance,
# so predictive_minus_contemp is a clean, exact -0.5.
#
# moves d_t = F_{t+1}-F_t = [+1,+1,+1,+1,-1,+1,-1] (between 8 forwards).
# predictor[t] = sign(d_{t-1}) (the realized PAST move), predictor[0]=0.
#   contemp hit at t  <=> sign(pred_t)==sign(d_{t-1})  -> TRUE for all by build.
#   lead    hit at t  <=> sign(pred_t)==sign(d_t)      -> momentum continuation.
# the d-sequence has exactly 3 continuations and 3 reversals over t=1..6.
# --------------------------------------------------------------------------- #
def test_contemporaneous_high_predictive_chance() -> None:
    k = 1
    #            idx: 0     1     2     3     4     5     6     7
    fwd =           [100.0, 101.0, 102.0, 103.0, 104.0, 103.0, 104.0, 103.0]
    # moves d0..d6:  +1    +1    +1    +1    -1    +1    -1
    pred =          [0.0,  +1.0, +1.0, +1.0, +1.0, -1.0, +1.0, -1.0]
    #               (pred[t] = sign(d_{t-1}); pred[0]=0 -> skipped both arms)

    # CONTEMP: pred_t vs PAST return F_t - F_{t-1} (= d_{t-1}):
    #   t1..t7 each: pred == sign(past) -> all HIT ; t0 past OOB -> skip
    #   => n=7, hits=7, hit_rate=1.0
    contemp = contemporaneous_sign_agreement(pred, fwd, k)
    assert contemp["n"] == 7
    assert contemp["hits"] == 7
    assert contemp["hit_rate"] == pytest.approx(1.0, abs=1e-12)

    # LEAD: pred_t vs FUTURE return F_{t+1}-F_t (= d_t):
    #   t0: pred 0 -> skip
    #   t1: pred+ d1+ HIT   t2: pred+ d2+ HIT   t3: pred+ d3+ HIT
    #   t4: pred+ d4- MISS  t5: pred- d5+ MISS  t6: pred+ d6- MISS
    #   t7: future OOB -> skip
    #   => n=6, hits=3, hit_rate=0.5  (pure chance — the predictor does NOT lead)
    lead = lead_lag_sign_agreement(pred, fwd, k)
    assert lead["n"] == 6
    assert lead["hits"] == 3
    assert lead["hit_rate"] == pytest.approx(0.5, abs=1e-12)

    # the gap is what isolates lead from lag: clearly negative here (-0.5).
    assert lead["hit_rate"] - contemp["hit_rate"] == pytest.approx(-0.5, abs=1e-12)


# --------------------------------------------------------------------------- #
# 5. shuffle_signs — the valid directional null.
#
# A valid directional-null must DESTROY direction while PRESERVING magnitude &
# timing: the per-trade (minute,size,strike,is_call) are untouched and only the
# aggressor SIGN is permuted, so the day's sign MULTISET (count of B/A/N) is
# invariant. It must also be deterministic per seed.
# --------------------------------------------------------------------------- #
def test_shuffle_preserves_sign_multiset_and_metadata() -> None:
    sides = ["B", "A", "B", "N", "A", "B", "A", "N"]  # signs: 3×+1, 3×-1, 2×0
    trades = [
        _trade(i, s, is_call=(i % 2 == 0), strike=5000.0 + 10 * i, size=1.0 + i)
        for i, s in enumerate(sides)
    ]

    seed = 20260612
    shuffled = shuffle_signs(trades, seed)

    # same length, paired position-for-position.
    assert len(shuffled) == len(trades)

    # SIGN MULTISET INVARIANCE — the load-bearing property of a directional null.
    in_signs = Counter(aggressor_sign(t.trade.side) for t in trades)
    out_signs = Counter(aggressor_sign(t.trade.side) for t in shuffled)
    assert out_signs == in_signs
    assert in_signs == Counter({1: 3, -1: 3, 0: 2})  # the planted multiset

    # MAGNITUDE/TIMING PRESERVED per trade: only `side` may change.
    for orig, sh in zip(trades, shuffled):
        assert sh.minute == orig.minute
        assert sh.trade.size == orig.trade.size
        assert sh.trade.strike == orig.trade.strike
        assert sh.trade.is_call == orig.trade.is_call
        assert sh.trade.price == orig.trade.price
        assert sh.trade.t_expiry == orig.trade.t_expiry


def test_shuffle_is_deterministic_per_seed_and_varies_across_seeds() -> None:
    sides = ["B", "A", "B", "N", "A", "B", "A", "N"]
    trades = [_trade(i, s) for i, s in enumerate(sides)]

    # same seed -> byte-identical side sequence (reproducible).
    a = [t.trade.side for t in shuffle_signs(trades, 20260612)]
    b = [t.trade.side for t in shuffle_signs(trades, 20260612)]
    assert a == b

    # different seeds -> generally different permutations (not a constant map).
    seed_variants = {
        tuple(t.trade.side for t in shuffle_signs(trades, sd))
        for sd in (20260612, 20260613, 20260614, 1, 7)
    }
    assert len(seed_variants) > 1


# --------------------------------------------------------------------------- #
# 6. per_minute_hiro — accounting + cumulative = running sum of delta.
#
# A tiny tape mixing: one priced call (n_used), one trade in a None-forward minute
# (n_no_forward), one neutral N trade (n_neutral), one below-intrinsic call whose
# IV cannot solve (n_iv_skip). Each skipped class contributes EXACTLY 0 to its
# minute, and cumulative is the prefix sum of delta.
# --------------------------------------------------------------------------- #
def test_per_minute_hiro_accounting_and_cumulative() -> None:
    #                   m0      m1     m2      m3      m4
    minute_forwards = [5000.0, None, 5000.0, 5000.0, 5000.0]
    trades = [
        _trade(0, "B"),                                   # m0: prices -> n_used
        _trade(1, "B"),                                   # m1: forward None -> n_no_forward
        _trade(2, "N"),                                   # m2: neutral -> n_neutral
        _trade(3, "B", strike=4000.0, price=10.0),        # m3: deep-ITM call, mid 10
        #   < intrinsic disc·(F-K)=1000 -> IV unsolvable -> n_iv_skip
    ]
    pm = per_minute_hiro(trades, minute_forwards, M, RATE)

    # exact accounting (every trade has a valid minute -> n_trades counts all 4).
    assert pm["n_trades"] == 4
    assert pm["n_used"] == 1
    assert pm["n_no_forward"] == 1
    assert pm["n_neutral"] == 1
    assert pm["n_iv_skip"] == 1

    # only m0 carries a (positive: call + B) increment; every skipped minute is 0.
    assert pm["delta"][0] > 0.0
    assert pm["delta"][1] == 0.0   # None forward contributed nothing
    assert pm["delta"][2] == 0.0   # neutral contributed nothing
    assert pm["delta"][3] == 0.0   # IV-skip contributed nothing
    assert pm["delta"][4] == 0.0   # no trade

    # cumulative is exactly the running prefix sum of delta.
    running = 0.0
    for i, d in enumerate(pm["delta"]):
        running += d
        assert pm["cumulative"][i] == pytest.approx(running, abs=1e-12)
    # ...so it plateaus at delta[0] after m0 (nothing else accumulates).
    assert pm["cumulative"] == pytest.approx([pm["delta"][0]] * 5, abs=1e-12)


# --------------------------------------------------------------------------- #
# 7. signed_volume_series — Σ sign·size (the NO-greek control), hand-verified.
#
# signed_vol[m]   = Σ s·size               ; sign_dir_vol[m] = Σ s·size·dir
#   dir = +1 for a call, -1 for a put. Neutral (N) trades drop out (s=0).
# --------------------------------------------------------------------------- #
def test_signed_volume_series_hand_computed() -> None:
    n = 3
    trades = [
        _trade(0, "B", is_call=True, size=10.0),   # s+1 call: sv +10 ; sdv +10
        _trade(0, "A", is_call=False, size=4.0),    # s-1 put : sv  -4 ; sdv (-1·4·-1)=+4
        _trade(1, "A", is_call=True, size=5.0),     # s-1 call: sv  -5 ; sdv -5
        _trade(1, "B", is_call=False, size=2.0),    # s+1 put : sv  +2 ; sdv (+1·2·-1)=-2
        _trade(2, "N", is_call=True, size=100.0),   # neutral : contributes 0 to both
    ]
    sv = signed_volume_series(trades, n)

    # signed volume per minute:  m0: 10-4=6 ; m1: -5+2=-3 ; m2: 0
    assert sv["delta_signed_vol"] == pytest.approx([6.0, -3.0, 0.0], abs=1e-12)
    # cumulative: [6, 6-3=3, 3]
    assert sv["cum_signed_vol"] == pytest.approx([6.0, 3.0, 3.0], abs=1e-12)

    # sign-dir volume per minute: m0: 10+4=14 ; m1: -5-2=-7 ; m2: 0
    assert sv["delta_sign_dir_vol"] == pytest.approx([14.0, -7.0, 0.0], abs=1e-12)
    # cumulative: [14, 14-7=7, 7]
    assert sv["cum_sign_dir_vol"] == pytest.approx([14.0, 7.0, 7.0], abs=1e-12)
