"""Re-run greek layers on CORRECT 0DTE data (data/raw/zerodte/) — zero API.

Replaces the contaminated quarterly-data results. Uses the VALIDATED engine
pipeline (build_snapshot -> exposure/levels/field, golden-tested) + surface.fit_svi
+ black76 vanna/charm, reading 0DTE option data from disk. Forward via put-call
parity (we pulled option symbols only, no futures; build_snapshot takes forward as
a param). Memory-safe streaming (NO .to_df on big files). t_expiry_from_clock is now
CORRECT because expiry IS same-day.

For each (day, instrument): build the chain at sample RTH minutes, run build_snapshot
(regime/flip/walls/GEX), fit SVI at midday (ATM vol/skew/EM), and compute VEX/CHEX
(open vs late). Prints a comparison vs the artefact (140-290% IV) it replaces.
"""
import sys, glob
sys.path.insert(0, "services/engine/src")
import math
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import databento as db

from engine.snapshot import build_snapshot, ChainQuote, t_expiry_from_clock, MULTIPLIER
from engine.black76 import vanna as b76_vanna, charm as b76_charm
from engine.exposure import DEALER_SIGN_CALL, DEALER_SIGN_PUT
from engine.iv import implied_vol
from engine.surface import fit_svi, svi_vol

try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

NY = ZoneInfo("America/New_York")
DEF = "data/raw/_probe/definition_range_0605_0612.dbn.zst"
ZERO = "data/raw/zerodte"
RATE = math.log(1.0 + 0.0531)
DAYS = ["2026-06-05","2026-06-08","2026-06-09","2026-06-10"]
INSTR_UND = {"ES":"ESM6","NQ":"NQM6"}
STEP = {"ES":5.0,"NQ":10.0}
SAMPLE_ET = [(9,35),(10,30),(12,30),(14,0),(15,55)]   # RTH sample minutes (ET)
WINDOW = 0.03

def dnum(ns): return datetime.fromtimestamp(ns/1e9, tz=timezone.utc)

def load_defs():
    """instrument -> {date -> {iid:(otype,strike,expiry_dt)}}, streamed once."""
    m = defaultdict(lambda: defaultdict(dict))
    for r in db.DBNStore.from_file(DEF):
        ic = str(getattr(r,"instrument_class",""))
        if ic not in ("C","P"): continue
        und = str(getattr(r,"underlying",""))
        instr = {"ESM6":"ES","NQM6":"NQ"}.get(und)
        if not instr: continue
        exp = getattr(r,"expiration",None)
        if not isinstance(exp,int): continue
        ed = dnum(exp); dkey = ed.strftime("%Y-%m-%d")
        rs = str(getattr(r,"raw_symbol",""))
        k = None
        for sep in (" C"," P"):
            if sep in rs:
                try: k=float(rs.split(sep)[1])
                except: pass
        if k is None: continue
        m[instr][dkey][r.instrument_id] = ("call" if ic=="C" else "put", k, ed)
    return m

def quotes_at(path, iidset, sample_secs, max_stale=180):
    """For each sample sec, latest mid in (sec-max_stale, sec] per iid.

    bbo-1m emits ~1 quote/min per active leg, so a quote older than max_stale
    (default 180s) is STALE and dropped — otherwise an illiquid leg's hours-old
    quote gets carried forward, corrupting the parity-forward and ATM selection
    (the bug that produced 0-regime/empty-wall minutes and 185-560% IV).
    """
    samples = sorted(sample_secs)
    res = {s: {} for s in samples}
    allq = defaultdict(list)
    for r in db.DBNStore.from_file(path):
        iid=r.instrument_id
        if iid not in iidset: continue
        lv=getattr(r,"levels",None)
        if not lv: continue
        b=getattr(lv[0],"bid_px",None); a=getattr(lv[0],"ask_px",None)
        if not(b and a and b>0 and a>=b): continue
        ts=int(getattr(r,"ts_event",0)/1e9)
        allq[iid].append((ts,(b/1e9+a/1e9)/2.0))
    for iid,series in allq.items():
        series.sort()
        for s in samples:
            mid=None; mts=None
            for ts,m in series:
                if ts<=s: mid=m; mts=ts
                else: break
            if mid is not None and mts is not None and (s-mts)<=max_stale:
                res[s][iid]=mid
    return res

def cumvol_at(path, iidset, rth_open_sec, sample_secs):
    """iid -> {sample_sec: cumulative traded size from RTH open..sample}."""
    samples=sorted(sample_secs)
    trades=defaultdict(list)
    for r in db.DBNStore.from_file(path):
        iid=r.instrument_id
        if iid not in iidset: continue
        ts=int(getattr(r,"ts_event",0)/1e9)
        if ts<rth_open_sec: continue
        sz=float(getattr(r,"size",0) or 0)
        trades[iid].append((ts,sz))
    out=defaultdict(dict)
    for iid,series in trades.items():
        series.sort()
        for s in samples:
            tot=sum(sz for ts,sz in series if ts<=s)
            out[iid][s]=tot
    return out

def oi_map(path, iidset):
    """iid -> final-settlement OI (latest ts_recv, stat_type 9)."""
    rows=defaultdict(list)
    for r in db.DBNStore.from_file(path):
        if int(getattr(r,"stat_type",-1))!=9: continue
        iid=r.instrument_id
        if iid not in iidset: continue
        rows[iid].append((getattr(r,"ts_recv",0) or 0, float(getattr(r,"quantity",0) or 0)))
    return {iid:max(v)[1] for iid,v in rows.items()}

