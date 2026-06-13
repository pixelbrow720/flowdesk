"""FlowDesk validation harness — data-driven driver (reads data/raw/zerodte/, zero API).

Closes the *mechanism* half of docs gap #1: produces, per (session, instrument), the
metrics that the operator's ~90-day forward test will rank — magnitude reconciliation
of synthetic positioning vs settled OI, and price-interaction (level attraction / pin
rate) against a random-strike baseline. The metric MATH is the unit-tested pure core
in ``analysis.harness.metrics``; this file only does the dbn streaming + engine calls
and prints a tidy table.

WHAT THIS IS NOT
================
NOT evidence. There are 4 correctly-structured 0DTE sessions on disk (one a crash
day); every number here is descriptive on a tiny correlated sample. It proves the
harness fires correctly end-to-end, so that the SAME code, run over ~90 sessions the
operator pulls later, becomes an actual test. The directional ΔOI test is deliberately
absent (degenerate on same-session 0DTE — see metrics.py). Cross-day Lapis-1 is also
impossible here (0DTE contracts don't persist day-to-day; zero key overlap).

Run from the repo root with the engine on the path:
    PYTHONPATH=services/engine/src .venv/Scripts/python.exe analysis/harness/run_validation.py
Requires the gitignored data/raw/zerodte/ + data/raw/_probe/ pull on disk.
"""
from __future__ import annotations

import glob
import math
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# Engine import (stdlib-only contract core); databento is a research-only dep.
sys.path.insert(0, os.path.join("services", "engine", "src"))
sys.path.insert(0, ".")  # so `analysis.harness.metrics` imports when run as a script

import databento as db  # noqa: E402

from analysis.harness.metrics import (  # noqa: E402
    distance_matched_levels,
    level_attraction_vs_baseline,
    magnitude_reconciliation,
    oi_walls,
    pin_rate,
)
from engine.snapshot import ChainQuote, build_snapshot, t_expiry_from_clock  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

NY = ZoneInfo("America/New_York")
DEF = "data/raw/_probe/definition_range_0605_0612.dbn.zst"
ZERO = "data/raw/zerodte"
RATE = math.log(1.0 + 0.0531)
DAYS = ["2026-06-05", "2026-06-08", "2026-06-09", "2026-06-10"]
STEP = {"ES": 5.0, "NQ": 10.0}
# Sample minutes for the per-minute close series (pin rate / attraction sampling).
SAMPLE_ET = [(9, 35), (10, 0), (10, 30), (11, 0), (12, 0), (12, 30),
             (13, 0), (14, 0), (15, 0), (15, 30), (15, 55)]
STAT_OI = 9
#: A session-instrument needs at least this many valid sample minutes to be scored;
#: otherwise a 2-of-11 day would yield a meaningless pin_rate reported as real.
MIN_MINUTES = 6


def _dnum(ns: int) -> datetime:
    return datetime.fromtimestamp(ns / 1e9, tz=timezone.utc)


def _aggressor_sign(side: object) -> int:
    s = str(side)
    return 1 if s == "B" else (-1 if s == "A" else 0)


def load_defs() -> dict:
    """instrument -> {date -> {iid: (otype, strike, expiry_dt)}}, streamed once."""
    m: dict = defaultdict(lambda: defaultdict(dict))
    for r in db.DBNStore.from_file(DEF):
        ic = str(getattr(r, "instrument_class", ""))
        if ic not in ("C", "P"):
            continue
        instr = {"ESM6": "ES", "NQM6": "NQ"}.get(str(getattr(r, "underlying", "")))
        if not instr:
            continue
        exp = getattr(r, "expiration", None)
        if not isinstance(exp, int):
            continue
        ed = _dnum(exp)
        rs = str(getattr(r, "raw_symbol", ""))
        k = None
        for sep in (" C", " P"):
            if sep in rs:
                try:
                    k = float(rs.split(sep)[1])
                except ValueError:
                    pass
        if k is None:
            continue
        m[instr][ed.strftime("%Y-%m-%d")][r.instrument_id] = (
            "call" if ic == "C" else "put", k, ed,
        )
    return m


