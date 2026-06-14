"""Unit tests for analysis.harness.synthetic_oi_eval — the FLOW-TERM structural core.

These LOCK the behaviour of the synthetic-OI #4 per-strike flow-term eval against
the agreed spec. They are PURE and deterministic: every ``ChainRow`` / ``FlowTrade``
fixture is hand-built with chosen values, and every expected number is computed by
hand in the comments. No databento, no disk — only the math plus the LOCKED engine
position model (``engine.synthetic_oi.q_per_leg`` / ``synthetic_gex``) the eval reuses.

WHY THIS FILE EXISTS — the load-bearing concern: ``synthetic_gex_by_strike`` is a NEW
sign-free per-strike aggregator. The ENTIRE eval is only trustworthy if that aggregator
is faithful to the engine. So the single most important test here is the ANCHOR
(``test_aggregator_sums_to_engine_scalar``): ``sum(by_strike.values())`` MUST equal the
engine's scalar ``synthetic_gex`` for EVERY ``w`` (w=0 pure OI, w=1 full flow, and w=0.5).
If that identity ever breaks, the per-strike split is wrong (double-sign, mis-scale, or a
thin-skip mismatch) and no downstream metric means anything. The second lock
(``test_no_double_sign_on_put_heavy_strike``) pins that the aggregator does NOT re-apply
the dealer sign to puts — the documented double-sign trap that would manufacture fake
divergence.

Style mirrors test_ddoi_divergence.py / test_hiro_eval.py: namespace import (no
__init__.py), no test classes, ``-> None`` functions, run via the repo-root .venv python.
Importing ``analysis.harness.synthetic_oi_eval`` first puts the engine ``src`` on
``sys.path`` (its import side-effect), so the subsequent ``engine.*`` imports resolve
without extra path wiring.
"""
from __future__ import annotations

import math
from collections import Counter

import pytest

from analysis.harness.synthetic_oi_eval import (
    FlowTrade,
    eval_flow_term,
    eval_tiered_term,
    flow_term_metrics,
    net_flow_from_trades,
    shuffle_flow_signs,
    synthetic_gex_by_strike,
    tiered_net_flow_from_trades,
)

# synthetic_oi_eval's import added the engine src to sys.path; these now resolve.
from engine.exposure import DEALER_SIGN_PUT, GEX_PCT_SCALE, ChainRow  # noqa: E402
from engine.synthetic_oi import (  # noqa: E402
    BLOCK_MIN_SIZE,
    RETAIL_MAX_SIZE,
    q_per_leg,
    synthetic_gex,
)

# Instrument multiplier (/ES = 50) and a representative forward. The exact values
# never matter to the identity tests — only that the SAME M/F feed both the engine
# scalar and the aggregator (the scale ``M·F²·GEX_PCT_SCALE`` cancels in the anchor).
M = 50.0
F = 5000.0


def _row(
    strike: float,
    *,
    call_gamma: float,
    put_gamma: float,
    call_oi: float,
    put_oi: float,
    thin: bool = False,
) -> ChainRow:
    """A ChainRow carrying only the fields synthetic-OI #4 reads (gamma + OI + thin).

    ``call_delta`` / ``put_delta`` / ``call_vol`` / ``put_vol`` are required by the
    dataclass but are IRRELEVANT to ``synthetic_gex`` (the #4 basis is OI, not VOL),
    so they are pinned to 0.0 to make the intent explicit: this fixture exercises the
    OI+flow gamma path only.
    """
    return ChainRow(
        strike=strike,
        call_gamma=call_gamma,
        put_gamma=put_gamma,
        call_delta=0.0,
        put_delta=0.0,
        call_vol=0.0,
        put_vol=0.0,
        call_oi=call_oi,
        put_oi=put_oi,
        thin=thin,
    )


