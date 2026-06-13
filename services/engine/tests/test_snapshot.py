"""Tests for engine.snapshot (step 1.3) — PRD #12 §2, T-05/T-06 integration.

Golden-fixture strategy
=======================
A deterministic option chain is built by *pricing* each leg with Black-76 at a
chosen IV smile, so the IV solver round-trips exactly and the whole pipeline is
reproducible. ``build_snapshot`` runs the full orchestration; the produced
Snapshot is compared against a frozen golden JSON
(``tests/golden/snapshot.golden.json``) within PRD #12 §2 tolerances:

  * Call/Put walls (OI, static): **EXACT**.
  * VOL levels (gamma_flip, largest_gex, largest_dex): within 1–2 strikes.
  * Regime sign: **EXACT**.
  * Everything else: tight numeric tolerance.

Independent invariants (not just golden equality) are also asserted so the test
is a real regression guard rather than a tautology: walls equal the strikes the
fixture OI dictates, regime sign equals the sign of aggregate net gamma, the
snapshot validates under the pydantic contract, and the serialized object
satisfies every TypeScript-zod constraint (key/shape parity).

Regenerate the golden after an intentional contract change:
    python -m tests.gen_golden        # (run from services/engine)
"""

from __future__ import annotations

import json
import math
import os
import re

from engine.black76 import price as bs_price
from engine.schema import parse_snapshot
from engine.snapshot import build_snapshot

GOLDEN_PATH = os.path.join(os.path.dirname(__file__), "golden", "snapshot.golden.json")

# --- shared deterministic fixture ----------------------------------------- #
INSTRUMENT = "ES"
TS_UTC = "2026-06-10T13:31:00Z"          # 09:31 ET -> minute_index 1
FORWARD = 5000.0
RATE = math.log(1.0517)                  # continuous r = ln(1 + SOFR)
T_EXPIRY = 0.02                          # year-fraction (synthetic, robust)
STATE = "LIVE"
AXIS = {"strike_min": 4980.0, "strike_max": 5020.0, "step": 5.0}

# strike: (call_vol, put_vol, call_oi, put_oi, sigma)
_ROWS = {
    4980.0: (200.0, 1800.0, 10.0, 200.0, 0.26),
    4985.0: (300.0, 1500.0, 10.0, 1100.0, 0.24),
    4990.0: (400.0, 1400.0, 10.0, 1600.0, 0.23),
    4995.0: (600.0, 1000.0, 10.0, 900.0, 0.22),
    5000.0: (900.0, 900.0, 50.0, 50.0, 0.21),
    5005.0: (1200.0, 500.0, 800.0, 10.0, 0.21),
    5010.0: (1500.0, 400.0, 1500.0, 10.0, 0.22),
    5015.0: (1300.0, 300.0, 1200.0, 10.0, 0.23),
    5020.0: (1000.0, 200.0, 300.0, 10.0, 0.25),
}

# Expected STATIC walls dictated purely by the fixture OI (independent of code).
EXPECTED_CALL_WALLS = [5010.0, 5015.0, 5005.0]   # call_oi: 1500 > 1200 > 800
EXPECTED_PUT_WALLS = [4990.0, 4985.0, 4995.0]    # put_oi: 1600 > 1100 > 900


def _fixture_chain():
    """Build the raw ChainQuote list, pricing mids with Black-76."""
    from engine.snapshot import ChainQuote

    chain = []
    for k, (cv, pv, c_oi, p_oi, sig) in _ROWS.items():
        call_mid = bs_price("call", FORWARD, k, T_EXPIRY, RATE, sig)
        put_mid = bs_price("put", FORWARD, k, T_EXPIRY, RATE, sig)
        chain.append(
            ChainQuote(
                strike=k,
                call_mid=call_mid,
                put_mid=put_mid,
                call_vol=cv,
                put_vol=pv,
                call_oi=c_oi,
                put_oi=p_oi,
                t_expiry=T_EXPIRY,
            )
        )
    return chain


def produce_snapshot():
    """Run the full pipeline and return the validated Snapshot."""
    return build_snapshot(
        INSTRUMENT, TS_UTC, _fixture_chain(), FORWARD, RATE, STATE, AXIS
    )


def _snap_dict():
    return json.loads(produce_snapshot().to_json())


# --------------------------------------------------------------------------- #
# Contract validation
# --------------------------------------------------------------------------- #
def test_validates_under_pydantic() -> None:
    snap = produce_snapshot()
    # Round-trip through the validator from a plain dict.
    reparsed = parse_snapshot(json.loads(snap.to_json()))
    assert reparsed.schema_version == 1
    assert reparsed.instrument == "ES"


