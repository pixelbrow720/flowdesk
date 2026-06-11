#!/usr/bin/env python3
"""Batched Databento GLBX.MDP3 ingest for FlowDesk (PRD #8 §9 — ANTI-BLOKIR).

GOLDEN RULE (PRD #8 §9 / AC-A7): pull **one schema = one full date-range
request**, then cache to disk. NEVER loop per day — a per-day loop is the classic
rate-limit / ban trigger. With 4 schemas you make exactly **4 requests total**,
each covering the full ``[start, end]`` window for ALL symbols at once.

This script makes NO network calls when imported or tested. It must be RUN BY
THE USER, in their own environment, with a valid ``DATABENTO_API_KEY`` and an
active GLBX.MDP3 subscription (TODO-FROM-OWNER). The sandbox has no network and
no ``databento`` package; the package is imported lazily inside :func:`run_ingest`.

WHAT IT WRITES (cache layout consumed by HistoricalSimAdapter)
--------------------------------------------------------------
    DATA_DIR/
      <schema>/<schema>_<START>_<END>.dbn.zst     # raw archive (one per schema)
      <schema>/<INSTR>_<START>_<END>.csv          # decoded, per-instrument cache

  * One raw ``.dbn.zst`` per schema (the literal request output) — archival.
  * Per-instrument decoded CSVs (``pretty_px=True, pretty_ts=True``) split from
    the SAME single response — no extra requests. These are what the adapter reads.

RATE-LIMIT-SAFE BEHAVIOUR
-------------------------
  * 1 request per schema (full range, all symbols) — see :func:`build_request_plan`.
  * A small fixed delay between schema requests (``INTER_REQUEST_DELAY_S``).
  * Exponential backoff with jitter on transient errors (:func:`_with_backoff`).
  * Idempotent: existing cache files are skipped unless ``--force``.

DATASET / SYMBOLOGY
-------------------
  dataset  = "GLBX.MDP3"
  schemas  = definition, statistics, trades, mbp-1   (bbo-1m may replace mbp-1)
  symbols  = ES.OPT, ES.FUT, NQ.OPT, NQ.FUT          (parent symbology)
  stype_in = "parent"

Usage (run by the user, NOT in CI):
    export DATABENTO_API_KEY=db-xxxx
    export DATA_DIR=/data/raw
    python scripts/ingest_databento.py --start 2026-06-01 --end 2026-06-05
"""
from __future__ import annotations

import argparse
import os
import random
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Sequence, TypeVar

DATASET = "GLBX.MDP3"
DEFAULT_SCHEMAS: tuple[str, ...] = ("definition", "statistics", "trades", "mbp-1")
PARENT_SYMBOLS: tuple[str, ...] = ("ES.OPT", "ES.FUT", "NQ.OPT", "NQ.FUT")
INSTRUMENTS: tuple[str, ...] = ("ES", "NQ")
STYPE_IN = "parent"

# Rate-limit-safe knobs.
INTER_REQUEST_DELAY_S = 2.0
MAX_RETRIES = 5
BACKOFF_BASE_S = 1.5

# 5 development days (plumbing/UI). Adjust to real trading days as needed.
DEV_START = date(2026, 6, 1)
DEV_END = date(2026, 6, 5)

# Golden dataset: add 2-3 EXTREME days on top of the 5 dev days. These exercise
# regimes the dev window may not (PRD #8 §9). Confirm exact dates against the
# calendar before pulling (TODO-FROM-OWNER: pick real sessions).
EXTREME_DAYS: tuple[tuple[str, str], ...] = (
    ("2026-06-19", "Triple-witching / quarterly OPEX (huge OI, pinning)"),
    ("2026-06-17", "Trending / high-vol session (FOMC-style directional move)"),
    ("2026-07-03", "Half-day (early close 13:00 ET) — session-edge handling"),
)

T = TypeVar("T")


@dataclass(frozen=True)
class RequestSpec:
    """One Databento request: a single schema over the full range, all symbols."""

    schema: str
    dataset: str
    symbols: tuple[str, ...]
    stype_in: str
    start: str  # YYYY-MM-DD inclusive
    end: str    # YYYY-MM-DD inclusive

    @property
    def stem(self) -> str:
        return f"{self.schema}_{self.start.replace('-', '')}_{self.end.replace('-', '')}"


@dataclass
class IngestConfig:
    api_key: str
    data_dir: Path
    start: str
    end: str
    schemas: tuple[str, ...] = DEFAULT_SCHEMAS
    symbols: tuple[str, ...] = PARENT_SYMBOLS
    force: bool = False


def build_request_plan(
    start: str, end: str, *, schemas: Sequence[str] = DEFAULT_SCHEMAS,
    symbols: Sequence[str] = PARENT_SYMBOLS,
) -> list[RequestSpec]:
    """Return EXACTLY one RequestSpec per schema (single full-range pull).

    This is the heart of the anti-block strategy and is pure/offline so it can
    be unit-tested (AC-A7: number of requests == number of schemas).
    """
    _validate_range(start, end)
    return [
        RequestSpec(
            schema=schema,
            dataset=DATASET,
            symbols=tuple(symbols),
            stype_in=STYPE_IN,
            start=start,
            end=end,
        )
        for schema in schemas
    ]