# A small deterministic chain: three NON-thin strikes (5010 is deliberately put-heavy
# in both OI and flow to exercise the sign path) + ONE thin strike at 5030 loaded with
# absurd gamma/OI/flow so that, if it were ever NOT skipped, every identity below would
# explode. Its survival of the anchor is the thin-skip proof.
ROWS = [
    _row(5000.0, call_gamma=0.020, put_gamma=0.018, call_oi=100.0, put_oi=80.0),
    _row(5010.0, call_gamma=0.015, put_gamma=0.012, call_oi=50.0, put_oi=120.0),  # put-heavy
    _row(5020.0, call_gamma=0.010, put_gamma=0.009, call_oi=30.0, put_oi=20.0),
    _row(5030.0, call_gamma=999.0, put_gamma=999.0, call_oi=999.0, put_oi=999.0, thin=True),
]

NET_FLOW = {
    (5000.0, True): 40.0,
    (5000.0, False): -10.0,
    (5010.0, True): 25.0,
    (5010.0, False): 60.0,   # put-heavy aggressor flow
    (5020.0, True): -5.0,
    (5020.0, False): 15.0,
    (5030.0, True): 1000.0,  # on the THIN strike -> must never enter the aggregation
    (5030.0, False): 1000.0,
}

_NON_THIN_STRIKES = {5000.0, 5010.0, 5020.0}


# --------------------------------------------------------------------------- #
# 1. THE ANCHOR — aggregator sums to the engine scalar at EVERY w.
#
# This is the whole point: synthetic_gex_by_strike is faithful iff, for every w,
#   sum(by_strike.values()) == engine.synthetic_oi.synthetic_gex(rows, ...)
# because both reuse the SAME q_per_leg Q, the SAME M·F²·GEX_PCT_SCALE scale, and
# the SAME thin-skip. A break here = double-sign / scale / thin-skip error and the
# entire eval is INVALID. We also assert the thin strike is SKIPPED by BOTH (its
# 1000-flow / 999-gamma never appears), so it contributes exactly 0.
# --------------------------------------------------------------------------- #
def test_aggregator_sums_to_engine_scalar() -> None:
    for w in (0.0, 0.5, 1.0):
        by_strike = synthetic_gex_by_strike(ROWS, NET_FLOW, M, F, w)
        engine_scalar = synthetic_gex(ROWS, NET_FLOW, M, F, w)

        # THE LOAD-BEARING IDENTITY. Both do identical float ops in identical row
        # order, so this is exact to float tolerance.
        assert math.isclose(
            sum(by_strike.values()), engine_scalar, rel_tol=1e-12, abs_tol=1e-6
        ), f"aggregator != engine scalar at w={w}"

        # thin strike skipped by the aggregator (its absurd 999/1000 never enters)...
        assert 5030.0 not in by_strike
        # ...and ONLY the three non-thin strikes are present.
        assert set(by_strike) == _NON_THIN_STRIKES


def test_thin_strike_contributes_zero_to_both() -> None:
    # Drop the thin row entirely; the engine scalar AND the aggregator sum must be
    # UNCHANGED -> the thin strike's 999-gamma / 1000-flow was contributing 0.
    rows_no_thin = [r for r in ROWS if not r.thin]
    for w in (0.0, 1.0):
        full = synthetic_gex(ROWS, NET_FLOW, M, F, w)
        trimmed = synthetic_gex(rows_no_thin, NET_FLOW, M, F, w)
        assert math.isclose(full, trimmed, rel_tol=1e-12, abs_tol=1e-9)

        by_full = synthetic_gex_by_strike(ROWS, NET_FLOW, M, F, w)
        by_trim = synthetic_gex_by_strike(rows_no_thin, NET_FLOW, M, F, w)
        assert by_full == by_trim


def test_w0_profile_is_pure_oi_and_flow_invariant() -> None:
    # At w=0 the additive (−flow)·w term VANISHES, so the profile is PURE OI-GEX and
    # must be identical no matter what flow map is supplied. This is the property
    # that makes ``profile_static`` the correct fixed reference for every shuffle arm.
    alt_flow = {k: v * 7.5 - 3.0 for k, v in NET_FLOW.items()}
    by0_real = synthetic_gex_by_strike(ROWS, NET_FLOW, M, F, 0.0)
    by0_alt = synthetic_gex_by_strike(ROWS, alt_flow, M, F, 0.0)
    assert by0_real == by0_alt


