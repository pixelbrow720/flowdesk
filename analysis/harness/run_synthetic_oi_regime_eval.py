"""Synthetic-OI VOLATILITY-REGIME predictive-eval RUNNER (reads data/raw/zerodte/, zero API).

STEP 2 of 2 — the dbn-driving RUNNER for the PURE core in
``analysis.harness.synthetic_oi_regime_eval``. ADDITIVE sibling of
``run_validation.py`` / ``run_hiro_eval.py`` / ``run_synthetic_oi_eval.py``: it touches NONE
of their metric paths and adds nothing to the engine/worker/Snapshot/schema. It answers
the ONE EXPLORATORY, t-causal, look-ahead-free question (see ``synthetic_oi_regime_eval.py``):

    Does the SIGN of net synthetic-dealer-gamma (the VOLATILITY-REGIME label) at minute ``t``
    separate the SIGN-FREE realized forward MOVE ``|F_{t+k} − F_t|`` — short-gamma minutes
    moving MORE than long-gamma minutes — and does it do so BEYOND the regime-label-shuffle,
    aggressor-sign-shuffle, and flow-only nulls?

The load-bearing T-CAUSAL anchor (the expert-pinned correctness point)
======================================================================
The regime PREDICTOR at minute ``t`` is built from a PRIOR-session OI anchor + aggressor
flow accumulated STRICTLY BEFORE ``F_t``'s timestamp (``ts < grid_secs[t] = open + t·60``,
i.e. trades in minutes ``< t``); the OUTCOME ``|F_{t+k} − F_t|`` is realized strictly later
(``> t``). The forward ``F_t`` is the parity forward AT the start-of-minute-``t`` instant
``grid_secs[t]``, so snapshotting flow ``< grid_secs[t]`` keeps the predictor strictly at-or-
before ``F_t`` and leaves NO contemporaneous flow shared with the outcome (the closed
look-ahead surface — see :func:`_cum_netflow_series`). The OI anchor is loaded by
:func:`_preopen_oi_anchor`, which for each iid takes the
``stat_type==9`` (open-interest) ``quantity`` from the record with the MAXIMUM ``ts_recv``
SUBJECT TO ``ts_recv < RTH_open`` (09:30 ET = 13:30 UTC on these June/EDT dates). Using
``max(ts_recv)`` UNCONDITIONALLY would leak: CME republishes the SAME prior-session OI
intraday (~14:1x UTC) carrying the SAME ``ts_ref`` as the genuine pre-open snapshot, so ONLY
``ts_recv < open`` distinguishes the look-ahead-free anchor from the intraday republish. This
predicate is NEVER relaxed: a day with no pre-open ``stat9`` (only an intraday republish) gets
an EMPTY anchor and is DROPPED, never salvaged by widening the predicate.

PROVENANCE NOTE — spec ``ts_ref == D-1`` deviation (FLAGGED, not silently changed)
----------------------------------------------------------------------------------
The build spec assumed the chosen record's ``ts_ref`` ET-date is the day before the session
(``D-1``). On the REAL on-disk data it is the *lagged prior settlement session* — D-2 /
prior-business-session (06-05→06-03, 06-09→06-07, 06-10→06-08) — because CME's reported OI
reference date trails by a settlement cycle. A literal ``== D-1`` raise would false-reject
EVERY usable day. The structural guarantee the spec relies on is unaffected (pre-open and
intraday republish share the same ``ts_ref``; only ``ts_recv`` separates them), so the
fail-closed provenance invariant enforced here is the meaningful one: the anchor's ``ts_ref``
ET-date must be a PRIOR session (``< session_date``); a same-day-or-future ``ts_ref`` raises
(that WOULD be a leak). The actual ``ts_ref`` + day-gap is printed for every used day.

EXPLORATORY: 3 USABLE correlated 0DTE days (06-08 dropped — no pre-open anchor), an
OPTION-DERIVED parity forward (NOT a futures price), descriptive only, NOT predictive-validated.
The HEADLINE is the control GAP, never the raw separation; at n<5 the verdict is UNDETERMINED
by construction. Synthetic-OI is NOT claimed to predict volatility.

Run from the repo root (engine on the path):
    PYTHONPATH=services/engine/src .venv/Scripts/python.exe analysis/harness/run_synthetic_oi_regime_eval.py
Requires the gitignored data/raw/zerodte/ + data/raw/_probe/ pull on disk.
"""
from __future__ import annotations

import math
import os
import sys
from collections import defaultdict
from dataclasses import replace
from datetime import datetime, timezone

sys.path.insert(0, os.path.join("services", "engine", "src"))
sys.path.insert(0, ".")  # so `analysis.harness.*` imports when run as a script

