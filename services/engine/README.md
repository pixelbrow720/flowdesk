# FlowDesk — Task 0.9 (PRD step 1.4): Feed adapters + Databento ingest

Implements the **feed layer** (PRD #8 §8–§9): one `FeedAdapter` interface with
two implementations, plus a rate-limit-safe Databento batch-ingest script.

```
Databento GLBX.MDP3  ->  FeedAdapter (historical | live)  ->  OptionChainMinute
                                                              -> to_engine_chain()
                                                              -> engine.build_snapshot()
```

> **Release note:** sequential release **0.9** (after 0.8). “1.4” is the PRD
> pipeline step ID for the feed layer, not the release number. Package version
> in `pyproject.toml` is `0.9.0`.

## Patch contents

```
flowdesk-0.9-feed/
└── services/engine/
    ├── pyproject.toml                       # flowdesk-engine → 0.9.0 (+ [ingest] extra)
    ├── src/engine/
    │   ├── feed/
    │   │   ├── __init__.py                  # make_adapter(FEED_MODE) factory (AC-A3)
    │   │   ├── base.py                      # FeedAdapter ABC + OptionChainMinute (locked shape)
    │   │   ├── historical.py                # HistoricalSimAdapter (reads DATA_DIR cache)
    │   │   └── live.py                      # LiveAdapter stub (FEED_MODE=live)
    │   ├── snapshot.py schema.py black76.py iv.py exposure.py field.py levels.py   # engine 0.8 (bundled)
    │   └── __init__.py
    ├── scripts/
    │   └── ingest_databento.py             # BATCHED ingest: 1 request per schema
    └── tests/
        ├── test_historical.py
        ├── gen_fixture.py                  # regenerates the synthetic fixture
        └── fixtures/raw/                   # BUNDLED synthetic Databento-shaped CSVs
            ├── definition/ES_20260610_20260610.csv
            ├── statistics/ES_20260610_20260610.csv
            ├── trades/ES_20260610_20260610.csv
            └── mbp-1/ES_20260610_20260610.csv
```

The full engine (0.8) is bundled so the feed adapter and its engine-consumption
test run standalone.

## The locked chain contract (PRD #8 §8)

`OptionChainMinute` — emitted IDENTICALLY by both adapters:

| field | type | meaning |
|---|---|---|
| `ts` | aware UTC datetime, minute-aligned | the minute |
| `forward` | float | underlying futures price F |
| `rows` | tuple[`ChainRow`] | per-leg rows |

`ChainRow` = `strike, type("call"|"put"), bid, ask, volume, oi` (exactly the
locked fields). `.mid = (bid+ask)/2` or `None` when a side is missing/crossed.

`to_engine_chain(chain, t_expiry=...)` bridges this to the engine's per-strike
`ChainQuote` (groups legs by strike) so `build_snapshot` (0.8) consumes it directly.

## Adapters

* **`HistoricalSimAdapter(data_dir)`** — `FEED_MODE=historical`. Reads cached
  Databento exports and assembles the chain for a minute from
  **definition** (strike/type/expiry + the future) + **statistics** (OI) +
  **trades** (cumulative VOL since the 09:30 ET RTH open) + **mbp-1/bbo** (mid).
* **`LiveAdapter`** — `FEED_MODE=live`. Interface-compatible **stub**; documents
  exactly where the realtime `databento.Live` subscription attaches. Raises
  `LiveFeedNotAvailable` on data calls (no network in the sandbox).
* **`make_adapter(FEED_MODE, data_dir=?, api_key=?)`** picks the implementation
  from a single env var — nothing else changes when the mode flips (AC-A3).

### Expected on-disk cache layout (read by HistoricalSimAdapter)

```
DATA_DIR/
  definition/<INSTR>_<START>_<END>.csv
  statistics/<INSTR>_<START>_<END>.csv
  trades/<INSTR>_<START>_<END>.csv
  mbp-1/<INSTR>_<START>_<END>.csv      # or bbo-1m (quote_schema="bbo-1m")
```

`<INSTR>` ∈ {ES, NQ}; `<START>`/`<END>` = `YYYYMMDD` (inclusive). CSVs are the
*decoded* Databento exports (`DBNStore.to_csv(pretty_px=True, pretty_ts=True)`):
real-unit prices, ISO-8601 UTC timestamps. Columns consumed (extras ignored):

| schema | columns |
|---|---|
| definition | `instrument_id, raw_symbol, instrument_class, strike_price, expiration, underlying` |
| statistics | `ts_event, instrument_id, stat_type, price, quantity` (`stat_type` 9 = OI, 3 = settlement) |
| trades | `ts_event, instrument_id, price, size` |
| mbp-1/bbo | `ts_event, instrument_id, bid_px_00, ask_px_00` |

## Databento batch-ingest (`scripts/ingest_databento.py`)

**Anti-block golden rule (PRD #8 §9 / AC-A7):** one **schema** = one **full
date-range** request, for ALL symbols at once. 4 schemas → **4 requests total**.
Never loop per day.

* `build_request_plan(start, end, schemas=...)` — pure/offline; returns exactly
  one `RequestSpec` per schema (this is what the test asserts).
* `run_ingest(config)` — lazily imports `databento`, pulls once per schema with
  `INTER_REQUEST_DELAY_S` spacing + exponential backoff/jitter, writes the raw
  `.dbn.zst` per schema, and splits per-instrument decoded CSVs from the SAME
  response (no extra requests). Idempotent (skips cached files unless `--force`).
* **Must be run by the user** with `DATABENTO_API_KEY` + a GLBX.MDP3
  subscription. No network is touched in the sandbox / on import.
* Ships **5 dev days** (`2026-06-01..2026-06-05`) and notes **3 extreme days**
  (OPEX, trending/high-vol, half-day) for the golden dataset.

```bash
# Preview the request plan WITHOUT network:
python scripts/ingest_databento.py --print-plan

# Real pull (user machine, with key):
export DATABENTO_API_KEY=db-xxxx DATA_DIR=/data/raw
pip install -e ".[ingest]"
python scripts/ingest_databento.py --start 2026-06-01 --end 2026-06-05
```

## Setup & run

```bash
cd services/engine
python -m venv .venv && source .venv/bin/activate   # Python >=3.11,<3.13
pip install -e ".[dev]"          # numpy, pydantic, tzdata (+ pytest, ruff, mypy)

# Regenerate the bundled fixture (optional — it is already committed):
PYTHONPATH=src:tests python tests/gen_fixture.py

# Run the feed tests:
pytest tests/test_historical.py -q
```

## Manual verification checklist

- [x] `python -m py_compile` over feed modules, ingest script, tests → OK.
- [x] **Well-formed chain:** `get_chain("ES", 13:31Z)` → 5 strikes, each with a
      call+put leg, positive mid/volume/OI; `ts` minute-aligned; `forward=5000`.
- [x] **Cumulative VOL** since 09:30 ET excludes the pre-open trade.
- [x] **One interface:** both adapters are `FeedAdapter`; `make_adapter` selects
      by `FEED_MODE`; `LiveAdapter` raises `LiveFeedNotAvailable` on data calls.
- [x] **Batched ingest:** `build_request_plan` returns exactly one request per
      schema over the full range (AC-A7); 3 extreme days noted.
- [x] **Engine consumption:** `to_engine_chain` → `build_snapshot` returns a
      valid Snapshot (schema_version 1, minute_index 1, walls 5010/4990).
- [x] Inline harness (pytest not installed in sandbox): **all tests PASS**.

## Assumptions

* **File paths:** the task asked for `feed/` + `scripts/`; the PRD tree (§1)
  sketches `engine/feed` + `engine/io/databento_ingest.py`. I followed the task:
  `engine/feed/{base,historical,live}.py` and `scripts/ingest_databento.py`.
  The locked `OptionChainMinute` field set is unchanged.
* **Adapter reads decoded CSVs**, not raw `.dbn`: keeps the adapter + tests
  dependency-free (no `databento` binary decoder needed offline). The ingest
  script writes both the raw `.dbn.zst` archive and the per-instrument CSV cache.
* **0DTE expiry selection:** options whose expiry date == the session date;
  else the nearest expiry ≥ session date. `get_expiry()` exposes it so the
  orchestrator can compute the snapshot-level `t_expiry` (ACT/365).
* **Forward** = front-future mid from mbp-1 (nearest expiry ≥ ts); falls back to
  the latest settlement price.
* **OI** = latest `OPEN_INTEREST` statistic ≤ ts (prior-session settle is fine);
  **VOL** = sum of trade sizes in `[RTH open, ts]` (09:30 ET, locked).
* **Parent symbology** (`ES.OPT/ES.FUT/NQ.OPT/NQ.FUT`, `stype_in="parent"`) for
  the ingest; instrument membership matched by symbol root.
* **`databento` pin (`==0.34.0`)** is the only dependency I could not verify
  online from the sandbox; it lives in the optional `[ingest]` extra (never
  imported by the engine/adapter/tests). Confirm/adjust against your Databento
  account's supported SDK before the live pull.

## TODO-FROM-OWNER

* `DATABENTO_API_KEY` + active **GLBX.MDP3** subscription (to run the ingest).
* Confirm the **5 dev days** are real trading sessions and pick the **2–3
  extreme days** (OPEX / trending / half-day) for the golden dataset.
* `SOFR_RATE` (engine uses `r = ln(1 + SOFR)`); the test uses a placeholder.
