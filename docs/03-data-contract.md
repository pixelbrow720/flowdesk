# 03 — The Data Contract (`Snapshot`)

The `Snapshot` is the only artifact that crosses the engine → api → web boundary.
It is defined twice and the two definitions must stay identical:

- **Python (pydantic):** `services/engine/src/engine/schema.py`
- **TypeScript (zod):** `packages/contracts/src/snapshot.ts`
- **Canonical prose:** `packages/contracts/CONTRACT.md` (kept beside the zod file)

`schema_version` is **1**.

## Top-level shape

```jsonc
{
  "schema_version": 1,
  "instrument": "ES",            // "ES" | "NQ"
  "session_date": "2026-06-09",  // ET trading date
  "ts": "2026-06-09T13:31:00Z",  // snapshot timestamp (UTC)
  "minute_index": 1,             // minutes since RTH open (09:30 ET = 0)
  "state": "LIVE",               // PREMARKET | LIVE | STALE | CLOSED | HOLIDAY
  "stale": false,
  "expired": false,
  "forward": 5312.25,            // F used for pricing
  "rate": 0.0531,                // r = ln(1 + SOFR)

  "axis":   { "strike_min": 5200, "strike_max": 5450, "step": 5 },
  "regime": { "net_gamma": -1.2e9, "sign": -1, "stability_pct": 73.4 },

  "profile": [                   // one row per strike
    { "strike": 5300, "net_gex": 1.1e8, "net_dex": -4.2e7, "interpolated": false }
  ],

  "field": {                     // price × strike projection grid
    "price_grid": [ 5300.0, 5301.0 ],
    "gamma":      [ /* len == price_grid */ ],
    "delta":      [ /* len == price_grid */ ]
  },

  "levels": {
    "call_walls":  [ { "strike": 5350, "value": 1.0e8 } ],
    "put_walls":   [ { "strike": 5250, "value": 9.0e7 } ],
    "gamma_flip":  5312.0,
    "largest_gex": { "strike": 5350, "value": 1.0e8 },
    "largest_dex": { "strike": 5250, "value": 8.0e7 }
  },

  "ohlc": { "o": 5310, "h": 5315, "l": 5308, "c": 5312.25 },   // optional
  "hiro": { "total": 1234, "calls": 800, "puts": -200,         // optional
            "zerodte": 1100, "retail": 50 }
}
```

## Field notes

- **`minute_index`** — 0 at 09:30 ET; increments each RTH minute. Used by the FE
  timeline scrubber and by the session JSON fixtures.
- **`state` / `stale` / `expired`** — resolved by the API worker (the engine is
  calendar-free). The FE uses these to dim (`stale`) or freeze (`expired`/`CLOSED`).
- **`forward` / `rate`** — the exact inputs used for this snapshot's pricing, so
  the FE can label the surface and reproduce numbers.
- **`axis`** — strike bounds + step (5 for /ES, 10 for /NQ).
- **`regime`** — net gamma, its sign, and a `stability_pct` describing how stable
  the regime is across recent minutes.
- **`profile[]`** — per-strike `net_gex` / `net_dex` (VOL-based). `interpolated`
  flags strikes filled in where the chain was sparse.
- **`field`** — the heatmap source. **Invariant:**
  `len(price_grid) == len(gamma) == len(delta)`. Enforced in `schema.py`.
- **`levels`** — call/put walls (gamma-dollar, Top-3), gamma flip, largest
  GEX/DEX strikes.
- **`ohlc?`** — optional candle for the underlying that minute.
- **`hiro?`** — optional signed order-flow aggregate (see [`04-engine.md`](04-engine.md)).
  Absence is valid; consumers must treat it as "no HIRO this minute."

## Rules for changing the contract

1. Edit **both** `schema.py` and `snapshot.ts` in the same change.
2. Keep `CONTRACT.md` accurate.
3. New data → prefer an **optional** field (no version bump), following the
   `ohlc` / `hiro` precedent.
4. Regenerate the golden fixture (`tests/gen_golden.py`) and the FE session JSON
   (`scripts/gen_session_snapshots.py`).
5. Run `pnpm --filter @flowdesk/contracts validate` (accepts the example,
   rejects malformed input).
