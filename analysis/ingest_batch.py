#!/usr/bin/env python3
"""Async BATCH ingest for bbo-1m — works around the 2.2GB synchronous-stream 504.

The synchronous timeseries.get_range endpoint 504s (gateway timeout) on the single
2.2GB bbo-1m stream. batch.submit_job runs the extract server-side and delivers
downloadable files via plain HTTP GET (resumable) — no gateway timeout, no ban risk
(504 is a timeout, not a penalty).

Same request params as the other three schemas (Option B, end-exclusive):
  dataset=GLBX.MDP3, symbols=[ES.OPT,ES.FUT,NQ.OPT,NQ.FUT], stype_in=parent,
  stype_out=instrument_id, schema=bbo-1m, range [2026-06-02, 2026-06-11).
Cost is within the already-approved $48.35 bundle (bbo-1m est. $37.46).

Key read from .env (never printed). Output consolidated to the existing on-disk
convention: data/raw/bbo-1m/bbo-1m_20260602_20260611.dbn.zst
"""
from __future__ import annotations

import glob
import shutil
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

DATASET = "GLBX.MDP3"
SYMBOLS = ["ES.OPT", "ES.FUT", "NQ.OPT", "NQ.FUT"]
STYPE_IN = "parent"
STYPE_OUT = "instrument_id"
SCHEMA = "bbo-1m"
START = "2026-06-02"
END = "2026-06-11"   # end-exclusive
STAGE = Path("data/raw/_batch")
DEST = Path("data/raw/bbo-1m") / f"bbo-1m_{START.replace('-', '')}_{END.replace('-', '')}.dbn.zst"
POLL_S = 20
DEADLINE_S = 3600


def load_key(p: str = ".env") -> str:
    with open(p, encoding="utf-8") as fh:
        for line in fh:
            s = line.strip()
            if s.startswith("DATABENTO_API_KEY="):
                return s.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("DATABENTO_API_KEY not found in .env")


def main() -> int:
    import databento as db

    key = load_key()
    print(f"key loaded from .env ({len(key)} chars, hidden)")
    client = db.Historical(key)

    try:
        cost = client.metadata.get_cost(
            dataset=DATASET, symbols=SYMBOLS, schema=SCHEMA,
            start=START, end=END, stype_in=STYPE_IN,
        )
        print(f"bbo-1m est. cost ${cost:.4f} (within approved $48.35 bundle)")
    except Exception as e:
        print(f"cost check skipped ({type(e).__name__}: {e})")

    if DEST.exists():
        print(f"[skip] {DEST} already present ({DEST.stat().st_size:,} bytes)")
        return 0

    job = client.batch.submit_job(
        dataset=DATASET, symbols=SYMBOLS, schema=SCHEMA,
        start=START, end=END, stype_in=STYPE_IN, stype_out=STYPE_OUT,
        split_duration="none",   # single combined archive -> matches naming convention
    )
    job_id = job["id"] if isinstance(job, dict) else job.id
    state0 = job.get("state") if isinstance(job, dict) else getattr(job, "state", "?")
    print(f"submitted batch job id={job_id} state={state0}")

    # poll until done
    t0 = time.time()
    last = None
    while time.time() - t0 < DEADLINE_S:
        jobs = client.batch.list_jobs()
        cur = None
        for j in jobs:
            jid = j["id"] if isinstance(j, dict) else j.id
            if jid == job_id:
                cur = j["state"] if isinstance(j, dict) else j.state
                break
        if cur != last:
            print(f"  [{time.strftime('%H:%M:%S')}] state={cur}")
            last = cur
        if cur == "done":
            break
        if cur in ("expired", "deleted"):
            raise SystemExit(f"batch job ended in state={cur}")
        time.sleep(POLL_S)
    else:
        raise SystemExit("timeout waiting for batch job to finish")

    STAGE.mkdir(parents=True, exist_ok=True)
    print(f"downloading job {job_id} -> {STAGE}")
    client.batch.download(output_dir=str(STAGE), job_id=job_id)

    data_files = sorted(glob.glob(str(STAGE / job_id / "*.dbn.zst")))
    print(f"downloaded data files: {[Path(p).name for p in data_files]}")
    if len(data_files) == 1:
        DEST.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(data_files[0], DEST)
        print(f"consolidated -> {DEST} ({DEST.stat().st_size:,} bytes)")
    elif len(data_files) > 1:
        # per-day fallback: rename each into the bbo-1m_<d>_<d>.dbn.zst convention
        import re
        for p in data_files:
            m = re.search(r"(\d{8})", Path(p).name)
            day = m.group(1) if m else Path(p).stem
            out = DEST.parent / f"bbo-1m_{day}_{day}.dbn.zst"
            shutil.copy(p, out)
            print(f"  consolidated -> {out}")
    else:
        print("WARNING: no .dbn.zst data file found in download; inspect staging dir")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
