"""Synthetic-OI #4 FLOW-TERM structural-eval runner (reads data/raw/zerodte/, zero API).

ADDITIVE sibling of ``run_validation.py`` / ``run_ddoi_divergence.py`` / ``run_hiro_eval.py``:
it does NOT touch any of their metric paths. It answers the ONE STRUCTURAL, look-ahead-free
question (see ``synthetic_oi_eval.py``): does the native-aggressor FLOW term ``(−flow)·w``
in synthetic-OI #4 add per-strike STRUCTURE OVER pure OI-GEX — i.e. is the ``w=1`` (OI+flow)
profile materially different from the ``w=0`` (pure OI) profile, or just a scalar rescale /
a same-magnitude random-sign null?

WHY EOD, whole-session, and NOT predictive
==========================================
OI is END-OF-DAY SETTLE only on this data (``statistics`` stat_type 9). Using intraday OI
would be look-ahead, so this is an END-OF-SESSION STRUCTURAL comparison with NO predictive
arm: nothing is scored against price, so there is NO hit-rate / NO "55%" for this arm. The
net-aggressor flow is the whole-day Σ ``aggressor_sign·size`` since the RTH open — IDENTICAL
to what ``run_validation.flow_and_vol`` accumulates and what ``engine.synthetic_oi`` consumes.

The fixed reference + the control
---------------------------------
``profile_static`` (``w=0``) is PURE OI-GEX; the flow term vanishes there, so it is INVARIANT
to any flow shuffle and is the correct fixed reference for both the real and the shuffle arm.
The SHUFFLE-FLOW control permutes the per-trade aggressor SIGN (destroying direction, keeping
magnitude/timing/strike distribution) — the real flow term must beat that same-magnitude null
on ``flow_norm_ratio`` / ``argmax_distance`` to carry directional structure.

Data loading reuses ``run_validation`` machinery VERBATIM (no duplication, no edits there):
``load_defs`` / ``_flat_def_map_all`` / ``_raw_*_iids`` / ``quotes_at`` / ``oi_settle`` /
``_aggressor_sign``. The EOD chain seeds settled OI onto each ``ChainQuote`` so ``_solve_chain``
populates ``ChainRow.call_oi`` / ``put_oi`` that ``engine.synthetic_oi.q_per_leg`` reads (OI
and VOL do NOT affect the solved gamma — gamma comes from the mid/IV — so seeding OI changes
only the position model, not the greeks). The gamma reference is read at the LATEST late-session
minute whose chain solves (the 16:00 ET bell is degenerate => thin), exactly like
``run_ddoi_divergence``.

Provenance guard: this separate entry calls ``assert_session_iids_0dte`` ITSELF (the same
fail-closed 0DTE chokepoint the others use), BEFORE any metric.

EXPLORATORY: 4 correlated 0DTE days, EOD STRUCTURAL only, NOT predictive, NOT validated. The
control GAP is the headline. The verdict is DERIVED from the printed thresholds, never hardcoded.

Run from the repo root:
    PYTHONPATH=services/engine/src .venv/Scripts/python.exe analysis/harness/run_synthetic_oi_eval.py
Requires the gitignored data/raw/zerodte/ + data/raw/_probe/ pull on disk.
"""
from __future__ import annotations

import math
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.join("services", "engine", "src"))
sys.path.insert(0, ".")  # so `analysis.harness.*` imports when run as a script

import databento as db  # noqa: E402