def _validate_range(start: str, end: str) -> None:
    s = datetime.strptime(start, "%Y-%m-%d").date()
    e = datetime.strptime(end, "%Y-%m-%d").date()
    if e < s:
        raise ValueError(f"end {end} is before start {start}")


def _with_backoff(fn: Callable[[], T], *, what: str) -> T:
    """Run ``fn`` with exponential backoff + jitter on transient failures."""
    last: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - surface after retries
            last = exc
            if attempt == MAX_RETRIES:
                break
            sleep_s = BACKOFF_BASE_S ** attempt + random.uniform(0, 1.0)
            print(f"  [retry {attempt}/{MAX_RETRIES}] {what} failed: {exc} -> sleep {sleep_s:.1f}s")
            time.sleep(sleep_s)
    raise RuntimeError(f"{what} failed after {MAX_RETRIES} attempts") from last


def run_ingest(config: IngestConfig) -> list[Path]:
    """Execute the batched ingest. Imports databento lazily (network required).

    Returns the list of written raw archive paths. ONE request per schema.
    """
    try:
        import databento as db  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on user env
        raise SystemExit(
            "The 'databento' package is required to run the ingest. Install the "
            "optional extra:  pip install -e '.[ingest]'"
        ) from exc

    client = db.Historical(config.api_key)
    plan = build_request_plan(
        config.start, config.end, schemas=config.schemas, symbols=config.symbols
    )
    print(f"Ingest plan: {len(plan)} request(s) (== {len(config.schemas)} schema(s)), "
          f"range {config.start}..{config.end}, symbols {list(config.symbols)}")

    written: list[Path] = []
    for i, spec in enumerate(plan):
        schema_dir = config.data_dir / spec.schema
        schema_dir.mkdir(parents=True, exist_ok=True)
        raw_path = schema_dir / f"{spec.stem}.dbn.zst"
        if raw_path.exists() and not config.force:
            print(f"  [skip] {raw_path} exists (use --force to refetch)")
            written.append(raw_path)
            continue

        def _pull() -> object:
            return client.timeseries.get_range(
                dataset=spec.dataset,
                schema=spec.schema,
                symbols=list(spec.symbols),
                stype_in=spec.stype_in,
                start=spec.start,
                end=spec.end,
            )

        print(f"  [{i + 1}/{len(plan)}] GET {spec.schema} {spec.start}..{spec.end}")
        store = _with_backoff(_pull, what=f"get_range({spec.schema})")
        store.to_file(str(raw_path))  # type: ignore[attr-defined]
        written.append(raw_path)
        _write_instrument_csvs(store, schema_dir, spec)

        if i < len(plan) - 1:
            time.sleep(INTER_REQUEST_DELAY_S)  # be polite between schemas

    print(f"Done. Wrote {len(written)} raw archive(s) under {config.data_dir}")
    return written


def _write_instrument_csvs(store: object, schema_dir: Path, spec: RequestSpec) -> None:
    """Split the single schema response into per-instrument decoded CSVs.

    No extra network requests: we decode the already-downloaded ``store``. The
    full decoded CSV is written once, then filtered per instrument by symbol
    root so the adapter can read ``<INSTR>_<START>_<END>.csv``.
    """
    import pandas as pd  # noqa: F401  # provided transitively by databento; import guards availability

    df = store.to_df(price_type="float", pretty_ts=True)  # type: ignore[attr-defined]
    if "symbol" not in df.columns:
        df = df.reset_index()
    stem_range = f"{spec.start.replace('-', '')}_{spec.end.replace('-', '')}"
    for instr in INSTRUMENTS:
        mask = df["symbol"].astype(str).str.upper().str.startswith(instr)
        sub = df[mask]
        out = schema_dir / f"{instr}_{stem_range}.csv"
        sub.to_csv(out, index=False)
        print(f"      wrote {out}  ({len(sub)} rows)")


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Batched Databento ingest (one request per schema).")
    p.add_argument("--start", default=DEV_START.isoformat(), help="inclusive YYYY-MM-DD")
    p.add_argument("--end", default=DEV_END.isoformat(), help="inclusive YYYY-MM-DD")
    p.add_argument("--data-dir", default=os.environ.get("DATA_DIR", "/data/raw"))
    p.add_argument("--schemas", nargs="*", default=list(DEFAULT_SCHEMAS))
    p.add_argument("--force", action="store_true", help="refetch even if cached")
    p.add_argument("--print-plan", action="store_true", help="print request plan and exit (no network)")
    return p.parse_args(list(argv))


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    if args.print_plan:
        plan = build_request_plan(args.start, args.end, schemas=args.schemas)
        print(f"{len(plan)} request(s) for {len(args.schemas)} schema(s):")
        for spec in plan:
            print(f"  - {spec.schema}: {spec.start}..{spec.end} symbols={list(spec.symbols)}")
        print("Extreme days to add for the golden dataset:")
        for day, why in EXTREME_DAYS:
            print(f"  - {day}: {why}")
        return 0

    api_key = os.environ.get("DATABENTO_API_KEY")
    if not api_key:
        print("ERROR: DATABENTO_API_KEY is not set. This script must be run by the "
              "user with a valid Databento key and subscription.", file=sys.stderr)
        return 2

    config = IngestConfig(
        api_key=api_key,
        data_dir=Path(args.data_dir),
        start=args.start,
        end=args.end,
        schemas=tuple(args.schemas),
        force=args.force,
    )
    run_ingest(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
