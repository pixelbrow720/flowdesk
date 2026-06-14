"""Unit tests for analysis.harness.run_synthetic_oi_regime_eval — the dbn-driving RUNNER.

These LOCK the LOAD-BEARING, look-ahead-free behaviour of the t-causal prior-session
OI anchor loader ``_preopen_oi_anchor`` (the anti-leak predicate), plus the runner's
pure helpers (``_cum_netflow_series``, ``_mean``). They are deterministic.

HOW THE ANCHOR LOADER IS DRIVEN WITHOUT REAL DBN FILES
======================================================
``_preopen_oi_anchor`` reads dbn inline via ``db.DBNStore.from_file(stats_path)`` and
iterates the records, but EVERY field is read through duck-typed attribute access
(``getattr(r, "stat_type", -1)``, ``r.instrument_id``, ``getattr(r, "ts_recv", 0)``,
``getattr(r, "quantity", 0)``, ``getattr(r, "ts_ref", 0)``). So the ACTUAL source
record-selection loop can be exercised by:
  1. monkeypatching the module-global ``db`` with a fake whose ``DBNStore.from_file``
     returns an in-memory list of fake stat9 records, and
  2. creating a real empty temp file so the ``os.path.exists`` gate passes.
No source refactor is performed — these tests pin the real loop, not a reimplementation.

THE ANTI-LEAK GUARANTEE (why this file exists)
==============================================
The regime predictor at minute ``t`` must use ONLY OI observed BEFORE the RTH open.
CME republishes the SAME prior-session OI intraday (~14:1x UTC) carrying the SAME
``ts_ref`` as the genuine pre-open snapshot, so ONLY ``ts_recv < open`` separates the
look-ahead-free anchor from the intraday republish. The single most important test is
``test_preopen_only_selected_over_intraday_republish`` — if the loader ever picked the
intraday record, the whole eval would silently leak.

Style mirrors test_provenance.py / test_synthetic_oi_regime_eval.py: namespace import
(no __init__.py), no test classes, ``-> None`` functions, run via the repo-root .venv
python.
"""
from __future__ import annotations

import math
import types
from datetime import date, datetime

import pytest

import analysis.harness.run_synthetic_oi_regime_eval as runner

# The runner re-imports NY (America/New_York) from run_validation; reuse it so our
# fixtures stamp times in the SAME zone the loader converts ts_ref back into.
NY = runner.NY

# A real correlated 0DTE session (matches the harness example day). Tuesday.
SESSION = date(2026, 6, 9)

# INT64_MAX — the price sentinel that lives on real stat9 OI rows. The loader must
# NEVER read `price`; we plant this to prove `quantity` is what gets anchored.
INT64_MAX = 9223372036854775807


# --------------------------------------------------------------------------- #
# fixtures / builders
# --------------------------------------------------------------------------- #
def _ns_et(y: int, m: int, d: int, hh: int, mm: int = 0) -> int:
    """Epoch-ns for ``hh:mm`` America/New_York on (y,m,d). Mirrors the on-disk stamp."""
    return int(datetime(y, m, d, hh, mm, tzinfo=NY).timestamp() * 1e9)


def _rth_open_sec(d: date = SESSION) -> int:
    """09:30 ET open as epoch-SECONDS (exactly how run_day computes it)."""
    return int(datetime(d.year, d.month, d.day, 9, 30, tzinfo=NY).timestamp())


class _Stat:
    """A minimal fake stat9 record: only the fields the loader actually reads."""

    def __init__(
        self,
        *,
        instrument_id: int,
        ts_recv: int,
        quantity: float,
        ts_ref: int = 0,
        stat_type: int = runner.STAT_OI,
        price: int | None = None,
    ) -> None:
        self.instrument_id = instrument_id
        self.ts_recv = ts_recv
        self.quantity = quantity
        self.ts_ref = ts_ref
        self.stat_type = stat_type
        if price is not None:
            self.price = price  # planted to prove it is ignored


def _call_anchor(monkeypatch, tmp_path, records, *, session_date=SESSION):
    """Drive the REAL ``_preopen_oi_anchor`` loop over in-memory ``records``.

    Creates a real temp file (so the ``os.path.exists`` gate passes) and patches the
    module-global ``db`` with a fake whose ``DBNStore.from_file`` yields ``records``.
    Returns ``(anchor, meta)`` exactly as the source does.
    """
    path = tmp_path / "statistics.dbn.zst"
    path.write_bytes(b"")  # exists -> passes the os.path.exists guard
    fake_db = types.SimpleNamespace(
        DBNStore=types.SimpleNamespace(from_file=lambda _p: list(records))
    )
    monkeypatch.setattr(runner, "db", fake_db)
    return runner._preopen_oi_anchor(str(path), session_date, _rth_open_sec(session_date))