# --------------------------------------------------------------------------- #
# 2. SIGN-FREENESS (anti-double-sign lock).
#
# q_per_leg ALREADY bakes the dealer sign into Q (q_put = −1·OI + (−flow)·w), so the
# aggregator must add NO further dealer sign. The clean lock: the per-strike value
# equals (call_gamma·q_call + put_gamma·q_put)·M·F²·GEX_PCT_SCALE using q_per_leg
# DIRECTLY. On a put-heavy strike (nonzero q_put), re-applying DEALER_SIGN_PUT would
# FLIP the put term -> a clearly different number, which we assert does NOT happen.
# --------------------------------------------------------------------------- #
def test_no_double_sign_on_put_heavy_strike() -> None:
    w = 1.0  # fully engage the flow term
    by_strike = synthetic_gex_by_strike(ROWS, NET_FLOW, M, F, w)

    put_heavy = ROWS[1]  # strike 5010 (put_oi=120, put flow=60)
    q_call, q_put = q_per_leg(put_heavy, NET_FLOW, w)
    # sanity: the put leg actually carries signed weight (else the trap can't bite).
    #   q_put = DEALER_SIGN_PUT·120 + (−60)·1 = −120 − 60 = −180  (nonzero)
    assert q_put == pytest.approx(-180.0, abs=1e-9)

    scale = M * F * F * GEX_PCT_SCALE
    correct = (put_heavy.call_gamma * q_call + put_heavy.put_gamma * q_put) * scale
    assert math.isclose(by_strike[5010.0], correct, rel_tol=1e-12, abs_tol=1e-6)

    # THE TRAP: re-applying DEALER_SIGN_PUT (−1) to the put term flips its sign.
    double_signed = (
        put_heavy.call_gamma * q_call
        + DEALER_SIGN_PUT * put_heavy.put_gamma * q_put
    ) * scale
    # the aggregator must NOT match the double-signed value (proves it is sign-free).
    assert not math.isclose(by_strike[5010.0], double_signed, rel_tol=1e-9)


# --------------------------------------------------------------------------- #
# 3a. flow_term_metrics — residual_r2 detects "flow is just a rescale of OI".
#
# gex == static (identical)        -> c=1, residual_r2=1.0 (perfectly redundant).
# gex == 3·static (scalar multiple)-> c=3, residual_r2=1.0 (flow adds NOTHING new).
# gex == static + ORTHOGONAL pert. -> residual_r2 clearly < 1 (structure detected).
# --------------------------------------------------------------------------- #
def test_residual_r2_identical_is_one() -> None:
    static = {5000.0: 10.0, 5010.0: -4.0, 5020.0: 6.0, 5030.0: -2.0}
    gex = dict(static)  # gex == static
    m = flow_term_metrics(gex, static)
    assert m["n"] == 4
    assert m["best_fit_scalar_c"] == pytest.approx(1.0, abs=1e-12)
    assert m["residual_r2"] == pytest.approx(1.0, abs=1e-12)     # zero residual
    assert m["flow_norm_ratio"] == pytest.approx(0.0, abs=1e-12)  # ‖0‖/‖s‖
    assert m["argmax_distance"] == 0.0


def test_residual_r2_scalar_multiple_is_redundant() -> None:
    static = {5000.0: 10.0, 5010.0: -4.0, 5020.0: 6.0, 5030.0: -2.0}
    gex = {k: 3.0 * v for k, v in static.items()}  # pure scalar multiple
    m = flow_term_metrics(gex, static)
    # c = Σ(g·s)/Σ(s²) = 3·Σs²/Σs² = 3 ; residual = g − 3s = 0 -> r2 = 1.0.
    assert m["best_fit_scalar_c"] == pytest.approx(3.0, abs=1e-12)
    assert m["residual_r2"] == pytest.approx(1.0, abs=1e-12)  # rescale ⇒ NOTHING new
    # ‖gex − static‖ = ‖3s − s‖ = ‖2s‖ -> flow_norm_ratio = 2.0.
    assert m["flow_norm_ratio"] == pytest.approx(2.0, abs=1e-12)
    assert m["argmax_distance"] == 0.0  # |3·static| peaks where |static| does


