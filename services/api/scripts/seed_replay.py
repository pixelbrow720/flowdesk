#!/usr/bin/env python3
"""Dev replay driver — feed REAL generated session frames into Redis + Timescale.

This is a LOCAL DEVELOPMENT convenience. It does NOT touch the live Databento
account and it does NOT fabricate data: it replays the per-minute ``Snapshot``
JSON already produced by ``services/engine/scripts/gen_session_snapshots.py``
(the same ``build_snapshot`` path the worker runs) so the API serves genuine
historical snapshots without waiting for market hours.

What it does
------------
* **Backfill** (default on): upsert every frame into TimescaleDB via
  :meth:`SnapshotRepository.save_snapshot`, so ``/api/replay`` and
  ``/api/replay/sessions`` return the full session immediately (idempotent on
  the ``(instrument, ts)`` primary key — safe to re-run).
* **Stream** (default on): write frames to Redis one minute at a time via
  :meth:`StateStore.set_now`, which also publishes to ``flowdesk:updates:{instrument}``
  so ``/api/snapshot`` and the ``/ws`` push reflect a "now" that advances at a
  configurable cadence (``--interval`` seconds/frame). ``--loop`` repeats the
  session forever for a continuously-live-looking dev terminal.

The published payload is the exact contract object (``schema_version`` 2); the
API validates it with ``Snapshot.model_validate`` unchanged.

Usage
-----
    # from repo root, datastores up (infra/docker-compose.yml):
    set REDIS_URL=redis://localhost:6379/0
    set TIMESCALE_DSN=postgres://flowdesk:flowdesk@localhost:5432/flowdesk
    python services/api/scripts/seed_replay.py --date 2026-06-09 --interval 1.0 --loop

    # backfill Timescale only (no live stream):
    python services/api/scripts/seed_replay.py --date 2026-06-09 --no-stream

Frames are read from ``--data-dir/<INSTR>_<date>.json`` (default:
``apps/dashboard/public/data`` — the frames the dashboard already ships with).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# Resolve repo layout so `import api.state` / `import db.repo` work regardless of
# the caller's cwd. file = services/api/scripts/seed_replay.py.
_SCRIPTS_DIR = Path(__file__).resolve().parent
_API_ROOT = _SCRIPTS_DIR.parent            # services/api
_REPO_ROOT = _API_ROOT.parents[1]          # repo root
for _p in (str(_API_ROOT / "src"), str(_API_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

DEFAULT_DATA_DIR = _REPO_ROOT / "apps" / "dashboard" / "public" / "data"


def _load_dotenv(path: Path) -> None:
    """Populate os.environ from a .env file WITHOUT overriding existing vars.

    Dev convenience only: the API/worker read env at runtime, and neither uvicorn
    nor this script auto-loads .env. Existing process env always wins.
    """
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


def _load_frames(data_dir: Path, instrument: str, date: str) -> list[dict]:
    """Load and lightly validate the generated session frames for one instrument."""
    path = data_dir / f"{instrument}_{date}.json"
    if not path.is_file():
        raise FileNotFoundError(
            f"no frames for {instrument} {date} at {path}. Generate them with "
            f"services/engine/scripts/gen_session_snapshots.py first."
        )
    frames = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(frames, list) or not frames:
        raise ValueError(f"{path} is not a non-empty JSON array of snapshots")
    # Defensive: the frames must carry the columns repo.save_snapshot binds.
    required = ("instrument", "session_date", "ts", "minute_index", "state", "regime", "forward")
    missing = [k for k in required if k not in frames[0]]
    if missing:
        raise ValueError(f"{path} frame[0] missing required keys: {missing}")
    return frames


async def _backfill(repo: object, frames_by_instr: dict[str, list[dict]]) -> None:
    """Upsert every frame into Timescale (idempotent). Enables /api/replay."""
    for instrument, frames in frames_by_instr.items():
        n = 0
        for frame in frames:
            await repo.save_snapshot(frame)  # type: ignore[attr-defined]
            n += 1
        print(f"  backfill {instrument}: {n} frames -> Timescale", flush=True)


async def _stream(
    store: object,
    frames_by_instr: dict[str, list[dict]],
    *,
    interval: float,
    loop: bool,
) -> None:
    """Publish frames to Redis one minute at a time (advances the live 'now').

    Interleaves instruments so ES and NQ advance together each tick. ``set_now``
    both stores ``flowdesk:now:{instrument}`` and publishes to the WS channel.
    """
    instruments = list(frames_by_instr)
    max_len = max(len(v) for v in frames_by_instr.values())
    pass_no = 0
    while True:
        pass_no += 1
        for i in range(max_len):
            for instrument in instruments:
                frames = frames_by_instr[instrument]
                if i < len(frames):
                    frame = frames[i]
                    await store.set_now(instrument, frame)  # type: ignore[attr-defined]
            if i % 30 == 0 or i == max_len - 1:
                shown = ", ".join(
                    f"{ins}@m{min(i, len(frames_by_instr[ins]) - 1)}" for ins in instruments
                )
                print(f"  stream pass {pass_no}: published minute {i}/{max_len - 1} ({shown})", flush=True)
            await asyncio.sleep(interval)
        if not loop:
            break


async def _amain(args: argparse.Namespace) -> int:
    _load_dotenv(_REPO_ROOT / ".env")

    data_dir = Path(args.data_dir)
    frames_by_instr = {
        instr: _load_frames(data_dir, instr, args.date) for instr in args.instruments
    }
    total = sum(len(v) for v in frames_by_instr.values())
    print(
        f"loaded {total} frames from {data_dir} "
        f"({', '.join(f'{k}={len(v)}' for k, v in frames_by_instr.items())})",
        flush=True,
    )

    pool = None
    try:
        # --- Timescale backfill (optional) ---
        if not args.no_backfill:
            dsn = os.environ.get("TIMESCALE_DSN")
            if not dsn:
                print("TIMESCALE_DSN not set; skipping backfill", file=sys.stderr, flush=True)
            else:
                from db.repo import SnapshotRepository, apply_migrations, create_pool

                pool = await create_pool(dsn)
                async with pool.acquire() as conn:
                    applied = await apply_migrations(conn)
                if applied:
                    print(f"  applied migrations: {applied}", flush=True)
                repo = SnapshotRepository(pool)
                await _backfill(repo, frames_by_instr)

        # --- Redis live stream (optional) ---
        if not args.no_stream:
            redis_url = os.environ.get("REDIS_URL")
            if not redis_url:
                print("REDIS_URL not set; cannot stream", file=sys.stderr, flush=True)
                return 2
            from api.state import create_state_store

            store = create_state_store(redis_url)
            print(
                f"streaming to Redis (interval={args.interval}s, loop={args.loop}); "
                f"Ctrl-C to stop",
                flush=True,
            )
            await _stream(
                store, frames_by_instr, interval=args.interval, loop=args.loop
            )
    finally:
        if pool is not None:
            await pool.close()
    print("done", flush=True)
    return 0


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--date", default="2026-06-09", help="session date YYYY-MM-DD (default 2026-06-09)")
    p.add_argument(
        "--data-dir",
        default=str(DEFAULT_DATA_DIR),
        help=f"dir holding <INSTR>_<date>.json (default {DEFAULT_DATA_DIR})",
    )
    p.add_argument("--instruments", nargs="*", default=["ES", "NQ"])
    p.add_argument(
        "--interval", type=float, default=1.0,
        help="seconds between published minutes when streaming (default 1.0)",
    )
    p.add_argument("--loop", action="store_true", help="repeat the session forever")
    p.add_argument("--no-backfill", action="store_true", help="skip the Timescale backfill")
    p.add_argument("--no-stream", action="store_true", help="skip the Redis live stream")
    args = p.parse_args(argv)
    try:
        return asyncio.run(_amain(args))
    except KeyboardInterrupt:
        print("\ninterrupted", flush=True)
        return 130


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
