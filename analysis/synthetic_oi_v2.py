"""Synthetic-OI GEX vs VOL-GEX — head-to-head on CORRECT 0DTE data. Zero API.

THE WHOLE POINT (why this is NOT just VOL with a fancy name):
  VOL-GEX (locked engine):  Σ static_sign · γ · cum_volume · M · F² · 0.01
      static_sign = +1 call / −1 put  -> ASSUMES dealer long-call/short-put ALWAYS,
      blind to who actually traded. This is the "feels like VOL" baseline.
  SYNTHETIC-OI GEX:         Σ dealer_pos · γ · M · F² · 0.01
      dealer_pos per leg = −Σ(aggressor_sign · size)   [dealer is OPPOSITE the
      customer aggressor: customers lift offers to BUY -> dealer SHORT that leg].
      Sign comes from REAL CME aggressor flow (B/A native) — the thing SpotGamma
      must GUESS via Lee-Ready and we get exact. NON-CIRCULAR (never reads ΔOI).

The concrete "difference from VOL" we measure:
  (1) regime-sign agreement VOL vs SYN per minute,
  (2) % of strikes where flow-derived dealer sign CONTRADICTS the static sign
      (the D.5.4 positioning bias VOL cannot see),
  (3) net-GEX divergence.

HONEST BOUND: 4 days, no price-validation -> this shows STRUCTURAL difference,
NOT that synthetic-OI predicts price better. That needs ~90 days (manual forward
test by the user). Memory-safe streaming.
"""
import sys, math
sys.path.insert(0, "services/engine/src")
from collections import defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import databento as db

from engine.black76 import gamma as b76_gamma
from engine.exposure import DEALER_SIGN_CALL, DEALER_SIGN_PUT
from engine.iv import implied_vol
from engine.snapshot import t_expiry_from_clock, MULTIPLIER

try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

NY = ZoneInfo("America/New_York")
DEF = "data/raw/_probe/definition_range_0605_0612.dbn.zst"
ZERO = "data/raw/zerodte"
RATE = math.log(1.0 + 0.0531)
DAYS = ["2026-06-05","2026-06-08","2026-06-09","2026-06-10"]
STEP = {"ES":5.0,"NQ":10.0}
SAMPLE_ET = [(9,35),(11,0),(12,30),(14,0)]
WINDOW = 0.03
GEX_PCT = 0.01

def dnum(ns): return datetime.fromtimestamp(ns/1e9, tz=timezone.utc)

def load_defs():
    m = defaultdict(lambda: defaultdict(dict))
    for r in db.DBNStore.from_file(DEF):
        ic = str(getattr(r,"instrument_class",""))
        if ic not in ("C","P"): continue
        instr = {"ESM6":"ES","NQM6":"NQ"}.get(str(getattr(r,"underlying","")))
        if not instr: continue
        exp = getattr(r,"expiration",None)
        if not isinstance(exp,int): continue
        dkey = dnum(exp).strftime("%Y-%m-%d")
        rs = str(getattr(r,"raw_symbol",""))
        k=None
        for sep in (" C"," P"):
            if sep in rs:
                try: k=float(rs.split(sep)[1])
                except: pass
        if k is None: continue
        m[instr][dkey][r.instrument_id]=("call" if ic=="C" else "put",k)
    return m

def quotes_at(path, iidset, sample_secs, max_stale=180):
    samples=sorted(sample_secs); res={s:{} for s in samples}
    allq=defaultdict(list)
    for r in db.DBNStore.from_file(path):
        iid=r.instrument_id
        if iid not in iidset: continue
        lv=getattr(r,"levels",None)
        if not lv: continue
        b=getattr(lv[0],"bid_px",None); a=getattr(lv[0],"ask_px",None)
        if not(b and a and b>0 and a>=b): continue
        allq[iid].append((int(getattr(r,"ts_event",0)/1e9),(b/1e9+a/1e9)/2.0))
    for iid,series in allq.items():
        series.sort()
        for s in samples:
            mid=None; mts=None
            for ts,mm in series:
                if ts<=s: mid=mm; mts=ts
                else: break
            if mid is not None and (s-mts)<=max_stale: res[s][iid]=mid
    return res

def signed_flow_at(path, iidset, rth_open, sample_secs):
    """iid -> {sample_sec: (cum_volume, net_signed_flow)} from RTH open..sample.
    net_signed = Σ aggressor_sign·size (B=+1 customer buy, A=−1 customer sell)."""
    samples=sorted(sample_secs); trades=defaultdict(list)
    for r in db.DBNStore.from_file(path):
        iid=r.instrument_id
        if iid not in iidset: continue
        ts=int(getattr(r,"ts_event",0)/1e9)
        if ts<rth_open: continue
        side=(getattr(r,"side","N") or "N")
        s=1 if side=="B" else (-1 if side=="A" else 0)
        sz=float(getattr(r,"size",0) or 0)
        trades[iid].append((ts,sz,s*sz))
    out=defaultdict(dict)
    for iid,series in trades.items():
        series.sort()
        for s in samples:
            vol=sum(sz for ts,sz,_ in series if ts<=s)
            net=sum(sf for ts,_,sf in series if ts<=s)
            out[iid][s]=(vol,net)
    return out