def test_residual_r2_orthogonal_perturbation_is_detected() -> None:
    # static = [1,-1,1,-1] ; perturb p = [1,1,1,1] is ORTHOGONAL (Σ p·s = 0).
    static = {5000.0: 1.0, 5010.0: -1.0, 5020.0: 1.0, 5030.0: -1.0}
    gex = {5000.0: 2.0, 5010.0: 0.0, 5020.0: 2.0, 5030.0: 0.0}  # = static + p
    m = flow_term_metrics(gex, static)
    # c = Σ(g·s)/Σ(s²) = (2·1 + 0·−1 + 2·1 + 0·−1)/4 = 4/4 = 1.
    assert m["best_fit_scalar_c"] == pytest.approx(1.0, abs=1e-12)
    # residual = g − 1·s = p = [1,1,1,1] ; ssres=4 ; mean_g=1, sstot=Σ(g−1)²=4.
    #   residual_r2 = 1 − 4/4 = 0.0  (structured residual ⇒ NOT a rescale of OI).
    assert m["residual_r2"] == pytest.approx(0.0, abs=1e-12)
    assert m["residual_r2"] < 1.0


def test_residual_r2_reshuffle_is_structured() -> None:
    # Move the dominant magnitude off 5000 onto 5010 -> a real strike re-weighting,
    # NOT a scalar multiple. (Same construction the ddoi reshuffle test locks.)
    static = {5000.0: 10.0, 5010.0: 1.0, 5020.0: 2.0, 5030.0: 3.0}   # s=[10,1,2,3]
    gex = {5000.0: 1.0, 5010.0: 10.0, 5020.0: 3.0, 5030.0: 2.0}      # g=[1,10,3,2]
    m = flow_term_metrics(gex, static)
    # c = Σ(g·s)/Σ(s²) = (10+10+6+6)/(100+1+4+9) = 32/114.
    assert m["best_fit_scalar_c"] == pytest.approx(32.0 / 114.0, abs=1e-12)
    # ssres ≈ 105.02, sstot = 50 -> residual_r2 ≈ 1 − 2.1003 ≈ −1.10 (well below 1).
    assert m["residual_r2"] == pytest.approx(-1.10035, abs=1e-3)
    assert m["residual_r2"] < 0.9


# --------------------------------------------------------------------------- #
# 3b. flow_norm_ratio — headline magnitude ‖gex − static‖₂ / ‖static‖₂.
# --------------------------------------------------------------------------- #
def test_flow_norm_ratio_hand_verified() -> None:
    static = {5000.0: 3.0, 5010.0: -1.0, 5020.0: 4.0}
    # identical -> ‖0‖/‖s‖ = 0.0
    assert flow_term_metrics(dict(static), static)["flow_norm_ratio"] == pytest.approx(
        0.0, abs=1e-12
    )
    # 2·static -> ‖2s − s‖/‖s‖ = ‖s‖/‖s‖ = 1.0
    gex2 = {k: 2.0 * v for k, v in static.items()}
    assert flow_term_metrics(gex2, static)["flow_norm_ratio"] == pytest.approx(
        1.0, abs=1e-12
    )


# --------------------------------------------------------------------------- #
# 3c. argmax_distance — does the flow term MOVE the dominant strike?
#
# NOTE: the metric (and the ddoi precedent) measures distance in STRIKE POINTS
# (the |max| key difference), not in index slots. Hand-verified accordingly.
# --------------------------------------------------------------------------- #
def test_argmax_distance_moves_dominant_strike() -> None:
    static = {5000.0: 10.0, 5010.0: 1.0, 5020.0: 2.0}  # |peak| at 5000
    gex = {5000.0: 2.0, 5010.0: 1.0, 5020.0: 9.0}      # |peak| at 5020
    m = flow_term_metrics(gex, static)
    assert m["static_argmax_strike"] == 5000.0
    assert m["gex_argmax_strike"] == 5020.0
    assert m["argmax_distance"] == pytest.approx(20.0, abs=1e-12)  # |5020 − 5000|