def quotes_at(path: str, iidset: set, sample_secs: list, max_stale: int = 180) -> dict:
    """sample_sec -> {iid: mid}, latest fresh bbo-1m mid in (sec-max_stale, sec]."""
    samples = sorted(sample_secs)
    res: dict = {s: {} for s in samples}
    allq: dict = defaultdict(list)
    for r in db.DBNStore.from_file(path):
        iid = r.instrument_id
        if iid not in iidset:
            continue
        lv = getattr(r, "levels", None)
        if not lv:
            continue
        b = getattr(lv[0], "bid_px", None)
        a = getattr(lv[0], "ask_px", None)
        if not (b and a and b > 0 and a >= b):
            continue
        ts = int(getattr(r, "ts_event", 0) / 1e9)
        allq[iid].append((ts, (b / 1e9 + a / 1e9) / 2.0))
    for iid, series in allq.items():
        series.sort()
        for s in samples:
            mid = mts = None
            for ts, mv in series:
                if ts <= s:
                    mid, mts = mv, ts
                else:
                    break
            if mid is not None and (s - mts) <= max_stale:
                res[s][iid] = mid
    return res


def flow_and_vol(path: str, iidset: set, rth_open_sec: int, sample_secs: list) -> tuple:
    """(cumvol, net_flow): per iid, cumulative size and Σ aggressor_sign·size to each
    sample second, since the RTH open. net_flow uses native CME aggressor side."""
    samples = sorted(sample_secs)
    trades: dict = defaultdict(list)
    for r in db.DBNStore.from_file(path):
        iid = r.instrument_id
        if iid not in iidset:
            continue
        ts = int(getattr(r, "ts_event", 0) / 1e9)
        if ts < rth_open_sec:
            continue
        sz = float(getattr(r, "size", 0) or 0)
        sgn = _aggressor_sign(getattr(r, "side", "N"))
        trades[iid].append((ts, sz, sgn))
    cumvol: dict = defaultdict(dict)
    netflow: dict = defaultdict(dict)
    for iid, series in trades.items():
        series.sort()
        for s in samples:
            cumvol[iid][s] = sum(sz for ts, sz, _ in series if ts <= s)
            netflow[iid][s] = sum(sgn * sz for ts, sz, sgn in series if ts <= s)
    return cumvol, netflow


def oi_settle(path: str, iidset: set) -> dict:
    """iid -> final-settlement OI (latest ts_recv, stat_type 9)."""
    rows: dict = defaultdict(list)
    for r in db.DBNStore.from_file(path):
        if int(getattr(r, "stat_type", -1)) != STAT_OI:
            continue
        iid = r.instrument_id
        if iid not in iidset:
            continue
        rows[iid].append((getattr(r, "ts_recv", 0) or 0, float(getattr(r, "quantity", 0) or 0)))
    return {iid: max(v)[1] for iid, v in rows.items()}


def _build_at(instr, ts, legs, mids, cv, s, t_exp):
    """build_snapshot at one sample second; returns (snap, forward) or (None, None)."""
    bystrike: dict = defaultdict(dict)
    for iid, (otype, k, _ed) in legs.items():
        if iid in mids:
            bystrike[k][otype] = (mids[iid], cv.get(iid, {}).get(s, 0.0))
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
            call_vol=cm[1] if cm else 0.0, put_vol=pm[1] if pm else 0.0,
            t_expiry=t_exp,
        ))
    ks = [float(x.strike) for x in quotes]
    axis = {"strike_min": min(ks), "strike_max": max(ks), "step": STEP[instr]}
    try:
        snap = build_snapshot(instr, ts, quotes, fwd, RATE, "LIVE", axis,
                              t_expiry=t_exp, stale=False, expired=False,
                              with_exposure_ext=True)
        return snap, fwd
    except Exception:
        return None, None