_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ISO_DT_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")
_SNAPSHOT_KEYS = {
    "schema_version", "instrument", "session_date", "ts", "minute_index",
    "state", "stale", "expired", "forward", "rate", "axis", "regime",
    "profile", "field", "levels", "ohlc", "hiro", "synthetic_oi",
}


def _assert_zod_compatible(d: dict) -> None:
    """Mirror every constraint of the TS zod SnapshotSchema (.strict()).

    node/zod cannot be installed offline in the authoring sandbox, so the zod
    contract is enforced here field-by-field with identical semantics (strict
    keys, finite numbers, enums, ISO formats, integer minute_index, and the
    field array-length invariant).
    """
    assert set(d) == _SNAPSHOT_KEYS                      # .strict(): no extra/missing
    assert d["schema_version"] == 1
    assert d["instrument"] in ("ES", "NQ")
    assert _ISO_DATE.match(d["session_date"])
    assert _ISO_DT_Z.match(d["ts"])                      # z.string().datetime()
    assert isinstance(d["minute_index"], int)           # z.number().int()
    assert d["state"] in ("PREMARKET", "LIVE", "STALE", "CLOSED", "HOLIDAY")
    assert isinstance(d["stale"], bool) and isinstance(d["expired"], bool)
    for k in ("forward", "rate"):
        assert isinstance(d[k], (int, float)) and math.isfinite(d[k])
    ax = d["axis"]
    assert set(ax) == {"strike_min", "strike_max", "step"}
    assert ax["step"] > 0 and all(math.isfinite(ax[v]) for v in ax)
    rg = d["regime"]
    assert set(rg) == {"net_gamma", "sign", "stability_pct"}
    assert rg["sign"] in (-1, 0, 1)
    assert 0.0 <= rg["stability_pct"] <= 100.0 and math.isfinite(rg["net_gamma"])
    for row in d["profile"]:
        assert set(row) == {"strike", "net_gex", "net_dex", "interpolated"}
        assert isinstance(row["interpolated"], bool)
        assert all(math.isfinite(row[k]) for k in ("strike", "net_gex", "net_dex"))
    f = d["field"]
    assert set(f) == {"price_grid", "gamma", "delta"}
    assert len(f["price_grid"]) == len(f["gamma"]) == len(f["delta"])   # invariant
    assert all(math.isfinite(v) for v in f["price_grid"] + f["gamma"] + f["delta"])
    lv = d["levels"]
    assert set(lv) == {"call_walls", "put_walls", "gamma_flip", "largest_gex", "largest_dex"}
    assert all(math.isfinite(x) for x in lv["call_walls"] + lv["put_walls"])
    for k in ("gamma_flip", "largest_gex", "largest_dex"):
        assert lv[k] is None or math.isfinite(lv[k])
    oh = d["ohlc"]
    assert oh is None or set(oh) == {"o", "h", "l", "c"}
    if oh is not None:
        assert all(math.isfinite(oh[k]) for k in ("o", "h", "l", "c"))
    hr = d["hiro"]
    assert hr is None or set(hr) == {"total", "calls", "puts", "zerodte", "retail"}
    if hr is not None:
        assert all(math.isfinite(hr[k]) for k in ("total", "calls", "puts", "zerodte", "retail"))
    so = d["synthetic_oi"]
    assert so is None or set(so) == {"gex", "sign", "gex_static", "w"}
    if so is not None:
        assert so["sign"] in (-1, 0, 1)
        assert 0.0 <= so["w"] <= 1.0
        assert all(math.isfinite(so[k]) for k in ("gex", "gex_static"))


def test_serialized_passes_zod_contract() -> None:
    _assert_zod_compatible(_snap_dict())


# --------------------------------------------------------------------------- #
# Session stamping
# --------------------------------------------------------------------------- #
def test_minute_index_and_session_date() -> None:
    snap = produce_snapshot()
    assert snap.minute_index == 1            # 09:31 ET, open 09:30
    assert snap.session_date == "2026-06-10"
    assert snap.ts == "2026-06-10T13:31:00Z"
    assert snap.state == "LIVE"
    assert snap.stale is False and snap.expired is False