# --------------------------------------------------------------------------- #
# 3d. flow_term_metrics — degenerate (empty / no shared strikes) is defined.
# --------------------------------------------------------------------------- #
def test_flow_term_metrics_empty_is_defined() -> None:
    m = flow_term_metrics({}, {})
    assert m["n"] == 0
    assert math.isnan(m["best_fit_scalar_c"])
    assert math.isnan(m["residual_r2"])
    assert math.isnan(m["flow_norm_ratio"])
    assert math.isnan(m["sign_agreement"])
    assert m["argmax_distance"] is None
    assert m["gex_argmax_strike"] is None
    assert m["static_argmax_strike"] is None


def test_flow_term_metrics_disjoint_strikes_is_n_zero() -> None:
    m = flow_term_metrics({5000.0: 1.0}, {6000.0: 1.0})  # empty intersection
    assert m["n"] == 0
    assert m["argmax_distance"] is None


# --------------------------------------------------------------------------- #
# 4. shuffle_flow_signs — the valid directional null.
#
# A valid directional null DESTROYS direction while PRESERVING the global sign
# MULTISET (and each trade's size/strike/is_call). Because the output is a NETTED
# {leg: Σ sign·size} map, we expose the sign multiset by putting every trade on a
# DISTINCT leg with size==1.0: then each leg's value IS its assigned sign, so the
# Counter of output values equals the Counter of the original signs. Deterministic
# per seed; varies across seeds.
# --------------------------------------------------------------------------- #
def test_shuffle_preserves_sign_multiset_and_legs() -> None:
    signs = [1, -1, 1, 0, -1, 1, -1, 0]  # multiset: 3×+1, 3×−1, 2×0
    trades = [
        FlowTrade(strike=5000.0 + 10.0 * i, is_call=(i % 2 == 0), size=1.0, sign=s)
        for i, s in enumerate(signs)
    ]
    legs = {(5000.0 + 10.0 * i, (i % 2 == 0)) for i in range(len(signs))}

    seed = 20260612
    out = shuffle_flow_signs(trades, seed)

    # no leg invented or dropped -> size/strike/is_call population preserved.
    assert set(out.keys()) == legs
    # SIGN MULTISET INVARIANCE — the load-bearing property of a directional null.
    # (size==1 per distinct leg ⇒ each value == its permuted sign.)
    assert Counter(out.values()) == Counter(float(s) for s in signs)
    assert Counter(float(s) for s in signs) == Counter({1.0: 3, -1.0: 3, 0.0: 2})


def test_shuffle_is_deterministic_per_seed_and_varies_across_seeds() -> None:
    signs = [1, -1, 1, 0, -1, 1, -1, 0]
    trades = [
        FlowTrade(strike=5000.0 + 10.0 * i, is_call=(i % 2 == 0), size=1.0, sign=s)
        for i, s in enumerate(signs)
    ]
    # same seed -> identical netted map (reproducible).
    assert shuffle_flow_signs(trades, 20260612) == shuffle_flow_signs(trades, 20260612)
    # different seeds -> generally different leg->sign assignments.
    variants = {
        tuple(sorted(shuffle_flow_signs(trades, sd).items()))
        for sd in (20260612, 20260613, 20260614, 1, 7)
    }
    assert len(variants) > 1


# --------------------------------------------------------------------------- #
# 5. net_flow_from_trades — Σ sign·size per (strike, is_call) leg, hand-computed.
# --------------------------------------------------------------------------- #
def test_net_flow_from_trades_hand_computed() -> None:
    trades = [
        FlowTrade(strike=5000.0, is_call=True, size=10.0, sign=+1),   # +10
        FlowTrade(strike=5000.0, is_call=True, size=4.0, sign=-1),    # −4  -> leg = +6
        FlowTrade(strike=5000.0, is_call=False, size=3.0, sign=+1),   # +3
        FlowTrade(strike=5010.0, is_call=True, size=5.0, sign=0),     # 0·5 = 0
    ]
    nf = net_flow_from_trades(trades)
    assert nf[(5000.0, True)] == pytest.approx(6.0, abs=1e-12)
    assert nf[(5000.0, False)] == pytest.approx(3.0, abs=1e-12)
    assert nf[(5010.0, True)] == pytest.approx(0.0, abs=1e-12)
    # keys are (float, bool) so they match the row.strike lookup inside q_per_leg.
    assert set(nf.keys()) == {(5000.0, True), (5000.0, False), (5010.0, True)}


