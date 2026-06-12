#!/usr/bin/env python3
"""Re-download an EXISTING completed Databento batch job (no re-submit, no re-bill).

The initial download truncated (41.8M of expected 778M). The job already
completed server-side, so we just re-fetch its files. Verifies the data file
size against the manifest, then consolidates to the on-disk convention.
Key from .env (never printed).
"""
from __future__ import annotations

import glob
import json
import shutil
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

JOB_ID = "GLBX-20260612-N7YWLUTJLY"
STAGE = Path("data/raw/_batch")
DEST = Path("data/raw/bbo-1m/bbo-1m_20260602_20260611.dbn.zst")


def load_key(p: str = ".env") -> str:
    with open(p, encoding="utf-8") as fh:
        for line in fh:
            s = line.strip()
            if s.startswith("DATABENTO_API_KEY="):
                return s.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("DATABENTO_API_KEY not found in .env")


def expected_size() -> int:
    man = json.loads((STAGE / JOB_ID / "manifest.json").read_text())
    for f in man["files"]:
        if f["filename"].endswith(".dbn.zst"):
            return f["size"]
    raise SystemExit("no .dbn.zst entry in manifest")


def main() -> int:
    import databento as db

    exp = expected_size()
    print(f"expected data-file size from manifest: {exp:,} bytes")

    # delete truncated data file so the re-download fetches it fresh
    for p in glob.glob(str(STAGE / JOB_ID / "*.dbn.zst")):
        sz = Path(p).stat().st_size
        if sz < exp:
            print(f"removing truncated {Path(p).name} ({sz:,} < {exp:,})")
            Path(p).unlink()

    key = load_key()
    print(f"key loaded from .env ({len(key)} chars, hidden)")
    client = db.Historical(key)

    print(f"re-downloading job {JOB_ID} -> {STAGE}")
    client.batch.download(output_dir=str(STAGE), job_id=JOB_ID)

    files = sorted(glob.glob(str(STAGE / JOB_ID / "*.dbn.zst")))
    if not files:
        print("ERROR: no .dbn.zst after download")
        return 1
    got = Path(files[0]).stat().st_size
    print(f"downloaded {Path(files[0]).name}: {got:,} bytes (expected {exp:,})")
    if got != exp:
        print(f"ERROR: size mismatch — still incomplete ({got:,} != {exp:,})")
        return 2

    DEST.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(files[0], DEST)
    print(f"consolidated -> {DEST} ({DEST.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
