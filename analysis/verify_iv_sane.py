"""Prove the symbology fix works: is IV SANE on real 0DTE data? ZERO API.

Reads only local files: streams definition_range for iid->(type,strike,expiry),
reads bbo-1m for one RTH minute, estimates forward via put-call parity (no futures
pull needed), solves Black-76 IV via engine.iv. Sane IV (~10-60%) => fix works;
insane (>100%) => still broken (the 140-290% artefact from quarterly mispricing).

Test day: 2026-06-09 (a crash day = hardest test). Memory-safe (streaming).
"""
import sys
sys.path.insert(0, "services/engine/src")
from datetime import datetime, timezone
import databento as db
from engine.iv import implied_vol

DEF="data/raw/_probe/definition_range_0605_0612.dbn.zst"
BBO="data/raw/zerodte/bbo-1m/2026-06-09.dbn.zst"
SESSION_EXP=datetime(2026,6,9,20,0,tzinfo=timezone.utc)  # 16:00 ET = 20:00 UTC (EDT)
RATE=__import__("math").log(1.0+0.0531)
PROBE_MIN=datetime(2026,6,9,14,30,tzinfo=timezone.utc)   # 10:30 ET, mid-morning

# 1) iid -> (type, strike, expiry_date) for ESM6 0DTE options, streaming
print("streaming definition for ESM6 0DTE iid map...")
iidmap={}
for r in db.DBNStore.from_file(DEF):
    if str(getattr(r,"instrument_class",""))not in("C","P"): continue
    if str(getattr(r,"underlying",""))!="ESM6": continue
    exp=getattr(r,"expiration",None)
    if not isinstance(exp,int): continue
    ed=datetime.fromtimestamp(exp/1e9,tz=timezone.utc)
    if ed.date()!=SESSION_EXP.date(): continue
    rs=str(getattr(r,"raw_symbol",""))
    # strike from raw_symbol after C/P
    k=None
    for sep in(" C"," P"):
        if sep in rs:
            try:k=float(rs.split(sep)[1])
            except:pass
    iidmap[r.instrument_id]=("call" if str(r.instrument_class)=="C" else "put",k,ed)
print(f"  {len(iidmap)} ESM6 0DTE option legs")

# 2) bbo-1m: capture mids at the probe minute
print(f"reading bbo-1m mids at {PROBE_MIN.strftime('%H:%MZ')}...")
mids={}  # iid -> mid
target=int(PROBE_MIN.timestamp())
for r in db.DBNStore.from_file(BBO):
    iid=r.instrument_id
    if iid not in iidmap: continue
    ts=int(getattr(r,"ts_event",0)/1e9)
    if ts//60 != target//60: continue
    lv=getattr(r,"levels",None)
    if not lv: continue
    b=getattr(lv[0],"bid_px",None); a=getattr(lv[0],"ask_px",None)
    if b and a and b>0 and a>=b:
        mids[iid]=(b/1e9+a/1e9)/2.0
print(f"  {len(mids)} legs quoted at probe minute")

# 3) group by strike -> (call_mid, put_mid)
bystrike={}
for iid,m in mids.items():
    typ,k,ed=iidmap[iid]
    if k is None: continue
    bystrike.setdefault(k,{})[typ]=m
both={k:v for k,v in bystrike.items() if "call" in v and "put" in v}
print(f"  {len(both)} strikes with both call & put")

# 4) forward via parity: strike minimizing |C-P| ~ ATM; F = K + (C-P)
T=(SESSION_EXP-PROBE_MIN).total_seconds()/(365*24*3600)
print(f"  T to expiry = {T:.6f} yr ({T*365*24:.2f} hours)")
atm_k=min(both, key=lambda k: abs(both[k]["call"]-both[k]["put"]))
fwd=atm_k+(both[atm_k]["call"]-both[atm_k]["put"])
print(f"  ATM strike={atm_k}, parity forward F={fwd:.1f}")

# 5) solve IV for near-ATM strikes (within +-3% of forward)
print(f"\n=== IV (Black-76) near ATM — SANE if ~10-60%, ARTEFACT if >100% ===")
lo,hi=fwd*0.97,fwd*1.03
rows=[]
for k in sorted(both):
    if not(lo<=k<=hi): continue
    for typ in("call","put"):
        iv=implied_vol(typ,both[k][typ],fwd,k,T,RATE)
        if iv: rows.append((k,typ,both[k][typ],iv))
for k,typ,mid,iv in rows[:20]:
    print(f"  K={k:>6.0f} {typ:>4} mid={mid:>7.2f}  IV={iv*100:>6.1f}%")
ivs=[iv for _,_,_,iv in rows]
if ivs:
    ivs.sort()
    med=ivs[len(ivs)//2]
    print(f"\n  median near-ATM IV = {med*100:.1f}%   (n={len(ivs)})")
    print("  VERDICT:", "SANE — fix works!" if 0.03<med<1.0 else "STILL ARTEFACT — investigate")
else:
    print("  no IV solved")