import databento as db  # noqa: E402

from analysis.harness.provenance import assert_session_iids_0dte  # noqa: E402
from analysis.harness.synthetic_oi_eval import (  # noqa: E402
    synthetic_gex_by_strike,
)
from analysis.harness.synthetic_oi_regime_eval import (  # noqa: E402
    DEFAULT_SHUFFLE_SEEDS,
    headline_gap,
    realized_move,
    regime_separation,
    regime_sign,
)
# Reuse the sibling runners' data-loading machinery VERBATIM (no duplication, no edits there):
# build_minute_forwards (dense 390-min RTH parity-forward grid), N_MINUTES, K_SET from the
# FLUX runner; MIN_NONTHIN + the per-day sign / single-day-domination tally from the synth-OI
# runner; load_defs / flat-def-map / raw-iid / quotes_at / constants from run_validation.
from analysis.harness.run_hiro_eval import (  # noqa: E402
    K_SET,
    N_MINUTES,
    build_minute_forwards,
)
from analysis.harness.run_synthetic_oi_eval import (  # noqa: E402
    MIN_NONTHIN,
    _gap_sign_tally,
)
from analysis.harness.run_validation import (  # noqa: E402
    DAYS,
    DEF,
    NY,
    RATE,
    STEP,
    ZERO,
    _aggressor_sign,
    _flat_def_map_all,
    _raw_settled_iids,
    _raw_traded_iids,
    load_defs,
    quotes_at,
)
from engine.snapshot import (  # noqa: E402
    MULTIPLIER,
    ChainQuote,
    _solve_chain,
    t_expiry_from_clock,
)

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

#: Operating weight for the flow term (w=1 fully adds (−flow); the OI anchor is the stock term).
W_OPERATING = 1.0

#: stat_type for open-interest in the statistics dbn (CME OI). Same const as run_validation.STAT_OI.
STAT_OI = 9

#: A "regime edge" claim needs more INDEPENDENT days than the 3 usable correlated 0DTE sessions
#: on disk. With n_days < this, even a consistent above-threshold gap is honestly UNDETERMINED
#: (suggestive but underpowered). Mirrors run_hiro_eval / run_synthetic_oi_eval. At n=3 a YES is
#: UNREACHABLE by construction — that is the honest expected result, not a failure.
MIN_DAYS_FOR_EDGE = 5

#: A (day, instrument) with fewer than this many SOLVABLE + DIRECTIONAL minutes is too sparse to
#: score a separation (the NQ case). Reported as a STOP-condition, marked UNDETERMINED, never faked.
MIN_SCORED_MINUTES = 20