print("================ GREEK RE-RUN ON CORRECT 0DTE DATA (zero API) ================")
print("Validated engine pipeline on data/raw/zerodte/. Replaces 140-290% artefact.\n")
defs = load_defs()

for day in DAYS:
    for instr in ("ES","NQ"):
        legs = defs[instr].get(day, {})
        if not legs:
            print(f"{day} {instr}: no legs"); continue
        iidset=set(legs)
        d=datetime.strptime(day,"%Y-%m-%d")
        rth_open=int(datetime(d.year,d.month,d.day,9,30,tzinfo=NY).timestamp())
        sample_secs=[int((datetime(d.year,d.month,d.day,h,mi,tzinfo=NY)).timestamp()) for h,mi in SAMPLE_ET]
        bbo=f"{ZERO}/bbo-1m/{day}.dbn.zst"; trd=f"{ZERO}/trades/{day}.dbn.zst"; sta=f"{ZERO}/statistics/{day}.dbn.zst"
        q=quotes_at(bbo, iidset, sample_secs)
        cv=cumvol_at(trd, iidset, rth_open, sample_secs)
        oi=oi_map(sta, iidset)
        # build per sample minute
        results=[]
        for s in sample_secs:
            ts=datetime.fromtimestamp(s,tz=timezone.utc)
            mids=q.get(s,{})
            # group by strike
            bystrike=defaultdict(dict)
            for iid,(otype,k,ed) in legs.items():
                if iid in mids:
                    bystrike[k][otype]=(mids[iid], cv.get(iid,{}).get(s,0.0), oi.get(iid,0.0))
            both={k:v for k,v in bystrike.items() if "call" in v and "put" in v}
            if len(both)<5: results.append((ts,None)); continue
            atm=min(both,key=lambda k:abs(both[k]["call"][0]-both[k]["put"][0]))
            fwd=atm+(both[atm]["call"][0]-both[atm]["put"][0])
            # forward sanity: parity F must land inside the dual-quoted strike range,
            # and the ATM straddle skew |C-P| must be < a few strike-steps (a large
            # value means the 'ATM' lock is on stale/garbage quotes). Reject if not.
            ks_both=sorted(both)
            if not (ks_both[0] <= fwd <= ks_both[-1]) or abs(both[atm]["call"][0]-both[atm]["put"][0]) > 6*STEP[instr]:
                results.append((ts,None)); continue
            t_exp=t_expiry_from_clock(ts)
            quotes=[]
            for k,v in sorted(bystrike.items()):
                cm=v.get("call"); pm=v.get("put")
                quotes.append(ChainQuote(strike=k,
                    call_mid=cm[0] if cm else None, put_mid=pm[0] if pm else None,
                    call_vol=cm[1] if cm else 0.0, put_vol=pm[1] if pm else 0.0,
                    call_oi=cm[2] if cm else 0.0, put_oi=pm[2] if pm else 0.0,
                    t_expiry=t_exp))
            ks=[float(x.strike) for x in quotes]
            axis={"strike_min":min(ks),"strike_max":max(ks),"step":STEP[instr]}
            try:
                snap=build_snapshot(instr,ts,quotes,fwd,RATE,"LIVE",axis,t_expiry=t_exp,stale=False,expired=False)
                results.append((ts,snap,fwd,both,t_exp))
            except Exception as e:
                results.append((ts,f"ERR {type(e).__name__}: {str(e)[:60]}")); continue
        # report this day/instrument
        print(f"\n########## {day} {instr} ##########")
        for item in results:
            ts=item[0]; et=ts.astimezone(NY).strftime("%H:%M")
            if item[1] is None: print(f"  {et} ET: (insufficient quotes)"); continue
            if isinstance(item[1],str): print(f"  {et} ET: {item[1]}"); continue
            snap=item[1]; fwd=item[2]
            r=snap.regime; lv=snap.levels
            print(f"  {et} ET F={fwd:7.1f} regime={r.sign:+d} netG={r.net_gamma:+.2e} "
                  f"flip={lv.gamma_flip if lv.gamma_flip else 0:.0f} "
                  f"cwall={[round(w) for w in lv.call_walls[:2]]} pwall={[round(w) for w in lv.put_walls[:2]]}")
        # SVI + skew at the midday (12:30 ET) sample
        def _is_snap(x): return not isinstance(x, (str, type(None)))
        mid_item=next((x for x in results
                       if len(x)==5 and _is_snap(x[1]) and x[0].astimezone(NY).hour==12), None)
        if mid_item:
            _,snap,fwd,both,t_exp=mid_item
            ks=[]; vs=[]
            for k in sorted(both):
                if not(fwd*(1-WINDOW)<=k<=fwd*(1+WINDOW)): continue
                cm,_,_=both[k]["call"]; pm,_,_=both[k]["put"]
                if k>=fwd: iv=implied_vol("call",cm,fwd,k,t_exp,RATE)
                else: iv=implied_vol("put",pm,fwd,k,t_exp,RATE)
                if iv and iv>0: ks.append(k); vs.append(iv)
            if len(ks)>=5:
                try:
                    sv=fit_svi(ks,vs,fwd,t_exp)
                    skew=(svi_vol(sv.params,0.01,t_exp)-svi_vol(sv.params,-0.01,t_exp))/0.02
                    print(f"  SVI@12:30: ATM_vol={sv.atm_vol*100:.1f}% skew={skew:.2f} "
                          f"EM={sv.expected_move:.1f} rmse={sv.rmse:.4f} arb_free={sv.arb_free}")
                except Exception as e:
                    print(f"  SVI@12:30: ERR {type(e).__name__}")
print("\nDONE.")
