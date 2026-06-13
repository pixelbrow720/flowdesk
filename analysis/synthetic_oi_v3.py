"""Synthetic-OI GEX (v3) — the REAL SpotGamma-style positioning, vs VOL. Zero API.

Why v2's (V+ΔOI)/2 promise was WRONG for 0DTE, and what's correct instead:
  ΔOI = OI(T)−OI(T−1) per contract. But a 0DTE contract VANISHES after its expiry
  day, so on expiry day ΔOI ≈ −OI_prior (everything closes/expires) — degenerate,
  not a positioning signal. The (V+ΔOI)/2 open/close split is the wrong tool here.
  The CORRECT synthetic-OI base for 0DTE is the carried-in OI LEVEL itself —
  which is literally SpotGamma's published formula  GEX = Γ·OI·sign·M·F²·0.01
  (OI, NOT volume). Our locked engine uses VOL (divergence #1), so OI-GEX is
  already a genuinely different positioning map, not "VOL with a fancy name".

Three GEX computed side-by-side per minute (the concrete comparison):
  VOL-GEX  = Σ static_sign · γ · cum_volume · M·F²·0.01   (our locked engine)
  OI-GEX   = Σ static_sign · γ · open_interest · M·F²·0.01 (classic SpotGamma)
  FLOW-GEX = Σ (−net_aggressor_sign) · γ · |net_flow| · M·F²·0.01  (our edge:
             dealer sign from REAL CME aggressor flow, which SpotGamma must guess)

The irreducible proprietary gap (documented, not hidden): the DIRECTION of the
carried-in OI is unknowable from the tape, so OI-GEX uses the static long-call/
short-put convention for it — same assumption SpotGamma makes. FLOW-GEX is the
part we can do better (native aggressor side). Predictive value (which of the
three actually forecasts price) needs the user's ~90-day manual forward test.

Zero API. Memory-safe streaming. Reuses the validated black76 + iv + staleness
fix from rerun_zerodte.
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
def rsign(v): return 1 if v>0 else (-1 if v<0 else 0)

def load_defs():
    m = defaultdict(lambda: defaultdict(dict))
    for r in db.DBNStore.from_file(DEF):
        ic=str(getattr(r,"instrument_class",""))
        if ic not in ("C","P"): continue
        instr={"ESM6":"ES","NQM6":"NQ"}.get(str(getattr(r,"underlying","")))
        if not instr: continue
        exp=getattr(r,"expiration",None)
        if not isinstance(exp,int): continue
        dkey=dnum(exp).strftime("%Y-%m-%d")
        rs=str(getattr(r,"raw_symbol",""))
        k=None
        for sep in (" C"," P"):
            if sep in rs:
                try: k=float(rs.split(sep)[1])
                except: pass
        if k is None: continue
        m[instr][dkey][r.instrument_id]=("call" if ic=="C" else "put",k)
    return m

def quotes_at(path, iidset, sample_secs, max_stale=180):
    samples=sorted(sample_secs); res={s:{} for s in samples}; allq=defaultdict(list)
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
            mid=mts=None
            for ts,mm in series:
                if ts<=s: mid=mm; mts=ts
                else: break
            if mid is not None and (s-mts)<=max_stale: res[s][iid]=mid
    return res

def flow_at(path, iidset, rth_open, sample_secs):
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

def oi_at(path, iidset):
    rows=defaultdict(list)
    for r in db.DBNStore.from_file(path):
        if int(getattr(r,"stat_type",-1))!=9: continue
        iid=r.instrument_id
        if iid not in iidset: continue
        rows[iid].append((getattr(r,"ts_recv",0) or 0, float(getattr(r,"quantity",0) or 0)))
    return {iid:max(v)[1] for iid,v in rows.items()}

print("================ SYNTHETIC-OI (v3): VOL vs OI vs FLOW GEX — correct 0DTE, zero API ================")
print("VOL=cum-volume·static (locked engine). OI=open-interest·static (classic SpotGamma).")
print("FLOW=aggressor-signed (our native-side edge). *** 4-day STRUCTURAL, not price-validated. ***\n")

defs=load_defs()
oi_total=0; oi_covered=0
for day in DAYS:
    for instr in ("ES","NQ"):
        legs=defs[instr].get(day,{})
        if not legs: continue
        iidset=set(legs)
        d=datetime.strptime(day,"%Y-%m-%d")
        rth_open=int(datetime(d.year,d.month,d.day,9,30,tzinfo=NY).timestamp())
        sample_secs=[int(datetime(d.year,d.month,d.day,h,mi,tzinfo=NY).timestamp()) for h,mi in SAMPLE_ET]
        q=quotes_at(f"{ZERO}/bbo-1m/{day}.dbn.zst", iidset, sample_secs)
        fl=flow_at(f"{ZERO}/trades/{day}.dbn.zst", iidset, rth_open, sample_secs)
        oi=oi_at(f"{ZERO}/statistics/{day}.dbn.zst", iidset)
        oi_total+=len(iidset); oi_covered+=len(oi)
        print(f"########## {day} {instr} ##########")
        for s in sample_secs:
            ts=datetime.fromtimestamp(s,tz=timezone.utc); et=ts.astimezone(NY).strftime("%H:%M")
            mids=q.get(s,{})
            bystrike=defaultdict(dict)
            for iid,(otype,k) in legs.items():
                if iid in mids:
                    vol,net=fl.get(iid,{}).get(s,(0.0,0.0))
                    bystrike[k][otype]=(mids[iid],vol,net,oi.get(iid,0.0))
            both={k:v for k,v in bystrike.items() if "call" in v and "put" in v}
            if len(both)<5: print(f"  {et} ET: (insufficient quotes)"); continue
            atm=min(both,key=lambda k:abs(both[k]["call"][0]-both[k]["put"][0]))
            fwd=atm+(both[atm]["call"][0]-both[atm]["put"][0])
            ks=sorted(both)
            if not(ks[0]<=fwd<=ks[-1]) or abs(both[atm]["call"][0]-both[atm]["put"][0])>6*STEP[instr]:
                print(f"  {et} ET: (forward sanity fail)"); continue
            t_exp=t_expiry_from_clock(ts); M=MULTIPLIER[instr]; scale=M*fwd*fwd*GEX_PCT
            vol_gex=oi_gex=flow_gex=0.0
            lo,hi=fwd*(1-WINDOW),fwd*(1+WINDOW)
            for k in both:
                if not(lo<=k<=hi): continue
                cm,cvol,cnet,coi=both[k]["call"]; pm,pvol,pnet,poi=both[k]["put"]
                civ=implied_vol("call",cm,fwd,k,t_exp,RATE); piv=implied_vol("put",pm,fwd,k,t_exp,RATE)
                if not civ or not piv or civ<=0 or piv<=0: continue
                cg=b76_gamma(fwd,k,t_exp,RATE,civ); pg=b76_gamma(fwd,k,t_exp,RATE,piv)
                vol_gex +=(DEALER_SIGN_CALL*cg*cvol + DEALER_SIGN_PUT*pg*pvol)*scale
                oi_gex  +=(DEALER_SIGN_CALL*cg*coi  + DEALER_SIGN_PUT*pg*poi )*scale
                flow_gex+=((-cnet)*cg + (-pnet)*pg)*scale
            print(f"  {et} ET F={fwd:7.1f} | VOL {rsign(vol_gex):+d} {vol_gex:+.2e} | "
                  f"OI {rsign(oi_gex):+d} {oi_gex:+.2e} | FLOW {rsign(flow_gex):+d} {flow_gex:+.2e}")
        print()
print(f"OI coverage: {oi_covered}/{oi_total} legs had an OI record "
      f"({100*oi_covered/oi_total:.0f}%).")
print("\nREAD: OI-GEX is the genuine SpotGamma formula (Γ·OI), structurally different")
print("from our VOL engine — that is the 'not just VOL' answer. FLOW-GEX adds the")
print("native-aggressor direction SpotGamma must guess. WHICH of the three predicts")
print("price is the ~90-day manual forward test, not decidable on 4 days.")
print("DONE.")
