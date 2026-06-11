"""Generate the synthetic Databento-shaped CSV fixture for test_historical.

Writes a small, deterministic cache under ``tests/fixtures/raw`` mirroring the
layout HistoricalSimAdapter expects:

    tests/fixtures/raw/
      definition/ES_20260610_20260610.csv
      statistics/ES_20260610_20260610.csv
      trades/ES_20260610_20260610.csv
      mbp-1/ES_20260610_20260610.csv

The data describes a single ES 0DTE session (2026-06-10) with a front future and
5 strikes (4990..5010) of calls + puts, priced so the chain is well-formed at
the sample minute 09:31 ET (13:31 UTC). Re-run:  python tests/gen_fixture.py
"""
from __future__ import annotations

import csv
from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "raw"

INSTR = "ES"
START = "20260610"
END = "20260610"
EXPIRY = "2026-06-10T20:00:00.000000000Z"  # 16:00 ET 0DTE expiry
FUT_EXPIRY = "2026-06-19T13:30:00.000000000Z"  # front quarterly future

FUTURE_ID = 1
FORWARD = 5000.0
STRIKES = [4990.0, 4995.0, 5000.0, 5005.0, 5010.0]

# Deterministic per-strike (call_oi, put_oi, call_vol, put_vol) and a mid offset.
# Call wall should land above forward, put wall below (verified in the test).
_PER_STRIKE = {
    4990.0: dict(call_oi=400, put_oi=1500, call_vol=120, put_vol=900, call_mid=14.0, put_mid=4.0),
    4995.0: dict(call_oi=600, put_oi=1200, call_vol=200, put_vol=700, call_mid=10.5, put_mid=5.5),
    5000.0: dict(call_oi=900, put_oi=900, call_vol=500, put_vol=500, call_mid=7.5, put_mid=7.5),
    5005.0: dict(call_oi=1300, put_oi=500, call_vol=800, put_vol=240, call_mid=5.5, put_mid=10.5),
    5010.0: dict(call_oi=1700, put_oi=350, call_vol=950, put_vol=110, call_mid=4.0, put_mid=14.0),
}


def _iid(strike: float, kind: str) -> int:
    base = int((strike - 4990.0) / 5.0) * 2 + 10
    return base + (0 if kind == "call" else 1)


def _write(schema: str, header: list[str], rows: list[list[object]]) -> Path:
    d = FIXTURE_DIR / schema
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{INSTR}_{START}_{END}.csv"
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)
    return path


def generate() -> list[Path]:
    written: list[Path] = []

    # -- definition -------------------------------------------------------
    defs: list[list[object]] = [
        [FUTURE_ID, "ESM6", "F", "", FUT_EXPIRY, "ES"],
    ]
    for k in STRIKES:
        defs.append([_iid(k, "call"), f"ES C{int(k)}", "C", k, EXPIRY, "ES"])
        defs.append([_iid(k, "put"), f"ES P{int(k)}", "P", k, EXPIRY, "ES"])
    written.append(_write(
        "definition",
        ["instrument_id", "raw_symbol", "instrument_class", "strike_price", "expiration", "underlying"],
        defs,
    ))

    # -- statistics (open interest @ 13:00Z prior settle; future settle) ---
    stats: list[list[object]] = [
        ["2026-06-10T13:00:00.000000000Z", FUTURE_ID, 3, FORWARD, 0],  # settlement
    ]
    for k in STRIKES:
        p = _PER_STRIKE[k]
        stats.append(["2026-06-10T13:00:00.000000000Z", _iid(k, "call"), 9, "", p["call_oi"]])
        stats.append(["2026-06-10T13:00:00.000000000Z", _iid(k, "put"), 9, "", p["put_oi"]])
    written.append(_write(
        "statistics",
        ["ts_event", "instrument_id", "stat_type", "price", "quantity"],
        stats,
    ))

    # -- trades (one trade at 13:30:30Z, inside RTH, <= sample minute) -----
    # ``side`` is the CME aggressor (B=buy-aggressor, A=sell-aggressor) consumed
    # by HIRO: calls bought (B), puts sold (A) -> net positive dealer hedging.
    trades: list[list[object]] = []
    for k in STRIKES:
        p = _PER_STRIKE[k]
        trades.append(["2026-06-10T13:30:30.000000000Z", _iid(k, "call"), "B", p["call_mid"], p["call_vol"]])
        trades.append(["2026-06-10T13:30:30.000000000Z", _iid(k, "put"), "A", p["put_mid"], p["put_vol"]])
    # A pre-open trade that must be EXCLUDED from cumulative VOL (13:00Z < RTH).
    trades.append(["2026-06-10T13:00:00.000000000Z", _iid(5000.0, "call"), "B", 7.5, 999])
    written.append(_write(
        "trades",
        ["ts_event", "instrument_id", "side", "price", "size"],
        trades,
    ))

    # -- mbp-1 (top of book @ 13:30:45Z, <= sample minute) -----------------
    quotes: list[list[object]] = [
        ["2026-06-10T13:30:45.000000000Z", FUTURE_ID, FORWARD - 0.25, FORWARD + 0.25],
    ]
    for k in STRIKES:
        p = _PER_STRIKE[k]
        quotes.append(["2026-06-10T13:30:45.000000000Z", _iid(k, "call"), p["call_mid"] - 0.5, p["call_mid"] + 0.5])
        quotes.append(["2026-06-10T13:30:45.000000000Z", _iid(k, "put"), p["put_mid"] - 0.5, p["put_mid"] + 0.5])
    written.append(_write(
        "mbp-1",
        ["ts_event", "instrument_id", "bid_px_00", "ask_px_00"],
        quotes,
    ))
    return written


if __name__ == "__main__":
    for p in generate():
        print("wrote", p)