# --------------------------------------------------------------------------- #
# 0. missing file -> empty anchor + default meta (read before any patching).
# --------------------------------------------------------------------------- #
def test_missing_file_returns_empty_anchor_and_default_meta(tmp_path) -> None:
    missing = tmp_path / "does_not_exist.dbn.zst"
    anchor, meta = runner._preopen_oi_anchor(str(missing), SESSION, _rth_open_sec())
    assert anchor == {}
    assert meta["n_preopen_iids"] == 0
    assert meta["ref_dates"] == ()
    assert meta["max_ref_gap_days"] is None
    assert meta["n_total_stat9"] == 0
    assert meta["n_preopen_records"] == 0


# --------------------------------------------------------------------------- #
# 1. THE ANTI-LEAK TEST — pre-open record chosen over the intraday republish.
#
# iid 101 has TWO stat9 rows carrying the SAME prior-session ts_ref:
#   * pre-open   ts_recv = 09:00 ET (< open), quantity = 500   <- the causal anchor
#   * intraday   ts_recv = 10:11 ET (>= open), quantity = 999  <- the republish (LEAK)
# The loader MUST pick the pre-open quantity (500) and NEVER the intraday 999.
# --------------------------------------------------------------------------- #
def test_preopen_only_selected_over_intraday_republish(monkeypatch, tmp_path) -> None:
    prior_ref = _ns_et(2026, 6, 8, 16)  # prior session settlement ref (06-08 < 06-09)
    records = [
        _Stat(instrument_id=101, ts_recv=_ns_et(2026, 6, 9, 9, 0),
              quantity=500.0, ts_ref=prior_ref),
        _Stat(instrument_id=101, ts_recv=_ns_et(2026, 6, 9, 10, 11),
              quantity=999.0, ts_ref=prior_ref),  # intraday republish — must be ignored
    ]
    anchor, meta = _call_anchor(monkeypatch, tmp_path, records)

    assert anchor == {101: 500.0}            # pre-open value, NOT 999.0
    assert 999.0 not in anchor.values()      # explicit: the leak value never surfaces
    assert meta["n_total_stat9"] == 2        # both stat9 rows seen
    assert meta["n_preopen_records"] == 1    # exactly one cleared ts_recv < open
    assert meta["n_preopen_iids"] == 1
    assert meta["ref_dates"] == (date(2026, 6, 8),)
    assert meta["max_ref_gap_days"] == 1     # 06-09 - 06-08


# --------------------------------------------------------------------------- #
# 2. BOUNDARY — ts_recv EXACTLY == open is EXCLUDED (guard is strict `<`).
#
# Two iids: 101 at exactly the open (must be excluded), 102 one ns before the open
# (must be included). Locks the strict `<` predicate. NOTE: the source uses
# `if rec >= rth_open_ns: continue`, i.e. an at-open record is dropped. This is the
# correct (non-leaky) choice; were it `<=`, the at-open 101 would be admitted and
# this test would FAIL — flagging the regression. (No deviation observed.)
# --------------------------------------------------------------------------- #
def test_boundary_ts_recv_equal_open_is_excluded_strict_lt(monkeypatch, tmp_path) -> None:
    open_ns = _rth_open_sec() * 1_000_000_000
    prior_ref = _ns_et(2026, 6, 8, 16)
    records = [
        _Stat(instrument_id=101, ts_recv=open_ns,       # EXACTLY at open -> excluded
              quantity=111.0, ts_ref=prior_ref),
        _Stat(instrument_id=102, ts_recv=open_ns - 1,   # 1 ns before open -> included
              quantity=222.0, ts_ref=prior_ref),
    ]
    anchor, meta = _call_anchor(monkeypatch, tmp_path, records)

    assert 101 not in anchor                 # at-open record rejected (strict <)
    assert anchor == {102: 222.0}
    assert meta["n_total_stat9"] == 2
    assert meta["n_preopen_records"] == 1


