"""Unit tests for analysis.harness.provenance — the fail-closed 0DTE tenor guard.

These LOCK the behaviour of ``assert_0dte`` (and its ``DataProvenance`` output)
against the agreed spec. They are deterministic: every ``expiration_ns`` is built
from a wall-clock ``datetime(..., 16, 0, tzinfo=America/New_York)`` so the fixture
mirrors the real on-disk data (epoch-ns UTC stamped at 16:00 ET). Expected values
are hand-computed in comments.

Style mirrors test_metrics.py: namespace import (no __init__.py), no test classes,
``-> None`` functions, run via the repo-root .venv python.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from analysis.harness.provenance import (
    DataProvenance,
    DefLeg,
    LegMeta,
    TenorContaminationError,
    assert_0dte,
    assert_session_iids_0dte,
)

# Same zone the module stamps expiries in; building fixtures here proves the
# guard compares dates in ET, not UTC.
NY = ZoneInfo("America/New_York")

# A real session date (matches the gen_session_snapshots example day). Tuesday.
SESSION = date(2026, 6, 9)


def _expiry_ns(d: date, hour: int = 16, minute: int = 0) -> int:
    """Epoch-ns (UTC) for ``hour:minute`` America/New_York on date ``d``.

    Mirrors how the real definition data is stamped: 16:00 ET -> epoch ns. The
    float*1e9 cast loses sub-microsecond precision (value > 2**53) but that is
    irrelevant for date/day-fraction comparisons and is fully deterministic, so
    fingerprints stay stable.
    """
    dt = datetime(d.year, d.month, d.day, hour, minute, tzinfo=NY)
    return int(dt.timestamp() * 1e9)


def _is_sha256_hex(s: str) -> bool:
    """True iff ``s`` is exactly 64 lowercase-or-upper hex chars (a sha256 digest)."""
    if len(s) != 64:
        return False
    try:
        int(s, 16)
    except ValueError:
        return False
    return True


def _leg(
    iid: int,
    *,
    strike: float = 5000.0,
    ic: str = "C",
    instrument: str = "ES",
    expiry: date = SESSION,
    hour: int = 16,
) -> LegMeta:
    return LegMeta(
        instrument_id=iid,
        expiration_ns=_expiry_ns(expiry, hour=hour),
        strike=strike,
        instrument_class=ic,
        instrument=instrument,
    )


def _def_leg(
    *,
    strike: float = 5000.0,
    ic: str = "C",
    instrument: str = "ES",
    expiry: date = SESSION,
    hour: int = 16,
) -> DefLeg:
    """A ``DefLeg`` (def_map VALUE; instrument_id is the map KEY, not a field)."""
    return DefLeg(
        expiration_ns=_expiry_ns(expiry, hour=hour),
        strike=strike,
        instrument_class=ic,
        instrument=instrument,
    )


# --------------------------------------------------------------------------- #
# happy path
# --------------------------------------------------------------------------- #
def test_clean_0dte_set_returns_full_provenance() -> None:
    # One ES call + one ES put + one NQ call, all expiring 16:00 ET on SESSION.
    legs = [
        _leg(101, strike=5000.0, ic="C", instrument="ES"),
        _leg(102, strike=5000.0, ic="P", instrument="ES"),
        _leg(201, strike=18000.0, ic="C", instrument="NQ"),
    ]
    prov = assert_0dte(legs, SESSION, source_label="zerodte/defs")

    assert isinstance(prov, DataProvenance)
    assert prov.source_label == "zerodte/defs"
    assert prov.session_date == SESSION
    assert prov.expiry_set == (SESSION,)           # one unique expiry == session
    assert prov.n_legs == 3
    assert prov.instruments == ("ES", "NQ")        # sorted unique underlyings
    # 16:00 ET expiry on the session date -> 0 days to the 16:00 ET close.
    assert prov.realized_tenor_days == pytest.approx(0.0, abs=1e-9)
    assert _is_sha256_hex(prov.fingerprint) and len(prov.fingerprint) == 64


# --------------------------------------------------------------------------- #
# the 5 fail-closed raise conditions (one test each)
# --------------------------------------------------------------------------- #
def test_empty_legs_raises() -> None:
    # Condition 1: never silently pass an empty chain.
    with pytest.raises(TenorContaminationError):
        assert_0dte([], SESSION, source_label="zerodte/defs")


def test_non_option_instrument_class_raises() -> None:
    # Condition 2: a future/non-option leg ("F") contaminates the option chain.
    legs = [
        _leg(101, ic="C", instrument="ES"),
        _leg(102, ic="F", instrument="ES"),  # not in {"C","P"}
    ]
    with pytest.raises(TenorContaminationError):
        assert_0dte(legs, SESSION, source_label="zerodte/defs")


def test_single_expiry_not_session_raises() -> None:
    # Condition 3: one expiry, but it is the NEXT day, not the session date.
    next_day = SESSION + timedelta(days=1)  # 2026-06-10
    legs = [_leg(101, expiry=next_day, ic="C", instrument="ES")]
    with pytest.raises(TenorContaminationError):
        assert_0dte(legs, SESSION, source_label="zerodte/defs")


def test_multiple_distinct_expiries_raises() -> None:
    # Condition 4: two distinct ET expiry dates present -> contamination.
    legs = [
        _leg(101, expiry=SESSION, ic="C", instrument="ES"),
        _leg(102, expiry=SESSION + timedelta(days=1), ic="P", instrument="ES"),
    ]
    with pytest.raises(TenorContaminationError):
        assert_0dte(legs, SESSION, source_label="zerodte/defs")


def test_far_tenor_nine_days_out_raises() -> None:
    # Condition 5 territory: an accidental quarterly/weekly pull 9 days out.
    # NB: with the real 16:00-ET stamp, a +9d leg first trips the expiry-date
    # check (condition 3) because its ET date != session; the >=1.0 day branch
    # is shadowed by that. Either way the guard must fail-closed. (See report.)
    nine_out = SESSION + timedelta(days=9)  # 2026-06-18
    legs = [_leg(101, expiry=nine_out, ic="C", instrument="ES")]
    with pytest.raises(TenorContaminationError):
        assert_0dte(legs, SESSION, source_label="zerodte/defs")


# --------------------------------------------------------------------------- #
# timezone correctness  (the load-bearing behaviour)
# --------------------------------------------------------------------------- #
def test_1600_et_on_session_date_passes() -> None:
    # Minimum bar: the real data shape (16:00 ET on the session) must PASS.
    legs = [_leg(101, hour=16, ic="C", instrument="ES")]
    prov = assert_0dte(legs, SESSION, source_label="zerodte/defs")
    assert prov.expiry_set == (SESSION,)
    assert prov.realized_tenor_days == pytest.approx(0.0, abs=1e-9)


def test_et_date_used_not_utc_date_load_bearing() -> None:
    # LOAD-BEARING TZ TEST.
    # 21:00 ET on 2026-06-09. June is EDT (UTC-4), so this instant is
    # 2026-06-10 01:00 UTC -> a DIFFERENT calendar day in UTC than in ET.
    #   * correct ET compare:  exp_date == 2026-06-09 == session  -> PASS
    #   * naive  UTC compare:  exp_date == 2026-06-10 != session  -> would RAISE
    # so if someone reimplemented the date compare in UTC, this test FAILS
    # (it would raise instead of returning a provenance).
    legs = [_leg(101, hour=21, ic="C", instrument="ES")]
    prov = assert_0dte(legs, SESSION, source_label="zerodte/defs")
    assert prov.expiry_set == (SESSION,)
    # days = (21:00 - 16:00) / 24h = 5/24 = 0.208333..., and < 1.0 so it passes.
    assert prov.realized_tenor_days == pytest.approx(5.0 / 24.0, abs=1e-6)


# --------------------------------------------------------------------------- #
# fingerprint determinism
# --------------------------------------------------------------------------- #
def test_fingerprint_is_order_independent() -> None:
    # Same legs, different input order -> identical fingerprint (sorts by iid).
    a = _leg(201, strike=18000.0, ic="C", instrument="NQ")
    b = _leg(101, strike=5000.0, ic="C", instrument="ES")
    c = _leg(102, strike=5000.0, ic="P", instrument="ES")

    fp1 = assert_0dte([a, b, c], SESSION, source_label="zerodte/defs").fingerprint
    fp2 = assert_0dte([c, a, b], SESSION, source_label="zerodte/defs").fingerprint

    # make the equality load-bearing: prove fp is a real, non-trivial digest first.
    assert _is_sha256_hex(fp1) and len(fp1) == 64
    assert fp1 == fp2


def test_fingerprint_changes_when_a_leg_field_changes() -> None:
    # Changing any identity field (here: strike) flips the digest.
    base = [
        _leg(101, strike=5000.0, ic="C", instrument="ES"),
        _leg(102, strike=5000.0, ic="P", instrument="ES"),
    ]
    changed = [
        _leg(101, strike=5001.0, ic="C", instrument="ES"),  # strike 5000 -> 5001
        _leg(102, strike=5000.0, ic="P", instrument="ES"),
    ]
    fp_base = assert_0dte(base, SESSION, source_label="zerodte/defs").fingerprint
    fp_changed = assert_0dte(changed, SESSION, source_label="zerodte/defs").fingerprint

    assert _is_sha256_hex(fp_base) and _is_sha256_hex(fp_changed)
    assert fp_base != fp_changed


# --------------------------------------------------------------------------- #
# summary()
# --------------------------------------------------------------------------- #
def test_summary_contains_label_session_and_fp_prefix() -> None:
    legs = [_leg(101, ic="C", instrument="ES")]
    prov = assert_0dte(legs, SESSION, source_label="zerodte/defs")
    s = prov.summary()
    assert "zerodte/defs" in s
    assert SESSION.isoformat() in s          # "2026-06-09"
    assert prov.fingerprint[:12] in s        # fp prefix as rendered by summary()


# --------------------------------------------------------------------------- #
# assert_session_iids_0dte — resolve RAW traded ids against the full def_map
#
# These lock the NON-TAUTOLOGICAL wiring helper and, critically, the
# unresolved-id fail-closed that a red-team audit caught regressing in the
# CALLER (an ES-only map silently dropping NQ ids instead of raising). The
# def_map KEY is the instrument_id; DefLeg carries only (expiration_ns, strike,
# instrument_class, instrument).
# --------------------------------------------------------------------------- #
def test_session_iids_happy_path_returns_full_provenance() -> None:
    # Combined ES + NQ universe, every leg 16:00 ET on SESSION. traded == all.
    def_map = {
        101: _def_leg(strike=5000.0, ic="C", instrument="ES"),
        102: _def_leg(strike=5000.0, ic="P", instrument="ES"),
        201: _def_leg(strike=18000.0, ic="C", instrument="NQ"),
        202: _def_leg(strike=18000.0, ic="P", instrument="NQ"),
    }
    traded = [101, 102, 201, 202]
    prov = assert_session_iids_0dte(
        traded, def_map, SESSION, source_label="zerodte/session-iids"
    )

    assert isinstance(prov, DataProvenance)
    assert prov.source_label == "zerodte/session-iids"
    assert prov.session_date == SESSION
    assert prov.expiry_set == (SESSION,)           # one unique expiry == session
    assert prov.n_legs == len(traded)              # 4 resolved legs
    assert prov.instruments == ("ES", "NQ")        # sorted unique underlyings
    assert prov.realized_tenor_days == pytest.approx(0.0, abs=1e-9)
    assert _is_sha256_hex(prov.fingerprint) and len(prov.fingerprint) == 64


def test_session_iids_unresolved_id_raises_load_bearing() -> None:
    # LOAD-BEARING. A traded id absent from def_map is the exact failure mode of
    # the map-scoping regression (NQ ids missing from an ES-only map). It must
    # FAIL-CLOSED, not silently drop the id.
    def_map = {
        101: _def_leg(ic="C", instrument="ES"),
        102: _def_leg(ic="P", instrument="ES"),
    }
    traded = [101, 102, 999]  # 999 has no definition
    with pytest.raises(TenorContaminationError) as ei:
        assert_session_iids_0dte(
            traded, def_map, SESSION, source_label="zerodte/session-iids"
        )
    # the message must name the offending id so the lineage break is actionable.
    assert "999" in str(ei.value)


def test_session_iids_combined_map_passes_where_es_only_map_raises() -> None:
    # Locks the scoping decision: the SAME mixed ES+NQ traded set must PASS
    # against a combined all-instrument map but RAISE against an ES-only map
    # (NQ ids unresolved). This is precisely why the fix resolves traded ids
    # against one combined universe rather than per-instrument maps.
    traded = [101, 201]  # one ES, one NQ

    combined_map = {
        101: _def_leg(strike=5000.0, ic="C", instrument="ES"),
        201: _def_leg(strike=18000.0, ic="C", instrument="NQ"),
    }
    es_only_map = {
        101: _def_leg(strike=5000.0, ic="C", instrument="ES"),
        # 201 (NQ) deliberately absent — the regression scenario.
    }

    prov = assert_session_iids_0dte(
        traded, combined_map, SESSION, source_label="zerodte/session-iids"
    )
    assert prov.expiry_set == (SESSION,)
    assert prov.instruments == ("ES", "NQ")
    assert prov.n_legs == 2

    with pytest.raises(TenorContaminationError) as ei:
        assert_session_iids_0dte(
            traded, es_only_map, SESSION, source_label="zerodte/session-iids"
        )
    assert "201" in str(ei.value)


def test_session_iids_contaminated_expiry_propagates() -> None:
    # A resolved leg whose true expiry is 9 days out must trip assert_0dte's
    # expiry check THROUGH the resolution path (proves the helper is not a
    # tautology — it feeds raw ids to the real fail-closed checks).
    nine_out = SESSION + timedelta(days=9)  # 2026-06-18
    def_map = {
        101: _def_leg(ic="C", instrument="ES", expiry=SESSION),
        102: _def_leg(ic="P", instrument="ES", expiry=nine_out),  # contaminated
    }
    traded = [101, 102]
    with pytest.raises(TenorContaminationError):
        assert_session_iids_0dte(
            traded, def_map, SESSION, source_label="zerodte/session-iids"
        )


def test_session_iids_fingerprint_is_order_independent() -> None:
    # Same traded ids + same map, different iteration order -> identical fp
    # (assert_0dte sorts legs by instrument_id before hashing).
    def_map = {
        101: _def_leg(strike=5000.0, ic="C", instrument="ES"),
        102: _def_leg(strike=5000.0, ic="P", instrument="ES"),
        201: _def_leg(strike=18000.0, ic="C", instrument="NQ"),
    }
    fp1 = assert_session_iids_0dte(
        [101, 102, 201], def_map, SESSION, source_label="zerodte/session-iids"
    ).fingerprint
    fp2 = assert_session_iids_0dte(
        [201, 101, 102], def_map, SESSION, source_label="zerodte/session-iids"
    ).fingerprint

    assert _is_sha256_hex(fp1) and len(fp1) == 64
    assert fp1 == fp2