def _preopen_oi_anchor(stats_path: str, session_date, rth_open_sec: int) -> dict:
    """T-CAUSAL prior-session OI anchor: {iid -> quantity} from the latest PRE-OPEN stat9.

    THE load-bearing look-ahead-free loader. For each ``instrument_id`` it takes the
    open-interest ``quantity`` (NOT ``price`` — that field is the INT64_MAX sentinel on stat9
    OI rows) from the ``stat_type==9`` record with the MAXIMUM ``ts_recv`` **subject to the hard
    predicate** ::

        ts_recv  <  rth_open            # 09:30 ET == 13:30 UTC on these June/EDT dates

    so the anchor is a snapshot of OI fixed BEFORE the session opens. ``max(ts_recv)`` WITHOUT
    this predicate would leak: CME republishes the same prior-session OI intraday (~14:1x UTC)
    with the SAME ``ts_ref`` as the genuine pre-open record, and only ``ts_recv`` separates them.
    The predicate is NEVER relaxed — if no record satisfies it (e.g. 06-08, whose only stat9 is
    the ~14:11 UTC intraday republish), this returns ``{}`` and the caller DROPS the day.

    PROVENANCE (fail-closed, see module docstring on the spec ``D-1`` deviation): the chosen
    records' ``ts_ref`` ET-dates must all be a PRIOR session (``< session_date``). A same-day or
    future ``ts_ref`` is itself a leak signal and RAISES. The actual ``ts_ref`` set + day-gap is
    returned alongside the anchor for the caller to log. Missing file -> ``({}, meta)``.
    """
    meta = {"n_preopen_iids": 0, "ref_dates": (), "max_ref_gap_days": None,
            "n_total_stat9": 0, "n_preopen_records": 0}
    if not os.path.exists(stats_path):
        return {}, meta
    rth_open_ns = int(rth_open_sec) * 1_000_000_000
    # iid -> (best_ts_recv_ns, quantity, ts_ref_ns) for the latest PRE-OPEN stat9 record.
    best: dict = {}
    n_total = 0
    n_preopen = 0
    for r in db.DBNStore.from_file(stats_path):
        if int(getattr(r, "stat_type", -1)) != STAT_OI:
            continue
        n_total += 1
        rec = int(getattr(r, "ts_recv", 0) or 0)
        if rec >= rth_open_ns:
            continue  # HARD leak guard: only OI observed strictly BEFORE the open is causal.
        n_preopen += 1
        iid = int(r.instrument_id)
        qty = float(getattr(r, "quantity", 0) or 0)
        ref = int(getattr(r, "ts_ref", 0) or 0)
        prev = best.get(iid)
        if prev is None or rec > prev[0]:
            best[iid] = (rec, qty, ref)

    meta["n_total_stat9"] = n_total
    meta["n_preopen_records"] = n_preopen
    if not best:
        return {}, meta

    # ---- PROVENANCE: every chosen record's ts_ref must be a PRIOR session (fail-closed) ----
    ref_dates: set = set()
    for _rec, _qty, ref in best.values():
        if ref:
            ref_et = datetime.fromtimestamp(ref / 1e9, tz=timezone.utc).astimezone(NY).date()
            ref_dates.add(ref_et)
    bad = sorted(d for d in ref_dates if d >= session_date)
    if bad:
        raise ValueError(
            f"_preopen_oi_anchor: pre-open OI anchor for session {session_date.isoformat()} "
            f"carries a NON-PRIOR ts_ref {[d.isoformat() for d in bad]} (>= session date). "
            f"A same-day/future OI reference inside a pre-open record is a look-ahead/lineage "
            f"contamination — refusing to anchor (stats_path={stats_path!r})."
        )
    sorted_refs = tuple(sorted(ref_dates))
    max_gap = (max((session_date - d).days for d in ref_dates) if ref_dates else None)
    meta["n_preopen_iids"] = len(best)
    meta["ref_dates"] = sorted_refs
    meta["max_ref_gap_days"] = max_gap
    anchor = {iid: qty for iid, (_rec, qty, _ref) in best.items()}
    return anchor, meta