# --------------------------------------------------------------------------- #
# 6. eval_flow_term — integration wiring lock.
#
# The full panel's "real" arm must be EXACTLY flow_term_metrics(profile_gex,
# profile_static) built from net_flow_from_trades + synthetic_gex_by_strike. Lock
# that composition (n / residual_r2 / flow_norm_ratio) so the integrator can't drift
# from its parts. Flow on the thin strike must not change n (3 non-thin strikes).
# --------------------------------------------------------------------------- #
def test_eval_flow_term_matches_its_parts() -> None:
    trades = [
        FlowTrade(strike=5000.0, is_call=True, size=10.0, sign=+1),
        FlowTrade(strike=5010.0, is_call=False, size=20.0, sign=-1),
        FlowTrade(strike=5020.0, is_call=True, size=5.0, sign=+1),
        FlowTrade(strike=5030.0, is_call=True, size=100.0, sign=+1),  # thin -> ignored
    ]
    net = net_flow_from_trades(trades)
    profile_static = synthetic_gex_by_strike(ROWS, net, M, F, 0.0)
    profile_gex = synthetic_gex_by_strike(ROWS, net, M, F, 1.0)
    expected = flow_term_metrics(profile_gex, profile_static)

    res = eval_flow_term(ROWS, trades, M, F)

    assert res["w"] == 1.0
    assert res["n"] == 3  # only the three non-thin shared strikes
    assert res["n"] == expected["n"]
    assert res["best_fit_scalar_c"] == pytest.approx(expected["best_fit_scalar_c"], abs=1e-12)
    assert res["residual_r2"] == pytest.approx(expected["residual_r2"], abs=1e-12)
    assert res["flow_norm_ratio"] == pytest.approx(expected["flow_norm_ratio"], abs=1e-12)


# --------------------------------------------------------------------------- #
# 7. tiered_net_flow_from_trades — the synthetic-OI #6 size-TIERED flow map.
#
# THE CORRECTNESS ANCHOR for the tiered constructor (the advisor-required lock):
# with retail_weight == block_weight == 1.0 EVERY tier_weight is 1.0, so the tiered
# map must reduce EXACTLY (math.isclose per leg, identical key set) to the plain
# net_flow_from_trades. If this ever drifts, the tiered constructor is unfaithful and
# the whole #6 arm is meaningless. Sizes deliberately span all three tiers (retail
# <=5, mid, block >=50 for /ES) AND multiple trades share a leg, so the reduction
# exercises summation, not just a single-trade pass-through.
# --------------------------------------------------------------------------- #
def test_tiered_reduces_to_plain_when_all_weights_one() -> None:
    trades = [
        FlowTrade(strike=5000.0, is_call=True, size=3.0, sign=+1),    # retail
        FlowTrade(strike=5000.0, is_call=True, size=60.0, sign=-1),   # block (/ES)
        FlowTrade(strike=5000.0, is_call=False, size=10.0, sign=+1),  # mid
        FlowTrade(strike=5010.0, is_call=True, size=2.0, sign=+1),    # retail
        FlowTrade(strike=5010.0, is_call=False, size=55.0, sign=-1),  # block (/ES)
    ]
    plain = net_flow_from_trades(trades)
    # all tiers weight 1.0 -> tier_weight is the identity -> EXACT reduction to #4.
    tiered = tiered_net_flow_from_trades(
        trades, "ES", retail_weight=1.0, block_weight=1.0
    )
    assert set(tiered.keys()) == set(plain.keys())
    for leg in plain:
        assert math.isclose(tiered[leg], plain[leg], rel_tol=1e-12, abs_tol=1e-12), leg


