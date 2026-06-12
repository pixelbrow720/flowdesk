"""Stage 2 (memory-safe, crash-resilient): resolve 0DTE symbols by STREAMING the
saved definition (NO to_df — that caused MemoryError/crash), then pull market data.

- Reads symbols from JSON cache if present; else streams definition -> JSON.
- Market pulls use get_range(...).to_file() = streamed to disk, no big DataFrame.
- Idempotent (skip existing), cost-gated per day (parent, cheap), NO retry,
  inter-call sleep, abort on any error. Key from .env, never printed.
"""
import sys, os, time, json
sys.path.insert(0, "services/engine/src")
from datetime import datetime, timezone
import databento as db
from databento.common.error import BentoClientError, BentoServerError

DEF_SAVE="data/raw/_probe/definition_range_0605_0612.dbn.zst"
SESSIONS=["2026-06-05","2026-06-08","2026-06-09","2026-06-10","2026-06-11"]
NEXT={"2026-06-05":"2026-06-06","2026-06-08":"2026-06-09","2026-06-09":"2026-06-10",
      "2026-06-10":"2026-06-11","2026-06-11":"2026-06-12"}
PARENTS={"2026-06-05":["EW1.OPT","QN1.OPT"],"2026-06-08":["E2A.OPT","Q2A.OPT"],
         "2026-06-09":["E2B.OPT","Q2B.OPT"],"2026-06-10":["E2C.OPT","Q2C.OPT"],
         "2026-06-11":["E2D.OPT","Q2D.OPT"]}
EMINI={"ESM6","NQM6"}
SCHEMAS=["statistics","trades","bbo-1m"]
OUTDIR="data/raw/zerodte"
SYMS_JSON=f"{OUTDIR}/symbols_by_day.json"
PER_DAY_BBO_CEIL=12.0; GLOBAL_CEIL=45.0; SLEEP=2.5

def load_key(p=".env"):
    for line in open(p,encoding="utf-8"):
        if line.strip().startswith("DATABENTO_API_KEY="):
            return line.split("=",1)[1].strip().strip('"').strip("'")
    raise SystemExit("no key")

os.makedirs(OUTDIR,exist_ok=True)

# ---- 1. resolve symbols (streaming, memory-safe) or load cache ----
if os.path.exists(SYMS_JSON):
    syms_by_day=json.load(open(SYMS_JSON))
    print(f"loaded symbol cache {SYMS_JSON}")
else:
    print("streaming definition to resolve symbols (memory-safe, no to_df)...")
    target={s for s in SESSIONS}
    acc={s:set() for s in SESSIONS}
    store=db.DBNStore.from_file(DEF_SAVE)
    for r in store:
        if str(getattr(r,"instrument_class","")) not in ("C","P"): continue
        if str(getattr(r,"underlying","")) not in EMINI: continue
        exp=getattr(r,"expiration",None)
        if not isinstance(exp,int): continue
        d=datetime.fromtimestamp(exp/1e9,tz=timezone.utc).strftime("%Y-%m-%d")
        if d in target:
            acc[d].add(str(getattr(r,"raw_symbol","")))
    syms_by_day={s:sorted(acc[s]) for s in SESSIONS}
    json.dump(syms_by_day, open(SYMS_JSON,"w"))
    print(f"saved {SYMS_JSON}")
for s in SESSIONS:
    print(f"  {s}: {len(syms_by_day[s])} legs")

# ---- 2. per-day cost ceiling (parent bbo, 2 syms, cheap, no 414) ----
key=load_key(); print(f"\nkey loaded ({len(key)} chars, hidden)")
client=db.Historical(key)
print("per-day bbo parent cost ceiling:")
cum=0.0
for s in SESSIONS:
    try:
        c=client.metadata.get_cost(dataset="GLBX.MDP3",schema="bbo-1m",
            symbols=PARENTS[s],stype_in="parent",start=s,end=NEXT[s])
    except (BentoServerError,BentoClientError) as e:
        print(f"  {s}: cost ERR {e.http_status} -> assume ceiling"); c=PER_DAY_BBO_CEIL
    cum+=c; print(f"  {s}: ${c:.4f}")
    if c>PER_DAY_BBO_CEIL: print(f"  ABORT {s} > ${PER_DAY_BBO_CEIL}"); raise SystemExit(0)
    time.sleep(1.0)
print(f"  cumulative ceiling: ${cum:.2f}")
if cum>GLOBAL_CEIL: print(f"ABORT cumulative > ${GLOBAL_CEIL}"); raise SystemExit(0)

# ---- 3. pull market data per day/schema, scoped, streamed to disk, no retry ----
print("\npulling market data (scoped, streamed, idempotent, no retry):")
total=0
for s in SESSIONS:
    syms=syms_by_day[s]
    for sch in SCHEMAS:
        d=os.path.join(OUTDIR,sch); os.makedirs(d,exist_ok=True)
        out=os.path.join(d,f"{s}.dbn.zst")
        if os.path.exists(out):
            print(f"  [skip] {out}"); total+=os.path.getsize(out); continue
        try:
            store=client.timeseries.get_range(dataset="GLBX.MDP3",schema=sch,
                symbols=syms,stype_in="raw_symbol",start=s,end=NEXT[s])
            store.to_file(out)
            sz=os.path.getsize(out); total+=sz
            print(f"  {s} {sch:11s} -> {sz:,} bytes")
        except BentoServerError as e:
            print(f"  {s} {sch} SERVER {e.http_status}: {e.message}. STOP."); raise SystemExit(1)
        except BentoClientError as e:
            print(f"  {s} {sch} CLIENT {e.http_status}: {e.message}. STOP."); raise SystemExit(1)
        time.sleep(SLEEP)
print(f"\nDONE. total {total:,} bytes -> {OUTDIR}/")
