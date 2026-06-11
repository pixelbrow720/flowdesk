# 05 — Data & Feeds

## Source

**Databento, dataset `GLBX.MDP3`** (CME Globex). FlowDesk consumes four schemas:

| Schema | Purpose |
|---|---|
| `definition` | Instrument definitions: strike, right (C/P), expiry, multiplier, mapping `instrument_id` ↔ contract |
| `statistics` | Official stats incl. settlement and **open interest (OI)** — used for gamma-dollar walls |
| `trades` | Per-trade prints incl. **`side`** (aggressor B/A/N) — drives volume and HIRO |
| `mbp-1` / `bbo-1m` | Top-of-book quotes — mid price for IV; `bbo-1m` is the 1-minute BBO variant |

**Quote schema note:** the engine fixtures and adapter default to `mbp-1`. The
locked data-contract research (and the FE session generation here) also support
**`bbo-1m`**, which is sufficient for IV/mids. `bbo-1m` is **not** sufficient to
build HIRO — HIRO needs per-trade `trades.side`, which is why the HIRO path reads
`trades`, not quotes. `mbp-10` / deeper book are **not** required.

## Feed adapters

Source: `services/engine/src/engine/feed/`.

### `base.py`
The `FeedAdapter` interface the engine/worker codes against. Abstracts "give me
the chain + trades for instrument *I* at minute *m*."

### `historical.py` (working)
Replays stored DBN/fixture data minute-by-minute over the RTH window. This is
the path used today for development, the golden fixture, and FE session JSON.

### `live.py` (STUB)
`LiveAdapter` raises `LiveFeedNotAvailable`. Real-time streaming is **not
implemented**. `FEED_MODE` selects the adapter; only `historical` is functional.
Wiring a real live feed is a roadmap item ([`09-roadmap.md`](09-roadmap.md)).

## Ingest

### `scripts/ingest_databento.py`
Batched, cost-aware historical ingest. Default schemas:
`definition, statistics, trades, mbp-1`. The cost-optimal ingest design
(resolve per-session-date → pull by `instrument_id`; stream for MVP, per-day
batch for prod; bill only returned DBN bytes; respect Databento rate limits) is
documented in the research and in the user's Notion "Arsitektur Ingest Historis
Cost-Optimal" note. Honour those limits when extending ingest.

### `scripts/gen_session_snapshots.py`
Generates the per-session Snapshot JSON the frontend loads from
`apps/web/public/sessions/` (e.g. `ES_2026-06-09.json`). Re-run after any engine
change that affects Snapshot values:

```bash
cd services/engine && PYTHONPATH=src python scripts/gen_session_snapshots.py \
  --date 2026-06-09 --data-dir <ABS>/data/raw \
  --out ../../apps/web/public/sessions --quote-schema bbo-1m
```

### `scripts/validate.py`
Validation/utility entrypoint. NOTE: there is currently **no** quantitative
backtest that reconciles synthetic positioning vs. official ΔOI or tests whether
GEX predicts /ES price — that harness is the top backlog item
([`08-status-and-gaps.md`](08-status-and-gaps.md)).

## Fixtures

`tests/fixtures/raw/{definition,mbp-1,statistics,trades}/` hold the deterministic
sample chain used by engine tests and the golden snapshot. They use `trades` +
`mbp-1` (not `tbbo`, not `bbo-1m`).