def test_tiered_map_sums_to_engine_scalar_anchor() -> None:
    # The sign-free aggregator anchor must hold for ANY flow map, including a TIERED one:
    # sum(synthetic_gex_by_strike(rows, tiered, ...)) == engine synthetic_gex(rows, tiered, ...).
    # Build a real tiered map from trades on the fixture strikes, then assert the identity at
    # every w (same load-bearing identity as test_aggregator_sums_to_engine_scalar).
    trades = [
        FlowTrade(strike=5000.0, is_call=True, size=60.0, sign=+1),   # block
        FlowTrade(strike=5000.0, is_call=False, size=3.0, sign=-1),   # retail -> deleted
        FlowTrade(strike=5010.0, is_call=False, size=80.0, sign=-1),  # block
        FlowTrade(strike=5020.0, is_call=True, size=10.0, sign=+1),   # mid
        FlowTrade(strike=5030.0, is_call=True, size=100.0, sign=+1),  # thin -> skipped
    ]
    tiered = tiered_net_flow_from_trades(trades, "ES")  # engine defaults (retail deleted)
    for w in (0.0, 0.5, 1.0):
        by_strike = synthetic_gex_by_strike(ROWS, tiered, M, F, w)
        engine_scalar = synthetic_gex(ROWS, tiered, M, F, w)
        assert math.isclose(
            sum(by_strike.values()), engine_scalar, rel_tol=1e-12, abs_tol=1e-6
        ), f"tiered aggregator != engine scalar at w={w}"
        assert 5030.0 not in by_strike  # thin strike still skipped under a tiered map


def test_tiered_default_deletes_retail_and_upweights_block() -> None:
    # Engine defaults: retail_weight=0.0 (DELETES retail), block_weight=1.5, /ES block_min=50.
    # One leg, three trades spanning all tiers, hand-computed.
    trades = [
        FlowTrade(strike=5000.0, is_call=True, size=3.0, sign=+1),    # retail -> 3·0.0   = 0
        FlowTrade(strike=5000.0, is_call=True, size=10.0, sign=+1),   # mid    -> 10·1.0  = +10
        FlowTrade(strike=5000.0, is_call=True, size=60.0, sign=-1),   # block  -> -60·1.5 = -90
    ]
    plain = net_flow_from_trades(trades)
    assert plain[(5000.0, True)] == pytest.approx(3.0 + 10.0 - 60.0, abs=1e-12)  # = -47
    tiered = tiered_net_flow_from_trades(trades, "ES")  # defaults
    # retail DELETED (not reweighted): +10 (mid) − 90 (block·1.5) = −80.
    assert tiered[(5000.0, True)] == pytest.approx(10.0 - 90.0, abs=1e-12)


def test_tiered_block_min_is_per_instrument() -> None:
    # size=30 is MID for /ES (block_min=50 -> weight 1.0) but BLOCK for /NQ
    # (block_min=25 -> weight 1.5). Proves the per-instrument block_min default is
    # sourced from engine.synthetic_oi.BLOCK_MIN_SIZE, not hardcoded.
    assert BLOCK_MIN_SIZE["ES"] == 50.0 and BLOCK_MIN_SIZE["NQ"] == 25.0
    trades = [FlowTrade(strike=5000.0, is_call=True, size=30.0, sign=+1)]
    es = tiered_net_flow_from_trades(trades, "ES")
    nq = tiered_net_flow_from_trades(trades, "NQ")
    assert es[(5000.0, True)] == pytest.approx(30.0 * 1.0, abs=1e-12)   # mid for /ES
    assert nq[(5000.0, True)] == pytest.approx(30.0 * 1.5, abs=1e-12)   # block for /NQ


def test_tiered_all_retail_collapses_to_empty_flow() -> None:
    # The documented DEGENERACY: an all-retail tape (every size <= RETAIL_MAX_SIZE) is
    # DELETED by the default retail_weight=0.0, so every leg's tiered net flow is 0.0
    # while the plain net flow is materially nonzero. This is the collapse the runner
    # reports as the finding (tiered flow term -> 0 -> profile_tiered -> pure OI).
    assert RETAIL_MAX_SIZE == 5.0
    trades = [
        FlowTrade(strike=5000.0, is_call=True, size=2.0, sign=+1),
        FlowTrade(strike=5010.0, is_call=False, size=5.0, sign=-1),
        FlowTrade(strike=5020.0, is_call=True, size=1.0, sign=+1),
    ]
    plain = net_flow_from_trades(trades)
    assert any(v != 0.0 for v in plain.values())  # plain flow is real
    tiered = tiered_net_flow_from_trades(trades, "ES")  # defaults -> all deleted
    assert all(v == 0.0 for v in tiered.values())  # every retail leg zeroed