# --------------------------------------------------------------------------- #
# 3. DROP-DAY — an iid with ONLY intraday records yields NO anchor (the 06-08 case).
# --------------------------------------------------------------------------- #
def test_drop_day_only_intraday_yields_empty_anchor(monkeypatch, tmp_path) -> None:
    prior_ref = _ns_et(2026, 6, 8, 16)
    records = [
        _Stat(instrument_id=101, ts_recv=_ns_et(2026, 6, 9, 14, 11),  # intraday republish
              quantity=500.0, ts_ref=prior_ref),
        _Stat(instrument_id=101, ts_recv=_ns_et(2026, 6, 9, 15, 0),
              quantity=505.0, ts_ref=prior_ref),
    ]
    anchor, meta = _call_anchor(monkeypatch, tmp_path, records)

    assert anchor == {}                      # no pre-open snapshot -> day is DROPPED upstream
    assert meta["n_total_stat9"] == 2
    assert meta["n_preopen_records"] == 0    # none cleared ts_recv < open
    assert meta["n_preopen_iids"] == 0
    assert meta["ref_dates"] == ()


# --------------------------------------------------------------------------- #
# 4. QUANTITY NOT PRICE — the anchored value is `quantity`; `price` (sentinel) ignored.
# --------------------------------------------------------------------------- #
def test_anchor_value_is_quantity_not_price(monkeypatch, tmp_path) -> None:
    prior_ref = _ns_et(2026, 6, 8, 16)
    records = [
        _Stat(instrument_id=101, ts_recv=_ns_et(2026, 6, 9, 9, 0),
              quantity=750.0, ts_ref=prior_ref, price=INT64_MAX),  # price is the sentinel
    ]
    anchor, meta = _call_anchor(monkeypatch, tmp_path, records)

    assert anchor == {101: 750.0}            # quantity, NOT the INT64_MAX price sentinel
    assert float(INT64_MAX) not in anchor.values()


# --------------------------------------------------------------------------- #
# 5. PROVENANCE — a same-day or future ts_ref inside a pre-open record RAISES.
#
# A pre-open record (ts_recv < open) whose OI reference date is the session itself (or
# later) is a look-ahead/lineage contamination; the loader fail-closes with ValueError.
# --------------------------------------------------------------------------- #
def test_same_day_ts_ref_raises_lookahead_provenance(monkeypatch, tmp_path) -> None:
    same_day_ref = _ns_et(2026, 6, 9, 16)   # ts_ref ET-date == session_date
    records = [
        _Stat(instrument_id=101, ts_recv=_ns_et(2026, 6, 9, 9, 0),
              quantity=500.0, ts_ref=same_day_ref),
    ]
    with pytest.raises(ValueError) as ei:
        _call_anchor(monkeypatch, tmp_path, records)
    msg = str(ei.value)
    assert "NON-PRIOR" in msg
    assert "2026-06-09" in msg               # the offending ref date is named


def test_future_ts_ref_raises(monkeypatch, tmp_path) -> None:
    future_ref = _ns_et(2026, 6, 10, 16)    # ts_ref ET-date AFTER the session
    records = [
        _Stat(instrument_id=101, ts_recv=_ns_et(2026, 6, 9, 9, 0),
              quantity=500.0, ts_ref=future_ref),
    ]
    with pytest.raises(ValueError) as ei:
        _call_anchor(monkeypatch, tmp_path, records)
    assert "2026-06-10" in str(ei.value)


# --------------------------------------------------------------------------- #
# 6. PROVENANCE — a prior (lagged) ts_ref PASSES and meta reports the gap.
#
# Mirrors the FLAGGED real-data deviation: CME's reported OI reference trails to the
# prior *settlement* session (D-2 here), NOT the spec's literal D-1. A prior ts_ref
# must still pass (the meaningful invariant is `ref < session`, not `== D-1`).
# --------------------------------------------------------------------------- #
def test_prior_lagged_ts_ref_passes_and_reports_gap(monkeypatch, tmp_path) -> None:
    lagged_ref = _ns_et(2026, 6, 5, 16)     # 06-05 (Fri) -> gap 4 days to 06-09
    records = [
        _Stat(instrument_id=101, ts_recv=_ns_et(2026, 6, 9, 9, 0),
              quantity=500.0, ts_ref=lagged_ref),
    ]
    anchor, meta = _call_anchor(monkeypatch, tmp_path, records)
    assert anchor == {101: 500.0}
    assert meta["ref_dates"] == (date(2026, 6, 5),)
    assert meta["max_ref_gap_days"] == 4