def test_session_flags_from_state() -> None:
    chain = _fixture_chain()
    closed = build_snapshot(INSTRUMENT, TS_UTC, chain, FORWARD, RATE, "CLOSED", AXIS)
    assert closed.expired is True and closed.stale is False
    stale = build_snapshot(INSTRUMENT, TS_UTC, chain, FORWARD, RATE, "STALE", AXIS)
    assert stale.stale is True and stale.expired is False


# --------------------------------------------------------------------------- #
# T-06: walls EXACT
# --------------------------------------------------------------------------- #
def test_walls_exact_vs_fixture() -> None:
    lv = produce_snapshot().levels
    assert lv.call_walls == EXPECTED_CALL_WALLS
    assert lv.put_walls == EXPECTED_PUT_WALLS


# --------------------------------------------------------------------------- #
# Regime sign EXACT
# --------------------------------------------------------------------------- #
def test_regime_sign_matches_net_gamma() -> None:
    snap = produce_snapshot()
    ng = snap.regime.net_gamma
    expected = 1 if ng > 0 else (-1 if ng < 0 else 0)
    assert snap.regime.sign == expected
    # sign also equals sign of the summed profile net_gex (independent check)
    s = sum(r.net_gex for r in snap.profile)
    assert snap.regime.sign == (1 if s > 0 else (-1 if s < 0 else 0))


# --------------------------------------------------------------------------- #
# Field invariants + profile ordering
# --------------------------------------------------------------------------- #
def test_field_and_profile_invariants() -> None:
    snap = produce_snapshot()
    f = snap.field
    assert len(f.price_grid) == len(f.gamma) == len(f.delta) == 9
    assert f.price_grid == [4980, 4985, 4990, 4995, 5000, 5005, 5010, 5015, 5020]
    assert all(math.isfinite(v) for v in f.gamma + f.delta)
    strikes = [r.strike for r in snap.profile]
    assert strikes == sorted(strikes)            # ascending
    assert len(strikes) == 9


def test_vol_levels_within_axis() -> None:
    lv = produce_snapshot().levels
    for v in (lv.gamma_flip, lv.largest_gex, lv.largest_dex):
        if v is not None:
            assert AXIS["strike_min"] <= v <= AXIS["strike_max"]


# --------------------------------------------------------------------------- #
# Thin strike -> interpolated flag, still validates
# --------------------------------------------------------------------------- #
def test_thin_strike_interpolated_and_validates() -> None:
    from engine.snapshot import ChainQuote

    chain = _fixture_chain()
    # Replace the 4980 quote with a thin (missing-mid) one.
    chain = [
        ChainQuote(strike=4980.0, call_mid=None, put_mid=None,
                   call_vol=200.0, put_vol=1800.0, call_oi=10.0, put_oi=200.0,
                   t_expiry=T_EXPIRY)
        if q.strike == 4980.0 else q
        for q in chain
    ]
    snap = build_snapshot(INSTRUMENT, TS_UTC, chain, FORWARD, RATE, STATE, AXIS)
    row = next(r for r in snap.profile if r.strike == 4980.0)
    assert row.interpolated is True
    _assert_zod_compatible(json.loads(snap.to_json()))


# --------------------------------------------------------------------------- #
# Divergence #5 -> option A: optional `hiro` field (additive, no version bump).
# --------------------------------------------------------------------------- #
def test_hiro_field_optional_absent_by_default() -> None:
    snap = produce_snapshot()
    # Absent when not supplied (mirrors the ohlc precedent) -> contract-valid.
    assert snap.hiro is None
    d = json.loads(snap.to_json())
    assert d["hiro"] is None


def test_hiro_field_round_trips_through_contract() -> None:
    from engine.hiro import hiro_series
    from engine.snapshot import MULTIPLIER
    from engine.hiro import HiroTrade

    # Two signed 0DTE trades: buy a call (bullish) + sell a put (bullish).
    trades = [
        HiroTrade(strike=5000.0, is_call=True, price=25.0, size=10.0, side="B", t_expiry=T_EXPIRY),
        HiroTrade(strike=4990.0, is_call=False, price=12.0, size=8.0, side="A", t_expiry=T_EXPIRY),
    ]
    series = hiro_series(trades, FORWARD, MULTIPLIER[INSTRUMENT], RATE)
    snap = build_snapshot(
        INSTRUMENT, TS_UTC, _fixture_chain(), FORWARD, RATE, STATE, AXIS,
        hiro=series.final,
    )
    assert snap.hiro is not None
    assert math.isclose(snap.hiro.total, series.final.total, rel_tol=1e-12)
    assert snap.hiro.calls > 0.0  # bought call -> positive dealer-buy pressure
    _assert_zod_compatible(json.loads(snap.to_json()))