# --------------------------------------------------------------------------- #
# 8. eval_tiered_term — the #6 integration wiring lock.
#
# The tiered arm's REFERENCE is the PLAIN #4 flow profile (NOT pure OI): the #6 question
# is whether size-tiering adds structure OVER the plain flow term. Lock that the "real"
# arm is EXACTLY flow_term_metrics(profile_tiered, profile_plain) built from the parts,
# and that the degeneracy bookkeeping (deleted/surviving counts) is correct.
# --------------------------------------------------------------------------- #
def test_eval_tiered_term_matches_its_parts_and_counts() -> None:
    trades = [
        FlowTrade(strike=5000.0, is_call=True, size=60.0, sign=+1),   # block
        FlowTrade(strike=5000.0, is_call=False, size=3.0, sign=-1),   # retail -> deleted
        FlowTrade(strike=5010.0, is_call=True, size=10.0, sign=+1),   # mid
        FlowTrade(strike=5010.0, is_call=False, size=80.0, sign=-1),  # block
        FlowTrade(strike=5020.0, is_call=True, size=2.0, sign=+1),    # retail -> deleted
        FlowTrade(strike=5030.0, is_call=True, size=100.0, sign=+1),  # thin strike (block)
    ]
    net_plain = net_flow_from_trades(trades)
    net_tiered = tiered_net_flow_from_trades(trades, "ES")  # defaults
    profile_plain = synthetic_gex_by_strike(ROWS, net_plain, M, F, 1.0)
    profile_tiered = synthetic_gex_by_strike(ROWS, net_tiered, M, F, 1.0)
    expected = flow_term_metrics(profile_tiered, profile_plain)

    res = eval_tiered_term(ROWS, trades, "ES", M, F)

    assert res["w"] == 1.0
    assert res["n"] == 3  # three non-thin shared strikes (5030 thin -> excluded)
    assert res["n"] == expected["n"]
    assert res["best_fit_scalar_c"] == pytest.approx(expected["best_fit_scalar_c"], abs=1e-12)
    assert res["residual_r2"] == pytest.approx(expected["residual_r2"], abs=1e-12)
    assert res["flow_norm_ratio"] == pytest.approx(expected["flow_norm_ratio"], abs=1e-12)

    # degeneracy bookkeeping: two retail trades (size 3, 2) are DELETED.
    assert res["n_trades"] == 6
    assert res["n_deleted_trades"] == 2
    assert res["n_surviving_trades"] == 4
    assert res["n_plain_legs"] == 6  # all six legs carry plain flow
    # surviving tiered legs = nonzero tiered values: 5000c, 5010c, 5010p, 5030c (4).
    assert res["n_surviving_legs"] == 4


def test_eval_tiered_term_reduces_to_plain_arm_when_weights_one() -> None:
    # With all tier weights 1.0 the tiered profile EQUALS the plain flow profile, so the
    # tiered arm's "real" comparison is profile vs ITSELF: residual_r2 == 1.0, the flow
    # term vs its own reference is zero magnitude, argmax does not move. This propagates
    # the constructor reduction (test 7) through the full integrator.
    trades = [
        FlowTrade(strike=5000.0, is_call=True, size=60.0, sign=+1),
        FlowTrade(strike=5010.0, is_call=False, size=10.0, sign=-1),
        FlowTrade(strike=5020.0, is_call=True, size=3.0, sign=+1),
    ]
    res = eval_tiered_term(
        ROWS, trades, "ES", M, F, retail_weight=1.0, block_weight=1.0
    )
    assert res["n"] == 3
    assert res["flow_norm_ratio"] == pytest.approx(0.0, abs=1e-12)  # tiered == plain
    assert res["residual_r2"] == pytest.approx(1.0, abs=1e-12)
    assert res["argmax_distance"] == pytest.approx(0.0, abs=1e-12)
    assert res["n_deleted_trades"] == 0  # nothing deleted at weight 1.0