# --------------------------------------------------------------------------- #
# 7. zero/falsy ts_ref skips the provenance check (no raise, anchor still built).
# --------------------------------------------------------------------------- #
def test_zero_ts_ref_skips_provenance_check(monkeypatch, tmp_path) -> None:
    records = [
        _Stat(instrument_id=101, ts_recv=_ns_et(2026, 6, 9, 9, 0),
              quantity=500.0, ts_ref=0),     # falsy -> `if ref:` guard skips it
    ]
    anchor, meta = _call_anchor(monkeypatch, tmp_path, records)
    assert anchor == {101: 500.0}
    assert meta["ref_dates"] == ()           # no ref contributed
    assert meta["max_ref_gap_days"] is None


# --------------------------------------------------------------------------- #
# 8. MAX ts_recv among MULTIPLE pre-open records wins (latest pre-open snapshot).
# --------------------------------------------------------------------------- #
def test_latest_preopen_ts_recv_wins(monkeypatch, tmp_path) -> None:
    prior_ref = _ns_et(2026, 6, 8, 16)
    records = [
        _Stat(instrument_id=101, ts_recv=_ns_et(2026, 6, 9, 9, 0),
              quantity=100.0, ts_ref=prior_ref),
        _Stat(instrument_id=101, ts_recv=_ns_et(2026, 6, 9, 9, 20),  # later, still pre-open
              quantity=200.0, ts_ref=prior_ref),
        _Stat(instrument_id=101, ts_recv=_ns_et(2026, 6, 9, 9, 10),
              quantity=150.0, ts_ref=prior_ref),
    ]
    anchor, meta = _call_anchor(monkeypatch, tmp_path, records)
    assert anchor == {101: 200.0}            # the 09:20 record (max ts_recv < open)
    assert meta["n_preopen_records"] == 3
    assert meta["n_preopen_iids"] == 1


# --------------------------------------------------------------------------- #
# 9. non-stat9 records are ignored (only stat_type == STAT_OI counted/used).
# --------------------------------------------------------------------------- #
def test_non_stat9_records_ignored(monkeypatch, tmp_path) -> None:
    prior_ref = _ns_et(2026, 6, 8, 16)
    records = [
        _Stat(instrument_id=101, ts_recv=_ns_et(2026, 6, 9, 9, 0),
              quantity=500.0, ts_ref=prior_ref),
        _Stat(instrument_id=101, ts_recv=_ns_et(2026, 6, 9, 9, 5),
              quantity=42.0, ts_ref=prior_ref, stat_type=8),  # NOT open-interest
    ]
    anchor, meta = _call_anchor(monkeypatch, tmp_path, records)
    assert anchor == {101: 500.0}            # the stat8 row never participates
    assert meta["n_total_stat9"] == 1        # stat8 excluded from the stat9 tally
    assert meta["n_preopen_records"] == 1


# --------------------------------------------------------------------------- #
# 10. multiple iids each anchored independently from their own latest pre-open row.
# --------------------------------------------------------------------------- #
def test_multiple_iids_anchored_independently(monkeypatch, tmp_path) -> None:
    prior_ref = _ns_et(2026, 6, 8, 16)
    records = [
        _Stat(instrument_id=101, ts_recv=_ns_et(2026, 6, 9, 9, 0),
              quantity=500.0, ts_ref=prior_ref),
        _Stat(instrument_id=202, ts_recv=_ns_et(2026, 6, 9, 9, 15),
              quantity=300.0, ts_ref=prior_ref),
        _Stat(instrument_id=202, ts_recv=_ns_et(2026, 6, 9, 12, 0),   # intraday for 202
              quantity=777.0, ts_ref=prior_ref),
    ]
    anchor, meta = _call_anchor(monkeypatch, tmp_path, records)
    assert anchor == {101: 500.0, 202: 300.0}   # 202 keeps its pre-open, not 777
    assert meta["n_preopen_iids"] == 2
    assert meta["n_total_stat9"] == 3
    assert meta["n_preopen_records"] == 2


