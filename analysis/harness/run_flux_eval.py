"""FLUX t->t+k PREDICTIVE-eval runner (reads data/raw/zerodte/ directly, zero API).

ADDITIVE sibling of ``run_validation.py`` / ``run_ddoi_divergence.py``: it does NOT touch
either file's metric path. It answers ONE controlled, look-ahead-free question (see
``flux_eval.py``): does the SIGN of per-minute FLUX flow (``delta_hiro_t``) lead the SIGN
of the future forward return ``F_{t+k} − F_t`` — and crucially, does it do so BEYOND the
sign-shuffled / signed-volume / contemporaneous / persistence controls?

Why read the dbn DIRECTLY (and not get_flux_trades)
===================================================
``engine.flux``'s ``get_flux_trades`` is welded to ``HistoricalSimAdapter``, which reads
DECODED CSVs that do not exist for these days. So this runner reads the trades
``.dbn.zst`` directly, exactly the way ``run_validation`` already streams dbn (same
``DBNStore.from_file`` loop, ``ts_event``/``size``/``side``/``price`` fields, ``price/1e9``
fixed-point per ``analysis/decode.py``), and reuses run_validation's ``load_defs`` /
``_flat_def_map_all`` / ``_raw_*_iids`` / ``quotes_at`` machinery verbatim (no duplication,
no edits there). The per-trade greek notional + aggressor sign come from the LOCKED engine
core (``engine.flux.signed_delta_notional`` / ``aggressor_sign``) via the pure
``flux_eval`` module — no greek re-implementation.

The OPTION-DERIVED parity forward (NOT a futures price)
-------------------------------------------------------
There are NO futures trades/bbo on disk, so the forward is the per-minute put-call-parity
forward ``fwd = atm + (call_mid − put_mid)`` built from bbo-1m option quotes — IDENTICAL
to ``run_validation._build_at`` / ``run_ddoi_divergence._eod_quotes`` (same ATM pick, same
``fwd in [Kmin,Kmax]`` and ``ATM spread <= 6·step`` quality filters), just evaluated on a
REGULAR per-minute grid over RTH (09:30..16:00 ET = 390 minutes). ``minute_forwards[t]`` is
read as of the START of minute ``t`` (second ``rth_open + t·60``), so it is observable AT
OR BEFORE every trade that prints in minute ``t`` (strictly causal); the outcome return
``F_{t+k} − F_t`` uses the same grid at ``t+k`` (with ``k >= 5`` the outcome timestamp is
strictly later than the predictor's information set — no leakage).

Provenance guard: this separate entry calls ``assert_session_iids_0dte`` ITSELF (the same
fail-closed 0DTE chokepoint ``run_validation.run_day`` uses), on the RAW traded∪settled id
population resolved against the full ES+NQ definition map, BEFORE any FLUX/return number.

EXPLORATORY: 4 correlated 0DTE days, OPTION-DERIVED parity forward (NOT futures price),
descriptive only, NOT predictive-validated. The control GAP is the headline, NOT the raw
hit-rate. The verdict line is DERIVED from the computed gaps, never hardcoded.

Run from the repo root:
    PYTHONPATH=services/engine/src .venv/Scripts/python.exe analysis/harness/run_hiro_eval.py
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

from analysis.harness.flux_eval import (  # noqa: E402
    DEFAULT_SHUFFLE_SEEDS,
    EvalTrade,
    eval_controls,
)
from analysis.harness.provenance import assert_session_iids_0dte  # noqa: E402
# Reuse run_validation's data-loading machinery verbatim (no duplication, no edits there).
from analysis.harness.run_validation import (  # noqa: E402
    DAYS,
    DEF,
    NY,
    RATE,
    STEP,
    ZERO,
    _flat_def_map_all,
    _raw_settled_iids,
    _raw_traded_iids,
    load_defs,
    quotes_at,
)
from engine.flux import FluxTrade  # noqa: E402
from engine.snapshot import MULTIPLIER, t_expiry_from_clock  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

#: RTH is 09:30..16:00 ET = 390 one-minute bars. minute index t in [0, N_MINUTES).
N_MINUTES = 390

#: Forward horizons (MINUTES on the per-minute grid). k >= 2 guarantees the outcome
#: timestamp strictly post-dates the predictor's information set (see module docstring);
#: {5,15,30} are short/medium/long intraday leads on a 390-minute session.
K_SET = (5, 15, 30)

#: A session-instrument needs at least this many minutes with a clean parity forward for
#: the lead-lag test to be anything but noise. Below it -> STOP-condition (reported, not
#: faked): the per-minute parity forward could not be cleanly built from bbo-1m.
MIN_FORWARD_MINUTES = 60

#: Aggressor-neutral fraction at/above this makes the directional test structurally
#: meaningless (almost no signed flow). Reported loudly, never hidden.
NEUTRAL_FRAC_DEGENERATE = 0.95

# ---- HONEST-VERDICT THRESHOLDS (all printed at runtime; nothing hardcoded into the
#      conclusion — the verdict is DERIVED from the computed per-instrument numbers) ----
#: A real directional edge requires the per-instrument n-weighted mean control-gap to
#: clear this. ES k=5 here lands ~+0.047 — just BELOW it — which is why it reads
#: "suggestive / at-threshold", NOT "edge".
EDGE_THRESH = 0.05
#: Below EDGE_THRESH but at/above this, with a CONSISTENT per-day sign, is "suggestive"
#: (a hint worth flagging) rather than a flat null. Between SUGGESTIVE_THRESH and
#: EDGE_THRESH => UNDETERMINED (not null, not edge).
SUGGESTIVE_THRESH = 0.03
#: A per-(day,instrument) row whose forward coverage is below this is UNDERPOWERED: its
#: lead-lag score rests on too few scored minutes to trust. Such rows are FLAGGED and an
#: instrument with ANY sub-floor day is reported UNDETERMINED for that k (coverage too
#: low to resolve edge-vs-null) rather than being silently pooled at equal weight. NQ's
#: 0.43–0.75 coverage trips this; ES's 0.99–1.00 does not.
COVERAGE_OK = 0.60
#: A hard "edge over shuffle" claim additionally needs more INDEPENDENT days than the 4
#: correlated 0DTE sessions on disk. With n_days < this, a consistent above-threshold
#: signal is honestly DOWNGRADED to "suggestive / UNDERPOWERED" (UNDETERMINED), never
#: "edge". This is why even a clean ES hint cannot be called a demonstrated edge here.
MIN_DAYS_FOR_EDGE = 5


def parity_forward(instr: str, legs: dict, mids: dict) -> float | None:
    """Put-call-parity forward from one minute's option mids, or None if ill-conditioned.

    BYTE-FOR-BYTE the forward logic of ``run_validation._build_at`` /
    ``run_ddoi_divergence._eod_quotes``: needs >= 5 strikes quoting BOTH call and put,
    picks ATM = argmin|call_mid − put_mid|, sets ``fwd = atm + (call_mid − put_mid)``, and
    rejects when the forward escapes the quoted strike range or the ATM call/put spread
    exceeds ``6·step`` (a degenerate/illiquid minute). ``mids`` is ``{iid: mid}`` for this
    minute (already option-mid, index points), exactly what ``quotes_at`` returns.
    """
    bystrike: dict = defaultdict(dict)
    for iid, (otype, k, _ed) in legs.items():
        if iid in mids:
            bystrike[float(k)][otype] = mids[iid]
    both = {k: v for k, v in bystrike.items() if "call" in v and "put" in v}
    if len(both) < 5:
        return None
    atm = min(both, key=lambda k: abs(both[k]["call"] - both[k]["put"]))
    fwd = atm + (both[atm]["call"] - both[atm]["put"])
    ks = sorted(both)
    if not (ks[0] <= fwd <= ks[-1]):
        return None
    if abs(both[atm]["call"] - both[atm]["put"]) > 6 * STEP[instr]:
        return None
    return fwd


def build_minute_forwards(instr: str, legs: dict, iidset: set, bbo_path: str,
                          rth_open_sec: int) -> list:
    """Regular per-minute parity-forward grid over RTH (length ``N_MINUTES``).

    ``minute_forwards[t]`` is the parity forward as of the START of minute ``t`` (second
    ``rth_open + t·60``), or ``None`` where bbo-1m gives no clean forward for that minute.
    Reuses ``run_validation.quotes_at`` (latest fresh mid within its staleness window) on
    the per-minute second grid, so the forward construction matches the rest of the
    harness exactly. Causal by construction: a START-of-minute forward precedes every
    trade printing inside that minute.
    """
    grid_secs = [rth_open_sec + t * 60 for t in range(N_MINUTES)]
    q = quotes_at(bbo_path, iidset, grid_secs)
    forwards: list = []
    for t, s in enumerate(grid_secs):
        mids = q.get(s, {})
        forwards.append(parity_forward(instr, legs, mids) if mids else None)
    return forwards


def load_eval_trades(path: str, legs: dict, rth_open_sec: int) -> list:
    """Stream the trades dbn -> chronological list of :class:`EvalTrade` over RTH.

    Mirrors ``run_validation.flow_and_vol`` / ``run_ddoi_divergence.leg_trades_full_day``
    (same ``DBNStore.from_file`` loop, ``ts_event``/``size``/``side`` fields, ``ts >=
    rth_open`` filter), but ALSO carries the trade ``price`` (``/1e9`` fixed-point, per
    ``analysis/decode.py``) and builds the locked-engine :class:`FluxTrade` so the pure
    metric can price each trade with ``engine.flux.signed_delta_notional`` (no greek
    re-impl). Each trade is tagged with its 0-based RTH minute index. Per-trade
    ``t_expiry`` is the real wall-clock tenor at the trade (``t_expiry_from_clock``),
    matching the worker default (methodology decision #3). Missing file -> []. UNLIKE
    DDOI, the aggressor ``side`` IS retained — FLUX is a directional flow.
    """
    if not os.path.exists(path):
        return []
    out: list = []
    for r in db.DBNStore.from_file(path):
        iid = r.instrument_id
        if iid not in legs:
            continue
        ts_sec = int(getattr(r, "ts_event", 0)) / 1e9
        minute = int((ts_sec - rth_open_sec) // 60)
        if minute < 0 or minute >= N_MINUTES:
            continue
        sz = float(getattr(r, "size", 0) or 0)
        if sz <= 0.0:
            continue
        px = float(getattr(r, "price", 0) or 0) / 1e9
        if px <= 0.0:
            continue
        side = str(getattr(r, "side", "N"))
        otype, k, _ed = legs[iid]
        ts_dt = datetime.fromtimestamp(ts_sec, tz=timezone.utc)
        t_exp = t_expiry_from_clock(ts_dt)
        tr = FluxTrade(
            strike=float(k), is_call=(otype == "call"), price=px, size=sz,
            side=side, t_expiry=t_exp,
        )
        out.append(EvalTrade(minute, tr))
    out.sort(key=lambda e: e.minute)
    return out


def run_day(instr: str, day: str, defs: dict) -> dict | None:
    """One (day, instrument) FLUX predictive-eval row, or None when skipped."""
    d = datetime.strptime(day, "%Y-%m-%d")

    # ---- TENOR PROVENANCE GUARD (fail-closed, BEFORE any FLUX/return number) ----
    # SAME chokepoint as run_validation.run_day: resolve the RAW traded∪settled id
    # population (no iidset filter) against the COMBINED ES+NQ definition map; a
    # non-session/unresolved id raises. Empty population -> loud skip (data absent).
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

    eval_trades = load_eval_trades(f"{ZERO}/trades/{day}.dbn.zst", legs, rth_open)
    if not eval_trades:
        return {"day": day, "instr": instr, "status": "no-data"}

    minute_forwards = build_minute_forwards(
        instr, legs, iidset, f"{ZERO}/bbo-1m/{day}.dbn.zst", rth_open
    )
    n_forward = sum(1 for f in minute_forwards if f is not None)
    if n_forward < MIN_FORWARD_MINUTES:
        # STOP-CONDITION: the per-minute parity forward cannot be cleanly built from
        # bbo-1m for this session — report it precisely, do NOT fabricate a forward.
        return {"day": day, "instr": instr, "status": "insufficient-forward-grid",
                "n_forward": n_forward}

    M = MULTIPLIER[instr]
    per_k = {k: eval_controls(eval_trades, minute_forwards, M, RATE, k,
                              seeds=DEFAULT_SHUFFLE_SEEDS)
             for k in K_SET}

    # Trade accounting is identical across k (same per_minute_hiro pass), read off k0.
    k0 = per_k[K_SET[0]]
    return {
        "day": day, "instr": instr, "status": "ok",
        "n_forward": n_forward, "forward_cov": n_forward / N_MINUTES,
        "n_legs": len(legs), "n_trades": k0["n_trades"], "n_used": k0["n_used"],
        "skipped_frac": k0["skipped_frac"], "neutral_frac": k0["neutral_frac"],
        "no_forward_frac": k0["no_forward_frac"],
        "per_k": per_k,
    }


def _f(x, p: int = 3) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "  n/a"
    return f"{x:+.{p}f}"


def _fmt_k(m: dict) -> str:
    """One-line per-k rendering, leading with the HEADLINE GAPS (not the raw hit-rate)."""
    return (f"k={m['k']:>2}  REAL_minus_SHUF={_f(m['real_minus_shuffle'])}  "
            f"PRED_minus_CONTEMP={_f(m['predictive_minus_contemp'])}  ||  "
            f"real={_f(m['real_hit'])} shuf={_f(m['shuffle_mean'])}"
            f"[{_f(m['shuffle_min'],2)},{_f(m['shuffle_max'],2)}] "
            f"sgnvol={_f(m['signed_vol_hit'])} contemp={_f(m['contemp_hit'])} "
            f"persist={_f(m['persistence_hit'])}  n={m['n']}")


def main() -> int:
    if not os.path.exists(DEF):
        print(f"ERROR: definition file missing: {DEF}\n"
              f"This harness needs the gitignored data/raw/ pull on disk.")
        return 2

    print("====== FLUX t->t+k PREDICTIVE EVAL — CONTROLLED, look-ahead-free (offline) ======")
    print("*** EXPLORATORY, n=4 correlated days, OPTION-DERIVED put-call-parity forward")
    print("    (NOT a futures price), descriptive only, NOT predictive-validated. ***")
    print("FLUX is strictly t-causal (Σ_{trades<=t} sign·δ·size·M·F); delta_hiro_t -> "
          "sign(F_{t+k}-F_t)")
    print("is look-ahead-free by construction (predictor uses <=t, outcome uses >t).")
    print("THE CONTROL-GAP IS THE HEADLINE, NOT THE RAW HIT-RATE: a raw hit-rate is")
    print("meaningless without REAL_minus_SHUF (edge over sign-shuffled) and")
    print("PRED_minus_CONTEMP (lead over the already-realized move). Shuffle seeds: "
          f"{list(DEFAULT_SHUFFLE_SEEDS)}.\n")

    defs = load_defs()
    rows = []
    for day in DAYS:
        for instr in ("ES", "NQ"):
            res = run_day(instr, day, defs)
            if res is None:
                continue
            rows.append(res)
            if res["status"] != "ok":
                extra = (f" (n_forward={res['n_forward']})"
                         if "n_forward" in res else "")
                print(f"  {day} {instr}: {res['status']}{extra}")
                continue
            cov_flag = ("  [LOW-COV UNDERPOWERED]"
                        if res["forward_cov"] < COVERAGE_OK else "")
            print(f"  {day} {instr}  fwd_cov={res['forward_cov']:.2f} "
                  f"({res['n_forward']}/{N_MINUTES}min)  legs={res['n_legs']}  "
                  f"trades={res['n_trades']} used={res['n_used']}  "
                  f"skip_frac={res['skipped_frac']:.2f} "
                  f"neutral_frac={res['neutral_frac']:.2f} "
                  f"no_fwd_frac={res['no_forward_frac']:.2f}{cov_flag}")
            if res["forward_cov"] < COVERAGE_OK:
                print(f"      [cov-warn] forward coverage {res['forward_cov']:.2f} < "
                      f"{COVERAGE_OK:.2f} => this row is UNDERPOWERED; it is FLAGGED and "
                      f"NOT pooled at equal weight in the per-instrument aggregate.")
            if res["neutral_frac"] >= NEUTRAL_FRAC_DEGENERATE:
                print(f"      [STOP-warn] aggressor-neutral fraction "
                      f"{res['neutral_frac']:.2f} >= {NEUTRAL_FRAC_DEGENERATE:.2f} "
                      f"=> directional test is STRUCTURALLY MEANINGLESS for this row.")
            for k in K_SET:
                print(f"      {_fmt_k(res['per_k'][k])}")

    ok = [r for r in rows if r["status"] == "ok"]
    if not ok:
        print("\n  (no session-instruments produced a usable forward grid)")
        return 0

    def _mean(vals: list) -> float:
        return sum(vals) / len(vals) if vals else float("nan")

    def _wmean(pairs: list) -> float:
        """n-weighted mean of (value, weight) pairs; NaN if total weight is 0."""
        num = sum(v * w for v, w in pairs)
        den = sum(w for _, w in pairs)
        return num / den if den else float("nan")

    INSTRS = ("ES", "NQ")

    def _aggregate(rows_i: list, k: int) -> dict:
        """Per-INSTRUMENT aggregate for one k (NEVER pooled across instruments).

        Pooling ES (fwd_cov ~1.0, n~380) with NQ (fwd_cov 0.43-0.75, n as low as 66)
        lets a single low-coverage NQ row flip the aggregate band and mask a consistent
        ES result. So we aggregate ES and NQ SEPARATELY, n-weight the control-gap mean
        (a 66-minute day must NOT count the same as a 385-minute day), keep the per-day
        band + sign tally, and carry coverage so the classifier can flag underpowered
        cells instead of averaging them in at equal weight.
        """
        days = []
        for r in rows_i:
            m = r["per_k"][k]
            g = m["real_minus_shuffle"]
            if g is None or (isinstance(g, float) and math.isnan(g)):
                continue
            days.append({
                "gap": g, "n": m["n"], "cov": r["forward_cov"],
                "pmc": m["predictive_minus_contemp"],
                "real": m["real_hit"], "shuf": m["shuffle_mean"],
            })
        if not days:
            return {"n_days": 0}
        gaps = [d["gap"] for d in days]
        n_pos = sum(1 for g in gaps if g > 0.0)
        n_neg = sum(1 for g in gaps if g < 0.0)
        pmcs = [d["pmc"] for d in days
                if not (isinstance(d["pmc"], float) and math.isnan(d["pmc"]))]
        return {
            "n_days": len(days),
            "wmean": _wmean([(d["gap"], d["n"]) for d in days]),
            "band": (min(gaps), max(gaps)),
            "n_pos": n_pos, "n_neg": n_neg,
            "consistent": (n_pos == len(days)) or (n_neg == len(days)),
            "sign": 1 if n_pos == len(days) else (-1 if n_neg == len(days) else 0),
            "low_cov_days": sum(1 for d in days if d["cov"] < COVERAGE_OK),
            "min_cov": min(d["cov"] for d in days),
            "total_n": sum(d["n"] for d in days),
            "mean_pmc": _mean(pmcs),
            "mean_real": _mean([d["real"] for d in days]),
            "mean_shuf": _mean([d["shuf"] for d in days]),
        }

    def _classify(a: dict) -> tuple:
        """Derive a THREE-state label from one per-instrument aggregate.

        States: EDGE | NULL | UNDETERMINED | INCONCLUSIVE. The key honesty rule:
        'underpowered' is NEVER collapsed into 'null'. Coverage gates first (you cannot
        call edge-vs-null on too few scored minutes); then a consistent above-threshold
        signal on adequate coverage with enough INDEPENDENT days is the only path to EDGE
        — short of that, a consistent at-/near-threshold signal is UNDETERMINED
        (suggestive but underpowered), and only a genuinely flat gap is NULL.
        """
        if a.get("n_days", 0) == 0:
            return ("INCONCLUSIVE", "no scorable minutes")
        wm = a["wmean"]
        consistency = (f"{max(a['n_pos'], a['n_neg'])}/{a['n_days']} days "
                       f"{'+' if a['sign'] >= 0 else '-'}")
        # 1) coverage gate dominates — too little forward to resolve anything.
        if a["low_cov_days"] > 0:
            return ("UNDETERMINED",
                    f"forward coverage too low ({a['low_cov_days']}/{a['n_days']} days "
                    f"< {COVERAGE_OK:.2f}, min {a['min_cov']:.2f}); cannot resolve "
                    f"edge-vs-null")
        # 2) adequate coverage — judge the directional signal.
        if a["consistent"] and abs(wm) >= SUGGESTIVE_THRESH:
            if abs(wm) >= EDGE_THRESH and a["n_days"] >= MIN_DAYS_FOR_EDGE:
                return ("EDGE",
                        f"consistent {consistency}, n-wtd mean {wm:+.3f} >= "
                        f"{EDGE_THRESH:.2f}, adequate coverage, n_days={a['n_days']} "
                        f"(STILL exploratory)")
            at_thresh = "AT-THRESHOLD " if abs(wm) < EDGE_THRESH else ""
            return ("UNDETERMINED",
                    f"suggestive ({consistency}, n-wtd mean {wm:+.3f}) but {at_thresh}"
                    f"UNDERPOWERED (n_days={a['n_days']} < {MIN_DAYS_FOR_EDGE} "
                    f"independent days)")
        # 3) adequate coverage, no consistent above-threshold signal => genuine null.
        why = "sign inconsistent across days" if not a["consistent"] else "below threshold"
        lo, hi = a["band"]
        return ("NULL",
                f"no edge over shuffle (n-wtd mean {wm:+.3f}, band "
                f"[{lo:+.2f},{hi:+.2f}], {why})")

    print("\n  -------- PER-INSTRUMENT aggregate (NOT pooled — pooling a high-coverage "
          "instrument with a low-coverage one masks both) --------")
    print(f"    thresholds: EDGE needs consistent per-day sign AND n-wtd "
          f"mean(REAL_minus_SHUF) >= {EDGE_THRESH:.2f} on adequate coverage (every day "
          f"fwd_cov >= {COVERAGE_OK:.2f}) AND n_days >= {MIN_DAYS_FOR_EDGE} independent "
          f"days.")
    print(f"                SUGGESTIVE/UNDERPOWERED = consistent sign, n-wtd mean in "
          f"[{SUGGESTIVE_THRESH:.2f},{EDGE_THRESH:.2f}) or too few days; UNDETERMINED = "
          f"any day fwd_cov < {COVERAGE_OK:.2f}; NULL = flat gap on adequate coverage.")

    state: dict = {}
    for instr in INSTRS:
        rows_i = [r for r in ok if r["instr"] == instr]
        if not rows_i:
            print(f"\n    [{instr}] no usable rows.")
            continue
        print(f"\n    [{instr}] {len(rows_i)} day(s)")
        for k in K_SET:
            a = _aggregate(rows_i, k)
            if a.get("n_days", 0) == 0:
                print(f"      k={k:>2}: no scorable minutes.")
                state[(instr, k)] = ("INCONCLUSIVE", "no scorable minutes")
                continue
            lo, hi = a["band"]
            cov_flag = "  [LOW-COV]" if a["low_cov_days"] else ""
            print(f"      k={k:>2}: n-wtd mean REAL_minus_SHUF={_f(a['wmean'])} "
                  f"per-day band=[{_f(lo, 2)},{_f(hi, 2)}]  "
                  f"({max(a['n_pos'], a['n_neg'])}/{a['n_days']} days "
                  f"{'+' if a['sign'] >= 0 else '-'})  "
                  f"mean PRED_minus_CONTEMP={_f(a['mean_pmc'])}  || "
                  f"real={_f(a['mean_real'])} shuf={_f(a['mean_shuf'])}  "
                  f"min_cov={a['min_cov']:.2f} total_n={a['total_n']}{cov_flag}")
            st = _classify(a)
            state[(instr, k)] = st
            print(f"           -> {st[0]}: {st[1]}")

    print("\n  -------- DERIVED THREE-STATE VERDICT (per instrument, from the numbers "
          "above) --------")
    print("    EDGE over shuffle | NULL (no edge) | UNDETERMINED/underpowered (coverage "
          "or day-count too low).")
    print("    'Underpowered' is NEVER collapsed into 'null' — absence of edge and "
          "inability-to-resolve are different states.")
    for k in K_SET:
        parts = []
        for instr in INSTRS:
            if (instr, k) in state:
                lbl, why = state[(instr, k)]
                parts.append(f"{instr} {lbl} ({why})")
        print(f"    k={k:>2}: " + " ; ".join(parts))

    # Honest one-line headline DERIVED from the state map (not hardcoded): we can only
    # claim an edge if some cell reached EDGE, and we can only claim an absence if no
    # cell is UNDETERMINED.
    any_edge = any(s[0] == "EDGE" for s in state.values())
    any_undet = any(s[0] == "UNDETERMINED" for s in state.values())
    caption = []
    caption.append("an EDGE appears at some (instrument,k) but STILL EXPLORATORY at n=4"
                   if any_edge else "NOT a demonstrated edge")
    if any_undet:
        caption.append("NOT a demonstrated absence either (some cells are "
                       "underpowered/UNDETERMINED)")
    print("\n  HEADLINE: " + "; ".join(caption) + ".")

    # Structural-meaningfulness corroboration from trade accounting (pooled is fine here:
    # this is descriptive flow accounting, not the directional verdict).
    mean_neutral = _mean([r["neutral_frac"] for r in ok])
    mean_skip = _mean([r["skipped_frac"] for r in ok])
    print(f"    accounting: mean aggressor-neutral_frac={_f(mean_neutral, 2)} "
          f"mean skipped_frac={_f(mean_skip, 2)} "
          f"(high neutral => signed flow is sparse => test weaker).")

    print("\n  READ: these are the numbers the code produced and a verdict DERIVED from the")
    print("  printed thresholds — NOT a validated finding. 4 correlated days is far too")
    print("  small; the forward is OPTION-DERIVED parity (NOT a traded futures price).")
    print("  EXPLORATORY, n=4, look-ahead-free, control-gap is the headline. FLUX is NOT")
    print("  claimed to predict anything — only the control gaps the numbers actually show.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