def regime_sign(v):
    return 1 if v>0 else (-1 if v<0 else 0)

print("================ SYNTHETIC-OI GEX vs VOL-GEX (correct 0DTE, zero API) ================")
print("VOL = static dealer sign (blind). SYN = dealer sign from REAL aggressor flow.")
print("*** 4-day STRUCTURAL comparison — NOT price-validated (needs ~90d). ***\n")

defs=load_defs()
agg_disagree=[]
for day in DAYS:
    for instr in ("ES","NQ"):
        legs=defs[instr].get(day,{})
        if not legs: continue
        iidset=set(legs)
        d=datetime.strptime(day,"%Y-%m-%d")
        rth_open=int(datetime(d.year,d.month,d.day,9,30,tzinfo=NY).timestamp())
        sample_secs=[int(datetime(d.year,d.month,d.day,h,mi,tzinfo=NY).timestamp()) for h,mi in SAMPLE_ET]
        q=quotes_at(f"{ZERO}/bbo-1m/{day}.dbn.zst", iidset, sample_secs)
        fl=signed_flow_at(f"{ZERO}/trades/{day}.dbn.zst", iidset, rth_open, sample_secs)
        print(f"########## {day} {instr} ##########")
        for s in sample_secs:
            ts=datetime.fromtimestamp(s,tz=timezone.utc); et=ts.astimezone(NY).strftime("%H:%M")
            mids=q.get(s,{})
            bystrike=defaultdict(dict)
            for iid,(otype,k) in legs.items():
                if iid in mids:
                    vol,net=fl.get(iid,{}).get(s,(0.0,0.0))
                    bystrike[k][otype]=(mids[iid],vol,net)
            both={k:v for k,v in bystrike.items() if "call" in v and "put" in v}
            if len(both)<5: print(f"  {et} ET: (insufficient quotes)"); continue
            atm=min(both,key=lambda k:abs(both[k]["call"][0]-both[k]["put"][0]))
            fwd=atm+(both[atm]["call"][0]-both[atm]["put"][0])
            ks=sorted(both)
            if not(ks[0]<=fwd<=ks[-1]) or abs(both[atm]["call"][0]-both[atm]["put"][0])>6*STEP[instr]:
                print(f"  {et} ET: (forward sanity fail)"); continue
            t_exp=t_expiry_from_clock(ts); M=MULTIPLIER[instr]
            vol_gex=syn_gex=0.0; disagree=n=0
            lo,hi=fwd*(1-WINDOW),fwd*(1+WINDOW)
            for k in both:
                if not(lo<=k<=hi): continue
                cm,cvol,cnet=both[k]["call"]; pm,pvol,pnet=both[k]["put"]
                civ=implied_vol("call",cm,fwd,k,t_exp,RATE); piv=implied_vol("put",pm,fwd,k,t_exp,RATE)
                if not civ or not piv or civ<=0 or piv<=0: continue
                cg=b76_gamma(fwd,k,t_exp,RATE,civ); pg=b76_gamma(fwd,k,t_exp,RATE,piv)
                scale=M*fwd*fwd*GEX_PCT
                # VOL-GEX: static sign x gamma x cum_volume
                vol_gex+=(DEALER_SIGN_CALL*cg*cvol + DEALER_SIGN_PUT*pg*pvol)*scale
                # SYN-GEX: dealer pos (=-customer net signed flow) x gamma
                dealer_call=-cnet; dealer_put=-pnet
                syn_gex+=(dealer_call*cg + dealer_put*pg)*scale
                # disagreement: does flow-derived dealer call-sign contradict static +1?
                if cnet!=0:
                    n+=1
                    if regime_sign(dealer_call)!=DEALER_SIGN_CALL: disagree+=1
                if pnet!=0:
                    n+=1
                    if regime_sign(dealer_put)!=DEALER_SIGN_PUT: disagree+=1
            dis=100.0*disagree/n if n else float("nan")
            if not math.isnan(dis): agg_disagree.append(dis)
            agree = "SAME" if regime_sign(vol_gex)==regime_sign(syn_gex) else "DIFFER"
            print(f"  {et} ET F={fwd:7.1f} | VOL regime={regime_sign(vol_gex):+d} ({vol_gex:+.2e}) | "
                  f"SYN regime={regime_sign(syn_gex):+d} ({syn_gex:+.2e}) | {agree} | flow≠static {dis:.0f}%")
        print()
if agg_disagree:
    print(f"=== mean strikes where REAL flow contradicts VOL's static dealer sign: "
          f"{sum(agg_disagree)/len(agg_disagree):.1f}% ===")
    print("That % is the positioning information VOL-GEX is BLIND to. >0 means SYN")
    print("carries signal VOL cannot. (Structural; predictive value needs ~90d forward test.)")
print("\nDONE.")