from analysis.harness.provenance import assert_session_iids_0dte  # noqa: E402
from analysis.harness.synthetic_oi_eval import (  # noqa: E402
    DEFAULT_SHUFFLE_SEEDS,
    FlowTrade,
    eval_flow_term,
)
# Reuse run_validation's data-loading machinery verbatim (no duplication, no edits there).
from analysis.harness.run_validation import (  # noqa: E402
    DAYS,
    DEF,
    NY,
    RATE,
    SAMPLE_ET,
    STEP,
    ZERO,
    _aggressor_sign,
    _flat_def_map_all,
    _raw_settled_iids,
    _raw_traded_iids,
    load_defs,
    oi_settle,
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

#: Operating weight for the flow term. w=1 fully adds (−flow); w=0 is the pure-OI baseline.
#: Matches engine.synthetic_oi.build_synthetic_oi's default w=1.0.
W_OPERATING = 1.0

#: Minimum non-thin strikes for a usable EOD gamma reference (same floor as
#: run_ddoi_divergence): Black-76 gamma is DEGENERATE at the 16:00 ET bell, so the gamma
#: reference is taken at the LATEST late-session sample minute whose solved chain clears
#: this floor. Net flow + OI remain whole-day/EOD; only the GAMMA the position model
#: multiplies is read at this solvable late minute. Look-ahead-free (no outcome scored).
MIN_NONTHIN = 8

#: A (day, instrument) needs at least this many SHARED strikes in the profile comparison
#: for the structural metrics to be anything but noise; below it -> degenerate STOP-row.
MIN_SHARED_STRIKES = 5

#: A "YES (exploratory)" structural claim additionally needs more INDEPENDENT days than the
#: 4 correlated 0DTE sessions on disk. With n_days < this, a consistent above-threshold gap
#: is honestly DOWNGRADED to UNDETERMINED (suggestive but underpowered), never "YES" — 4
#: correlated days cannot support a structural edge. Mirrors run_hiro_eval.MIN_DAYS_FOR_EDGE.
MIN_DAYS_FOR_EDGE = 5


def _gap_sign_tally(day_gaps: list) -> dict:
    """Per-day SIGN tally + single-day-domination check over the norm_ratio_gap list.

    Mirrors ``run_hiro_eval._aggregate``'s per-day sign accounting (``n_pos``/``n_neg``/
    ``consistent``; run_hiro_eval.py:380-390): a positive MEAN gap means NOTHING if the
    per-day gaps flip sign — that is a coin-flip, not directional structure. Additionally
    flags when ONE day DOMINATES the signed sum (its exclusion flips the mean sign, or its
    |gap| exceeds 50% of the |signed sum|), so a single-day artefact is VISIBLE rather than
    hidden behind the mean. ``day_gaps`` is a list of ``(day_label, gap)``; NaN/None dropped.
    """
    clean = [(d, g) for d, g in day_gaps
             if g is not None and not (isinstance(g, float) and math.isnan(g))]
    n = len(clean)
    if n == 0:
        return {"n_days": 0, "n_pos": 0, "n_neg": 0, "consistent": False,
                "gaps": [], "mean_all": float("nan"), "mean_excl_dom": float("nan"),
                "dom_day": None, "dom_gap": float("nan"), "dom_frac": float("nan"),
                "sign_flip": False, "dominated": False}
    gaps = [g for _, g in clean]
    n_pos = sum(1 for g in gaps if g > 0.0)
    n_neg = sum(1 for g in gaps if g < 0.0)
    consistent = (n_pos == n) or (n_neg == n)
    signed_sum = sum(gaps)
    mean_all = signed_sum / n
    dom_i = max(range(n), key=lambda i: abs(gaps[i]))
    dom_day, dom_gap = clean[dom_i]
    rest = [g for i, g in enumerate(gaps) if i != dom_i]
    mean_excl = (sum(rest) / len(rest)) if rest else float("nan")
    dom_frac = abs(dom_gap) / abs(signed_sum) if abs(signed_sum) > 1e-9 else float("inf")
    sign_flip = (not math.isnan(mean_excl)) and (mean_all * mean_excl < 0.0)
    dominated = sign_flip or dom_frac > 0.5
    return {
        "n_days": n, "n_pos": n_pos, "n_neg": n_neg, "consistent": consistent,
        "gaps": clean, "mean_all": mean_all, "mean_excl_dom": mean_excl,
        "dom_day": dom_day, "dom_gap": dom_gap, "dom_frac": dom_frac,
        "sign_flip": sign_flip, "dominated": dominated,
    }


def load_flow_trades(path: str, legs: dict, rth_open_sec: int) -> list:
    """Stream the trades dbn -> chronological list of :class:`FlowTrade` over RTH.

    Mirrors ``run_validation.flow_and_vol`` (same ``DBNStore.from_file`` loop,
    ``ts_event``/``size``/``side`` fields, ``ts >= rth_open`` filter) but retains the native
    CME aggressor SIGN per trade (B=+1/A=-1/N=0 via ``run_validation._aggressor_sign``) so the
    per-trade :func:`synthetic_oi_eval.shuffle_flow_signs` control is faithful. Net flow is
    Σ ``sign·size`` per leg — exactly the ``net_aggressor_flow`` ``engine.synthetic_oi``
    consumes. Missing file -> []. Neutral (N) trades are KEPT (sign 0) so the shuffle's sign
    multiset matches the real tape's neutral share.
    """
    if not os.path.exists(path):
        return []
    out: list = []
    for r in db.DBNStore.from_file(path):
        iid = r.instrument_id
        if iid not in legs:
            continue
        ts = int(getattr(r, "ts_event", 0) / 1e9)
        if ts < rth_open_sec:
            continue
        sz = float(getattr(r, "size", 0) or 0)
        if sz <= 0.0:
            continue
        sgn = _aggressor_sign(getattr(r, "side", "N"))
        otype, k, _ed = legs[iid]
        out.append(FlowTrade(strike=float(k), is_call=(otype == "call"), size=sz, sign=sgn))
    return out


def _eod_quotes_with_oi(instr: str, legs: dict, mids: dict, oi: dict, t_exp: float) -> tuple:
    """Build (quotes, forward) at end-of-session from EOD mids + settled OI per leg.

    Mirrors ``run_validation._build_at`` / ``run_ddoi_divergence._eod_quotes`` forward/ATM/
    quality filters EXACTLY, but seeds each leg's ChainQuote with the settled OI (``oi[iid]``)
    instead of volume — synthetic-OI #4's stock anchor is ``s_static·OI``, so the solved rows
    must carry OI for ``q_per_leg``. OI does NOT affect the solved gamma (gamma comes from the
    mid/IV), so this changes only the position model. ``call_vol``/``put_vol`` are left 0 (the
    VOL profile is irrelevant to this eval). Returns ``(None, None)`` when the chain is too
    thin / the forward is ill-conditioned.
    """
    bystrike: dict = defaultdict(dict)
    for iid, (otype, k, _ed) in legs.items():
        if iid in mids:
            bystrike[k][otype] = (mids[iid], float(oi.get(iid, 0.0)))
    both = {k: v for k, v in bystrike.items() if "call" in v and "put" in v}
    if len(both) < 5:
        return None, None
    atm = min(both, key=lambda k: abs(both[k]["call"][0] - both[k]["put"][0]))
    fwd = atm + (both[atm]["call"][0] - both[atm]["put"][0])
    ks_both = sorted(both)
    if not (ks_both[0] <= fwd <= ks_both[-1]):
        return None, None
    if abs(both[atm]["call"][0] - both[atm]["put"][0]) > 6 * STEP[instr]:
        return None, None
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
    return quotes, fwd


def run_day(instr: str, day: str, defs: dict) -> dict | None:
    """One (day, instrument) EOD flow-term structural row, or None when skipped."""
    d = datetime.strptime(day, "%Y-%m-%d")

    # ---- TENOR PROVENANCE GUARD (fail-closed, BEFORE any metric) --------------
    # SAME chokepoint as run_validation/run_ddoi_divergence/run_hiro_eval: resolve the
    # RAW traded∪settled id population (no iidset filter) against the COMBINED ES+NQ
    # definition map; a non-session/unresolved id raises. Empty population -> loud skip.
    flat_def_map = _flat_def_map_all(defs)
    traded_settled_iids = (
        _raw_traded_iids(f"{ZERO}/trades/{day}.dbn.zst")
        | _raw_settled_iids(f"{ZERO}/statistics/{day}.dbn.zst")
    )
    if not traded_settled_iids:
        print(f"  [provenance] WARN no traded/settled iids for {day} — skipping")
        return None
    prov = assert_session_iids_0dte(
        traded_settled_iids, flat_def_map, d.date(), source_label=f"zerodte/{day}",
    )
    print(f"  [provenance] {prov.summary()}")

    legs = defs[instr].get(day, {})
    if not legs:
        return None
    iidset = set(legs)

    rth_open = int(datetime(d.year, d.month, d.day, 9, 30, tzinfo=NY).timestamp())
    sample_secs = [int(datetime(d.year, d.month, d.day, h, mi, tzinfo=NY).timestamp())
                   for h, mi in SAMPLE_ET]

    # Whole-day signed aggressor flow (the #4 net_aggressor_flow domain — EOD, since open).
    trades = load_flow_trades(f"{ZERO}/trades/{day}.dbn.zst", legs, rth_open)
    if not trades:
        return {"day": day, "instr": instr, "status": "no-data"}

    # End-of-day settled OI per leg (the s_static·OI stock anchor). EOD-only by nature.
    oi = oi_settle(f"{ZERO}/statistics/{day}.dbn.zst", iidset)
    if not oi:
        return {"day": day, "instr": instr, "status": "no-oi"}

    # ---- GAMMA REFERENCE: latest solvable late-session minute --------------------
    # Flow + OI are whole-day/EOD; the per-strike GAMMA the position model multiplies must
    # be read where Black-76 IV actually solves. At the bell t_expiry -> ~1e-5 yr and EVERY
    # strike goes thin, so scan the sample minutes LATEST-first and take the first whose
    # solved chain clears MIN_NONTHIN. Still contemporaneous/EOD => look-ahead-free.
    q = quotes_at(f"{ZERO}/bbo-1m/{day}.dbn.zst", iidset, sample_secs)
    M = MULTIPLIER[instr]
    chosen = None  # (sec, t_exp, fwd, rows)
    for s in sorted(sample_secs, reverse=True):
        mids = q.get(s, {})
        if not mids:
            continue
        ts = datetime.fromtimestamp(s, tz=timezone.utc)
        t_exp = t_expiry_from_clock(ts)
        quotes, fwd = _eod_quotes_with_oi(instr, legs, mids, oi, t_exp)
        if quotes is None:
            continue
        rows = _solve_chain(quotes, fwd, RATE, t_exp)
        if sum(1 for r in rows if not r.thin) >= MIN_NONTHIN:
            chosen = (s, t_exp, fwd, rows)
            break
    if chosen is None:
        return {"day": day, "instr": instr, "status": "insufficient-chain"}
    eod_sec, t_exp, fwd, rows = chosen
    ref_et = datetime.fromtimestamp(eod_sec, tz=timezone.utc).astimezone(NY)
    ref_label = f"{ref_et.hour:02d}:{ref_et.minute:02d}"

    panel = eval_flow_term(rows, trades, M, fwd, w=W_OPERATING, seeds=DEFAULT_SHUFFLE_SEEDS)
    if panel["n"] < MIN_SHARED_STRIKES:
        return {"day": day, "instr": instr, "status": "degenerate-profile",
                "n_shared": panel["n"]}

    return {
        "day": day, "instr": instr, "status": "ok", "fwd": fwd, "ref_et": ref_label,
        "n_legs": len(legs), "n_trades": len(trades), "panel": panel,
    }


def _f(x, p: int = 3) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "  n/a"
    return f"{x:+.{p}f}"


def _fmt_panel(m: dict) -> str:
    """One-line per-row rendering, leading with the HEADLINE GAPS (control-gap is headline)."""
    return (f"NORMratio_GAP(real-shuf)={_f(m['norm_ratio_gap'])}  "
            f"argmaxΔ_GAP={_f(m['argmax_gap'], 2)}  ||  "
            f"flow_norm_ratio={_f(m['flow_norm_ratio'])} "
            f"shuf={_f(m['shuffle_norm_mean'])}"
            f"[{_f(m['shuffle_norm_min'], 2)},{_f(m['shuffle_norm_max'], 2)}]  "
            f"resid_r2={_f(m['residual_r2'])} c={_f(m['best_fit_scalar_c'], 2)}  "
            f"argmaxΔ={m['argmax_distance']} sign_agr={_f(m['sign_agreement'], 2)} "
            f"n={m['n']}")


def main() -> int:
    if not os.path.exists(DEF):
        print(f"ERROR: definition file missing: {DEF}\n"
              f"This harness needs the gitignored data/raw/ pull on disk.")
        return 2

    print("==== SYNTHETIC-OI #4 FLOW-TERM — EOD STRUCTURAL eval (gex[w=1] vs gex_static[w=0]) ====")
    print("*** EXPLORATORY, n=4 correlated days, EOD STRUCTURAL (no predictive arm — OI is")
    print("    EOD-settle; intraday OI would be look-ahead). THERE IS NO HIT-RATE / NO 55%")
    print("    for this structural arm. The control-gap is the headline. ***")
    print("Question: does the native-aggressor FLOW term (−flow)·w add per-strike STRUCTURE")
    print("over pure OI-GEX, or is w=1 just a scalar rescale / a same-magnitude random-sign null?")
    print("profile_static (w=0) is PURE OI-GEX (flow vanishes), the fixed reference for both arms.")
    print("SHUFFLE-FLOW control permutes per-trade aggressor SIGN (kills direction, keeps")
    print(f"magnitude); real must beat it. Shuffle seeds: {list(DEFAULT_SHUFFLE_SEEDS)}.")
    print("Flows + OI are WHOLE-DAY/EOD; gamma is read at the latest late-session minute that")
    print("solves (the 16:00 ET bell is degenerate => thin), shown as gamma@HH:MMET.\n")

    defs = load_defs()
    rows = []
    for day in DAYS:
        for instr in ("ES", "NQ"):
            res = run_day(instr, day, defs)
            if res is None:
                continue
            rows.append(res)
            if res["status"] != "ok":
                extra = (f" (n_shared={res['n_shared']})" if "n_shared" in res else "")
                print(f"  {day} {instr}: {res['status']}{extra}")
                continue
            m = res["panel"]
            print(f"  {day} {instr}  F={res['fwd']:.0f}  strikes={m['n']} "
                  f"legs={res['n_legs']} trades={res['n_trades']}  gamma@{res['ref_et']}ET")
            print(f"      {_fmt_panel(m)}")

    ok = [r for r in rows if r["status"] == "ok"]
    if not ok:
        print("\n  (no session-instruments produced a usable profile)")
        return 0

    def _mean(vals: list) -> float:
        clean = [v for v in vals
                 if v is not None and not (isinstance(v, float) and math.isnan(v))]
        return sum(clean) / len(clean) if clean else float("nan")

    # ---- PER-INSTRUMENT aggregate (NOT pooled — the HIRO lesson: pooling masks both) ----
    INSTRS = ("ES", "NQ")

    # HONEST-VERDICT THRESHOLDS (all printed; the verdict is DERIVED from the numbers).
    RESID_R2_HIGH = 0.95   # residual_r2 >= this ⇒ gex ≈ c·static ⇒ flow is a scalar rescale (null)
    NORM_NEGLIGIBLE = 0.05  # flow_norm_ratio < this ⇒ flow term is negligible vs pure OI (null)
    GAP_MEANINGFUL = 0.05   # real flow_norm_ratio exceeds shuffle by >= this ⇒ beats random-sign

    print("\n  -------- PER-INSTRUMENT aggregate (NOT pooled) --------")
    print(f"    thresholds: residual_r2 >= {RESID_R2_HIGH:.2f} ⇒ flow ≈ scalar·OI (no new "
          f"shape = NULL); flow_norm_ratio < {NORM_NEGLIGIBLE:.2f} ⇒ flow negligible (NULL);")
    print(f"                norm_ratio_gap (real − shuffle) >= {GAP_MEANINGFUL:.2f} ⇒ flow "
          f"beats a same-magnitude random-sign null (directional structure).")
    print(f"                BUT a positive MEAN gap is NOT directional unless the PER-DAY "
          f"sign is CONSISTENT (all days same sign) AND not a single-day artefact, AND "
          f"n_days >= {MIN_DAYS_FOR_EDGE}")
    print(f"                independent days (4 correlated 0DTE days cannot support an "
          f"edge). A sign-inconsistent / single-day-dominated instrument is UNDETERMINED, "
          f"NEVER YES.")

    agg: dict = {}
    for instr in INSTRS:
        rows_i = [r for r in ok if r["instr"] == instr]
        if not rows_i:
            print(f"\n    [{instr}] no usable rows.")
            continue
        ps = [r["panel"] for r in rows_i]
        # PER-DAY norm_ratio_gap list (with day labels) — the basis for the sign tally and
        # the single-day-domination check. A POSITIVE MEAN gap is meaningless if the per-day
        # gaps flip sign (coin-flip) or one day dominates the signed sum (single-day artefact).
        day_gaps = [(r["day"], r["panel"]["norm_ratio_gap"]) for r in rows_i]
        tally = _gap_sign_tally(day_gaps)
        a = {
            "n_days": len(ps),
            "flow_norm_ratio": _mean([p["flow_norm_ratio"] for p in ps]),
            "residual_r2": _mean([p["residual_r2"] for p in ps]),
            "norm_ratio_gap": _mean([p["norm_ratio_gap"] for p in ps]),
            "argmax_gap": _mean([p["argmax_gap"] for p in ps]),
            "shuffle_norm_mean": _mean([p["shuffle_norm_mean"] for p in ps]),
            "argmax_distance": _mean([float(p["argmax_distance"])
                                      for p in ps if p["argmax_distance"] is not None]),
            "sign_agreement": _mean([p["sign_agreement"] for p in ps]),
            # Per-day sign tally + single-day-domination (mirrors run_hiro_eval._aggregate).
            "n_pos": tally["n_pos"], "n_neg": tally["n_neg"],
            "consistent": tally["consistent"],
            "gap_days": tally["gaps"],
            "mean_excl_dom": tally["mean_excl_dom"],
            "dom_day": tally["dom_day"], "dom_gap": tally["dom_gap"],
            "dom_frac": tally["dom_frac"], "sign_flip": tally["sign_flip"],
            "dominated": tally["dominated"],
        }
        agg[instr] = a
        print(f"\n    [{instr}] {a['n_days']} day(s)")
        print(f"      mean flow_norm_ratio={_f(a['flow_norm_ratio'])} "
              f"(shuffle={_f(a['shuffle_norm_mean'])})  "
              f"mean NORMratio_GAP={_f(a['norm_ratio_gap'])}")
        print(f"      mean residual_r2={_f(a['residual_r2'])}  "
              f"mean argmaxΔ={_f(a['argmax_distance'], 2)} "
              f"(GAP={_f(a['argmax_gap'], 2)})  mean sign_agr={_f(a['sign_agreement'], 2)}")
        # ---- SIGN-CONSISTENCY + SINGLE-DAY-DOMINATION SURFACING (the red-team headline) ----
        per_day_str = "  ".join(f"{d}={_f(g)}" for d, g in a["gap_days"])
        print(f"      per-day NORMratio_GAP: {per_day_str}")
        print(f"      sign tally: {a['n_pos']}+ / {a['n_neg']}-  over {a['n_days']} day(s)"
              f"  => consistent={a['consistent']}"
              + ("" if a["consistent"] else "  [SIGN-INCONSISTENT: coin-flip, NOT directional]"))
        print(f"      mean GAP incl all days={_f(a['norm_ratio_gap'])}  "
              f"vs mean EXCLUDING dominant day {a['dom_day']}({_f(a['dom_gap'])})"
              f"={_f(a['mean_excl_dom'])}")
        if a["dominated"]:
            why = ("excluding it FLIPS the mean sign" if a["sign_flip"]
                   else f"its |gap| is {a['dom_frac'] * 100:.0f}% of the |signed sum|")
            print(f"      [SINGLE-DAY-DOMINATION] {a['dom_day']} ({_f(a['dom_gap'])}) "
                  f"dominates the mean: {why} => the positive mean is a single-day artefact.")

    # ---- DERIVED HONEST VERDICT (per instrument, from the numbers above) --------------
    def _verdict(a: dict) -> str:
        fnr = a["flow_norm_ratio"]
        rr2 = a["residual_r2"]
        gap = a["norm_ratio_gap"]
        if math.isnan(fnr):
            return "INCONCLUSIVE — no numeric basis (flow_norm_ratio undefined)."
        if fnr < NORM_NEGLIGIBLE:
            return (f"NO — flow term NEGLIGIBLE (flow_norm_ratio {fnr:+.3f} < "
                    f"{NORM_NEGLIGIBLE:.2f}); w=1 ≈ pure OI-GEX. INCONCLUSIVE-leaning-NO "
                    "at n=4.")
        redundant = (not math.isnan(rr2)) and rr2 >= RESID_R2_HIGH
        beats_random = (not math.isnan(gap)) and gap >= GAP_MEANINGFUL
        consistent = a["consistent"]
        dominated = a["dominated"]
        enough_days = a["n_days"] >= MIN_DAYS_FOR_EDGE
        sign_str = f"{a['n_pos']}+/{a['n_neg']}-"

        # ---- SIGN-CONSISTENCY + SINGLE-DAY-DOMINATION GATE (the red-team fix) ----------
        # A positive MEAN gap that flips sign across days (coin-flip) or rests on ONE
        # dominant day is NOT directional structure — it can NEVER read "YES". Route it to
        # UNDETERMINED (mirrors run_hiro_eval's consistency gate, run_hiro_eval.py:421/433:
        # a sign-inconsistent instrument is never an EDGE). This is exactly the NQ case the
        # red-team flagged: 2+/2- with 06-05 dominating the mean.
        if beats_random and (not consistent or dominated):
            bits = []
            if dominated:
                excl = (f"excluding it mean = {a['mean_excl_dom']:+.3f}"
                        if not math.isnan(a["mean_excl_dom"]) else "single-day-dominated")
                bits.append(f"positive mean is a single-day artefact "
                            f"({a['dom_day']} = {a['dom_gap']:+.3f}; {excl})")
            cons_word = "inconsistent" if not consistent else "consistent"
            bits.append(f"per-day sign {sign_str}, {cons_word}")
            return (f"UNDETERMINED — mean norm_ratio_gap {gap:+.3f} >= "
                    f"{GAP_MEANINGFUL:.2f} but its DIRECTION is NOT separable from "
                    f"random-sign flow at n=4: " + "; ".join(bits) + ". "
                    "Flow term is materially-sized but NOT directional (NEVER YES).")

        if redundant and not beats_random:
            return (f"NO — flow term is a SCALAR RESCALE of OI (residual_r2 {rr2:+.3f} >= "
                    f"{RESID_R2_HIGH:.2f}) and does NOT beat the random-sign null "
                    f"(norm_ratio_gap {gap:+.3f} < {GAP_MEANINGFUL:.2f}); no per-strike "
                    "structure. INCONCLUSIVE-leaning-NO at n=4.")
        if (not redundant) and beats_random:
            # Past the gate: consistent per-day sign AND not single-day-dominated. A real
            # structural claim ALSO needs more INDEPENDENT days than the 4 correlated 0DTE
            # sessions on disk — mirror run_hiro_eval.py:422 (n_days >= MIN_DAYS_FOR_EDGE).
            if not enough_days:
                return (f"UNDETERMINED — flow term is consistent (per-day sign {sign_str}) "
                        f"and beats the random-sign null (norm_ratio_gap {gap:+.3f} >= "
                        f"{GAP_MEANINGFUL:.2f}) with a structured residual (residual_r2 "
                        f"{rr2:+.3f}), BUT is UNDERPOWERED (n_days={a['n_days']} < "
                        f"{MIN_DAYS_FOR_EDGE} independent days); 4 correlated days cannot "
                        "support a structural edge. Suggestive, NOT demonstrated.")
            return (f"YES (exploratory) — flow term is NON-redundant (residual_r2 {rr2:+.3f} "
                    f"< {RESID_R2_HIGH:.2f}: structured residual), CONSISTENT per-day "
                    f"(sign {sign_str}) AND beats the random-sign null (norm_ratio_gap "
                    f"{gap:+.3f} >= {GAP_MEANINGFUL:.2f}); n_days={a['n_days']}.")
        if beats_random and redundant:
            return (f"PARTIAL — flow beats the random-sign null (gap {gap:+.3f} >= "
                    f"{GAP_MEANINGFUL:.2f}, consistent {sign_str}) but is ~collinear with "
                    f"OI shape (residual_r2 {rr2:+.3f} >= {RESID_R2_HIGH:.2f}); directional "
                    "but little NEW shape. UNDETERMINED at n=4.")
        return (f"UNDETERMINED — flow term is material (flow_norm_ratio {fnr:+.3f}) with a "
                f"structured residual (residual_r2 {rr2:+.3f}) but does NOT clearly beat the "
                f"random-sign null (norm_ratio_gap {gap:+.3f} < {GAP_MEANINGFUL:.2f}); "
                f"per-day sign {sign_str} ({'consistent' if consistent else 'inconsistent'}); "
                "direction not separable from random at n=4.")

    print("\n  -------- DERIVED VERDICT (per instrument, from the numbers + thresholds above) --------")
    for instr in INSTRS:
        if instr in agg:
            print(f"    [{instr}] {_verdict(agg[instr])}")

    print("\n  READ: these are the numbers the code produced and a verdict DERIVED from the")
    print("  printed thresholds — NOT a validated finding. 4 correlated days is far too small;")
    print("  the weight w is a HEURISTIC knob, not ground truth; OI direction (s_static) is the")
    print("  same irreducible assumption every vendor makes. EXPLORATORY, n=4, EOD STRUCTURAL,")
    print("  NOT predictive. Synthetic-OI is NOT claimed to predict anything.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