def run_day(instr: str, day: str, defs: dict) -> dict | None:
    legs = defs[instr].get(day, {})
    if not legs:
        return None
    iidset = set(legs)
    d = datetime.strptime(day, "%Y-%m-%d")
    rth_open = int(datetime(d.year, d.month, d.day, 9, 30, tzinfo=NY).timestamp())
    sample_secs = [int(datetime(d.year, d.month, d.day, h, mi, tzinfo=NY).timestamp())
                   for h, mi in SAMPLE_ET]
    q = quotes_at(f"{ZERO}/bbo-1m/{day}.dbn.zst", iidset, sample_secs)
    cv, nf = flow_and_vol(f"{ZERO}/trades/{day}.dbn.zst", iidset, rth_open, sample_secs)
    oi = oi_settle(f"{ZERO}/statistics/{day}.dbn.zst", iidset)

    # ---- per-minute snapshots -> forward series + levels at open/close ---------
    closes = []
    first_snap = last_snap = None
    fwd_open = fwd_close = None
    dropped = 0
    for s in sample_secs:
        ts = datetime.fromtimestamp(s, tz=timezone.utc)
        snap, fwd = _build_at(instr, ts, legs, q.get(s, {}), cv, s, t_expiry_from_clock(ts))
        if snap is None:
            dropped += 1
            continue
        closes.append(fwd)
        if first_snap is None:
            first_snap, fwd_open = snap, fwd
        last_snap, fwd_close = snap, fwd
    if first_snap is None or last_snap is None or len(closes) < MIN_MINUTES:
        return {"day": day, "instr": instr, "status": "insufficient-quotes",
                "n_minutes": len(closes), "dropped": dropped}

    # ---- magnitude reconciliation: settle OI vs net aggressor flow (per leg) ----
    # Controlled for cumulative VOLUME: |flow| and settled OI both scale with raw
    # activity, so the headline number is the PARTIAL correlation holding volume
    # fixed (the part NOT explained by "active strikes are active"). See metrics §2.
    settle_by_key: dict = {}
    flow_by_key: dict = {}
    vol_by_key: dict = {}
    call_oi_by_strike: dict = {}
    put_oi_by_strike: dict = {}
    last_s = sample_secs[-1]
    for iid, (otype, k, _ed) in legs.items():
        is_call = otype == "call"
        if iid in oi:
            settle_by_key[(k, is_call)] = oi[iid]
            if is_call:
                call_oi_by_strike[k] = call_oi_by_strike.get(k, 0.0) + oi[iid]
            else:
                put_oi_by_strike[k] = put_oi_by_strike.get(k, 0.0) + oi[iid]
        fv = nf.get(iid, {}).get(last_s)
        if fv is not None:
            flow_by_key[(k, is_call)] = fv
        vv = cv.get(iid, {}).get(last_s)
        if vv is not None:
            vol_by_key[(k, is_call)] = vv
    recon = magnitude_reconciliation(settle_by_key, flow_by_key, control=vol_by_key)

    # ---- price interaction vs DISTANCE-MATCHED baseline ------------------------
    # CAUSAL: levels are taken from the OPEN snapshot (pre-committed), then we ask
    # whether price migrated toward them by the close. Using the CLOSE snapshot's
    # levels would be circular — gamma_flip/largest_gex sit near the current price
    # by construction, so "price reached them by close" would be tautological.
    # Baseline = strikes at a COMPARABLE distance from the open forward (not all
    # strikes), else a near-the-money level's attraction is biased vs a far-strike
    # mean. Walls are intentionally NOT scored here: they need OI (not fed to the
    # offline chain), and the only OI we have is the EOD settle — using that at the
    # open would be look-ahead. Walls belong to a separate OI-aware harness pass.
    lv = first_snap.levels
    axis = first_snap.axis
    all_strikes = [axis.strike_min + i * axis.step
                   for i in range(int((axis.strike_max - axis.strike_min) / axis.step) + 1)]
    price = {}
    for name, level in (("gamma_flip", lv.gamma_flip),
                        ("largest_gex", lv.largest_gex)):
        if level is None:
            continue
        baseline = distance_matched_levels(level, all_strikes, fwd_open,
                                           band=STEP[instr])
        attr = level_attraction_vs_baseline(fwd_open, fwd_close, level, baseline)
        pin = pin_rate(closes, level, tolerance=STEP[instr])
        price[name] = {"level": level, "excess_attraction": attr["excess"],
                       "n_baseline": attr["n_baseline"], "pin_rate": pin["pin_rate"]}

    return {
        "day": day, "instr": instr, "status": "ok",
        "fwd_open": fwd_open, "fwd_close": fwd_close,
        "n_minutes": len(closes), "dropped": dropped,
        "reconciliation": recon, "price": price,
        # Carried for the NEXT session's cross-day OI-wall test (look-ahead-free:
        # today's settle-OI walls are tested against tomorrow's price).
        "call_oi_by_strike": call_oi_by_strike,
        "put_oi_by_strike": put_oi_by_strike,
        "closes": closes,
        "all_strikes": all_strikes,
    }


