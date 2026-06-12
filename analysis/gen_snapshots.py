#!/usr/bin/env python3
"""Drive gen_session_snapshots.py over the 8-day case-study window.

Runs the REAL engine path (HistoricalSimAdapter -> to_engine_chain ->
build_snapshot) for each (instrument, day), reading the isolated case-study CSVs
in data/case_study/raw and writing per-day Snapshot JSON to
data/case_study/snapshots. No network. Skips days whose CSVs are absent.

Run from repo root:  .venv/Scripts/python.exe analysis/gen_snapshots.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

REPO = Path(__file__).resolve().parents[1]
ENGINE = REPO / "services" / "engine"
RAW = REPO / "data" / "case_study" / "raw"
OUT = REPO / "data" / "case_study" / "snapshots"
PY = REPO / ".venv" / "Scripts" / "python.exe"

TRADING_DAYS = ["2026-06-01", "2026-06-02", "2026-06-03", "2026-06-04",
                "2026-06-05", "2026-06-08", "2026-06-09", "2026-06-10"]


def day_has_data(day: str) -> bool:
    """Require all four schemas present for both instruments for this day."""
    stamp = day.replace("-", "")
    for sch in ("definition", "statistics", "trades", "bbo-1m"):
        for instr in ("ES", "NQ"):
            if not (RAW / sch / f"{instr}_{stamp}_{stamp}.csv").exists():
                return False
    return True


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    env_pythonpath = str(ENGINE / "src")
    ran = skipped = 0
    for day in TRADING_DAYS:
        if not day_has_data(day):
            print(f"[skip] {day}: missing one or more schema CSVs")
            skipped += 1
            continue
        cmd = [
            str(PY), "scripts/gen_session_snapshots.py",
            "--date", day,
            "--data-dir", str(RAW),
            "--out", str(OUT),
            "--quote-schema", "bbo-1m",
            "--instruments", "ES", "NQ",
        ]
        print(f"[run] {day}: {' '.join(cmd[2:])}")
        env = {"PYTHONPATH": env_pythonpath}
        import os
        full_env = {**os.environ, **env}
        r = subprocess.run(cmd, cwd=str(ENGINE), env=full_env,
                           capture_output=True, text=True)
        sys.stdout.write(r.stdout)
        if r.returncode != 0:
            sys.stdout.write(r.stderr[-2000:])
            print(f"[FAIL] {day} rc={r.returncode}")
        else:
            ran += 1
    print(f"\nDone. ran={ran} skipped={skipped}. Snapshots -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