def load_flow_trades_min(path: str, legs: dict, rth_open_sec: int) -> list:
    """Stream the trades dbn -> chronological list of ``(minute, strike, is_call, size, sign)``.

    Mirrors ``run_validation.flow_and_vol`` / ``run_synthetic_oi_eval.load_flow_trades`` (same
    ``DBNStore.from_file`` loop, ``ts_event``/``size``/``side`` fields, ``ts >= rth_open`` filter,
    native CME aggressor sign via ``run_validation._aggressor_sign``) but tags each trade with its
    0-based RTH minute index so the cumulative net-flow STRICTLY BEFORE ``grid_secs[t]`` (trades
    in minutes ``< t``) can be snapshotted on the per-minute grid by :func:`_cum_netflow_series`.
    Neutral (sign 0) trades are KEPT so the aggressor-sign shuffle's sign multiset
    matches the real tape. Missing file -> [].
    """
    if not os.path.exists(path):
        return []
    out: list = []
    for r in db.DBNStore.from_file(path):
        iid = r.instrument_id
        if iid not in legs:
            continue
        ts_sec = int(getattr(r, "ts_event", 0) / 1e9)
        if ts_sec < rth_open_sec:
            continue
        minute = int((ts_sec - rth_open_sec) // 60)
        if minute < 0 or minute >= N_MINUTES:
            continue
        sz = float(getattr(r, "size", 0) or 0)
        if sz <= 0.0:
            continue
        sgn = _aggressor_sign(getattr(r, "side", "N"))
        otype, k, _ed = legs[iid]
        out.append((minute, float(k), otype == "call", sz, sgn))
    out.sort(key=lambda e: e[0])
    return out


def _minute_rows(instr: str, legs: dict, mids: dict, anchor_oi: dict,
                 fwd: float, t_exp: float) -> list:
    """Solve one minute's chain with the PRE-OPEN OI anchor seeded onto each leg.

    Mirrors ``run_synthetic_oi_eval._eod_quotes_with_oi`` quote construction (OI seeded onto the
    ChainQuote, vol left 0) but takes the already-validated parity ``fwd`` (built by
    ``build_minute_forwards``) instead of recomputing/refiltering it — so the predictor's scale
    forward is byte-identical to the outcome grid's ``forwards[t]``. OI does NOT affect the solved
    gamma (gamma comes from the mid/IV), so seeding the prior-session OI changes only the position
    model, never the greeks. Returns the solved ``ChainRow`` list (callers count non-thin rows).
    """
    bystrike: dict = defaultdict(dict)
    for iid, (otype, k, _ed) in legs.items():
        if iid in mids:
            bystrike[k][otype] = (mids[iid], float(anchor_oi.get(iid, 0.0)))
    quotes = []
    for k, v in sorted(bystrike.items()):
        cm = v.get("call")
        pm = v.get("put")
        quotes.append(ChainQuote(
            strike=k,
            call_mid=cm[0] if cm else None, put_mid=pm[0] if pm else None,
            call_oi=cm[1] if cm else 0.0, put_oi=pm[1] if pm else 0.0,
            t_expiry=t_exp,
        ))
    return _solve_chain(quotes, fwd, RATE, t_exp)


def _cum_netflow_series(trades_min: list, sign_list: list, solvable: set) -> dict:
    """{minute -> {(strike,is_call): Σ sign·size for trades STRICTLY BEFORE minute t}} at solvable t.

    ``trades_min`` is the ``(minute, strike, is_call, size, _sign)`` list; ``sign_list`` is the
    PARALLEL per-trade sign assignment (the real signs, or a seeded permutation for the
    aggressor-sign-shuffle null). Walking minutes 0..N keeps the build O(trades + minutes) and
    snapshots a copy of the running net-flow only at minutes we actually score. This is the SAME
    cumulative ``Σ aggressor_sign·size since open`` quantity ``run_validation.flow_and_vol``
    accumulates and ``engine.synthetic_oi.q_per_leg`` consumes.

    T-CAUSAL CUTOFF (look-ahead fix 3c): the snapshot for minute ``t`` is taken at the
    START-of-minute-``t`` boundary ``grid_secs[t] = open + t·60`` — which is the EXACT timestamp
    of the parity forward ``F_t`` the outcome ``|F_{t+k} − F_t|`` is measured from — BEFORE
    minute ``t``'s own trades are folded in. So ``out[t]`` includes ONLY trades with
    ``ts < grid_secs[t]`` (``minute < t``; cumulative through the END of minute ``t-1``). Minute
    ``t``'s trades fall in ``[grid_secs[t], grid_secs[t+1])`` — AT-OR-AFTER ``F_t``'s instant —
    and are intentionally EXCLUDED, so the predictor uses only information ``≤ F_t`` while the
    outcome uses ``F_{t+k} > F_t``: no contemporaneous predictor/outcome overlap. The first
    scored minute ``t=0`` is therefore ANCHOR-ONLY (``out[0] == {}`` => flow=0), which is correct
    and handled cleanly downstream (``q_per_leg`` reads ``net_flow.get(...,0.0)``).
    """
    by_min: dict = defaultdict(list)
    for (mi, k, is_call, sz, _sg), sg2 in zip(trades_min, sign_list):
        by_min[mi].append((k, is_call, sz, sg2))
    running: dict = {}
    out: dict = {}
    for t in range(N_MINUTES):
        # T-CAUSAL CUTOFF (look-ahead fix 3c): snapshot at the START-of-minute-t boundary
        # grid_secs[t] = open + t*60 (== F_t's exact timestamp) BEFORE folding minute t's OWN
        # trades. So out[t] carries only flow with ts < grid_secs[t] (minute < t; cumulative
        # through the END of minute t-1). Minute t's trades live in [grid_secs[t], grid_secs[t+1]),
        # i.e. AT-OR-AFTER F_t, and must NOT enter the predictor. out[0] = {} (anchor-only, flow=0).
        if t in solvable:
            out[t] = dict(running)
        for (k, is_call, sz, sg2) in by_min.get(t, []):
            key = (k, is_call)
            running[key] = running.get(key, 0.0) + float(sg2) * float(sz)
    return out


def _regimes_from(predictors: dict, solvable_sorted: list, cum_series: dict,
                  M: float, *, use_oi: bool) -> list:
    """Regime-sign series aligned to ``solvable_sorted`` from a cum-flow series + the cached rows.

    ``use_oi=True`` uses the OI-anchored rows (the real regime + the aggressor-sign-shuffle null,
    which keep the prior-session OI stock anchor); ``use_oi=False`` uses the OI-zeroed rows (the
    FLOW-ONLY arm — same solved gammas, anchor removed) so the regime is driven by ``(−flow)·w``
    alone. The per-minute synthetic-GEX profile is the sign-free engine-backed
    :func:`synthetic_gex_by_strike`; only its SIGN (:func:`regime_sign`) enters the metric.
    """
    regs: list = []
    for t in solvable_sorted:
        rows, rows_no_oi, F_t = predictors[t]
        src = rows if use_oi else rows_no_oi
        prof = synthetic_gex_by_strike(src, cum_series[t], M, F_t, W_OPERATING)
        regs.append(regime_sign(prof))
    return regs


def _mean(vals: list) -> float:
    clean = [v for v in vals
             if v is not None and not (isinstance(v, float) and math.isnan(v))]
    return sum(clean) / len(clean) if clean else float("nan")


def run_day(instr: str, day: str, defs: dict) -> dict | None:
    """One (day, instrument) regime-eval row, or None when skipped before scoring."""
    d = datetime.strptime(day, "%Y-%m-%d")
    session_date = d.date()

    # ---- TENOR PROVENANCE GUARD (fail-closed, BEFORE any anchor/metric) -----------------
    # SAME chokepoint as run_validation/run_hiro_eval/run_synthetic_oi_eval: resolve the RAW
    # traded∪settled id population (no iidset filter) against the COMBINED ES+NQ definition map;
    # a non-session/unresolved id raises. Empty population -> loud skip (data absent).
    flat_def_map = _flat_def_map_all(defs)
    traded_settled_iids = (
        _raw_traded_iids(f"{ZERO}/trades/{day}.dbn.zst")
        | _raw_settled_iids(f"{ZERO}/statistics/{day}.dbn.zst")
    )
    if not traded_settled_iids:
        print(f"  [provenance] WARN no traded/settled iids for {day} — skipping")
        return None
    prov = assert_session_iids_0dte(
        traded_settled_iids, flat_def_map, session_date, source_label=f"zerodte/{day}",
    )
    print(f"  [provenance] {prov.summary()}")

    legs = defs[instr].get(day, {})
    if not legs:
        return None
    iidset = set(legs)

    rth_open = int(datetime(d.year, d.month, d.day, 9, 30, tzinfo=NY).timestamp())

    # ---- T-CAUSAL PRIOR-SESSION OI ANCHOR (the load-bearing, look-ahead-free loader) -----
    anchor_oi, anchor_meta = _preopen_oi_anchor(
        f"{ZERO}/statistics/{day}.dbn.zst", session_date, rth_open
    )
    if not anchor_oi:
        # STOP-CONDITION (do NOT relax ts_recv<open to salvage): no pre-open OI snapshot exists
        # for this session (only an intraday republish). Drop with a printed reason.
        print(f"  {day} {instr}: DROPPED — no pre-open OI anchor "
              f"(ts_recv<open empty; {anchor_meta['n_total_stat9']} stat9 rows, "
              f"{anchor_meta['n_preopen_records']} pre-open) -> dropped")
        return {"day": day, "instr": instr, "status": "no-preopen-anchor"}
    ref_str = ",".join(x.isoformat() for x in anchor_meta["ref_dates"])
    print(f"  [oi-anchor] {day} {instr}: {anchor_meta['n_preopen_iids']} legs anchored from "
          f"PRE-OPEN stat9 (ts_recv<open); ts_ref={{{ref_str}}} "
          f"(prior session, gap={anchor_meta['max_ref_gap_days']}d; spec said D-1 — see note)")

    # ---- OUTCOME grid: dense 390-min RTH parity forward (reused VERBATIM from run_hiro_eval).
    minute_forwards = build_minute_forwards(
        instr, legs, iidset, f"{ZERO}/bbo-1m/{day}.dbn.zst", rth_open
    )
    n_forward = sum(1 for f in minute_forwards if f is not None)
    if n_forward == 0:
        print(f"  {day} {instr}: insufficient-forward-grid (n_forward=0)")
        return {"day": day, "instr": instr, "status": "no-forward-grid"}

    # ---- PER-MINUTE PREDICTOR: solve chain w/ OI anchor at each minute that clears MIN_NONTHIN.
    # Per-minute mids on the SAME minute grid build_minute_forwards used (causal: start-of-minute).
    grid_secs = [rth_open + t * 60 for t in range(N_MINUTES)]
    q = quotes_at(f"{ZERO}/bbo-1m/{day}.dbn.zst", iidset, grid_secs)
    M = MULTIPLIER[instr]

    predictors: dict = {}  # minute -> (rows_with_oi, rows_no_oi, F_t)
    n_long = n_short = n_zero = 0
    for t in range(N_MINUTES):
        F_t = minute_forwards[t]
        if F_t is None:
            continue  # outcome/scale forward ill-conditioned this minute -> unscored.
        mids = q.get(grid_secs[t], {})
        if not mids:
            continue
        ts = datetime.fromtimestamp(grid_secs[t], tz=timezone.utc)
        t_exp = t_expiry_from_clock(ts)
        rows = _minute_rows(instr, legs, mids, anchor_oi, F_t, t_exp)
        if sum(1 for r in rows if not r.thin) < MIN_NONTHIN:
            continue  # chain too thin to solve a meaningful gamma profile -> unscored.
        rows_no_oi = [replace(r, call_oi=0.0, put_oi=0.0) for r in rows]
        predictors[t] = (rows, rows_no_oi, F_t)

    solvable = sorted(predictors)
    if not solvable:
        print(f"  {day} {instr}: no solvable minutes (chain never cleared MIN_NONTHIN)")
        return {"day": day, "instr": instr, "status": "no-solvable-minutes",
                "n_forward": n_forward}

    # ---- cumulative signed flow series (real + per-seed aggressor-sign shuffle) -----------
    trades_min = load_flow_trades_min(f"{ZERO}/trades/{day}.dbn.zst", legs, rth_open)
    real_signs = [tr[4] for tr in trades_min]
    solvable_set = set(solvable)
    cum_real = _cum_netflow_series(trades_min, real_signs, solvable_set)

    # REAL regimes (OI anchor + flow) and the FLOW-ONLY regimes (anchor zeroed, same gammas).
    regimes = _regimes_from(predictors, solvable, cum_real, M, use_oi=True)
    regimes_flowonly = _regimes_from(predictors, solvable, cum_real, M, use_oi=False)
    for r in regimes:
        if r > 0:
            n_long += 1
        elif r < 0:
            n_short += 1
        else:
            n_zero += 1

    # aggressor-sign-shuffle regimes: permute per-trade sign (SAME multiset), keep anchor+gammas.
    import random as _random
    sign_shuffle_regimes = []
    for sd in DEFAULT_SHUFFLE_SEEDS:
        perm = list(real_signs)
        _random.Random(sd).shuffle(perm)
        cum_s = _cum_netflow_series(trades_min, perm, solvable_set)
        sign_shuffle_regimes.append(_regimes_from(predictors, solvable, cum_s, M, use_oi=True))

    # ---- METRIC per k (pure core): separation + 3 control gaps -----------------------------
    per_k: dict = {}
    for k in K_SET:
        moves = [realized_move(minute_forwards, t, k) for t in solvable]

        sep_panel = regime_separation(regimes, moves)
        # GAP 1 (HEADLINE): regime-LABEL shuffle null (the pure-core control).
        hg = headline_gap(regimes, moves, seeds=DEFAULT_SHUFFLE_SEEDS)

        # GAP 2: aggressor-SIGN shuffle null — regimes rebuilt from sign-shuffled flow + SAME
        # anchor + SAME gammas; gap = sep_real − mean(sep over sign-shuffle seeds).
        sign_seps = [regime_separation(rs, moves)["sep"] for rs in sign_shuffle_regimes]
        sign_seps_valid = [s for s in sign_seps if s is not None]
        sign_shuffle_mean = _mean(sign_seps_valid) if sign_seps_valid else float("nan")
        sep_real = sep_panel["sep"]
        sign_shuffle_gap = (
            sep_real - sign_shuffle_mean
            if (sep_real is not None and not math.isnan(sign_shuffle_mean))
            else float("nan")
        )

        # GAP 3: FLOW-ONLY arm — its OWN regime-label-shuffle headline gap (anchor removed),
        # isolating whether the FLOW (not the OI stock) carries the separation.
        hg_flow = headline_gap(regimes_flowonly, moves, seeds=DEFAULT_SHUFFLE_SEEDS)

        per_k[k] = {
            "k": k,
            "sep": sep_real,
            "sep_reason": sep_panel["reason"],
            "n_scored": sep_panel["n_scored"],
            "n_short_scored": sep_panel["n_short"],
            "n_long_scored": sep_panel["n_long"],
            "mean_short": sep_panel["mean_short"],
            "mean_long": sep_panel["mean_long"],
            # GAP 1 (headline, regime-label shuffle)
            "headline_gap": hg["headline_gap"],
            "sep_shuffle_mean": hg["sep_shuffle_mean"],
            # GAP 2 (aggressor-sign shuffle)
            "sign_shuffle_gap": sign_shuffle_gap,
            "sign_shuffle_sep_mean": sign_shuffle_mean,
            # GAP 3 (flow-only arm, regime-label shuffle on flow-only regimes)
            "flowonly_headline_gap": hg_flow["headline_gap"],
            "flowonly_sep": hg_flow["sep_real"],
        }

    n_scored_directional = n_long + n_short
    status = "ok"
    if n_scored_directional < MIN_SCORED_MINUTES:
        status = "sparse"  # STOP-condition: too few directional minutes (the NQ case).
    if n_long == 0 or n_short == 0:
        status = "no-regime-variation"  # STOP: regime never flips -> zero separation possible.

    return {
        "day": day, "instr": instr, "status": status,
        "n_forward": n_forward, "n_solvable": len(solvable),
        "n_long": n_long, "n_short": n_short, "n_zero": n_zero,
        "n_trades": len(trades_min), "n_legs": len(legs),
        "anchor_legs": anchor_meta["n_preopen_iids"],
        "ref_gap_days": anchor_meta["max_ref_gap_days"],
        "per_k": per_k,
    }


def _f(x, p: int = 3) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "  n/a"
    return f"{x:+.{p}f}"


def _fmt_k(m: dict) -> str:
    """One-line per-k rendering, leading with the HEADLINE GAP (control-gap is the headline)."""
    reason = f" [{m['sep_reason']}]" if m["sep_reason"] else ""
    return (f"k={m['k']:>2}  HEADLINE_gap(label-shuf)={_f(m['headline_gap'])}  "
            f"signshuf_gap={_f(m['sign_shuffle_gap'])}  flowonly_gap={_f(m['flowonly_headline_gap'])}"
            f"  ||  sep={_f(m['sep'])}{reason} "
            f"(short n={m['n_short_scored']} mean={_f(m['mean_short'], 1)} / "
            f"long n={m['n_long_scored']} mean={_f(m['mean_long'], 1)})  n_scored={m['n_scored']}")


def main() -> int:
    if not os.path.exists(DEF):
        print(f"ERROR: definition file missing: {DEF}\n"
              f"This harness needs the gitignored data/raw/ pull on disk.")
        return 2

    print("==== SYNTHETIC-OI VOLATILITY-REGIME PREDICTIVE EVAL — t-causal, look-ahead-free ====")
    print("*** EXPLORATORY. The regime PREDICTOR at t uses a PRE-OPEN (prior-session) OI anchor")
    print("    + aggressor flow accumulated STRICTLY BEFORE F_t (ts<open+t*60, minutes <t); the")
    print("    OUTCOME |F_{t+k}-F_t| is realized >t (no contemporaneous predictor/outcome overlap).")
    print("    LONG-gamma (Σgex>0) => dealers SUPPRESS vol (small moves); SHORT-gamma (Σgex<0)")
    print("    => dealers AMPLIFY vol (large moves). sep>0 = short-gamma minutes move MORE. ***")
    print("THE CONTROL-GAP IS THE HEADLINE, NOT THE RAW sep. Three nulls reported per k:")
    print("  (1) regime-LABEL shuffle (HEADLINE_gap); (2) aggressor-SIGN shuffle (signshuf_gap,")
    print("      same anchor+gammas, random flow direction); (3) FLOW-ONLY arm (anchor=0).")
    print(f"  Shuffle seeds: {list(DEFAULT_SHUFFLE_SEEDS)}.")
    print("OI anchor predicate: stat9 quantity at MAX ts_recv s.t. ts_recv<open (NEVER relaxed);")
    print("a day with no pre-open stat9 is DROPPED. ts_ref provenance = prior session (fail-closed;")
    print("spec said D-1 but real CME ts_ref lags to D-2/prior-session — FLAGGED, not D-1).\n")

    defs = load_defs()
    rows = []
    for day in DAYS:
        for instr in ("ES", "NQ"):
            res = run_day(instr, day, defs)
            if res is None:
                continue
            rows.append(res)
            if res["status"] in ("no-preopen-anchor",):
                continue  # already printed the drop reason
            if res["status"] in ("no-forward-grid", "no-solvable-minutes"):
                print(f"  {day} {instr}: {res['status']}")
                continue
            flag = ""
            if res["status"] == "sparse":
                flag = "  [SPARSE -> UNDETERMINED]"
            elif res["status"] == "no-regime-variation":
                flag = "  [NO REGIME FLIP -> zero separation]"
            print(f"  {day} {instr}  solvable={res['n_solvable']}min  "
                  f"regime split: long={res['n_long']} short={res['n_short']} "
                  f"flat={res['n_zero']}  (legs={res['n_legs']} anchored={res['anchor_legs']} "
                  f"trades={res['n_trades']}){flag}")
            if res["status"] == "no-regime-variation":
                print(f"      [STOP] regime never flips (long={res['n_long']} short="
                      f"{res['n_short']}) => no short-vs-long contrast; contributes ZERO "
                      f"separation. Reported, not faked.")
            if res["status"] == "sparse":
                print(f"      [STOP] only {res['n_long'] + res['n_short']} directional minutes "
                      f"< {MIN_SCORED_MINUTES} => too sparse to score; UNDETERMINED/insufficient.")
            for k in K_SET:
                print(f"      {_fmt_k(res['per_k'][k])}")

    scorable = [r for r in rows if r["status"] in ("ok", "sparse", "no-regime-variation")]
    usable_days = sorted({r["day"] for r in scorable})
    dropped_days = sorted({r["day"] for r in rows if r["status"] == "no-preopen-anchor"})

    print(f"\n  -------- PER-INSTRUMENT aggregate (NOT pooled) — {len(usable_days)} usable day(s) "
          f"{usable_days}; dropped {dropped_days} (no pre-open OI anchor) --------")
    print(f"    A regime EDGE needs a CONSISTENT per-day HEADLINE_gap sign, not single-day-")
    print(f"    dominated, AND n_days >= {MIN_DAYS_FOR_EDGE} INDEPENDENT days. At n<{MIN_DAYS_FOR_EDGE}")
    print(f"    the result is UNDETERMINED by construction (a YES is unreachable). Not a failure.")

    INSTRS = ("ES", "NQ")
    state: dict = {}
    for instr in INSTRS:
        rows_i = [r for r in scorable if r["instr"] == instr]
        if not rows_i:
            print(f"\n    [{instr}] no usable rows.")
            continue
        ok_i = [r for r in rows_i if r["status"] == "ok"]
        print(f"\n    [{instr}] {len(rows_i)} usable day(s) "
              f"({len(ok_i)} scorable-ok, {len(rows_i) - len(ok_i)} sparse/no-flip)")
        for k in K_SET:
            day_gaps = [(r["day"], r["per_k"][k]["headline_gap"]) for r in ok_i]
            tally = _gap_sign_tally(day_gaps)
            mean_hl = _mean([r["per_k"][k]["headline_gap"] for r in ok_i])
            mean_sign = _mean([r["per_k"][k]["sign_shuffle_gap"] for r in ok_i])
            mean_flow = _mean([r["per_k"][k]["flowonly_headline_gap"] for r in ok_i])
            per_day_str = "  ".join(f"{d}={_f(g)}" for d, g in tally["gaps"])
            n_days = tally["n_days"]
            # ---- DERIVED THREE-STATE VERDICT (mirrors the sibling gate) ----
            if n_days == 0:
                verdict = ("INCONCLUSIVE", "no scorable-ok day produced a defined HEADLINE_gap "
                           "(degenerate arms / no regime flip)")
            elif not tally["consistent"]:
                verdict = ("UNDETERMINED",
                           f"per-day HEADLINE_gap sign INCONSISTENT ({tally['n_pos']}+/"
                           f"{tally['n_neg']}-) => coin-flip, NOT directional")
            elif tally["dominated"]:
                why = ("excluding it flips the mean sign" if tally["sign_flip"]
                       else f"its |gap| is {tally['dom_frac'] * 100:.0f}% of the |signed sum|")
                verdict = ("UNDETERMINED",
                           f"single-day artefact: {tally['dom_day']} dominates ({why})")
            elif n_days < MIN_DAYS_FOR_EDGE:
                verdict = ("UNDETERMINED",
                           f"consistent ({tally['n_pos']}+/{tally['n_neg']}-, mean "
                           f"{mean_hl:+.3f}) but UNDERPOWERED (n_days={n_days} < "
                           f"{MIN_DAYS_FOR_EDGE}); n=3 correlated 0DTE days cannot support an edge")
            else:
                verdict = ("EDGE (exploratory)",
                           f"consistent ({tally['n_pos']}+/{tally['n_neg']}-) HEADLINE_gap mean "
                           f"{mean_hl:+.3f}, n_days={n_days}")
            state[(instr, k)] = verdict
            print(f"      k={k:>2}: mean HEADLINE_gap={_f(mean_hl)}  mean signshuf_gap="
                  f"{_f(mean_sign)}  mean flowonly_gap={_f(mean_flow)}  "
                  f"({tally['n_pos']}+/{tally['n_neg']}- over {n_days}d)")
            if per_day_str:
                print(f"           per-day HEADLINE_gap: {per_day_str}")
            print(f"           -> {verdict[0]}: {verdict[1]}")

    print("\n  -------- DERIVED VERDICT (per instrument,k — from the numbers above) --------")
    for k in K_SET:
        parts = []
        for instr in INSTRS:
            if (instr, k) in state:
                lbl, why = state[(instr, k)]
                parts.append(f"{instr} {lbl}")
        if parts:
            print(f"    k={k:>2}: " + " ; ".join(parts))

    print("\n  HONEST CAPTION: EXPLORATORY, t-causal look-ahead-free, n=3 usable days "
          "(06-08 dropped: no pre-open OI anchor), ES-dense/NQ-sparse, option-derived parity "
          "forward, control-gap is headline, UNDETERMINED expected at n<5, NOT signal.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