def main() -> int:
    if not os.path.exists(DEF):
        print(f"ERROR: definition file missing: {DEF}\n"
              f"This harness needs the gitignored data/raw/ pull on disk.")
        return 2
    print("=============== FlowDesk VALIDATION HARNESS (mechanism, NOT evidence) ===============")
    print(f"Sessions on disk: {len([d for d in DAYS if glob.glob(f'{ZERO}/bbo-1m/{d}.dbn.zst')])}"
          f" of {len(DAYS)} (4 correlated 0DTE days — descriptive only).")
    print("ΔOI: MAGNITUDE-only + volume-controlled (direction degenerate on 0DTE; raw rho")
    print("is confounded by activity). Price: vs DISTANCE-MATCHED baseline. No verdicts —")
    print("on this sample nothing here is a signal; append ~90 sessions before reading.\n")
    defs = load_defs()
    rows = []
    by_key: dict = {}
    for day in DAYS:
        for instr in ("ES", "NQ"):
            res = run_day(instr, day, defs)
            if res is None:
                continue
            rows.append(res)
            if res["status"] == "ok":
                by_key[(instr, day)] = res
            if res["status"] != "ok":
                print(f"  {day} {instr}: {res['status']} "
                      f"(n_minutes={res.get('n_minutes', 0)}, dropped={res.get('dropped', 0)})")
                continue
            rc = res["reconciliation"]
            rho = f"{rc['rho']:+.3f}" if rc["rho"] is not None else " n/a "
            prho = f"{rc['partial_rho']:+.3f}" if rc["partial_rho"] is not None else " n/a "
            print(f"  {day} {instr}  F {res['fwd_open']:.0f}->{res['fwd_close']:.0f}  "
                  f"n_min={res['n_minutes']}/{len(SAMPLE_ET)} drop={res['dropped']}  "
                  f"recon[n={rc['n']:>3} rho_raw={rho} rho|vol={prho}]")
            for nm, pv in res["price"].items():
                ex = pv["excess_attraction"]
                exs = f"{ex:+.3f}" if ex is not None else "n/a"
                pin = pv["pin_rate"]
                print(f"        {nm:>12} @{pv['level']:.0f}: "
                      f"excess_attraction={exs} (nbase={pv['n_baseline']})  pin_rate={pin:.2f}")

    # ---- cross-day OI-wall test (look-ahead-free) ------------------------------
    # PRIOR session's settle-OI walls (raw OI, SpotGamma-classic) tested against the
    # CURRENT session's price. T-1 fully precedes T, so the walls are pre-committed;
    # strikes persist across days even though the 0DTE contracts do not. This is a
    # WEAKER claim than the product's intraday gamma-$ wall (we lack prior-day gamma),
    # but it is the only wall test this data supports without look-ahead.
    print("\n--- cross-day OI-wall persistence (prior settle-OI walls vs next-day price) ---")
    wall_n = 0
    for instr in ("ES", "NQ"):
        for prev, cur in zip(DAYS[:-1], DAYS[1:]):
            p = by_key.get((instr, prev))
            c = by_key.get((instr, cur))
            if not p or not c:
                continue
            fwd_open_c = c["fwd_open"]
            walls = oi_walls(p["call_oi_by_strike"], p["put_oi_by_strike"], fwd_open_c)
            for side in ("call_walls", "put_walls"):
                levels = walls[side]
                if not levels:
                    continue
                lvl = levels[0]  # rank-1 wall
                baseline = distance_matched_levels(lvl, c["all_strikes"], fwd_open_c,
                                                   band=STEP[instr])
                attr = level_attraction_vs_baseline(fwd_open_c, c["fwd_close"], lvl, baseline)
                pin = pin_rate(c["closes"], lvl, tolerance=STEP[instr])
                exs = f"{attr['excess']:+.3f}" if attr["excess"] is not None else "n/a"
                print(f"  {prev[5:]}->{cur[5:]} {instr} {side[:4]}1 @{lvl:.0f} "
                      f"(F={fwd_open_c:.0f}): excess_attraction={exs} "
                      f"(nbase={attr['n_baseline']})  pin_rate={pin['pin_rate']:.2f}")
                wall_n += 1
    if wall_n == 0:
        print("  (no consecutive session pairs with usable OI walls)")

    print(f"\n{len([r for r in rows if r['status'] == 'ok'])} session-instruments computed. "
          f"Append ~90 sessions and re-run before reading ANY result as a signal.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
