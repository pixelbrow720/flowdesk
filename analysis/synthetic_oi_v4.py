"""Synthetic-OI #4 — HYBRID OI-anchored + flow-update. The product-grade lens.

Per strike K, type tau, minute t, dealer SIGNED CONTRACT position:

    Q4(K,tau,t) = s_static(tau)*OI_open(K,tau)            # (1) carried-in stock anchor
                  + sum_{trade i<=t, K,tau} (-a_i)*size_i*w  # (2) intraday flow update

  s_static = +1 call / -1 put (the irreducible proprietary fallback for the
             DIRECTION of carried-in OI — unknowable from tape, same for all vendors).
  OI_open  = prior-session settled open interest (statistics stat_type=9, ts_ref =
             prior session -> genuine carried-in stock, static intraday). NOT same-day
             delta-OI (degenerate for 0DTE). Null sentinel 2147483647 dropped.
  a_i      = native CME aggressor (B=+1, A=-1, N=0). dealer takes opposite -> -a_i.
             0% N in this data => zero directional info lost (our edge over Lee-Ready).
  w        = open/close weight in [0,1], THE proprietary parameter, made TUNABLE.
             Swept here {0.0, 0.5, 1.0}. w=0 -> pure OI-GEX (SpotGamma classic);
             OI_open absent & w=1 -> pure FLOW-GEX. #4 generalizes all prior lenses.

GEX4(t) = sum_K sum_tau Gamma_tau * Q4 * M * F^2 * 0.01   (locked kernel, signed-Q)

NON-CIRCULAR: never uses same-day delta-OI. Validation (operator, ~90d) is vs
NEXT-day OI settle hold-out + price, not vs the OI used to build it.

HONEST SCOPE: ES robustly supported (OI cov 97-100% near-money, flow/OI 0.2-0.6).
NQ FLAGGED FRAGILE (OI cov 66-87%, flow/OI 0.67-1.25 -> flow swamps thin anchor).
4 correlated days = STRUCTURAL, not price-validated. Zero API, streaming.
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
SAMPLE_ET = [(9,35),(11,0),(12,30),(14,0),(15,30)]
WINDOW = 0.03
GEX_PCT = 0.01
W_SWEEP = [0.0, 0.5, 1.0]          # open/close weight: 0=pure OI, 1=full flow
OI_NULL = 2147483647

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
    """iid -> {sample_sec: net_signed_flow = sum aggressor_sign*size up to sample}."""
    samples=sorted(sample_secs); trades=defaultdict(list)
    for r in db.DBNStore.from_file(path):
        iid=r.instrument_id
        if iid not in iidset: continue
        ts=int(getattr(r,"ts_event",0)/1e9)
        if ts<rth_open: continue
        side=(getattr(r,"side","N") or "N")
        sgn=1 if side=="B" else (-1 if side=="A" else 0)
        sz=float(getattr(r,"size",0) or 0)
        trades[iid].append((ts,sgn*sz))
    out=defaultdict(dict)
    for iid,series in trades.items():
        series.sort()
        for s in samples:
            out[iid][s]=sum(sf for ts,sf in series if ts<=s)
    return out

def oi_at(path, iidset):
    rows=defaultdict(list)
    for r in db.DBNStore.from_file(path):
        if int(getattr(r,"stat_type",-1))!=9: continue
        iid=r.instrument_id
        if iid not in iidset: continue
        q=float(getattr(r,"quantity",0) or 0)
        if q==OI_NULL: continue
        rows[iid].append((getattr(r,"ts_recv",0) or 0, q))
    return {iid:max(v)[1] for iid,v in rows.items()}

print("================ SYNTHETIC-OI #4 — HYBRID OI-anchored + flow-update ================")
print("Q4 = s_static*OI_open + sum(-aggressor*size*w). w-sweep {0=pure OI, .5, 1=full flow}.")
print("vs VOL-GEX (locked). *** ES robust; NQ FLAGGED fragile. 4-day structural, not validated. ***\n")

defs=load_defs()
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
        flag = "" if instr=="ES" else "  [NQ: fragile anchor]"
        print(f"########## {day} {instr}{flag} ##########")
        for s in sample_secs:
            ts=datetime.fromtimestamp(s,tz=timezone.utc); et=ts.astimezone(NY).strftime("%H:%M")
            mids=q.get(s,{})
            bystrike=defaultdict(dict)
            for iid,(otype,k) in legs.items():
                if iid in mids:
                    bystrike[k][otype]=(mids[iid], fl.get(iid,{}).get(s,0.0), oi.get(iid,0.0))
            both={k:v for k,v in bystrike.items() if "call" in v and "put" in v}
            if len(both)<5: print(f"  {et} ET: (insufficient quotes)"); continue
            atm=min(both,key=lambda k:abs(both[k]["call"][0]-both[k]["put"][0]))
            fwd=atm+(both[atm]["call"][0]-both[atm]["put"][0])
            ks=sorted(both)
            if not(ks[0]<=fwd<=ks[-1]) or abs(both[atm]["call"][0]-both[atm]["put"][0])>6*STEP[instr]:
                print(f"  {et} ET: (forward sanity fail)"); continue
            t_exp=t_expiry_from_clock(ts); M=MULTIPLIER[instr]; scale=M*fwd*fwd*GEX_PCT
            lo,hi=fwd*(1-WINDOW),fwd*(1+WINDOW)
            q4={w:0.0 for w in W_SWEEP}
            for k in both:
                if not(lo<=k<=hi): continue
                cm,cnet,coi=both[k]["call"]; pm,pnet,poi=both[k]["put"]
                civ=implied_vol("call",cm,fwd,k,t_exp,RATE); piv=implied_vol("put",pm,fwd,k,t_exp,RATE)
                if not civ or not piv or civ<=0 or piv<=0: continue
                cg=b76_gamma(fwd,k,t_exp,RATE,civ); pg=b76_gamma(fwd,k,t_exp,RATE,piv)
                for w in W_SWEEP:
                    dealer_call = DEALER_SIGN_CALL*coi + (-cnet)*w
                    dealer_put  = DEALER_SIGN_PUT *poi + (-pnet)*w
                    q4[w]+=(dealer_call*cg + dealer_put*pg)*scale
            cells=" | ".join(f"w={w}:{rsign(q4[w]):+d} {q4[w]:+.2e}" for w in W_SWEEP)
            print(f"  {et} ET F={fwd:7.1f} | {cells}")
        print()
print("READ: w=0 column = pure OI-GEX (carried-in stock, SpotGamma-classic).")
print("w=1 = OI anchor fully updated by native-aggressor flow (the #4 product lens).")
print("Watch where w=0 and w=1 DIFFER in sign: that is where intraday flow has")
print("flipped the dealer's positioning vs the morning stock — the actionable signal.")
print("Predictive ranking of w is the operator's ~90-day forward test. DONE.")