# --------------------------------------------------------------------------- #
# Golden comparison (PRD #12 §2 tolerances)
# --------------------------------------------------------------------------- #
def _isclose(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-3)


def test_matches_golden_within_tolerances() -> None:
    assert os.path.exists(GOLDEN_PATH), "golden missing; run tests/gen_golden.py"
    with open(GOLDEN_PATH) as fh:
        gold = json.load(fh)
    got = _snap_dict()

    # Exact scalars / enums.
    for k in ("schema_version", "instrument", "session_date", "ts",
              "minute_index", "state", "stale", "expired"):
        assert got[k] == gold[k], k
    assert got["axis"] == gold["axis"]

    # Regime: sign EXACT, numbers within tolerance.
    assert got["regime"]["sign"] == gold["regime"]["sign"]
    assert _isclose(got["regime"]["net_gamma"], gold["regime"]["net_gamma"])
    assert _isclose(got["regime"]["stability_pct"], gold["regime"]["stability_pct"])

    # Walls EXACT.
    assert got["levels"]["call_walls"] == gold["levels"]["call_walls"]
    assert got["levels"]["put_walls"] == gold["levels"]["put_walls"]

    # VOL levels within 1–2 strikes (<= 2 * step).
    tol = 2.0 * gold["axis"]["step"]
    for k in ("gamma_flip", "largest_gex", "largest_dex"):
        g, x = gold["levels"][k], got["levels"][k]
        assert (g is None) == (x is None), k
        if g is not None:
            assert abs(x - g) <= tol, (k, x, g)

    # Profile: same strikes/flags, values within tolerance.
    assert len(got["profile"]) == len(gold["profile"])
    for rg, rx in zip(gold["profile"], got["profile"]):
        assert rx["strike"] == rg["strike"]
        assert rx["interpolated"] == rg["interpolated"]
        assert _isclose(rx["net_gex"], rg["net_gex"])
        assert _isclose(rx["net_dex"], rg["net_dex"])

    # Field arrays within tolerance.
    for arr in ("price_grid", "gamma", "delta"):
        assert len(got["field"][arr]) == len(gold["field"][arr])
        for a, b in zip(got["field"][arr], gold["field"][arr]):
            assert _isclose(a, b), arr


# --------------------------------------------------------------------------- #
# Divergence #3: real-clock 0DTE day-count (t_expiry_from_clock).
# NOT the default; the locked DEFAULT_T_EXPIRY = 0.5/365 is unchanged.
# --------------------------------------------------------------------------- #
def test_t_expiry_from_clock_shrinks_through_session() -> None:
    from engine.snapshot import SECONDS_PER_YEAR, t_expiry_from_clock

    # 09:30 ET == 13:30 UTC (summer EDT). 6.5h to the 16:00 ET settlement.
    open_t = t_expiry_from_clock("2026-06-10T13:30:00Z")
    noon_t = t_expiry_from_clock("2026-06-10T16:00:00Z")  # 12:00 ET, 4h left
    assert math.isclose(open_t, (6.5 * 3600.0) / SECONDS_PER_YEAR, rel_tol=1e-9)
    assert math.isclose(noon_t, (4.0 * 3600.0) / SECONDS_PER_YEAR, rel_tol=1e-9)
    # Strictly decreasing as the clock advances toward settlement.
    assert open_t > noon_t > 0.0


def test_t_expiry_from_clock_floored_at_or_after_settlement() -> None:
    from engine.snapshot import T_EXPIRY_FLOOR, t_expiry_from_clock

    # 16:00 ET (20:00 UTC EDT) == settlement -> floored, strictly positive.
    at_close = t_expiry_from_clock("2026-06-10T20:00:00Z")
    after = t_expiry_from_clock("2026-06-10T21:00:00Z")
    assert at_close == T_EXPIRY_FLOOR
    assert after == T_EXPIRY_FLOOR
    assert T_EXPIRY_FLOOR > 0.0


def test_t_expiry_from_clock_custom_settlement_hour() -> None:
    from engine.snapshot import SECONDS_PER_YEAR, t_expiry_from_clock

    # 15:00 ET settlement (some 0DTE/AM-settled refs); 09:30 ET -> 5.5h.
    t = t_expiry_from_clock("2026-06-10T13:30:00Z", settlement_hour=15, settlement_minute=0)
    assert math.isclose(t, (5.5 * 3600.0) / SECONDS_PER_YEAR, rel_tol=1e-9)
