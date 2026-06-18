# 05 — Data & Feeds

## Source

**Databento, dataset `GLBX.MDP3`** (CME Globex). FlowDesk consumes four schemas:

| Schema | Purpose |
|---|---|
| `definition` | Instrument definitions: strike, right (C/P), expiry, multiplier, mapping `instrument_id` ↔ contract |
| `statistics` | Official stats incl. settlement and **open interest (OI)** — used for gamma-dollar walls |
| `trades` | Per-trade prints incl. **`side`** (aggressor B/A/N) — drives volume and FLUX |
| `mbp-1` / `bbo-1m` | Top-of-book quotes — mid price for IV; `bbo-1m` is the 1-minute BBO variant |

**Quote schema note:** the engine fixtures and adapter default to `mbp-1`. The
locked data-contract research (and the session-snapshot generation here) also
support **`bbo-1m`**, which is sufficient for IV/mids. `bbo-1m` is **not**
sufficient to build FLUX — FLUX needs per-trade `trades.side`, which is why the
FLUX path reads `trades`, not quotes. `mbp-10` / deeper book are **not** required.

## Feed adapters

Source: `services/engine/src/engine/feed/`.

### `base.py`
The `FeedAdapter` interface the engine/worker codes against. Abstracts "give me
the chain + trades for instrument *I* at minute *m*."

### `historical.py` (working)
Replays stored DBN/fixture data minute-by-minute over the RTH window. This is
the path used today for development, the golden fixture, and session-snapshot JSON.

### `live.py` (real, with safety rail)
`LiveAdapter` is a real-time Databento adapter, but its contact with the live
account is **gated by a two-key arming rail** (`FEED_MODE=live` **and**
`LIVE_FEED_ARMED=1`). Without both keys, `make_adapter("live")` raises
`LiveFeedNotArmed`. The shell is fully implemented (databento `Live`
subscription + four schemas: `definition`, `statistics`, `trades`, `mbp-1`),
and the per-minute chain assembly lives in a separate, unit-tested
`engine.feed.live_book.LiveBook` (pure Python, network-free) — the
test seam substitutes a hand-rolled `FakeLiveClient`. Built-in circuit
breaker (`_BreakerState`): 5 consecutive `_connect()` failures within a
5-minute rolling window opens the breaker permanently (raises
`LiveFeedDegraded`) — no auto-recovery, humans only. Bounded reconnect:
5 attempts, exponential backoff capped at 60s, 5-minute total wall budget.
The minute-assembly logic (definition + OI + cumulative VOL + top-of-book
mid wired to the realtime stream) ships in a follow-up; the
`FakeLiveClient` seam means that code can be developed against recorded
fixtures. See `docs/architecture/live-feed-threat-model.md` for the F1–F7
failure catalogue and the arming rail rationale.

**Production posture:** the beta image intentionally does **not** set
`LIVE_FEED_ARMED=1`. Flipping it requires the operator runbook procedure
(see `docs/ops/deploy-runbook.md`). Until that arm happens, `FEED_MODE=live`
on the worker raises `LiveFeedNotArmed` at boot — `historical` is the
only functional mode.

## Ingest

### `scripts/ingest_databento.py`
Batched, cost-aware historical ingest. Default schemas:
`definition, statistics, trades, mbp-1`. The cost-optimal ingest design
(resolve per-session-date → pull by `instrument_id`; stream for MVP, per-day
batch for prod; bill only returned DBN bytes; respect Databento rate limits) is
documented in the research and in the user's Notion "Arsitektur Ingest Historis
Cost-Optimal" note. Honour those limits when extending ingest.

### `scripts/gen_session_snapshots.py`
Generates per-session Snapshot JSON (e.g. `ES_2026-06-09.json`) for offline
consumption by REST/WS clients. Re-run after any engine change that affects
Snapshot values:

```bash
cd services/engine && PYTHONPATH=src python scripts/gen_session_snapshots.py \
  --date 2026-06-09 --data-dir <ABS>/data/raw \
  --out <output-dir> --quote-schema bbo-1m
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