# --------------------------------------------------------------------------- #
# PURE-CORE RUNNER HELPERS (no dbn) — _cum_netflow_series + _mean.
# --------------------------------------------------------------------------- #
def test_cum_netflow_series_causal_and_snapshot_is_a_copy() -> None:
    # trades_min entries: (minute, strike, is_call, size, _trade_sign). The 5th field
    # is IGNORED here — _cum_netflow_series uses the PARALLEL sign_list.
    #
    # T-CAUSAL CONTRACT (look-ahead fix 3c): out[t] is snapshotted at the START-of-minute-t
    # boundary grid_secs[t] == F_t's exact timestamp, taken BEFORE minute t's OWN trades are
    # folded into the running net-flow. So out[t] carries ONLY flow from minutes STRICTLY
    # BEFORE t (ts < grid_secs[t]); a minute-m trade registers in out[t] only for t > m, never
    # within/before its own minute. Hence out[0] == {} ALWAYS (anchor-only: no flow strictly
    # before the first minute's start). The OLD leaky fold folded minute-t's trades BEFORE the
    # snapshot, so out[0] wrongly carried the minute-0 trade; the asserts below now FAIL if
    # anyone reverts to that <=t fold — this test ENCODES the anti-leak guarantee.
    trades_min = [
        (0, 5000.0, True, 2.0, +1),
        (1, 5000.0, True, 3.0, +1),
        (2, 5010.0, False, 1.0, +1),
    ]
    sign_list = [+1, -1, +1]                 # the signs actually applied
    solvable = {0, 1, 2}                     # snapshot each minute to watch flow roll FORWARD

    out = runner._cum_netflow_series(trades_min, sign_list, solvable)

    # ANTI-LEAK: minute-0's own trade is NOT in out[0]; the t=0 snapshot is anchor-only (flow=0).
    assert out[0] == {}
    # ...but that minute-0 trade DOES surface exactly ONE minute later: out[1] == +1*2 = 2.0.
    # This is the value the OLD (leaky) test pinned at out[0]; the fix pushes it to out[1],
    # proving flow registers STRICTLY AFTER its minute, never within/before F_t.
    assert out[1] == {(5000.0, True): 2.0}
    # minute 2: cumulative through the END of minute 1 = +2 + (-1*3) = -1.0. Minute-2's OWN
    # trade (5010,False) is EXCLUDED (snapshot-before-fold) — it would first appear at out[3].
    assert out[2] == {(5000.0, True): -1.0}
    assert (5010.0, False) not in out[2]     # minute-2 flow never leaks into its own snapshot
    # SNAPSHOT-IS-A-COPY: out[1] was frozen at t=1 and is NOT retroactively mutated by the later
    # (t>=1) fold that drove running to -1.0 — distinct dict objects, value held constant.
    assert out[1] is not out[2]
    assert out[1] == {(5000.0, True): 2.0}


def test_cum_netflow_series_sign_list_overrides_trade_sign() -> None:
    # A single minute-0 trade whose intrinsic sign is +1, but sign_list assigns -1 (the
    # aggressor-sign-shuffle null mechanism). The applied sign must be the sign_list one.
    #
    # T-CAUSAL CONTRACT: the minute-0 trade is folded AFTER out[0] is snapshotted, so it CANNOT
    # appear in out[0] (== {}); it first surfaces at out[1]. We snapshot minute 1 too so the
    # applied sign is observable. The OLD leaky fold put -4.0 in out[0] — that now FAILS,
    # encoding the anti-leak guarantee alongside the sign-override check.
    trades_min = [(0, 5000.0, True, 4.0, +1)]
    out = runner._cum_netflow_series(trades_min, [-1], {0, 1})
    # ANTI-LEAK: nothing registers strictly before minute-0's start.
    assert out[0] == {}
    # The trade registers at out[1] (strictly AFTER its minute) with the sign_list sign applied:
    # -1*4 = -4.0, NOT the intrinsic +1 (which would be +4.0).
    assert out[1] == {(5000.0, True): -4.0}


def test_cum_netflow_series_empty_when_no_solvable_minutes() -> None:
    trades_min = [(0, 5000.0, True, 2.0, +1)]
    assert runner._cum_netflow_series(trades_min, [+1], set()) == {}


def test_mean_filters_none_and_nan() -> None:
    assert runner._mean([1.0, 2.0, 3.0]) == pytest.approx(2.0, abs=1e-12)
    assert runner._mean([1.0, None, 3.0]) == pytest.approx(2.0, abs=1e-12)
    assert runner._mean([1.0, float("nan"), 3.0]) == pytest.approx(2.0, abs=1e-12)


def test_mean_empty_and_all_invalid_is_nan() -> None:
    assert math.isnan(runner._mean([]))
    assert math.isnan(runner._mean([None, float("nan")]))
